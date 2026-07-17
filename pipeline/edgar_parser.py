"""SEC EDGAR XBRL response -> structured financial data conversion.

Parses us-gaap tags from the Company Facts API
and converts them into a consolidated financial statement dict.
Amount unit: USD millions ($M)
"""

from datetime import date

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


def _duration_days(entry: dict) -> int | None:
    if not entry.get("start") or not entry.get("end"):
        return None
    return (date.fromisoformat(entry["end"]) - date.fromisoformat(entry["start"])).days + 1


def _dedupe_duration_entries(
    entries: list[dict], computed_as_of: date | None = None
) -> list[dict]:
    """Select the latest as-of filing for each SEC duration fact."""
    eligible = [
        e
        for e in entries
        if e.get("start")
        and e.get("end")
        and (
            computed_as_of is None
            or not e.get("filed")
            or date.fromisoformat(e["filed"]) <= computed_as_of
        )
    ]
    grouped: dict[tuple, list[dict]] = {}
    for entry in eligible:
        key = (
            entry.get("_concept"),
            entry.get("_unit"),
            entry["start"],
            entry["end"],
            entry.get("form"),
        )
        grouped.setdefault(key, []).append(entry)

    selected = []
    for group in grouped.values():
        ordered = sorted(
            group,
            key=lambda e: (
                e.get("filed", ""),
                e.get("form", "").endswith("/A"),
                e.get("accn", ""),
            ),
            reverse=True,
        )
        best = ordered[0]
        same_rank = [
            e
            for e in ordered
            if (e.get("filed"), e.get("form")) == (best.get("filed"), best.get("form"))
        ]
        if len({e.get("val") for e in same_rank}) > 1:
            raise ValueError(
                f"ambiguous SEC facts for {best.get('_concept')} "
                f"{best['start']}..{best['end']}"
            )
        selected.append(best)
    return selected


def extract_quarterly_facts(
    facts: dict,
    concepts: list[str],
    fiscal_year: int,
    fiscal_period: str,
    computed_as_of: date | None = None,
) -> dict:
    """Extract a discrete 10-Q duration fact, deriving it from YTD if needed."""
    if fiscal_period not in {"Q1", "Q2", "Q3"}:
        raise ValueError(f"unsupported fiscal period: {fiscal_period}")

    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    for concept in concepts:
        raw_entries = us_gaap.get(concept, {}).get("units", {}).get("USD", [])
        entries = []
        for raw in raw_entries:
            if (
                raw.get("fy") == fiscal_year
                and raw.get("fp") == fiscal_period
                and raw.get("form") in ("10-Q", "10-Q/A")
                and raw.get("start")
            ):
                entry = dict(raw)
                entry["_concept"] = concept
                entry["_unit"] = "USD"
                entries.append(entry)
        entries = _dedupe_duration_entries(entries, computed_as_of)
        if not entries:
            continue
        latest_end = max(e["end"] for e in entries)
        entries = [e for e in entries if e["end"] == latest_end]

        discrete = [e for e in entries if 77 <= (_duration_days(e) or 0) <= 105]
        if discrete:
            if len({(e["start"], e["end"], e["val"]) for e in discrete}) != 1:
                raise ValueError(f"ambiguous discrete facts for {concept} {fiscal_year} {fiscal_period}")
            return _quarter_fact_payload(discrete[0], "reported_discrete")

        if fiscal_period == "Q1":
            raise ValueError(f"Q1 duration is not a supported 13/14-week period: {concept}")

        current = max(entries, key=lambda e: _duration_days(e) or 0)
        previous_fp = f"Q{int(fiscal_period[1]) - 1}"
        previous = _find_ytd_entry(
            facts, concept, fiscal_year, previous_fp, current["start"], computed_as_of
        )
        if previous["end"] >= current["end"]:
            raise ValueError(f"non-contiguous YTD periods for {concept}")
        value = current["val"] - previous["val"]
        if value < 0:
            raise ValueError(f"negative YTD difference for {concept}")
        payload = _quarter_fact_payload(current, "derived_from_ytd")
        payload["value"] = _to_millions(value)
        payload["derived_from"] = {
            "current_ytd": _quarter_fact_payload(current, "reported_ytd"),
            "prior_ytd": _quarter_fact_payload(previous, "reported_ytd"),
        }
        return payload
    raise ValueError(f"no quarterly fact found for {fiscal_year} {fiscal_period}")


def _find_ytd_entry(
    facts: dict,
    concept: str,
    fiscal_year: int,
    fiscal_period: str,
    period_start: str,
    computed_as_of: date | None,
) -> dict:
    entries = []
    raw_entries = (
        facts.get("facts", {})
        .get("us-gaap", {})
        .get(concept, {})
        .get("units", {})
        .get("USD", [])
    )
    for raw in raw_entries:
        if (
            raw.get("fy") == fiscal_year
            and raw.get("fp") == fiscal_period
            and raw.get("form") in ("10-Q", "10-Q/A")
            and raw.get("start") == period_start
        ):
            entry = dict(raw)
            entry["_concept"] = concept
            entry["_unit"] = "USD"
            entries.append(entry)
    selected = _dedupe_duration_entries(entries, computed_as_of)
    if len(selected) != 1:
        raise ValueError(f"missing or ambiguous prior YTD for {concept} {fiscal_period}")
    return selected[0]


def _quarter_fact_payload(entry: dict, kind: str) -> dict:
    return {
        "value": _to_millions(entry["val"]),
        "concept": entry["_concept"],
        "unit": entry["_unit"],
        "fy": entry.get("fy"),
        "fp": entry.get("fp"),
        "form": entry.get("form"),
        "accn": entry.get("accn"),
        "filed": entry.get("filed"),
        "period_start": entry.get("start"),
        "period_end": entry.get("end"),
        "kind": kind,
        "raw_value": entry["val"],
    }


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


def _extract_duration_fact(
    facts: dict,
    concepts: list[str],
    fiscal_year: int,
    fiscal_period: str,
    computed_as_of: date | None,
) -> dict | None:
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    expected_forms = ("10-K", "10-K/A") if fiscal_period == "FY" else ("10-Q", "10-Q/A")
    for concept in concepts:
        entries = []
        for raw in us_gaap.get(concept, {}).get("units", {}).get("USD", []):
            if (
                raw.get("fy") == fiscal_year
                and raw.get("fp") == fiscal_period
                and raw.get("form") in expected_forms
                and raw.get("start")
            ):
                entry = dict(raw)
                entry["_concept"] = concept
                entry["_unit"] = "USD"
                entries.append(entry)
        selected = _dedupe_duration_entries(entries, computed_as_of)
        if selected:
            return max(
                selected,
                key=lambda e: (e.get("end", ""), _duration_days(e) or 0),
            )
    return None


def parse_ttm_financials(
    cik: str,
    annual_year: int,
    computed_as_of: date | None = None,
) -> tuple[dict, dict] | None:
    """Build a verified TTM anchor from SEC annual and comparable YTD facts."""
    facts = get_company_facts(cik)
    field_concepts = {
        "revenue": CONCEPT_MAP["revenue"],
        "op": CONCEPT_MAP["op"],
        "net_income": CONCEPT_MAP["net_income"],
        "dep": CONCEPT_MAP["dep"],
        "capex": CONCEPT_MAP["capex"],
    }
    current_year = annual_year + 1
    available_periods = []
    for fp in ("Q1", "Q2", "Q3"):
        if _extract_duration_fact(
            facts, field_concepts["revenue"], current_year, fp, computed_as_of
        ):
            available_periods.append(fp)
    if not available_periods:
        return None
    latest_period = available_periods[-1]

    values: dict[str, int] = {}
    provenance_fields: dict[str, dict] = {}
    for field, concepts in field_concepts.items():
        annual = prior = current = None
        for concept in concepts:
            annual_candidate = _extract_duration_fact(
                facts, [concept], annual_year, "FY", computed_as_of
            )
            prior_candidate = _extract_duration_fact(
                facts, [concept], annual_year, latest_period, computed_as_of
            )
            current_candidate = _extract_duration_fact(
                facts, [concept], current_year, latest_period, computed_as_of
            )
            if annual_candidate and prior_candidate and current_candidate:
                annual, prior, current = (
                    annual_candidate,
                    prior_candidate,
                    current_candidate,
                )
                break
        if not annual or not prior or not current:
            return None
        if annual["start"] != prior["start"] or current["start"] == prior["start"]:
            raise ValueError(f"{field}: incomparable SEC YTD boundaries")
        result = annual["val"] - prior["val"] + current["val"]
        if result < 0:
            raise ValueError(f"{field}: negative TTM result")
        values[field] = _to_millions(result)
        provenance_fields[field] = {
            "concept": annual["_concept"],
            "unit": "USD",
            "annual": _quarter_fact_payload(annual, "reported_annual"),
            "prior_ytd": _quarter_fact_payload(prior, "reported_ytd"),
            "current_ytd": _quarter_fact_payload(current, "reported_ytd"),
            "result": values[field],
        }

    values["amort"] = 0
    provenance = {
        "formula": "fy_minus_prior_ytd_plus_current_ytd",
        "computed_as_of": str(computed_as_of or date.today()),
        "source": "sec_companyfacts",
        "company_cik": str(cik).zfill(10),
        "fields": provenance_fields,
        "adjustments": [],
    }
    return values, provenance


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
