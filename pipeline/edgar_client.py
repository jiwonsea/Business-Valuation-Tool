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


_KR_TICKER = re.compile(r"(\d{6})(?:\.(?:KS|KQ))?")
_JP_TICKER = re.compile(r"(\d{4})(?:\.T)?")
_CLASS_TICKER = re.compile(r"([A-Z]{1,5})[.\-]([A-Z])")


def _ticker_key(ticker: str) -> str | None:
    """Normal form in which two notations of one ticker are equal.

    The folding of the selection check (_comparable_ticker in
    pipeline/profile_generator.py), repeated here so that this client does not
    import that module; tests/test_ticker_identification.py compares the two.
    005930.KS = 005930, 7203.T = 7203, BRK-B = BRK.B. A dot is a hyphen only
    in that share-class notation: AB.CD is not AB-CD. None for a blank string:
    no ticker.
    """
    text = "".join(ticker.split()).upper()
    if not text:
        return None
    for pattern, form in (
        (_KR_TICKER, r"\1"),
        (_JP_TICKER, r"\1"),
        (_CLASS_TICKER, r"\1.\2"),
    ):
        match = pattern.fullmatch(text)
        if match:
            return match.expand(form)
    return text


@api_guard("edgar")
def search_company(query: str, ticker: str | None = None) -> list[dict]:
    """Search SEC-registered companies by name or ticker.

    Args:
        ticker: ticker the caller selected for this company, if any. When the
            result would not start with it, its row is moved to the front: a
            short ticker ("ON") is otherwise preceded, and past ten rows cut
            off, by companies whose name merely contains the query. The row
            spelled like the selection is preferred over one in another
            notation of the same ticker ("BRK.B" finds "BRK-B"). A result
            that already starts with the selected ticker is left as it is.

    Returns:
        [{"cik": "320193", "ticker": "AAPL", "name": "Apple Inc."}]
    """
    resp = _client.get(COMPANY_TICKERS_URL)
    resp.raise_for_status()
    data = resp.json()

    selected = ticker.strip() if isinstance(ticker, str) else ""
    wanted = _ticker_key(selected)
    spelled = None  # first row whose ticker is the selected one as spelled
    folded = None  # first row whose ticker is another notation of it

    results = []
    query_lower = query.lower()
    for _, entry in data.items():
        name = entry.get("title", "")
        entry_ticker = entry.get("ticker", "")
        matches = query_lower in name.lower() or query_lower == entry_ticker.lower()
        is_spelled = is_folded = False
        if wanted is not None and entry_ticker:
            is_spelled = spelled is None and entry_ticker.upper() == selected.upper()
            is_folded = (
                not is_spelled
                and folded is None
                and _ticker_key(entry_ticker) == wanted
            )
        if not (matches or is_spelled or is_folded):
            continue
        row = {
            "cik": str(entry["cik_str"]),
            "ticker": entry_ticker,
            "name": name,
        }
        if matches:
            results.append(row)
        if is_spelled:
            spelled = row
        elif is_folded:
            folded = row

    first = spelled or folded
    if first is not None and not (
        results and _ticker_key(results[0]["ticker"]) == wanted
    ):
        # only the row moved up leaves its old place; other rows with the
        # same ticker or the same CIK stay
        results = [first] + [row for row in results if row is not first]
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
