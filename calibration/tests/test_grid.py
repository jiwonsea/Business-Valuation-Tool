"""Tests for calibration.grid — bucket partitioning and scenario role assignment."""

from __future__ import annotations

from datetime import date

from backtest.models import BacktestRecord, ScenarioSnapshot

from calibration.grid import (
    BucketKey,
    bucket_records,
    classify_scenarios,
    horizon_is_mature,
)


def _scn(code: str, prob: float, post_dlom: int) -> ScenarioSnapshot:
    return ScenarioSnapshot(code=code, name=code, prob=prob, pre_dlom=post_dlom, post_dlom=post_dlom)


def _record(
    *,
    ticker: str = "T1",
    market: str = "US",
    primary_method: str | None = "dcf_primary",
    analysis_date: date = date(2024, 1, 1),
    price_t3m: float | None = 100.0,
    price_t6m: float | None = 100.0,
    price_t12m: float | None = 100.0,
    scenarios: list[ScenarioSnapshot] | None = None,
    legal_status: str = "listed",
) -> BacktestRecord:
    if scenarios is None:
        scenarios = [_scn("A", 50, 100), _scn("B", 25, 130), _scn("C", 25, 70)]
    return BacktestRecord(
        snapshot_id=f"snap-{ticker}",
        valuation_id=f"val-{ticker}",
        ticker=ticker,
        market=market,
        currency="USD",
        unit_multiplier=1,
        company_name="Test",
        legal_status=legal_status,
        analysis_date=analysis_date,
        predicted_value=100,
        price_t3m=price_t3m,
        price_t6m=price_t6m,
        price_t12m=price_t12m,
        scenarios=scenarios,
        primary_method=primary_method,
    )


class TestClassifyScenarios:
    def test_three_scenarios_assigns_bull_base_bear_by_value(self):
        roles = classify_scenarios(
            [_scn("A", 40, 100), _scn("B", 30, 150), _scn("C", 30, 50)]
        )
        assert roles["bull"][0].code == "B"
        assert roles["base"][0].code == "A"
        assert roles["bear"][0].code == "C"

    def test_one_scenario_is_base(self):
        roles = classify_scenarios([_scn("X", 100, 50)])
        assert roles["base"][0].code == "X"
        assert roles["bull"] == []
        assert roles["bear"] == []

    def test_two_scenarios_skip_base(self):
        roles = classify_scenarios([_scn("A", 50, 80), _scn("B", 50, 120)])
        assert roles["bull"][0].code == "B"
        assert roles["bear"][0].code == "A"
        assert roles["base"] == []

    def test_four_scenarios_middle_two_become_base(self):
        roles = classify_scenarios(
            [
                _scn("A", 25, 100),
                _scn("B", 25, 150),
                _scn("C", 25, 50),
                _scn("D", 25, 110),
            ]
        )
        assert roles["bull"][0].code == "B"
        assert roles["bear"][0].code == "C"
        assert {s.code for s in roles["base"]} == {"A", "D"}

    def test_empty_input_returns_empty_roles(self):
        roles = classify_scenarios([])
        assert roles == {"bull": [], "base": [], "bear": []}

    def test_ties_broken_lexicographically(self):
        roles = classify_scenarios([_scn("Z", 50, 100), _scn("A", 50, 100)])
        assert roles["bear"][0].code == "A"
        assert roles["bull"][0].code == "Z"


class TestHorizonMaturity:
    def test_mature_when_enough_time_elapsed(self):
        r = _record(analysis_date=date(2024, 1, 1))
        today = date(2025, 1, 5)
        assert horizon_is_mature(r, "t3m", today=today)
        assert horizon_is_mature(r, "t6m", today=today)
        assert horizon_is_mature(r, "t12m", today=today)

    def test_not_mature_for_recent_record(self):
        r = _record(analysis_date=date(2025, 1, 1))
        today = date(2025, 2, 1)
        assert not horizon_is_mature(r, "t3m", today=today)
        assert not horizon_is_mature(r, "t12m", today=today)


class TestBucketRecords:
    def test_partitions_by_market_and_method_and_horizon(self):
        r_us_dcf = _record(ticker="A", market="US", primary_method="dcf_primary")
        r_kr_mult = _record(ticker="B", market="KR", primary_method="multiples")
        today = date(2026, 1, 1)
        buckets = bucket_records([r_us_dcf, r_kr_mult], today=today)
        keys = set(buckets.keys())
        assert BucketKey("US", "dcf_primary", "t3m") in keys
        assert BucketKey("US", "dcf_primary", "t6m") in keys
        assert BucketKey("US", "dcf_primary", "t12m") in keys
        assert BucketKey("KR", "multiples", "t12m") in keys

    def test_skips_unlisted(self):
        r = _record(legal_status="비상장")
        today = date(2026, 1, 1)
        assert bucket_records([r], today=today) == {}

    def test_skips_records_without_scenarios(self):
        r = _record(scenarios=[])
        today = date(2026, 1, 1)
        assert bucket_records([r], today=today) == {}

    def test_skips_horizon_with_missing_price(self):
        r = _record(price_t3m=None, price_t6m=200.0, price_t12m=None)
        today = date(2026, 1, 1)
        buckets = bucket_records([r], today=today)
        assert BucketKey("US", "dcf_primary", "t6m") in buckets
        assert BucketKey("US", "dcf_primary", "t3m") not in buckets
        assert BucketKey("US", "dcf_primary", "t12m") not in buckets

    def test_skips_immature_horizon_even_with_price(self):
        r = _record(analysis_date=date(2025, 12, 1))
        today = date(2026, 1, 1)
        buckets = bucket_records([r], today=today)
        assert buckets == {}

    def test_record_present_in_multiple_horizon_buckets(self):
        r = _record()
        today = date(2026, 1, 1)
        buckets = bucket_records([r], today=today)
        assert len(buckets) == 3
        for b in buckets.values():
            assert b.n == 1

    def test_unknown_method_falls_back_to_unknown(self):
        r = _record(primary_method=None)
        today = date(2026, 1, 1)
        buckets = bucket_records([r], today=today)
        assert any(k.sector == "unknown" for k in buckets.keys())
