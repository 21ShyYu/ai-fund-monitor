from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def get_conn(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection, schema_sql: str) -> None:
    conn.executescript(schema_sql)
    conn.commit()


def upsert_price(
    conn: sqlite3.Connection,
    fund_code: str,
    fund_name: str,
    nav: float,
    daily_change_pct: float,
    observed_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO fund_prices (fund_code, fund_name, nav, daily_change_pct, observed_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (fund_code, fund_name, nav, daily_change_pct, observed_at),
    )
    conn.commit()


def insert_news(
    conn: sqlite3.Connection,
    title: str,
    summary: str,
    source: str,
    published_at: str,
    category: str,
) -> None:
    conn.execute(
        """
        INSERT INTO news_items (title, summary, source, published_at, category)
        VALUES (?, ?, ?, ?, ?)
        """,
        (title, summary, source, published_at, category),
    )
    conn.commit()


def insert_prediction(
    conn: sqlite3.Connection,
    fund_code: str,
    pred_return: float,
    pred_vol: float,
    confidence: float,
    signal: str,
    reason: str,
    risk_hint: str,
    created_at: str,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO predictions
        (fund_code, pred_return, pred_vol, confidence, signal, reason, risk_hint, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (fund_code, pred_return, pred_vol, confidence, signal, reason, risk_hint, created_at),
    )
    conn.commit()
    return int(cur.lastrowid)


def insert_job_log(
    conn: sqlite3.Connection,
    job_name: str,
    status: str,
    detail: str,
    created_at: str | None = None,
) -> None:
    ts = created_at or datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO job_logs (job_name, status, detail, created_at) VALUES (?, ?, ?, ?)",
        (job_name, status, detail, ts),
    )
    conn.commit()


def get_recent_prices(conn: sqlite3.Connection, fund_code: str, limit: int = 30) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT fund_code, fund_name, nav, daily_change_pct, observed_at
        FROM fund_prices
        WHERE fund_code = ?
        ORDER BY observed_at DESC
        LIMIT ?
        """,
        (fund_code, limit),
    )
    return [dict(x) for x in cur.fetchall()][::-1]


def get_recent_predictions(conn: sqlite3.Connection, limit: int = 200) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT id, fund_code, pred_return, pred_vol, confidence, signal, reason, risk_hint, created_at
        FROM predictions
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(x) for x in cur.fetchall()]


def get_latest_signals(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT p.*
        FROM predictions p
        JOIN (
            SELECT fund_code, MAX(created_at) AS max_created
            FROM predictions
            GROUP BY fund_code
        ) latest ON latest.fund_code = p.fund_code AND latest.max_created = p.created_at
        ORDER BY p.fund_code
        """
    )
    return [dict(x) for x in cur.fetchall()]


def get_recent_news(conn: sqlite3.Connection, limit: int = 300) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT id, title, summary, source, published_at, category
        FROM news_items
        ORDER BY published_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(x) for x in cur.fetchall()]

