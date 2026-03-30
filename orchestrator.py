"""전체 워크플로우 오케스트레이터 — 5단계 파이프라인.

Phase 1: 데이터 수집 (DART)
Phase 2: 부문 분석 (AI 보조)
Phase 3: 가정값 설정 (AI 초안 → 사용자 수정)
Phase 4: 밸류에이션 (엔진)
Phase 5: 출력 (Excel + 리서치 노트)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from schemas.models import ValuationInput, ValuationResult
from cli import load_profile, run_valuation
from output.excel_builder import export


def run_from_profile(profile_path: str, output_dir: str | None = None) -> tuple[ValuationInput, ValuationResult, str]:
    """YAML 프로필 → 밸류에이션 → Excel.

    Returns:
        (입력 데이터, 결과, Excel 경로)
    """
    vi = load_profile(profile_path)
    result = run_valuation(vi)
    excel_path = export(vi, result, output_dir)
    return vi, result, excel_path


def format_summary(vi: ValuationInput, result: ValuationResult) -> str:
    """결과 요약 텍스트 생성 (리서치 노트/UI 용)."""
    lines = []
    lines.append(f"# {vi.company.name} 기업가치평가 요약")
    lines.append(f"분석일: {vi.company.analysis_date}")
    lines.append("")

    # WACC
    w = result.wacc
    lines.append(f"## WACC: {w.wacc}%")
    lines.append(f"- βL={w.bl}, Ke={w.ke}%, Kd(세후)={w.kd_at}%")
    lines.append("")

    # SOTP
    seg_names = {code: info["name"] for code, info in vi.segments.items()}
    lines.append(f"## SOTP EV: {result.total_ev:,}백만원 ({result.total_ev/100:,.0f}억원)")
    for code, s in result.sotp.items():
        if s.ev > 0:
            lines.append(f"- {seg_names.get(code, code)}: EBITDA {s.ebitda:,} × {s.multiple:.1f}x = {s.ev:,}백만원")
    lines.append("")

    # 시나리오
    lines.append("## 시나리오 분석")
    for code, sc in vi.scenarios.items():
        sr = result.scenarios[code]
        lines.append(f"- {sc.name} ({sc.prob}%): 주당 {sr.post_dlom:,}원 → 가중 {sr.weighted:,}원")
    lines.append(f"- **확률가중 주당 가치: {result.weighted_value:,}원**")
    lines.append("")

    # DCF
    dcf = result.dcf
    diff = (dcf.ev_dcf - result.total_ev) / result.total_ev * 100
    lines.append(f"## DCF 교차검증: {dcf.ev_dcf:,}백만원 (SOTP 대비 {diff:+.1f}%)")

    return "\n".join(lines)
