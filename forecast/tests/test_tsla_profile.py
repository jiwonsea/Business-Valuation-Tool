"""TSLA profile regression checks for decoupled forward/backtest drivers."""

from pathlib import Path

import pytest

from engine.generic_forecast import run_generic_forecast
from generic_cli import backtest_generic, load_generic_profile

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load():
    return load_generic_profile(REPO_ROOT / "profiles" / "tsla.generic.yaml")


def test_tsla_forward_q2_matches_frozen_anchor() -> None:
    forecast = run_generic_forecast(_load())
    base_q2 = forecast.scenarios_quarterly["base"][0]
    weighted_q2 = forecast.weighted_quarterly[0]

    assert base_q2.quarter_label == "2026Q2"
    assert base_q2.revenue_total == pytest.approx(26_864.4)
    assert base_q2.eps_diluted == pytest.approx(0.39, abs=0.01)
    assert weighted_q2.revenue_total == pytest.approx(26_808.43, abs=0.01)
    assert weighted_q2.eps_diluted == pytest.approx(0.43, abs=0.02)


def test_tsla_backtest_uses_target_quarter_calendar_slots() -> None:
    profile = _load()
    methodology = profile.backtest_methodology
    assert methodology is not None
    expected_growth = [-0.14, 0.14, 0.06, -0.01]
    assert methodology.revenue_growth_qoq == expected_growth

    result = backtest_generic(profile)
    for row in result["rows"]:
        slot = int(row["quarter"][-1]) - 1
        modeled_growth = row["model_rev"] / row["rw_rev"] - 1.0
        assert modeled_growth == pytest.approx(expected_growth[slot])


def test_tsla_methodology_matches_recent_actual_seasonality() -> None:
    actuals = [a for a in _load().actuals if a.quarter_label >= "2022Q4"]
    growth_by_slot: dict[int, list[float]] = {slot: [] for slot in range(4)}
    for previous, current in zip(actuals, actuals[1:]):
        slot = int(current.quarter_label[-1]) - 1
        growth_by_slot[slot].append(
            current.revenue_total / previous.revenue_total - 1.0
        )

    means = [sum(values) / len(values) for values in growth_by_slot.values()]
    assert means == pytest.approx([-0.136, 0.143, 0.058, -0.005], abs=0.001)
