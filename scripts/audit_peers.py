# -*- coding: utf-8 -*-
"""One-off peer audit for profiles/*.yaml (backlog P1(c), CODEX-approved design).

Read-only: classifies every peer entry by heuristic pattern and emits a markdown
report. No network, no LLM calls, no profile mutation. Verification tiers here
are REPORT-ONLY suggestions (verified/unresolved judgment needs the local ticker
registry, which is a later P1 step).

Usage: python scripts/audit_peers.py [--out docs/PEER_AUDIT_<date>.md]
"""

import argparse
import datetime as dt
import glob
import re
import sys

import yaml

# One-off M&A / delisted watchlist (NOT a permanent contract -- see backlog P1:
# permanent solution is a local registry with listing_status/acquired_by).
DEFUNCT = {
    "xilinx": "AMD 인수 (2022) — 독립 상장 소멸",
    "mellanox": "NVIDIA 인수 (2020)",
    "activision": "Microsoft 인수 (2023)",
    "vmware": "Broadcom 인수 (2023)",
    "credit suisse": "UBS 인수 (2023)",
    "altera": "Intel 인수 (2015; 2024~ 분사 진행 — 상태 확인 필요)",
    "롯데칩스": "실존 반도체 기업 아님 (제과 브랜드 혼동 의심)",
}
# Product lines / brands that are not reporting entities.
PRODUCT_LINE = re.compile(
    r"(arc graphics|geforce|radeon(?!\s*division)|ryzen|snapdragon(?!\s*ride)|playstation(?!\s*hardware))",
    re.I,
)
DIVISION = re.compile(
    r"(division|사업부|부문|segment|\(.*(datacenter|data center|gaming|automotive|semiconductor|hardware|soc|graphics).*\))",
    re.I,
)
FUSION = re.compile(r"\S\s*/\s*\S")  # "A / B" composite names
CLASS_SHARE = re.compile(r"class\s+[a-c]\b", re.I)  # legit "X / Class B" pattern
ODD = re.compile(
    r"(협회|peers|기타|등\b|외\s*\d|industry average|sector average)", re.I
)
VINTAGE = re.compile(
    r"(20(1\d|2[0-4]))\D*(consensus|estimate|multiple|기준|추정)", re.I
)


def classify(name: str, notes: str):
    flags = []
    low = name.lower()
    for key, why in DEFUNCT.items():
        if key in low:
            flags.append(("DEFUNCT", why))
    if FUSION.search(name) and not CLASS_SHARE.search(name):
        flags.append(("FUSION", "복수 법인/항목을 단일 배수로 융합한 표기"))
    if ODD.search(name):
        flags.append(("NON_ENTITY", "협회/평균/기타 등 법인 아님 신호"))
    if PRODUCT_LINE.search(name):
        flags.append(("PRODUCT_LINE", "제품 라인/브랜드 — 독립 재무 없음"))
    elif DIVISION.search(name):
        flags.append(("DIVISION_EST", "사업부 추정치 — notes에 추정 명시 여부 확인"))
    m = VINTAGE.search(notes or "")
    if m:
        yr = int(m.group(1))
        if yr <= dt.date.today().year - 2:
            flags.append(("STALE", f"배수 빈티지 {yr} — 갱신 검토"))
    return flags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out", default=f"docs/PEER_AUDIT_{dt.date.today().isoformat()}.md"
    )
    args = ap.parse_args()

    rows, totals = [], {"profiles": 0, "peers": 0}
    for path in sorted(glob.glob("profiles/*.yaml")):
        try:
            d = yaml.safe_load(open(path, encoding="utf-8"))
        except Exception as e:  # noqa: BLE001 - audit must not stop on one bad file
            rows.append((path, "(파싱 실패)", "", [("PARSE_ERROR", str(e)[:80])]))
            continue
        peers = (d or {}).get("peers") or []
        totals["profiles"] += 1
        for p in peers:
            totals["peers"] += 1
            name = str(p.get("name", ""))
            flags = classify(name, str(p.get("notes", "")))
            if flags:
                rows.append(
                    (
                        path,
                        name,
                        f"{p.get('ev_ebitda', '?')}x [{p.get('segment_code', '?')}]",
                        flags,
                    )
                )

    sev_order = [
        "PARSE_ERROR",
        "DEFUNCT",
        "NON_ENTITY",
        "FUSION",
        "PRODUCT_LINE",
        "DIVISION_EST",
        "STALE",
    ]
    lines = [
        f"# 피어 전수 감사 리포트 ({dt.date.today().isoformat()})",
        "",
        f"스캔: 프로파일 {totals['profiles']}개 · 피어 {totals['peers']}건 · 플래그 {len(rows)}건 "
        "(읽기 전용 — 제거/수정은 수동 확정 후 별도 커밋)",
        "",
        "| 심각도 | 프로파일 | 피어 | 배수[SEG] | 사유 |",
        "|---|---|---|---|---|",
    ]

    def sev(r):
        return min(sev_order.index(f[0]) for f in r[3])

    for path, name, mult, flags in sorted(rows, key=sev):
        tag = " · ".join(f"**{k}** {v}" for k, v in flags)
        lines.append(f"| {flags[0][0]} | `{path}` | {name} | {mult} | {tag} |")
    lines += [
        "",
        "심각도: DEFUNCT/NON_ENTITY/FUSION = 제거 후보 · PRODUCT_LINE = 제거 또는 모회사 치환 · "
        "DIVISION_EST = notes 추정 명시 확인 · STALE = 배수 갱신 검토 (표시용, 밸류에이션 무영향).",
        "",
    ]
    open(args.out, "w", encoding="utf-8", newline="").write("\r\n".join(lines))
    print(f"report -> {args.out} | flagged {len(rows)}/{totals['peers']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
