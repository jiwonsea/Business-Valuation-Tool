"""GP / OP margin projection using cost-per-bit ASP leverage."""

from __future__ import annotations

from schemas.models import (
    AnchorMargins,
    MarginAssumptions,
    MarginBaseline,
    QuarterlyForecast,
)


def project_margins(
    revenue_forecast: list[QuarterlyForecast],
    baseline: MarginBaseline,
    assumptions: MarginAssumptions,
    anchor_margins: AnchorMargins,
) -> list[QuarterlyForecast]:
    """Populate GP / OP / NP margins on each forecast quarter.

    Args:
        revenue_forecast: Output of segment_revenue.project_quarterly_revenue
            with segment revenue and hbm_share populated.
        baseline: Prior-4Q averages retained for interface compatibility.
        assumptions: Scenario-specific SG&A / R&D ratios.
        anchor_margins: Historical anchor gross margins and cost decline rates.

    Returns:
        Same length list, with gp_margin / op_margin / np_margin and matching
        gross_profit / operating_profit / net_profit populated.

    Raises:
        ValueError: If required segment revenue is missing.
    """
    del baseline
    results: list[QuarterlyForecast] = []
    for forecast in revenue_forecast:
        revenue_by_segment = {segment.segment_id: segment.revenue for segment in forecast.revenue_by_segment}
        try:
            dram_revenue = revenue_by_segment["dram"]
            nand_revenue = revenue_by_segment["nand"]
            other_revenue = revenue_by_segment["other"]
        except KeyError as exc:
            raise ValueError(f"missing {exc.args[0]} segment") from exc

        hbm_revenue = forecast.hbm_share * dram_revenue
        ddr_revenue = (1.0 - forecast.hbm_share) * dram_revenue
        periods = forecast.margin_periods_since_anchor
        hbm_margin = _cost_per_bit_margin(
            anchor_margins.gm_hbm,
            anchor_margins.cost_decline_qoq_hbm,
            forecast.asp_hbm,
            periods,
        )
        ddr_margin = _cost_per_bit_margin(
            anchor_margins.gm_ddr,
            anchor_margins.cost_decline_qoq_ddr,
            forecast.asp_ddr,
            periods,
        )
        nand_margin = _cost_per_bit_margin(
            anchor_margins.gm_nand,
            anchor_margins.cost_decline_qoq_nand,
            forecast.asp_nand,
            periods,
        )
        gross_profit = (
            hbm_revenue * hbm_margin
            + ddr_revenue * ddr_margin
            + nand_revenue * nand_margin
            + other_revenue * anchor_margins.gm_other
        )
        gp_margin = gross_profit / forecast.revenue_total if forecast.revenue_total else 0.0
        gp_margin = min(0.9, gp_margin)
        gross_profit = forecast.revenue_total * gp_margin
        op_margin = gp_margin - _opex_pct_of_revenue(assumptions, forecast.revenue_total)
        operating_profit = forecast.revenue_total * op_margin
        results.append(
            forecast.model_copy(
                update={
                    "gross_profit": gross_profit,
                    "operating_profit": operating_profit,
                    "net_profit": operating_profit,
                    "gp_margin": gp_margin,
                    "op_margin": op_margin,
                    "np_margin": op_margin,
                }
            )
        )
    return results


def _opex_pct_of_revenue(assumptions: MarginAssumptions, revenue_total: float) -> float:
    """Opex ratio: fixed + variable split when configured, else constant sga + rnd.

    The fixed + variable form captures operating leverage (opex sticky in absolute
    KRW): the ratio falls as revenue grows. PLAN_opex_model.md. Legacy profiles
    without the split keep the previous constant-% behaviour bit-identical.
    """
    if assumptions.opex_fixed_krw_bn is None:
        return assumptions.sga_pct_of_revenue + assumptions.rnd_pct_of_revenue
    if revenue_total <= 0.0:
        raise ValueError("revenue_total must be positive for fixed+variable opex")
    return assumptions.opex_fixed_krw_bn / revenue_total + assumptions.opex_variable_pct_of_revenue


def _cost_per_bit_margin(
    anchor_margin: float,
    cost_decline_qoq: float,
    asp_factor: float,
    periods_since_anchor: int,
) -> float:
    if asp_factor <= 0.0:
        raise ValueError("ASP factor must be positive")
    cost_factor = (1.0 - cost_decline_qoq) ** periods_since_anchor
    return 1.0 - (1.0 - anchor_margin) * cost_factor / asp_factor
