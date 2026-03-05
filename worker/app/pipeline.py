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
        fund_name_map = {str(x.get("code", "")): str(x.get("name", "")) for x in funds}
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

        recent_news = get_recent_news(conn, limit=300)
        ranked_news = _prioritize_news(recent_news, funds, limit=250)
        if not ranked_news:
            msg = "No news data was fetched in this run."
            errors.append(msg)
            insert_job_log(conn, "news_fetch", "FAILED", msg)
        news_agreement, hot_risk = calc_news_scores(ranked_news)
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
                    "fund_name": fund_name_map.get(str(x["fund_code"]), ""),
                    "signal": x["signal"],
                    "signal_cn": CN_SIGNAL_MAP.get(x["signal"], x["signal"]),
                    "confidence": x["confidence"],
                    "pred_return_pct": round(float(x["pred_return"]) * 100, 2),
                    "risk_hint": x["risk_hint"],
                }
            )

        llm_fund_payload = []
        for fund in funds:
            code = str(fund["code"])
            prices = get_recent_prices(conn, code, limit=5)
            if not prices:
                continue
            latest_price = prices[-1]
            llm_fund_payload.append(
                {
                    "fund_code": code,
                    "fund_name": fund_name_map.get(code, ""),
                    "latest_nav": float(latest_price["nav"]),
                    "latest_daily_change_pct": float(latest_price["daily_change_pct"]),
                    "observed_at": str(latest_price["observed_at"]),
                    "recent_nav_series": [round(float(x["nav"]), 6) for x in prices],
                }
            )
        llm_news_payload = [
            {
                "published_at": str(x.get("published_at", "")),
                "source": str(x.get("source", "")),
                "title": str(x.get("title", "")),
                "summary": str(x.get("summary", ""))[:160],
            }
            for x in ranked_news[:20]
        ]

        report = ""
        if llm_fund_payload:
            try:
                report = generate_report(
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url,
                    model=settings.llm_model,
                    timeout_sec=settings.llm_timeout_sec,
                    input_payload={
                        "rule": "只允许基于最近净值和当前时政热点生成研判，不可引用XGBoost结果",
                        "funds": llm_fund_payload,
                        "political_news": llm_news_payload,
                    },
                )
            except Exception as exc:
                msg = f"LLM report failed: {exc}"
                errors.append(msg)
                insert_job_log(conn, "llm", "FAILED", msg)
                report = ""

        _send_feishu(settings, report, signals_payload, errors)

        export_frontend_json(settings.export_dir, latest, history, ranked_news)
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
        lines.append("XGBoost信号结果：")
        for x in signals_payload:
            display_name = str(x.get("fund_name", "")).strip()
            code = str(x["fund_code"])
            name_with_code = f"{display_name}({code})" if display_name else code
            lines.append(
                f"- {name_with_code}: {x['signal_cn']} | 置信度 {x['confidence']} | 预测收益 {x['pred_return_pct']}%"
            )
    else:
        lines.append("XGBoost信号结果：无（本轮未生成有效预测）")

    if report:
        lines.extend(["", "LLM总结：", report])
    else:
        lines.extend(["", "LLM总结：未生成（请检查 LLM 配置或接口状态）"])

    if errors:
        lines.extend(["", "异常提示："])
        for e in errors[:20]:
            lines.append(f"- {e}")

    send_text(settings.feishu_webhook, "基金预测日报", "\n".join(lines))


def _prioritize_news(
    news_items: list[dict[str, object]],
    funds: list[dict[str, object]],
    limit: int = 250,
) -> list[dict[str, object]]:
    if not news_items:
        return []
    keywords = _build_news_keywords(funds)
    scored: list[tuple[float, str, dict[str, object]]] = []
    for row in news_items:
        title = str(row.get("title", ""))
        summary = str(row.get("summary", ""))
        text = f"{title} {summary}".lower()
        title_low = title.lower()
        score = 0.0
        for kw, weight in keywords:
            if kw in text:
                score += weight
                if kw in title_low:
                    score += weight * 0.7
        published_at = str(row.get("published_at", ""))
        scored.append((score, published_at, row))

    has_relevant = any(s > 0 for s, _, _ in scored)
    if has_relevant:
        filtered = [x for x in scored if x[0] > 0]
    else:
        filtered = scored

    filtered.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [x[2] for x in filtered[:limit]]


def _build_news_keywords(funds: list[dict[str, object]]) -> list[tuple[str, float]]:
    weighted_keywords: dict[str, float] = {
        "白酒": 3.0,
        "消费": 2.6,
        "食品饮料": 2.6,
        "茅台": 2.8,
        "五粮液": 2.8,
        "泸州老窖": 2.8,
        "洋河": 2.4,
        "油价": 3.2,
        "原油": 3.2,
        "黄金": 3.2,
        "美元": 2.6,
        "美债": 2.6,
        "利率": 2.4,
        "加息": 3.2,
        "降息": 3.0,
        "通胀": 3.0,
        "衰退": 2.6,
        "地缘": 3.2,
        "战争": 3.5,
        "冲突": 2.8,
        "制裁": 2.8,
        "俄乌": 3.4,
        "中东": 3.4,
        "关税": 2.4,
        "汇率": 2.4,
        "risk": 1.8,
        "war": 2.0,
        "oil": 2.2,
        "gold": 2.2,
        "inflation": 2.0,
        "rate": 1.6,
        "fed": 2.0,
    }

    for fund in funds:
        code = str(fund.get("code", "")).strip()
        name = str(fund.get("name", "")).strip()
        if code:
            weighted_keywords[code.lower()] = max(weighted_keywords.get(code.lower(), 0.0), 2.8)
        if name:
            lowered = name.lower()
            weighted_keywords[lowered] = max(weighted_keywords.get(lowered, 0.0), 2.6)
            if "白酒" in name or "酒" in name:
                weighted_keywords["白酒"] = max(weighted_keywords["白酒"], 3.2)
            if "消费" in name:
                weighted_keywords["消费"] = max(weighted_keywords["消费"], 3.0)
            if "黄金" in name:
                weighted_keywords["黄金"] = max(weighted_keywords["黄金"], 3.4)
            if "原油" in name or "石油" in name:
                weighted_keywords["原油"] = max(weighted_keywords["原油"], 3.4)
                weighted_keywords["油价"] = max(weighted_keywords["油价"], 3.4)

    items = [(k, v) for k, v in weighted_keywords.items() if k]
    items.sort(key=lambda x: x[1], reverse=True)
    return items
