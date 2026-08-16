"""Tax + non-operating finance line projection.

NI = OP × (1 - effective_tax_rate) + net_interest
net_interest = revenue × net_interest_pct_of_revenue (typically slightly negative)
"""

from __future__ import annotations

from schemas.models import FinanceAssumptions, QuarterlyForecast


def apply_taxes_and_finance(
    forecast: list[QuarterlyForecast],
    assumptions: FinanceAssumptions,
) -> list[QuarterlyForecast]:
    """Compute net profit and net margin from operating profit.

    Args:
        forecast: Margin-populated forecast (operating_profit non-zero).
        assumptions: Effective tax rate + net interest ratio.

    Returns:
        List with net_profit and np_margin filled.

    Raises:
        NotImplementedError: Codex implementation.
    """
    results: list[QuarterlyForecast] = []
    for quarter in forecast:
        net_interest = quarter.revenue_total * assumptions.net_interest_pct_of_revenue
        net_profit = quarter.operating_profit * (1.0 - assumptions.effective_tax_rate) + net_interest
        np_margin = net_profit / quarter.revenue_total if quarter.revenue_total else 0.0
        results.append(quarter.model_copy(update={"net_profit": net_profit, "np_margin": np_margin}))
    return results
