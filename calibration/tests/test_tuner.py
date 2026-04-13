"""Tests for calibration.tuner — grid enumeration, prediction, search."""

from __future__ import annotations

from datetime import date

from backtest.models import BacktestRecord, ScenarioSnapshot

from calibration.grid import Bucket, BucketKey
from calibration.tuner import (
    GRID_STEP,
    PROB_BOUNDS,
    confidence_tier,
    enumerate_prob_grid,
    predict_with_probs,
    search_sc_prob,
)


def _scn(code: str, prob: float, post_dlom: int) -> ScenarioSnapshot:
    return ScenarioSnapshot(code=code, name=code, prob=prob, pre_dlom=post_dlom, post_dlom=post_dlom)


def _record(
    ticker: str,
    *,
    scenarios: list[ScenarioSnapshot],
    price: float,
    horizon: str = "t12m",
    primary_method: str = "dcf_primary",
    analysis_date: date = date(2024, 1, 1),
    market: str = "US",
) -> BacktestRecord:
    return BacktestRecord(
        snapshot_id=f"snap-{ticker}",
        valuation_id=f"val-{ticker}",
        ticker=ticker,
        market=market,
        currency="USD",
        unit_multiplier=1,
        company_name="Test",
        legal_status="listed",
        analysis_date=analysis_date,
        predicted_value=100,
        scenarios=scenarios,
        primary_method=primary_method,
        **{f"price_{horizon}": price},
    )


class TestGridEnumeration:
    def test_all_points_sum_to_100(self):
        for triple in enumerate_prob_grid():
            assert sum(triple) == 100

    def test_all_points_within_bounds(self):
        lo, hi = PROB_BOUNDS
        for triple in enumerate_prob_grid():
            assert all(lo <= p <= hi for p in triple)

    def test_grid_step_honored(self):
        for triple in enumerate_prob_grid():
            assert all(p % GRID_STEP == 0 for p in triple)

    def test_includes_balanced_corner(self):
        # The default-balanced (35, 35, 30)-style point exists somewhere
        grid = enumerate_prob_grid()
        assert (50, 25, 25) in grid
        assert (30, 35, 35) in grid


class TestPredictWithProbs:
    def test_three_scenarios_weighted_correctly(self):
        scenarios = [_scn("A", 50, 100), _scn("B", 30, 200), _scn("C", 20, 50)]
        r = _record("X", scenarios=scenarios, price=100)
        # bull=200, base=100, bear=50; equal weight → 350/3
        result = predict_with_probs(r, {"bull": 33, "base": 33, "bear": 33})
        assert abs(result - (200 + 100 + 50) / 3) < 1e-6

    def test_renormalises_when_role_missing(self):
        # Two-scenario record has no 'base' role
        scenarios = [_scn("A", 50, 80), _scn("B", 50, 120)]
        r = _record("Y", scenarios=scenarios, price=100)
        # probs {bull:60, base:30, bear:10} → renormalise on bull/bear → 60/70 vs 10/70
        result = predict_with_probs(r, {"bull": 60, "base": 30, "bear": 10})
        expected = 120 * (60 / 70) + 80 * (10 / 70)
        assert abs(result - expected) < 1e-6


class TestConfidenceTier:
    def test_stable_requires_t12m_and_n_30(self):
        assert confidence_tier(30, "t12m") == "stable"
        assert confidence_tier(50, "t12m") == "stable"
        assert confidence_tier(29, "t12m") == "preliminary"

    def test_preliminary_short_horizons(self):
        assert confidence_tier(10, "t3m") == "preliminary"
        assert confidence_tier(10, "t6m") == "preliminary"
        assert confidence_tier(40, "t6m") == "preliminary"

    def test_insufficient_below_n_10(self):
        assert confidence_tier(9, "t12m") == "insufficient"
        assert confidence_tier(0, "t3m") == "insufficient"


class TestSearchSCProb:
    def _planted_bucket(self, *, n: int, true_probs: tuple[int, int, int]) -> Bucket:
        """Build a bucket where the realized price equals the weighted prediction
        under ``true_probs`` (bull/base/bear). Recovery should land near true_probs.
        """
        p_bull, p_base, p_bear = true_probs
        records = []
        for i in range(n):
            # Per-record values jitter so the bucket isn't degenerate
            bear_v = 50 + (i % 5)
            base_v = 100 + (i % 7)
            bull_v = 200 + (i % 11)
            scenarios = [
                _scn("BEAR", 25, bear_v),
                _scn("BASE", 50, base_v),
                _scn("BULL", 25, bull_v),
            ]
            true_price = (
                p_bull * bull_v + p_base * base_v + p_bear * bear_v
            ) / 100.0
            records.append(
                _record(
                    f"T{i}",
                    scenarios=scenarios,
                    price=true_price,
                    horizon="t12m",
                    analysis_date=date(2024, 1, 1),
                )
            )
        return Bucket(key=BucketKey("US", "dcf_primary", "t12m"), records=records)

    def test_recovers_planted_optimal_within_5pp(self):
        true_probs = (40, 35, 25)
        bucket = self._planted_bucket(n=30, true_probs=true_probs)
        rec = search_sc_prob(bucket)
        assert rec.tier == "stable"
        assert rec.recommended is not None
        for role, true_p in zip(("bull", "base", "bear"), true_probs):
            assert abs(rec.recommended[role] - true_p) <= 5

    def test_insufficient_bucket_yields_no_recommendation(self):
        bucket = self._planted_bucket(n=5, true_probs=(40, 35, 25))
        rec = search_sc_prob(bucket)
        assert rec.tier == "insufficient"
        assert rec.recommended is None
        assert any("suppressed" in n for n in rec.notes)

    def test_preliminary_tier_for_t6m_with_enough_samples(self):
        records = []
        for i in range(15):
            scenarios = [_scn("A", 50, 100), _scn("B", 25, 150), _scn("C", 25, 50)]
            records.append(
                _record(
                    f"T{i}",
                    scenarios=scenarios,
                    price=100.0 + i * 0.1,
                    horizon="t6m",
                    analysis_date=date(2024, 1, 1),
                )
            )
        bucket = Bucket(key=BucketKey("US", "dcf_primary", "t6m"), records=records)
        rec = search_sc_prob(bucket)
        assert rec.tier == "preliminary"
        assert rec.recommended is not None

    def test_recommended_mape_not_worse_than_baseline(self):
        bucket = self._planted_bucket(n=30, true_probs=(45, 30, 25))
        rec = search_sc_prob(bucket)
        assert rec.baseline_mape is not None
        assert rec.recommended_mape is not None
        assert rec.recommended_mape <= rec.baseline_mape + 1e-9
