"""Synthetic, network-independent tests for engine.skill_metrics.

Hand-computed expectations for MASE, Theil U2, surprise-direction and the
None/graceful paths. No DART / yfinance dependency.
"""

from __future__ import annotations

import pytest

from engine.skill_metrics import SkillRow, compute_skill


def _row(label, actual_rev, model_rev, rw_rev, actual_eps=None, model_eps=None, rw_eps=None):
    return SkillRow(
        quarter_label=label,
        actual_revenue=actual_rev,
        model_revenue=model_rev,
        rw_revenue=rw_rev,
        actual_eps=actual_eps,
        model_eps=model_eps,
        rw_eps=rw_eps,
    )


def test_mase_equals_one_when_model_equals_rw():
    rows = [
        _row("Q1", actual_rev=100.0, model_rev=110.0, rw_rev=110.0),
        _row("Q2", actual_rev=100.0, model_rev=90.0, rw_rev=90.0),
    ]
    skill = compute_skill(rows)
    assert skill.mase_revenue == pytest.approx(1.0)
    assert skill.theil_u2_revenue == pytest.approx(1.0)


def test_mase_below_one_when_model_beats_rw():
    # model err |5|,|5| -> MAE 5 ; rw err |10|,|10| -> MAE 10 ; MASE 0.5
    rows = [
        _row("Q1", actual_rev=100.0, model_rev=105.0, rw_rev=110.0),
        _row("Q2", actual_rev=100.0, model_rev=95.0, rw_rev=90.0),
    ]
    skill = compute_skill(rows)
    assert skill.mase_revenue == pytest.approx(0.5)
    # RMSE ratio identical here (symmetric errors) -> U2 0.5
    assert skill.theil_u2_revenue == pytest.approx(0.5)


def test_mase_above_one_when_model_loses_to_rw():
    # model MAE 20, rw MAE 10 -> MASE 2.0
    rows = [
        _row("Q1", actual_rev=100.0, model_rev=120.0, rw_rev=110.0),
        _row("Q2", actual_rev=100.0, model_rev=80.0, rw_rev=90.0),
    ]
    skill = compute_skill(rows)
    assert skill.mase_revenue == pytest.approx(2.0)


def test_theil_u2_hand_computed():
    # model sq err: 4, 0 -> RMSE sqrt(2) ; rw sq err: 16, 4 -> RMSE sqrt(10)
    rows = [
        _row("Q1", actual_rev=100.0, model_rev=102.0, rw_rev=104.0),
        _row("Q2", actual_rev=100.0, model_rev=100.0, rw_rev=98.0),
    ]
    skill = compute_skill(rows)
    assert skill.theil_u2_revenue == pytest.approx((2.0 / 10.0) ** 0.5)


def test_rw_hit_ratio_counts_nonnegative_actual_qoq():
    # actual_qoq = actual - rw : Q1 +10 (hit), Q2 -10 (miss), Q3 0 (hit, >=0)
    rows = [
        _row("Q1", actual_rev=110.0, model_rev=0.0, rw_rev=100.0),
        _row("Q2", actual_rev=90.0, model_rev=0.0, rw_rev=100.0),
        _row("Q3", actual_rev=100.0, model_rev=0.0, rw_rev=100.0),
    ]
    skill = compute_skill(rows)
    assert skill.rw_hit_ratio_direction == pytest.approx(2.0 / 3.0)


def test_naive_rw_revenue_mape():
    # |rw-actual|/|actual| : 0.10, 0.10 -> 0.10
    rows = [
        _row("Q1", actual_rev=100.0, model_rev=0.0, rw_rev=110.0),
        _row("Q2", actual_rev=100.0, model_rev=0.0, rw_rev=90.0),
    ]
    skill = compute_skill(rows)
    assert skill.naive_rw_revenue_mape == pytest.approx(0.10)


def test_surprise_direction_same_and_opposite_side():
    # est=10. Q1: model 12 (>est), actual 11 (>est) -> same side -> hit
    #         Q2: model 12 (>est), actual 8 (<est)   -> opposite   -> miss
    history = {
        "Q1": {"actual": 11.0, "estimate": 10.0, "surprise_pct": 0.1},
        "Q2": {"actual": 8.0, "estimate": 10.0, "surprise_pct": -0.2},
    }
    rows = [
        _row("Q1", actual_rev=100.0, model_rev=100.0, rw_rev=100.0,
             actual_eps=11.0, model_eps=12.0, rw_eps=9.0),
        _row("Q2", actual_rev=100.0, model_rev=100.0, rw_rev=100.0,
             actual_eps=8.0, model_eps=12.0, rw_eps=9.0),
    ]
    skill = compute_skill(rows, history)
    assert skill.surprise_direction_accuracy == pytest.approx(0.5)
    assert skill.n_surprise_scored == 2


def test_surprise_skips_quarter_without_history():
    # Only Q1 has a vintage estimate; Q2 missing -> excluded, N == 1.
    history = {"Q1": {"actual": 11.0, "estimate": 10.0, "surprise_pct": 0.1}}
    rows = [
        _row("Q1", actual_rev=100.0, model_rev=100.0, rw_rev=100.0,
             actual_eps=11.0, model_eps=12.0, rw_eps=9.0),
        _row("Q2", actual_rev=100.0, model_rev=100.0, rw_rev=100.0,
             actual_eps=8.0, model_eps=12.0, rw_eps=9.0),
    ]
    skill = compute_skill(rows, history)
    assert skill.n_surprise_scored == 1
    assert skill.surprise_direction_accuracy == pytest.approx(1.0)


def test_skill_score_vs_consensus_hand_computed():
    # est err |2|,|2| -> MAE 2 ; model err |1|,|1| -> MAE 1 ; score 1 - 1/2 = 0.5
    history = {
        "Q1": {"actual": 10.0, "estimate": 12.0, "surprise_pct": 0.0},
        "Q2": {"actual": 10.0, "estimate": 8.0, "surprise_pct": 0.0},
    }
    rows = [
        _row("Q1", actual_rev=100.0, model_rev=100.0, rw_rev=100.0,
             actual_eps=10.0, model_eps=11.0, rw_eps=9.0),
        _row("Q2", actual_rev=100.0, model_rev=100.0, rw_rev=100.0,
             actual_eps=10.0, model_eps=9.0, rw_eps=11.0),
    ]
    skill = compute_skill(rows, history)
    assert skill.skill_score_eps_vs_consensus == pytest.approx(0.5)


def test_no_consensus_history_yields_none_consensus_metrics():
    rows = [
        _row("Q1", actual_rev=100.0, model_rev=105.0, rw_rev=110.0,
             actual_eps=10.0, model_eps=10.5, rw_eps=11.0),
        _row("Q2", actual_rev=100.0, model_rev=95.0, rw_rev=90.0,
             actual_eps=10.0, model_eps=9.5, rw_eps=9.0),
    ]
    skill = compute_skill(rows, consensus_history=None)
    assert skill.skill_score_eps_vs_consensus is None
    assert skill.surprise_direction_accuracy is None
    assert skill.n_surprise_scored == 0
    # RW metrics still computed.
    assert skill.mase_revenue == pytest.approx(0.5)
    assert skill.mase_eps == pytest.approx(0.5)


def test_empty_rows_yields_all_none():
    skill = compute_skill([])
    assert skill.n == 0
    assert skill.n_eps == 0
    assert skill.mase_revenue is None
    assert skill.theil_u2_revenue is None
    assert skill.naive_rw_revenue_mape is None
    assert skill.rw_hit_ratio_direction is None
    assert skill.n_surprise_scored == 0


def test_eps_metrics_skip_rows_missing_eps():
    # Only Q1 has full EPS; Q2 actual_eps None -> EPS MASE over 1 row.
    rows = [
        _row("Q1", actual_rev=100.0, model_rev=100.0, rw_rev=100.0,
             actual_eps=10.0, model_eps=11.0, rw_eps=12.0),
        _row("Q2", actual_rev=100.0, model_rev=100.0, rw_rev=100.0),
    ]
    skill = compute_skill(rows)
    assert skill.n == 2
    assert skill.n_eps == 1
    # model eps MAE 1, rw eps MAE 2 -> 0.5
    assert skill.mase_eps == pytest.approx(0.5)


def test_trailing_8q_skill_is_reported_for_long_window():
    rows = [
        _row(
            f"Q{i}",
            actual_rev=100.0,
            model_rev=100.0,
            rw_rev=100.0 + i,
            actual_eps=10.0,
            model_eps=10.0,
            rw_eps=10.0 + i,
        )
        for i in range(1, 10)
    ]
    skill = compute_skill(rows)
    assert skill.n == 9
    assert skill.n_eps == 9
    assert skill.trailing_8q is not None
    assert skill.trailing_8q.n == 8
    assert skill.trailing_8q.n_eps == 8
    assert skill.trailing_8q.trailing_8q is None
