"""R16 — investability gate 출력 델타 진단.

READ-ONLY. 파일을 쓰지 않고, 네트워크/LLM 호출을 하지 않는다.

목적:
  R12 수정(`text=vi.profile_text`)으로 TODO/placeholder 검사가 처음으로 프로덕션
  실행 경로에서 발화한다. 그 결과 `profiles/*.yaml`의 게이트 판정과 quality가
  어떻게 바뀌는지 **실측**한다.

비교:
  OLD 게이트 = text=""            (R12 이전 동작 — TODO/placeholder 검사 사실상 무력)
  NEW 게이트 = text=profile_text  (R12 이후 동작)

출력:
  프로필별 draft(old→new), quality(pre-gate → post-gate), 신규 blocker 목록.
  마지막에 "text 때문에 판정이 바뀐" 프로필만 따로 집계한다.

사용:
  PYTHONIOENCODING=utf-8 python scripts/r16_profile_delta.py
  PYTHONIOENCODING=utf-8 python scripts/r16_profile_delta.py profiles/nvda.yaml
"""

from __future__ import annotations

import io
import sys
import traceback
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.investability_gate import (  # noqa: E402
    evaluate_investability,
    gate_inputs_from_profile,
)
from valuation_runner import (  # noqa: E402
    _dcf_per_share,
    _peer_median_per_share,
    _raw_profile_for_gate,
    calc_quality_score,
    load_profile,
    run_valuation,
)

# TODO/placeholder 계열 blocker만 뽑기 위한 check 이름
_TEXT_DEPENDENT_CHECKS = {"no_todo_markers", "no_placeholder_multiples"}


def _gate(vi, result, pre_gate_grade: str | None, text: str):
    """게이트를 지정한 text로 재평가한다 (프로덕션과 동일한 입력 조립)."""
    cons = vi.consolidated.get(vi.base_year, {})
    inputs = gate_inputs_from_profile(
        _raw_profile_for_gate(vi, result),
        dcf_value=_dcf_per_share(vi, result),
        peer_median_value=_peer_median_per_share(result),
        quality_grade=pre_gate_grade,
        consolidated_revenue=cons.get("revenue"),
        text=text,
    )
    return evaluate_investability(inputs)


def _blockers(report) -> list[str]:
    return [f.check for f in report.findings if f.severity == "block" and not f.passed]


def analyze(path: Path) -> dict:
    vi = load_profile(str(path))
    result = run_valuation(vi)  # ← 현재(NEW) 게이트가 이미 적용된 결과

    # 게이트 적용 전 quality: 원본 vi(draft 플래그 그대로)로 재계산
    pre = calc_quality_score(vi, result)
    pre_grade, pre_total = pre.grade, pre.total

    old = _gate(vi, result, pre_grade, text="")
    new = _gate(vi, result, pre_grade, text=vi.profile_text)

    old_b, new_b = set(_blockers(old)), set(_blockers(new))
    text_only = sorted((new_b - old_b) & _TEXT_DEPENDENT_CHECKS)

    post = result.quality
    return {
        "file": path.name,
        "yaml_draft": vi.draft,
        "old_draft": old.draft,
        "new_draft": new.draft,
        "verdict_flipped": (not old.draft) and new.draft,  # text 때문에 새로 draft가 된 경우
        "pre_grade": pre_grade,
        "pre_total": pre_total,
        "post_grade": post.grade if post else None,
        "post_total": post.total if post else None,
        "result_draft": result.draft,
        "old_blockers": sorted(old_b),
        "new_blockers": sorted(new_b),
        "text_only_blockers": text_only,
    }


def main() -> int:
    args = sys.argv[1:]
    paths = (
        [Path(a) for a in args]
        if args
        else sorted((ROOT / "profiles").glob("*.yaml"))
    )

    rows: list[dict] = []
    failed: list[tuple[str, str]] = []
    for path in paths:
        try:
            rows.append(analyze(path))
        except Exception as exc:  # 진단 도구 — 한 파일 실패가 전체를 막지 않는다
            failed.append((path.name, f"{type(exc).__name__}: {exc}"))
            traceback.print_exc(limit=1)

    print("\n" + "=" * 100)
    print("R16 — investability gate 출력 델타 (OLD text=\"\"  →  NEW text=profile_text)")
    print("=" * 100)
    header = f"{'profile':<22} {'yaml':<6} {'draft(old→new)':<16} {'quality(pre→post)':<20} {'text로 새로 걸린 blocker'}"
    print(header)
    print("-" * 100)
    for r in rows:
        draft_col = f"{str(r['old_draft']):<5} → {str(r['new_draft']):<5}"
        q_col = f"{r['pre_grade']}/{r['pre_total']} → {r['post_grade']}/{r['post_total']}"
        flag = "🔴 " if r["verdict_flipped"] else "   "
        print(
            f"{flag}{r['file']:<19} {str(r['yaml_draft']):<6} {draft_col:<16} {q_col:<20} "
            f"{', '.join(r['text_only_blockers']) or '—'}"
        )

    flipped = [r for r in rows if r["verdict_flipped"]]
    newly_f = [r for r in rows if r["post_grade"] == "F" and r["pre_grade"] != "F"]
    already = [r for r in rows if r["old_draft"] and r["new_draft"]]

    print("-" * 100)
    print(f"총 프로필                          : {len(rows)}")
    print(f"R12 이전에도 이미 draft            : {len(already)}  (dcf_vs_peer 등 text 무관 blocker)")
    print(f"🔴 text 때문에 새로 draft가 된 것   : {len(flipped)}  → {[r['file'] for r in flipped]}")
    print(f"🔴 quality가 F로 떨어진 것          : {len(newly_f)}  → {[r['file'] for r in newly_f]}")
    if failed:
        print(f"\n실행 실패 {len(failed)}건:")
        for name, err in failed:
            print(f"  - {name}: {err}")

    print(
        "\n해석:\n"
        "  · 'R12 이전에도 이미 draft'  = 게이트가 원래도 잡고 있었다. R12는 blocker 사유만 추가.\n"
        "  · 'text 때문에 새로 draft'   = R12가 없었으면 **확신 있는 밸류에이션이 나갔을** 프로필.\n"
        "                                 ← 이 목록이 곧 '게이트가 죽어 있던 동안의 실제 노출'이다.\n"
        "  · 'quality F로 하락'         = 주간 리포트/네이버 포스팅 출력이 실제로 바뀌는 대상."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
