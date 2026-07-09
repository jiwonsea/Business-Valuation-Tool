"""EDINET API v2 client and XBRL parser for Japanese listed companies.

EDINET API v2 requires an API key in the ``Subscription-Key`` query parameter.
Set ``EDINET_API_KEY`` in the environment for live document list/download calls.

Internal financial unit: JPY millions, matching BVT's KR/US display-unit model.
"""

from __future__ import annotations

import io
import os
import time
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx
from defusedxml.ElementTree import fromstring as safe_fromstring

from .api_guard import api_guard

EDINET_BASE = os.getenv("EDINET_API_BASE", "https://api.edinet-fsa.go.jp/api/v2")
_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "edinet"
_DOC_CACHE_TTL = 86400

ANNUAL_DOC_TYPE = "120"
QUARTERLY_DOC_TYPE = "140"


@dataclass(frozen=True)
class EdinetDocument:
    doc_id: str
    edinet_code: str
    sec_code: str
    filer_name: str
    doc_type_code: str
    doc_description: str
    period_end: date | None
    submit_date: date | None


def _api_key() -> str:
    key = os.getenv("EDINET_API_KEY")
    if not key:
        raise RuntimeError("EDINET_API_KEY is required for EDINET API v2")
    return key


@api_guard("edinet")
def get_document_list(file_date: date) -> list[dict[str, Any]]:
    """Return EDINET documents for one file date."""
    params = {
        "date": file_date.isoformat(),
        "type": 2,
        "Subscription-Key": _api_key(),
    }
    resp = httpx.get(f"{EDINET_BASE}/documents.json", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if str(data.get("statusCode") or data.get("StatusCode")) not in {"200", ""}:
        raise RuntimeError(data.get("message") or f"EDINET API error: {data}")
    return data.get("results") or []


@api_guard("edinet")
def download_xbrl_zip(doc_id: str) -> bytes:
    """Download submitted document body, audit report, and XBRL ZIP."""
    params = {"type": 1, "Subscription-Key": _api_key()}
    resp = httpx.get(f"{EDINET_BASE}/documents/{doc_id}", params=params, timeout=60)
    resp.raise_for_status()
    return resp.content


def find_latest_document(
    sec_code: str,
    *,
    as_of: date | None = None,
    days_back: int = 460,
    include_quarterly: bool = False,
) -> EdinetDocument | None:
    """Find latest annual securities report for a 4-digit Japanese securities code."""
    as_of = as_of or date.today()
    normalized = _normalize_sec_code(sec_code)
    wanted_types = {ANNUAL_DOC_TYPE}
    if include_quarterly:
        wanted_types.add(QUARTERLY_DOC_TYPE)

    best: EdinetDocument | None = None
    for offset in range(days_back + 1):
        file_date = as_of - timedelta(days=offset)
        for row in _cached_document_list(file_date):
            doc = _document_from_row(row)
            if doc is None:
                continue
            if _normalize_sec_code(doc.sec_code) != normalized:
                continue
            if doc.doc_type_code not in wanted_types:
                continue
            if best is None or (doc.submit_date or date.min) > (best.submit_date or date.min):
                best = doc
        if best is not None and best.doc_type_code == ANNUAL_DOC_TYPE:
            return best
    return best


def get_edinet_code(sec_code: str, *, as_of: date | None = None) -> str | None:
    doc = find_latest_document(sec_code, as_of=as_of, include_quarterly=True)
    return doc.edinet_code if doc else None


def fetch_financials(sec_code: str, years: list[int] | None = None) -> dict[int, dict]:
    """Fetch and parse latest EDINET annual report for BVT profile generation."""
    doc = find_latest_document(sec_code)
    if doc is None:
        raise RuntimeError(f"No EDINET annual securities report found for {sec_code}")
    parsed = parse_xbrl_zip(download_xbrl_zip(doc.doc_id))
    if years is None:
        return parsed
    return {year: row for year, row in parsed.items() if year in set(years)}


def parse_xbrl_zip(content: bytes) -> dict[int, dict]:
    """Parse the first likely XBRL instance in an EDINET ZIP."""
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        names = [
            name
            for name in zf.namelist()
            if name.lower().endswith(".xbrl") and "audit" not in name.lower()
        ]
        if not names:
            raise ValueError("EDINET ZIP contains no XBRL instance")
        # Prefer the main public-doc instance over taxonomy/linkbase files.
        names.sort(key=lambda name: (0 if "PublicDoc" in name else 1, len(name)))
        return parse_xbrl_text(zf.read(names[0]).decode("utf-8", errors="replace"))


def parse_xbrl_text(xml_text: str) -> dict[int, dict]:
    root = safe_fromstring(xml_text.encode("utf-8"))
    contexts = _parse_contexts(root)
    facts = _collect_facts(root, contexts)
    years = sorted({ctx["year"] for ctx in contexts.values() if ctx.get("year")})
    result: dict[int, dict] = {}
    for year in years:
        row = {
            "revenue": _first_fact(facts, year, FIELD_TAGS["revenue"], "duration"),
            "op": _first_fact(facts, year, FIELD_TAGS["op"], "duration"),
            "net_income": _first_fact(facts, year, FIELD_TAGS["net_income"], "duration"),
            "assets": _first_fact(facts, year, FIELD_TAGS["assets"], "instant"),
            "liabilities": _first_fact(facts, year, FIELD_TAGS["liabilities"], "instant"),
            "equity": _first_fact(facts, year, FIELD_TAGS["equity"], "instant"),
            "dep": _first_fact(facts, year, FIELD_TAGS["dep"], "duration"),
            "amort": _first_fact(facts, year, FIELD_TAGS["amort"], "duration"),
            "gross_borr": _first_fact(facts, year, FIELD_TAGS["gross_borr"], "instant"),
            "cash": _first_fact(facts, year, FIELD_TAGS["cash"], "instant"),
            "capex": abs(_first_fact(facts, year, FIELD_TAGS["capex"], "duration")),
            "interest_expense": _first_fact(facts, year, FIELD_TAGS["interest_expense"], "duration"),
        }
        row["net_borr"] = row["gross_borr"] - row.pop("cash", 0)
        row["de_ratio"] = round(row["gross_borr"] / row["equity"] * 100, 1) if row["equity"] else 0.0
        if any(row.get(key, 0) for key in ("revenue", "op", "net_income", "assets")):
            result[year] = row
    return result


FIELD_TAGS = {
    "revenue": [
        "RevenueIFRS",
        "Revenue",
        "NetSales",
        "OperatingRevenue",
    ],
    "op": [
        "OperatingProfitLossIFRS",
        "OperatingIncome",
        "OperatingProfit",
        "OperatingIncomeLoss",
    ],
    "net_income": [
        "ProfitLossAttributableToOwnersOfParentIFRS",
        "ProfitLossAttributableToOwnersOfParent",
        "NetIncomeLossAttributableToOwnersOfParent",
        "ProfitLoss",
        "NetIncome",
    ],
    "assets": ["AssetsIFRS", "Assets", "TotalAssets"],
    "liabilities": ["LiabilitiesIFRS", "Liabilities", "TotalLiabilities"],
    "equity": [
        "EquityAttributableToOwnersOfParentIFRS",
        "Equity",
        "NetAssets",
        "ShareholdersEquity",
    ],
    "dep": ["DepreciationAndAmortisationIFRS", "DepreciationAndAmortization", "Depreciation"],
    "amort": ["AmortisationExpense", "AmortizationOfIntangibleAssets", "Amortization"],
    "gross_borr": ["BondsAndBorrowingsIFRS", "InterestBearingDebt", "Borrowings", "BondsPayable"],
    "cash": ["CashAndCashEquivalentsIFRS", "CashAndCashEquivalents", "CashAndDeposits"],
    "capex": ["PurchaseOfPropertyPlantAndEquipment", "PaymentsForPurchaseOfPropertyPlantAndEquipment"],
    "interest_expense": ["FinanceCostsIFRS", "InterestExpenses", "InterestExpense"],
}


def _cached_document_list(file_date: date) -> list[dict[str, Any]]:
    cache = _CACHE_DIR / f"documents_{file_date.isoformat()}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < _DOC_CACHE_TTL:
        import json

        return json.loads(cache.read_text(encoding="utf-8"))
    rows = get_document_list(file_date)
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    import json

    cache.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def _document_from_row(row: dict[str, Any]) -> EdinetDocument | None:
    doc_id = row.get("docID")
    if not doc_id:
        return None
    return EdinetDocument(
        doc_id=doc_id,
        edinet_code=row.get("edinetCode") or "",
        sec_code=row.get("secCode") or "",
        filer_name=row.get("filerName") or "",
        doc_type_code=str(row.get("docTypeCode") or ""),
        doc_description=row.get("docDescription") or "",
        period_end=_parse_date(row.get("periodEnd")),
        submit_date=_parse_date(str(row.get("submitDateTime") or "")[:10]),
    )


def _parse_contexts(root) -> dict[str, dict[str, Any]]:
    contexts = {}
    for elem in root.iter():
        if _local(elem.tag) != "context":
            continue
        context_id = elem.attrib.get("id")
        if not context_id:
            continue
        period_type = ""
        end = None
        has_segment = False
        for child in elem.iter():
            local = _local(child.tag)
            if local == "segment":
                has_segment = True
            elif local == "instant":
                period_type = "instant"
                end = _parse_date(child.text)
            elif local == "endDate":
                period_type = "duration"
                end = _parse_date(child.text)
        contexts[context_id] = {
            "type": period_type,
            "end": end,
            "year": end.year if end else None,
            "has_segment": has_segment,
        }
    return contexts


def _collect_facts(root, contexts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    facts = []
    for elem in root.iter():
        context_ref = elem.attrib.get("contextRef")
        if not context_ref or context_ref not in contexts:
            continue
        value = _number(elem.text)
        if value is None:
            continue
        facts.append(
            {
                "tag": _local(elem.tag),
                "value": round(value / 1_000_000),
                "context": contexts[context_ref],
            }
        )
    return facts


def _first_fact(facts: list[dict[str, Any]], year: int, tags: list[str], period_type: str) -> int:
    tag_lowers = [tag.lower() for tag in tags]
    exact_candidates = []
    fuzzy_candidates = []
    for fact in facts:
        ctx = fact["context"]
        if ctx.get("year") != year or ctx.get("type") != period_type:
            continue
        tag = fact["tag"].lower()
        if any(wanted == tag for wanted in tag_lowers):
            exact_candidates.append(fact)
            continue
        if any(wanted in tag for wanted in tag_lowers):
            fuzzy_candidates.append(fact)
    candidates = exact_candidates or fuzzy_candidates
    if not candidates:
        return 0
    candidates.sort(key=lambda fact: (fact["context"].get("has_segment", False), -abs(fact["value"])))
    return int(candidates[0]["value"])


def _normalize_sec_code(sec_code: str) -> str:
    code = str(sec_code).strip()
    if code.endswith(".T"):
        code = code[:-2]
    code = "".join(ch for ch in code if ch.isdigit())
    if len(code) == 5 and code.endswith("0"):
        code = code[:4]
    return code


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag
