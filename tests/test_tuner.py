"""Tests for calibration.tuner internals."""

from __future__ import annotations

from datetime import date

from backtest.models import BacktestRecord, ScenarioSnapshot
from calibration.tuner import _baseline_probs_from_records


def _record(probs_post_dlom: list[tuple[float, int]]) -> BacktestRecord:
    """Build a record from (prob%, post_dlom) pairs. Codes assigned A/B/C/…"""
    scenarios = [
        ScenarioSnapshot(
            code=chr(ord("A") + i),
            name=f"S{i}",
            prob=p,
            pre_dlom=v,
            post_dlom=v,
        )
        for i, (p, v) in enumerate(probs_post_dlom)
    ]
    return BacktestRecord(
        snapshot_id=f"snap-{len(scenarios)}",
        valuation_id="val",
        ticker="ACM",
        market="US",
        currency="USD",
        unit_multiplier=1,
        company_name="Acme",
        legal_status="listed",
        analysis_date=date(2026, 1, 1),
        predicted_value=100,
        scenarios=scenarios,
    )


def test_baseline_three_scenarios_sums_to_100():
    # 3 scenarios → one bull, one base, one bear (simple case).
    r = _record([(20.0, 100), (50.0, 110), (30.0, 120)])
    out = _baseline_probs_from_records([r])
    assert out["bear"] == 20.0
    assert out["base"] == 50.0
    assert out["bull"] == 30.0
    assert sum(out.values()) == 100.0


def test_baseline_four_scenarios_base_mass_preserved():
    """4 scenarios → 2 collapse into 'base'. Prior bug averaged them."""
    # post_dlom ordered: 100, 110, 120, 130
    # Roles: bear=100 (prob 10), base={110, 120} (prob 20+30=50), bull=130 (prob 40)
    r = _record([(10.0, 100), (20.0, 110), (30.0, 120), (40.0, 130)])
    out = _baseline_probs_from_records([r])
    assert out["bear"] == 10.0
    assert out["base"] == 50.0
    assert out["bull"] == 40.0
    assert sum(out.values()) == 100.0


def test_baseline_five_scenarios_three_base_entries():
    # post_dlom 100..140, probs 5/15/25/35/20
    # bear=5, base=15+25+35=75, bull=20
    r = _record([(5.0, 100), (15.0, 110), (25.0, 120), (35.0, 130), (20.0, 140)])
    out = _baseline_probs_from_records([r])
    assert out["bear"] == 5.0
    assert out["base"] == 75.0
    assert out["bull"] == 20.0
    assert sum(out.values()) == 100.0


def test_baseline_averages_across_records():
    # Two records, each sums to 100. Bucket baseline = per-role mean.
    r1 = _record([(10.0, 100), (50.0, 110), (40.0, 120)])  # bear=10 base=50 bull=40
    r2 = _record([(30.0, 100), (40.0, 110), (30.0, 120)])  # bear=30 base=40 bull=30
    out = _baseline_probs_from_records([r1, r2])
    assert out["bear"] == 20.0
    assert out["base"] == 45.0
    assert out["bull"] == 35.0
    assert sum(out.values()) == 100.0


def test_baseline_empty_records():
    out = _baseline_probs_from_records([])
    assert out == {"bear": 0.0, "base": 0.0, "bull": 0.0}


def test_baseline_single_scenario_all_base():
    # 1 scenario → classified as 'base' entirely.
    r = _record([(100.0, 100)])
    out = _baseline_probs_from_records([r])
    assert out["bear"] == 0.0
    assert out["base"] == 100.0
    assert out["bull"] == 0.0
