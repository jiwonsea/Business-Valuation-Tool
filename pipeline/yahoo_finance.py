"""Yahoo Finance market data -- stock price, market cap, beta.

Via yfinance library or direct API calls.
"""

import re

import httpx

# ticker: alphanumeric/dot/hyphen/caret, 1-15 chars (includes KR: 005930.KS etc.)
_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-^]{1,15}$")

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_client = httpx.Client(headers=_HEADERS, timeout=10, follow_redirects=True)


def _validate_ticker(ticker: str) -> str:
    """Validate ticker format. Raises ValueError if invalid."""
    if not _TICKER_RE.match(ticker):
        raise ValueError(f"유효하지 않은 ticker 형식: {ticker!r}")
    return ticker


def get_stock_info(ticker: str) -> dict | None:
    """Fetch basic stock information from Yahoo Finance.

    Returns:
        {"price": float, "market_cap": int, "shares_outstanding": int,
         "beta": float, "currency": str, "name": str} or None
    """
    ticker = _validate_ticker(ticker)
    url = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"

    try:
        resp = _client.get(
            url.format(ticker=ticker),
            params={"interval": "1d", "range": "5d"},
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None

    result_data = data.get("chart", {}).get("result", [])
    if not result_data:
        return None

    meta = result_data[0].get("meta", {})

    return {
        "price": meta.get("regularMarketPrice", 0),
        "currency": meta.get("currency", "USD"),
        "name": meta.get("shortName", ticker),
        "exchange": meta.get("exchangeName", ""),
        "exchange_code": meta.get("exchange", ""),
    }


def get_market_cap(ticker: str) -> int | None:
    """Fetch market cap (KRW or USD). Returns None on failure."""
    summary = get_quote_summary(ticker)
    if summary and summary.get("market_cap"):
        return int(summary["market_cap"])
    return None


# OTC Markets exchange codes (based on Yahoo Finance exchangeName / exchange)
_OTC_EXCHANGES = {
    # By exchangeName
    "PNK",        # OTC Pink Sheets
    "PK",         # OTC Pink
    "OBB",        # OTC Bulletin Board
    "OTC",        # OTC general
    "NCM",        # NASDAQ Capital Market (some small-caps, but regulated exchange)
    # By exchange code
    "PNK",
    "OBB",
    "OQX",        # OTCQX
    "OQB",        # OTCQB
}

# Major regulated exchanges
_MAJOR_EXCHANGES = {
    "NYQ", "NYSE", "NMS", "NAS", "NASDAQ", "NGM",  # NYSE, NASDAQ
    "ASE", "AMEX", "BTS", "BATS",                    # AMEX, BATS
    "PCX", "ARCA", "NYSEArca",                        # NYSE Arca
}


def classify_exchange(exchange_name: str, exchange_code: str = "") -> str:
    """Yahoo Finance exchange info -> listing classification.

    Returns:
        "상장" -- Major exchange (NYSE, NASDAQ, etc.)
        "OTC"  -- Over-the-counter (OTC Pink, OTCQX/QB, OTC BB)
        "비상장" -- Cannot determine
    """
    for val in (exchange_name, exchange_code):
        upper = val.upper().strip()
        if upper in _MAJOR_EXCHANGES:
            return "상장"
        if upper in _OTC_EXCHANGES:
            return "OTC"
        # Partial matching
        if any(otc in upper for otc in ("OTC", "PINK", "BULLETIN")):
            return "OTC"
        if any(ex in upper for ex in ("NYSE", "NASDAQ", "BATS", "ARCA")):
            return "상장"

    return "비상장"


def get_quote_summary(ticker: str) -> dict | None:
    """Yahoo Finance Quote Summary -- detailed information.

    Returns:
        {"market_cap": int, "shares_outstanding": int, "beta": float,
         "enterprise_value": int, "trailing_pe": float, "forward_pe": float,
         "ev_ebitda": float, "price": float} or None
    """
    ticker = _validate_ticker(ticker)
    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
    modules = "defaultKeyStatistics,financialData,summaryDetail,price"

    try:
        resp = _client.get(
            url,
            params={"modules": modules},
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None

    qr = data.get("quoteSummary", {}).get("result", [])
    if not qr:
        return None

    item = qr[0]
    stats = item.get("defaultKeyStatistics", {})
    fin = item.get("financialData", {})
    price_data = item.get("price", {})

    def _raw(d: dict, key: str):
        v = d.get(key, {})
        return v.get("raw") if isinstance(v, dict) else v

    return {
        "market_cap": _raw(price_data, "marketCap") or 0,
        "shares_outstanding": _raw(stats, "sharesOutstanding") or 0,
        "beta": _raw(stats, "beta") or 0,
        "enterprise_value": _raw(stats, "enterpriseValue") or 0,
        "ev_ebitda": _raw(stats, "enterpriseToEbitda") or 0,
        "trailing_pe": _raw(stats, "trailingPE") or 0,
        "forward_pe": _raw(stats, "forwardPE") or 0,
        "price": _raw(price_data, "regularMarketPrice") or 0,
        "currency": price_data.get("currency", "USD"),
    }
