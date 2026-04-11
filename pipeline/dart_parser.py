"""DART API response -> structured financial data conversion.

KRW -> million KRW unit conversion, with account mapping.
"""

import re

# DART account names -> internal key mapping
ACCOUNT_MAP = {
    # IS (Income Statement) -- Revenue (top-line)
    "매출액": "revenue",  # Traditional format: Sales -> COGS -> Gross Profit
    "수익(매출액)": "revenue",  # Variant notation
    "영업수익": "revenue",  # IFRS by-function format: Operating Revenue - Operating Expense = Operating Income
    # IS -- Operating Income (Revenue - Costs)
    "영업이익": "op",
    "영업이익(손실)": "op",
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
        {"revenue": int, "op": int, ..., "dep": int, "amort": int} (million KRW)
    """
    result = {}

    for item in items:
        acct_name = item.get("account_nm", "")
        # Prefer current period amount, fallback to thstrm_amount
        amount_str = item.get("thstrm_amount", "")

        # Account mapping
        internal_key = ACCOUNT_MAP.get(acct_name)
        if internal_key and internal_key not in result:
            result[internal_key] = _to_millions(amount_str)

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
