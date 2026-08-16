from __future__ import annotations

from datetime import date

import pytest

from engine.scenario import aggregate_quarterly_to_annual, build_scenario_tree
from schemas.models import (
    CompanyMeta,
    QuarterlyForecast,
    ScenarioCase,
    ScenarioProbabilities,
    SegmentForecast,
)


def _q(label: str, scenario: str, revenue: float) -> QuarterlyForecast:
    return QuarterlyForecast(
        quarter_label=label,
        scenario=scenario,
        revenue_total=revenue,
        revenue_by_segment=[SegmentForecast(segment_id="dram", revenue=revenue)],
        gross_profit=revenue * 0.4,
        operating_profit=revenue * 0.3,
        net_profit=revenue * 0.2,
        gp_margin=0.4,
        op_margin=0.3,
        np_margin=0.2,
        eps_basic=revenue,
    )


def _case(name: str, revenue: float, labels: list[str] | None = None) -> ScenarioCase:
    quarterly = [_q(label, name, revenue) for label in (labels or ["2026Q1", "2026Q2"])]
    return ScenarioCase(
        scenario=name,
        probability={"bear": 0.25, "base": 0.50, "bull": 0.25}[name],
        rationale="test",
        quarterly=quarterly,
        annual=aggregate_quarterly_to_annual(quarterly, name),
    )


def _company() -> CompanyMeta:
    return CompanyMeta(
        name="SK Hynix",
        name_kr="SK",
        ticker_yahoo="000660.KS",
        corp_code_dart="00164779",
        fiscal_year_end_month=12,
        reporting_unit="KRW_billion",
    )


def test_weighted_quarterly_equals_weighted_sum_of_cases():
    tree = build_scenario_tree(
        _company(),
        date(2026, 5, 30),
        _case("bear", 80),
        _case("base", 100),
        _case("bull", 140),
        ScenarioProbabilities(bear=0.25, base=0.50, bull=0.25),
    )

    assert tree.weighted_quarterly[0].revenue_total == pytest.approx(105.0)


def test_aggregate_to_annual_sums_four_quarters():
    annual = aggregate_quarterly_to_annual(
        [_q("2026Q1", "base", 10), _q("2026Q2", "base", 20), _q("2027Q1", "base", 30)],
        "base",
    )

    assert annual[0].fiscal_year == 2026
    assert annual[0].revenue_total == pytest.approx(30.0)


def test_build_tree_rejects_misaligned_quarters():
    with pytest.raises(ValueError):
        build_scenario_tree(
            _company(),
            date(2026, 5, 30),
            _case("bear", 80),
            _case("base", 100, ["2026Q2"]),
            _case("bull", 140),
            ScenarioProbabilities(bear=0.25, base=0.50, bull=0.25),
        )
