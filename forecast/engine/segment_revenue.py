"""Segment-level revenue projection.

SK Hynix: DRAM (HBM + DDR blended) + NAND + Other.
DRAM_blended_ASP = HBM_share × HBM_ASP + (1 - HBM_share) × DDR_ASP.
"""

from __future__ import annotations

from schemas.models import (
    HistoricalDriver,
    MarginBaseline,
    MarginCarryover,
    QuarterlyActual,
    QuarterlyForecast,
    SegmentAssumptions,
    SegmentForecast,
)


def build_margin_carryover(
    historical_drivers: dict[str, HistoricalDriver],
    through_quarter: str,
) -> MarginCarryover:
    """Accumulate historical ASP factors from the first driver quarter to seed.

    Args:
        historical_drivers: Historical market ASP drivers keyed by quarter label.
        through_quarter: Last quarter to include, usually the forward seed quarter.

    Returns:
        MarginCarryover with anchor-quarter ASP changes excluded.

    Raises:
        ValueError: If no drivers exist, labels are invalid, or through_quarter is missing.
    """
    if not historical_drivers:
        raise ValueError("historical_drivers must contain at least one quarter")
    sorted_labels = sorted(historical_drivers, key=_quarter_sort_key)
    if through_quarter not in historical_drivers:
        raise ValueError(f"missing historical driver for seed quarter {through_quarter}")

    asp_hbm = 1.0
    asp_ddr = 1.0
    asp_nand = 1.0
    periods = 0
    through_key = _quarter_sort_key(through_quarter)
    for label in sorted_labels:
        if _quarter_sort_key(label) > through_key:
            break
        driver = historical_drivers[label]
        asp_hbm *= 1.0 + driver.hbm_asp_qoq
        asp_ddr *= 1.0 + driver.ddr_asp_qoq
        asp_nand *= 1.0 + driver.nand_asp_qoq
        periods += 1

    return MarginCarryover(
        asp_hbm=asp_hbm,
        asp_ddr=asp_ddr,
        asp_nand=asp_nand,
        periods_since_anchor=periods,
    )


def _segment_revenue(actual: QuarterlyActual, segment_id: str) -> float:
    for segment in actual.revenue_by_segment:
        if segment.segment_id == segment_id:
            return segment.revenue
    raise ValueError(f"missing segment revenue: {segment_id}")


def project_quarterly_revenue(
    prior_actual: QuarterlyActual,
    baseline: MarginBaseline,
    assumptions: SegmentAssumptions,
    n_quarters: int,
    margin_carryover: MarginCarryover | None = None,
) -> list[QuarterlyForecast]:
    """Project N forward quarters of segment revenue from a starting actual.

    Args:
        prior_actual: Last reported quarter (acts as the seed for bit volume and ASP).
        baseline: Prior-4Q averages — used as ASP / margin baseline for cyclical functions.
        assumptions: Per-quarter driver inputs (length must be >= n_quarters).
        n_quarters: How many forward quarters to project.

    Returns:
        List of QuarterlyForecast with revenue_total + revenue_by_segment populated.
        Margins are left at zero — populated later by margin_model.project_margins.

    Raises:
        ValueError: If driver list lengths < n_quarters.
        NotImplementedError: Codex implementation.
    """
    driver_lists = [
        assumptions.dram_bit_growth_qoq,
        assumptions.dram_hbm_share_qoq,
        assumptions.dram_ddr_asp_qoq,
        assumptions.nand_bit_growth_qoq,
        assumptions.nand_asp_qoq,
        assumptions.other_revenue_growth_qoq,
    ]
    if n_quarters < 1:
        raise ValueError("n_quarters must be positive")
    if any(len(values) < n_quarters for values in driver_lists):
        raise ValueError("driver list lengths must be >= n_quarters")

    dram_revenue = _segment_revenue(prior_actual, "dram")
    nand_revenue = _segment_revenue(prior_actual, "nand")
    other_revenue = _segment_revenue(prior_actual, "other")

    ddr_asp = baseline.dram_blended_asp or 1.0
    hbm_asp = ddr_asp
    nand_asp = baseline.nand_blended_asp or 1.0
    margin_hbm_asp = margin_carryover.asp_hbm if margin_carryover else 1.0
    margin_ddr_asp = margin_carryover.asp_ddr if margin_carryover else 1.0
    margin_nand_asp = margin_carryover.asp_nand if margin_carryover else 1.0
    margin_periods = margin_carryover.periods_since_anchor if margin_carryover else 0
    dram_bit_volume = dram_revenue / ddr_asp
    nand_bit_volume = nand_revenue / nand_asp

    forecasts: list[QuarterlyForecast] = []
    quarter_label = prior_actual.quarter_label
    for i in range(n_quarters):
        quarter_label = _next_quarter_label(quarter_label)

        dram_bit_volume *= 1.0 + assumptions.dram_bit_growth_qoq[i]
        hbm_share = assumptions.dram_hbm_share_qoq[i]
        if not 0.0 <= hbm_share <= 1.0:
            raise ValueError("dram_hbm_share_qoq values must be between 0 and 1")
        hbm_asp_change = assumptions.dram_hbm_asp_yoy / 4.0
        ddr_asp_change = assumptions.dram_ddr_asp_qoq[i]
        hbm_asp *= 1.0 + hbm_asp_change
        ddr_asp *= 1.0 + ddr_asp_change
        margin_hbm_asp *= 1.0 + hbm_asp_change
        margin_ddr_asp *= 1.0 + ddr_asp_change
        dram_asp = hbm_share * hbm_asp + (1.0 - hbm_share) * ddr_asp
        dram = dram_bit_volume * dram_asp

        nand_bit_volume *= 1.0 + assumptions.nand_bit_growth_qoq[i]
        nand_asp_change = assumptions.nand_asp_qoq[i]
        nand_asp *= 1.0 + nand_asp_change
        margin_nand_asp *= 1.0 + nand_asp_change
        nand = nand_bit_volume * nand_asp

        other_revenue *= 1.0 + assumptions.other_revenue_growth_qoq[i]
        margin_periods += 1
        total = dram + nand + other_revenue
        forecasts.append(
            QuarterlyForecast(
                quarter_label=quarter_label,
                revenue_total=total,
                revenue_by_segment=[
                    SegmentForecast(segment_id="dram", revenue=dram),
                    SegmentForecast(segment_id="nand", revenue=nand),
                    SegmentForecast(segment_id="other", revenue=other_revenue),
                ],
                hbm_share=hbm_share,
                asp_hbm=margin_hbm_asp,
                asp_ddr=margin_ddr_asp,
                asp_nand=margin_nand_asp,
                margin_periods_since_anchor=margin_periods,
                gross_profit=0.0,
                operating_profit=0.0,
                net_profit=0.0,
                gp_margin=0.0,
                op_margin=0.0,
                np_margin=0.0,
            )
        )
    return forecasts


def _next_quarter_label(label: str) -> str:
    """Helper: '2026Q1' -> '2026Q2', '2026Q4' -> '2027Q1'."""
    if len(label) < 6 or "Q" not in label:
        raise ValueError(f"invalid quarter label: {label}")
    year_text, quarter_text = label.split("Q", 1)
    year = int(year_text)
    quarter = int(quarter_text)
    if quarter not in {1, 2, 3, 4}:
        raise ValueError(f"invalid quarter label: {label}")
    if quarter == 4:
        return f"{year + 1}Q1"
    return f"{year}Q{quarter + 1}"


def _quarter_sort_key(label: str) -> tuple[int, int]:
    if len(label) < 6 or "Q" not in label:
        raise ValueError(f"invalid quarter label: {label}")
    year_text, quarter_text = label.split("Q", 1)
    year = int(year_text)
    quarter = int(quarter_text)
    if quarter not in {1, 2, 3, 4}:
        raise ValueError(f"invalid quarter label: {label}")
    return year, quarter
