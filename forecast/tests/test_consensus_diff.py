from __future__ import annotations

from datetime import date

import pytest

from engine.consensus_diff import compute_consensus_gap
from engine.scenario import aggregate_quarterly_to_annual, build_scenario_tree
from schemas.models import (
    CompanyMeta,
    ConsensusRecord,
    QuarterlyForecast,
    ScenarioCase,
    ScenarioProbabilities,
    SegmentForecast,
)


def _tree():
    company = CompanyMeta(
        name="SK Hynix",
        name_kr="SK",
        ticker_yahoo="000660.KS",
        corp_code_dart="00164779",
        fiscal_year_end_month=12,
        reporting_unit="KRW_billion",
    )
    q = QuarterlyForecast(
        quarter_label="2026Q1",
        revenue_total=110.0,
        revenue_by_segment=[SegmentForecast(segment_id="dram", revenue=110.0)],
        gross_profit=40.0,
        operating_profit=30.0,
        net_profit=20.0,
        gp_margin=0.4,
        op_margin=0.3,
        np_margin=0.2,
        eps_basic=55.0,
    )
    base = ScenarioCase(
        scenario="base",
        probability=0.5,
        rationale="",
        quarterly=[q],
        annual=aggregate_quarterly_to_annual([q], "base"),
    )
    bear = base.model_copy(update={"scenario": "bear", "probability": 0.25})
    bull = base.model_copy(update={"scenario": "bull", "probability": 0.25})
    return build_scenario_tree(
        company,
        date(2026, 5, 30),
        bear,
        base,
        bull,
        ScenarioProbabilities(bear=0.25, base=0.50, bull=0.25),
    )


def test_gap_pct_calculation():
    consensus = ConsensusRecord(
        ticker="000660.KS",
        as_of=date(2026, 5, 30),
        revenue_estimate_quarterly={"2026Q1": 100.0},
        eps_estimate_quarterly={"2026Q1": 50.0},
        revenue_estimate_annual={},
        eps_estimate_annual={},
    )

    gaps = compute_consensus_gap(_tree(), consensus)

    assert gaps[0].gap_pct == pytest.approx(0.10)


def test_missing_consensus_yields_na():
    consensus = ConsensusRecord(
        ticker="000660.KS",
        as_of=date(2026, 5, 30),
        revenue_estimate_quarterly={},
        eps_estimate_quarterly={},
        revenue_estimate_annual={},
        eps_estimate_annual={},
    )

    gaps = compute_consensus_gap(_tree(), consensus)

    assert gaps[0].direction == "n_a"
    assert gaps[0].gap_pct is None


def test_interpretation_left_blank():
    consensus = ConsensusRecord(
        ticker="000660.KS",
        as_of=date(2026, 5, 30),
        revenue_estimate_quarterly={"2026Q1": 100.0},
        eps_estimate_quarterly={},
        revenue_estimate_annual={},
        eps_estimate_annual={},
    )

    assert compute_consensus_gap(_tree(), consensus)[0].interpretation == ""
