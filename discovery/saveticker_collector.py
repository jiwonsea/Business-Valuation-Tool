"""SaveTicker news collection for US market discovery.

SaveTicker exposes unauthenticated paginated JSON at
https://api.saveticker.com/api/news/list. Items include ticker tags such as
"$NVDA" and, when available, the original article URL in extra.source_url.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

import httpx

from pipeline.api_guard import ApiGuard, ApiGuardError

BASE_URL = "https://api.saveticker.com/api/news/list"


def _parse_pub_date(item: dict[str, Any]) -> str:
    for key in ("published_at", "publishedAt", "created_at", "createdAt", "date"):
        value = item.get(key)
        if value:
            return str(value)
    return datetime.now(timezone.utc).isoformat()


def _source_url(item: dict[str, Any]) -> str:
    extra = item.get("extra")
    if isinstance(extra, dict):
        url = extra.get("source_url") or extra.get("url")
        if url:
            return str(url)
    url = item.get("url") or item.get("link")
    if url:
        return str(url)
    item_id = item.get("id")
    return f"https://www.saveticker.com/news/{item_id}" if item_id else ""


def _extract_tickers(item: dict[str, Any]) -> list[str]:
    tags = item.get("tag_names") or item.get("tags") or []
    tickers: list[str] = []
    if not isinstance(tags, list):
        return tickers
    for tag in tags:
        text = str(tag).strip().upper()
        if not text.startswith("$"):
            continue
        ticker = text[1:].strip()
        if ticker and ticker.replace(".", "").isalpha():
            tickers.append(ticker)
    return tickers


def _normalize_item(item: dict[str, Any]) -> dict[str, Any] | None:
    title = str(item.get("title") or item.get("headline") or "").strip()
    url = _source_url(item)
    tickers = _extract_tickers(item)
    if not title or not url or not tickers:
        return None
    return {
        "title": title,
        "description": str(item.get("summary") or item.get("description") or ""),
        "link": url,
        "url": url,
        "pub_date": _parse_pub_date(item),
        "source": "saveticker",
        "tickers": tickers,
        "view_count": int(item.get("view_count") or item.get("views") or 0),
    }


def fetch_saveticker_news(max_items: int = 100) -> list[dict]:
    """Collect recent SaveTicker news and extract US ticker tags."""
    page_size = min(max(max_items, 1), 50)
    max_pages = max(1, (max_items + page_size - 1) // page_size)
    results: list[dict] = []
    page = 1

    while page <= max_pages:
        try:
            ApiGuard.get().check("saveticker")
        except ApiGuardError:
            break

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    BASE_URL,
                    params={"page": page, "page_size": page_size},
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                ApiGuard.get().record_success("saveticker")
                payload = resp.json()
        except Exception as exc:
            try:
                ApiGuard.get().record_failure("saveticker", exc)
            except Exception:
                pass
            break

        raw_items = (
            payload.get("news_list") or payload.get("data")
            if isinstance(payload, dict)
            else payload
        )
        if isinstance(raw_items, dict):
            raw_items = raw_items.get("items") or raw_items.get("results") or []
        if not isinstance(raw_items, list) or not raw_items:
            break

        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            item = _normalize_item(raw)
            if item:
                results.append(item)
                if len(results) >= max_items:
                    break

        page += 1

    return results


def get_top_us_tickers(
    n: int = 15,
    max_items: int = 100,
    news: list[dict] | None = None,
) -> list[dict]:
    """Return top mentioned US tickers without an LLM discovery call."""
    news = news if news is not None else fetch_saveticker_news(max_items=max_items)
    counts: Counter[str] = Counter()
    views: Counter[str] = Counter()
    articles: dict[str, list[dict]] = defaultdict(list)

    for item in news:
        for ticker in item.get("tickers", []):
            counts[ticker] += 1
            views[ticker] += int(item.get("view_count") or 0)
            if len(articles[ticker]) < 3:
                articles[ticker].append(
                    {"title": item["title"], "url": item.get("url") or item["link"]}
                )

    ranked = sorted(counts, key=lambda t: (counts[t], views[t], t), reverse=True)
    return [
        {
            "name": ticker,
            "ticker": ticker,
            "market": "US",
            "reason": f"SaveTicker mention count {counts[ticker]}",
            "news_count": counts[ticker],
            "top_news": articles[ticker],
        }
        for ticker in ranked[:n]
    ]


if __name__ == "__main__":
    sample = fetch_saveticker_news(max_items=10)
    print(f"news={len(sample)}")
    for item in sample[:5]:
        print(f"{','.join(item.get('tickers', []))}: {item['title']} -> {item['link']}")
    print("top_tickers=")
    for row in get_top_us_tickers(n=10, max_items=50):
        print(f"{row['ticker']}: {row['reason']}")
