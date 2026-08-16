"""NVDA-2 stage 2b: fiscal-aware generic Yahoo consensus normalization."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from engine.generic_forecast import run_generic_forecast
from generic_cli import backtest_generic, render_markdown
from pipeline import yahoo_fetcher
from pipeline.generic_consensus import to_generic_consensus_record
from schemas.generic import GenericProfile

REPO_ROOT = Path(__file__).resolve().parent.parent


def _profile(*, fiscal_year_end_month: int = 1) -> GenericProfile:
    latest_end = date(2026, 4, 26) if fiscal_year_end_month == 1 else date(2026, 3, 31)
    latest_label = "2026Q1"
    return GenericProfile.model_validate(
        dict(
            name="Test Co",
            name_kr="테스트",
            ticker="TST",
            currency="USD",
            reporting_unit="USD_million",
            fiscal_year_end_month=fiscal_year_end_month,
            weighted_avg_diluted=24_000_000_000,
            seed=dict(quarter_label=latest_label, revenue_total=80_000.0),
            window=dict(start_quarter="2026Q2", n_quarters=4),
            actuals=[
                dict(
                    quarter_label="2025Q4",
                    period_end=(date(2026, 1, 25) if fiscal_year_end_month == 1 else date(2025, 12, 31)),
                    revenue_total=60_000.0,
                    net_profit=6_000.0,
                    diluted_shares=24_000_000_000,
                ),
                dict(
                    quarter_label=latest_label,
                    period_end=latest_end,
                    revenue_total=80_000.0,
                    net_profit=56_000.0,
                    diluted_shares=24_000_000_000,
                ),
            ],
            bear=dict(probability=0.25, revenue_growth_qoq=[0.0] * 4, op_margin=0.50, effective_tax_rate=0.15),
            base=dict(probability=0.50, revenue_growth_qoq=[0.05] * 4, op_margin=0.60, effective_tax_rate=0.15),
            bull=dict(probability=0.25, revenue_growth_qoq=[0.10] * 4, op_margin=0.65, effective_tax_rate=0.15),
        )
    )


def _raw(
    *,
    latest_history: str = "2026-04-26",
    revenue_0q: float | None = 90_000_000_000.0,
    eps_0q: float | None = 2.5,
) -> dict:
    revenue_rows = [
        {"period": "0q", "avg": revenue_0q},
        {"period": "+1q", "avg": 95_000_000_000.0},
        {"period": "0y", "avg": 350_000_000_000.0},
        {"period": "+1y", "avg": 420_000_000_000.0},
    ]
    earnings_rows = [
        {"period": "0q", "avg": eps_0q},
        {"period": "+1q", "avg": 2.7},
        {"period": "0y", "avg": 10.0},
        {"period": "+1y", "avg": 12.0},
    ]
    return {
        "revenue_estimate": revenue_rows,
        "earnings_estimate": earnings_rows,
        "earnings_history": [
            {
                "quarter": "2026-01-25T00:00:00",
                "epsActual": 2.0,
                "epsEstimate": 1.9,
                "surprisePercent": 5.0,
            },
            {
                "quarter": f"{latest_history}T00:00:00",
                "epsActual": 2.4,
                "epsEstimate": 2.2,
                "surprisePercent": 9.0,
            },
        ],
    }


def test_january_fye_maps_forward_and_history_to_model_labels() -> None:
    record = to_generic_consensus_record(_raw(), _profile(), date(2026, 7, 21))

    assert record.revenue_estimate_quarterly == {
        "2026Q2": pytest.approx(90_000.0),
        "2026Q3": pytest.approx(95_000.0),
    }
    assert record.eps_estimate_quarterly == {"2026Q2": 2.5, "2026Q3": 2.7}
    assert record.revenue_estimate_annual[2027] == pytest.approx(350_000.0)
    assert record.eps_estimate_annual[2027] == pytest.approx(10.0)
    assert set(record.revenue_estimate_annual) == {2027, 2028}
    assert set(record.history) == {"2025Q4", "2026Q1"}
    assert record.quality_notes == []


def test_calendar_filer_maps_next_quarter_and_current_fiscal_year() -> None:
    raw = _raw(latest_history="2026-03-31")
    raw["earnings_history"] = [raw["earnings_history"][-1]]
    record = to_generic_consensus_record(raw, _profile(fiscal_year_end_month=12), date(2026, 7, 21))

    assert set(record.revenue_estimate_quarterly) == {"2026Q2", "2026Q3"}
    assert set(record.revenue_estimate_annual) == {2026, 2027}


def test_same_fiscal_quarter_anchor_accepts_month_end_history_date() -> None:
    record = to_generic_consensus_record(
        _raw(latest_history="2026-04-30"), _profile(), date(2026, 7, 21)
    )

    assert record.revenue_estimate_quarterly["2026Q2"] == pytest.approx(90_000.0)
    assert record.eps_estimate_quarterly["2026Q2"] == 2.5
    assert record.quality_notes == []


@pytest.mark.parametrize("history", [[], None])
def test_missing_history_refuses_forward_but_keeps_explicit_none(history) -> None:
    raw = _raw()
    raw["earnings_history"] = history
    record = to_generic_consensus_record(raw, _profile(), date(2026, 7, 21))

    assert all(value is None for value in record.revenue_estimate_quarterly.values())
    assert all(value is None for value in record.eps_estimate_annual.values())
    assert record.history == {}
    assert any("anchor refused" in note for note in record.quality_notes)


def test_anchor_mismatch_refuses_forward_but_keeps_mapped_history() -> None:
    record = to_generic_consensus_record(
        _raw(latest_history="2026-01-25"), _profile(), date(2026, 7, 21)
    )

    assert all(value is None for value in record.eps_estimate_quarterly.values())
    assert set(record.history) == {"2025Q4"}
    assert any("2026-01-25" in note and "2026-04-26" in note for note in record.quality_notes)


def test_snapshot_predating_latest_actual_is_rejected() -> None:
    with pytest.raises(ValueError, match="predates latest actual"):
        to_generic_consensus_record(_raw(), _profile(), date(2026, 4, 25))


def test_quarterly_period_set_mismatch_is_quality_failure() -> None:
    raw = _raw()
    raw["earnings_estimate"] = [
        row for row in raw["earnings_estimate"] if row["period"] != "+1q"
    ]
    record = to_generic_consensus_record(raw, _profile(), date(2026, 7, 21))

    assert all(value is None for value in record.eps_estimate_quarterly.values())
    assert any("period-set mismatch" in note for note in record.quality_notes)


def test_revenue_unit_gate_suppresses_original_and_preserves_audit_value() -> None:
    record = to_generic_consensus_record(
        _raw(revenue_0q=400_000_000_000.0), _profile(), date(2026, 7, 21)
    )

    assert record.revenue_estimate_quarterly["2026Q2"] is None
    assert any("original=400000" in note and "ratio=5.000" in note for note in record.quality_notes)


def test_missing_revenue_skips_unit_and_margin_gates_without_failure() -> None:
    record = to_generic_consensus_record(
        _raw(revenue_0q=None), _profile(), date(2026, 7, 21)
    )

    assert record.revenue_estimate_quarterly["2026Q2"] is None
    assert record.eps_estimate_quarterly["2026Q2"] == pytest.approx(2.5)
    assert not any("gate failed" in note and "2026Q2" in note for note in record.quality_notes)


def test_margin_gate_pass_fail_and_missing_eps_not_run() -> None:
    passed = to_generic_consensus_record(_raw(eps_0q=2.5), _profile(), date(2026, 7, 21))
    failed = to_generic_consensus_record(_raw(eps_0q=4.0), _profile(), date(2026, 7, 21))
    missing = to_generic_consensus_record(_raw(eps_0q=None), _profile(), date(2026, 7, 21))

    assert passed.eps_estimate_quarterly["2026Q2"] == pytest.approx(2.5)
    assert failed.eps_estimate_quarterly["2026Q2"] is None
    assert any("original EPS=4" in note for note in failed.quality_notes)
    assert missing.eps_estimate_quarterly["2026Q2"] is None
    assert not any("2026Q2 implied" in note for note in missing.quality_notes)


def test_consensus_history_fills_existing_skill_structure() -> None:
    profile = _profile()
    raw = _raw()
    record = to_generic_consensus_record(raw, profile, date(2026, 7, 21))
    backtest = backtest_generic(profile, record.history)

    assert backtest["skill"]["n_surprise_scored"] == 1
    assert backtest["skill"]["skill_score_eps_vs_consensus"] is not None


def test_report_renders_fiscal_consensus_and_quality_notes() -> None:
    profile = _profile()
    raw = _raw(revenue_0q=400_000_000_000.0)
    record = to_generic_consensus_record(raw, profile, date(2026, 7, 21))
    report = render_markdown(
        profile,
        run_generic_forecast(profile),
        backtest_generic(profile, record.history),
        record,
    )

    assert "Yahoo consensus (fiscal-aware)" in report
    assert "FY2027" in report
    assert "0q revenue unit gate failed" in report


def test_yahoo_snapshot_cache_preserves_as_of_and_fetch_timestamp(tmp_path, monkeypatch) -> None:
    class FakeTicker:
        earnings_estimate = None
        revenue_estimate = None
        earnings_history = None
        info = {}

    monkeypatch.setattr(yahoo_fetcher, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(yahoo_fetcher.yf, "Ticker", lambda ticker: FakeTicker())

    raw = yahoo_fetcher.fetch_consensus("NVDA", use_cache=False)
    cached = json.loads((tmp_path / f"yahoo_NVDA_{date.today():%Y%m%d}.json").read_text(encoding="utf-8"))

    assert raw["as_of"] == date.today().isoformat()
    assert raw["fetch_timestamp"].endswith("+00:00")
    assert cached["as_of"] == raw["as_of"]
    assert cached["fetch_timestamp"] == raw["fetch_timestamp"]
