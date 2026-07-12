"""DART API response -> structured financial data conversion.

KRW -> million KRW unit conversion, with account mapping.
"""

import logging
import re

from schemas.provenance import NetDebtComponents

logger = logging.getLogger(__name__)

# DART account names -> internal key mapping
ACCOUNT_MAP = {
    # IS (Income Statement) -- Revenue (top-line)
    "매출액": "revenue",  # Traditional format: Sales -> COGS -> Gross Profit
    "수익(매출액)": "revenue",  # Variant notation
    "영업수익": "revenue",  # IFRS by-function format: Operating Revenue - Operating Expense = Operating Income
    # IS -- Operating Income (Revenue - Costs)
    "영업이익": "op",
    "영업이익(손실)": "op",
    # IS -- Interest expense (for distress ICR calculation)
    "이자비용": "interest_expense",
    "금융비용": "interest_expense",
    "금융원가": "interest_expense",
    # IS -- Net Income
    "당기순이익": "net_income",
    "당기순이익(손실)": "net_income",
    # BS (Balance Sheet)
    "자산총계": "assets",
    "부채총계": "liabilities",
    "자본총계": "equity",
}

# Cash flow statement non-cash items
NONCASH_MAP = {
    "감가상각비": "dep",
    "유형자산감가상각비": "dep",
    "무형자산상각비": "amort",
}

# Cash flow statement capital expenditures (PP&E acquisition = investing outflow)
CAPEX_MAP = {
    "유형자산의 취득": "capex",
    "유형자산취득": "capex",
    "유형자산의취득": "capex",
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


def parse_financial_statements(items: list[dict], year: int) -> dict:
    """fnlttSinglAcntAll response -> consolidated financial statement dict.

    Args:
        items: DART API raw items
        year: Target fiscal year

    Returns:
        {"revenue": int, "op": int, ..., "dep": int, "amort": int,
         "capex": int, "gross_borr": int, "net_borr": int} (million KRW)
    """
    result = {}
    capex_raw = None  # None = not found; track separately to take abs()

    for item in items:
        acct_name = item.get("account_nm", "")
        amount_str = item.get("thstrm_amount", "")

        # IS / BS account mapping
        internal_key = ACCOUNT_MAP.get(acct_name)
        if internal_key and internal_key not in result:
            result[internal_key] = _to_millions(amount_str)

        # Capex: first matching CF item wins (CF outflows are reported as negative)
        if capex_raw is None and acct_name in CAPEX_MAP:
            capex_raw = _to_millions(amount_str)

    # Capex: DART reports investing outflows as negative; store absolute value
    if capex_raw is not None:
        result["capex"] = abs(capex_raw)
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

_BS_BORROWING_KEYS = ("단기차입금", "유동성장기부채", "장기차입금", "사채", "유동성사채")
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
