"""Scenario tree construction and probability weighting.

Bear / Base / Bull cases combined via user-defined probabilities (must sum to 1.0).
Weighted forecast = Σ (probability × case_value) per metric per period.
"""

from __future__ import annotations

from datetime import date

from schemas.models import (
    AnnualForecast,
    CompanyMeta,
    QuarterlyForecast,
    SegmentForecast,
    ScenarioCase,
    ScenarioProbabilities,
    ScenarioTree,
)


def _year_from_quarter(label: str) -> int:
    return int(label.split("Q", 1)[0])


def aggregate_quarterly_to_annual(
    quarterly: list[QuarterlyForecast],
    scenario: str = "base",
) -> list[AnnualForecast]:
    """Group quarterly forecasts into fiscal-year buckets and sum P&L lines.

    Args:
        quarterly: List of QuarterlyForecast (any scenario).
        scenario: Scenario label to stamp on output.

    Returns:
        List of AnnualForecast — one entry per fiscal year covered.

    Raises:
        NotImplementedError: Codex implementation.
    """
    buckets: dict[int, list[QuarterlyForecast]] = {}
    for quarter in quarterly:
        buckets.setdefault(_year_from_quarter(quarter.quarter_label), []).append(quarter)

    annual: list[AnnualForecast] = []
    for fiscal_year in sorted(buckets):
        quarters = buckets[fiscal_year]
        eps_values = [q.eps_basic for q in quarters if q.eps_basic is not None]
        annual.append(
            AnnualForecast(
                fiscal_year=fiscal_year,
                scenario=scenario,  # type: ignore[arg-type]
                revenue_total=sum(q.revenue_total for q in quarters),
                operating_profit=sum(q.operating_profit for q in quarters),
                net_profit=sum(q.net_profit for q in quarters),
                eps_basic=sum(eps_values) if eps_values else None,
            )
        )
    return annual


def build_scenario_tree(
    company: CompanyMeta,
    as_of: date,
    bear: ScenarioCase,
    base: ScenarioCase,
    bull: ScenarioCase,
    probabilities: ScenarioProbabilities,
) -> ScenarioTree:
    """Combine 3 case forecasts into a tree with probability-weighted view.

    The weighted forecast is per-period: each quarter and each fiscal year
    is the probability-weighted sum across the 3 cases.

    Args:
        company: Company meta from profile YAML.
        as_of: Run date.
        bear, base, bull: Pre-computed scenario cases.
        probabilities: Must sum to 1.0 (validator on ScenarioProbabilities enforces).

    Returns:
        ScenarioTree with weighted_quarterly and weighted_annual populated.

    Raises:
        ValueError: If quarter labels don't align across cases.
        NotImplementedError: Codex implementation.
    """
    case_quarters = [
        [quarter.quarter_label for quarter in bear.quarterly],
        [quarter.quarter_label for quarter in base.quarterly],
        [quarter.quarter_label for quarter in bull.quarterly],
    ]
    if case_quarters[0] != case_quarters[1] or case_quarters[1] != case_quarters[2]:
        raise ValueError("scenario quarter labels must align")

    case_years = [
        [annual.fiscal_year for annual in bear.annual],
        [annual.fiscal_year for annual in base.annual],
        [annual.fiscal_year for annual in bull.annual],
    ]
    if case_years[0] != case_years[1] or case_years[1] != case_years[2]:
        raise ValueError("scenario annual fiscal years must align")

    probs = {"bear": probabilities.bear, "base": probabilities.base, "bull": probabilities.bull}
    cases = {"bear": bear, "base": base, "bull": bull}
    weighted_quarterly: list[QuarterlyForecast] = []
    for idx, quarter_label in enumerate(case_quarters[0]):
        quarters = {name: case.quarterly[idx] for name, case in cases.items()}
        segment_ids = [segment.segment_id for segment in base.quarterly[idx].revenue_by_segment]
        weighted_segments = [
            SegmentForecast(
                segment_id=segment_id,
                revenue=sum(
                    probs[name]
                    * next(s.revenue for s in quarters[name].revenue_by_segment if s.segment_id == segment_id)
                    for name in cases
                ),
            )
            for segment_id in segment_ids
        ]
        eps_values = [quarters[name].eps_basic for name in cases]
        weighted_quarterly.append(
            QuarterlyForecast(
                quarter_label=quarter_label,
                scenario="weighted",
                revenue_total=sum(probs[name] * quarters[name].revenue_total for name in cases),
                revenue_by_segment=weighted_segments,
                hbm_share=sum(probs[name] * quarters[name].hbm_share for name in cases),
                asp_hbm=sum(probs[name] * quarters[name].asp_hbm for name in cases),
                asp_ddr=sum(probs[name] * quarters[name].asp_ddr for name in cases),
                asp_nand=sum(probs[name] * quarters[name].asp_nand for name in cases),
                margin_periods_since_anchor=max(
                    quarters[name].margin_periods_since_anchor for name in cases
                ),
                gross_profit=sum(probs[name] * quarters[name].gross_profit for name in cases),
                operating_profit=sum(probs[name] * quarters[name].operating_profit for name in cases),
                net_profit=sum(probs[name] * quarters[name].net_profit for name in cases),
                gp_margin=sum(probs[name] * quarters[name].gp_margin for name in cases),
                op_margin=sum(probs[name] * quarters[name].op_margin for name in cases),
                np_margin=sum(probs[name] * quarters[name].np_margin for name in cases),
                eps_basic=sum(probs[name] * (quarters[name].eps_basic or 0.0) for name in cases)
                if any(value is not None for value in eps_values)
                else None,
                eps_diluted=sum(probs[name] * (quarters[name].eps_diluted or 0.0) for name in cases)
                if any(quarters[name].eps_diluted is not None for name in cases)
                else None,
            )
        )

    weighted_annual: list[AnnualForecast] = []
    for idx, fiscal_year in enumerate(case_years[0]):
        annuals = {name: case.annual[idx] for name, case in cases.items()}
        eps_values = [annuals[name].eps_basic for name in cases]
        weighted_annual.append(
            AnnualForecast(
                fiscal_year=fiscal_year,
                scenario="weighted",
                revenue_total=sum(probs[name] * annuals[name].revenue_total for name in cases),
                operating_profit=sum(probs[name] * annuals[name].operating_profit for name in cases),
                net_profit=sum(probs[name] * annuals[name].net_profit for name in cases),
                eps_basic=sum(probs[name] * (annuals[name].eps_basic or 0.0) for name in cases)
                if any(value is not None for value in eps_values)
                else None,
            )
        )

    return ScenarioTree(
        company=company,
        as_of=as_of,
        bear=bear,
        base=base,
        bull=bull,
        weighted_quarterly=weighted_quarterly,
        weighted_annual=weighted_annual,
    )
