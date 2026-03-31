"""DART OpenAPI client -- financial statements, annual reports, and corporate code lookup.

Requires DART API Key: https://opendart.fss.or.kr/
Environment variable: DART_API_KEY
"""

import io
import logging
import os
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

DART_BASE = "https://opendart.fss.or.kr/api"

# corpCode.xml disk cache (8MB ZIP -> avoid re-downloading each time)
_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
_CORP_CODE_CACHE = _CACHE_DIR / "corpCode.xml"
_CORP_CODE_TTL = 86400  # 24 hours


def _get_api_key() -> str:
    key = os.getenv("DART_API_KEY")
    if not key:
        raise RuntimeError("DART_API_KEY 환경변수가 설정되지 않았습니다.")
    return key


def _load_corp_code_xml() -> ET.Element:
    """Load corpCode.xml (disk cache first, re-download on expiry)."""
    from .api_guard import ApiGuard

    guard = ApiGuard.get()

    # Check cache validity
    if _CORP_CODE_CACHE.exists():
        age = time.time() - _CORP_CODE_CACHE.stat().st_mtime
        if age < _CORP_CODE_TTL:
            logger.debug("corpCode.xml 캐시 사용 (age=%.0fs)", age)
            guard.record_cache_hit("dart")
            return ET.parse(_CORP_CODE_CACHE).getroot()

    # No cache or expired -> download
    guard.check("dart")
    logger.info("corpCode.xml 다운로드 중 (~8MB)...")
    key = _get_api_key()
    resp = httpx.get(f"{DART_BASE}/corpCode.xml", params={"crtfc_key": key}, timeout=30)
    resp.raise_for_status()
    guard.record_success("dart")

    z = zipfile.ZipFile(io.BytesIO(resp.content))
    xml_data = z.read(z.namelist()[0])

    # Save to disk
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _CORP_CODE_CACHE.write_bytes(xml_data)
    logger.info("corpCode.xml 캐시 저장 완료 (%s)", _CORP_CODE_CACHE)

    return ET.fromstring(xml_data)


def get_corp_code(company_name: str) -> str | None:
    """Look up DART corp_code by company name.

    corpCode.xml -> full corporate code ZIP -> XML parsing -> company name matching
    """
    result = get_corp_info(company_name)
    return result["corp_code"] if result else None


def get_corp_info(company_name: str) -> dict | None:
    """Look up DART corp_code + listing status by company name.

    Returns:
        {"corp_code": str, "stock_code": str|None, "is_listed": bool} or None
    """
    root = _load_corp_code_xml()

    # Collect all matching candidates, then sort by listed first + exact match first
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

    # Sort: exact match > listed > others
    candidates.sort(key=lambda c: (c["_exact"], c["is_listed"]), reverse=True)
    best = candidates[0]
    best.pop("_exact")
    return best


from .api_guard import api_guard


@api_guard("dart")
def get_financial_statements(
    corp_code: str,
    year: int,
    report_code: str = "11011",  # 11011=Annual Report
    fs_div: str = "CFS",  # CFS=Consolidated, OFS=Separate
) -> list[dict]:
    """Full financial statement single-account query (fnlttSinglAcntAll).

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


@api_guard("dart")
def get_report_document(rcept_no: str) -> str:
    """Download annual report body XML.

    Args:
        rcept_no: Receipt number (obtained from financial_statements result)

    Returns:
        XML body text
    """
    key = _get_api_key()
    resp = httpx.get(f"{DART_BASE}/document.xml",
                     params={"crtfc_key": key, "rcept_no": rcept_no}, timeout=60)
    resp.raise_for_status()

    z = zipfile.ZipFile(io.BytesIO(resp.content))
    # Usually the first file is the body
    xml_data = z.read(z.namelist()[0])
    return xml_data.decode("utf-8", errors="replace")


@api_guard("dart")
def get_single_company_info(corp_code: str) -> dict:
    """Company overview query (company.json).

    Returns: CEO name, industry, address, shares, etc.
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
    """Parse DART number string ('5,969,782,550' -> 5969782550, '-' -> 0)."""
    if not s or s.strip() in ("-", ""):
        return 0
    return int(s.replace(",", "").strip())


@api_guard("dart")
def get_stock_total_info(
    corp_code: str,
    year: int,
    reprt_code: str = "11011",
) -> dict | None:
    """Query total shares status (stockTotqySttus.json).

    Args:
        corp_code: DART corporate code
        year: Fiscal year (e.g., 2024)
        reprt_code: 11011=Annual, 11012=Semi-annual, 11013=Q1, 11014=Q3

    Returns:
        {
            "shares_ordinary": int,   # Total ordinary shares issued
            "shares_preferred": int,  # Total preferred shares issued
            "treasury_ordinary": int, # Treasury shares (ordinary)
            "treasury_preferred": int,# Treasury shares (preferred)
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
        # istc_totqy: total shares currently issued, tesstk_co: treasury shares
        issued = _parse_dart_number(item.get("istc_totqy", "0"))
        treasury = _parse_dart_number(item.get("tesstk_co", "0"))

        if "보통주" in se:
            result["shares_ordinary"] = issued
            result["treasury_ordinary"] = treasury
        elif "우선주" in se:
            result["shares_preferred"] = issued
            result["treasury_preferred"] = treasury

    return result
