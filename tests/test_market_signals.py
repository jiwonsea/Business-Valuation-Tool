"""Tests for Phase 4: Market signals integration."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from schemas.models import MarketSignals


# ── MarketSignals model tests ──

class TestMarketSignals:
    def test_empty_signals(self):
        s = MarketSignals()
        assert not s.has_any()

    def test_has_any_with_one_field(self):
        s = MarketSignals(vix=18.5)
        assert s.has_any()

    def test_full_signals(self):
        s = MarketSignals(
            fed_funds_rate=5.25,
            us_10y_yield=4.35,
            breakeven_inflation=2.3,
            credit_spread_baa=1.85,
            vix=18.5,
            target_mean=185.0,
            target_high=230.0,
            target_low=140.0,
            analyst_count=28,
            recommendation="overweight",
            news_sentiment_score=0.35,
            sentiment_label="positive",
            sentiment_article_count=42,
            iv_30d_atm=32.0,
            iv_percentile=65.0,
            put_call_ratio=0.85,
            fetched_at="2026-04-06T12:00:00",
        )
        assert s.has_any()
        assert s.vix == 18.5
        assert s.target_mean == 185.0

    def test_fetched_at_excluded_from_has_any(self):
        s = MarketSignals(fetched_at="2026-04-06T12:00:00")
        assert not s.has_any()


# ── Prompt formatter tests ──

class TestFormatMarketSignals:
    def test_none_signals(self):
        from ai.prompts import _format_market_signals
        assert _format_market_signals(None) == ""

    def test_empty_signals(self):
        from ai.prompts import _format_market_signals
        s = MarketSignals()
        assert _format_market_signals(s) == ""

    def test_macro_only(self):
        from ai.prompts import _format_market_signals
        s = MarketSignals(
            fed_funds_rate=5.25,
            us_10y_yield=4.35,
            vix=18.5,
            fetched_at="2026-04-06T12:00:00",
        )
        result = _format_market_signals(s)
        assert "<market_signals>" in result
        assert "Fed Funds: 5.25%" in result
        assert "10Y Treasury: 4.35%" in result
        assert "VIX: 18.5" in result
        assert "</market_signals>" in result

    def test_analyst_consensus(self):
        from ai.prompts import _format_market_signals
        s = MarketSignals(
            target_mean=185.0,
            target_low=140.0,
            target_high=230.0,
            analyst_count=28,
            recommendation="overweight",
        )
        result = _format_market_signals(s)
        assert "ANALYST CONSENSUS" in result
        assert "N=28" in result
        assert "185.0" in result
        assert "Overweight" in result

    def test_high_vix_guidance(self):
        from ai.prompts import _format_market_signals
        s = MarketSignals(vix=30.0, fetched_at="2026-04-06T12:00:00")
        result = _format_market_signals(s)
        assert "VIX is elevated" in result

    def test_sentiment_guidance_positive(self):
        from ai.prompts import _format_market_signals
        s = MarketSignals(news_sentiment_score=0.5, sentiment_label="positive", sentiment_article_count=10)
        result = _format_market_signals(s)
        assert "positive" in result.lower()
        assert "Bull" in result

    def test_sentiment_guidance_negative(self):
        from ai.prompts import _format_market_signals
        s = MarketSignals(news_sentiment_score=-0.5, sentiment_label="negative", sentiment_article_count=10)
        result = _format_market_signals(s)
        assert "negative" in result.lower()
        assert "Bear" in result


# ── Validator tests ──

class TestValidateScenariosWithSignals:
    def test_no_signals(self):
        from ai.validators import validate_scenarios_with_signals
        assert validate_scenarios_with_signals([], None) == []

    def test_analyst_deviation_warning(self):
        from ai.validators import validate_scenarios_with_signals
        signals = MarketSignals(target_mean=100.0)
        warnings = validate_scenarios_with_signals([], signals, weighted_value=200)
        assert any("애널리스트 목표가" in w for w in warnings)

    def test_no_warning_within_range(self):
        from ai.validators import validate_scenarios_with_signals
        signals = MarketSignals(target_mean=100.0)
        warnings = validate_scenarios_with_signals([], signals, weighted_value=120)
        assert not any("애널리스트 목표가" in w for w in warnings)

    def test_vix_spread_warning(self):
        from ai.validators import validate_scenarios_with_signals
        signals = MarketSignals(vix=30.0)
        scenarios = [
            {"code": "Bull", "prob": 35},
            {"code": "Base", "prob": 35},
            {"code": "Bear", "prob": 30},
        ]
        warnings = validate_scenarios_with_signals(scenarios, signals)
        assert any("VIX" in w for w in warnings)

    def test_sentiment_inconsistency(self):
        from ai.validators import validate_scenarios_with_signals
        signals = MarketSignals(news_sentiment_score=0.5)
        scenarios = [
            {"code": "Bull", "name": "Bull Case", "prob": 20},
            {"code": "Base", "name": "Base Case", "prob": 40},
            {"code": "Bear", "name": "Bear Case", "prob": 40},
        ]
        warnings = validate_scenarios_with_signals(scenarios, signals)
        assert any("불일치" in w for w in warnings)

    def test_iv_spread_warning(self):
        from ai.validators import validate_scenarios_with_signals
        signals = MarketSignals(iv_30d_atm=50.0)
        scenarios = [
            {"code": "Bull", "prob": 30, "drivers": {"wacc_adj": 0.2}},
            {"code": "Bear", "prob": 30, "drivers": {"wacc_adj": -0.2}},
        ]
        warnings = validate_scenarios_with_signals(scenarios, signals)
        assert any("IV" in w for w in warnings)


# ── FRED fetch tests (mocked) ──

class TestFredFetch:
    @patch("pipeline.market_signals.httpx.get")
    def test_fred_series_success(self, mock_get):
        from pipeline.market_signals import _fetch_fred_series, _CACHE_DIR
        mock_resp = MagicMock()
        mock_resp.text = "DATE,VALUE\n2026-04-01,5.25\n2026-04-02,5.33"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        from pipeline.api_guard import ApiGuard
        ApiGuard._reset_singleton()

        # Use tmp_path style: patch the cache dir check so cache miss is forced
        cache_file = _CACHE_DIR / "fred" / "DFF.json"
        if cache_file.exists():
            cache_file.unlink()

        result = _fetch_fred_series("DFF")
        assert result == 5.33

    @patch("pipeline.market_signals.httpx.get")
    def test_fred_series_missing_values(self, mock_get):
        from pipeline.market_signals import _fetch_fred_series, _CACHE_DIR
        mock_resp = MagicMock()
        mock_resp.text = "DATE,VALUE\n2026-04-01,.\n2026-04-02,."
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        from pipeline.api_guard import ApiGuard
        ApiGuard._reset_singleton()

        cache_file = _CACHE_DIR / "fred" / "DFF.json"
        if cache_file.exists():
            cache_file.unlink()

        result = _fetch_fred_series("DFF")
        assert result is None


# ── Backtest A/B comparison tests ──

class TestABComparison:
    def test_insufficient_data(self):
        from backtest.report import calc_ab_comparison
        from backtest.models import BacktestRecord
        from datetime import date

        records = [
            BacktestRecord(
                snapshot_id="1", valuation_id="v1", ticker="AAPL",
                market="US", currency="USD", unit_multiplier=1,
                company_name="Apple", legal_status="listed",
                analysis_date=date(2026, 1, 1), predicted_value=150,
                market_signals_version=0,
            )
        ]
        assert calc_ab_comparison(records) is None

    def test_split_by_version(self):
        from backtest.report import calc_ab_comparison
        from backtest.models import BacktestRecord
        from datetime import date

        def _make(vid, version, price_t6m=None):
            return BacktestRecord(
                snapshot_id=vid, valuation_id=vid, ticker="AAPL",
                market="US", currency="USD", unit_multiplier=1,
                company_name="Apple", legal_status="listed",
                analysis_date=date(2026, 1, 1), predicted_value=150,
                price_t0=140.0, price_t6m=price_t6m,
                market_signals_version=version,
            )

        records = [
            _make("v0a", 0, 145), _make("v0b", 0, 150), _make("v0c", 0, 155),
            _make("v1a", 1, 148), _make("v1b", 1, 152), _make("v1c", 1, 150),
        ]
        result = calc_ab_comparison(records)
        assert result is not None
        assert result["v0"]["n"] == 3
        assert result["v1"]["n"] == 3


# ── Prompt integration tests (signals parameter passthrough) ──

class TestPromptSignalsIntegration:
    def test_scenario_design_accepts_signals(self):
        from ai.prompts import prompt_scenario_design
        s = MarketSignals(vix=25.0, fetched_at="2026-04-06")
        result = prompt_scenario_design(
            "TestCo", "상장", "뉴스 내용", signals=s,
        )
        assert "VIX: 25.0" in result

    def test_scenario_classify_accepts_signals(self):
        from ai.prompts import prompt_scenario_classify
        s = MarketSignals(fed_funds_rate=5.25, fetched_at="2026-04-06")
        result = prompt_scenario_classify(
            "TestCo", "상장", "뉴스 내용", signals=s,
        )
        assert "Fed Funds: 5.25%" in result

    def test_scenario_refine_accepts_signals(self):
        from ai.prompts import prompt_scenario_refine
        s = MarketSignals(us_10y_yield=4.35, fetched_at="2026-04-06")
        draft = {"scenario_draft": []}
        result = prompt_scenario_refine(
            "TestCo", "상장", "뉴스 내용", draft, signals=s,
        )
        assert "10Y Treasury: 4.35%" in result

    def test_no_signals_no_block(self):
        from ai.prompts import prompt_scenario_design
        result = prompt_scenario_design("TestCo", "상장", "뉴스 내용")
        assert "<market_signals>" not in result
