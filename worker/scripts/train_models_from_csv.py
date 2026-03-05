from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from xgboost import XGBRegressor

from app.config import Settings
from app.features import build_feature_vector
from app.model_wrappers import ReturnBlendModel


def _build_dataset_from_df(df: pd.DataFrame, lookback: int = 20) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows = [
        {
            "nav": float(r["nav"]),
            "daily_change_pct": float(r["daily_change_pct"]),
            "observed_at": str(r["date"]),
        }
        for _, r in df.iterrows()
    ]
    returns = np.array([float(x["daily_change_pct"]) / 100.0 for x in rows], dtype=float)
    x_list: list[list[float]] = []
    y_ret: list[float] = []
    y_vol: list[float] = []

    for idx in range(lookback - 1, len(rows) - 1):
        history = rows[: idx + 1]
        feat = build_feature_vector(history)
        x_list.append(
            [
                feat["mean_return_5"],
                feat["mean_return_10"],
                feat["vol_10"],
                feat["momentum_5"],
                feat["latest_nav"],
            ]
        )
        next_ret = float(returns[idx + 1])
        y_ret.append(next_ret)
        y_vol.append(abs(next_ret))

    if not x_list:
        return np.empty((0, 5)), np.empty((0,)), np.empty((0,))
    return np.array(x_list, dtype=float), np.array(y_ret, dtype=float), np.array(y_vol, dtype=float)


def _fit_arima_next_return(returns: np.ndarray) -> float:
    if returns.size < 30:
        return float(np.mean(returns[-5:])) if returns.size else 0.0
    try:
        model = ARIMA(returns, order=(2, 0, 2))
        fit = model.fit()
        pred = fit.forecast(steps=1)
        return float(pred[0])
    except Exception:
        return float(np.mean(returns[-5:])) if returns.size else 0.0


def _train_one_fund(
    csv_path: Path,
    model_root: Path,
    fund_code: str,
    min_samples: int,
    use_arima: bool,
    arima_weight: float,
) -> None:
    df = pd.read_csv(csv_path)
    needed = {"date", "nav", "daily_change_pct"}
    if not needed.issubset(set(df.columns)):
        raise RuntimeError(f"{csv_path}: missing required columns {sorted(needed)}")

    df = df[["date", "nav", "daily_change_pct"]].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "nav", "daily_change_pct"]).sort_values("date").reset_index(drop=True)
    if len(df) < 60:
        raise RuntimeError(f"{fund_code}: too few history rows ({len(df)}). Need >=60.")

    x, y_ret, y_vol = _build_dataset_from_df(df, lookback=20)
    if x.shape[0] < min_samples:
        raise RuntimeError(f"{fund_code}: not enough train samples ({x.shape[0]} < {min_samples}).")

    ret_model = XGBRegressor(
        n_estimators=240,
        max_depth=4,
        learning_rate=0.04,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        random_state=42,
    )
    vol_model = XGBRegressor(
        n_estimators=160,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        random_state=42,
    )
    ret_model.fit(x, y_ret)
    vol_model.fit(x, y_vol)

    if use_arima:
        arima_next = _fit_arima_next_return(y_ret)
        ret_artifact = ReturnBlendModel(ret_model, arima_next_return=arima_next, arima_weight=arima_weight)
    else:
        ret_artifact = ret_model

    out_dir = model_root / fund_code
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(ret_artifact, out_dir / "xgboost.joblib")
    joblib.dump(vol_model, out_dir / "vol.joblib")
    print(f"[OK] {fund_code} model exported -> {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train fund models from CSV and export joblib files.")
    parser.add_argument("--fund-code", default="", help="Train one fund code only")
    parser.add_argument("--csv-dir", default="worker/runtime/history_csv", help="CSV directory")
    parser.add_argument("--min-samples", type=int, default=40, help="Minimum train samples")
    parser.add_argument("--use-arima", action="store_true", help="Blend ARIMA one-step return forecast")
    parser.add_argument("--arima-weight", type=float, default=0.25, help="Blend weight for ARIMA")
    args = parser.parse_args()

    settings = Settings.load()
    codes = [args.fund_code.strip()] if args.fund_code.strip() else [str(x["code"]) for x in settings.load_funds()]
    csv_dir = (Path(args.csv_dir) if Path(args.csv_dir).is_absolute() else (settings.config_dir.parents[1] / args.csv_dir)).resolve()

    for code in codes:
        csv_path = csv_dir / f"{code}.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")
        _train_one_fund(
            csv_path=csv_path,
            model_root=settings.model_dir,
            fund_code=code,
            min_samples=args.min_samples,
            use_arima=bool(args.use_arima),
            arima_weight=float(args.arima_weight),
        )


if __name__ == "__main__":
    main()
