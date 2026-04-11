"""SEC EDGAR API client -- US company financial statement retrieval.

Free, no API key required. User-Agent header mandatory (SEC policy).
https://www.sec.gov/edgar/sec-api-documentation
"""

import atexit
import re

import httpx

_CIK_RE = re.compile(r"^\d{1,10}$")

EDGAR_BASE = "https://data.sec.gov"
EDGAR_FULL_TEXT = "https://efts.sec.gov/LATEST"
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

HEADERS = {
    "User-Agent": "KoreanValuationTool/1.0 (contact@example.com)",
    "Accept-Encoding": "gzip, deflate",
}

_client = httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True)
atexit.register(_client.close)

from .api_guard import api_guard


@api_guard("edgar")
def search_company(query: str) -> list[dict]:
    """Search SEC-registered companies by name or ticker.

    Returns:
        [{"cik": "320193", "ticker": "AAPL", "name": "Apple Inc."}]
    """
    resp = _client.get(COMPANY_TICKERS_URL)
    resp.raise_for_status()
    data = resp.json()

    results = []
    query_lower = query.lower()
    for _, entry in data.items():
        name = entry.get("title", "")
        ticker = entry.get("ticker", "")
        if query_lower in name.lower() or query_lower == ticker.lower():
            results.append(
                {
                    "cik": str(entry["cik_str"]),
                    "ticker": ticker,
                    "name": name,
                }
            )
    return results[:10]


def _validate_cik(cik: str) -> str:
    """Validate CIK number format. Raises ValueError if invalid."""
    if not _CIK_RE.match(cik):
        raise ValueError(f"유효하지 않은 CIK 형식: {cik!r}")
    return cik


@api_guard("edgar")
def get_company_facts(cik: str) -> dict:
    """Retrieve full XBRL Fact data for a company.

    SEC Company Facts API: all financial items across all periods.

    Args:
        cik: CIK number (zero-padding not required, handled automatically)

    Returns:
        Raw JSON (very large dict -- parse only needed items)
    """
    cik_padded = _validate_cik(cik).zfill(10)
    url = f"{EDGAR_BASE}/api/xbrl/companyfacts/CIK{cik_padded}.json"
    resp = _client.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


@api_guard("edgar")
def get_company_concept(cik: str, taxonomy: str, concept: str) -> dict:
    """Retrieve all-period data for a specific XBRL concept.

    Example: get_company_concept("320193", "us-gaap", "Revenues")

    Args:
        cik: CIK number
        taxonomy: "us-gaap" | "dei" | "ifrs-full"
        concept: XBRL tag name (e.g., "Revenues", "NetIncomeLoss")

    Returns:
        {"units": {"USD": [{"val": ..., "fy": ..., "fp": ...}]}}
    """
    cik_padded = _validate_cik(cik).zfill(10)
    url = f"{EDGAR_BASE}/api/xbrl/companyconcept/CIK{cik_padded}/{taxonomy}/{concept}.json"
    resp = _client.get(url)
    resp.raise_for_status()
    return resp.json()


@api_guard("edgar")
def get_submissions(cik: str) -> dict:
    """Retrieve company submission history (filing history).

    10-K, 10-Q filing list + basic company info.

    Returns:
        {"name": str, "tickers": list, "filings": {"recent": {...}}}
    """
    cik_padded = _validate_cik(cik).zfill(10)
    url = f"{EDGAR_BASE}/submissions/CIK{cik_padded}.json"
    resp = _client.get(url)
    resp.raise_for_status()
    return resp.json()
