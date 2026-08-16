"""valuation_bridge: EPS-gap -> fair-value delta + overlay/band consumption.

PLAN_valuation_bridge.md. Two layers, kept numerically separate:
  - Layer 1: (model FY1 EPS vs consensus) × elasticity -> fair-value delta, plus a
    band projection from the below-OP EPS band half-width.
  - Layer 2: overlays -> a macro entry/risk score, NEVER folded into the layer-1
    point delta (CLAUDE.md two-layer split).

Guards: missing or unreliable consensus -> fair-value delta None + note
(HANDOFF_backtest_diag §①-B: yfinance .KS consensus can be ~3x broken).
The bridge is read-only over the ScenarioTree (forecast EPS bit-identical).

Deterministic: builds a tiny tree in-process, no network.
"""

from __future__ import annotations

from datetime import date

import pytest

from engine.below_op_events import build_event_adjusted_eps
from engine.scenario import aggregate_quarterly_to_annual, build_scenario_tree
from engine.valuation_bridge import sensitivity_to_dcf
from schemas.models import (
    BelowOpEvent,
    CompanyMeta,
    Overlay,
    QuarterlyForecast,
    ScenarioCase,
    ScenarioProbabilities,
    SegmentForecast,
    ValuationBridgeResult,
)


def _tree(eps: float = 100.0):
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
        eps_basic=eps,
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
        company, date(2026, 5, 30), bear, base, bull,
        ScenarioProbabilities(bear=0.25, base=0.50, bull=0.25),
    )


def _overlays():
    return [
        Overlay(as_of_date=date(2026, 5, 15), target_period_label="2026Q2",
                driver="FX", direction="risk_down", magnitude=0.03, confidence=0.4),
        Overlay(as_of_date=date(2026, 6, 1), target_period_label="2026Q3",
                driver="UST", direction="risk_down", magnitude=0.05, confidence=0.2),
    ]


# --- Layer 1: EPS gap -> fair-value delta ---------------------------------- #

def test_fair_value_delta_is_elasticity_times_eps_gap() -> None:
    tree = _tree(eps=100.0)
    result = sensitivity_to_dcf(tree, consensus_eps_fy=80.0, fair_value_elasticity=1.2)
    assert isinstance(result, ValuationBridgeResult)
    # weighted FY1 EPS == 100 (single quarter); gap vs 80 = +25%.
    assert result.eps_delta_pct == pytest.approx(0.25)
    assert result.fair_value_delta_pct == pytest.approx(1.2 * 0.25)


def test_below_op_events_do_not_change_fair_value_delta() -> None:
    """A present event scenario must never feed one-off EPS into valuation."""
    tree = _tree(eps=100.0)
    before = sensitivity_to_dcf(tree, consensus_eps_fy=80.0, fair_value_elasticity=1.2)
    event = BelowOpEvent(
        id="kioxia_spc1_disposal",
        as_of_date=date(2026, 3, 30),
        amount_as_of=date(2026, 3, 30),
        target_period_label="2026Q1",
        kind="asset_disposal_gain",
        amount_krw_bn=40_000.0,
        basis="net_income_level",
        probability=0.8,
        confidence="estimated",
        source="estimate",
    )
    event_scenario = build_event_adjusted_eps(
        [(q.quarter_label, q.eps_basic) for q in tree.weighted_quarterly],
        800_000_000,
        [event],
        calculation_as_of=date(2026, 3, 30),
    )
    after = sensitivity_to_dcf(tree, consensus_eps_fy=80.0, fair_value_elasticity=1.2)

    assert event_scenario.quarters[0].eps_expected != tree.weighted_quarterly[0].eps_basic
    assert after.model_dump() == before.model_dump()


def test_missing_consensus_holds_delta() -> None:
    result = sensitivity_to_dcf(_tree(), consensus_eps_fy=None)
    assert result.eps_delta_pct is None
    assert result.fair_value_delta_pct is None
    assert result.note


def test_unreliable_consensus_holds_delta() -> None:
    result = sensitivity_to_dcf(_tree(), consensus_eps_fy=80.0, consensus_reliable=False)
    assert result.fair_value_delta_pct is None
    assert "신뢰" in result.note or "reliab" in result.note.lower()


def test_band_projection_brackets_point_delta() -> None:
    result = sensitivity_to_dcf(
        _tree(eps=100.0), consensus_eps_fy=80.0, fair_value_elasticity=1.2,
        eps_half_width_pct=0.2279,
    )
    assert result.fair_value_delta_low is not None
    assert result.fair_value_delta_high is not None
    assert result.fair_value_delta_low < result.fair_value_delta_pct < result.fair_value_delta_high


# --- Layer 2: overlays -> separate risk score ------------------------------ #

def test_overlay_risk_score_is_signed_weighted_sum() -> None:
    result = sensitivity_to_dcf(
        _tree(), consensus_eps_fy=80.0, overlays=_overlays(), overlay_weight=1.0
    )
    # risk_down -> -1; -(0.03*0.4) - (0.05*0.2) = -0.022.
    assert result.overlay_risk_score == pytest.approx(-0.022)
    assert result.overlays == _overlays()


def test_overlays_do_not_perturb_fair_value_delta() -> None:
    """Layer separation: overlays change only the layer-2 score, not layer-1 delta."""
    without = sensitivity_to_dcf(_tree(), consensus_eps_fy=80.0, fair_value_elasticity=1.2)
    with_ov = sensitivity_to_dcf(
        _tree(), consensus_eps_fy=80.0, fair_value_elasticity=1.2, overlays=_overlays()
    )
    assert with_ov.fair_value_delta_pct == without.fair_value_delta_pct
    assert with_ov.overlay_risk_score != without.overlay_risk_score


def test_bridge_does_not_mutate_tree() -> None:
    tree = _tree(eps=100.0)
    before = tree.model_dump_json()
    sensitivity_to_dcf(tree, consensus_eps_fy=80.0, overlays=_overlays())
    assert tree.model_dump_json() == before


def test_docstring_forbids_event_adjusted_eps_input() -> None:
    """P2 contract is explicit at the valuation API boundary."""
    doc = sensitivity_to_dcf.__module__
    assert doc == "engine.valuation_bridge"
    module_doc = __import__(doc, fromlist=["__doc__"]).__doc__ or ""
    assert "event-adjusted EPS" in module_doc
    assert "never be injected" in module_doc
