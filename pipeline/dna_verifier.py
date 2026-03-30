"""D&A 교차검증 모듈.

DART 재무제표와 사업보고서 주석의 비현금항목을 대조하여
감가상각비(dep), 무형자산상각비(amort) 정확성을 검증한다.
"""

from .dart_client import get_financial_statements, get_report_document
from .dart_parser import parse_noncash_from_xml


def verify_dna(
    corp_code: str,
    year: int,
    expected_dep: int | None = None,
    expected_amort: int | None = None,
    tolerance_pct: float = 5.0,
) -> dict:
    """D&A 데이터 교차검증.

    1. fnlttSinglAcntAll에서 당기 데이터 조회
    2. 사업보고서 XML에서 비현금항목 추출
    3. expected 값과 대조 (있는 경우)

    Args:
        corp_code: DART 기업코드
        year: 회계연도
        expected_dep: 예상 감가상각비 (백만원)
        expected_amort: 예상 무형자산상각비 (백만원)
        tolerance_pct: 허용 오차 (%)

    Returns:
        {"status": "OK"|"WARN"|"ERROR", "dep": int, "amort": int,
         "source": str, "discrepancies": list[str]}
    """
    result = {
        "status": "OK",
        "dep": 0,
        "amort": 0,
        "source": "",
        "discrepancies": [],
    }

    # 1. 재무제표 조회
    try:
        items = get_financial_statements(corp_code, year)
    except Exception as e:
        result["status"] = "ERROR"
        result["discrepancies"].append(f"재무제표 조회 실패: {e}")
        return result

    # rcept_no 추출 (첫 항목에서)
    rcept_no = items[0].get("rcept_no", "") if items else ""

    # 2. 사업보고서 주석에서 D&A 추출
    if rcept_no:
        try:
            xml_text = get_report_document(rcept_no)
            noncash = parse_noncash_from_xml(xml_text)
            if noncash:
                result["dep"] = noncash.get("dep", 0)
                result["amort"] = noncash.get("amort", 0)
                result["source"] = f"DART 사업보고서 주석 (rcept_no={rcept_no})"
        except Exception as e:
            result["discrepancies"].append(f"사업보고서 파싱 실패: {e}")

    # 3. 기대값 대조
    if expected_dep is not None and result["dep"] > 0:
        diff = abs(result["dep"] - expected_dep)
        pct = diff / expected_dep * 100 if expected_dep > 0 else 0
        if pct > tolerance_pct:
            result["status"] = "WARN"
            result["discrepancies"].append(
                f"dep 불일치: DART={result['dep']:,} vs 예상={expected_dep:,} (차이 {pct:.1f}%)"
            )

    if expected_amort is not None and result["amort"] > 0:
        diff = abs(result["amort"] - expected_amort)
        pct = diff / expected_amort * 100 if expected_amort > 0 else 0
        if pct > tolerance_pct:
            result["status"] = "WARN"
            result["discrepancies"].append(
                f"amort 불일치: DART={result['amort']:,} vs 예상={expected_amort:,} (차이 {pct:.1f}%)"
            )

    return result
