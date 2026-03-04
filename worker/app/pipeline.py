from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import ROOT_DIR, Settings
from .db import (
    get_conn,
    get_latest_signals,
    get_recent_news,
    get_recent_predictions,
    get_recent_prices,
    init_schema,
    insert_job_log,
    insert_news,
    insert_prediction,
    upsert_price,
)
from .exporter import export_frontend_json, git_auto_push
from .features import build_feature_vector
from .feishu import send_text
from .llm import generate_report
from .predictor import ModelLoadError, predict_from_models
from .risk import calc_drawdown, calc_news_scores, decide_signal
from .sources import fetch_fund_snapshot, fetch_news


CN_SIGNAL_MAP = {"ADD": "加仓", "REDUCE": "减仓", "CLEAR": "清仓", "HOLD": "观望"}


def run_pipeline() -> None:
    settings = Settings.load()
    conn = get_conn(settings.db_path)
    try:
        schema_sql = (ROOT_DIR / "worker" / "sql" / "schema.sql").read_text(encoding="utf-8")
        init_schema(conn, schema_sql)

        funds = settings.load_funds()
        strategy = settings.load_strategy()
        news_sources = settings.load_news_sources()
        now = datetime.now().isoformat(timespec="seconds")

        errors: list[str] = []

        for fund in funds:
            code = fund["code"]
            name = fund["name"]
            try:
                px = fetch_fund_snapshot(code)
                upsert_price(
                    conn,
                    fund_code=code,
                    fund_name=name,
                    nav=float(px["nav"]),
                    daily_change_pct=float(px["daily_change_pct"]),
                    observed_at=str(px["observed_at"]),
                )
            except Exception as exc:
                msg = f"Price fetch failed [{code}]: {exc}"
                errors.append(msg)
                insert_job_log(conn, "price_fetch", "FAILED", msg)

        news_items, news_errors = fetch_news(news_sources)
        for e in news_errors:
            errors.append(e)
            insert_job_log(conn, "news_fetch", "WARN", e)
        for n in news_items:
            insert_news(
                conn,
                title=n["title"],
                summary=n["summary"],
                source=n["source"],
                published_at=n["published_at"],
                category=n["category"],
            )

        recent_news = get_recent_news(conn, limit=250)
        if not recent_news:
            msg = "No news data was fetched in this run."
            errors.append(msg)
            insert_job_log(conn, "news_fetch", "FAILED", msg)
        news_agreement, hot_risk = calc_news_scores(recent_news)
        data_freshness = 1.0

        predicted_count = 0
        for fund in funds:
            code = fund["code"]
            prices = get_recent_prices(conn, code, limit=60)
            if len(prices) < 10:
                msg = f"Insufficient price history [{code}]: {len(prices)} rows (<10)"
                errors.append(msg)
                insert_job_log(conn, "predict", "FAILED", msg)
                continue
            try:
                features = build_feature_vector(prices)
                model_out = predict_from_models(settings.model_dir, code, features, prices)
                dd = calc_drawdown(prices)
                signal = decide_signal(
                    strategy=strategy,
                    pred_return=model_out.pred_return,
                    pred_vol=model_out.pred_vol,
                    model_consistency=model_out.model_consistency,
                    feature_quality=model_out.feature_quality,
                    news_agreement=news_agreement,
                    data_freshness=data_freshness,
                    hot_risk=hot_risk,
                    drawdown_pct=dd,
                )
                insert_prediction(
                    conn,
                    fund_code=code,
                    pred_return=model_out.pred_return,
                    pred_vol=model_out.pred_vol,
                    confidence=signal.confidence,
                    signal=signal.signal,
                    reason=signal.reason,
                    risk_hint=signal.risk_hint,
                    created_at=now,
                )
                predicted_count += 1
            except ModelLoadError as exc:
                msg = f"Model error [{code}]: {exc}"
                errors.append(msg)
                insert_job_log(conn, "predict", "FAILED", msg)
            except Exception as exc:
                msg = f"Prediction failed [{code}]: {exc}"
                errors.append(msg)
                insert_job_log(conn, "predict", "FAILED", msg)

        latest = get_latest_signals(conn)
        history = get_recent_predictions(conn, limit=250)
        if predicted_count == 0:
            msg = "No valid predictions generated in this run."
            errors.append(msg)
            insert_job_log(conn, "pipeline", "FAILED", msg)

        signals_payload = []
        for x in latest:
            signals_payload.append(
                {
                    "fund_code": x["fund_code"],
                    "signal": x["signal"],
                    "signal_cn": CN_SIGNAL_MAP.get(x["signal"], x["signal"]),
                    "confidence": x["confidence"],
                    "pred_return_pct": round(float(x["pred_return"]) * 100, 2),
                    "risk_hint": x["risk_hint"],
                }
            )
        report = ""
        if predicted_count > 0:
            try:
                report = generate_report(
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url,
                    model=settings.llm_model,
                    timeout_sec=settings.llm_timeout_sec,
                    input_payload={"signals": signals_payload, "news_count": len(recent_news)},
                )
            except Exception as exc:
                msg = f"LLM report failed: {exc}"
                errors.append(msg)
                insert_job_log(conn, "llm", "FAILED", msg)
                report = ""

        _send_feishu(settings, report, signals_payload, errors)

        export_frontend_json(settings.export_dir, latest, history, recent_news)
        if settings.github_auto_push:
            git_auto_push(Path(ROOT_DIR), settings.github_branch)

        status = "SUCCESS" if predicted_count > 0 and not errors else "PARTIAL"
        insert_job_log(
            conn,
            "pipeline",
            status,
            f"funds={len(funds)}, news={len(news_items)}, predicted={predicted_count}, errors={len(errors)}",
        )
    except Exception as exc:
        insert_job_log(conn, "pipeline", "FAILED", str(exc))
        raise
    finally:
        conn.close()


def _send_feishu(
    settings: Settings, report: str, signals_payload: list[dict[str, object]], errors: list[str]
) -> None:
    lines = ["基金预测日报", ""]
    if signals_payload:
        lines.append("信号结果：")
        for x in signals_payload:
            lines.append(
                f"- {x['fund_code']}: {x['signal_cn']} | 置信度 {x['confidence']} | 预测收益 {x['pred_return_pct']}%"
            )
    else:
        lines.append("信号结果：无（本轮未生成有效预测）")
    if report:
        lines.extend(["", "LLM总结：", report])
    else:
        lines.extend(["", "LLM总结：未生成（请检查 LLM 配置或接口状态）"])
    if errors:
        lines.extend(["", "异常提示："])
        for e in errors[:20]:
            lines.append(f"- {e}")
    send_text(settings.feishu_webhook, "基金预测日报", "\n".join(lines))
