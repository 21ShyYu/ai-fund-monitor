from __future__ import annotations

import json
import re
from html import unescape
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from typing import Any

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
    # Eastmoney response shape: jsonpgz({...});
    matched = re.search(r"jsonpgz\((\{.*\})\);?", text, flags=re.DOTALL)
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
    news_source_config: dict[str, Any] | list[dict[str, Any]],
    per_feed_limit: int = 30,
    feed_timeout_sec: int = 12,
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

    seen: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            errors.append("Invalid news source item: each source must be an object.")
            continue
        mode = str(source.get("mode", "rss")).strip().lower()
        category = str(source.get("category", "policy"))
        source_name = str(source.get("name", "unknown"))
        source_limit = int(source.get("max_items", per_feed_limit))
        require_political = bool(source.get("require_political", False))
        try:
            if mode == "html":
                fetched = _fetch_from_html_source(
                    source=source,
                    source_name=source_name,
                    category=category,
                    feed_timeout_sec=feed_timeout_sec,
                    per_feed_limit=source_limit,
                )
            else:
                fetched = _fetch_from_rss_source(
                    source=source,
                    source_name=source_name,
                    category=category,
                    feed_timeout_sec=feed_timeout_sec,
                    per_feed_limit=source_limit,
                )
        except Exception as exc:
            errors.append(f"News source fetch failed: {source_name} ({exc})")
            continue

        if not fetched:
            errors.append(f"News source has no entries: {source_name}")
            continue

        for row in fetched:
            if require_political and not _looks_political(
                f"{row.get('title', '')} {row.get('summary', '')}"
            ):
                continue
            dedupe_key = f"{row.get('source')}|{row.get('published_at')}|{row.get('title')}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            items.append(row)
    return items, errors


def _extract_published(entry: Any) -> str:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat(timespec="seconds")
    if entry.get("published"):
        return str(entry.get("published"))
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _fetch_from_rss_source(
    source: dict[str, Any],
    source_name: str,
    category: str,
    feed_timeout_sec: int,
    per_feed_limit: int,
) -> list[dict[str, str]]:
    import feedparser

    rss_url = str(source.get("rss_url", "")).strip()
    if not rss_url:
        raise DataSourceError(f"News source missing rss_url: {source_name}")
    resp = requests.get(
        rss_url,
        timeout=feed_timeout_sec,
        headers={"User-Agent": "ai-fund-monitor/1.0"},
    )
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)
    rows: list[dict[str, str]] = []
    for entry in parsed.entries[:per_feed_limit]:
        rows.append(
            {
                "title": str(entry.get("title", ""))[:300],
                "summary": _clean_html(str(entry.get("summary", "")))[:260],
                "source": source_name,
                "published_at": _extract_published(entry),
                "category": category,
            }
        )
    return rows


def _fetch_from_html_source(
    source: dict[str, Any],
    source_name: str,
    category: str,
    feed_timeout_sec: int,
    per_feed_limit: int,
) -> list[dict[str, str]]:
    list_url = str(source.get("list_url", "")).strip()
    if not list_url:
        raise DataSourceError(f"HTML news source missing list_url: {source_name}")
    link_patterns = source.get("link_patterns", [])
    compiled_patterns: list[re.Pattern[str]] = []
    if isinstance(link_patterns, list):
        for p in link_patterns:
            if isinstance(p, str) and p.strip():
                compiled_patterns.append(re.compile(p.strip(), re.I))
    list_resp = requests.get(
        list_url,
        timeout=feed_timeout_sec,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ai-fund-monitor/1.0)"},
    )
    list_resp.raise_for_status()
    links = _extract_links(_response_text(list_resp), list_url, compiled_patterns)
    rows: list[dict[str, str]] = []
    for article_url in links[:per_feed_limit]:
        try:
            parsed = _parse_article_page(article_url, source_name, category, feed_timeout_sec)
        except Exception:
            continue
        if parsed:
            rows.append(parsed)
    return rows


def _extract_links(
    html: str,
    base_url: str,
    patterns: list[re.Pattern[str]],
) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"""href=["']([^"']+)["']""", html, flags=re.I):
        href = match.group(1).strip()
        if not href or href.startswith("javascript:") or href.startswith("#"):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.scheme not in {"http", "https"}:
            continue
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if patterns and not any(p.search(normalized) for p in patterns):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        links.append(normalized)
    return links


def _parse_article_page(
    article_url: str,
    source_name: str,
    category: str,
    timeout_sec: int,
) -> dict[str, str] | None:
    resp = requests.get(
        article_url,
        timeout=timeout_sec,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ai-fund-monitor/1.0)"},
    )
    resp.raise_for_status()
    html = _response_text(resp)
    title = _extract_title(html)
    if not title:
        return None
    published_at = _extract_published_from_html(html)
    summary = _extract_summary(html)
    if not summary:
        summary = title
    return {
        "title": title[:300],
        "summary": summary[:260],
        "source": source_name,
        "published_at": published_at,
        "category": category,
    }


def _extract_title(html: str) -> str:
    patterns = [
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
        r"<h1[^>]*>(.*?)</h1>",
        r"<title>(.*?)</title>",
    ]
    for pattern in patterns:
        matched = re.search(pattern, html, flags=re.I | re.S)
        if matched:
            text = _clean_html(matched.group(1))
            if text:
                return text
    return ""


def _extract_summary(html: str) -> str:
    patterns = [
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        matched = re.search(pattern, html, flags=re.I | re.S)
        if matched:
            text = _clean_html(matched.group(1))
            if len(text) >= 18:
                return text
    paragraphs: list[str] = []
    for m in re.finditer(r"<p[^>]*>(.*?)</p>", html, flags=re.I | re.S):
        text = _clean_html(m.group(1))
        if len(text) >= 28 and "责任编辑" not in text:
            paragraphs.append(text)
    for text in paragraphs:
        if not re.search(r"\d{4}[-年]\d{1,2}[-月]\d{1,2}", text):
            return text
    return paragraphs[0] if paragraphs else ""


def _extract_published_from_html(html: str) -> str:
    patterns = [
        r'content=["\'](\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)["\']',
        r'content=["\'](\d{4}-\d{2}-\d{2})["\']',
        r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?)",
        r"(\d{4}-\d{2}-\d{2})",
        r"(\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2})",
        r"(\d{4}年\d{1,2}月\d{1,2}日)",
    ]
    for pattern in patterns:
        matched = re.search(pattern, html)
        if matched:
            raw = matched.group(1).strip()
            normalized = (
                raw.replace("年", "-").replace("月", "-").replace("日", "").replace("T", " ")
            )
            normalized = re.sub(r"\s+", " ", normalized).strip()
            for fmt in [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
            ]:
                try:
                    dt = datetime.strptime(normalized, fmt)
                    return dt.isoformat(timespec="seconds")
                except ValueError:
                    continue
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _looks_political(text: str) -> bool:
    lowered = text.lower()
    keywords = [
        "时政",
        "国务院",
        "两会",
        "中央",
        "政策",
        "政府",
        "部长",
        "总书记",
        "经济工作",
        "全国人大",
        "政协",
        "国常会",
        "监管",
    ]
    return any(k in lowered for k in keywords)


def _response_text(resp: requests.Response) -> str:
    if resp.encoding and resp.encoding.lower() not in {"iso-8859-1", "latin-1"}:
        return resp.text
    enc = resp.apparent_encoding or "utf-8"
    try:
        return resp.content.decode(enc, errors="ignore")
    except Exception:
        return resp.text
