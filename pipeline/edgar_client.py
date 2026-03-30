"""SEC EDGAR API 클라이언트 — 미국 기업 재무제표 조회.

무료, API Key 불필요. User-Agent 헤더 필수 (SEC 정책).
https://www.sec.gov/edgar/sec-api-documentation
"""

import httpx

EDGAR_BASE = "https://data.sec.gov"
EDGAR_FULL_TEXT = "https://efts.sec.gov/LATEST"
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

HEADERS = {
    "User-Agent": "KoreanValuationTool/1.0 (contact@example.com)",
    "Accept-Encoding": "gzip, deflate",
}


def search_company(query: str) -> list[dict]:
    """기업명 또는 ticker로 SEC 등록 기업 검색.

    Returns:
        [{"cik": "320193", "ticker": "AAPL", "name": "Apple Inc."}]
    """
    resp = httpx.get(COMPANY_TICKERS_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results = []
    query_lower = query.lower()
    for _, entry in data.items():
        name = entry.get("title", "")
        ticker = entry.get("ticker", "")
        if query_lower in name.lower() or query_lower == ticker.lower():
            results.append({
                "cik": str(entry["cik_str"]),
                "ticker": ticker,
                "name": name,
            })
    return results[:10]


def get_company_facts(cik: str) -> dict:
    """기업의 전체 XBRL Fact 데이터 조회.

    SEC Company Facts API: 모든 재무 항목의 전 기간 데이터.

    Args:
        cik: CIK 번호 (zero-padded 불필요, 자동 처리)

    Returns:
        Raw JSON (매우 큰 dict — 필요한 항목만 파싱하여 사용)
    """
    cik_padded = cik.zfill(10)
    url = f"{EDGAR_BASE}/api/xbrl/companyfacts/CIK{cik_padded}.json"
    resp = httpx.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_company_concept(cik: str, taxonomy: str, concept: str) -> dict:
    """특정 XBRL concept의 전 기간 데이터 조회.

    예: get_company_concept("320193", "us-gaap", "Revenues")

    Args:
        cik: CIK 번호
        taxonomy: "us-gaap" | "dei" | "ifrs-full"
        concept: XBRL 태그명 (e.g., "Revenues", "NetIncomeLoss")

    Returns:
        {"units": {"USD": [{"val": ..., "fy": ..., "fp": ...}]}}
    """
    cik_padded = cik.zfill(10)
    url = f"{EDGAR_BASE}/api/xbrl/companyconcept/CIK{cik_padded}/{taxonomy}/{concept}.json"
    resp = httpx.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_submissions(cik: str) -> dict:
    """기업의 제출 이력 조회 (filing history).

    10-K, 10-Q 등 filing 목록 + 기본 기업정보.

    Returns:
        {"name": str, "tickers": list, "filings": {"recent": {...}}}
    """
    cik_padded = cik.zfill(10)
    url = f"{EDGAR_BASE}/submissions/CIK{cik_padded}.json"
    resp = httpx.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()
