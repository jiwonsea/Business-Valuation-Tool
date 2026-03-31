"""Market-specific macro data -- terminal growth rate, effective tax rate, diluted shares estimation.

Since engine functions are pure, values collected/calculated here are injected into profiles.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


# ── Terminal growth rate defaults ──

# Market-specific long-term expected growth rate (nominal GDP growth ~ inflation + real GDP)
_DEFAULT_TERMINAL_GROWTH = {
    "US": 2.5,   # US: ~2% inflation + ~0.5% real growth (conservative)
    "KR": 2.0,   # KR: ~2% target inflation + ~0% potential growth (aging demographics)
}

# ── FRED persistent disk cache ──
_FRED_CACHE_PATH = Path(__file__).resolve().parent.parent / ".cache" / "fred" / "breakeven.json"
_FRED_CACHE_TTL = 86400  # 24 hours


def get_terminal_growth(market: str = "KR") -> float:
    """Return market-specific terminal growth rate default (%).

    Uses the latest expected inflation from FRED API when available,
    falls back to hardcoded defaults on failure.
    """
    # FRED API (US 10Y Breakeven Inflation Rate)
    if market == "US":
        try:
            rate = _fetch_fred_breakeven()
            if rate is not None:
                # Breakeven ~ expected inflation, +0.5%p real growth
                return round(rate + 0.5, 1)
        except Exception as e:
            logger.debug("FRED breakeven 조회 실패: %s", e)

    return _DEFAULT_TERMINAL_GROWTH.get(market, 2.0)


def _fetch_fred_breakeven() -> float | None:
    """FRED: 10-Year Breakeven Inflation Rate (T10YIE).

    Public API -- no API key required.
    Uses persistent disk cache (TTL 24h) to avoid redundant API calls.
    """
    # 1) Check disk cache
    if _FRED_CACHE_PATH.exists():
        try:
            if time.time() - _FRED_CACHE_PATH.stat().st_mtime < _FRED_CACHE_TTL:
                data = json.loads(_FRED_CACHE_PATH.read_text(encoding="utf-8"))
                cached_val = data.get("value")
                if cached_val is not None:
                    logger.debug("FRED 캐시 적중: %.2f%%", cached_val)
                    return cached_val
        except (json.JSONDecodeError, OSError):
            pass

    # 2) API call with dynamic date window (last 90 days)
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
    cosd = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    try:
        resp = httpx.get(
            url,
            params={"id": "T10YIE", "cosd": cosd},
            timeout=5,
        )
        resp.raise_for_status()
        lines = resp.text.strip().split("\n")
        if len(lines) < 2:
            return None
        # Value from last row
        last_val = lines[-1].split(",")[-1].strip()
        if last_val == ".":
            return None
        rate = float(last_val)

        # 3) Save to disk cache
        try:
            _FRED_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            _FRED_CACHE_PATH.write_text(
                json.dumps({"value": rate, "fetched_at": datetime.now().isoformat()}),
                encoding="utf-8",
            )
        except OSError:
            pass  # Cache write failure is non-critical

        return rate
    except (httpx.HTTPError, ValueError, IndexError):
        return None


# ── Effective tax rate ──

def calc_effective_tax_rate(financials: dict[int, dict]) -> float | None:
    """Reverse-calculate effective tax rate from financial statements (%).

    Effective tax rate = 1 - (net income / pre-tax income)
    Pre-tax income = operating income + non-operating (approximation: direct calc, not reverse from net/(1-tax))

    In practice, uses the average of the most recent 3 years.
    """
    rates = []
    for year in sorted(financials.keys(), reverse=True)[:3]:
        data = financials[year]
        net_income = data.get("net_income", 0)
        op = data.get("op", 0)

        # Pre-tax income approximation: based on operating income (ignoring non-operating -- non-financial companies only)
        # More accurate when pre_tax_income field is available
        pre_tax = data.get("pre_tax_income", 0)
        if pre_tax <= 0 and op > 0 and net_income > 0:
            # Reverse from net income to operating income ratio
            pre_tax = op  # Conservative approximation (assumes non-operating = 0)

        if pre_tax > 0 and net_income >= 0:
            rate = (1 - net_income / pre_tax) * 100
            if 0 <= rate <= 60:  # Filter out abnormal values
                rates.append(rate)

    if rates:
        return round(sum(rates) / len(rates), 1)
    return None


# ── Diluted shares outstanding ──

def get_diluted_shares(ticker: str, market: str = "US") -> int | None:
    """Fetch diluted shares outstanding from Yahoo Finance.

    Actual share count reflecting SBC/stock options.
    """
    from . import yahoo_finance  # lazy: optional pipeline dependency

    if market == "KR":
        try:
            from . import yfinance_fetcher
            ticker = yfinance_fetcher.resolve_kr_ticker(ticker)
        except ImportError:
            ticker = f"{ticker}.KS"

    try:
        summary = yahoo_finance.get_quote_summary(ticker)
        if summary:
            # Yahoo's sharesOutstanding is basic shares
            # No separate diluted field, so return basic
            # (Parsing directly from SEC filings would be more accurate but out of scope)
            return summary.get("shares_outstanding", 0) or None
    except Exception as e:
        logger.debug("희석주식수 조회 실패 (%s): %s", ticker, e)
    return None
