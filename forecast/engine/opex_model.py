"""SG&A / R&D / D&A projection helpers.

For MVP these are simple % of revenue. R&D scales with capex via 5Y straight-line lag.
D&A is implicit in GP margin already, so this module currently focuses on operating cost
checks and sanity caps.
"""

from __future__ import annotations

from schemas.models import MarginAssumptions, QuarterlyForecast


def sanity_check_opex(
    forecast: list[QuarterlyForecast],
    assumptions: MarginAssumptions,
    tolerance: float = 0.02,
) -> list[str]:
    """Return warning strings if implied SG&A / R&D drifts from assumption by > tolerance.

    Used for cross-checking that margin_model output is internally consistent.
    Mirrors margin_model's opex path: fixed + variable split when configured
    (PLAN_opex_model.md), else the constant (sga + rnd) % of revenue.

    Args:
        forecast: Margin-populated forecast.
        assumptions: Expected ratios.
        tolerance: Acceptable deviation (default 2pp).

    Returns:
        List of human-readable warnings. Empty list = clean.
    """
    warnings: list[str] = []
    for quarter in forecast:
        if assumptions.opex_fixed_krw_bn is not None and quarter.revenue_total > 0:
            expected_spread = (
                assumptions.opex_fixed_krw_bn / quarter.revenue_total
                + assumptions.opex_variable_pct_of_revenue
            )
        else:
            expected_spread = assumptions.sga_pct_of_revenue + assumptions.rnd_pct_of_revenue
        implied_spread = quarter.gp_margin - quarter.op_margin
        if abs(implied_spread - expected_spread) > tolerance:
            warnings.append(
                f"{quarter.quarter_label}: implied opex spread {implied_spread:.4f} "
                f"differs from assumption {expected_spread:.4f}"
            )
    return warnings
