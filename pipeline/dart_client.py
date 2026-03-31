"""DART OpenAPI 클라이언트 — 재무제표, 사업보고서, 기업코드 조회.

DART API Key 필요: https://opendart.fss.or.kr/
환경변수: DART_API_KEY
"""

import io
import os
import zipfile
from xml.etree import ElementTree as ET

import httpx

DART_BASE = "https://opendart.fss.or.kr/api"


def _get_api_key() -> str:
    key = os.getenv("DART_API_KEY")
    if not key:
        raise RuntimeError("DART_API_KEY 환경변수가 설정되지 않았습니다.")
    return key


def get_corp_code(company_name: str) -> str | None:
    """회사명으로 DART corp_code 조회.

    corpCode.xml → 전체 기업코드 ZIP → XML 파싱 → 회사명 매칭
    """
    result = get_corp_info(company_name)
    return result["corp_code"] if result else None


def get_corp_info(company_name: str) -> dict | None:
    """회사명으로 DART corp_code + 상장 여부 조회.

    Returns:
        {"corp_code": str, "stock_code": str|None, "is_listed": bool} or None
    """
    key = _get_api_key()
    resp = httpx.get(f"{DART_BASE}/corpCode.xml", params={"crtfc_key": key}, timeout=30)
    resp.raise_for_status()

    z = zipfile.ZipFile(io.BytesIO(resp.content))
    xml_data = z.read(z.namelist()[0])
    root = ET.fromstring(xml_data)

    # 모든 매칭 후보를 수집한 뒤, 상장사 우선 + 정확매칭 우선으로 정렬
    candidates = []
    for corp in root.findall(".//list"):
        name = corp.findtext("corp_name", "")
        if company_name in name or name in company_name:
            stock_code = (corp.findtext("stock_code") or "").strip()
            is_exact = (name == company_name)
            is_listed = bool(stock_code)
            candidates.append({
                "corp_code": corp.findtext("corp_code", ""),
                "stock_code": stock_code if stock_code else None,
                "is_listed": is_listed,
                "_exact": is_exact,
            })

    if not candidates:
        return None

    # 정렬: 정확매칭 > 상장사 > 나머지
    candidates.sort(key=lambda c: (c["_exact"], c["is_listed"]), reverse=True)
    best = candidates[0]
    best.pop("_exact")
    return best


def get_financial_statements(
    corp_code: str,
    year: int,
    report_code: str = "11011",  # 11011=사업보고서
    fs_div: str = "CFS",  # CFS=연결, OFS=개별
) -> list[dict]:
    """전체 재무제표 단일계정 조회 (fnlttSinglAcntAll).

    Returns: list of account dicts
    """
    key = _get_api_key()
    params = {
        "crtfc_key": key,
        "corp_code": corp_code,
        "bsns_year": str(year),
        "reprt_code": report_code,
        "fs_div": fs_div,
    }
    resp = httpx.get(f"{DART_BASE}/fnlttSinglAcntAll.json", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "000":
        raise RuntimeError(f"DART API 오류: {data.get('message', 'unknown')}")

    return data.get("list", [])


def get_report_document(rcept_no: str) -> str:
    """사업보고서 본문 XML 다운로드.

    Args:
        rcept_no: 접수번호 (financial_statements 결과에서 획득)

    Returns:
        XML 본문 텍스트
    """
    key = _get_api_key()
    resp = httpx.get(f"{DART_BASE}/document.xml",
                     params={"crtfc_key": key, "rcept_no": rcept_no}, timeout=60)
    resp.raise_for_status()

    z = zipfile.ZipFile(io.BytesIO(resp.content))
    # 보통 첫 번째 파일이 본문
    xml_data = z.read(z.namelist()[0])
    return xml_data.decode("utf-8", errors="replace")


def get_single_company_info(corp_code: str) -> dict:
    """기업 개황 조회 (company.json).

    Returns: 대표자명, 업종, 주소, 주식수 등
    """
    key = _get_api_key()
    resp = httpx.get(f"{DART_BASE}/company.json",
                     params={"crtfc_key": key, "corp_code": corp_code}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "000":
        raise RuntimeError(f"DART API 오류: {data.get('message')}")
    return data


def _parse_dart_number(s: str) -> int:
    """DART 숫자 문자열 파싱 ('5,969,782,550' → 5969782550, '-' → 0)."""
    if not s or s.strip() in ("-", ""):
        return 0
    return int(s.replace(",", "").strip())


def get_stock_total_info(
    corp_code: str,
    year: int,
    reprt_code: str = "11011",
) -> dict | None:
    """주식의 총수 현황 조회 (stockTotqySttus.json).

    Args:
        corp_code: DART 고유번호
        year: 사업연도 (e.g., 2024)
        reprt_code: 11011=사업보고서, 11012=반기, 11013=1분기, 11014=3분기

    Returns:
        {
            "shares_ordinary": int,   # 보통주 발행주식총수
            "shares_preferred": int,  # 우선주 발행주식총수
            "treasury_ordinary": int, # 자기주식수 (보통주)
            "treasury_preferred": int,# 자기주식수 (우선주)
        }
        or None if API call fails
    """
    key = _get_api_key()
    params = {
        "crtfc_key": key,
        "corp_code": corp_code,
        "bsns_year": str(year),
        "reprt_code": reprt_code,
    }
    resp = httpx.get(
        f"{DART_BASE}/stockTotqySttus.json", params=params, timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "000":
        return None

    result = {
        "shares_ordinary": 0,
        "shares_preferred": 0,
        "treasury_ordinary": 0,
        "treasury_preferred": 0,
    }
    for item in data.get("list", []):
        se = (item.get("se") or "").strip()
        # istc_totqy: 현재 발행주식총수, tesstk_co: 자기주식수
        issued = _parse_dart_number(item.get("istc_totqy", "0"))
        treasury = _parse_dart_number(item.get("tesstk_co", "0"))

        if "보통주" in se:
            result["shares_ordinary"] = issued
            result["treasury_ordinary"] = treasury
        elif "우선주" in se:
            result["shares_preferred"] = issued
            result["treasury_preferred"] = treasury

    return result
