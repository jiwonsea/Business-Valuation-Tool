"""중요도 스코어링 — 뉴스 빈도 + 기업 규모 기반.

점수 = news_score(0~50) + size_score(0~50)  →  ★ 5단계 등급.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 시가총액 구간별 점수 (USD 기준, KRW는 환산)
_LARGE_CAP_USD = 10_000_000_000    # $10B+
_MID_CAP_USD = 2_000_000_000      # $2B+
_KRW_TO_USD = 1_350               # 대략적 환율


def _stars(score: int) -> str:
    """점수 → ★ 5단계 문자열."""
    if score >= 80:
        return "★★★★★"
    if score >= 60:
        return "★★★★☆"
    if score >= 40:
        return "★★★☆☆"
    if score >= 20:
        return "★★☆☆☆"
    return "★☆☆☆☆"


def _count_news_mentions(company_name: str, news: list[dict]) -> int:
    """뉴스 제목+설명에서 기업명 언급 횟수."""
    name_lower = company_name.lower()
    count = 0
    for n in news:
        text = f"{n.get('title', '')} {n.get('description', '')}".lower()
        if name_lower in text:
            count += 1
    return count


def _news_score(mention_count: int, max_mentions: int) -> int:
    """뉴스 언급 비율 → 0~50점."""
    if max_mentions <= 0:
        return 25  # 기본값
    ratio = mention_count / max_mentions
    return min(50, int(ratio * 50))


def _size_score(market_cap_usd: int | None) -> int:
    """시가총액(USD 환산) → 0~50점."""
    if market_cap_usd is None:
        return 20  # 조회 실패 시 중립 점수
    if market_cap_usd >= _LARGE_CAP_USD:
        return 50
    if market_cap_usd >= _MID_CAP_USD:
        return 30
    return 10


def _fetch_market_cap_usd(ticker: str | None, market: str) -> int | None:
    """시가총액 조회 후 USD로 환산."""
    if not ticker:
        return None
    try:
        from pipeline.yahoo_finance import get_market_cap

        # KR 티커 보정
        yahoo_ticker = ticker
        if market == "KR" and not ticker.endswith((".KS", ".KQ")):
            yahoo_ticker = f"{ticker}.KS"

        cap = get_market_cap(yahoo_ticker)
        if not cap:
            return None

        # KRW → USD 환산
        if market == "KR":
            return int(cap / _KRW_TO_USD)
        return cap
    except Exception as e:
        logger.debug("시가총액 조회 실패 (%s): %s", ticker, e)
        return None


def score_companies(
    companies: list[dict],
    news: list[dict],
) -> list[dict]:
    """기업별 중요도 스코어 계산 + 내림차순 정렬.

    Args:
        companies: DiscoveryEngine 출력 [{"name", "ticker", "reason", "market"}]
        news: 수집된 뉴스 리스트

    Returns:
        companies에 score, stars, news_count, market_cap 필드 추가 후 score 내림차순 정렬.
    """
    # 1) 뉴스 언급 횟수 집계
    mention_counts = {}
    for co in companies:
        name = co.get("name", "")
        mention_counts[name] = _count_news_mentions(name, news)

    max_mentions = max(mention_counts.values(), default=0)

    # 2) 각 기업 스코어링
    scored = []
    for co in companies:
        name = co.get("name", "")
        ticker = co.get("ticker")
        market = co.get("market", "KR")

        mentions = mention_counts.get(name, 0)
        ns = _news_score(mentions, max_mentions)

        cap_usd = _fetch_market_cap_usd(ticker, market)
        ss = _size_score(cap_usd)

        total = ns + ss
        co_scored = {
            **co,
            "score": total,
            "stars": _stars(total),
            "news_count": mentions,
            "market_cap_usd": cap_usd,
        }
        scored.append(co_scored)

    # 3) score 내림차순 정렬
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
