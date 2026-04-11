"""Fetch historical outcome prices for backtesting via yfinance."""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Optional

from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)

# Fields that yfinance returns no data for (but target date is in the past)
_MAX_RETRIES = 3
_RETRY_BASE_SECONDS = 2.0
_BACKWARD_SEARCH_DAYS = 7  # Search backward for nearest trading day


def _resolve_ticker(ticker: str, market: str) -> str:
    """Resolve ticker to yfinance-compatible format."""
    if market == "KR":
        try:
            from pipeline.yfinance_fetcher import resolve_kr_ticker

            return resolve_kr_ticker(ticker)
        except (ImportError, Exception) as e:
            logger.debug("KR ticker resolution failed for %s: %s", ticker, e)
            if not ticker.endswith((".KS", ".KQ")):
                return f"{ticker}.KS"
    return ticker


def _fetch_price_at_date(
    yf_ticker,
    target: date,
    today: date,
) -> tuple[Optional[float], Optional[date], Optional[str]]:
    """Fetch closing price at or before target date.

    Returns:
        (price, actual_date, error_message)
        - price=None, error=None means future date (not yet available)
        - price=None, error=str means fetch failed
    """
    if target > today:
        return None, None, None  # Future date, not an error

    # Search backward only (no lookahead bias)
    start = target - timedelta(days=_BACKWARD_SEARCH_DAYS)
    end = target + timedelta(days=1)  # yfinance end is exclusive

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            hist = yf_ticker.history(
                start=start.isoformat(), end=end.isoformat(), auto_adjust=True
            )
            if hist is not None and not hist.empty:
                # Get the last available trading day on or before target
                price = float(hist["Close"].iloc[-1])
                actual_date = hist.index[-1].date()
                return price, actual_date, None

            # Empty DataFrame — could be rate limit or delisted
            if attempt < _MAX_RETRIES:
                wait = _RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                logger.debug(
                    "Empty result for %s at %s, retry %d/%d in %.1fs",
                    yf_ticker.ticker,
                    target,
                    attempt,
                    _MAX_RETRIES,
                    wait,
                )
                time.sleep(wait)
            else:
                return None, None, "no_data_after_retries"

        except Exception as e:
            if attempt < _MAX_RETRIES:
                wait = _RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                logger.debug(
                    "Error fetching %s at %s: %s, retry %d/%d",
                    yf_ticker.ticker,
                    target,
                    e,
                    attempt,
                    _MAX_RETRIES,
                )
                time.sleep(wait)
            else:
                return None, None, f"exception: {e}"

    return None, None, "max_retries_exceeded"


def fetch_outcome_prices(
    ticker: str,
    market: str,
    analysis_date: date,
    horizons_months: list[int] | None = None,
) -> dict:
    """Fetch actual market prices at T+N month horizons.

    Args:
        ticker: Stock ticker (e.g., "005930", "AAPL")
        market: "KR" or "US"
        analysis_date: Date of the original valuation
        horizons_months: List of month offsets (default: [3, 6, 12])

    Returns:
        {
            "price_t0": float | None,
            "price_t3m": float | None, "date_t3m": date | None,
            "price_t6m": float | None, "date_t6m": date | None,
            "price_t12m": float | None, "date_t12m": date | None,
            "fetch_errors": {horizon_key: error_message},
        }
    """
    import yfinance as yf

    if horizons_months is None:
        horizons_months = [3, 6, 12]

    resolved = _resolve_ticker(ticker, market)
    yf_ticker = yf.Ticker(resolved)
    today = date.today()

    result: dict = {"fetch_errors": {}}

    # T0 price (at analysis date)
    price_t0, _, err_t0 = _fetch_price_at_date(yf_ticker, analysis_date, today)
    result["price_t0"] = price_t0
    if err_t0:
        result["fetch_errors"]["t0"] = err_t0

    # Horizon prices
    horizon_map = {3: "t3m", 6: "t6m", 12: "t12m"}
    for months in horizons_months:
        key = horizon_map.get(months, f"t{months}m")
        target = analysis_date + relativedelta(months=months)

        price, actual_date, err = _fetch_price_at_date(yf_ticker, target, today)
        result[f"price_{key}"] = price
        result[f"date_{key}"] = actual_date
        if err:
            result["fetch_errors"][key] = err

    return result
