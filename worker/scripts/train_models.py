from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
from xgboost import XGBRegressor

from app.config import Settings
from app.db import get_conn
from app.features import build_feature_vector


def _load_fund_codes(settings: Settings) -> list[str]:
    funds = settings.load_funds()
    return [str(x["code"]) for x in funds if bool(x.get("enabled", True))]


def _load_rows(conn, fund_code: str) -> list[dict]:
    cur = conn.execute(
        """
        SELECT fund_code, fund_name, nav, daily_change_pct, observed_at
        FROM fund_prices
        WHERE fund_code = ?
        ORDER BY observed_at ASC
        """,
        (fund_code,),
    )
    return [dict(x) for x in cur.fetchall()]


def _build_dataset(rows: list[dict], lookback: int = 20) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if len(rows) < lookback + 2:
        return np.empty((0, 5)), np.empty((0,)), np.empty((0,))

    returns = np.array([float(x["daily_change_pct"]) / 100.0 for x in rows], dtype=float)
    x_list: list[list[float]] = []
    y_ret: list[float] = []
    y_vol: list[float] = []

    for idx in range(lookback - 1, len(rows) - 1):
        history = rows[: idx + 1]
        f = build_feature_vector(history)
        x_list.append(
            [
                f["mean_return_5"],
                f["mean_return_10"],
                f["vol_10"],
                f["momentum_5"],
                f["latest_nav"],
            ]
        )
        next_ret = float(returns[idx + 1])
        y_ret.append(next_ret)
        y_vol.append(abs(next_ret))

    return np.array(x_list, dtype=float), np.array(y_ret, dtype=float), np.array(y_vol, dtype=float)


def _train_one_fund(model_dir: Path, fund_code: str, rows: list[dict], min_samples: int) -> None:
    x, y_ret, y_vol = _build_dataset(rows)
    if x.shape[0] < min_samples:
        raise RuntimeError(
            f"{fund_code}: not enough training samples ({x.shape[0]} < {min_samples}). "
            "Run pipeline more times to accumulate fund_prices."
        )

    ret_model = XGBRegressor(
        n_estimators=180,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        random_state=42,
    )
    vol_model = XGBRegressor(
        n_estimators=120,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        random_state=42,
    )

    ret_model.fit(x, y_ret)
    vol_model.fit(x, y_vol)

    out_dir = model_dir / fund_code
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(ret_model, out_dir / "xgboost.joblib")
    joblib.dump(vol_model, out_dir / "vol.joblib")
    print(f"[OK] {fund_code} -> {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and export fund models to runtime/models.")
    parser.add_argument("--fund-code", help="Only train one fund code", default="")
    parser.add_argument("--min-samples", type=int, default=30, help="Minimum samples required per fund")
    args = parser.parse_args()

    settings = Settings.load()
    conn = get_conn(settings.db_path)
    try:
        codes = [args.fund_code.strip()] if args.fund_code.strip() else _load_fund_codes(settings)
        for code in codes:
            rows = _load_rows(conn, code)
            _train_one_fund(settings.model_dir, code, rows, min_samples=args.min_samples)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
