"""DART API response -> structured financial data conversion.

KRW -> million KRW unit conversion, with account mapping.

Data contract (Phase 2 gate, HANDOFF_CODEX_c_gate_research_2026-07-18 §7.2 — no relaxation):

1. Per-account allowed statements are FIXED (`STATEMENT_CONTRACT`):
   revenue / op / interest_expense / net_income -> IS·CIS,
   assets / liabilities / equity -> BS, capex -> CF.
   Rows from any other statement (notably SCE, which carries its own `당기순이익`
   rows including a non-controlling-interest-only line) are never mapping
   candidates. Before this contract, row order (CIS preceding SCE) protected the
   result only by accident.
2. Duplicate-candidate selection within the allowed statements is explicit:
   (a) statements are tried in the order they appear in `STATEMENT_CONTRACT`
       (IS before CIS: a dedicated income statement outranks the comprehensive
       statement that republishes the same line);
   (b) within the first statement that has candidates, if all candidate values
       are identical the first row in payload order wins (payload order is the
       filing's own presentation order);
   (c) if candidate values DIFFER within that statement, the account is
       ambiguous -> `AmbiguousAccountError` (fail-closed; silent selection is
       forbidden — same design as `dart_client._parse_dart_number`).
3. Account-name aliases live in `ACCOUNT_ALIASES` / `CAPEX_ALIASES` (the formal
   registry; `ACCOUNT_MAP` / `CAPEX_MAP` are derived views kept for backward
   compatibility). Alias drift across years (e.g. `영업이익` <-> `영업이익(손실)`)
   is a registry concern, not a parser special case.
4. Original filing values and later restated comparatives are preserved
   SEPARATELY (`extract_reported_values`): the original (`thstrm_amount`,
   basis="original") is what point-in-time computation may consume; the
   following-year comparative (`frmtrm_amount`, basis="restated_comparative")
   is retained for audit and never overwrites the original.
"""

import logging
import re

from schemas.point_in_time import ReportedFinancialValue, available_at_from_rcept_no
from schemas.provenance import NetDebtComponents

logger = logging.getLogger(__name__)


class AmbiguousAccountError(ValueError):
    """Same-statement mapping candidates disagree — refuse to pick silently.

    Fail-closed by design (contract §7.2-2, following the
    `dart_client._parse_dart_number` precedent): a silently chosen wrong line
    would flow an unflagged wrong number into every downstream valuation.
    Callers treat the year as missing (data_fetcher already catches per-year
    exceptions and logs a warning).
    """


# ── Formal alias registry (contract §7.2-3) ──
# Internal key -> every DART account_nm spelling observed for that concept.
# Add new aliases HERE (with a comment citing the filing that introduced the
# spelling), never inline in parsing code.

ACCOUNT_ALIASES: dict[str, tuple[str, ...]] = {
    "revenue": (
        "매출액",  # Traditional format: Sales -> COGS -> Gross Profit
        "수익(매출액)",  # Variant notation
        "영업수익",  # IFRS by-function format
    ),
    "op": (
        "영업이익",
        "영업이익(손실)",  # Alias drift observed LG FY2020->FY2021 (pilot v2)
    ),
    "interest_expense": (
        "이자비용",
        "금융비용",
        "금융원가",
    ),
    "net_income": (
        "당기순이익",
        "당기순이익(손실)",
    ),
    "assets": ("자산총계",),
    "liabilities": ("부채총계",),
    "equity": ("자본총계",),
}

CAPEX_ALIASES: tuple[str, ...] = (
    "유형자산의 취득",  # PP&E acquisition = investing outflow
    "유형자산취득",
    "유형자산의취득",
)

# Derived views — same name/content as the historical dicts so existing
# consumers (pilot scripts, tests) keep working unchanged.
ACCOUNT_MAP: dict[str, str] = {
    alias: key for key, aliases in ACCOUNT_ALIASES.items() for alias in aliases
}
CAPEX_MAP: dict[str, str] = {alias: "capex" for alias in CAPEX_ALIASES}

# ── Per-account allowed statements (contract §7.2-1) ──
# Tuple order IS the selection priority (§7.2-2a).
STATEMENT_CONTRACT: dict[str, tuple[str, ...]] = {
    "revenue": ("IS", "CIS"),
    "op": ("IS", "CIS"),
    "interest_expense": ("IS", "CIS"),
    "net_income": ("IS", "CIS"),
    "assets": ("BS",),
    "liabilities": ("BS",),
    "equity": ("BS",),
    "capex": ("CF",),
}

# fnlttSinglAcntAll rows carry sj_div; fall back to sj_nm for payloads that
# only carry the Korean statement name (same convention as estimate_borrowings).
_SJ_NM_TO_DIV = {
    "재무상태표": "BS",
    "손익계산서": "IS",
    "포괄손익계산서": "CIS",
    "현금흐름표": "CF",
    "자본변동표": "SCE",
}


def _statement_of(item: dict) -> str:
    """Normalized statement code of a row ('' when undeclared -> never a candidate)."""
    sj = item.get("sj_div") or ""
    if sj:
        return sj
    return _SJ_NM_TO_DIV.get(item.get("sj_nm", ""), "")


# Cash flow statement non-cash items
NONCASH_MAP = {
    "감가상각비": "dep",
    "유형자산감가상각비": "dep",
    "무형자산상각비": "amort",
}


def _to_millions(value_str: str) -> int:
    """Convert KRW string to million KRW integer."""
    if not value_str:
        return 0
    cleaned = re.sub(r"[,\s]", "", value_str)
    # Parentheses = negative
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        won = int(cleaned)
    except ValueError:
        try:
            won = int(float(cleaned))
        except ValueError:
            return 0
    return round(won / 1_000_000)


def _map_internal_key(acct_name: str) -> str | None:
    """account_nm -> internal key via the alias registry (None = unmapped)."""
    key = ACCOUNT_MAP.get(acct_name)
    if key is None and acct_name in CAPEX_MAP:
        key = "capex"
    return key


def _select_by_contract(
    items: list[dict], amount_field: str, year: int
) -> dict[str, int]:
    """Contract-governed account selection (§7.2-1/2).

    Only rows whose statement is in `STATEMENT_CONTRACT[key]` are candidates.
    Statements are tried in contract order; within the first statement that has
    candidates, identical values -> first row wins (payload order), differing
    values -> AmbiguousAccountError (fail-closed, no silent pick).
    """
    candidates: dict[str, dict[str, list[int]]] = {}  # key -> statement -> values
    for item in items:
        key = _map_internal_key(item.get("account_nm", ""))
        if key is None:
            continue
        statement = _statement_of(item)
        if statement not in STATEMENT_CONTRACT[key]:
            continue  # §7.2-1: e.g. SCE `당기순이익` rows are never candidates
        candidates.setdefault(key, {}).setdefault(statement, []).append(
            _to_millions(item.get(amount_field, ""))
        )

    selected: dict[str, int] = {}
    for key, per_statement in candidates.items():
        for statement in STATEMENT_CONTRACT[key]:  # §7.2-2a: priority = contract order
            values = per_statement.get(statement)
            if not values:
                continue
            if len(set(values)) > 1:  # §7.2-2c: fail-closed
                raise AmbiguousAccountError(
                    f"DART {amount_field} FY{year}: '{key}' has "
                    f"{len(values)} conflicting candidates in statement "
                    f"{statement}: {values} — refusing to pick silently "
                    "(contract §7.2-2)."
                )
            selected[key] = values[0]  # §7.2-2b: identical -> first in payload order
            break
    return selected


def parse_financial_statements(items: list[dict], year: int) -> dict:
    """fnlttSinglAcntAll response -> consolidated financial statement dict.

    Selection follows the module data contract (STATEMENT_CONTRACT + alias
    registry + fail-closed ambiguity). Raises AmbiguousAccountError when
    same-statement candidates disagree.

    Args:
        items: DART API raw items
        year: Target fiscal year

    Returns:
        {"revenue": int, "op": int, ..., "dep": int, "amort": int,
         "capex": int, "gross_borr": int, "net_borr": int} (million KRW)
    """
    result = _select_by_contract(items, "thstrm_amount", year)

    # Capex: DART reports investing outflows as negative; store absolute value
    if "capex" in result:
        result["capex"] = abs(result["capex"])
    else:
        logger.debug(
            "parse_financial_statements: capex 항목 미발견 (year=%d) — profile_generator가 capex_to_da fallback 사용",
            year,
        )

    # Interest-bearing debt + net debt (from balance sheet items)
    borrowings = estimate_borrowings(items)
    result.update(borrowings)

    # §2.1 정규화 원장 (P0-1). legacy net_borr를 덮어쓰지 않는다 — 별도 필드로 얹는다.
    result["net_debt_components"] = extract_net_debt_components(items)

    return result


def extract_reported_values(
    items: list[dict], year: int
) -> list[ReportedFinancialValue]:
    """Preserve original filing values and restated comparatives SEPARATELY (§7.2-4).

    From one FY`year` annual-report payload this yields, per contract account:
      - basis="original"              : thstrm_amount, fiscal_year=year — the
        value that was available at this filing's receipt date. This is the ONLY
        basis point-in-time computation may consume (§7.2-5).
      - basis="restated_comparative"  : frmtrm_amount, fiscal_year=year-1 — the
        comparative the later filing republished for the prior year. Audit
        record; it never overwrites the prior year's original.

    Selection rules are identical to parse_financial_statements (statement
    contract + priority + fail-closed ambiguity). Unlike the legacy dict path,
    blank/'-' amounts are treated as missing (not coerced to 0) — a new API has
    no legacy-parity obligation, and a fabricated 0 is worse than a gap.

    Raises AmbiguousAccountError on same-statement conflicting candidates and
    ValueError when the payload carries no rcept_no (no available_at -> the
    value cannot participate in point-in-time selection).
    """
    rcept_no = ""
    for item in items:
        if item.get("rcept_no"):
            rcept_no = item["rcept_no"]
            break
    if not rcept_no:
        raise ValueError(
            f"extract_reported_values FY{year}: payload has no rcept_no — "
            "without a receipt date the values have no available_at (§7.2-5)."
        )
    available_at = available_at_from_rcept_no(rcept_no)

    out: list[ReportedFinancialValue] = []
    for amount_field, basis, fiscal_year in (
        ("thstrm_amount", "original", year),
        ("frmtrm_amount", "restated_comparative", year - 1),
    ):
        # Strict candidate collection: keep row provenance, skip blank amounts.
        candidates: dict[str, dict[str, list[tuple[int, str]]]] = {}
        for item in items:
            key = _map_internal_key(item.get("account_nm", ""))
            if key is None:
                continue
            statement = _statement_of(item)
            if statement not in STATEMENT_CONTRACT[key]:
                continue
            raw = (item.get(amount_field) or "").strip()
            if raw in ("", "-"):
                continue  # missing stays missing — no interpolation (§7.2-5)
            candidates.setdefault(key, {}).setdefault(statement, []).append(
                (_to_millions(raw), item.get("account_nm", ""))
            )

        for key, per_statement in candidates.items():
            for statement in STATEMENT_CONTRACT[key]:
                rows = per_statement.get(statement)
                if not rows:
                    continue
                values = [v for v, _ in rows]
                if len(set(values)) > 1:
                    raise AmbiguousAccountError(
                        f"DART {amount_field} FY{fiscal_year}: '{key}' has "
                        f"conflicting candidates in statement {statement}: "
                        f"{values} — refusing to pick silently (contract §7.2-2)."
                    )
                value, account_nm = rows[0]
                out.append(
                    ReportedFinancialValue(
                        account=key,
                        fiscal_year=fiscal_year,
                        value_mkrw=abs(value) if key == "capex" else value,
                        basis=basis,
                        statement=statement,
                        account_nm=account_nm,
                        rcept_no=rcept_no,
                        available_at=available_at,
                    )
                )
                break

    return out


def parse_noncash_from_xml(xml_text: str) -> dict[str, int]:
    """Extract non-cash items (depreciation, amortization) from annual report XML.

    Returns:
        {"dep": int, "amort": int} (converted from thousand KRW to million KRW)
    """
    result = {}

    # Search for "non-cash items" or "non-cash" section
    pattern = r"비현금[항목\s]*조정.*?(?=현금의|투자활동|영업활동에서)"
    match = re.search(pattern, xml_text, re.DOTALL)
    if not match:
        return result

    section = match.group(0)
    # Strip XML tags
    clean = re.sub(r"<[^>]+>", " ", section)
    clean = re.sub(r"\s+", " ", clean)

    for korean_name, key in NONCASH_MAP.items():
        # Pattern: "감가상각비 123,456,789 111,222,333"
        pat = rf"{korean_name}\s+([\d,\(\)\-]+)"
        m = re.search(pat, clean)
        if m:
            val_str = m.group(1).replace(",", "")
            if val_str.startswith("(") and val_str.endswith(")"):
                val_str = val_str[1:-1]
            try:
                result[key] = round(
                    int(val_str) / 1_000_000
                )  # thousand KRW -> million KRW
            except ValueError:
                pass

    return result


def estimate_borrowings(items: list[dict]) -> dict[str, int]:
    """Extract borrowing-related items from balance sheet -> estimate gross/net borrowings.

    Returns:
        {"gross_borr": int, "net_borr": int} (million KRW)
    """
    borrowing_keys = [
        "단기차입금",
        "유동성장기부채",
        "장기차입금",
        "사채",
        "유동성사채",
    ]
    cash_keys = ["현금및현금성자산", "단기금융상품"]

    gross_borr = 0
    cash = 0

    for item in items:
        # Balance-sheet items only. Substring matching below would otherwise
        # catch cash-flow line items like "단기금융상품의 감소/증가" and
        # "사채의 발행/상환", massively overstating cash and borrowings.
        sj = item.get("sj_div") or item.get("sj_nm", "")
        if sj not in ("BS", "재무상태표"):
            continue

        name = item.get("account_nm", "")
        amt = _to_millions(item.get("thstrm_amount", ""))

        for bk in borrowing_keys:
            if bk in name:
                gross_borr += amt
                break

        for ck in cash_keys:
            if ck in name:
                cash += amt
                break

    return {"gross_borr": gross_borr, "net_borr": gross_borr - cash}


# ── §2.1 순차입금 taxonomy (P0-1) ──

_BS_BORROWING_KEYS = (
    "단기차입금",
    "유동성장기부채",
    "장기차입금",
    "사채",
    "유동성사채",
)
_BS_CASH_KEYS = ("현금및현금성자산",)
_BS_SHORT_TERM_INVESTMENT_KEYS = ("단기금융상품",)
# 차감하지 '않는' 항목 (기록만 한다)
_BS_RESTRICTED_KEYS = ("사용제한", "사용이 제한", "제한예금")


def extract_net_debt_components(items: list[dict]) -> NetDebtComponents | None:
    """§2.1 구성요소를 재무상태표 개별 계정에서 수집한다 (P0-1).

    독립 합계는 수집하지 않는다 (`net_debt=None`). DART 표준계정에는 순차입금을 단일
    사실로 보고하는 계정이 없다. 구성요소를 더해 합계 자리에 넣으면 `reconciled`가 항상
    True가 되어 대조가 공허해진다 (CODEX 계약 §8: "독립 합계를 구할 수 없으면 임의
    생성하지 말고 None 유지").

    따라서 KR은 `reconciled=None` → `blocked_unreconcilable` → 엔진은 legacy 정의를
    계속 쓴다. 이것이 의도된 동작이다. 구성요소는 감사와 후속 대조(P2-5)를 위해 기록된다.
    """
    gross_borr = 0
    cash = 0
    sti = 0
    restricted = 0
    seen_borr = seen_cash = seen_sti = seen_restricted = False

    for item in items:
        # BS 항목만. 부분문자열 매칭이라 CF 항목("사채의 발행", "단기금융상품의 감소")이
        # 섞이면 현금·차입이 폭증한다 (NAVER 순현금 5배 과대계상 사례).
        sj = item.get("sj_div") or item.get("sj_nm", "")
        if sj not in ("BS", "재무상태표"):
            continue

        name = item.get("account_nm", "")
        amt = _to_millions(item.get("thstrm_amount", ""))

        # 제한현금이 먼저다: 어떤 차감 버킷에도 들어가지 않는다.
        if any(k in name for k in _BS_RESTRICTED_KEYS):
            restricted += amt
            seen_restricted = True
            continue

        if any(k in name for k in _BS_BORROWING_KEYS):
            gross_borr += amt
            seen_borr = True
            continue

        if any(k in name for k in _BS_CASH_KEYS):
            cash += amt
            seen_cash = True
            continue

        if any(k in name for k in _BS_SHORT_TERM_INVESTMENT_KEYS):
            sti += amt
            seen_sti = True

    if not (seen_borr or seen_cash or seen_sti):
        return None

    return NetDebtComponents(
        cash=cash if seen_cash else None,
        marketable_debt_securities=None,  # KR 표준계정에 대응 태그 없음
        short_term_investments=sti if seen_sti else None,
        restricted_cash_excluded=restricted if seen_restricted else None,
        equity_securities_excluded=None,
        gross_borrowings=gross_borr if seen_borr else None,
        net_debt=None,  # 독립 합계 원천 없음 — 날조하지 않는다
    )
