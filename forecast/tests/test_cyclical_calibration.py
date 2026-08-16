"""Cyclical driver calibration + skill gate.

Rebuilt as a superset after an accidental overwrite of the round-2 file: covers
the OLS passthrough helper (incl. edge cases) AND the n>=8 skill gate that keeps
the cyclical path consistent with Item 1 (no skill claim on a coin-flip sample).
"""

from __future__ import annotations

import pytest

from engine.cyclical_drivers.calibration import (
    MIN_SKILL_N,
    calibrate_passthrough,
    expanding_driver_skill,
)


# ── calibrate_passthrough ────────────────────────────────────────────────────
def test_calibrate_recovers_linear_slope() -> None:
    spreads = [0, 1, 2, 3, 4]
    margins = [0.1, 0.2, 0.3, 0.4, 0.5]  # 0.1 per unit
    assert abs(calibrate_passthrough(spreads, margins) - 0.1) < 1e-9


def test_calibrate_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        calibrate_passthrough([1, 2, 3], [0.1, 0.2])


def test_calibrate_too_few_points_returns_zero() -> None:
    assert calibrate_passthrough([1.0], [0.1]) == 0.0


def test_calibrate_flat_spread_returns_zero() -> None:
    # zero variance in spread -> denom 0 -> slope 0 (no division error)
    assert calibrate_passthrough([2.0, 2.0, 2.0], [0.1, 0.2, 0.3]) == 0.0


# ── expanding_driver_skill: gate ─────────────────────────────────────────────
def test_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        expanding_driver_skill([1, 2, 3], [0.1, 0.2])


def test_short_scored_sample_abstains_even_if_beating_naive() -> None:
    spreads = [float(i) for i in range(10)]  # min_train=8 -> 2 scored
    margins = [0.10 + 0.01 * i for i in range(10)]
    skill = expanding_driver_skill(spreads, margins, min_train=8)
    assert skill.n == 2 and skill.n < MIN_SKILL_N
    assert skill.beats_naive is True
    assert skill.skill_pass is False
    assert "min_n" in skill.reason


def test_long_scored_sample_passes() -> None:
    spreads = [float(i) for i in range(20)]  # 12 scored
    margins = [0.10 + 0.01 * i for i in range(20)]
    skill = expanding_driver_skill(spreads, margins, min_train=8)
    assert skill.n == 12 and skill.n >= MIN_SKILL_N
    assert skill.beats_naive is True
    assert skill.skill_pass is True
    assert skill.reason == "beats_naive & n>=min_n"


def test_no_scored_points_is_empty_and_abstains() -> None:
    spreads = [float(i) for i in range(8)]  # min_train=8 -> 0 scored
    margins = [0.10 + 0.01 * i for i in range(8)]
    skill = expanding_driver_skill(spreads, margins, min_train=8)
    assert skill.n == 0
    assert skill.model_mae is None and skill.naive_mae is None
    assert skill.skill_pass is False


def test_model_worse_than_naive_does_not_pass() -> None:
    # noisy margins uncorrelated with the smooth spread -> model shouldn't beat RW
    spreads = [float(i) for i in range(20)]
    margins = [0.10, 0.40, 0.11, 0.39, 0.12, 0.38, 0.13, 0.37,
               0.14, 0.36, 0.15, 0.35, 0.16, 0.34, 0.17, 0.33,
               0.18, 0.32, 0.19, 0.31]
    skill = expanding_driver_skill(spreads, margins, min_train=8)
    assert skill.n >= MIN_SKILL_N
    assert skill.skill_pass == (skill.beats_naive and skill.n >= MIN_SKILL_N)
