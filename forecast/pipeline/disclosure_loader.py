"""Disclosure / IR text loader.

Phase B uses two sources:
  - local IR deck PDFs, extracted with PyMuPDF
  - keyless DART public viewer MD&A text, cached under reports/.cache

STATUS: DORMANT (2026-07-31). The code is intact but unreachable in the current
configuration: the only production callers are cli.py's Phase-B modes
(--signal-backtest / --call-brief), and both exit early unless the profile
carries a `signal_layer` section. No profile has carried one since 4ebeb7c
(2026-07-10), where the block was dropped from profiles/sk_hynix.yaml during a
window roll-forward. Whether that removal was a deliberate retirement or
collateral loss was NOT determined; see HANDOFF_CODEX_doc_ingest_2026-07-31.md.

KNOWN GAP — do not treat these functions as extraction-complete:
  - load_ir_decks computes char_count_kr but nothing checks it. An image-only or
    partially-image PDF yields empty/partial text and flows on without error.
  - fetch_dart_mdna guards only `char_count_kr == 0`, which cannot distinguish a
    genuinely empty source from a failed extraction (reports/.cache/
    mdna_20240814003052.json is 67 chars of boilerplate and passes).
  - _find_mdna_params slices the FIRST matching viewer node only; a filing that
    splits the section across several eleIds yields partial text silently.

A completeness contract (per-page char counts, extractor version, section
anchors, sha256 of the source) is deliberately NOT implemented here: with zero
reachable callers it could not be validated on a real execution path. It is
specified as part of Phase-B reactivation, together with restored profiles and
real IR-deck / DART fixtures.
"""

from __future__ import annotations

import html
import json
import logging
import re
import time
from datetime import date
from pathlib import Path

from pipeline._ssl_setup import ensure_ssl_env
from schemas.models import DisclosureDocument

ensure_ssl_env()

import httpx  # noqa: E402

logger = logging.getLogger(__name__)

DART_VIEWER_MAIN = "https://dart.fss.or.kr/dsaf001/main.do"
DART_VIEWER_BODY = "https://dart.fss.or.kr/report/viewer.do"
CACHE_DIR = Path("reports/.cache")
MDNA_TITLE = "\uc774\uc0ac\uc758 \uacbd\uc601\uc9c4\ub2e8 \ubc0f \ubd84\uc11d\uc758\uacac"


def count_kr_chars(text: str) -> int:
    """Count Hangul syllable characters."""
    return sum(1 for ch in text if "\uac00" <= ch <= "\ud7a3")


def load_ir_decks(
    deck_specs: list[dict],
    decks_dir: Path,
) -> list[DisclosureDocument]:
    """Load local IR deck PDFs into DisclosureDocuments."""
    import fitz

    documents: list[DisclosureDocument] = []
    for spec in deck_specs:
        filename = spec.get("filename", "")
        path = decks_dir / filename
        period_label = str(spec.get("period_label") or spec.get("event_label") or "")
        if not path.exists():
            logger.warning("IR deck missing, dropping event %s: %s", period_label, path)
            continue

        with fitz.open(path) as pdf:
            raw_text = "\n".join(page.get_text() for page in pdf)

        documents.append(
            DisclosureDocument(
                source="ir_deck",
                doc_date=date.fromisoformat(str(spec["doc_date"])),
                period_label=period_label,
                raw_text=raw_text,
                char_count_kr=count_kr_chars(raw_text),
                url_or_path=str(path),
            )
        )

    return sorted(documents, key=lambda document: document.doc_date)


def _get_with_retry(url: str, params: dict[str, str]) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = httpx.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            return response
        except Exception as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def _extract_tree_value(block: str, name: str) -> str | None:
    patterns = [
        rf"{name}\s*[:=]\s*['\"]([^'\"]+)['\"]",
        rf"['\"]{name}['\"]\s*[:=]\s*['\"]([^'\"]+)['\"]",
        rf"\[['\"]{name}['\"]\]\s*=\s*['\"]([^'\"]+)['\"]",
    ]
    for pattern in patterns:
        match = re.search(pattern, block)
        if match:
            return match.group(1)
    return None


def _find_mdna_params(main_html: str, rcp_no: str) -> dict[str, str]:
    candidates = [MDNA_TITLE, "\uacbd\uc601\uc9c4\ub2e8 \ubc0f \ubd84\uc11d\uc758\uacac"]
    for title in candidates:
        for match in re.finditer(re.escape(title), main_html):
            end = min(len(main_html), match.end() + 2500)
            block = main_html[match.start():end]
            params = {
                "rcpNo": rcp_no,
                "dcmNo": _extract_tree_value(block, "dcmNo") or "",
                "eleId": _extract_tree_value(block, "eleId") or "",
                "offset": _extract_tree_value(block, "offset") or "",
                "length": _extract_tree_value(block, "length") or "",
            }
            if all(params.values()):
                return params
    raise ValueError(f"could not locate DART MD&A viewer node for rcpNo={rcp_no}")


def _html_to_text(raw_html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw_html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = re.sub(r"(?i)</tr\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def fetch_dart_mdna(
    rcp_no: str,
    period_label: str,
    doc_date: date,
    use_cache: bool = True,
) -> DisclosureDocument:
    """Fetch one DART MD&A narrative from the public viewer."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"mdna_{rcp_no}.json"
    if use_cache and cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            cached = json.load(f)
        return DisclosureDocument.model_validate(cached)

    main_response = _get_with_retry(DART_VIEWER_MAIN, {"rcpNo": rcp_no})
    main_html = main_response.text
    params = _find_mdna_params(main_html, rcp_no)
    body_response = _get_with_retry(DART_VIEWER_BODY, params)
    raw_text = _html_to_text(body_response.text)
    char_count_kr = count_kr_chars(raw_text)
    if char_count_kr == 0:
        raise ValueError(f"DART MD&A text was empty for rcpNo={rcp_no}")

    document = DisclosureDocument(
        source="dart_mdna",
        doc_date=doc_date,
        period_label=period_label,
        raw_text=raw_text,
        char_count_kr=char_count_kr,
        url_or_path=f"{DART_VIEWER_BODY}?rcpNo={rcp_no}",
    )
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(document.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
    return document
