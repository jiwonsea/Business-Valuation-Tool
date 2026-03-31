"""yfinance-based financial statement and market data collection.

Auto-detects KOSPI (.KS) / KOSDAQ (.KQ), provides 3-year financials and market data.
Unlike engine/, this is a pipeline module that performs IO, so httpx/yfinance usage is allowed.
"""

import logging
import os
import shutil

# ── Fix Windows unicode username SSL certificate path issue ──
# yfinance (curl_cffi-based) cannot read CA cert from unicode paths.
# Setting os.environ alone doesn't propagate to the already-loaded native curl library,
# so we call Win32 API SetEnvironmentVariableW directly via ctypes.
_CA_BUNDLE_PATH = "C:/ProgramData/yfinance_cacert.pem"

if os.name == "nt":
    try:
        import certifi
        ca_src = certifi.where()
        if not ca_src.isascii():
            os.makedirs(os.path.dirname(_CA_BUNDLE_PATH), exist_ok=True)
            if not os.path.exists(_CA_BUNDLE_PATH):
                shutil.copy2(ca_src, _CA_BUNDLE_PATH)
            # Set both Python os.environ and Win32 API
            os.environ["CURL_CA_BUNDLE"] = _CA_BUNDLE_PATH
            import ctypes
            ctypes.windll.kernel32.SetEnvironmentVariableW("CURL_CA_BUNDLE", _CA_BUNDLE_PATH)
    except Exception:
        pass

import yfinance as yf

logger = logging.getLogger(__name__)

# ── Cache ──
_kr_ticker_cache: dict[str, str] = {}
_kr_exchange_cache: dict[str, str] = {}  # ticker → "KOSPI" | "KOSDAQ"
_ticker_info_cache: dict[str, dict] = {}  # resolved_ticker → yf.Ticker().info


def _get_ticker_info(resolved: str) -> dict:
    """Cached yf.Ticker().info lookup (called only once per session)."""
    if resolved in _ticker_info_cache:
        return _ticker_info_cache[resolved]
    t = yf.Ticker(resolved)
    info = t.info or {}
    _ticker_info_cache[resolved] = info
    return info


def _get_ticker_obj(resolved: str) -> yf.Ticker:
    """Return yf.Ticker object + cache info as side effect."""
    t = yf.Ticker(resolved)
    if resolved not in _ticker_info_cache:
        _ticker_info_cache[resolved] = t.info or {}
    return t


def _is_valid_yf_ticker(info: dict, raw_ticker: str) -> bool:
    """Validate whether yfinance info contains valid ticker data.

    When queried with an incorrect suffix (.KS/.KQ), the price may still appear
    but longName returns a corrupted string (e.g., "247540.KS,0P0001GZPV,...").
    """
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not price or price <= 0:
        return False
    name = info.get("longName") or info.get("shortName") or ""
    # Name starting with raw ticker indicates corrupted data
    if name.startswith(raw_ticker):
        return False
    return True


def resolve_kr_ticker(ticker: str) -> str:
    """Convert Korean stock code to yfinance ticker (auto-detect KOSPI .KS / KOSDAQ .KQ).

    Detection strategy:
      1) Query with .KS -> if price + valid longName, it's KOSPI
      2) Query with .KQ -> if price + valid longName, it's KOSDAQ
      3) Both fail -> .KS fallback
    """
    if ticker in _kr_ticker_cache:
        return _kr_ticker_cache[ticker]

    # Try KOSPI (.KS)
    ks = f"{ticker}.KS"
    try:
        info = _get_ticker_info(ks)
        if _is_valid_yf_ticker(info, ticker):
            _kr_ticker_cache[ticker] = ks
            _kr_exchange_cache[ticker] = "KOSPI"
            return ks
    except Exception:
        pass

    # Try KOSDAQ (.KQ)
    kq = f"{ticker}.KQ"
    try:
        info = _get_ticker_info(kq)
        if _is_valid_yf_ticker(info, ticker):
            _kr_ticker_cache[ticker] = kq
            _kr_exchange_cache[ticker] = "KOSDAQ"
            return kq
    except Exception:
        pass

    # fallback
    _kr_ticker_cache[ticker] = ks
    _kr_exchange_cache[ticker] = "KOSPI"
    return ks


def get_exchange_segment(ticker: str) -> str:
    """Return exchange segment from cache (use after calling resolve_kr_ticker)."""
    return _kr_exchange_cache.get(ticker, "")


def _resolve_ticker(ticker: str, market: str) -> str:
    """Convert to yfinance ticker format based on market."""
    if market == "KR":
        return resolve_kr_ticker(ticker)
    return ticker  # US: as-is


def _safe_get(df, row_labels: list[str], col_idx: int = 0):
    """Return the first matching value from multiple candidate row labels in a DataFrame."""
    if df is None or df.empty:
        return None
    for label in row_labels:
        if label in df.index:
            try:
                val = df.loc[label].iloc[col_idx]
                if val is not None and str(val) != "nan":
                    return float(val)
            except (IndexError, TypeError):
                continue
    return None


def _scale_value(raw_val, currency: str) -> int:
    """Convert raw currency value to million KRW / $M unit.

    yfinance returns values in the base currency unit (KRW, USD, etc.).
    KRW: / 1,000,000 -> million KRW
    USD: / 1,000,000 -> $M
    Other: / 1,000,000 (default)
    """
    if raw_val is None:
        return 0
    return round(float(raw_val) / 1_000_000)


from .api_guard import api_guard


@api_guard("yfinance")
def fetch_financials(ticker: str, market: str = "US") -> dict[int, dict] | None:
    """Collect 3-year financial statements via yfinance.

    Returns:
        {year: {revenue, op, net_income, assets, liabilities, equity,
                dep, amort, gross_borr, net_borr, de_ratio, interest_expense}}
        KR=million KRW, US=$M. None if fetch fails.
    """
    resolved = _resolve_ticker(ticker, market)
    try:
        t = _get_ticker_obj(resolved)
        info = _ticker_info_cache.get(resolved, {})
        currency = info.get("currency", "USD" if market == "US" else "KRW")

        # Annual financial statements (DataFrame, columns = dates)
        inc = t.financials  # Income Statement
        bs = t.balance_sheet  # Balance Sheet
        cf = t.cashflow  # Cashflow

        if inc is None or inc.empty:
            logger.warning("yfinance 손익계산서 없음: %s", resolved)
            return None

    except Exception as e:
        logger.warning("yfinance 데이터 수집 실패 (%s): %s", resolved, e)
        return None

    result = {}
    # Process each column (date) -- up to 3 years
    for col_idx in range(min(3, inc.shape[1] if inc is not None else 0)):
        try:
            col_date = inc.columns[col_idx]
            year = col_date.year if hasattr(col_date, "year") else int(str(col_date)[:4])
        except (IndexError, ValueError):
            continue

        def _get_inc(labels):
            return _safe_get(inc, labels, col_idx)

        def _get_bs(labels):
            return _safe_get(bs, labels, col_idx) if bs is not None else None

        def _get_cf(labels):
            return _safe_get(cf, labels, col_idx) if cf is not None else None

        # Income Statement
        revenue = _get_inc(["Total Revenue", "Revenue", "Operating Revenue"])
        op = _get_inc(["Operating Income", "EBIT", "Operating Profit"])
        net_income = _get_inc(["Net Income", "Net Income Common Stockholders",
                               "Net Income From Continuing Operations"])
        interest_expense = _get_inc(["Interest Expense", "Interest Expense Non Operating",
                                     "Net Interest Income"])

        # Balance Sheet
        assets = _get_bs(["Total Assets"])
        liabilities = _get_bs(["Total Liabilities Net Minority Interest",
                               "Total Liab", "Total Liabilities"])
        equity = _get_bs(["Stockholders Equity", "Total Equity Gross Minority Interest",
                          "Common Stock Equity", "Total Stockholder Equity"])
        total_debt = _get_bs(["Total Debt", "Net Debt"])  # Interest-bearing debt
        long_term_debt = _get_bs(["Long Term Debt", "Long Term Debt And Capital Lease Obligation"])
        short_term_debt = _get_bs(["Current Debt", "Current Debt And Capital Lease Obligation",
                                   "Short Long Term Debt"])
        cash = _get_bs(["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments",
                        "Cash Financial", "Cash And Short Term Investments"])

        # Cashflow — D&A
        dep_amort = _get_cf(["Depreciation And Amortization",
                             "Depreciation Amortization Depletion"])
        dep_only = _get_cf(["Depreciation"])
        amort_only = _get_cf(["Amortization Of Intangibles", "Amortization"])

        # Scaling
        s = lambda v: _scale_value(v, currency)  # noqa: E731

        revenue_s = s(revenue)
        op_s = s(op)
        net_income_s = s(net_income)
        assets_s = s(assets)
        liabilities_s = s(liabilities)
        equity_s = s(equity)
        interest_expense_s = s(interest_expense) if interest_expense else 0

        # Separate D&A
        if dep_only is not None and amort_only is not None:
            dep_s = s(dep_only)
            amort_s = s(amort_only)
        elif dep_amort is not None:
            dep_s = s(dep_amort)
            amort_s = 0
        else:
            dep_s = 0
            amort_s = 0

        # Interest-bearing debt (gross_borr)
        if total_debt is not None and total_debt > 0:
            gross_borr_s = s(total_debt)
        elif long_term_debt is not None or short_term_debt is not None:
            gross_borr_s = s(long_term_debt or 0) + s(short_term_debt or 0)
        else:
            gross_borr_s = 0

        cash_s = s(cash) if cash else 0
        net_borr_s = gross_borr_s - cash_s

        # D/E ratio (interest-bearing debt / book equity)
        de_ratio = round(gross_borr_s / equity_s * 100, 1) if equity_s > 0 else 0.0

        result[year] = {
            "revenue": revenue_s,
            "op": op_s,
            "net_income": net_income_s,
            "assets": assets_s,
            "liabilities": liabilities_s,
            "equity": equity_s,
            "dep": dep_s,
            "amort": amort_s,
            "gross_borr": gross_borr_s,
            "net_borr": net_borr_s,
            "de_ratio": de_ratio,
            "interest_expense": interest_expense_s,
        }

    return result if result else None


@api_guard("yfinance")
def fetch_market_data(ticker: str, market: str = "US") -> dict | None:
    """Collect market data from yfinance.

    Returns:
        {price, market_cap, beta, industry, shares_outstanding,
         currency, exchange, exchange_code}
    """
    resolved = _resolve_ticker(ticker, market)
    try:
        info = _get_ticker_info(resolved)
        if not info.get("regularMarketPrice") and not info.get("currentPrice"):
            logger.warning("yfinance 시장 데이터 없음: %s", resolved)
            return None

        price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        market_cap_raw = info.get("marketCap", 0)
        currency = info.get("currency", "USD" if market == "US" else "KRW")

        # market_cap: convert to million KRW or $M
        market_cap = round(market_cap_raw / 1_000_000) if market_cap_raw else 0

        return {
            "price": price,
            "market_cap": market_cap,  # million KRW / $M
            "beta": info.get("beta"),
            "industry": info.get("industry", ""),
            "shares_outstanding": info.get("sharesOutstanding", 0),
            "currency": currency,
            "exchange": info.get("exchange", ""),
            "exchange_code": info.get("exchangeTimezoneName", ""),
        }
    except Exception as e:
        logger.warning("yfinance 시장 데이터 실패 (%s): %s", resolved, e)
        return None
