"""Scenario shift of the one discount rate a valuation method consumes."""

import math

from schemas.models import DiscountShift, RateKind


def effective_discount_rate(
    base_rate: float, adj: float, rate_kind: RateKind
) -> tuple[float, DiscountShift]:
    """Add a scenario's `wacc_adj` (%p) to the Base rate and record the move.

    The rate is the one the method discounts with: WACC for DCF (any distress
    premium is already inside the Base WACC), cost of equity for DDM/RIM, the
    pipeline discount rate for rNPV. Nothing is rounded, so a zero adjustment
    returns the Base rate itself. The +-3.0 range is checked on ScenarioParams.
    """
    if not math.isfinite(adj):
        raise ValueError(f"Discount-rate adjustment must be finite: {adj}")
    applied = base_rate + adj
    return applied, DiscountShift(
        rate_kind=rate_kind, base_rate=base_rate, adj=adj, applied_rate=applied
    )
