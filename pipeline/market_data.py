"""Market data collection -- shares, market cap, OTC prices.

Data collected from KRX, 38.co.kr, etc.
"""

import re

import httpx
from bs4 import BeautifulSoup

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_client = httpx.Client(headers=_HEADERS, timeout=15, follow_redirects=True)

from .api_guard import api_guard


@api_guard("krx")
def get_38_company_info(company_name: str) -> dict | None:
    """Fetch unlisted company information from 38.co.kr.

    Returns:
        {"shares_total": int, "par_value": int, "capital": int,
         "otc_price": int, "otc_volume_avg": int} or None
    """
    # Search
    search_url = "https://www.38.co.kr/html/fund/index.htm"
    params = {"o": "k", "key": company_name}

    try:
        resp = _client.get(search_url, params=params)
        resp.raise_for_status()
    except httpx.HTTPError:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    result = {}

    # Extract key information from table
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        label = cells[0].get_text(strip=True)
        value = cells[1].get_text(strip=True)

        if "주식수" in label or "발행주식" in label:
            nums = re.findall(r"[\d,]+", value)
            if nums:
                result["shares_total"] = int(nums[0].replace(",", ""))
        elif "액면가" in label:
            nums = re.findall(r"[\d,]+", value)
            if nums:
                result["par_value"] = int(nums[0].replace(",", ""))
        elif "자본금" in label:
            nums = re.findall(r"[\d,.]+", value)
            if nums:
                result["capital"] = int(float(nums[0].replace(",", "")))

    return result if result else None


@api_guard("krx")
def get_krx_market_cap(stock_code: str) -> dict | None:
    """Fetch listed company market cap from KRX.

    Args:
        stock_code: Stock code (e.g., "005930")

    Returns:
        {"market_cap": int, "price": int, "shares": int} or None
    """
    url = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
    payload = {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT01501",
        "isuCd": stock_code,
    }

    try:
        resp = _client.post(url, data=payload)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None

    items = data.get("OutBlock_1", [])
    if not items:
        return None

    item = items[0]
    return {
        "market_cap": int(item.get("MKTCAP", "0").replace(",", "")),
        "price": int(item.get("TDD_CLSPRC", "0").replace(",", "")),
        "shares": int(item.get("LIST_SHRS", "0").replace(",", "")),
    }
