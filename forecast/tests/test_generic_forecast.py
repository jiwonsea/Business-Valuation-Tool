"""Tests for the generic (sector-agnostic) forecast path.

Covers the driver-vector normalisation, the revenue/EPS recursion, probability
weighting, unit scaling, and profile validation. Pure-function, exact-value
assertions (no IO), mirroring the memory-engine test style.
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from schemas.generic import GenericProfile, GenericScenarioAssumptions
from engine.generic_forecast import project_scenario, run_generic_forecast


def _profile(**overrides) -> GenericProfile:
    base = dict(
        name="Test Co",
        name_kr="테스트",
        ticker="TST",
        currency="USD",
        reporting_unit="USD_million",
        fiscal_year_end_month=12,
        weighted_avg_diluted=1_000_000_000,  # 1B shares
        seed=dict(quarter_label="2025Q4", revenue_total=1000.0),
        window=dict(start_quarter="2026Q1", n_quarters=4),
        actuals=[
            dict(quarter_label="2025Q3", revenue_total=950.0, eps_diluted=0.10),
            dict(quarter_label="2025Q4", revenue_total=1000.0, eps_diluted=0.11),
        ],
        bear=dict(probability=0.25, revenue_growth_qoq=[0.0, 0.0, 0.0, 0.0], op_margin=0.10, effective_tax_rate=0.20),
        base=dict(probability=0.50, revenue_growth_qoq=[0.05, 0.05, 0.05, 0.05], op_margin=0.20, effective_tax_rate=0.20),
        bull=dict(probability=0.25, revenue_growth_qoq=[0.10, 0.10, 0.10, 0.10], op_margin=0.30, effective_tax_rate=0.20),
    )
    base.update(overrides)
    return GenericProfile.model_validate(base)


def test_scalar_driver_broadcasts_to_vector():
    a = GenericScenarioAssumptions(
        probability=0.5, revenue_growth_qoq=[0.05], op_margin=0.2,
        effective_tax_rate=0.2, net_interest_pct_of_revenue=0.0,
    )
    assert a.margin(4) == [0.2, 0.2, 0.2, 0.2]
    assert a.tax(3) == [0.2, 0.2, 0.2]


def test_revenue_compounds_and_eps_scales():
    p = _profile()
    q = project_scenario(p, p.base, "base")
    assert len(q) == 4
    # revenue: 1000 * 1.05^k
    assert q[0].revenue_total == pytest.approx(1050.0)
    assert q[3].revenue_total == pytest.approx(1000.0 * 1.05 ** 4)
    # EPS: op = rev*0.20; net = op*(1-0.20); eps = net * 1e6 / 1e9
    op0 = 1050.0 * 0.20
    net0 = op0 * 0.80
    assert q[0].eps_diluted == pytest.approx(net0 * 1_000_000 / 1_000_000_000)


def test_net_interest_flows_into_pretax():
    p = _profile(
        base=dict(probability=0.50, revenue_growth_qoq=[0.0, 0.0, 0.0, 0.0], op_margin=0.20,
                  effective_tax_rate=0.0, net_interest_pct_of_revenue=0.05),
    )
    q = project_scenario(p, p.base, "base")
    # pretax = rev*0.20 + rev*0.05 = rev*0.25; tax 0 -> net = 250 on rev 1000
    assert q[0].net_profit == pytest.approx(1000.0 * 0.25)


def test_probability_weighting_is_convex_combination():
    p = _profile()
    fc = run_generic_forecast(p)
    q_bear = fc.scenarios_quarterly["bear"][0].revenue_total
    q_base = fc.scenarios_quarterly["base"][0].revenue_total
    q_bull = fc.scenarios_quarterly["bull"][0].revenue_total
    expected = 0.25 * q_bear + 0.50 * q_base + 0.25 * q_bull
    assert fc.weighted_quarterly[0].revenue_total == pytest.approx(expected)


def test_annual_is_sum_of_four_quarters():
    p = _profile()
    fc = run_generic_forecast(p)
    assert len(fc.weighted_annual) == 1  # all four forward quarters land in 2026
    total = sum(q.revenue_total for q in fc.weighted_quarterly)
    assert fc.weighted_annual[0].revenue_total == pytest.approx(total)


def test_probabilities_must_sum_to_one():
    with pytest.raises(ValidationError):
        _profile(bull=dict(probability=0.50, revenue_growth_qoq=[0.1, 0.1, 0.1, 0.1], op_margin=0.3, effective_tax_rate=0.2))


def test_short_driver_vector_rejected():
    p = _profile()
    with pytest.raises(ValueError):
        # window wants 4 quarters but growth only has 2
        project_scenario(
            p,
            GenericScenarioAssumptions(probability=0.5, revenue_growth_qoq=[0.05, 0.05], op_margin=0.2, effective_tax_rate=0.2),
            "base",
        )


def test_krw_billion_unit_scale():
    p = _profile(reporting_unit="KRW_billion", currency="KRW")
    q = project_scenario(p, p.base, "base")
    # eps = net(bn) * 1e9 / shares
    op0 = 1050.0 * 0.20
    net0 = op0 * 0.80
    assert q[0].eps_diluted == pytest.approx(net0 * 1_000_000_000 / 1_000_000_000)
    assert math.isfinite(q[0].eps_diluted)
