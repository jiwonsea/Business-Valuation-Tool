"""Full workflow orchestrator -- 5-phase pipeline.

Phase 1: Data collection (DART)
Phase 2: Segment analysis (AI-assisted)
Phase 3: Assumption setup (AI draft -> user revision)
Phase 4: Valuation (engine)
Phase 5: Output (Excel + research note)
"""

import logging
from pathlib import Path

from schemas.models import ValuationInput, ValuationResult
from valuation_runner import load_profile, run_valuation, _seg_names
from output.excel_builder import export

logger = logging.getLogger(__name__)


def _save_to_db(
    vi: ValuationInput, result: ValuationResult, profile_path: str | None = None
) -> str | None:
    """Save valuation result to Supabase (silently ignore on failure)."""
    try:
        from db.repository import save_valuation, save_profile

        val_id = save_valuation(vi, result)
        if val_id and profile_path:
            yaml_text = Path(profile_path).read_text(encoding="utf-8")
            save_profile(
                company_name=vi.company.name,
                profile_yaml=yaml_text,
                profile_data=vi.model_dump(mode="json"),
                file_name=Path(profile_path).name,
            )
        # Capture prediction snapshot for backtesting
        if val_id:
            try:
                from db.backtest_repository import save_prediction_snapshot

                save_prediction_snapshot(vi, result, val_id)
            except Exception:
                logger.debug("Prediction snapshot save skipped")
        return val_id
    except Exception:
        logger.debug("DB save skipped (Supabase not configured or unavailable)")
        return None


def run_from_profile(
    profile_path: str, output_dir: str | None = None
) -> tuple[ValuationInput, ValuationResult, str]:
    """YAML profile -> valuation -> Excel.

    Returns:
        (input data, result, Excel path)
    """
    vi = load_profile(profile_path)
    result = run_valuation(vi)
    excel_path = export(vi, result, output_dir)
    _save_to_db(vi, result, profile_path)
    return vi, result, excel_path


def format_summary(vi: ValuationInput, result: ValuationResult) -> str:
    """Generate result summary text (for research notes / UI)."""
    lines = []
    unit = vi.company.currency_unit
    sym = "원" if vi.company.market == "KR" else "$"
    seg_names = _seg_names(vi)

    lines.append(f"# {vi.company.name} 기업가치평가 요약")
    lines.append(
        f"분석일: {vi.company.analysis_date}  |  방법론: **{result.primary_method.upper()}**"
    )
    lines.append("")

    # WACC section
    w = result.wacc
    lines.append(f"## WACC: {w.wacc}%")
    lines.append(f"- βL={w.bl}, Ke={w.ke}%, Kd(세후)={w.kd_at}%")
    lines.append("")

    # DDM (financial sector)
    if result.ddm:
        ddm = result.ddm
        lines.append("## DDM 밸류에이션")
        lines.append(
            f"- DPS: {ddm.dps:,.0f}{sym}  |  배당성장률: {ddm.growth:.2f}%  |  Ke: {ddm.ke:.2f}%"
        )
        lines.append(f"- **주당 내재가치: {ddm.equity_per_share:,}{sym}**")
        lines.append("")

    # Multiples Primary (relative valuation)
    if result.multiples_primary:
        mp = result.multiples_primary
        lines.append(f"## 상대가치평가 ({mp.primary_multiple_method})")
        lines.append(
            f"- 지표값: {mp.metric_value:,.0f}{unit}  |  배수: {mp.multiple:.1f}x"
        )
        lines.append(f"- **주당 가치: {mp.per_share:,}{sym}**")
        lines.append("")

    # NAV (net asset value)
    if result.nav:
        nv = result.nav
        lines.append("## 순자산가치(NAV)")
        lines.append(
            f"- 총자산: {nv.total_assets:,}{unit}  |  재평가: {nv.revaluation:+,}{unit}"
        )
        lines.append(
            f"- 부채: {nv.total_liabilities:,}{unit}  |  NAV: {nv.nav:,}{unit}"
        )
        lines.append(f"- **주당 NAV: {nv.per_share:,}{sym}**")
        lines.append("")

    # SOTP (if available)
    if result.sotp:
        lines.append(f"## SOTP EV: {result.total_ev:,}{unit}")
        for code, s in result.sotp.items():
            if s.ev > 0:
                if s.method == "ev_revenue":
                    _m_lbl, _m_val = "Revenue", getattr(s, "revenue", 0) or 0
                else:
                    _m_lbl, _m_val = "EBITDA", s.ebitda
                lines.append(
                    f"- {seg_names.get(code, code)}: {_m_lbl} {_m_val:,} × {s.multiple:.1f}x = {s.ev:,}{unit}"
                )
        lines.append("")

    # DCF
    if result.dcf:
        dcf = result.dcf
        lines.append(f"## DCF EV: {dcf.ev_dcf:,}{unit}")
        if result.sotp and result.total_ev > 0:
            diff = (dcf.ev_dcf - result.total_ev) / result.total_ev * 100
            lines.append(f"- SOTP 대비 {diff:+.1f}%")
        lines.append("")

    # Scenarios
    if result.scenarios:
        lines.append("## 시나리오 분석")
        for code, sc in vi.scenarios.items():
            if code in result.scenarios:
                sr = result.scenarios[code]
                lines.append(
                    f"- {sc.name} ({sc.prob}%): 주당 {sr.post_dlom:,}{sym} → 가중 {sr.weighted:,}{sym}"
                )
        lines.append(f"- **확률가중 주당 가치: {result.weighted_value:,}{sym}**")
        lines.append("")

    # Gap ratio + reverse-DCF diagnostic
    if result.market_comparison and result.market_comparison.market_price > 0:
        mc = result.market_comparison
        lines.append("## 시장가격 비교")
        lines.append(
            f"- 내재가치: {mc.intrinsic_value:,}{sym}  |  시장가: {mc.market_price:,.0f}{sym}"
        )
        lines.append(f"- 괴리율: {mc.gap_ratio:+.1%}")
        if mc.flag:
            lines.append(f"- ⚠ {mc.flag}")
        lines.append("")

    # Reverse rNPV (when primary_method == "rnpv")
    if result.reverse_rnpv:
        rv = result.reverse_rnpv
        lines.append("## 역방향 rNPV")
        lines.append(
            f"- 모델 EV: {rv.model_ev:,}{unit} → 시장 EV: {rv.target_ev:,}{unit} (괴리 {rv.gap_pct:+.1f}%)"
        )
        if rv.implied_pos_scale is not None:
            lines.append(f"- 시장 내재 PoS 배수: {rv.implied_pos_scale:.3f}x")
        if rv.implied_peak_scale is not None:
            lines.append(f"- 시장 내재 Peak Sales 배수: {rv.implied_peak_scale:.3f}x")
        if rv.implied_discount_rate is not None:
            lines.append(f"- 시장 내재 할인율: {rv.implied_discount_rate:.2f}%")
        lines.append("")

    # Reverse-DCF gap diagnostic (when |gap| >= 20%)
    if result.gap_diagnostic:
        gd = result.gap_diagnostic
        _LABELS = {
            "wacc_overestimated": "WACC 과대추정",
            "growth_underestimated": "성장률 과소추정",
            "optionality_premium": "옵셔널리티 프리미엄",
            "market_pessimism": "시장 저평가 가능성",
        }
        lines.append("## 역방향 DCF 진단")
        lines.append(f"- 진단 유형: **{_LABELS.get(gd.category, gd.category)}**")
        if gd.implied_wacc is not None:
            lines.append(f"- 시장 내재 WACC: {gd.implied_wacc:.2f}%")
        if gd.implied_tgr is not None:
            lines.append(f"- 시장 내재 TGR: {gd.implied_tgr:.2f}%")
        if gd.implied_growth_mult is not None:
            lines.append(f"- 시장 내재 성장배수: {gd.implied_growth_mult:.2f}x")
        if not gd.reconcilable:
            lines.append("- ⚠ EBITDA 기반 DCF로 시장가격 설명 불가 (옵셔널리티 구간)")
        if gd.suggestions:
            lines.append("- 권고사항:")
            for s in gd.suggestions[:3]:
                lines.append(f"  - {s}")
        lines.append("")

    # Cross-validation
    if result.cross_validations:
        lines.append("## 교차검증")
        for cv in result.cross_validations:
            lines.append(f"- {cv.method}: {cv.per_share:,}{sym}")
        lines.append("")

    return "\n".join(lines)
