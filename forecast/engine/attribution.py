"""EPS-error driver attribution (diagnostic, pure).

Decomposes one quarter's model-vs-actual EPS error into additive contributions
from five sequential levers, using a realized-ratio bridge:

    EPS = revenue × (GP/revenue) × (OP/GP) × (NI/OP) × (1e9/shares)
        = revenue × gross_margin × opex_conv × taxfin_conv × (1e9/shares)

Substituting model→actual one lever at a time (revenue, gross margin, opex
conversion, tax/finance conversion, shares) and measuring the reduction in the
relative EPS error gives contributions that sum exactly to the total error
(telescoping sum). Tax and finance are folded into one OP→NI conversion ratio
because the two cannot be separated from actuals alone (one equation, two
unknowns); the same holds for opex as a single GP→OP conversion.

This is a post-mortem attribution, NOT a forecast: actual ratios explain a
realized error only — they are never fed back into the no-look-ahead backtest.
"""

from __future__ import annotations

from schemas.models import DriverAttribution, QuarterlyActual, QuarterlyForecast

NI_TO_KRW = 1_000_000_000.0  # net profit is carried in KRW billions


def attribute_eps_error(
    target: QuarterlyActual,
    forecast: QuarterlyForecast,
    model_basic_shares: int,
) -> DriverAttribution:
    """Attribute the model-vs-actual EPS error of one backtest quarter.

    Args:
        target: Realized quarter (must carry eps_basic and non-zero
            revenue / gross_profit / operating_profit / net_profit).
        forecast: Model forecast for the same quarter (post eps_bridge).
        model_basic_shares: Weighted-average basic share count the model used.

    Returns:
        DriverAttribution whose five contributions sum to eps_error_total.

    Raises:
        ValueError: If eps_basic is missing/zero or any bridge denominator is
            zero, so the realized-ratio decomposition is undefined.
    """
    actual_eps = target.eps_basic
    model_eps = forecast.eps_basic
    if actual_eps in (None, 0):
        raise ValueError(f"{target.quarter_label}: actual eps_basic required for attribution")
    if model_eps is None:
        raise ValueError(f"{target.quarter_label}: model eps_basic missing")
    if model_basic_shares <= 0:
        raise ValueError("model_basic_shares must be positive")

    for label, value in (
        ("actual revenue", target.revenue_total),
        ("actual gross_profit", target.gross_profit),
        ("actual operating_profit", target.operating_profit),
        ("actual net_profit", target.net_profit),
        ("model revenue", forecast.revenue_total),
        ("model gross_profit", forecast.gross_profit),
        ("model operating_profit", forecast.operating_profit),
        ("model net_profit", forecast.net_profit),
    ):
        if value == 0:
            raise ValueError(f"{target.quarter_label}: {label} is zero — bridge undefined")

    # Model levers.
    r_m = forecast.revenue_total
    g_m = forecast.gross_profit / forecast.revenue_total          # gross margin
    o_m = forecast.operating_profit / forecast.gross_profit       # GP→OP conversion
    c_m = forecast.net_profit / forecast.operating_profit         # OP→NI conversion
    inv_s_m = NI_TO_KRW / model_basic_shares

    # Actual levers (ratios realized; 1e9/shares recovered as eps/NI).
    r_a = target.revenue_total
    g_a = target.gross_profit / target.revenue_total
    o_a = target.operating_profit / target.gross_profit
    c_a = target.net_profit / target.operating_profit
    inv_s_a = actual_eps / target.net_profit

    def eps(r: float, g: float, o: float, c: float, inv_s: float) -> float:
        return r * g * o * c * inv_s

    def err(value: float) -> float:
        return (value - actual_eps) / actual_eps

    # Sequential model→actual substitution (telescoping; sums to err of full model).
    e0 = eps(r_m, g_m, o_m, c_m, inv_s_m)   # full model (== model_eps)
    e1 = eps(r_a, g_m, o_m, c_m, inv_s_m)   # + actual revenue
    e2 = eps(r_a, g_a, o_m, c_m, inv_s_m)   # + actual gross margin
    e3 = eps(r_a, g_a, o_a, c_m, inv_s_m)   # + actual opex conversion
    e4 = eps(r_a, g_a, o_a, c_a, inv_s_m)   # + actual tax/finance conversion
    # e5 == actual_eps by construction; contrib_shares = err(e4) − 0.

    return DriverAttribution(
        quarter_label=target.quarter_label,
        eps_error_total=err(e0),
        contrib_revenue=err(e0) - err(e1),
        contrib_gross_margin=err(e1) - err(e2),
        contrib_opex=err(e2) - err(e3),
        contrib_tax_finance=err(e3) - err(e4),
        contrib_shares=err(e4),
        model_basic_shares=model_basic_shares,
        actual_implied_basic_shares=target.net_profit * NI_TO_KRW / actual_eps,
    )
