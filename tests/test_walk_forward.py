"""Tests for the walk-forward CV harness in :mod:`calibration.walk_forward`."""

from __future__ import annotations

from datetime import date, timedelta

from backtest.models import BacktestRecord, ScenarioSnapshot
from calibration.walk_forward import (
    FoldResult,
    WalkForwardResult,
    render_report,
    tune_walk_forward,
    walk_forward_splits,
    write_report,
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


def test_walk_forward_splits_no_same_date_leakage():
    """Records sharing one analysis_date must not split across train/test.

    Build a dataset where every "week" has 3 records on the same date. The
    old index-based split would bisect such a group at the fold boundary,
    leaking future same-day info into train. The fix pushes the boundary
    past the shared-date block so train end-date is strictly before test
    start-date.
    """
    records = []
    for week in range(15):
        shared_date = date(2024, 1, 1) + timedelta(days=week * 7)
        for _ in range(3):
            r = _record(day_offset=week * 7, actual_t6m=100.0)
            r.analysis_date = shared_date
            records.append(r)

    splits = walk_forward_splits(records, n_splits=5, min_train_size=10)
    assert splits, "dataset should still produce folds"
    for train, test in splits:
        train_dates = {r.analysis_date for r in train}
        test_dates = {r.analysis_date for r in test}
        assert not (train_dates & test_dates), (
            f"same-date leakage: overlap={train_dates & test_dates}"
        )
        assert max(train_dates) < min(test_dates)


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


def test_suppressed_folds_contribute_baseline_to_aggregate(monkeypatch):
    """When a fold suppresses its recommendation, mean_test_mape must still
    include that fold's baseline_test_mape. Previously the aggregation
    silently dropped suppressed folds, biasing mean_test_mape toward only
    the folds that emitted a recommendation (docstring contract violated).

    Deterministic: patch search_sc_prob so every other fold returns
    recommended=None (suppressed) while the rest emit a normal
    recommendation. Then verify the aggregate uses baseline_test_mape for
    the suppressed folds.
    """
    import calibration.walk_forward as wf
    from calibration.tuner import Recommendation

    call_state = {"i": 0}

    def fake_search_sc_prob(bucket):
        i = call_state["i"]
        call_state["i"] += 1
        baseline = {"bull": 25.0, "base": 50.0, "bear": 25.0}
        # Odd folds suppressed (recommended=None), even folds emit a rec.
        if i % 2 == 1:
            return Recommendation(
                bucket_key=bucket.key,
                n=len(bucket.records),
                tier="preliminary",
                baseline=baseline,
                recommended=None,
                baseline_mape=0.10,
                recommended_mape=None,
                baseline_coverage=None,
                recommended_coverage=None,
                notes=["suppressed"],
            )
        return Recommendation(
            bucket_key=bucket.key,
            n=len(bucket.records),
            tier="preliminary",
            baseline=baseline,
            recommended={"bull": 30.0, "base": 45.0, "bear": 25.0},
            baseline_mape=0.10,
            recommended_mape=0.08,
            baseline_coverage=None,
            recommended_coverage=None,
            notes=[],
        )

    monkeypatch.setattr(wf, "search_sc_prob", fake_search_sc_prob)

    records = _build_dataset(30)
    result = tune_walk_forward(records, horizon="t6m", n_splits=5)
    assert result.folds, "synthetic dataset should produce folds"

    suppressed = [f for f in result.folds if f.recommended_probs is None]
    emitted = [f for f in result.folds if f.recommended_probs is not None]
    assert suppressed, "patch should have produced suppressed folds"
    assert emitted, "patch should have produced emitted folds"

    # Every suppressed fold must have baseline_test_mape populated (from the
    # patched recommendation's baseline). Aggregate must include them.
    for f in suppressed:
        assert f.baseline_test_mape is not None
        assert f.test_mape is None  # current contract: None signals suppression

    expected_values: list[float] = []
    for f in result.folds:
        v = f.test_mape if f.test_mape is not None else f.baseline_test_mape
        if v is not None:
            expected_values.append(v)
    expected_mean = sum(expected_values) / len(expected_values)
    assert result.mean_test_mape is not None
    assert abs(result.mean_test_mape - expected_mean) < 1e-9
    # The bug: the old code dropped suppressed folds, so mean_test_mape
    # would have equaled the mean over emitted folds only. Verify the fix
    # uses more values than just the emitted subset.
    emitted_values = [f.test_mape for f in emitted if f.test_mape is not None]
    assert len(expected_values) > len(emitted_values)


def test_tune_walk_forward_empty_returns_notes():
    """Empty input yields a result with no folds and a diagnostic note."""
    result = tune_walk_forward([], horizon="t6m", n_splits=5)
    assert result.folds == []
    assert result.mean_test_mape is None
    assert result.notes
    assert "insufficient data" in result.notes[0]


# ── render_report / write_report ──


def test_render_report_with_folds_contains_aggregate_and_per_fold():
    records = _build_dataset(30)
    result = tune_walk_forward(records, horizon="t6m", n_splits=5)
    text = render_report(result, report_date=date(2026, 4, 13))
    assert "Walk-Forward CV Report -- 2026-04-13" in text
    assert "US/dcf_primary/t6m" in text
    assert "## Aggregate" in text
    assert "## Per-fold" in text
    assert "Mean train MAPE" in text
    for fold in result.folds:
        assert f"| {fold.fold_index} |" in text


def test_render_report_empty_emits_placeholder():
    result = tune_walk_forward([], horizon="t6m", n_splits=5)
    text = render_report(result, report_date=date(2026, 4, 13))
    assert "No folds were produced" in text
    assert "## Aggregate" not in text
    assert "rerun" in text.lower() or "re-run" in text.lower()


def test_cli_runs_per_market_sector_bucket(monkeypatch, tmp_path, capsys):
    """CLI must bucket by (market, primary_method) and emit one summary per."""
    import sys

    import calibration.walk_forward as wf

    us_records = _build_dataset(30)  # market=US, primary_method=dcf_primary
    kr_records = [
        _record(
            day_offset=i * 7,
            actual_t6m=100.0,
            market="KR",
            primary_method="sotp",
        )
        for i in range(30)
    ]
    dataset = us_records + kr_records

    monkeypatch.setattr(wf, "DEFAULT_REPORT_DIR", tmp_path)

    import backtest.dataset as bd
    monkeypatch.setattr(bd, "build_backtest_dataset", lambda **kw: dataset)

    monkeypatch.setattr(sys, "argv", ["walk_forward", "--n-splits", "5"])
    wf.main()

    out = capsys.readouterr().out
    assert "KR/sotp/t6m" in out
    assert "US/dcf_primary/t6m" in out
    assert any((tmp_path / "KR_sotp").glob("walk_forward_*.md"))
    assert any((tmp_path / "US_dcf_primary").glob("walk_forward_*.md"))


def test_write_report_creates_file(tmp_path):
    records = _build_dataset(30)
    result = tune_walk_forward(records, horizon="t6m", n_splits=5)
    out = write_report(result, output_dir=tmp_path, report_date=date(2026, 4, 13))
    assert out.exists()
    assert out.name == "walk_forward_2026-04-13.md"
    assert "Walk-Forward CV Report" in out.read_text(encoding="utf-8")
