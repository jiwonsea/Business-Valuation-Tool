"""P1/P2 promotion-gate pilot v2 (HANDOFF_CODEX_next_scope_decision_2026-07-17 §6.3).

Observation-only research script.  It never writes profiles, engine code, or DB.

Two phases, separable so collection (network) and analysis (offline) can run on
different machines:

  --collect   3 companies x FY2016-2025 x 2 endpoints = exactly 60 DART calls
              (financial 30 + stock 30).  Auto-retry is disabled in-process
              (max_retries=0) so the 60-call cap equals actual HTTP attempts.
              Raw payloads are dumped to a JSON snapshot for offline analysis.
              Aborts before any call if DART remaining quota < 60.

  --analyze   Zero network.  Reproduces the v1 quality metrics from the
              snapshot, then emits per-account restatement-conflict rows in the
              contract's 9-field format with rule-based classification
              (restatement / mapping_error / unit_error / unresolved — no
              guessing: anything ambiguous stays unresolved).  Outputs are
              deterministic: all content derives from the snapshot only.

Point-in-time notes (contract §6.3-3): each fiscal year's payload carries its
own rcept_no (DART filing receipt id whose first 8 digits are the filing date =
available_at).  The conflict table compares the original report value
(thstrm_amount of FY report Y) against the following report's comparative
(frmtrm_amount of FY report Y+1) — both observable at their respective filing
dates; no current-snapshot backfill is used anywhere.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.dart_parser import ACCOUNT_MAP, CAPEX_MAP, parse_financial_statements

COMPANIES = {
    "Samsung Electronics": "00126380",
    "SK hynix": "00164779",
    "LG Electronics": "00401731",
}
YEARS = tuple(range(2016, 2026))
CORE_FIELDS = (
    "revenue",
    "op",
    "net_income",
    "assets",
    "liabilities",
    "equity",
    "capex",
    "gross_borr",
    "net_borr",
)
UNCOVERED_PHASE2_FIELDS = ("eps", "bps", "dps", "roic", "fcf")

SNAPSHOT_DEFAULT = REPO_ROOT / "research" / "pilot_v2" / "raw_payloads.json"
CLASSIFICATION_CSV = REPO_ROOT / "research" / "pilot_v2" / "conflict_classification.csv"
CLASSIFICATION_MD = REPO_ROOT / "research" / "pilot_v2" / "conflict_classification.md"
REPORT_DEFAULT = REPO_ROOT / "pilot_multiyear_quality_report_v2.md"

CALL_BUDGET = 60  # financial 30 + stock 30 — contract hard cap


# ---------------------------------------------------------------------------
# Shared v1-compatible helpers
# ---------------------------------------------------------------------------


def _millions(value) -> int | None:
    if value in (None, "", "-"):
        return None
    try:
        return round(int(str(value).replace(",", "").strip()) / 1_000_000)
    except ValueError:
        return None


def _candidates(items: list[dict], amount_key: str) -> dict[str, list[dict]]:
    """All rows mapping to each internal key, in payload order (provenance)."""
    out: dict[str, list[dict]] = {}
    for item in items:
        name = item.get("account_nm", "")
        key = ACCOUNT_MAP.get(name)
        if key is None and name in CAPEX_MAP:
            key = "capex"
        if key is None:
            continue
        amount = _millions(item.get(amount_key))
        if amount is None:
            continue
        value = abs(amount) if key == "capex" else amount
        out.setdefault(key, []).append(
            {
                "account_nm": name,
                "sj_div": item.get("sj_div", ""),
                "raw": item.get(amount_key, ""),
                "value_mkrw": value,
                "rcept_no": item.get("rcept_no", ""),
            }
        )
    return out


def _period_values(items: list[dict], amount_key: str) -> dict[str, int]:
    """First-match-per-key values — byte-for-byte v1 semantics."""
    values: dict[str, int] = {}
    for item in items:
        name = item.get("account_nm", "")
        key = ACCOUNT_MAP.get(name)
        if key is None and name in CAPEX_MAP:
            key = "capex"
        if key is None or key in values:
            continue
        amount = _millions(item.get(amount_key))
        if amount is not None:
            values[key] = abs(amount) if key == "capex" else amount
    return values


# ---------------------------------------------------------------------------
# Collection (network — run where DART is reachable)
# ---------------------------------------------------------------------------


def collect(snapshot_path: Path) -> int:
    from datetime import date

    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")

    from pipeline.api_guard import ApiGuard
    from pipeline.dart_client import get_financial_statements, get_stock_total_info

    guard = ApiGuard.get()
    before = guard.get_usage_summary().get("dart", {})
    remaining = before.get("remaining", 0)
    if remaining < CALL_BUDGET:
        print(
            f"ABORT: DART remaining quota {remaining} < {CALL_BUDGET}. "
            "No external call was made (contract §6.3-1)."
        )
        return 1

    # Contract: cap counts actual HTTP attempts.  Disable in-process auto-retry
    # so one endpoint call == one attempt; a failed year is recorded, not retried.
    guard.configure("dart", max_retries=0)

    call_log: list[dict] = []
    data: dict[str, dict] = {}
    calls_made = 0

    for name, corp_code in COMPANIES.items():
        company: dict[str, dict] = {"corp_code": corp_code, "financial": {}, "stock": {}}
        data[name] = company
        for year in YEARS:
            if calls_made + 2 > CALL_BUDGET:
                print("ABORT: call budget would be exceeded — stopping early.")
                break

            calls_made += 1
            try:
                items = get_financial_statements(corp_code, year, fs_div="CFS")
                company["financial"][str(year)] = {"items": items}
                call_log.append(
                    {"n": calls_made, "endpoint": "fnlttSinglAcntAll",
                     "company": name, "year": year, "ok": True,
                     "rows": len(items)}
                )
            except Exception as exc:  # recorded, never retried here
                company["financial"][str(year)] = {"error": str(exc)}
                call_log.append(
                    {"n": calls_made, "endpoint": "fnlttSinglAcntAll",
                     "company": name, "year": year, "ok": False,
                     "error": str(exc)}
                )

            calls_made += 1
            try:
                shares = get_stock_total_info(corp_code, year)
                company["stock"][str(year)] = {"shares": shares}
                call_log.append(
                    {"n": calls_made, "endpoint": "stockTotqySttus",
                     "company": name, "year": year, "ok": True}
                )
            except Exception as exc:
                company["stock"][str(year)] = {"error": str(exc)}
                call_log.append(
                    {"n": calls_made, "endpoint": "stockTotqySttus",
                     "company": name, "year": year, "ok": False,
                     "error": str(exc)}
                )

    after = guard.get_usage_summary().get("dart", {})
    snapshot = {
        "meta": {
            "collected_on": date.today().isoformat(),
            "contract": "HANDOFF_CODEX_next_scope_decision_2026-07-17 §6.3",
            "call_budget": CALL_BUDGET,
            "calls_made": calls_made,
            "quota_before": before,
            "quota_after": after,
            "endpoints": ["fnlttSinglAcntAll", "stockTotqySttus"],
            "call_log": call_log,
        },
        "companies": data,
    }

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = snapshot_path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=1),
        encoding="utf-8",
        newline="",
    )
    os.replace(tmp, snapshot_path)
    print(f"snapshot: {snapshot_path}")
    print(
        f"calls_made={calls_made} "
        f"dart_calls_delta={after.get('calls', 0) - before.get('calls', 0)} "
        f"remaining={after.get('remaining')}"
    )
    return 0


# ---------------------------------------------------------------------------
# Analysis (offline — zero network)
# ---------------------------------------------------------------------------


@dataclass
class CompanyQuality:
    name: str
    years_ok: int = 0
    mapped: int = 0
    expected: int = 0
    restatement_pairs: int = 0
    restatement_conflicts: int = 0
    fs_rows: int = 0
    mixed_fs_rows: int = 0
    numeric_values: int = 0
    invalid_numeric_values: int = 0
    share_years_ok: int = 0
    share_api_errors: int = 0
    share_data_missing: int = 0
    conflict_rows: list[dict] = field(default_factory=list)


def _rcept_no(items: list[dict]) -> str:
    for item in items:
        r = item.get("rcept_no")
        if r:
            return r
    return ""


def _fmt_candidates(cands: list[dict]) -> str:
    parts = []
    for c in cands:
        parts.append(
            f"{c['account_nm']}({c['sj_div']})={c['value_mkrw']:,}"
        )
    return " | ".join(parts)


def _classify(cur: list[dict], nxt: list[dict], cur_val: int, nxt_val: int) -> tuple[str, str]:
    """Rule-based classification with evidence.  Ambiguity -> unresolved.

    Rules (documented for the gate review):
      unit_error     ~1000x ratio between the two sides (unit-scale slip).
      mapping_error  the two sides were sourced from different statements
                     (sj_div mismatch), or statement-matched pairs agree while
                     the first-match chosen values differ (pure ordering
                     artifact of the account_nm-only ACCOUNT_MAP lookup).
      restatement    statement-matched pair(s) (same sj_div on both sides)
                     report different values -> the following filing carries a
                     changed comparative.  An account-label alias change
                     (e.g. 영업이익 -> 영업이익(손실), both legitimate
                     ACCOUNT_MAP aliases of the same key) does NOT make this a
                     mapping error; it is recorded in the evidence.
      unresolved     anything else — no guessing.
    """
    cur_chosen = cur[0]
    nxt_chosen = nxt[0]

    ratio = None
    if nxt_val not in (0, None) and cur_val not in (0, None):
        try:
            ratio = abs(cur_val / nxt_val)
        except ZeroDivisionError:
            ratio = None

    # 1. unit_error: ~1000x either direction (KRW vs thousand-KRW style slips)
    if ratio is not None and (900 <= ratio <= 1100 or 1 / 1100 <= ratio <= 1 / 900):
        return (
            "unit_error",
            f"~1000x ratio ({ratio:.4g}); original[{_fmt_candidates([cur_chosen])}] "
            f"vs following-comparative[{_fmt_candidates([nxt_chosen])}]",
        )

    # 2. mapping_error (cross-statement): sides sourced from different statements.
    if cur_chosen["sj_div"] != nxt_chosen["sj_div"]:
        return (
            "mapping_error",
            f"cross-statement sourcing: original from '{cur_chosen['account_nm']}'"
            f"({cur_chosen['sj_div']}), following-comparative from "
            f"'{nxt_chosen['account_nm']}'({nxt_chosen['sj_div']}); "
            f"candidates original[{_fmt_candidates(cur)}] "
            f"following[{_fmt_candidates(nxt)}]",
        )

    # Statement-level pairing: first candidate per sj_div on each side.
    def _per_sj(cands: list[dict]) -> dict[str, dict]:
        m: dict[str, dict] = {}
        for c in cands:
            m.setdefault(c["sj_div"], c)
        return m

    cur_sj = _per_sj(cur)
    nxt_sj = _per_sj(nxt)
    shared = [s for s in cur_sj if s in nxt_sj]
    pair_diffs = [
        (s, cur_sj[s], nxt_sj[s])
        for s in shared
        if cur_sj[s]["value_mkrw"] != nxt_sj[s]["value_mkrw"]
    ]

    if shared and pair_diffs:
        # 3. restatement: same-statement pair(s) changed in the later filing.
        pair_txt = "; ".join(
            f"{s}: {c['value_mkrw']:,} -> {n['value_mkrw']:,}"
            for s, c, n in pair_diffs
        )
        notes = []
        if cur_chosen["account_nm"] != nxt_chosen["account_nm"]:
            notes.append(
                f"account label alias changed '{cur_chosen['account_nm']}' -> "
                f"'{nxt_chosen['account_nm']}' (both map to the same key)"
            )
        if len(cur) > 1 or len(nxt) > 1:
            notes.append(
                "multi-candidate hazard (account_nm-only lookup also matches "
                f"other statements): original[{_fmt_candidates(cur)}] "
                f"following[{_fmt_candidates(nxt)}]"
            )
        return (
            "restatement",
            f"statement-matched pair(s) differ in the following filing — {pair_txt}"
            + ("; " + "; ".join(notes) if notes else ""),
        )

    if shared and not pair_diffs:
        # 4. mapping_error (ordering): matched pairs agree, yet the v1
        #    first-match chosen values differ -> pure ordering artifact.
        return (
            "mapping_error",
            "statement-matched pairs agree; conflict is a first-match ordering "
            f"artifact; candidates original[{_fmt_candidates(cur)}] "
            f"following[{_fmt_candidates(nxt)}]",
        )

    return ("unresolved", "no rule matched; requires manual review")


def analyze_company(name: str, blob: dict) -> CompanyQuality:
    quality = CompanyQuality(name=name)
    raw_by_year: dict[int, list[dict]] = {}

    for year in YEARS:
        fin = blob["financial"].get(str(year), {})
        items = fin.get("items")
        if items is None:
            continue
        raw_by_year[year] = items
        parsed = parse_financial_statements(items, year)
        quality.years_ok += 1
        quality.expected += len(CORE_FIELDS)
        quality.mapped += sum(parsed.get(f) is not None for f in CORE_FIELDS)

        for item in items:
            quality.fs_rows += 1
            if item.get("fs_div") not in (None, "", "CFS"):
                quality.mixed_fs_rows += 1
            amount = item.get("thstrm_amount")
            if amount not in (None, "", "-"):
                quality.numeric_values += 1
                if _millions(amount) is None:
                    quality.invalid_numeric_values += 1

        stock = blob["stock"].get(str(year), {})
        if "error" in stock:
            quality.share_api_errors += 1
        else:
            shares = stock.get("shares")
            if shares and shares.get("shares_ordinary", 0) > 0:
                issued = shares["shares_ordinary"]
                treasury = shares.get("treasury_ordinary", 0)
                if issued >= treasury >= 0:
                    quality.share_years_ok += 1
            elif shares is not None:
                quality.share_data_missing += 1

    for year in YEARS[:-1]:
        cur_items = raw_by_year.get(year, [])
        nxt_items = raw_by_year.get(year + 1, [])
        current = _period_values(cur_items, "thstrm_amount")
        next_comparative = _period_values(nxt_items, "frmtrm_amount")
        cur_cands = _candidates(cur_items, "thstrm_amount")
        nxt_cands = _candidates(nxt_items, "frmtrm_amount")

        for key in sorted(set(current) & set(next_comparative)):
            quality.restatement_pairs += 1
            cur_val = current[key]
            nxt_val = next_comparative[key]
            if cur_val == nxt_val:
                continue
            quality.restatement_conflicts += 1
            classification, evidence = _classify(
                cur_cands[key], nxt_cands[key], cur_val, nxt_val
            )
            diff = nxt_val - cur_val
            rel = round(diff / cur_val * 100, 2) if cur_val else None
            quality.conflict_rows.append(
                {
                    "company": name,
                    "account": key,
                    "fiscal_year": year,
                    "original_report_value": cur_val,
                    "following_report_comparative_value": nxt_val,
                    "absolute_diff": diff,
                    "relative_diff_pct": rel,
                    "classification": classification,
                    "evidence": (
                        f"unit=MKRW; original filing rcept_no={_rcept_no(cur_items)} "
                        f"(FY{year} annual), following filing "
                        f"rcept_no={_rcept_no(nxt_items)} (FY{year + 1} annual); "
                        + evidence
                    ),
                }
            )

    return quality


def _pct(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 1) if denominator else 0.0


CSV_FIELDS = [
    "company",
    "account",
    "fiscal_year",
    "original_report_value",
    "following_report_comparative_value",
    "absolute_diff",
    "relative_diff_pct",
    "classification",
    "evidence",
]


def render_classification_md(rows: list[dict], meta: dict) -> str:
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1
    lines = [
        "# 재작성 충돌 계정별 분류표 (파일럿 v2)",
        "",
        f"- 스냅샷 수집일: {meta.get('collected_on', 'n/a')} · 계약: {meta.get('contract', '')}",
        "- 값 단위: 백만원(MKRW). original = FY 연차보고서 당기(thstrm), "
        "following comparative = 익년 연차보고서 전기(frmtrm).",
        "- classification ∈ {restatement, mapping_error, unit_error, unresolved} — "
        "규칙 기반, 판단 불가 시 unresolved(추측 금지).",
        "",
        "| company | account | FY | original | following comp. | diff | diff% | class | evidence |",
        "|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for r in rows:
        rel = r["relative_diff_pct"]
        lines.append(
            f"| {r['company']} | {r['account']} | {r['fiscal_year']} | "
            f"{r['original_report_value']:,} | "
            f"{r['following_report_comparative_value']:,} | "
            f"{r['absolute_diff']:,} | "
            f"{rel if rel is not None else 'n/a'} | {r['classification']} | "
            f"{r['evidence'].replace('|', '/')} |"
        )
    total = len(rows)
    lines += [
        "",
        "## 분류 합계",
        "",
        f"- 총 충돌: **{total}건**",
    ]
    for cls in ("restatement", "mapping_error", "unit_error", "unresolved"):
        lines.append(f"- {cls}: {counts.get(cls, 0)}건")
    lines.append(
        f"- 합계 검증: {sum(counts.values())} == {total} → "
        f"{'OK' if sum(counts.values()) == total else 'MISMATCH'}"
    )
    lines.append("")
    return "\n".join(lines)


def render_report(results: list[CompanyQuality], meta: dict) -> str:
    lines = [
        "# P1/P2 다년 데이터 품질 파일럿 v2",
        "",
        f"- 스냅샷 수집일: {meta.get('collected_on', 'n/a')} · "
        f"DART 실사용 {meta.get('calls_made', '?')}콜 (상한 {meta.get('call_budget', 60)})",
        "- 범위: KR 3사 × FY2016~FY2025, DART 연결(CFS) 연차 — v1과 동일 입력 계약",
        "- 변경점: dart_client 비고행 파싱 수정(GO 58/60) 반영 후 재수집 · "
        "계정별 충돌 분류표 신설(`research/pilot_v2/`)",
        "- 주의: 이 파일럿은 프로필·엔진·DB를 변경하지 않는다.",
        "",
        "| 회사 | 연도 성공 | 핵심 매핑률 | 결측률 | 재작성 충돌률 | CFS 혼입률 | 금액 정규화 | 주식수 정규화 | 주식 API 오류/원천결측 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for q in results:
        lines.append(
            f"| {q.name} | {q.years_ok}/10 | {_pct(q.mapped, q.expected):.1f}% | "
            f"{100 - _pct(q.mapped, q.expected):.1f}% | "
            f"{_pct(q.restatement_conflicts, q.restatement_pairs):.1f}% "
            f"({q.restatement_conflicts}/{q.restatement_pairs}) | "
            f"{_pct(q.mixed_fs_rows, q.fs_rows):.1f}% | "
            f"{100 - _pct(q.invalid_numeric_values, q.numeric_values):.1f}% | "
            f"{_pct(q.share_years_ok, len(YEARS)):.1f}% | "
            f"{q.share_api_errors}/{q.share_data_missing} |"
        )

    total_expected = sum(q.expected for q in results)
    total_mapped = sum(q.mapped for q in results)
    total_pairs = sum(q.restatement_pairs for q in results)
    total_conflicts = sum(q.restatement_conflicts for q in results)
    hynix = next((q for q in results if q.name == "SK hynix"), None)
    hynix_rate = _pct(hynix.share_years_ok, len(YEARS)) if hynix else 0.0
    lines.extend(
        [
            "",
            "## 판정",
            "",
            f"- 전체 핵심 계정 매핑률: **{_pct(total_mapped, total_expected):.1f}%**",
            f"- 전체 결측률: **{100 - _pct(total_mapped, total_expected):.1f}%**",
            f"- 비교 가능한 전년 수치의 재작성/매핑 충돌률: **{_pct(total_conflicts, total_pairs):.1f}%** ({total_conflicts}/{total_pairs})",
            f"- **SK hynix 주식수 정규화 재측정: {hynix_rate:.1f}%** "
            f"(v1 0.0% — 비고행 파싱 수정의 실 API 실효성 검증)",
            f"- 현 파서 미커버 필드: **{', '.join(UNCOVERED_PHASE2_FIELDS)}**",
            "- 계정별 충돌 분류표: `research/pilot_v2/conflict_classification.md` (합계=충돌 수 검증 포함).",
            "",
            "## 파서 위험 신호 (게이트 발견사항 — 코드 변경 없음, Phase 2 계약 반영 필요)",
            "",
            "- `ACCOUNT_MAP` 주 매핑 루프는 `sj_div`를 필터하지 않는다"
            " (`pipeline/dart_parser.py` L82-89). fnlttSinglAcntAll에는 자본변동표(SCE)에도"
            " `당기순이익` 행이 존재하며(비지배지분 단독 행 포함) 현재는 행 순서(CIS 선행)가"
            " 우연히 보호하고 있다. Phase 2 본구현 시 sj_div 필터를 데이터 계약에 명시할 것.",
            "- 계정명 별칭 변동 관측: 동일 개념이 연도에 따라 `영업이익` ↔ `영업이익(손실)` 등으로"
            " 표기 변경됨 — ACCOUNT_MAP 별칭 커버리지가 시계열 일관성의 전제 조건.",
            "",
            "## point-in-time 원칙 (§6.3-3 — 게이트 계약 그대로)",
            "",
            "- available_at = DART 접수일(rcept_no 선두 8자리). `available_at <= t` 자료만 사용.",
            "- 유통주식 = 평가일 이전 최신 보고서의 발행주식수 − 자기주식. 현재 snapshot 소급 0.",
            "- LTM 재구성 불가 시 결측 처리. corporate action 복원 불가 시 결측/경고.",
            "- 멀티플은 LTM P/B·P/S만. \"12M Forward\" 표기 금지.",
            "- 간이 관측 가격 기준일 = 사업보고서 접수일 종가.",
            "",
            "## 승격 게이트",
            "",
            "본 보고서는 수집 가능성 재측정 + 충돌 원인 분류를 담은 게이트 산출물이며 "
            "P1/P2 본구현 승인이 아니다. 게이트 판정은 분류 결과에 대한 Codex 교차검증 후 결정한다.",
            "",
        ]
    )
    return "\n".join(lines)


def analyze(snapshot_path: Path, report_path: Path) -> int:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    meta = snapshot.get("meta", {})
    results = [
        analyze_company(name, blob)
        for name, blob in snapshot["companies"].items()
    ]

    all_rows: list[dict] = []
    for q in results:
        all_rows.extend(q.conflict_rows)

    CLASSIFICATION_CSV.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, lineterminator="\r\n")
    writer.writeheader()
    for row in all_rows:
        writer.writerow(row)
    # newline="" everywhere: suppress platform newline translation so the
    # emitted bytes (CRLF) are identical on Windows and Linux from the first
    # run — cross-review 2026-07-18 finding (host first-run hash mismatch).
    CLASSIFICATION_CSV.write_text(buf.getvalue(), encoding="utf-8-sig", newline="")

    CLASSIFICATION_MD.write_text(
        render_classification_md(all_rows, meta).replace("\n", "\r\n"),
        encoding="utf-8",
        newline="",
    )
    report_path.write_text(
        render_report(results, meta).replace("\n", "\r\n"),
        encoding="utf-8",
        newline="",
    )

    total_conflicts = sum(q.restatement_conflicts for q in results)
    print(f"report: {report_path}")
    print(f"classification: {CLASSIFICATION_MD}")
    print(
        f"conflicts={total_conflicts} rows={len(all_rows)} "
        f"sum_check={'OK' if total_conflicts == len(all_rows) else 'MISMATCH'}"
    )
    for q in results:
        print(
            f"  {q.name}: conflicts={q.restatement_conflicts}/{q.restatement_pairs} "
            f"share_ok={q.share_years_ok}/10 share_api_err={q.share_api_errors}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--collect", action="store_true", help="fetch 60 DART calls -> snapshot")
    mode.add_argument("--analyze", action="store_true", help="offline analysis from snapshot")
    parser.add_argument("--snapshot", default=str(SNAPSHOT_DEFAULT))
    parser.add_argument("--output", default=str(REPORT_DEFAULT))
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)
    if args.collect:
        return collect(snapshot_path)
    return analyze(snapshot_path, Path(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
