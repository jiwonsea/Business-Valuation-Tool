"""Market-intrinsic gap diagnostics via reverse DCF.

When |gap_ratio| >= GAP_THRESHOLD (default 20%), this module:
  1. Solves for the implied WACC, implied TGR, and implied growth multiplier
     that would make DCF intrinsic value equal to market price.
  2. Categorizes the gap into one of four archetypes.
  3. Returns a structured GapDiagnostic with actionable suggestions.

This is called from valuation_runner after market_comparison is computed.
Results are stored in ValuationResult.gap_diagnostic and surfaced in console/Excel/email.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schemas.models import DCFParams


GAP_THRESHOLD = 0.20  # 20%: trigger diagnostics above this |gap_ratio|

# Bounds for binary-search solvers
_WACC_LO, _WACC_HI = 2.0, 25.0  # %
_TGR_LO, _TGR_HI = 0.0, 5.0  # % (TGR < WACC enforced inside solver)
_GMULT_LO, _GMULT_HI = 0.3, 8.0  # multiplier applied to every growth rate
_TOLERANCE = 1e-4  # convergence (relative EV error)
_MAX_ITER = 60


@dataclass
class GapDiagnostic:
    """Structured gap analysis result."""

    gap_pct: float  # (intrinsic - market) / market * 100  (negative = market premium)
    direction: str  # "market_premium" | "market_discount"

    # Reverse-DCF implied parameters
    implied_wacc: float | None = None  # % that reconciles with market price
    implied_tgr: float | None = None  # % that reconciles with market price
    implied_growth_mult: float | None = None  # multiplier on all growth rates

    # Diagnosis
    category: str = ""  # see _CATEGORIES below
    explanation: str = ""  # Korean explanation for console/email
    suggestions: list[str] = field(default_factory=list)  # actionable YAML edits

    # Feasibility flag
    reconcilable: bool = (
        True  # False = even max assumptions can't bridge gap (optionality)
    )


# ── Gap Category Definitions ──────────────────────────────────────────────────

_CATEGORIES = {
    "wacc_overestimated": {
        "label": "WACC 과대추정",
        "explanation": (
            "시장이 내재한 할인율이 모델 WACC보다 {delta:.1f}%p 낮습니다. "
            "리스크 프리미엄 또는 베타를 재검토하세요."
        ),
    },
    "growth_underestimated": {
        "label": "성장률 과소추정",
        "explanation": (
            "시장 가격을 설명하려면 성장률을 {mult:.1f}배 상향하거나 "
            "TGR을 {tgr:.1f}%까지 높여야 합니다. "
            "컨센서스 성장률 또는 신규 사업 파이프라인을 반영하세요."
        ),
    },
    "optionality_premium": {
        "label": "옵셔널리티 프리미엄",
        "explanation": (
            "WACC, TGR, 성장률을 극단까지 조정해도 시장가격({gap_pct:.0f}% 프리미엄)을 "
            "설명할 수 없습니다. 현재 EBITDA에 미반영된 AI·플랫폼·신사업 옵셔널리티가 "
            "존재할 가능성이 높습니다. DCF 결과를 투자 판단에 직접 사용하지 마세요."
        ),
    },
    "market_pessimism": {
        "label": "시장 저평가 가능성",
        "explanation": (
            "내재가치가 시장가보다 {gap_pct:.0f}% 높습니다. "
            "시장이 실적 회복 가능성을 낮게 보거나 유동성 리스크를 반영하고 있을 수 있습니다. "
            "성장 가정과 시장 컨센서스를 교차 검증하세요."
        ),
    },
    "minor_gap": {
        "label": "소폭 괴리",
        "explanation": "괴리율이 20% 미만으로 모델 정밀도 범위 내입니다.",
    },
}


# ── Reverse-DCF Solvers ───────────────────────────────────────────────────────


def _eval_dcf_ev(
    ebitda_base: int,
    da_base: int,
    revenue_base: int,
    wacc_pct: float,
    params: "DCFParams",
) -> float:
    """Return DCF EV (display units) for given parameters."""
    from engine.dcf import calc_dcf

    result = calc_dcf(
        ebitda_base=ebitda_base,
        da_base=da_base,
        revenue_base=revenue_base,
        wacc_pct=wacc_pct,
        params=params,
    )
    return float(result.ev_dcf)


def _binary_search(
    f, lo: float, hi: float, target: float, tol: float = _TOLERANCE
) -> float | None:
    """Binary search for x in [lo, hi] where f(x) == target (monotone f).

    Returns None if the target is outside [f(hi), f(lo)].
    """
    f_lo = f(lo)
    f_hi = f(hi)

    # Determine monotone direction
    if f_lo < f_hi:
        # f is increasing: check target in range
        if not (f_lo <= target <= f_hi):
            return None
        for _ in range(_MAX_ITER):
            mid = (lo + hi) / 2
            f_mid = f(mid)
            if abs(f_mid - target) / max(abs(target), 1e-6) < tol:
                return mid
            if f_mid < target:
                lo = mid
            else:
                hi = mid
    else:
        # f is decreasing: check target in range
        if not (f_hi <= target <= f_lo):
            return None
        for _ in range(_MAX_ITER):
            mid = (lo + hi) / 2
            f_mid = f(mid)
            if abs(f_mid - target) / max(abs(target), 1e-6) < tol:
                return mid
            if f_mid > target:
                lo = mid
            else:
                hi = mid
    return None  # Did not converge within max iterations


def solve_implied_wacc(
    target_ev: float,
    ebitda_base: int,
    da_base: int,
    revenue_base: int,
    params: "DCFParams",
) -> float | None:
    """Find WACC (%) such that DCF EV == target_ev.

    DCF EV is monotone-decreasing in WACC, so we binary-search [lo, hi].
    Lower bound is max(TGR + 0.5, 2.0) to satisfy Gordon Growth precondition.
    Returns None if target is not reachable within WACC bounds.
    """
    # WACC must exceed TGR to keep Gordon Growth finite
    lo = max(params.terminal_growth + 0.5, _WACC_LO)

    def f(wacc: float) -> float:
        try:
            return _eval_dcf_ev(ebitda_base, da_base, revenue_base, wacc, params)
        except (ValueError, ZeroDivisionError) as e:
            logger.warning(
                "solve_implied_wacc: DCF eval failed at wacc=%.2f: %s", wacc, e
            )
            return 0.0

    return _binary_search(f, lo=lo, hi=_WACC_HI, target=target_ev)


def solve_implied_tgr(
    target_ev: float,
    ebitda_base: int,
    da_base: int,
    revenue_base: int,
    wacc_pct: float,
    params: "DCFParams",
) -> float | None:
    """Find terminal growth rate (%) such that DCF EV == target_ev.

    EV is monotone-increasing in TGR (higher TGR -> higher terminal value).
    TGR is capped at wacc_pct - 0.5 to keep Gordon Growth finite.
    Also capped at _TGR_HI (5%) — beyond this is economically implausible.
    """
    tgr_hi = min(_TGR_HI, wacc_pct - 0.5)
    if tgr_hi <= _TGR_LO:
        return None

    def f(tgr: float) -> float:
        p = params.model_copy(update={"terminal_growth": tgr})
        try:
            return _eval_dcf_ev(ebitda_base, da_base, revenue_base, wacc_pct, p)
        except (ValueError, ZeroDivisionError) as e:
            logger.warning("solve_implied_tgr: DCF eval failed at tgr=%.2f: %s", tgr, e)
            return 0.0

    return _binary_search(f, lo=_TGR_LO, hi=tgr_hi, target=target_ev)


def solve_implied_growth_multiplier(
    target_ev: float,
    ebitda_base: int,
    da_base: int,
    revenue_base: int,
    wacc_pct: float,
    params: "DCFParams",
) -> float | None:
    """Find multiplier k such that DCF EV(rates * k) == target_ev.

    EV is monotone-increasing in k.
    """
    base_rates = params.ebitda_growth_rates or []
    if not base_rates:
        return None

    def f(mult: float) -> float:
        new_rates = [max(r * mult, -0.5) for r in base_rates]
        p = params.model_copy(update={"ebitda_growth_rates": new_rates})
        try:
            return _eval_dcf_ev(ebitda_base, da_base, revenue_base, wacc_pct, p)
        except (ValueError, ZeroDivisionError) as e:
            logger.warning(
                "solve_implied_growth: DCF eval failed at mult=%.2f: %s", mult, e
            )
            return 0.0

    return _binary_search(f, lo=_GMULT_LO, hi=_GMULT_HI, target=target_ev)


# ── Main Diagnostic Function ──────────────────────────────────────────────────


def diagnose_gap(
    gap_ratio: float,
    market_price: float,
    intrinsic_per_share: int,
    market_ev: float,
    ebitda_base: int,
    da_base: int,
    revenue_base: int,
    wacc_pct: float,
    params: "DCFParams",
) -> GapDiagnostic | None:
    """Run reverse-DCF diagnostics and return GapDiagnostic.

    Args:
        gap_ratio: (intrinsic - market) / market  (from MarketComparisonResult)
        market_price: Current market price per share
        intrinsic_per_share: Model intrinsic value per share
        market_ev: Target enterprise value (market cap + net debt, display units)
        ebitda_base, da_base, revenue_base: Latest-year financials
        wacc_pct: Current WACC (%)
        params: Current DCFParams

    Returns:
        GapDiagnostic or None if gap < threshold or EBITDA <= 0.
    """
    if abs(gap_ratio) < GAP_THRESHOLD:
        return None
    if ebitda_base <= 0:
        return None

    gap_pct = gap_ratio * 100
    direction = "market_premium" if gap_ratio < 0 else "market_discount"

    diag = GapDiagnostic(gap_pct=gap_pct, direction=direction)

    if direction == "market_premium":
        # Market > intrinsic: solve for parameters that bridge gap upward
        impl_wacc = solve_implied_wacc(
            target_ev=market_ev,
            ebitda_base=ebitda_base,
            da_base=da_base,
            revenue_base=revenue_base,
            params=params,
        )
        impl_tgr = solve_implied_tgr(
            target_ev=market_ev,
            ebitda_base=ebitda_base,
            da_base=da_base,
            revenue_base=revenue_base,
            wacc_pct=wacc_pct,
            params=params,
        )
        impl_gmult = solve_implied_growth_multiplier(
            target_ev=market_ev,
            ebitda_base=ebitda_base,
            da_base=da_base,
            revenue_base=revenue_base,
            wacc_pct=wacc_pct,
            params=params,
        )

        diag.implied_wacc = round(impl_wacc, 2) if impl_wacc is not None else None
        diag.implied_tgr = round(impl_tgr, 2) if impl_tgr is not None else None
        diag.implied_growth_mult = (
            round(impl_gmult, 2) if impl_gmult is not None else None
        )

        # Categorize
        wacc_delta = wacc_pct - (impl_wacc or wacc_pct)

        if impl_wacc is None and impl_tgr is None and impl_gmult is None:
            # Nothing in range can explain the gap
            diag.category = "optionality_premium"
            diag.reconcilable = False
            diag.explanation = _CATEGORIES["optionality_premium"]["explanation"].format(
                gap_pct=abs(gap_pct)
            )
            diag.suggestions = [
                "EBITDA 기반 DCF로는 설명 불가한 프리미엄 — 모델 결과를 단독 투자 판단에 사용 금지",
                "옵셔널리티 자산(AI 제품, 플랫폼 MAU, 파이프라인 NPV)의 별도 SOTP 추가 검토",
                "시장 컨센서스 TP와 당사 내재가치의 차이를 투자 메모에 명시",
            ]

        elif impl_wacc is not None and wacc_delta >= 2.0:
            # WACC needs to drop significantly to reconcile
            diag.category = "wacc_overestimated"
            diag.explanation = _CATEGORIES["wacc_overestimated"]["explanation"].format(
                delta=wacc_delta
            )
            diag.suggestions = [
                f"wacc_params 검토: 현재 WACC={wacc_pct:.1f}%, 시장 내재 WACC≈{impl_wacc:.1f}%",
                "베타(bu) 또는 ERP를 업계 컨센서스와 비교해 재보정",
                f"또는 TGR을 현재보다 높게 설정 (시장 내재 TGR≈{impl_tgr:.1f}%"
                if impl_tgr
                else "",
            ]
            diag.suggestions = [s for s in diag.suggestions if s]

        elif impl_tgr is not None and impl_tgr >= 4.0:
            # TGR needs to be very high
            diag.category = "optionality_premium"
            diag.reconcilable = False
            diag.explanation = _CATEGORIES["optionality_premium"]["explanation"].format(
                gap_pct=abs(gap_pct)
            )
            diag.suggestions = [
                f"시장 내재 TGR={impl_tgr:.1f}%는 장기 GDP 성장률 상한 초과 — 단순 DCF로 설명 불가",
                "신규 사업/플랫폼 등 EBITDA 외 가치 창출 원천을 별도 평가 필요",
                "역방향 DCF 결과를 투자 메모에 명시하여 시장 기대치 시각화",
            ]

        elif impl_gmult is not None and impl_gmult >= 1.5:
            # Growth needs to be boosted substantially
            diag.category = "growth_underestimated"
            diag.explanation = _CATEGORIES["growth_underestimated"][
                "explanation"
            ].format(mult=impl_gmult, tgr=impl_tgr if impl_tgr is not None else 0)
            diag.suggestions = [
                f"성장률 재검토 필요: 시장 내재 성장배수={impl_gmult:.1f}x",
                "컨센서스 매출 성장률(Bloomberg/FactSet) 반영 고려",
                f"dcf_params.ebitda_growth_rates를 현재 대비 ~{(impl_gmult - 1) * 100:.0f}% 상향 검토",
                "또는 신시장 진입·M&A 효과를 시나리오 growth_adj_pct에 반영",
            ]

        else:
            # Moderate gap, some combination works
            diag.category = "growth_underestimated"
            diag.explanation = _CATEGORIES["growth_underestimated"][
                "explanation"
            ].format(mult=impl_gmult or 1.0, tgr=impl_tgr or 0)
            diag.suggestions = [
                "성장률 소폭 상향 또는 WACC 재검토로 괴리 해소 가능",
                f"시장 내재 WACC≈{impl_wacc:.1f}%" if impl_wacc else "",
                f"시장 내재 TGR≈{impl_tgr:.1f}%" if impl_tgr else "",
            ]
            diag.suggestions = [s for s in diag.suggestions if s]

    else:
        # direction == "market_discount": intrinsic > market
        diag.category = "market_pessimism"
        diag.explanation = _CATEGORIES["market_pessimism"]["explanation"].format(
            gap_pct=abs(gap_pct)
        )
        # For market discount: find what WACC would explain market (higher WACC → lower EV)
        impl_wacc = solve_implied_wacc(
            target_ev=market_ev,
            ebitda_base=ebitda_base,
            da_base=da_base,
            revenue_base=revenue_base,
            params=params,
        )
        diag.implied_wacc = round(impl_wacc, 2) if impl_wacc is not None else None
        diag.suggestions = [
            f"시장 내재 WACC≈{impl_wacc:.1f}% (모델 WACC={wacc_pct:.1f}%보다 높음)"
            if impl_wacc
            else "시장이 추가 리스크 프리미엄 반영 중",
            "시장 컨센서스 대비 성장가정이 지나치게 낙관적인지 점검",
            "유동성 리스크, 지배구조 이슈, 업황 악화 시나리오 반영 여부 확인",
        ]
        diag.suggestions = [s for s in diag.suggestions if s]

    return diag


def format_gap_diagnostic(diag: GapDiagnostic, is_listed: bool = True) -> str:
    """Format GapDiagnostic as Korean console output."""
    if not is_listed:
        return ""

    lines = []
    dir_label = (
        "시장가 프리미엄" if diag.direction == "market_premium" else "내재가치 프리미엄"
    )
    lines.append(f"\n[역방향 DCF 진단] 괴리율 {abs(diag.gap_pct):.1f}% ({dir_label})")
    lines.append(
        f"  진단: {_CATEGORIES.get(diag.category, {}).get('label', diag.category)}"
    )

    if diag.implied_wacc is not None:
        lines.append(f"  시장 내재 WACC : {diag.implied_wacc:.2f}%")
    if diag.implied_tgr is not None:
        lines.append(f"  시장 내재 TGR  : {diag.implied_tgr:.2f}%")
    if diag.implied_growth_mult is not None:
        lines.append(f"  시장 내재 성장배수: {diag.implied_growth_mult:.2f}x")

    if not diag.reconcilable:
        lines.append("  ⚠ EBITDA 기반 DCF로 시장가격 설명 불가 (옵셔널리티 구간)")

    lines.append(f"\n  {diag.explanation}")

    if diag.suggestions:
        lines.append("\n  [권고사항]")
        for s in diag.suggestions:
            lines.append(f"    • {s}")

    return "\n".join(lines)
