"""Fetch peer trading multiples from yfinance for external-market calibration.

Collects per-ticker EV/EBITDA, EV/Revenue, trailing/forward P/E, D/E, market cap.
Accepts an injectable fetcher so tests can run offline with frozen fixtures.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Iterable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PeerMultiples:
    """Trading multiples snapshot for one peer ticker."""

    ticker: str
    ev_ebitda: float | None = None
    ev_revenue: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    de_ratio: float | None = None  # Debt/Equity (yfinance scale: percent, e.g. 45.2)
    market_cap: float | None = None  # Raw currency units from yfinance

    def is_empty(self) -> bool:
        return all(
            v is None
            for v in (
                self.ev_ebitda,
                self.ev_revenue,
                self.trailing_pe,
                self.forward_pe,
            )
        )


# Callable returning a dict-like info payload (yf.Ticker().info compatible).
InfoFetcher = Callable[[str], dict]


def _default_yfinance_fetcher(ticker: str) -> dict:
    """Production fetcher — calls yfinance. Imported lazily so tests need no network."""
    from pipeline.yfinance_fetcher import _get_ticker_info, _resolve_ticker

    resolved = _resolve_ticker(ticker, "KR" if ticker.isdigit() else "US")
    return _get_ticker_info(resolved) or {}


def _coerce(value) -> float | None:
    """yfinance returns ints, floats, or strings like 'N/A'. Normalize to float|None."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def _info_to_multiples(ticker: str, info: dict) -> PeerMultiples:
    """Extract canonical multiple fields from a yfinance info dict."""
    return PeerMultiples(
        ticker=ticker,
        ev_ebitda=_coerce(info.get("enterpriseToEbitda")),
        ev_revenue=_coerce(info.get("enterpriseToRevenue")),
        trailing_pe=_coerce(info.get("trailingPE")),
        forward_pe=_coerce(info.get("forwardPE")),
        de_ratio=_coerce(info.get("debtToEquity")),
        market_cap=_coerce(info.get("marketCap")),
    )


def fetch_peer_multiples(
    tickers: Iterable[str],
    *,
    fetcher: InfoFetcher | None = None,
) -> list[PeerMultiples]:
    """Fetch multiples for each peer ticker via the injected fetcher.

    Args:
        tickers: Peer ticker symbols (yfinance-ready; caller resolves KR suffixes).
        fetcher: Override for tests. Default calls yfinance.

    Returns:
        One ``PeerMultiples`` per ticker. Fields may be ``None`` when yfinance
        omits them; downstream stats skip ``None`` values.
    """
    f = fetcher or _default_yfinance_fetcher
    out: list[PeerMultiples] = []
    for t in tickers:
        try:
            info = f(t)
        except Exception as e:
            logger.warning("peer fetch failed (%s): %s", t, e)
            out.append(PeerMultiples(ticker=t))
            continue
        out.append(_info_to_multiples(t, info or {}))
    return out
