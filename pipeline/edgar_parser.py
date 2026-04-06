"""SEC EDGAR XBRL response -> structured financial data conversion.

Parses us-gaap tags from the Company Facts API
and converts them into a consolidated financial statement dict.
Amount unit: USD millions ($M)
"""

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
            e for e in usd_entries
            if e.get("fp") == "FY" and e.get("fy") == year
            and e.get("form", "") in ("10-K", "10-K/A")
        ]
        if candidates:
            best = max(candidates, key=lambda e: e.get("end", ""))
            return _to_millions(best["val"])

        # If no 10-K, use any FY entry (latest end date)
        fallbacks = [
            e for e in usd_entries
            if e.get("fp") == "FY" and e.get("fy") == year
        ]
        if fallbacks:
            best = max(fallbacks, key=lambda e: e.get("end", ""))
            return _to_millions(best["val"])

    return None


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

        # Net debt calculation
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
