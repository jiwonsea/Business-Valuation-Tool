"""Importance scoring -- based on news frequency (time-weighted) + company size.

Score = news_score(0-50) + size_score(0-50) -> 5-level star rating.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime

logger = logging.getLogger(__name__)

# Market cap bracket scores (USD basis, KRW converted)
_LARGE_CAP_USD = 10_000_000_000    # $10B+
_MID_CAP_USD = 2_000_000_000      # $2B+
_KRW_TO_USD = 1_350               # Approximate exchange rate


def _stars(score: int) -> str:
    """Convert score to 5-level star string."""
    n = 5 if score >= 80 else 4 if score >= 60 else 3 if score >= 40 else 2 if score >= 20 else 1
    try:
        result = "\u2605" * n + "\u2606" * (5 - n)
        result.encode("utf-8")
        return result
    except (UnicodeEncodeError, UnicodeDecodeError):
        return "[" + "*" * n + " " * (5 - n) + "]"


def _time_decay_weight(pub_date_str: str, now: datetime | None = None) -> float:
    """Calculate time decay weight: recent news weighs more.

    weight = max(0.1, 1.0 - days_ago / 30)
    30-day-old news -> 0.1, today's news -> 1.0
    """
    now = now or datetime.now()
    try:
        pub = datetime.fromisoformat(pub_date_str[:19])
        days_ago = (now - pub).total_seconds() / 86400
        return max(0.1, 1.0 - days_ago / 30)
    except (ValueError, TypeError):
        return 0.5  # Unparseable date -> neutral weight


def _count_news_mentions(company_name: str, news: list[dict]) -> float:
    """Count company name mentions with time decay weighting.

    Returns weighted mention score (float).
    """
    name_lower = company_name.lower()
    now = datetime.now()
    score = 0.0
    for n in news:
        text = f"{n.get('title', '')} {n.get('description', '')}".lower()
        if name_lower in text:
            score += _time_decay_weight(n.get("pub_date", ""), now)
    return score


def _news_score(mention_score: float, max_mentions: float) -> int:
    """News mention ratio -> 0-50 points."""
    if max_mentions <= 0:
        return 25  # Default
    ratio = mention_score / max_mentions
    return min(50, int(ratio * 50))


def _size_score(market_cap_usd: int | None) -> int:
    """Market cap (USD equivalent) -> 0-50 points."""
    if market_cap_usd is None:
        return 20  # Neutral score on lookup failure
    if market_cap_usd >= _LARGE_CAP_USD:
        return 50
    if market_cap_usd >= _MID_CAP_USD:
        return 30
    return 10


# Ticker values that mean "unknown" — should not be passed to Yahoo Finance
_INVALID_TICKERS: frozenset[str] = frozenset({
    "미지정", "n/a", "unknown", "없음", "미확인", "tbd", "null", "none", "-",
})


def _fetch_market_cap_usd(ticker: str | None, market: str) -> int | None:
    """Fetch market cap and convert to USD."""
    if not ticker or not ticker.strip() or ticker.strip().lower() in _INVALID_TICKERS:
        return None
    try:
        from pipeline.yahoo_finance import get_market_cap

        # KR ticker: use resolve_kr_ticker for proper KOSPI/KOSDAQ detection
        yahoo_ticker = ticker
        if market == "KR" and not ticker.endswith((".KS", ".KQ")):
            try:
                from pipeline.yfinance_fetcher import resolve_kr_ticker
                yahoo_ticker = resolve_kr_ticker(ticker)
            except (ImportError, Exception):
                yahoo_ticker = f"{ticker}.KS"

        cap = get_market_cap(yahoo_ticker)
        if not cap or cap <= 0:
            return None

        # KRW -> USD conversion
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
    """Calculate per-company importance score + sort descending.

    Args:
        companies: DiscoveryEngine output [{"name", "ticker", "reason", "market"}]
        news: Collected news list

    Returns:
        Companies with score, stars, news_count, market_cap fields added, sorted by score descending.
    """
    # 1) Count news mentions (time-weighted)
    mention_scores: dict[str, float] = {}
    for co in companies:
        name = co.get("name", "")
        mention_scores[name] = _count_news_mentions(name, news)

    max_mentions = max(mention_scores.values(), default=0)

    # 2) Score each company
    scored = []
    for co in companies:
        name = co.get("name", "")
        ticker = co.get("ticker")
        market = co.get("market", "KR")

        mentions = mention_scores.get(name, 0)
        ns = _news_score(mentions, max_mentions)

        cap_usd = _fetch_market_cap_usd(ticker, market)
        ss = _size_score(cap_usd)

        total = ns + ss
        co_scored = {
            **co,
            "score": total,
            "stars": _stars(total),
            "news_count": round(mentions, 1),
            "market_cap_usd": cap_usd,
        }
        scored.append(co_scored)

    # 3) Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
