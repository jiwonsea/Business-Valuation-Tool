"""Valuation quality scoring -- pure functions, no IO.

Computes a 0-100 composite quality score from ValuationResult data.
Inspired by autoresearch's val_bpb: a clear scalar metric after every run.

rNPV mode (primary_method == "rnpv"):
  cv_convergence bucket (25 pts) is restructured:
    - rnpv_weighted_cv (0-10):         CV among rNPV-appropriate methods (DCF excluded)
    - rnpv_pipeline_diversity (0-8):   drug count + phase variety
    - rnpv_pos_grounding (0-6):        custom PoS coverage
    - rnpv_scenario_coverage (0-1):    pos_override in at least one scenario
  market_alignment bucket (25 pts, listed only) is restructured:
    - price gap component (0-15): same formula, rescaled
    - rnpv_reverse_consistency (0-10): reverse rNPV implied parameter sanity
"""

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schemas.models import (
        CrossValidationItem,
        MarketComparisonResult,
        QualityScore,
        ValuationInput,
        ValuationResult,
        WACCParams,
        WACCResult,
    )


# ── Market-specific WACC parameter ranges ──

_WACC_RANGES = {
    "KR": {
        "rf": (2.5, 5.0),
        "erp": (4.0, 8.0),
        "beta": (0.3, 2.0),
        "kd_pre": (2.0, 10.0),
    },
    "US": {
        "rf": (3.0, 5.5),
        "erp": (4.0, 7.0),
        "beta": (0.3, 2.0),
        "kd_pre": (2.0, 8.0),
    },
}

# Methods unsuitable for pharma pipeline convergence (EBITDA-based TV misses pipeline option value)
_RNPV_EXCLUDED_CV_METHODS = {"DCF (FCFF)"}


def calc_quality_score(
    vi: "ValuationInput", result: "ValuationResult"
) -> "QualityScore":
    """Compute composite quality score (0-100) from valuation I/O."""
    from schemas.models import QualityScore

    is_listed = vi.company.legal_status in ("상장", "listed")
    market = vi.company.market
    is_rnpv = result.primary_method == "rnpv"

    # ── Cross-validation / rNPV-specific first bucket ──
    if is_rnpv:
        wcv_score, wcv_warns = _cv_convergence_score_rnpv(result.cross_validations)
        pd_score, pd_warns = _rnpv_pipeline_diversity(vi)
        pg_score, pg_warns = _rnpv_pos_grounding(vi)
        sc_cov_score, sc_cov_warns = _rnpv_scenario_coverage(vi)
        cv_score = wcv_score + pd_score + pg_score + sc_cov_score
        cv_warns = wcv_warns + pd_warns + pg_warns + sc_cov_warns
    else:
        wcv_score = pd_score = pg_score = sc_cov_score = 0
        cv_score, cv_warns = _cv_convergence_score(result.cross_validations)

    wacc_score, wacc_warns = _wacc_plausibility_score(
        result.wacc, vi.wacc_params, market
    )
    sc_score, sc_warns = _scenario_consistency_score(
        vi.scenarios, result.scenarios, result.weighted_value
    )

    warnings = cv_warns + wacc_warns + sc_warns

    rr_score = 0
    if is_listed:
        if is_rnpv:
            ma_score, ma_warns = _market_alignment_score_rnpv(result.market_comparison)
            rr_score, rr_warns = _reverse_rnpv_consistency(result)
            ma_score = ma_score + rr_score
            warnings += ma_warns + rr_warns
        else:
            ma_score, ma_warns = _market_alignment_score(result.market_comparison)
            warnings += ma_warns
        raw_total = cv_score + wacc_score + sc_score + ma_score
        max_score = 100
        total = raw_total
    else:
        ma_score = 0
        raw_sum = cv_score + wacc_score + sc_score  # out of 75
        max_score = 75
        total = round(raw_sum * 100 / 75) if raw_sum > 0 else 0

    grade = _grade(total)

    return QualityScore(
        total=total,
        cv_convergence=cv_score,
        wacc_plausibility=wacc_score,
        scenario_consistency=sc_score,
        market_alignment=ma_score,
        max_score=max_score,
        warnings=warnings,
        grade=grade,
        is_rnpv=is_rnpv,
        rnpv_weighted_cv=wcv_score,
        rnpv_pipeline_diversity=pd_score,
        rnpv_pos_grounding=pg_score,
        rnpv_scenario_coverage=sc_cov_score,
        rnpv_reverse_consistency=rr_score,
    )


def _cv_convergence_score(
    cross_vals: list["CrossValidationItem"],
) -> tuple[int, list[str]]:
    """Score cross-validation convergence (0-25).

    Measures coefficient of variation across per-share values from different methods.
    Tighter convergence = higher confidence that the valuation is internally consistent.
    """
    warnings: list[str] = []

    values = [cv.per_share for cv in cross_vals if cv.per_share > 0]
    if len(values) < 2:
        warnings.append("교차검증 방법이 2개 미만입니다")
        return 0, warnings

    mean_raw = statistics.mean(values)
    if mean_raw <= 0:
        warnings.append("교차검증 평균 주당가치가 0 이하입니다")
        return 0, warnings

    # Filter extreme outliers (>3x or <1/3 of median) — P/E near-zero NI, P/BV distortion, etc.
    median = statistics.median(values)
    filtered = [v for v in values if median / 3 <= v <= median * 3]
    n_excluded = len(values) - len(filtered)
    if n_excluded > 0:
        excluded_methods = [
            cv.method
            for cv in cross_vals
            if cv.per_share > 0 and not (median / 3 <= cv.per_share <= median * 3)
        ]
        warnings.append(f"극단값 {n_excluded}개 제외 ({', '.join(excluded_methods)})")

    if len(filtered) < 2:
        warnings.append("극단값 제외 후 교차검증 방법이 2개 미만입니다")
        return 3, warnings

    mean = statistics.mean(filtered)
    stdev = statistics.stdev(filtered)
    cv = stdev / mean * 100  # CV in %

    if cv < 8:
        score = 25
    elif cv < 15:
        score = 20
    elif cv < 25:
        score = 14
    elif cv < 40:
        score = 8
    else:
        score = 3
        warnings.append(f"교차검증 수렴도 낮음 (CV={cv:.1f}%)")

    return score, warnings


def _cv_convergence_score_rnpv(
    cross_vals: list["CrossValidationItem"],
) -> tuple[int, list[str]]:
    """rNPV-weighted convergence score (0-10).

    Excludes DCF (FCFF) because EBITDA-based terminal value systematically
    misses pharma pipeline option value. Tighter convergence among
    rNPV-appropriate methods (EV/Revenue, P/BV, P/E) earns more points.
    """
    warnings: list[str] = []

    rnpv_cvs = [cv for cv in cross_vals if cv.method not in _RNPV_EXCLUDED_CV_METHODS]
    values = [cv.per_share for cv in rnpv_cvs if cv.per_share > 0]

    if len(values) < 2:
        warnings.append("rNPV 적합 교차검증 방법이 2개 미만 (DCF 제외 기준)")
        return 1, warnings

    median = statistics.median(values)
    filtered = [v for v in values if median / 3 <= v <= median * 3]
    if len(filtered) < 2:
        warnings.append("극단값 제외 후 rNPV 적합 교차검증 방법이 2개 미만")
        return 1, warnings

    mean = statistics.mean(filtered)
    stdev = statistics.stdev(filtered)
    cv = stdev / mean * 100  # CV in %

    if cv < 10:
        score = 10
    elif cv < 20:
        score = 8
    elif cv < 30:
        score = 5
    elif cv < 45:
        score = 2
    else:
        score = 1
        warnings.append(f"rNPV 적합 방법 수렴도 낮음 (CV={cv:.1f}%, DCF 제외 기준)")

    return score, warnings


def _rnpv_pipeline_diversity(vi: "ValuationInput") -> tuple[int, list[str]]:
    """Pipeline diversity score (0-8): drug count (0-4) + phase variety (0-4).

    More drugs and more phases = more diversified risk = higher confidence.
    """
    warnings: list[str] = []

    if not vi.rnpv_params or not vi.rnpv_params.pipeline:
        warnings.append("파이프라인 데이터 없음")
        return 0, warnings

    pipeline = vi.rnpv_params.pipeline
    drug_count = len(pipeline)
    phases = {d.phase for d in pipeline}

    # Drug count component (0-4)
    if drug_count >= 6:
        count_pts = 4
    elif drug_count >= 4:
        count_pts = 3
    elif drug_count >= 2:
        count_pts = 2
    else:
        count_pts = 1

    # Phase variety component (0-4)
    n_phases = len(phases)
    if n_phases >= 4:
        phase_pts = 4
    elif n_phases >= 3:
        phase_pts = 3
    elif n_phases >= 2:
        phase_pts = 2
    else:
        phase_pts = 1
        warnings.append(f"파이프라인 단일 Phase 집중 ({list(phases)[0]})")

    return count_pts + phase_pts, warnings


def _rnpv_pos_grounding(vi: "ValuationInput") -> tuple[int, list[str]]:
    """PoS grounding score (0-6): custom PoS coverage vs phase-default fallback.

    Analyst-set success probabilities that deviate from generic phase averages
    indicate deeper due diligence and reduce model uncertainty.
    Reduced from 0-7 to 0-6 to accommodate rnpv_scenario_coverage (0-1).
    """
    warnings: list[str] = []

    if not vi.rnpv_params or not vi.rnpv_params.pipeline:
        return 0, []

    pipeline = vi.rnpv_params.pipeline
    # Approved drugs (PoS=1.0 by definition) are excluded from grounding assessment
    non_approved = [d for d in pipeline if d.phase != "approved"]
    if not non_approved:
        # All drugs approved — PoS grounding not meaningful, give full points
        return 6, []

    custom_count = sum(1 for d in non_approved if d.success_prob is not None)
    custom_pct = custom_count / len(non_approved) * 100

    if custom_pct >= 50:
        score = 6
    elif custom_pct >= 25:
        score = 4
    elif custom_pct >= 10:
        score = 2
    else:
        score = 1
        warnings.append(
            f"PoS 커스텀 설정 부족 — 비승인 약물 {len(non_approved)}개 중 {custom_count}개만 커스텀 PoS 사용"
        )

    return score, warnings


def _rnpv_scenario_coverage(vi: "ValuationInput") -> tuple[int, list[str]]:
    """Scenario pos_override coverage (0-1): rNPV scenario risk differentiation.

    pos_override in at least one scenario means the analyst models pipeline risk
    differently across bull/bear — a hallmark of thoughtful rNPV scenario design.
    """
    warnings: list[str] = []

    has_pos_override = any(
        sc.pos_override for sc in vi.scenarios.values() if sc.pos_override
    )

    if has_pos_override:
        return 1, []

    warnings.append("시나리오 pos_override 없음 — 파이프라인 리스크 시나리오 미반영")
    return 0, warnings


def _reverse_rnpv_consistency(result: "ValuationResult") -> tuple[int, list[str]]:
    """Reverse rNPV implied parameter sanity (0-10, listed rNPV only).

    Checks whether implied PoS scale, peak-sales scale, and discount rate
    are within plausible ranges. Parameters far outside normal bounds
    suggest the model and market diverge on fundamental assumptions.
    """
    warnings: list[str] = []
    rr = result.reverse_rnpv

    if rr is None:
        return 5, []  # Neutral — not penalized for missing market data

    # Model is already very close to market — no stretch needed
    if abs(rr.gap_pct) < 10:
        return 10, []

    score = 0

    # implied_pos_scale: plausible range [0.3, 3.0]
    if rr.implied_pos_scale is not None:
        if 0.3 <= rr.implied_pos_scale <= 3.0:
            score += 3
        else:
            warnings.append(
                f"implied PoS 배수 극단값 ({rr.implied_pos_scale:.2f}×) — 시장 수렴 불가"
            )

    # implied_peak_scale: plausible range [0.3, 3.0]
    if rr.implied_peak_scale is not None:
        if 0.3 <= rr.implied_peak_scale <= 3.0:
            score += 3
        else:
            warnings.append(
                f"implied Peak Sales 배수 극단값 ({rr.implied_peak_scale:.2f}×) — 시장 수렴 불가"
            )

    # implied_discount_rate: plausible range [5, 30]%
    if rr.implied_discount_rate is not None:
        if 5.0 <= rr.implied_discount_rate <= 30.0:
            score += 4
        else:
            warnings.append(
                f"implied 할인율 극단값 ({rr.implied_discount_rate:.1f}%) — 시장 수렴 불가"
            )

    if (
        rr.implied_pos_scale is None
        and rr.implied_peak_scale is None
        and rr.implied_discount_rate is None
    ):
        return 5, ["Reverse rNPV 파라미터 수렴 실패 — 시장가격 정합 불가"]

    return score, warnings


def _wacc_plausibility_score(
    wacc_result: "WACCResult",
    wacc_params: "WACCParams",
    market: str,
) -> tuple[int, list[str]]:
    """Score WACC plausibility (0-25).

    Range-checks each WACC component against market-specific reasonable bounds.
    -5 points per out-of-range component (minimum 0).
    """
    warnings: list[str] = []
    ranges = _WACC_RANGES.get(market, _WACC_RANGES["KR"])
    deductions = 0

    # Risk-free rate
    lo, hi = ranges["rf"]
    if not lo <= wacc_params.rf <= hi:
        deductions += 5
        warnings.append(
            f"무위험이자율 범위 이탈 (Rf={wacc_params.rf:.1f}%, 적정 {lo}-{hi}%)"
        )

    # Equity risk premium
    lo, hi = ranges["erp"]
    if not lo <= wacc_params.erp <= hi:
        deductions += 5
        warnings.append(f"ERP 범위 이탈 ({wacc_params.erp:.1f}%, 적정 {lo}-{hi}%)")

    # Levered beta (from result, not input unlevered)
    lo, hi = ranges["beta"]
    if not lo <= wacc_result.bl <= hi:
        deductions += 5
        warnings.append(
            f"레버드 베타 범위 이탈 (βL={wacc_result.bl:.2f}, 적정 {lo}-{hi})"
        )

    # Pre-tax cost of debt
    lo, hi = ranges["kd_pre"]
    if not lo <= wacc_params.kd_pre <= hi:
        deductions += 5
        warnings.append(
            f"세전타인자본비용 범위 이탈 (Kd={wacc_params.kd_pre:.1f}%, 적정 {lo}-{hi}%)"
        )

    # Overall WACC sanity (final check)
    if wacc_result.wacc < 4.0 or wacc_result.wacc > 18.0:
        deductions += 5
        warnings.append(f"WACC 극단값 ({wacc_result.wacc:.1f}%, 일반적 범위 4-18%)")

    return max(25 - deductions, 0), warnings


def _scenario_consistency_score(
    scenarios_in: dict,
    scenarios_out: dict,
    weighted_value: int,
) -> tuple[int, list[str]]:
    """Score scenario design quality (0-25).

    Checks: (a) scenario count, (b) weighted vs base deviation, (c) spread reasonableness.
    """
    warnings: list[str] = []
    n_scenarios = len(scenarios_in)

    # (a) Scenario count: 8 / 4 / 0
    if n_scenarios >= 3:
        count_pts = 8
    elif n_scenarios == 2:
        count_pts = 4
    else:
        count_pts = 0
        if n_scenarios == 0:
            warnings.append("시나리오가 없습니다")
            return 0, warnings

    # Collect per-share values from scenario results (probability-weighted)
    per_share_values = []
    for sr in scenarios_out.values():
        ps = sr.post_dlom
        if ps > 0:
            per_share_values.append(ps)

    if not per_share_values or weighted_value <= 0:
        warnings.append("시나리오 결과값이 부족합니다")
        return count_pts, warnings

    # (b) Weighted vs probability-weighted mean deviation: 8 / 4 / 0
    # Use probability-weighted mean (same basis as weighted_value) for consistency
    total_prob = sum(sc.prob for sc in scenarios_in.values()) if scenarios_in else 100
    weighted_mean_ps = (
        sum(
            sr.post_dlom * scenarios_in[code].prob / total_prob
            for code, sr in scenarios_out.items()
            if code in scenarios_in and sr.post_dlom > 0
        )
        if scenarios_in
        else statistics.mean(per_share_values)
    )
    mean_ps = (
        weighted_mean_ps if weighted_mean_ps > 0 else statistics.mean(per_share_values)
    )
    deviation_pct = abs(weighted_value - mean_ps) / mean_ps * 100 if mean_ps > 0 else 0

    if deviation_pct < 20:
        dev_pts = 8
    elif deviation_pct < 40:
        dev_pts = 4
    else:
        dev_pts = 0
        warnings.append(f"가중평균과 시나리오 평균 괴리 과대 ({deviation_pct:.0f}%)")

    # (c) Spread reasonableness: 9 / 5 / 2
    spread_pct = (
        (max(per_share_values) - min(per_share_values)) / mean_ps * 100
        if mean_ps > 0
        else 0
    )

    if 5 <= spread_pct <= 200:
        spread_pts = 9
    elif spread_pct < 5:
        spread_pts = 2
        warnings.append(f"시나리오 간 편차 과소 ({spread_pct:.0f}%)")
    else:
        spread_pts = 2
        warnings.append(f"시나리오 간 편차 과대 ({spread_pct:.0f}%)")

    return count_pts + dev_pts + spread_pts, warnings


def _market_alignment_score(
    mc: "MarketComparisonResult | None",
) -> tuple[int, list[str]]:
    """Score market price alignment (0-25, listed only).

    Lower gap_ratio = higher confidence. Unlisted companies should NOT call this.
    """
    warnings: list[str] = []

    if mc is None or mc.market_price <= 0:
        warnings.append("시장가격 비교 데이터 없음")
        return 0, warnings

    gap = abs(mc.gap_ratio * 100)  # gap_ratio is decimal (e.g. 0.35 = 35%)

    if gap < 15:
        score = 25
    elif gap < 25:
        score = 20
    elif gap < 40:
        score = 14
    elif gap < 60:
        score = 8
    else:
        score = 3
        warnings.append(f"시장가격 괴리율 과대 ({gap:.0f}%)")
        # Extreme undervaluation relative to market (>3x): likely optionality-driven premium
        if mc.gap_ratio < -0.66:  # intrinsic < 1/3 of market price
            warnings.append(
                "⚠ 내재가치가 시장가의 1/3 미만: 시장은 현재 EBITDA에 반영되지 않은 "
                "AI/플랫폼/신사업 옵셔널리티 프리미엄을 부여하고 있을 가능성이 높습니다. "
                "DCF/SOTP 결과를 액면 그대로 투자 판단에 사용하지 마세요."
            )

    return score, warnings


def _market_alignment_score_rnpv(
    mc: "MarketComparisonResult | None",
) -> tuple[int, list[str]]:
    """Price gap component of market alignment for rNPV (0-15).

    Same thresholds as _market_alignment_score but rescaled to 15 pts,
    leaving 10 pts for reverse rNPV consistency.
    """
    warnings: list[str] = []

    if mc is None or mc.market_price <= 0:
        warnings.append("시장가격 비교 데이터 없음")
        return 0, warnings

    gap = abs(mc.gap_ratio * 100)

    if gap < 15:
        score = 15
    elif gap < 25:
        score = 12
    elif gap < 40:
        score = 8
    elif gap < 60:
        score = 4
    else:
        score = 1
        warnings.append(f"시장가격 괴리율 과대 ({gap:.0f}%)")
        if mc.gap_ratio < -0.66:
            warnings.append(
                "⚠ 내재가치가 시장가의 1/3 미만: 시장은 현재 rNPV에 반영되지 않은 "
                "파이프라인 옵셔널리티 프리미엄을 부여하고 있을 가능성이 높습니다."
            )

    return score, warnings


def _grade(total: int) -> str:
    """Map total score (0-100) to letter grade."""
    if total >= 85:
        return "A"
    elif total >= 70:
        return "B"
    elif total >= 55:
        return "C"
    elif total >= 40:
        return "D"
    else:
        return "F"


def format_quality_report(quality: "QualityScore", is_listed: bool) -> str:
    """Format quality score as Korean console output."""
    lines = []

    if quality.is_rnpv:
        suffix = " [rNPV 기준]"
    elif not is_listed:
        suffix = " [비상장 — 3항목 기준]"
    else:
        suffix = ""

    lines.append(f"품질 점수: {quality.total}/100 ({quality.grade}){suffix}")

    if quality.is_rnpv:
        lines.append(f"  - 교차검증 (rNPV 기준): {quality.cv_convergence}/25")
        lines.append(f"      · 방법론 수렴도 (DCF 제외): {quality.rnpv_weighted_cv}/10")
        lines.append(f"      · 파이프라인 다양성: {quality.rnpv_pipeline_diversity}/8")
        lines.append(f"      · PoS 그라운딩: {quality.rnpv_pos_grounding}/6")
        lines.append(f"      · 시나리오 커버리지: {quality.rnpv_scenario_coverage}/1")
    else:
        lines.append(f"  - 교차검증 수렴도: {quality.cv_convergence}/25")

    lines.append(f"  - WACC 적정성: {quality.wacc_plausibility}/25")
    lines.append(f"  - 시나리오 정합성: {quality.scenario_consistency}/25")

    if is_listed:
        if quality.is_rnpv:
            lines.append(f"  - 시장가격 정합 [rNPV]: {quality.market_alignment}/25")
            price_component = (
                quality.market_alignment - quality.rnpv_reverse_consistency
            )
            lines.append(f"      · 가격 괴리: {price_component}/15")
            lines.append(
                f"      · Reverse rNPV 정합: {quality.rnpv_reverse_consistency}/10"
            )
        else:
            lines.append(f"  - 시장가격 정합: {quality.market_alignment}/25")

    for w in quality.warnings:
        lines.append(f"  ⚠ {w}")

    return "\n".join(lines)
