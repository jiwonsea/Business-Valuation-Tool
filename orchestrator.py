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
from valuation_runner import load_profile, run_valuation
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
    unit = vi.company.currency_unit
    sym = "원" if vi.company.market == "KR" else "$"
    seg_names = {code: info["name"] for code, info in vi.segments.items()}

    lines.append(f"# {vi.company.name} 기업가치평가 요약")
    lines.append(f"분석일: {vi.company.analysis_date}  |  방법론: **{result.primary_method.upper()}**")
    lines.append("")

    # WACC
    w = result.wacc
    lines.append(f"## WACC: {w.wacc}%")
    lines.append(f"- βL={w.bl}, Ke={w.ke}%, Kd(세후)={w.kd_at}%")
    lines.append("")

    # DDM (금융업종)
    if result.ddm:
        ddm = result.ddm
        lines.append(f"## DDM 밸류에이션")
        lines.append(f"- DPS: {ddm.dps:,.0f}{sym}  |  배당성장률: {ddm.growth:.2f}%  |  Ke: {ddm.ke:.2f}%")
        lines.append(f"- **주당 내재가치: {ddm.equity_per_share:,}{sym}**")
        lines.append("")

    # SOTP (있는 경우)
    if result.sotp:
        lines.append(f"## SOTP EV: {result.total_ev:,}{unit}")
        for code, s in result.sotp.items():
            if s.ev > 0:
                lines.append(f"- {seg_names.get(code, code)}: EBITDA {s.ebitda:,} × {s.multiple:.1f}x = {s.ev:,}{unit}")
        lines.append("")

    # DCF
    if result.dcf:
        dcf = result.dcf
        lines.append(f"## DCF EV: {dcf.ev_dcf:,}{unit}")
        if result.sotp and result.total_ev > 0:
            diff = (dcf.ev_dcf - result.total_ev) / result.total_ev * 100
            lines.append(f"- SOTP 대비 {diff:+.1f}%")
        lines.append("")

    # 시나리오
    if result.scenarios:
        lines.append("## 시나리오 분석")
        for code, sc in vi.scenarios.items():
            if code in result.scenarios:
                sr = result.scenarios[code]
                lines.append(f"- {sc.name} ({sc.prob}%): 주당 {sr.post_dlom:,}{sym} → 가중 {sr.weighted:,}{sym}")
        lines.append(f"- **확률가중 주당 가치: {result.weighted_value:,}{sym}**")
        lines.append("")

    # 괴리율
    if result.market_comparison and result.market_comparison.market_price > 0:
        mc = result.market_comparison
        lines.append("## 시장가격 비교")
        lines.append(f"- 내재가치: {mc.intrinsic_value:,}{sym}  |  시장가: {mc.market_price:,.0f}{sym}")
        lines.append(f"- 괴리율: {mc.gap_ratio:+.1%}")
        if mc.flag:
            lines.append(f"- ⚠ {mc.flag}")
        lines.append("")

    # 교차검증
    if result.cross_validations:
        lines.append("## 교차검증")
        for cv in result.cross_validations:
            lines.append(f"- {cv.method}: {cv.per_share:,}{sym}")
        lines.append("")

    return "\n".join(lines)
