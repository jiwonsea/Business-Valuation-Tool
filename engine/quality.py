"""Valuation quality scoring -- pure functions, no IO.

Computes a 0-100 composite quality score from ValuationResult data.
Inspired by autoresearch's val_bpb: a clear scalar metric after every run.
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
    "KR": {"rf": (2.5, 5.0), "erp": (4.0, 8.0), "beta": (0.3, 2.0), "kd_pre": (2.0, 10.0)},
    "US": {"rf": (3.0, 5.5), "erp": (4.0, 7.0), "beta": (0.3, 2.0), "kd_pre": (2.0, 8.0)},
}


def calc_quality_score(vi: "ValuationInput", result: "ValuationResult") -> "QualityScore":
    """Compute composite quality score (0-100) from valuation I/O."""
    from schemas.models import QualityScore

    is_listed = vi.company.legal_status in ("상장", "listed")
    market = vi.company.market

    cv_score, cv_warns = _cv_convergence_score(result.cross_validations)
    wacc_score, wacc_warns = _wacc_plausibility_score(
        result.wacc, vi.wacc_params, market
    )
    sc_score, sc_warns = _scenario_consistency_score(
        vi.scenarios, result.scenarios, result.weighted_value
    )

    warnings = cv_warns + wacc_warns + sc_warns

    if is_listed:
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
            cv.method for cv in cross_vals
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
        warnings.append(f"무위험이자율 범위 이탈 (Rf={wacc_params.rf:.1f}%, 적정 {lo}-{hi}%)")

    # Equity risk premium
    lo, hi = ranges["erp"]
    if not lo <= wacc_params.erp <= hi:
        deductions += 5
        warnings.append(f"ERP 범위 이탈 ({wacc_params.erp:.1f}%, 적정 {lo}-{hi}%)")

    # Levered beta (from result, not input unlevered)
    lo, hi = ranges["beta"]
    if not lo <= wacc_result.bl <= hi:
        deductions += 5
        warnings.append(f"레버드 베타 범위 이탈 (βL={wacc_result.bl:.2f}, 적정 {lo}-{hi})")

    # Pre-tax cost of debt
    lo, hi = ranges["kd_pre"]
    if not lo <= wacc_params.kd_pre <= hi:
        deductions += 5
        warnings.append(f"세전타인자본비용 범위 이탈 (Kd={wacc_params.kd_pre:.1f}%, 적정 {lo}-{hi}%)")

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
    weighted_mean_ps = sum(
        sr.post_dlom * scenarios_in[code].prob / total_prob
        for code, sr in scenarios_out.items()
        if code in scenarios_in and sr.post_dlom > 0
    ) if scenarios_in else statistics.mean(per_share_values)
    mean_ps = weighted_mean_ps if weighted_mean_ps > 0 else statistics.mean(per_share_values)
    deviation_pct = abs(weighted_value - mean_ps) / mean_ps * 100 if mean_ps > 0 else 0

    if deviation_pct < 20:
        dev_pts = 8
    elif deviation_pct < 40:
        dev_pts = 4
    else:
        dev_pts = 0
        warnings.append(f"가중평균과 시나리오 평균 괴리 과대 ({deviation_pct:.0f}%)")

    # (c) Spread reasonableness: 9 / 5 / 2
    spread_pct = (max(per_share_values) - min(per_share_values)) / mean_ps * 100 if mean_ps > 0 else 0

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
    suffix = "" if is_listed else " [비상장 — 3항목 기준]"
    lines.append(f"품질 점수: {quality.total}/100 ({quality.grade}){suffix}")
    lines.append(f"  - 교차검증 수렴도: {quality.cv_convergence}/25")
    lines.append(f"  - WACC 적정성: {quality.wacc_plausibility}/25")
    lines.append(f"  - 시나리오 정합성: {quality.scenario_consistency}/25")
    if is_listed:
        lines.append(f"  - 시장가격 정합: {quality.market_alignment}/25")
    for w in quality.warnings:
        lines.append(f"  ⚠ {w}")
    return "\n".join(lines)
