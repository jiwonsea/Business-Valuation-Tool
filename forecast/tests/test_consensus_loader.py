from __future__ import annotations

from datetime import date

from pipeline.consensus_loader import to_consensus_record


def test_quarterly_consensus_labels_derive_from_as_of_when_history_period_is_null(
    sk_hynix_yahoo_raw: dict,
) -> None:
    raw = {
        **sk_hynix_yahoo_raw,
        "earnings_history": [
            {**row, "period": None}
            for row in sk_hynix_yahoo_raw["earnings_history"]
        ],
    }

    record = to_consensus_record(raw, "000660.KS", as_of=date(2026, 6, 2))

    assert set(record.revenue_estimate_quarterly) == {"2026Q2", "2026Q3"}
    assert set(record.eps_estimate_quarterly) == {"2026Q2", "2026Q3"}
    assert record.revenue_estimate_quarterly["2026Q2"] == 81815.89382
    assert "quarterly revenue consensus unavailable" not in record.notes
    assert "quarterly EPS consensus unavailable" not in record.notes


def test_quarterly_consensus_labels_roll_over_year_boundary(sk_hynix_yahoo_raw: dict) -> None:
    record = to_consensus_record(sk_hynix_yahoo_raw, "000660.KS", as_of=date(2026, 12, 15))

    assert set(record.revenue_estimate_quarterly) == {"2026Q4", "2027Q1"}


# --- earnings_history field-name mapping (quarter vs period) -----------------
# Real yfinance / cached snapshots key earnings_history rows by "quarter"; the
# committed fixture (and some legacy caches) key them by "period". The loader
# must accept both so vintage consensus history is not silently dropped — an
# empty history zeroes surprise-direction and consensus-skill scoring (N=0).


def test_history_populated_when_rows_keyed_by_quarter() -> None:
    """Real yfinance/cache shape: earnings_history indexed by 'quarter'."""
    raw = {
        "earnings_estimate": [],
        "revenue_estimate": [],
        "earnings_history": [
            {
                "quarter": "2025-06-30T00:00:00.000",
                "epsActual": 9572.0,
                "epsEstimate": 9338.132,
                "surprisePercent": 0.025,
            },
            {
                "quarter": "2025-12-31T00:00:00.000",
                "epsActual": 21522.0,
                "epsEstimate": 17822.42,
                "surprisePercent": 0.2076,
            },
        ],
    }

    record = to_consensus_record(raw, "000660.KS", as_of=date(2026, 6, 2))

    assert set(record.history) == {"2025Q2", "2025Q4"}
    assert record.history["2025Q2"]["actual"] == 9572.0
    assert record.history["2025Q2"]["estimate"] == 9338.132
    assert record.history["2025Q2"]["surprise_pct"] == 0.025
    assert record.history["2025Q4"]["estimate"] == 17822.42


def test_history_populated_when_rows_keyed_by_period_legacy() -> None:
    """Legacy/fixture shape: earnings_history indexed by 'period'."""
    raw = {
        "earnings_history": [
            {
                "period": "2026-03-31 00:00:00",
                "epsActual": 56670.0,
                "epsEstimate": 40016.555,
                "surprisePercent": 0.41619998,
            },
        ],
    }

    record = to_consensus_record(raw, "000660.KS", as_of=date(2026, 6, 2))

    assert set(record.history) == {"2026Q1"}
    assert record.history["2026Q1"]["actual"] == 56670.0


def test_history_empty_when_earnings_history_missing() -> None:
    """No earnings_history → history {} (graceful, unchanged behavior)."""
    record = to_consensus_record({}, "000660.KS", as_of=date(2026, 6, 2))

    assert record.history == {}
