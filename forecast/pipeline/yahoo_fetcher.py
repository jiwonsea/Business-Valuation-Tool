"""yfinance wrapper — consensus + history.

Cache: reports/.cache/yahoo_{ticker}_{YYYYMMDD}.json
Empty fields are returned as None explicitly (not missing keys) so downstream
schema validation surfaces unavailability rather than silently skipping.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from pipeline._ssl_setup import ensure_ssl_env

ensure_ssl_env()

import yfinance as yf  # noqa: E402

CACHE_DIR = Path("reports/.cache")
yf.cache.set_cache_location(str(CACHE_DIR))


def _cache_path(prefix: str, ticker: str) -> Path:
    safe = ticker.replace(".", "_")
    return CACHE_DIR / f"{prefix}_{safe}_{date.today():%Y%m%d}.json"


def _records(frame) -> list[dict]:
    if frame is None:
        return []
    try:
        return json.loads(frame.reset_index().to_json(orient="records", date_format="iso"))
    except Exception:
        return []


def fetch_consensus(ticker: str, use_cache: bool = True) -> dict:
    """Fetch analyst consensus snapshot for a ticker.

    Pulls from yfinance Ticker(ticker):
      - earnings_estimate  (quarter / year)
      - revenue_estimate   (quarter / year)
      - earnings_history   (prior 4Q with actual·estimate·surprise)
      - info               (shares outstanding, market cap)

    Args:
        ticker: yfinance ticker, e.g. "000660.KS".
        use_cache: If True and a same-day cache exists, return it instead of refetching.

    Returns:
        dict matching ConsensusRecord shape (caller wraps in Pydantic).

    Raises:
        NotImplementedError: Codex implementation.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _cache_path("yahoo", ticker)
    if use_cache and cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    ticker_obj = yf.Ticker(ticker)
    raw = {
        "ticker": ticker,
        "as_of": date.today().isoformat(),
        "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
        "earnings_estimate": _records(getattr(ticker_obj, "earnings_estimate", None)),
        "revenue_estimate": _records(getattr(ticker_obj, "revenue_estimate", None)),
        "earnings_history": _records(getattr(ticker_obj, "earnings_history", None)),
        "info": getattr(ticker_obj, "info", {}) or {},
    }
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2, allow_nan=False)
    return raw


def fetch_price_history(ticker: str, period: str = "3y", use_cache: bool = True) -> dict:
    """Fetch quarterly price history for context (forecast chart overlay).

    Args:
        ticker: yfinance ticker.
        period: yfinance period string ("3y", "5y", "max").
        use_cache: Same-day cache reuse.

    Returns:
        dict with daily OHLCV downsampled to quarter-end snapshots.

    Raises:
        NotImplementedError: Codex implementation.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _cache_path(f"price_{period}", ticker)
    if use_cache and cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    history = yf.Ticker(ticker).history(period=period)
    records = _records(history)
    raw = {"ticker": ticker, "period": period, "history": records}
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2, allow_nan=False)
    return raw


def fetch_earnings_dates(ticker: str, limit: int = 24, use_cache: bool = True) -> dict:
    """Fetch past/scheduled earnings-announcement dates (T0 event backbone).

    These timestamps anchor the CAR event study: each row is one earnings event
    with its announcement date and (for past events) EPS estimate/reported/surprise.

    Args:
        ticker: yfinance ticker, e.g. "000660.KS".
        limit: Number of rows to request from yfinance get_earnings_dates.
        use_cache: Same-day cache reuse.

    Returns:
        dict {"ticker": ..., "events": [ {date, epsEstimate, epsReported, surprisePct}, ... ]}.
        Empty fields are explicit None so downstream alignment surfaces gaps.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _cache_path("earnings_dates", ticker)
    if use_cache and cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    frame = yf.Ticker(ticker).get_earnings_dates(limit=limit)
    raw = {"ticker": ticker, "events": _records(frame)}
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2, allow_nan=False)
    return raw
