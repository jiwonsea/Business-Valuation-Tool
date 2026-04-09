"""News collection -- Naver News API (KR) + Google News RSS (US).

Naver API: Requires NAVER_CLIENT_ID and NAVER_CLIENT_SECRET environment variables.
Google RSS: No API key required.
"""

from __future__ import annotations

import os
from defusedxml.ElementTree import fromstring as safe_fromstring
from datetime import datetime, timedelta
from html import unescape

import httpx


class NewsCollector:
    """News collector."""

    def __init__(self, timeout: float = 10.0):
        self._timeout = timeout

    def collect_kr(
        self,
        query: str = "주식시장 실적",
        days: int = 30,
        max_items: int = 100,
    ) -> list[dict]:
        """Collect Korean news via Naver News Search API.

        Returns:
            [{"title", "description", "link", "pub_date", "source"}]
        """
        client_id = os.environ.get("NAVER_CLIENT_ID", "")
        client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")

        if not client_id or not client_secret:
            print("[WARN] NAVER_CLIENT_ID/SECRET 미설정. KR 뉴스 수집 건너뜀.")
            return []

        headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        }
        url = "https://openapi.naver.com/v1/search/news.json"

        results = []
        display = min(max_items, 100)  # Naver API max 100 items/request

        try:
            from pipeline.api_guard import ApiGuard

            ApiGuard.get().check("naver")
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url, headers=headers, params={
                    "query": query,
                    "display": display,
                    "start": 1,
                    "sort": "date",
                })
                resp.raise_for_status()
                data = resp.json()
                ApiGuard.get().record_success("naver")

                cutoff = datetime.now() - timedelta(days=days)
                for item in data.get("items", []):
                    # Date parsing (Naver: "Mon, 31 Mar 2025 10:00:00 +0900")
                    try:
                        pub = datetime.strptime(
                            item["pubDate"], "%a, %d %b %Y %H:%M:%S %z"
                        ).replace(tzinfo=None)
                    except (ValueError, KeyError):
                        pub = datetime.now()

                    if pub < cutoff:
                        continue

                    results.append({
                        "title": _strip_html(item.get("title", "")),
                        "description": _strip_html(item.get("description", "")),
                        "link": item.get("originallink") or item.get("link", ""),
                        "pub_date": pub.isoformat(),
                        "source": "naver",
                    })
        except Exception as e:
            print(f"[ERROR] 네이버 뉴스 수집 실패: {e}")
            try:
                from pipeline.api_guard import ApiGuard
                ApiGuard.get().record_failure("naver", e)
            except Exception as guard_err:
                print(f"[WARN] ApiGuard record_failure 실패: {guard_err}")

        return results

    def collect_us(
        self,
        query: str = "stock market earnings",
        days: int = 30,
        max_items: int = 50,
    ) -> list[dict]:
        """Collect US news via Google News RSS.

        Returns:
            [{"title", "description", "link", "pub_date", "source"}]
        """
        encoded_q = query.replace(" ", "+")
        url = (
            f"https://news.google.com/rss/search?"
            f"q={encoded_q}&hl=en-US&gl=US&ceid=US:en"
        )

        results = []
        cutoff = datetime.now() - timedelta(days=days)

        try:
            from pipeline.api_guard import ApiGuard

            ApiGuard.get().check("google_rss")
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url)
                resp.raise_for_status()
                ApiGuard.get().record_success("google_rss")

                root = safe_fromstring(resp.text)
                for item in root.iter("item"):
                    title = item.findtext("title", "")
                    link = item.findtext("link", "")
                    pub_str = item.findtext("pubDate", "")
                    description = item.findtext("description", "")

                    # Date parsing (RSS: "Mon, 31 Mar 2025 10:00:00 GMT")
                    try:
                        pub = datetime.strptime(pub_str, "%a, %d %b %Y %H:%M:%S %Z")
                    except ValueError:
                        pub = datetime.now()

                    if pub < cutoff:
                        continue

                    results.append({
                        "title": _strip_html(title),
                        "description": _strip_html(description),
                        "link": link,
                        "pub_date": pub.isoformat(),
                        "source": "google_rss",
                    })

                    if len(results) >= max_items:
                        break
        except Exception as e:
            print(f"[ERROR] Google News RSS 수집 실패: {e}")
            try:
                from pipeline.api_guard import ApiGuard
                ApiGuard.get().record_failure("google_rss", e)
            except Exception as guard_err:
                print(f"[WARN] ApiGuard record_failure 실패: {guard_err}")

        return results

    def collect_for_company(
        self,
        company_name: str,
        market: str = "KR",
        days: int = 30,
        max_items: int = 50,
    ) -> list[dict]:
        """Collect related news by company name (auto-dispatch KR/US).

        Args:
            company_name: Company name or ticker
            market: "KR" | "US"
            days: Collection period (days)
            max_items: Maximum items to collect

        Returns:
            [{"title", "description", "link", "pub_date", "source"}]
        """
        if market == "KR":
            news = self.collect_kr(company_name, days=days, max_items=max_items)
        else:
            news = self.collect_us(company_name, days=days, max_items=max_items)

        # Deduplicate (by title)
        seen = set()
        unique = []
        for n in news:
            if n["title"] not in seen:
                seen.add(n["title"])
                unique.append(n)

        return unique


def _strip_html(text: str) -> str:
    """Remove HTML tags and entities."""
    import re
    clean = re.sub(r"<[^>]+>", "", text)
    return unescape(clean).strip()
