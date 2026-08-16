"""Consensus reliability: separate genuine quality failures from mere absence.

Codex follow-up #1. The bridge guard must hold only on real data-quality problems
(yfinance .KS implied net margin >60%, HANDOFF_backtest_diag §①-B), NOT when a
benign field (e.g. quarterly consensus) is simply absent — otherwise a valid annual
EPS bridge is wrongly suppressed. ``quality_notes`` carries only quality failures;
``notes`` keeps the full display list (absence + quality).
"""

from __future__ import annotations

from datetime import date

from pipeline.consensus_loader import to_consensus_record


def test_quality_notes_empty_on_mere_absence() -> None:
    """Empty input -> absence notes present, but quality_notes empty (reliable)."""
    record = to_consensus_record({}, "000660.KS", as_of=date(2026, 6, 2))
    assert record.quality_notes == []
    assert any("unavailable" in n for n in record.notes)


def test_quality_notes_flag_implied_margin_over_60pct() -> None:
    """Implausible consensus (implied net margin >60%) -> quality_notes populated."""
    raw = {
        # 0y annual: revenue 50e12 KRW -> 50,000 bn; EPS 100,000 won/share.
        # implied margin = (100000 * 689e6 / 1e9) / 50000 = 1.378 -> >60%.
        "revenue_estimate": [{"period": "0y", "avg": 50_000_000_000_000.0}],
        "earnings_estimate": [{"period": "0y", "avg": 100_000.0}],
    }
    record = to_consensus_record(
        raw, "000660.KS", as_of=date(2026, 6, 2), weighted_avg_basic_shares=689_000_000
    )
    assert any("net margin" in n for n in record.quality_notes)
    # Still surfaced in the display notes too.
    assert any("net margin" in n for n in record.notes)


def test_realistic_annual_consensus_is_reliable_despite_quarterly_absence() -> None:
    """Annual EPS present + realistic margin, quarterly absent -> reliable (no quality note).

    This is the case the old len(notes)==0 guard wrongly suppressed.
    """
    raw = {
        # 0y annual: revenue 80e12 -> 80,000 bn; EPS 20,000 won/share.
        # implied margin = (20000 * 689e6 / 1e9) / 80000 = 0.172 -> realistic.
        "revenue_estimate": [{"period": "0y", "avg": 80_000_000_000_000.0}],
        "earnings_estimate": [{"period": "0y", "avg": 20_000.0}],
    }
    record = to_consensus_record(
        raw, "000660.KS", as_of=date(2026, 6, 2), weighted_avg_basic_shares=689_000_000
    )
    # Quarterly absent -> notes has absence warnings, but no quality failure.
    assert record.quality_notes == []
    assert record.eps_estimate_annual.get(2026) == 20_000.0
