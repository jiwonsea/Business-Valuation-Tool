"""DART OpenAPI client -- financial statements, annual reports, and corporate code lookup.

Requires DART API Key: https://opendart.fss.or.kr/
Environment variable: DART_API_KEY
"""

import io
import logging
import os
import re
import time
import zipfile
from pathlib import Path
from xml.etree.ElementTree import Element as ET_Element
from defusedxml.ElementTree import parse as safe_parse, fromstring as safe_fromstring

import httpx

logger = logging.getLogger(__name__)

DART_BASE = os.getenv("DART_API_BASE", "https://opendart.fss.or.kr/api")

# corpCode.xml disk cache (8MB ZIP -> avoid re-downloading each time)
_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
_CORP_CODE_CACHE = _CACHE_DIR / "corpCode.xml"
_CORP_CODE_TTL = 86400  # 24 hours


def _get_api_key() -> str:
    key = os.getenv("DART_API_KEY")
    if not key:
        raise RuntimeError("DART_API_KEY 환경변수가 설정되지 않았습니다.")
    return key


def _load_corp_code_xml() -> ET_Element:
    """Load corpCode.xml (disk cache first, re-download on expiry)."""
    from .api_guard import ApiGuard

    guard = ApiGuard.get()

    # Check cache validity
    if _CORP_CODE_CACHE.exists():
        age = time.time() - _CORP_CODE_CACHE.stat().st_mtime
        if age < _CORP_CODE_TTL:
            logger.debug("corpCode.xml 캐시 사용 (age=%.0fs)", age)
            guard.record_cache_hit("dart")
            return safe_parse(_CORP_CODE_CACHE).getroot()

    # No cache or expired -> download
    guard.check("dart")
    logger.info("corpCode.xml 다운로드 중 (~8MB)...")
    key = _get_api_key()
    resp = httpx.get(f"{DART_BASE}/corpCode.xml", params={"crtfc_key": key}, timeout=30)
    resp.raise_for_status()
    guard.record_success("dart")

    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        xml_data = z.read(z.namelist()[0])

    # Save to disk
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _CORP_CODE_CACHE.write_bytes(xml_data)
    logger.info("corpCode.xml 캐시 저장 완료 (%s)", _CORP_CODE_CACHE)

    return safe_fromstring(xml_data)


def get_corp_code(company_name: str) -> str | None:
    """Look up DART corp_code by company name.

    corpCode.xml -> full corporate code ZIP -> XML parsing -> company name matching
    """
    result = get_corp_info(company_name)
    return result["corp_code"] if result else None


# Words that only state the legal form of a company.
_LEGAL_FORM_WORDS = frozenset(
    {"co", "ltd", "inc", "corp", "corporation", "company", "limited", "주식회사", "주"}
)
_NAME_WORD = re.compile(r"[0-9a-z가-힣]+")


def _name_as_written(name: str) -> str:
    """A company name with case and spacing set aside, nothing else."""
    return " ".join(name.split()).casefold()


def _name_letters(name: str) -> str:
    """A company name with punctuation set aside as well; every word is kept.

    "JS Corporation." == "JS Corporation", "KT & G" == "KT&G".
    """
    return "".join(_NAME_WORD.findall(name.casefold().replace("&", " and ")))


def _registered_name_key(name: str) -> str:
    """A company name with its legal-form words dropped too.

    "SK Hynix" == "SK hynix Inc.", "LS Corporation" == "LS Corp.". Words that
    tell companies apart stay: "OCI" != "OCI Holdings Company Ltd.".
    """
    words = _NAME_WORD.findall(name.casefold().replace("&", " and "))
    return "".join(word for word in words if word not in _LEGAL_FORM_WORDS)


# Strictest first. A looser comparison merges distinct listed companies
# ("JS Corporation" / "JS Company Limited" share a key), so it is used only
# when no stricter one finds a row. The letters and the key can also point at
# different companies, because a legal-form word is dropped only where it
# stands alone: "Sewon Corporation" has the letters of "SewonCorporation" and
# the key of "Sewon Co.,Ltd". The letters are asked first.
_NAME_FORMS = (_name_as_written, _name_letters, _registered_name_key)


def _find_selected_listing(
    root: ET_Element, company_name: str, stock_code: str
) -> dict | None:
    """Registry row for a listing a caller selected by name and stock code.

    Only rows that carry a stock code are looked at, and among them only the
    rows registered under the selected name, Korean or English. The row that
    carries ``stock_code`` is the company. When none of them carries it, name
    and code disagree: the company the name states is returned with its own
    stock code, and the caller that selected ``stock_code`` rejects it.

    None when no row is registered under the selected name. The stock code
    alone identifies nothing: a selected code may be another company's, and
    the name is the only evidence against it. Among several rows the most
    recently modified one wins, then registry order.
    """
    listed = [
        corp
        for corp in root.findall(".//list")
        if (corp.findtext("stock_code") or "").strip()
    ]
    for form in _NAME_FORMS:
        wanted = form(company_name)
        if not wanted:
            continue
        named = [
            corp
            for corp in listed
            if wanted
            in (
                form(corp.findtext("corp_name") or ""),
                form(corp.findtext("corp_eng_name") or ""),
            )
        ]
        if named:
            with_code = [
                corp
                for corp in named
                if (corp.findtext("stock_code") or "").strip() == stock_code
            ]
            best = max(
                with_code or named, key=lambda corp: corp.findtext("modify_date") or ""
            )
            return {
                "corp_code": best.findtext("corp_code", ""),
                "stock_code": (best.findtext("stock_code") or "").strip(),
                "is_listed": True,
            }
    return None


def get_corp_info(company_name: str, stock_code: str | None = None) -> dict | None:
    """Look up DART corp_code + listing status by company name.

    Args:
        stock_code: stock code the caller selected for this company, if any.
            The rows registered under ``company_name`` are then tried first,
            see _find_selected_listing(). Without one, or when no row is
            registered under that name, the lookup is the name lookup below.

    Returns:
        {"corp_code": str, "stock_code": str|None, "is_listed": bool} or None
    """
    root = _load_corp_code_xml()

    if stock_code:
        selected = _find_selected_listing(root, company_name, stock_code)
        if selected is not None:
            return selected

    # Collect all matching candidates, then sort by listed first + exact match first
    candidates = []
    for corp in root.findall(".//list"):
        name = corp.findtext("corp_name", "")
        if company_name in name or name in company_name:
            stock_code = (corp.findtext("stock_code") or "").strip()
            is_exact = name == company_name
            is_listed = bool(stock_code)
            candidates.append(
                {
                    "corp_code": corp.findtext("corp_code", ""),
                    "stock_code": stock_code if stock_code else None,
                    "is_listed": is_listed,
                    "_exact": is_exact,
                }
            )

    if not candidates:
        return None

    # Sort: exact match > listed > others
    candidates.sort(key=lambda c: (c["_exact"], c["is_listed"]), reverse=True)
    best = candidates[0]
    best.pop("_exact")
    return best


def get_corp_eng_name_by_stock_code(stock_code: str) -> str | None:
    """Return DART corp_eng_name for a given stock code (6-digit KR code).

    Returns English company name from DART corpCode.xml, or None if not found.
    Uses the same cached XML as get_corp_info — no extra network calls.
    """
    if not stock_code or not stock_code.strip().isdigit():
        return None
    code = stock_code.strip()
    root = _load_corp_code_xml()
    for corp in root.findall(".//list"):
        sc = (corp.findtext("stock_code") or "").strip()
        if sc == code:
            eng = (corp.findtext("corp_eng_name") or "").strip()
            return eng if eng else None
    return None


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
    resp = httpx.get(
        f"{DART_BASE}/document.xml",
        params={"crtfc_key": key, "rcept_no": rcept_no},
        timeout=60,
    )
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        xml_data = z.read(z.namelist()[0])
    return xml_data.decode("utf-8", errors="replace")


@api_guard("dart")
def get_single_company_info(corp_code: str) -> dict:
    """Company overview query (company.json).

    Returns: CEO name, industry, address, shares, etc.
    """
    key = _get_api_key()
    resp = httpx.get(
        f"{DART_BASE}/company.json",
        params={"crtfc_key": key, "corp_code": corp_code},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "000":
        raise RuntimeError(f"DART API 오류: {data.get('message')}")
    return data


def _parse_dart_number(s: str) -> int:
    """Parse DART number string ('5,969,782,550' -> 5969782550, '-' -> 0).

    Fail-closed by design: only blank/'-' map to 0; any other non-numeric
    string raises ValueError. A silent 0 on a valid share-class row would
    understate treasury shares and flow an unflagged wrong number into
    valuation -- explicit failure is safer. Non-numeric rows (합계/비고)
    must be filtered out by the caller before parsing.
    """
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
        f"{DART_BASE}/stockTotqySttus.json",
        params=params,
        timeout=15,
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
        # Only 보통주/우선주 rows carry per-class share counts. The 합계 row
        # duplicates totals and the 비고 row holds multi-line free text
        # (e.g. treasury-stock history) that must never reach the number
        # parser -- it crashed with ValueError on SK hynix.
        if "보통주" not in se and "우선주" not in se:
            continue
        # istc_totqy: total shares currently issued, tesstk_co: treasury shares
        issued = _parse_dart_number(item.get("istc_totqy", "0"))
        treasury = _parse_dart_number(item.get("tesstk_co", "0"))

        if "보통주" in se:
            result["shares_ordinary"] = issued
            result["treasury_ordinary"] = treasury
        else:
            result["shares_preferred"] = issued
            result["treasury_preferred"] = treasury

    return result
