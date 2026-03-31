"""뉴스 수집 — 네이버 뉴스 API (KR) + Google News RSS (US).

네이버 API: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 환경변수 필요.
Google RSS: API Key 불필요.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from html import unescape

import httpx


class NewsCollector:
    """뉴스 수집기."""

    def __init__(self, timeout: float = 10.0):
        self._timeout = timeout

    def collect_kr(
        self,
        query: str = "주식시장 실적",
        days: int = 30,
        max_items: int = 100,
    ) -> list[dict]:
        """네이버 뉴스 검색 API로 한국 뉴스 수집.

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
        display = min(max_items, 100)  # 네이버 API 최대 100건/요청

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url, headers=headers, params={
                    "query": query,
                    "display": display,
                    "start": 1,
                    "sort": "date",
                })
                resp.raise_for_status()
                data = resp.json()

                cutoff = datetime.now() - timedelta(days=days)
                for item in data.get("items", []):
                    # 날짜 파싱 (네이버: "Mon, 31 Mar 2025 10:00:00 +0900")
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

        return results

    def collect_us(
        self,
        query: str = "stock market earnings",
        days: int = 30,
        max_items: int = 50,
    ) -> list[dict]:
        """Google News RSS로 미국 뉴스 수집.

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
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url)
                resp.raise_for_status()

                root = ET.fromstring(resp.text)
                for item in root.iter("item"):
                    title = item.findtext("title", "")
                    link = item.findtext("link", "")
                    pub_str = item.findtext("pubDate", "")
                    description = item.findtext("description", "")

                    # 날짜 파싱 (RSS: "Mon, 31 Mar 2025 10:00:00 GMT")
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

        return results


    def collect_for_company(
        self,
        company_name: str,
        market: str = "KR",
        days: int = 30,
        max_items: int = 50,
    ) -> list[dict]:
        """기업명으로 관련 뉴스 수집 (KR/US 자동 분기).

        Args:
            company_name: 기업명 또는 ticker
            market: "KR" | "US"
            days: 수집 기간 (일)
            max_items: 최대 수집 건수

        Returns:
            [{"title", "description", "link", "pub_date", "source"}]
        """
        if market == "KR":
            news = self.collect_kr(company_name, days=days, max_items=max_items)
        else:
            news = self.collect_us(company_name, days=days, max_items=max_items)

        # 중복 제거 (제목 기준)
        seen = set()
        unique = []
        for n in news:
            if n["title"] not in seen:
                seen.add(n["title"])
                unique.append(n)

        return unique


def _strip_html(text: str) -> str:
    """HTML 태그 및 엔티티 제거."""
    import re
    clean = re.sub(r"<[^>]+>", "", text)
    return unescape(clean).strip()
