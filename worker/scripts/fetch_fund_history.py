from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from app.config import Settings


API_URL = "https://api.fund.eastmoney.com/f10/lsjz"
PINGZHONG_URL = "https://fund.eastmoney.com/pingzhongdata/{code}.js"


def _safe_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        matched = re.search(r"(\{.*\})", text, flags=re.DOTALL)
        if not matched:
            raise
        return json.loads(matched.group(1))


def _extract_js_var(js_text: str, var_name: str) -> str:
    pattern = rf"var\s+{re.escape(var_name)}\s*=\s*(.*?);"
    m = re.search(pattern, js_text, flags=re.DOTALL)
    if not m:
        raise ValueError(f"Missing JS variable: {var_name}")
    return m.group(1).strip()


def _fetch_from_pingzhong(code: str, timeout_sec: int = 15) -> list[dict[str, Any]]:
    resp = requests.get(
        PINGZHONG_URL.format(code=code),
        params={"v": int(datetime.now().timestamp())},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=timeout_sec,
    )
    resp.raise_for_status()
    js_text = resp.text
    arr_text = _extract_js_var(js_text, "Data_netWorthTrend")
    arr = json.loads(arr_text)
    rows: list[dict[str, Any]] = []
    for item in arr:
        ts = item.get("x")
        nav = item.get("y")
        pct = item.get("equityReturn")
        if ts in (None, "") or nav in (None, "") or pct in (None, ""):
            continue
        try:
            date_str = datetime.fromtimestamp(float(ts) / 1000.0).strftime("%Y-%m-%d")
            rows.append(
                {
                    "date": date_str,
                    "nav": float(nav),
                    "daily_change_pct": float(pct),
                }
            )
        except (ValueError, TypeError):
            continue

    rows.sort(key=lambda x: x["date"])
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if row["date"] in seen:
            continue
        seen.add(row["date"])
        deduped.append(row)
    return deduped


def _fetch_one_fund(code: str, timeout_sec: int = 15) -> list[dict[str, Any]]:
    # Primary source: full historical JS dataset (usually much longer than paged API).
    try:
        rows = _fetch_from_pingzhong(code, timeout_sec=timeout_sec)
        if rows:
            return rows
    except Exception:
        pass

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://fundf10.eastmoney.com/",
            "Accept": "application/json, text/plain, */*",
        }
    )

    page = 1
    page_size = 50
    rows: list[dict[str, Any]] = []

    while True:
        resp = session.get(
            API_URL,
            params={
                "fundCode": code,
                "pageIndex": page,
                "pageSize": page_size,
                "startDate": "",
                "endDate": "",
            },
            timeout=timeout_sec,
        )
        resp.raise_for_status()
        payload = _safe_json(resp.text)

        data = payload.get("Data") or {}
        items = data.get("LSJZList") or []
        if not items:
            break

        for item in items:
            date_str = str(item.get("FSRQ", "")).strip()
            nav_str = str(item.get("DWJZ", "")).strip()
            pct_str = str(item.get("JZZZL", "")).strip()
            if not date_str or not nav_str or not pct_str:
                continue
            try:
                rows.append(
                    {
                        "date": date_str[:10],
                        "nav": float(nav_str),
                        "daily_change_pct": float(pct_str),
                    }
                )
            except ValueError:
                continue

        total_count = int(data.get("TotalCount") or 0)
        if page * page_size >= total_count:
            break
        page += 1

    # Eastmoney returns newest first. Convert to ascending date order for training.
    rows.sort(key=lambda x: x["date"])
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if row["date"] in seen:
            continue
        seen.add(row["date"])
        deduped.append(row)
    return deduped


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "nav", "daily_change_pct"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch historical fund data and save CSV files.")
    parser.add_argument("--fund-code", default="", help="Only fetch one fund code")
    parser.add_argument(
        "--out-dir",
        default="worker/runtime/history_csv",
        help="Output directory for CSV files",
    )
    args = parser.parse_args()

    settings = Settings.load()
    funds = settings.load_funds()
    codes = [args.fund_code.strip()] if args.fund_code.strip() else [str(x["code"]) for x in funds]
    out_dir = (Path(args.out_dir) if Path(args.out_dir).is_absolute() else (settings.config_dir.parents[1] / args.out_dir)).resolve()

    for code in codes:
        rows = _fetch_one_fund(code)
        out_path = out_dir / f"{code}.csv"
        _write_csv(out_path, rows)
        print(f"[OK] {code}: {len(rows)} rows -> {out_path}")


if __name__ == "__main__":
    main()
