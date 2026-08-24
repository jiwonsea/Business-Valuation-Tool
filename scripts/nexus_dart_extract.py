"""Nexus (205500) DART raw-filing extractor — Step 0 fact check.

Sandbox has no network access to opendart.fss.or.kr, so this must run LOCALLY.

Usage (from repo root):
    python scripts/nexus_dart_extract.py

Downloads the two filings, saves the raw document text, and slices out the
sections needed to settle the CROSS_SERVICE multiple debate:
  1. 특수관계자 (Opengame Foundation / OGF BVI) -- related-party or not?
  2. 용역계약 조건 (기간/갱신/수익인식/검수)
  3. 매출채권 & 대손충당금 (22,470백만 회수 실적)
  4. 전환사채 풋/리픽싱 하한 (3~7회)
  5. 주식매수선택권 (미행사 수량/행사가)
  6. 주식수 변동 (101,158주 브리지)

All output written UTF-8 to valuation-results/2026-07-13-nexus-onestore/_dart_raw/
Only ASCII status lines are printed (avoids Windows cp949 UnicodeEncodeError).
"""

from __future__ import annotations

import io
import os
import re
import sys
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "valuation-results" / "2026-07-13-nexus-onestore" / "_dart_raw"
DART_BASE = "https://opendart.fss.or.kr/api"

FILINGS = {
    "분기보고서_2026Q1": "20260514001378",
    "사업보고서_2025": "20260320000272",
}

# (label, regex) -- searched against the plain-text body
SECTIONS: list[tuple[str, str]] = [
    (
        "01_특수관계자",
        r"특수관계자|특수 관계자|관계기업|종속기업|Opengame|OGF|오픈게임",
    ),
    ("02_용역계약", r"용역계약|포괄적\s*용역|계약기간|수익인식|검수|진행률|수행의무"),
    ("03_매출채권", r"매출채권|대손충당금|기대신용손실|연체|회수"),
    (
        "04_전환사채",
        r"전환사채|조기상환청구권|풋옵션|매도청구권|전환가액|리픽싱|최저\s*조정",
    ),
    ("05_스톡옵션", r"주식매수선택권|스톡옵션|행사가격|부여수량"),
    ("06_주식수변동", r"발행주식|주식의\s*총수|증자|전환권행사|제3자배정|자기주식"),
]

CONTEXT = 1200  # chars of context around each hit


def _load_key() -> str:
    key = os.environ.get("DART_API_KEY")
    if key:
        return key
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith("DART_API_KEY"):
                return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit("DART_API_KEY not found (env or .env)")


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "euc-kr", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def fetch(rcept_no: str, key: str) -> str:
    resp = httpx.get(
        f"{DART_BASE}/document.xml",
        params={"crtfc_key": key, "rcept_no": rcept_no},
        timeout=120,
    )
    resp.raise_for_status()
    if resp.headers.get("content-type", "").startswith("application/json"):
        raise SystemExit(f"DART error for {rcept_no}: {resp.text[:300]}")
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        parts = [_decode(z.read(n)) for n in z.namelist()]
    return "\n\n<!--FILE BREAK-->\n\n".join(parts)


def to_text(xml: str) -> str:
    """Strip tags, keep table cell boundaries as ' | ' so numbers stay readable."""
    s = xml
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)</\s*(td|th)\s*>", " | ", s)
    s = re.sub(r"(?i)</\s*(tr|p|div|table|br)\s*>", "\n", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = (
        s.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
    )
    s = re.sub(r"[ \t\xa0]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def slice_sections(text: str, name: str) -> None:
    for label, pattern in SECTIONS:
        rx = re.compile(pattern)
        spans: list[tuple[int, int]] = []
        for m in rx.finditer(text):
            lo, hi = max(0, m.start() - CONTEXT // 3), min(len(text), m.end() + CONTEXT)
            if spans and lo <= spans[-1][1]:
                spans[-1] = (spans[-1][0], max(spans[-1][1], hi))
            else:
                spans.append((lo, hi))
        body = "\n\n===== HIT =====\n\n".join(text[a:b] for a, b in spans)
        path = OUT_DIR / f"{name}__{label}.txt"
        path.write_text(
            f"# {name} / {label}\n# pattern: {pattern}\n# hits(merged): {len(spans)}\n\n{body}",
            encoding="utf-8",
        )
        print(
            f"  [{label}] merged_spans={len(spans):3d} chars={len(body):7d} -> {path.name}"
        )


def main() -> None:
    key = _load_key()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, rcept in FILINGS.items():
        print(f"\n== {name} ({rcept}) ==")
        xml = fetch(rcept, key)
        raw_path = OUT_DIR / f"{name}__RAW.txt"
        text = to_text(xml)
        raw_path.write_text(text, encoding="utf-8")
        print(f"  RAW chars={len(text)} -> {raw_path.name}")
        slice_sections(text, name)
    print(f"\nDONE. Output dir: {OUT_DIR}")


if __name__ == "__main__":
    sys.exit(main())
