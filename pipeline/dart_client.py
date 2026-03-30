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
    key = _get_api_key()
    resp = httpx.get(f"{DART_BASE}/corpCode.xml", params={"crtfc_key": key}, timeout=30)
    resp.raise_for_status()

    z = zipfile.ZipFile(io.BytesIO(resp.content))
    xml_data = z.read(z.namelist()[0])
    root = ET.fromstring(xml_data)

    for corp in root.findall(".//list"):
        name = corp.findtext("corp_name", "")
        if company_name in name or name in company_name:
            return corp.findtext("corp_code", "")
    return None


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
