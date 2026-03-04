from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import feedparser
import requests


class DataSourceError(Exception):
    pass


def fetch_fund_snapshot(fund_code: str, timeout_sec: int = 15) -> dict[str, Any]:
    """
    Pull realtime estimated fund price from Eastmoney public endpoint.
    Raises exception on any invalid or unavailable response.
    """
    url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
    resp = requests.get(url, timeout=timeout_sec)
    resp.raise_for_status()
    text = resp.text.strip()
    matched = re.search(r"jsonpgz\\((\\{.*\\})\\);?", text)
    if not matched:
        raise DataSourceError(f"Fund source returned unexpected payload: {fund_code}")
    payload = json.loads(matched.group(1))
    if payload.get("gsz") in (None, "") or payload.get("gszzl") in (None, ""):
        raise DataSourceError(f"Fund source missing required fields: {fund_code}")
    nav = float(payload["gsz"])
    rate = float(payload["gszzl"])
    ts = payload.get("gztime") or datetime.now().isoformat(timespec="seconds")
    return {"nav": nav, "daily_change_pct": rate, "observed_at": ts}


def fetch_news(
    news_source_config: dict[str, Any] | list[dict[str, Any]], per_feed_limit: int = 30
) -> tuple[list[dict[str, str]], list[str]]:
    items: list[dict[str, str]] = []
    errors: list[str] = []
    sources: list[dict[str, Any]]
    if isinstance(news_source_config, list):
        sources = news_source_config
    elif isinstance(news_source_config, dict):
        raw_sources = news_source_config.get("sources", [])
        sources = raw_sources if isinstance(raw_sources, list) else []
    else:
        errors.append(
            "Invalid news_sources.json format: expected object with 'sources' list or a list of sources."
        )
        return items, errors

    for source in sources:
        if not isinstance(source, dict):
            errors.append("Invalid news source item: each source must be an object.")
            continue
        rss_url = source.get("rss_url", "").strip()
        if not rss_url:
            errors.append(f"News source missing rss_url: {source.get('name', 'unknown')}")
            continue
        parsed = feedparser.parse(rss_url)
        if getattr(parsed, "bozo", 0):
            errors.append(f"News source parse warning: {source.get('name', 'unknown')}")
        category = source.get("category", "other")
        source_name = source.get("name", "unknown")
        if not parsed.entries:
            errors.append(f"News source has no entries: {source_name}")
        for entry in parsed.entries[:per_feed_limit]:
            published = _extract_published(entry)
            items.append(
                {
                    "title": entry.get("title", "")[:300],
                    "summary": _clean_html(entry.get("summary", ""))[:1200],
                    "source": source_name,
                    "published_at": published,
                    "category": category,
                }
            )
    return items, errors


def _extract_published(entry: Any) -> str:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat(timespec="seconds")
    if entry.get("published"):
        return str(entry.get("published"))
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_html(raw: str) -> str:
    return re.sub(r"<[^>]+>", "", raw).strip()
