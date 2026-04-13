"""Tests for the walk-forward CV harness in :mod:`calibration.walk_forward`."""

from __future__ import annotations

from datetime import date, timedelta

from backtest.models import BacktestRecord, ScenarioSnapshot
from calibration.walk_forward import (
    FoldResult,
    WalkForwardResult,
    tune_walk_forward,
    walk_forward_splits,
)


def _scenarios(bull: int, base: int, bear: int) -> list[ScenarioSnapshot]:
    return [
        ScenarioSnapshot(code="bull", name="bull", prob=25, pre_dlom=bull, post_dlom=bull),
        ScenarioSnapshot(code="base", name="base", prob=50, pre_dlom=base, post_dlom=base),
        ScenarioSnapshot(code="bear", name="bear", prob=25, pre_dlom=bear, post_dlom=bear),
    ]


def _record(
    *,
    day_offset: int,
    actual_t6m: float,
    bull: int = 140,
    base: int = 100,
    bear: int = 70,
    market: str = "US",
    primary_method: str = "dcf_primary",
) -> BacktestRecord:
    return BacktestRecord(
        snapshot_id=f"snap-{day_offset}",
        valuation_id=f"val-{day_offset}",
        ticker="TEST",
        market=market,
        currency="USD",
        unit_multiplier=1,
        company_name="Test Corp",
        legal_status="상장",
        analysis_date=date(2024, 1, 1) + timedelta(days=day_offset),
        predicted_value=base,
        price_at_prediction=actual_t6m,
        price_t6m=actual_t6m,
        scenarios=_scenarios(bull, base, bear),
        primary_method=primary_method,
    )


def _build_dataset(n: int = 30, *, actual_factory=None) -> list[BacktestRecord]:
    records = []
    for i in range(n):
        actual = actual_factory(i) if actual_factory else 100.0
        records.append(_record(day_offset=i * 7, actual_t6m=actual))
    return records


# ── walk_forward_splits ──


def test_walk_forward_splits_time_order():
    """Train end date must be <= test start date for every fold."""
    records = _build_dataset(30)
    splits = walk_forward_splits(records, n_splits=5)
    assert splits, "expected at least one split"
    for train, test in splits:
        assert max(r.analysis_date for r in train) <= min(r.analysis_date for r in test)


def test_walk_forward_splits_expanding():
    """Train sizes are monotonically non-decreasing across folds."""
    records = _build_dataset(30)
    splits = walk_forward_splits(records, n_splits=5)
    sizes = [len(train) for train, _ in splits]
    assert sizes == sorted(sizes)
    assert len(set(sizes)) > 1, "expanding window should grow over folds"


def test_walk_forward_insufficient_data():
    """Datasets below the minimum produce an empty split list."""
    records = _build_dataset(5)
    assert walk_forward_splits(records, n_splits=5, min_train_size=10) == []
    assert walk_forward_splits([], n_splits=5) == []


# ── tune_walk_forward ──


def test_tune_walk_forward_smoke():
    """End-to-end run over synthetic data populates the aggregate fields.

    Requested 5 splits but the first fold may be dropped when its train slice
    is below ``min_train_size``; assert at least n_splits-1 folds materialise.
    """
    records = _build_dataset(30)
    result = tune_walk_forward(records, horizon="t6m", n_splits=5)
    assert isinstance(result, WalkForwardResult)
    assert result.market == "US"
    assert result.sector == "dcf_primary"
    assert result.horizon == "t6m"
    assert 4 <= len(result.folds) <= 5
    assert all(isinstance(f, FoldResult) for f in result.folds)
    assert all(f.train_size > 0 and f.test_size > 0 for f in result.folds)


def test_tune_walk_forward_overfit_gap():
    """A regime shift between train and test produces a positive overfit gap.

    Train slice (early records) prices cluster around the bear scenario; test
    slice (later records) shifts toward the bull scenario. A prob mix tuned on
    train will under-predict on test, so test MAPE should exceed train MAPE.
    """
    def actual_factory(i: int) -> float:
        return 70.0 if i < 18 else 140.0

    records = _build_dataset(30, actual_factory=actual_factory)
    result = tune_walk_forward(records, horizon="t6m", n_splits=5)
    assert result.folds, "synthetic dataset should produce folds"
    assert result.mean_train_mape is not None
    assert result.mean_test_mape is not None
    assert result.overfitting_gap is not None
    assert result.overfitting_gap > 0, (
        f"expected positive overfit gap, got {result.overfitting_gap}"
    )


def test_tune_walk_forward_empty_returns_notes():
    """Empty input yields a result with no folds and a diagnostic note."""
    result = tune_walk_forward([], horizon="t6m", n_splits=5)
    assert result.folds == []
    assert result.mean_test_mape is None
    assert result.notes
    assert "insufficient data" in result.notes[0]
