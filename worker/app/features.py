from __future__ import annotations

from typing import Any

import numpy as np


def build_feature_vector(price_rows: list[dict[str, Any]]) -> dict[str, float]:
    if not price_rows:
        return {
            "mean_return_5": 0.0,
            "mean_return_10": 0.0,
            "vol_10": 0.0,
            "momentum_5": 0.0,
            "latest_nav": 0.0,
        }

    returns = np.array([float(x["daily_change_pct"]) / 100.0 for x in price_rows], dtype=float)
    navs = np.array([float(x["nav"]) for x in price_rows], dtype=float)

    def _mean_last(arr: np.ndarray, n: int) -> float:
        if arr.size == 0:
            return 0.0
        return float(np.mean(arr[-n:]))

    def _std_last(arr: np.ndarray, n: int) -> float:
        if arr.size == 0:
            return 0.0
        return float(np.std(arr[-n:]))

    momentum_5 = 0.0
    if navs.size >= 6 and navs[-6] != 0:
        momentum_5 = float((navs[-1] - navs[-6]) / navs[-6])

    return {
        "mean_return_5": _mean_last(returns, 5),
        "mean_return_10": _mean_last(returns, 10),
        "vol_10": _std_last(returns, 10),
        "momentum_5": momentum_5,
        "latest_nav": float(navs[-1]),
    }

