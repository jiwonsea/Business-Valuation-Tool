"""SEC EDGAR XBRL response -> structured financial data conversion.

Parses us-gaap tags from the Company Facts API
and converts them into a consolidated financial statement dict.
Amount unit: USD millions ($M)
"""

from schemas.provenance import NetDebtComponents

from .edgar_client import get_company_facts

# XBRL us-gaap tag -> internal key mapping
# Companies may use different tags, so fallback lists are provided
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
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "AcquisitionsNetOfCashAcquiredAndPurchasesOfBusinesses",
    ],
}


# ── §2.1 순차입금 taxonomy (P0-1) ──
#
# 두 경로는 서로 다른 XBRL 사실(fact)에서 나온다. 한쪽을 다른 쪽의 합으로 만들면
# reconciled가 항상 True가 되어 대조가 공허해진다 (CODEX 계약 §8).
#
#   Path A (구성요소)  : 개별(itemized) 태그 — 재무상태표 라인별 공시
#   Path B (독립 합계) : 결합(aggregate) 태그 — 회사가 스스로 합계로 보고한 단일 사실
#
# 두 경로가 어긋나면 태그 매핑이 무언가를 빠뜨렸거나 이중계상한 것이다 → 게이트가 차단한다.

# Path A — 현금성 구성요소 (차감 대상)
_TAG_CASH = ["CashAndCashEquivalentsAtCarryingValue"]
# 시장성 '채무'증권과 단기투자는 같은 풀이다. 아래 태그들은 대체(alternate)이지 가산 항목이 아니다.
_TAG_MARKETABLE_DEBT = [
    "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    "MarketableSecuritiesCurrent",
]
_TAG_SHORT_TERM_INVESTMENTS = ["ShortTermInvestments"]

# Path A — 차감하지 '않는' 항목 (기록만 한다)
_TAG_RESTRICTED_CASH = [
    "RestrictedCashAndCashEquivalentsAtCarryingValue",
    "RestrictedCashCurrent",
    "RestrictedCash",
]
_TAG_EQUITY_SECURITIES = [
    "EquitySecuritiesFvNiCurrent",
    "EquitySecuritiesFvNiCurrentAndNoncurrent",
]

# Path A — 차입금 구성요소 (개별 태그의 합)
_TAG_ITEMIZED_BORROWINGS = [
    "LongTermDebtCurrent",
    "LongTermDebtNoncurrent",
    "ShortTermBorrowings",
    "CommercialPaper",
    "OtherShortTermBorrowings",
]

# Path B — 결합 태그 (독립 합계). Path A 태그와 교집합이 없어야 한다.
_TAG_AGGREGATE_DEBT = [
    "DebtLongtermAndShorttermCombinedAmount",
    "DebtAndCapitalLeaseObligations",
    "LongTermDebtAndCapitalLeaseObligations",
    "LongTermDebt",
]
_TAG_AGGREGATE_CASH = ["CashCashEquivalentsAndShortTermInvestments"]
# 제한현금이 섞인 결합 태그. PLAN §2.1: "결합 태그가 있으면 제한현금 제외 후 사용".
_TAG_AGGREGATE_CASH_WITH_RESTRICTED = [
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
]

# Path A/B가 같은 태그를 공유하면 대조가 정의로 퇴화한다 (import 시점에 검증).
_PATH_A_TAGS = set(
    _TAG_CASH
    + _TAG_MARKETABLE_DEBT
    + _TAG_SHORT_TERM_INVESTMENTS
    + _TAG_ITEMIZED_BORROWINGS
)
_PATH_B_TAGS = set(
    _TAG_AGGREGATE_DEBT + _TAG_AGGREGATE_CASH + _TAG_AGGREGATE_CASH_WITH_RESTRICTED
)
assert not (_PATH_A_TAGS & _PATH_B_TAGS), (
    "독립 합계 태그가 구성요소 태그와 겹친다 — 대조가 무의미해진다"
)


def _to_millions(val: float | int) -> int:
    """USD raw → USD millions."""
    return round(val / 1_000_000)


def _extract_annual(facts: dict, concepts: list[str], year: int) -> int | None:
    """Extract the annual (10-K) value for a specific year from XBRL facts.

    10-K filings tag comparative year data with the same fy,
    so we select the entry with the latest end date to extract actual FY data.

    Args:
        facts: company facts raw JSON
        concepts: List of XBRL tags to try (in priority order)
        year: fiscal year

    Returns:
        USD millions integer or None
    """
    us_gaap = facts.get("facts", {}).get("us-gaap", {})

    for concept in concepts:
        concept_data = us_gaap.get(concept, {})
        units = concept_data.get("units", {})
        usd_entries = units.get("USD", [])

        # Collect 10-K entries for the target FY -> select latest end date
        candidates = [
            e
            for e in usd_entries
            if e.get("fp") == "FY"
            and e.get("fy") == year
            and e.get("form", "") in ("10-K", "10-K/A")
        ]
        if candidates:
            best = max(candidates, key=lambda e: e.get("end", ""))
            return _to_millions(best["val"])

        # If no 10-K, use any FY entry (latest end date)
        fallbacks = [
            e for e in usd_entries if e.get("fp") == "FY" and e.get("fy") == year
        ]
        if fallbacks:
            best = max(fallbacks, key=lambda e: e.get("end", ""))
            return _to_millions(best["val"])

    return None


def extract_net_debt_components(facts: dict, year: int) -> NetDebtComponents | None:
    """§2.1 구성요소와 독립 합계를 서로 다른 태그 계열에서 수집한다 (P0-1).

    독립 합계(`net_debt`)는 결합 태그(Path B)에서만 나온다. 구성요소를 더해 만들지 않는다 —
    그렇게 하면 `reconciled`가 항상 True가 되어 대조가 공허해진다 (CODEX 계약 §8).
    결합 태그가 없으면 `net_debt=None` → `reconciled=None` → 게이트가 legacy로 되돌린다.
    없는 합계를 지어내는 것보다 정상화를 포기하는 쪽이 옳다.

    Returns:
        NetDebtComponents, 또는 관련 태그가 하나도 없으면 None.
    """

    def pick(tags: list[str]) -> int | None:
        """우선순위대로 첫 히트. 대체 태그이지 가산 항목이 아니다."""
        return _extract_annual(facts, tags, year)

    # ── Path A: 개별 태그 → 구성요소 ──
    cash = pick(_TAG_CASH)
    marketable = pick(_TAG_MARKETABLE_DEBT)
    # 같은 풀을 두 번 차감하지 않는다: 시장성 채무증권 태그가 잡히면 ShortTermInvestments는 버린다.
    sti = None if marketable is not None else pick(_TAG_SHORT_TERM_INVESTMENTS)

    itemized = [v for tag in _TAG_ITEMIZED_BORROWINGS if (v := pick([tag])) is not None]
    gross_borrowings = sum(itemized) if itemized else None

    restricted = pick(_TAG_RESTRICTED_CASH)

    # ── Path B: 결합 태그 → 독립 합계 ──
    aggregate_debt = pick(_TAG_AGGREGATE_DEBT)
    aggregate_cash = pick(_TAG_AGGREGATE_CASH)
    if aggregate_cash is None:
        with_restricted = pick(_TAG_AGGREGATE_CASH_WITH_RESTRICTED)
        if with_restricted is not None and restricted is not None:
            aggregate_cash = with_restricted - restricted  # 제한현금 제외 후 사용

    independent_total = (
        aggregate_debt - aggregate_cash
        if aggregate_debt is not None and aggregate_cash is not None
        else None
    )

    components = NetDebtComponents(
        cash=cash,
        marketable_debt_securities=marketable,
        short_term_investments=sti,
        restricted_cash_excluded=restricted,
        equity_securities_excluded=pick(_TAG_EQUITY_SECURITIES),
        gross_borrowings=gross_borrowings,
        net_debt=independent_total,
    )

    material = (cash, marketable, sti, gross_borrowings, independent_total)
    if all(v is None for v in material):
        return None
    return components


def parse_financials(cik: str, years: list[int] | None = None) -> dict[int, dict]:
    """CIK -> annual consolidated financial statement dict.

    Args:
        cik: SEC CIK number
        years: List of years to query (None for most recent 3 years)

    Returns:
        {2024: {"revenue": int, "op": int, ..., "de_ratio": float}, ...}
        Amount unit: USD millions
    """
    facts = get_company_facts(cik)

    if years is None:
        # Estimate years from recent filings
        years = _guess_recent_years(facts)

    result = {}
    for year in years:
        row = {}
        for internal_key, concepts in CONCEPT_MAP.items():
            val = _extract_annual(facts, concepts, year)
            row[internal_key] = val if val is not None else 0

        # D&A fallback: estimate from DDA if dep+amort are missing
        if row.get("dep", 0) == 0 and row.get("amort", 0) == 0:
            dda = _extract_annual(facts, ["DepreciationDepletionAndAmortization"], year)
            if dda:
                row["dep"] = dda
                row["amort"] = 0

        # Net debt (legacy 정의: gross − cash). P0-1에서도 그대로 보존한다.
        cash = row.pop("cash", 0)
        row["net_borr"] = row.get("gross_borr", 0) - cash
        row["gross_borr"] = row.get("gross_borr", 0)

        # §2.1 정규화 원장 (P0-1). legacy 값을 덮어쓰지 않는다 — 별도 필드로 얹는다.
        row["net_debt_components"] = extract_net_debt_components(facts, year)

        # D/E ratio
        equity = row.get("equity", 0)
        liabilities = row.get("liabilities", 0)
        row["de_ratio"] = round(liabilities / equity * 100, 1) if equity > 0 else 0

        result[year] = row

    return result


def _guess_recent_years(facts: dict, n: int = 3) -> list[int]:
    """Estimate the most recent n fiscal years from XBRL facts."""
    us_gaap = facts.get("facts", {}).get("us-gaap", {})

    # Try multiple revenue tags in order
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

    return sorted(fy_set, reverse=True)[:n]


def get_shares_outstanding(cik: str, year: int | None = None) -> int | None:
    """Query shares outstanding (XBRL dei tag).

    Returns:
        Number of shares or None
    """
    facts = get_company_facts(cik)
    dei = facts.get("facts", {}).get("dei", {})

    concept = dei.get("EntityCommonStockSharesOutstanding", {})
    entries = concept.get("units", {}).get("shares", [])

    # Based on latest filing
    if not entries:
        return None

    if year:
        for e in reversed(entries):
            if e.get("fy") == year:
                return int(e["val"])

    # Most recent value
    return int(entries[-1]["val"])
