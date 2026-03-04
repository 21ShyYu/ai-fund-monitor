from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class SignalOutput:
    confidence: float
    signal: str
    reason: str
    risk_hint: str
    drawdown_pct: float


def calc_drawdown(price_rows: list[dict[str, Any]]) -> float:
    if len(price_rows) < 2:
        return 0.0
    navs = np.array([float(x["nav"]) for x in price_rows], dtype=float)
    peaks = np.maximum.accumulate(navs)
    drawdowns = np.where(peaks > 0, (peaks - navs) / peaks, 0.0)
    return float(np.max(drawdowns))


def decide_signal(
    strategy: dict[str, Any],
    pred_return: float,
    pred_vol: float,
    model_consistency: float,
    feature_quality: float,
    news_agreement: float,
    data_freshness: float,
    hot_risk: float,
    drawdown_pct: float,
) -> SignalOutput:
    confidence = 100.0 * (
        0.45 * model_consistency
        + 0.25 * feature_quality
        + 0.20 * news_agreement
        + 0.10 * data_freshness
    )
    confidence = max(0.0, min(100.0, confidence))

    rules = strategy.get("signal_rules", {})
    max_dd_limit = float(strategy.get("risk", {}).get("max_drawdown_limit", 0.08))
    dd_triggered = drawdown_pct > max_dd_limit

    add_thr = float(rules.get("add_position_pred_return_gt", 0.012))
    clear_thr = float(rules.get("clear_position_pred_return_lt", -0.015))
    reduce_low = float(rules.get("reduce_range_low", -0.008))
    reduce_high = float(rules.get("reduce_range_high", 0.005))
    add_conf = float(rules.get("add_position_confidence_gte", 70))
    reduce_conf = float(rules.get("reduce_position_confidence_lt", 60))
    hot_add_max = float(rules.get("add_position_hot_risk_lt", 0.4))
    hot_reduce_min = float(rules.get("reduce_position_hot_risk_gte", 0.5))

    signal = "HOLD"
    reason = "No strong edge."
    risk_hint = _risk_hint(pred_vol, hot_risk, drawdown_pct, max_dd_limit)

    if pred_return < clear_thr or dd_triggered:
        signal = "CLEAR"
        reason = "Predicted downside or drawdown control triggered."
    elif (
        pred_return > add_thr
        and confidence >= add_conf
        and hot_risk < hot_add_max
        and not dd_triggered
    ):
        signal = "ADD"
        reason = "Positive expected return with acceptable risk."
    elif (
        reduce_low <= pred_return <= reduce_high
        or confidence < reduce_conf
        or hot_risk >= hot_reduce_min
    ):
        signal = "REDUCE"
        reason = "Weak edge or elevated risk indicators."

    return SignalOutput(
        confidence=round(confidence, 2),
        signal=signal,
        reason=reason,
        risk_hint=risk_hint,
        drawdown_pct=round(drawdown_pct, 4),
    )


def calc_news_scores(news_items: list[dict[str, Any]]) -> tuple[float, float]:
    if not news_items:
        return 0.5, 0.2
    text = " ".join((x.get("title", "") + " " + x.get("summary", "")).lower() for x in news_items)
    positive_kw = ["上涨", "回暖", "利好", "增长", "修复", "反弹", "improve", "growth"]
    negative_kw = ["下跌", "暴跌", "利空", "风险", "波动", "监管", "tightening", "risk"]
    pos_hits = sum(text.count(k) for k in positive_kw)
    neg_hits = sum(text.count(k) for k in negative_kw)
    total = max(1, pos_hits + neg_hits)
    sentiment = 0.5 + (pos_hits - neg_hits) / (2 * total)
    sentiment = max(0.0, min(1.0, sentiment))
    # More negative concentration means higher hot risk.
    hot_risk = max(0.0, min(1.0, neg_hits / total))
    return sentiment, hot_risk


def _risk_hint(pred_vol: float, hot_risk: float, dd: float, dd_limit: float) -> str:
    hints: list[str] = []
    if pred_vol > 0.015:
        hints.append("Predicted volatility is high.")
    if hot_risk > 0.6:
        hints.append("News risk concentration is elevated.")
    if dd > dd_limit:
        hints.append("Portfolio drawdown exceeds configured limit.")
    if not hints:
        hints.append("Risk is within configured tolerance.")
    return " ".join(hints)

