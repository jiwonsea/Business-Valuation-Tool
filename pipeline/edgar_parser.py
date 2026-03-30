"""SEC EDGAR XBRL 응답 → 구조화된 재무 데이터 변환.

Company Facts API의 us-gaap 태그를 파싱하여
연결 재무제표(consolidated) dict로 변환한다.
금액 단위: USD millions ($M)
"""

from .edgar_client import get_company_facts

# XBRL us-gaap 태그 → 내부 키 매핑
# 기업마다 사용하는 태그가 다를 수 있으므로 fallback 리스트 제공
CONCEPT_MAP = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "op": [
        "OperatingIncomeLoss",
    ],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
    ],
    "assets": [
        "Assets",
    ],
    "liabilities": [
        "Liabilities",
    ],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "dep": [
        "Depreciation",
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
    ],
    "amort": [
        "AmortizationOfIntangibleAssets",
    ],
    "gross_borr": [
        "LongTermDebt",
        "LongTermDebtAndCapitalLeaseObligations",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsAndShortTermInvestments",
    ],
}


def _to_millions(val: float | int) -> int:
    """USD raw → USD millions."""
    return round(val / 1_000_000)


def _extract_annual(facts: dict, concepts: list[str], year: int) -> int | None:
    """XBRL facts에서 특정 연도의 연간(10-K) 값 추출.

    Args:
        facts: company facts raw JSON
        concepts: 시도할 XBRL 태그 리스트 (우선순위)
        year: fiscal year

    Returns:
        USD millions 정수 or None
    """
    us_gaap = facts.get("facts", {}).get("us-gaap", {})

    for concept in concepts:
        concept_data = us_gaap.get(concept, {})
        units = concept_data.get("units", {})
        usd_entries = units.get("USD", [])

        for entry in usd_entries:
            # 연간 데이터만 (fp="FY"), 해당 연도
            if entry.get("fp") == "FY" and entry.get("fy") == year:
                # 10-K filing 우선
                form = entry.get("form", "")
                if form in ("10-K", "10-K/A"):
                    return _to_millions(entry["val"])

        # 10-K가 없으면 FY 아무거나
        for entry in usd_entries:
            if entry.get("fp") == "FY" and entry.get("fy") == year:
                return _to_millions(entry["val"])

    return None


def parse_financials(cik: str, years: list[int] | None = None) -> dict[int, dict]:
    """CIK → 연도별 연결 재무제표 dict.

    Args:
        cik: SEC CIK 번호
        years: 조회할 연도 리스트 (None이면 최근 3년)

    Returns:
        {2024: {"revenue": int, "op": int, ..., "de_ratio": float}, ...}
        금액 단위: USD millions
    """
    facts = get_company_facts(cik)

    if years is None:
        # 최근 filing에서 연도 추정
        years = _guess_recent_years(facts)

    result = {}
    for year in years:
        row = {}
        for internal_key, concepts in CONCEPT_MAP.items():
            val = _extract_annual(facts, concepts, year)
            row[internal_key] = val if val is not None else 0

        # D&A fallback: dep+amort가 없으면 DDA에서 추정
        if row.get("dep", 0) == 0 and row.get("amort", 0) == 0:
            dda = _extract_annual(facts, ["DepreciationDepletionAndAmortization"], year)
            if dda:
                row["dep"] = dda
                row["amort"] = 0

        # Net debt 계산
        cash = row.pop("cash", 0)
        row["net_borr"] = row.get("gross_borr", 0) - cash
        row["gross_borr"] = row.get("gross_borr", 0)

        # D/E ratio
        equity = row.get("equity", 0)
        liabilities = row.get("liabilities", 0)
        row["de_ratio"] = round(liabilities / equity * 100, 1) if equity > 0 else 0

        result[year] = row

    return result


def _guess_recent_years(facts: dict, n: int = 3) -> list[int]:
    """XBRL facts에서 최근 n개 fiscal year 추정."""
    us_gaap = facts.get("facts", {}).get("us-gaap", {})

    # 여러 revenue 태그를 순서대로 시도
    revenue_tags = [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ]

    fy_set = set()
    for tag in revenue_tags:
        concept_data = us_gaap.get(tag, {})
        entries = concept_data.get("units", {}).get("USD", [])
        for e in entries:
            if e.get("fp") == "FY" and e.get("form") in ("10-K", "10-K/A"):
                fy_set.add(e["fy"])
        if fy_set:
            break  # 하나라도 찾으면 중단

    return sorted(fy_set, reverse=True)[:n]


def get_shares_outstanding(cik: str, year: int | None = None) -> int | None:
    """발행주식수 조회 (XBRL dei 태그).

    Returns:
        주식수 (shares) or None
    """
    facts = get_company_facts(cik)
    dei = facts.get("facts", {}).get("dei", {})

    concept = dei.get("EntityCommonStockSharesOutstanding", {})
    entries = concept.get("units", {}).get("shares", [])

    # 최신 filing 기준
    if not entries:
        return None

    if year:
        for e in reversed(entries):
            if e.get("fy") == year:
                return int(e["val"])

    # 가장 최근 값
    return int(entries[-1]["val"])
