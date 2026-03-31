"""DART API 응답 → 구조화된 재무 데이터 변환.

원 → 백만원 단위 변환, 계정 매핑 포함.
"""

import re

# DART 계정과목 → 내부 키 매핑
ACCOUNT_MAP = {
    # IS (손익계산서) — 매출/수익 (top-line Revenue)
    "매출액": "revenue",           # 전통 형식: 매출액 → 매출원가 → 매출총이익
    "수익(매출액)": "revenue",     # 변형 표기
    "영업수익": "revenue",         # IFRS 기능별 형식: 영업수익 − 영업비용 = 영업이익
    # IS — 영업이익 (Operating Income, Revenue − Costs)
    "영업이익": "op",
    "영업이익(손실)": "op",
    # IS — 당기순이익
    "당기순이익": "net_income",
    "당기순이익(손실)": "net_income",
    # BS (재무상태표)
    "자산총계": "assets",
    "부채총계": "liabilities",
    "자본총계": "equity",
}

# 현금흐름표 비현금항목
NONCASH_MAP = {
    "감가상각비": "dep",
    "유형자산감가상각비": "dep",
    "무형자산상각비": "amort",
}


def _to_millions(value_str: str) -> int:
    """원 단위 문자열 → 백만원 정수 변환."""
    if not value_str:
        return 0
    cleaned = re.sub(r"[,\s]", "", value_str)
    # 괄호 = 음수
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
    """fnlttSinglAcntAll 응답 → 연결 재무제표 dict.

    Args:
        items: DART API raw items
        year: 대상 회계연도

    Returns:
        {"revenue": int, "op": int, ..., "dep": int, "amort": int} (백만원)
    """
    result = {}

    for item in items:
        acct_name = item.get("account_nm", "")
        # 당기 금액 우선, 없으면 thstrm_amount
        amount_str = item.get("thstrm_amount", "")

        # 계정 매핑
        internal_key = ACCOUNT_MAP.get(acct_name)
        if internal_key and internal_key not in result:
            result[internal_key] = _to_millions(amount_str)

    return result


def parse_noncash_from_xml(xml_text: str) -> dict[str, int]:
    """사업보고서 XML에서 비현금항목(감가상각비, 무형자산상각비) 추출.

    Returns:
        {"dep": int, "amort": int} (천원 → 백만원 변환)
    """
    result = {}

    # "비현금항목" 또는 "비현금" 섹션 탐색
    pattern = r"비현금[항목\s]*조정.*?(?=현금의|투자활동|영업활동에서)"
    match = re.search(pattern, xml_text, re.DOTALL)
    if not match:
        return result

    section = match.group(0)
    # XML 태그 제거
    clean = re.sub(r"<[^>]+>", " ", section)
    clean = re.sub(r"\s+", " ", clean)

    for korean_name, key in NONCASH_MAP.items():
        # "감가상각비 123,456,789 111,222,333" 패턴
        pat = rf"{korean_name}\s+([\d,\(\)\-]+)"
        m = re.search(pat, clean)
        if m:
            val_str = m.group(1).replace(",", "")
            if val_str.startswith("(") and val_str.endswith(")"):
                val_str = val_str[1:-1]
            try:
                result[key] = round(int(val_str) / 1_000_000)  # 천원 → 백만원
            except ValueError:
                pass

    return result


def estimate_borrowings(items: list[dict]) -> dict[str, int]:
    """BS에서 차입금 관련 항목 추출 → 총차입금/순차입금 추정.

    Returns:
        {"gross_borr": int, "net_borr": int} (백만원)
    """
    borrowing_keys = [
        "단기차입금", "유동성장기부채", "장기차입금",
        "사채", "유동성사채",
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
