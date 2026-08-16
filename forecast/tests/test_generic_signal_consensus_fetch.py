from __future__ import annotations

from datetime import date

import pytest

from engine import generic_signal
from engine.generic_signal import _extract_aligned_annual_eps, fetch_consensus_fy1_eps


def test_extracts_aligned_current_year_from_list_shape() -> None:
    raw = {
        "earnings_estimate": [
            {"period": "0y", "avg": 8.75},
            {"period": "+1y", "avg": 9.50},
        ]
    }

    assert _extract_aligned_annual_eps(raw, 2026, today=date(2026, 7, 8)) == pytest.approx(8.75)


def test_extracts_aligned_next_year_from_dict_shape() -> None:
    raw = {
        "earnings_estimate": {
            "0y": {"avg": 8.75},
            "+1y": {"avg": 9.50},
        }
    }

    assert _extract_aligned_annual_eps(raw, 2027, today=date(2026, 7, 8)) == pytest.approx(9.50)


def test_year_mismatch_returns_none() -> None:
    raw = {"earnings_estimate": [{"period": "0y", "avg": 8.75}]}

    assert _extract_aligned_annual_eps(raw, 2025, today=date(2026, 7, 8)) is None


def test_nan_or_missing_avg_returns_none() -> None:
    assert _extract_aligned_annual_eps(
        {"earnings_estimate": [{"period": "0y", "avg": None}]},
        2026,
        today=date(2026, 7, 8),
    ) is None
    assert _extract_aligned_annual_eps(
        {"earnings_estimate": [{"period": "0y", "avg": float("nan")}]},
        2026,
        today=date(2026, 7, 8),
    ) is None


def test_fetch_consensus_uses_pipeline_fetch_and_aligns_year(monkeypatch) -> None:
    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 7, 8)

    def fake_fetch_consensus(ticker: str):
        assert ticker == "NVDA"
        return {
            "earnings_estimate": [
                {"period": "0y", "avg": 8.75},
                {"period": "+1y", "avg": 9.50},
            ]
        }

    monkeypatch.setattr("pipeline.yahoo_fetcher.fetch_consensus", fake_fetch_consensus)
    monkeypatch.setattr(generic_signal, "date", FakeDate)

    assert fetch_consensus_fy1_eps("NVDA", 2027) == pytest.approx(9.50)


def test_fetch_consensus_returns_none_on_fetch_failure(monkeypatch) -> None:
    def broken_fetch_consensus(ticker: str):
        raise RuntimeError("offline")

    monkeypatch.setattr("pipeline.yahoo_fetcher.fetch_consensus", broken_fetch_consensus)

    assert fetch_consensus_fy1_eps("NVDA", 2026) is None
