from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np


@dataclass
class ModelOutput:
    pred_return: float
    pred_vol: float
    model_consistency: float
    feature_quality: float


class ModelLoadError(Exception):
    pass


def predict_from_models(
    model_dir: Path, fund_code: str, features: dict[str, float], price_rows: list[dict[str, Any]]
) -> ModelOutput:
    """
    Load user-trained models if present.
    Expected path:
      {model_dir}/{fund_code}/xgboost.joblib
      {model_dir}/{fund_code}/vol.joblib
    """
    x = np.array(
        [
            features["mean_return_5"],
            features["mean_return_10"],
            features["vol_10"],
            features["momentum_5"],
            features["latest_nav"],
        ],
        dtype=float,
    ).reshape(1, -1)

    fund_model_dir = model_dir / fund_code
    ret_model_path = fund_model_dir / "xgboost.joblib"
    vol_model_path = fund_model_dir / "vol.joblib"

    if not ret_model_path.exists():
        raise ModelLoadError(f"Missing return model file: {ret_model_path}")
    if not vol_model_path.exists():
        raise ModelLoadError(f"Missing volatility model file: {vol_model_path}")

    pred_return = _predict_or_raise(ret_model_path, x)
    pred_vol = abs(_predict_or_raise(vol_model_path, x))

    model_consistency = _calc_model_consistency(price_rows)
    feature_quality = _calc_feature_quality(features, len(price_rows))
    return ModelOutput(
        pred_return=pred_return,
        pred_vol=pred_vol,
        model_consistency=model_consistency,
        feature_quality=feature_quality,
    )


def _predict_or_raise(model_path: Path, x: np.ndarray) -> float:
    if not model_path.exists():
        raise ModelLoadError(f"Model file not found: {model_path}")
    model = joblib.load(model_path)
    y = model.predict(x)
    return float(y[0])


def _calc_model_consistency(price_rows: list[dict[str, Any]]) -> float:
    if len(price_rows) < 5:
        return 0.4
    recent_returns = [abs(float(x["daily_change_pct"]) / 100.0) for x in price_rows[-10:]]
    avg_abs = float(np.mean(recent_returns)) if recent_returns else 0.0
    # Lower noise means higher consistency.
    score = max(0.3, min(0.95, 1.0 - avg_abs * 10))
    return score


def _calc_feature_quality(features: dict[str, float], data_points: int) -> float:
    score = 0.5
    if data_points >= 30:
        score += 0.25
    if abs(features["momentum_5"]) > 0.005:
        score += 0.1
    if features["vol_10"] > 0:
        score += 0.1
    return max(0.2, min(0.98, score))
