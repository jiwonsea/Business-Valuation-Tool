"""Tests for backtest calibration infrastructure."""

from __future__ import annotations

import math
from datetime import date

import pytest

from backtest.models import BacktestRecord, ScenarioSnapshot
from backtest.metrics import (
    calc_forecast_price_error,
    calc_gap_closure,
    calc_interval_score,
    calc_calibration_curve,
    calc_forecast_error_by_method,
)


# ── Helpers ──


def _make_record(
    predicted_value: int = 50,
    unit_multiplier: int = 1,
    price_t0: float | None = None,
    price_t3m: float | None = None,
    price_t6m: float | None = None,
    price_t12m: float | None = None,
    price_at_prediction: float | None = None,
    gap_ratio: float | None = None,
    scenarios: list[ScenarioSnapshot] | None = None,
    legal_status: str = "상장",
    currency: str = "USD",
) -> BacktestRecord:
    return BacktestRecord(
        snapshot_id="snap-1",
        valuation_id="val-1",
        ticker="TEST",
        market="US",
        currency=currency,
        unit_multiplier=unit_multiplier,
        company_name="Test Corp",
        legal_status=legal_status,
        analysis_date=date(2025, 1, 1),
        predicted_value=predicted_value,
        predicted_gap_ratio=gap_ratio,
        price_at_prediction=price_at_prediction,
        wacc_pct=10.0,
        price_t0=price_t0,
        price_t3m=price_t3m,
        price_t6m=price_t6m,
        price_t12m=price_t12m,
        scenarios=scenarios or [],
    )


def _make_scenarios(
    values: list[tuple[str, float, int, int]],
) -> list[ScenarioSnapshot]:
    """Create scenario snapshots from (code, prob, pre_dlom, post_dlom) tuples."""
    return [
        ScenarioSnapshot(code=code, name=code, prob=prob, pre_dlom=pre, post_dlom=post)
        for code, prob, pre, post in values
    ]


# ═══ 6-1. Forecast-to-Price Error ═══


class TestForecastPriceError:
    def test_perfect_prediction(self):
        """Predicted == actual → MAPE = 0."""
        r = _make_record(predicted_value=100, unit_multiplier=1, price_t6m=100.0)
        result = calc_forecast_price_error([r], "t6m")
        assert result["mape"] == pytest.approx(0.0)
        assert result["median_ape"] == pytest.approx(0.0)
        assert result["log_ratio_mean"] == pytest.approx(0.0)
        assert result["n"] == 1

    def test_known_error(self):
        """Known values → exact MAPE/median/log_ratio."""
        r1 = _make_record(predicted_value=120, unit_multiplier=1, price_t6m=100.0)
        r2 = _make_record(predicted_value=80, unit_multiplier=1, price_t6m=100.0)
        result = calc_forecast_price_error([r1, r2], "t6m")
        # APE: |120-100|/100=0.2, |80-100|/100=0.2 → MAPE=0.2
        assert result["mape"] == pytest.approx(0.2)
        assert result["median_ape"] == pytest.approx(0.2)
        # log: ln(120/100)=0.1823, ln(80/100)=-0.2231 → mean=-0.0204
        assert result["log_ratio_mean"] == pytest.approx(
            (math.log(1.2) + math.log(0.8)) / 2, abs=1e-4
        )
        assert result["n"] == 2

    def test_kr_currency_normalization(self):
        """KR unit_multiplier correctly converts predicted_value to native currency."""
        # predicted_value=50 in 백만원 (unit_mult=1_000_000) → 50,000,000 KRW
        # market price = 50,000,000 KRW → MAPE = 0
        r = _make_record(
            predicted_value=50,
            unit_multiplier=1_000_000,
            price_t6m=50_000_000.0,
            currency="KRW",
        )
        result = calc_forecast_price_error([r], "t6m")
        assert result["mape"] == pytest.approx(0.0)
        assert result["n"] == 1

    def test_kr_currency_without_normalization_would_fail(self):
        """Without normalization, KR MAPE would be ~100% — this verifies it's NOT."""
        r = _make_record(
            predicted_value=50,
            unit_multiplier=1_000_000,
            price_t6m=55_000_000.0,  # 10% higher
            currency="KRW",
        )
        result = calc_forecast_price_error([r], "t6m")
        # Should be ~9.09% error, NOT ~100%
        assert result["mape"] is not None
        assert result["mape"] < 0.15  # Definitely not near 1.0
        expected = abs(50_000_000 - 55_000_000) / 55_000_000
        assert result["mape"] == pytest.approx(expected, abs=1e-4)

    def test_empty_records(self):
        result = calc_forecast_price_error([], "t6m")
        assert result["n"] == 0
        assert result["mape"] is None

    def test_unlisted_excluded(self):
        """Unlisted companies are excluded from metrics."""
        r = _make_record(predicted_value=100, price_t6m=100.0, legal_status="비상장")
        result = calc_forecast_price_error([r], "t6m")
        assert result["n"] == 0

    def test_missing_price_excluded(self):
        """Records with None price at horizon are excluded."""
        r = _make_record(predicted_value=100, price_t6m=None)
        result = calc_forecast_price_error([r], "t6m")
        assert result["n"] == 0


# ═══ 6-2. Gap Closure ═══


class TestGapClosure:
    def test_full_convergence(self):
        """Price moves from t0 to exactly predicted → closure = 1.0."""
        r = _make_record(
            predicted_value=100,
            unit_multiplier=1,
            price_at_prediction=80.0,
            price_t6m=100.0,
        )
        result = calc_gap_closure([r], "t6m")
        assert result["mean_closure"] == pytest.approx(1.0)
        assert result["positive_closure_rate"] == pytest.approx(1.0)

    def test_no_movement(self):
        """Price unchanged → closure = 0.0."""
        r = _make_record(
            predicted_value=100,
            unit_multiplier=1,
            price_at_prediction=80.0,
            price_t6m=80.0,
        )
        result = calc_gap_closure([r], "t6m")
        assert result["mean_closure"] == pytest.approx(0.0)
        assert result["positive_closure_rate"] == pytest.approx(0.0)

    def test_opposite_direction(self):
        """Price moves away from predicted → closure < 0."""
        r = _make_record(
            predicted_value=100,
            unit_multiplier=1,
            price_at_prediction=80.0,
            price_t6m=70.0,
        )
        result = calc_gap_closure([r], "t6m")
        # closure = (70-80)/(100-80) = -10/20 = -0.5
        assert result["mean_closure"] == pytest.approx(-0.5)

    def test_falling_market_correct_undervaluation(self):
        """Falling market where undervaluation call is still correct (gap closes)."""
        # Predicted=100, T0=80 (gap_ratio>0, undervalued)
        # Market falls to 85 — gap still closed partially
        r = _make_record(
            predicted_value=100,
            unit_multiplier=1,
            price_at_prediction=80.0,
            price_t6m=85.0,
        )
        result = calc_gap_closure([r], "t6m")
        # closure = (85-80)/(100-80) = 5/20 = 0.25 > 0 → correct signal
        assert result["mean_closure"] == pytest.approx(0.25)
        assert result["positive_closure_rate"] == pytest.approx(1.0)

    def test_overvaluation_gap_closure(self):
        """Overvalued prediction: predicted < t0. Price drops → gap closes."""
        r = _make_record(
            predicted_value=60,
            unit_multiplier=1,
            price_at_prediction=80.0,
            price_t6m=70.0,
        )
        result = calc_gap_closure([r], "t6m")
        # gap = 60 - 80 = -20, movement = 70 - 80 = -10
        # closure = -10 / -20 = 0.5
        assert result["mean_closure"] == pytest.approx(0.5)

    def test_empty_records(self):
        result = calc_gap_closure([], "t6m")
        assert result["n"] == 0

    def test_no_gap_skipped(self):
        """When predicted == t0, there's no gap → record skipped."""
        r = _make_record(
            predicted_value=100,
            unit_multiplier=1,
            price_at_prediction=100.0,
            price_t6m=110.0,
        )
        result = calc_gap_closure([r], "t6m")
        assert result["n"] == 0  # Skipped due to zero gap


# ═══ 6-3. Interval Score ═══


class TestIntervalScore:
    def test_actual_inside_range(self):
        """Actual price within scenario range → covered."""
        scenarios = _make_scenarios(
            [
                ("Bear", 25, 70, 70),
                ("Base", 50, 100, 100),
                ("Bull", 25, 130, 130),
            ]
        )
        r = _make_record(
            predicted_value=100, unit_multiplier=1, price_t6m=95.0, scenarios=scenarios
        )
        result = calc_interval_score([r], "t6m")
        assert result["coverage_rate"] == pytest.approx(1.0)
        assert result["n"] == 1

    def test_actual_outside_range(self):
        """Actual price outside scenario range → not covered."""
        scenarios = _make_scenarios(
            [
                ("Bear", 25, 70, 70),
                ("Base", 50, 100, 100),
                ("Bull", 25, 130, 130),
            ]
        )
        r = _make_record(
            predicted_value=100, unit_multiplier=1, price_t6m=150.0, scenarios=scenarios
        )
        result = calc_interval_score([r], "t6m")
        assert result["coverage_rate"] == pytest.approx(0.0)

    def test_interval_width(self):
        """Width = (max - min) / predicted."""
        scenarios = _make_scenarios(
            [
                ("Bear", 25, 80, 80),
                ("Bull", 75, 120, 120),
            ]
        )
        r = _make_record(
            predicted_value=100, unit_multiplier=1, price_t6m=100.0, scenarios=scenarios
        )
        result = calc_interval_score([r], "t6m")
        # width = (120-80)/100 = 0.4
        assert result["mean_interval_width"] == pytest.approx(0.4)

    def test_no_scenarios(self):
        """Record with no scenarios → excluded."""
        r = _make_record(predicted_value=100, price_t6m=100.0, scenarios=[])
        result = calc_interval_score([r], "t6m")
        assert result["n"] == 0

    def test_kr_unit_multiplier_applied(self):
        """Scenario values multiplied by unit_multiplier for range comparison."""
        scenarios = _make_scenarios(
            [
                ("Bear", 25, 40, 40),
                ("Base", 50, 50, 50),
                ("Bull", 25, 60, 60),
            ]
        )
        # unit_multiplier=1M → range = [40M, 60M], actual = 45M → covered
        r = _make_record(
            predicted_value=50,
            unit_multiplier=1_000_000,
            price_t6m=45_000_000.0,
            scenarios=scenarios,
            currency="KRW",
        )
        result = calc_interval_score([r], "t6m")
        assert result["coverage_rate"] == pytest.approx(1.0)


# ═══ 6-4. Calibration Curve ═══


class TestCalibrationCurve:
    def test_insufficient_data(self):
        """Fewer than 30 observations → returns None."""
        scenarios = _make_scenarios(
            [
                ("Bear", 20, 80, 80),
                ("Base", 50, 100, 100),
                ("Bull", 30, 120, 120),
            ]
        )
        records = [
            _make_record(
                predicted_value=100,
                unit_multiplier=1,
                price_t6m=float(95 + i),
                scenarios=scenarios,
            )
            for i in range(5)
        ]
        result = calc_calibration_curve(records, "t6m", min_total_observations=30)
        assert result is None

    def test_sufficient_data_returns_bins(self):
        """With enough data, returns calibration bins."""
        scenarios = _make_scenarios(
            [
                ("Bear", 15, 80, 80),
                ("Base", 50, 100, 100),
                ("Bull", 35, 120, 120),
            ]
        )
        # 15 records × 3 scenarios = 45 observations
        records = [
            _make_record(
                predicted_value=100,
                unit_multiplier=1,
                price_t6m=float(95 + i % 10),
                scenarios=scenarios,
            )
            for i in range(15)
        ]
        result = calc_calibration_curve(
            records, "t6m", n_bins=5, min_total_observations=30, min_bin_samples=5
        )
        assert result is not None
        assert len(result) > 0
        for b in result:
            assert "bin_label" in b
            assert "assigned_prob_mean" in b
            assert "realized_freq" in b
            assert "count" in b


# ═══ BacktestRecord Model ═══


class TestBacktestRecord:
    def test_predicted_value_native(self):
        r = _make_record(predicted_value=50, unit_multiplier=1_000_000)
        assert r.predicted_value_native == 50_000_000.0

    def test_is_listed(self):
        r1 = _make_record(legal_status="상장")
        r2 = _make_record(legal_status="listed")
        r3 = _make_record(legal_status="비상장")
        assert r1.is_listed is True
        assert r2.is_listed is True
        assert r3.is_listed is False

    def test_scenario_range_native(self):
        scenarios = _make_scenarios(
            [
                ("Bear", 25, 70, 70),
                ("Bull", 75, 130, 130),
            ]
        )
        r = _make_record(unit_multiplier=100, scenarios=scenarios)
        lo, hi = r.scenario_range_native()
        assert lo == 7000
        assert hi == 13000

    def test_scenario_range_empty(self):
        r = _make_record(scenarios=[])
        assert r.scenario_range_native() is None

    def test_get_price(self):
        r = _make_record(price_t3m=42.0, price_t6m=45.0)
        assert r.get_price("t3m") == 42.0
        assert r.get_price("t6m") == 45.0
        assert r.get_price("t12m") is None


# ═══ 6-5. Method-Level Breakdown ═══


class TestForecastErrorByMethod:
    def _make_method_record(
        self, predicted: int, actual: float, method: str
    ) -> BacktestRecord:
        return BacktestRecord(
            snapshot_id="snap-x",
            valuation_id="val-x",
            ticker="T",
            market="US",
            currency="USD",
            unit_multiplier=1,
            company_name="Co",
            legal_status="listed",
            analysis_date=date(2025, 1, 1),
            predicted_value=predicted,
            price_t6m=actual,
            primary_method=method,
        )

    def test_groups_by_method(self):
        """Results are split by primary_method."""
        records = [
            self._make_method_record(100, 100.0, "sotp"),
            self._make_method_record(100, 100.0, "sotp"),
            self._make_method_record(100, 100.0, "sotp"),
            self._make_method_record(120, 100.0, "dcf_primary"),
            self._make_method_record(120, 100.0, "dcf_primary"),
            self._make_method_record(120, 100.0, "dcf_primary"),
        ]
        result = calc_forecast_error_by_method(records, "t6m", min_n=3)
        assert "sotp" in result
        assert "dcf_primary" in result
        assert result["sotp"]["mape"] == pytest.approx(0.0)
        assert result["dcf_primary"]["mape"] == pytest.approx(0.2)

    def test_none_method_grouped_as_unknown(self):
        """primary_method=None is grouped under 'unknown'."""
        records = [
            BacktestRecord(
                snapshot_id="s",
                valuation_id="v",
                ticker="T",
                market="US",
                currency="USD",
                unit_multiplier=1,
                company_name="Co",
                legal_status="listed",
                analysis_date=date(2025, 1, 1),
                predicted_value=100,
                price_t6m=100.0,
                primary_method=None,
            )
            for _ in range(3)
        ]
        result = calc_forecast_error_by_method(records, "t6m", min_n=3)
        assert "unknown" in result

    def test_method_below_min_n_excluded(self):
        """Methods with fewer than min_n records are excluded."""
        records = [
            self._make_method_record(100, 100.0, "sotp"),
            self._make_method_record(100, 100.0, "sotp"),  # only 2 sotp records
            self._make_method_record(100, 100.0, "ddm"),
            self._make_method_record(100, 100.0, "ddm"),
            self._make_method_record(100, 100.0, "ddm"),
        ]
        result = calc_forecast_error_by_method(records, "t6m", min_n=3)
        assert "sotp" not in result  # excluded (n=2 < 3)
        assert "ddm" in result  # included (n=3 >= 3)

    def test_unlisted_excluded_from_method_breakdown(self):
        """Unlisted companies are excluded from method breakdown."""
        records = [
            BacktestRecord(
                snapshot_id="s",
                valuation_id="v",
                ticker="T",
                market="US",
                currency="USD",
                unit_multiplier=1,
                company_name="Co",
                legal_status="비상장",
                analysis_date=date(2025, 1, 1),
                predicted_value=100,
                price_t6m=100.0,
                primary_method="sotp",
            )
            for _ in range(5)
        ]
        result = calc_forecast_error_by_method(records, "t6m", min_n=3)
        assert result == {}

    def test_empty_records(self):
        result = calc_forecast_error_by_method([], "t6m")
        assert result == {}


# ═══ Price Tracker (unit tests, no yfinance call) ═══


class TestPriceTrackerHelpers:
    def test_resolve_ticker_us(self):
        from backtest.price_tracker import _resolve_ticker

        assert _resolve_ticker("AAPL", "US") == "AAPL"

    def test_resolve_ticker_kr_fallback(self):
        """KR ticker without pipeline module falls back to .KS suffix."""
        from backtest.price_tracker import _resolve_ticker

        # If resolve_kr_ticker fails, should fallback to .KS
        result = _resolve_ticker("005930", "KR")
        assert result.endswith((".KS", ".KQ"))
