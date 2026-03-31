"""Yahoo Finance 시장 데이터 — 주가, 시가총액, beta.

yfinance 라이브러리 또는 직접 API 호출.
"""

import httpx


def get_stock_info(ticker: str) -> dict | None:
    """Yahoo Finance에서 주식 기본 정보 조회.

    Returns:
        {"price": float, "market_cap": int, "shares_outstanding": int,
         "beta": float, "currency": str, "name": str} or None
    """
    url = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        resp = httpx.get(
            url.format(ticker=ticker),
            headers=headers,
            params={"interval": "1d", "range": "5d"},
            timeout=10,
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


# OTC Markets 거래소 코드 (Yahoo Finance exchangeName / exchange 기준)
_OTC_EXCHANGES = {
    # exchangeName 기준
    "PNK",        # OTC Pink Sheets
    "PK",         # OTC Pink
    "OBB",        # OTC Bulletin Board
    "OTC",        # OTC 일반
    "NCM",        # NASDAQ Capital Market (일부 소형주이나 정규 거래소)
    # exchange 코드 기준
    "PNK",
    "OBB",
    "OQX",        # OTCQX
    "OQB",        # OTCQB
}

# 주요 정규 거래소
_MAJOR_EXCHANGES = {
    "NYQ", "NYSE", "NMS", "NAS", "NASDAQ", "NGM",  # NYSE, NASDAQ
    "ASE", "AMEX", "BTS", "BATS",                    # AMEX, BATS
    "PCX", "ARCA", "NYSEArca",                        # NYSE Arca
}


def classify_exchange(exchange_name: str, exchange_code: str = "") -> str:
    """Yahoo Finance 거래소 정보 → 상장 구분.

    Returns:
        "상장" — 주요 거래소 (NYSE, NASDAQ 등)
        "OTC"  — 장외 거래소 (OTC Pink, OTCQX/QB, OTC BB)
        "비상장" — 판별 불가
    """
    for val in (exchange_name, exchange_code):
        upper = val.upper().strip()
        if upper in _MAJOR_EXCHANGES:
            return "상장"
        if upper in _OTC_EXCHANGES:
            return "OTC"
        # 부분 매칭
        if any(otc in upper for otc in ("OTC", "PINK", "BULLETIN")):
            return "OTC"
        if any(ex in upper for ex in ("NYSE", "NASDAQ", "BATS", "ARCA")):
            return "상장"

    return "비상장"


def get_quote_summary(ticker: str) -> dict | None:
    """Yahoo Finance Quote Summary — 상세 정보.

    Returns:
        {"market_cap": int, "shares_outstanding": int, "beta": float,
         "enterprise_value": int, "trailing_pe": float, "forward_pe": float,
         "ev_ebitda": float, "price": float} or None
    """
    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
    modules = "defaultKeyStatistics,financialData,summaryDetail,price"

    try:
        resp = httpx.get(
            url,
            params={"modules": modules},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
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
