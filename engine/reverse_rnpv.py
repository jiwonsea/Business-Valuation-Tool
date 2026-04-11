"""Reverse rNPV — given a target EV (market price), solve for implied parameters.

Three solver modes:
  1. **Implied PoS scale**: uniform multiplier on all pipeline PoS values that
     reconciles rNPV enterprise value with market EV.
  2. **Implied peak-sales scale**: uniform multiplier on all peak_sales that
     reconciles rNPV enterprise value with market EV.
  3. **Per-drug solo PoS**: for each non-approved drug independently, what PoS
     would close the gap alone? Uses direct algebraic solve (O(1) per drug)
     since rNPV is linear in each drug's PoS.

Modes 1-2 use binary search on the monotone relationship between the parameter
and enterprise value. Mode 3 exploits linearity: EV = base_ev + npv_i × (pos_i - current_pos_i).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.rnpv import calc_rnpv

_TOLERANCE = 1e-4
_MAX_ITER = 60

# Bounds
_POS_SCALE_LO, _POS_SCALE_HI = 0.1, 5.0      # 10% to 500% of base PoS
_PEAK_SCALE_LO, _PEAK_SCALE_HI = 0.1, 5.0     # 10% to 500% of base peak sales
_DISCOUNT_LO, _DISCOUNT_HI = 1.0, 25.0         # 1% to 25% discount rate


@dataclass
class ReverseRNPVResult:
    """Result of reverse rNPV analysis."""
    target_ev: int                   # Market EV we're trying to match ($M)
    model_ev: int                    # Model rNPV enterprise value ($M)
    gap_pct: float                   # (model_ev - target_ev) / target_ev * 100

    # Implied parameters (None = solver couldn't find solution in bounds)
    implied_pos_scale: float | None = None       # Multiplier on all PoS
    implied_peak_scale: float | None = None      # Multiplier on all peak_sales
    implied_discount_rate: float | None = None   # Discount rate (%) that reconciles

    # Per-drug implied PoS at the solved scale (for reporting)
    implied_pos_per_drug: list[dict] = field(default_factory=list)
    # Per-drug implied peak_sales at the solved scale
    implied_peak_per_drug: list[dict] = field(default_factory=list)
    # Per-drug independent PoS (linear solve, each drug solved in isolation)
    implied_pos_solo: list[dict] = field(default_factory=list)


def _binary_search(f, lo: float, hi: float, target: float) -> float | None:
    """Binary search for x in [lo, hi] where f(x) ≈ target (monotone f)."""
    f_lo = f(lo)
    f_hi = f(hi)

    # Determine direction
    increasing = f_lo < f_hi

    if increasing:
        if target < f_lo or target > f_hi:
            return None
    else:
        if target < f_hi or target > f_lo:
            return None

    for _ in range(_MAX_ITER):
        mid = (lo + hi) / 2
        f_mid = f(mid)
        if abs(f_mid - target) / max(abs(target), 1e-6) < _TOLERANCE:
            return mid
        if (f_mid < target) == increasing:
            lo = mid
        else:
            hi = mid

    return (lo + hi) / 2  # Return best estimate if not converged


def _eval_rnpv_ev(
    pipeline: list[dict],
    discount_rate: float,
    r_and_d_cost: int,
    decline_rate: float,
    default_margin: float,
    tax_rate: float,
) -> float:
    """Evaluate rNPV enterprise value for given pipeline parameters."""
    result = calc_rnpv(
        pipeline=pipeline,
        discount_rate=discount_rate,
        r_and_d_cost=r_and_d_cost,
        decline_rate=decline_rate,
        default_margin=default_margin,
        tax_rate=tax_rate,
    )
    return float(result.enterprise_value)


def solve_implied_pos_scale(
    target_ev: float,
    pipeline: list[dict],
    discount_rate: float,
    r_and_d_cost: int = 0,
    decline_rate: float = 20.0,
    default_margin: float = 0.35,
    tax_rate: float = 0.22,
) -> float | None:
    """Find uniform PoS scale factor k such that rNPV EV(PoS × k) == target_ev.

    Each drug's PoS is multiplied by k, capped at 1.0.
    rNPV EV is monotone-increasing in k.
    """
    from engine.rnpv import PHASE_POS

    def f(scale: float) -> float:
        adj = []
        for d in pipeline:
            ad = dict(d)
            base_pos = d.get("success_prob") or PHASE_POS.get(d.get("phase", "preclinical"), 0.10)
            ad["success_prob"] = min(base_pos * scale, 1.0)
            adj.append(ad)
        return _eval_rnpv_ev(adj, discount_rate, r_and_d_cost, decline_rate, default_margin, tax_rate)

    return _binary_search(f, _POS_SCALE_LO, _POS_SCALE_HI, target_ev)


def solve_implied_peak_scale(
    target_ev: float,
    pipeline: list[dict],
    discount_rate: float,
    r_and_d_cost: int = 0,
    decline_rate: float = 20.0,
    default_margin: float = 0.35,
    tax_rate: float = 0.22,
) -> float | None:
    """Find uniform peak-sales scale k such that rNPV EV(peak × k) == target_ev.

    Each drug's peak_sales and existing_revenue are multiplied by k.
    rNPV EV is monotone-increasing in k.
    """
    def f(scale: float) -> float:
        adj = []
        for d in pipeline:
            ad = dict(d)
            ad["peak_sales"] = round(d.get("peak_sales", 0) * scale)
            if d.get("existing_revenue", 0) > 0:
                ad["existing_revenue"] = round(d["existing_revenue"] * scale)
            adj.append(ad)
        return _eval_rnpv_ev(adj, discount_rate, r_and_d_cost, decline_rate, default_margin, tax_rate)

    return _binary_search(f, _PEAK_SCALE_LO, _PEAK_SCALE_HI, target_ev)


def solve_implied_discount_rate(
    target_ev: float,
    pipeline: list[dict],
    r_and_d_cost: int = 0,
    decline_rate: float = 20.0,
    default_margin: float = 0.35,
    tax_rate: float = 0.22,
) -> float | None:
    """Find discount rate (%) such that rNPV EV == target_ev.

    rNPV EV is monotone-decreasing in discount rate.
    """
    def f(dr: float) -> float:
        return _eval_rnpv_ev(pipeline, dr, r_and_d_cost, decline_rate, default_margin, tax_rate)

    return _binary_search(f, _DISCOUNT_LO, _DISCOUNT_HI, target_ev)


def solve_implied_per_drug_pos(
    target_ev: float,
    pipeline: list[dict],
    discount_rate: float,
    r_and_d_cost: int = 0,
    decline_rate: float = 20.0,
    default_margin: float = 0.35,
    tax_rate: float = 0.22,
) -> list[dict]:
    """Solve each drug's independent implied PoS via direct algebra.

    For each non-approved drug, answers: "What PoS would this drug need
    alone to close the model-market gap (all other drugs at base PoS)?"

    rNPV is linear in each drug's PoS:
        EV(pos_i) = base_ev + npv_i × (pos_i - current_pos_i)
        implied_pos_i = (target_ev - base_ev) / npv_i + current_pos_i

    Only 1 call to calc_rnpv needed (O(1) total).

    Returns list of dicts with keys:
        name, phase, base_pos, implied_pos (None if unsolvable),
        solvable, max_ev_contribution, skipped.
    """
    from engine.rnpv import PHASE_POS

    if target_ev <= 0:
        return []

    base_result = calc_rnpv(
        pipeline=pipeline,
        discount_rate=discount_rate,
        r_and_d_cost=r_and_d_cost,
        decline_rate=decline_rate,
        default_margin=default_margin,
        tax_rate=tax_rate,
    )
    base_ev = float(base_result.enterprise_value)
    gap = target_ev - base_ev

    results = []
    for dr in base_result.drug_results:
        base_pos = dr.success_prob
        npv_i = dr.npv  # Unadjusted NPV (before PoS)

        # Skip drugs already at PoS >= 1.0 (no room to adjust upward,
        # and reducing them changes the "approved" semantics)
        if base_pos >= 1.0:
            results.append({
                "name": dr.name,
                "phase": dr.phase,
                "base_pos": base_pos,
                "implied_pos": None,
                "solvable": False,
                "max_ev_contribution": 0,
                "skipped": True,
            })
            continue

        # Max marginal EV contribution: what if this drug had PoS=1.0?
        max_contribution = round(npv_i * (1.0 - base_pos))

        # Drug with zero NPV contributes nothing regardless of PoS
        if npv_i == 0:
            results.append({
                "name": dr.name,
                "phase": dr.phase,
                "base_pos": base_pos,
                "implied_pos": None,
                "solvable": False,
                "max_ev_contribution": 0,
                "skipped": False,
            })
            continue

        # Linear solve: implied_pos = gap / npv_i + current_pos
        implied_pos = gap / npv_i + base_pos
        solvable = 0.0 <= implied_pos <= 1.0

        results.append({
            "name": dr.name,
            "phase": dr.phase,
            "base_pos": base_pos,
            "implied_pos": round(implied_pos, 4) if solvable else None,
            "solvable": solvable,
            "max_ev_contribution": max_contribution,
            "skipped": False,
        })

    return results


def reverse_rnpv(
    target_ev: float,
    model_ev: float,
    pipeline: list[dict],
    discount_rate: float,
    r_and_d_cost: int = 0,
    decline_rate: float = 20.0,
    default_margin: float = 0.35,
    tax_rate: float = 0.22,
) -> ReverseRNPVResult:
    """Run full reverse rNPV analysis.

    Solves for implied PoS scale, implied peak-sales scale, and implied
    discount rate that would make the model EV equal target_ev.

    Args:
        target_ev: Market enterprise value (display units, e.g. $M).
        model_ev: Current model rNPV enterprise value.
        pipeline: List of drug dicts (same format as calc_rnpv input).
        discount_rate: Current discount rate (%).
        r_and_d_cost: Annual R&D cost.
        decline_rate: Post-patent decline rate (%).
        default_margin: Default operating margin.
        tax_rate: Corporate tax rate.
    """
    from engine.rnpv import PHASE_POS

    gap_pct = (model_ev - target_ev) / target_ev * 100 if target_ev else 0

    kwargs = dict(
        r_and_d_cost=r_and_d_cost,
        decline_rate=decline_rate,
        default_margin=default_margin,
        tax_rate=tax_rate,
    )

    # 1. Implied PoS scale
    pos_scale = solve_implied_pos_scale(
        target_ev, pipeline, discount_rate, **kwargs,
    )

    # 2. Implied peak-sales scale
    peak_scale = solve_implied_peak_scale(
        target_ev, pipeline, discount_rate, **kwargs,
    )

    # 3. Implied discount rate
    impl_dr = solve_implied_discount_rate(
        target_ev, pipeline, **kwargs,
    )

    # Build per-drug implied PoS
    implied_pos_drugs = []
    if pos_scale is not None:
        for d in pipeline:
            base_pos = d.get("success_prob") or PHASE_POS.get(d.get("phase", "preclinical"), 0.10)
            implied_pos_drugs.append({
                "name": d["name"],
                "base_pos": base_pos,
                "implied_pos": min(base_pos * pos_scale, 1.0),
            })

    # Build per-drug implied peak sales
    implied_peak_drugs = []
    if peak_scale is not None:
        for d in pipeline:
            implied_peak_drugs.append({
                "name": d["name"],
                "base_peak": d.get("peak_sales", 0),
                "implied_peak": round(d.get("peak_sales", 0) * peak_scale),
            })

    # 4. Per-drug independent PoS (linear solve, O(1))
    implied_pos_solo = solve_implied_per_drug_pos(
        target_ev, pipeline, discount_rate, **kwargs,
    )

    return ReverseRNPVResult(
        target_ev=round(target_ev),
        model_ev=round(model_ev),
        gap_pct=round(gap_pct, 1),
        implied_pos_scale=round(pos_scale, 3) if pos_scale is not None else None,
        implied_peak_scale=round(peak_scale, 3) if peak_scale is not None else None,
        implied_discount_rate=round(impl_dr, 2) if impl_dr is not None else None,
        implied_pos_per_drug=implied_pos_drugs,
        implied_peak_per_drug=implied_peak_drugs,
        implied_pos_solo=implied_pos_solo,
    )
