"""IBM generic profile integrity tests (EFE Q2-2026 batch).

Guards the EDGAR-sourced actuals block that the forward forecast is seeded from:
contiguity, FY-sum identity (rev & NI), and load-time EPS derivation coherence
against the as-filed diluted EPS. These are the NVDA-1 defects (mixed-basis EPS,
silent Q3->Q1 joins) applied to a new December-filer profile.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from generic_cli import backtest_generic, load_generic_profile
from engine.segment_revenue import _next_quarter_label

PROFILE_PATH = Path(__file__).resolve().parents[1] / "profiles" / "ibm.generic.yaml"

# EDGAR-verified FY totals (USD millions) for the identity check.
FY_REVENUE = {2023: 61860, 2024: 62754, 2025: 67535}
FY_NET_INCOME = {2023: 7502, 2024: 6023, 2025: 10593}

# As-filed diluted EPS per quarter (provenance), for the derivation coherence check.
AS_FILED_EPS = {
    "2023Q1": 1.01, "2023Q2": 1.72, "2023Q3": 1.84,
    "2024Q1": 1.72, "2024Q2": 1.96, "2024Q3": -0.36,
    "2025Q1": 1.12, "2025Q2": 2.31, "2025Q3": 1.84,
    "2026Q1": 1.28,
}


@pytest.fixture(scope="module")
def profile():
    return load_generic_profile(PROFILE_PATH)


def test_profile_loads_calendar_filer(profile):
    assert profile.ticker == "IBM"
    assert profile.fiscal_year_end_month == 12
    assert profile.split_history == []  # IBM has not split since 1999
    assert profile.window.start_quarter == "2026Q2"


def test_actuals_contiguous(profile):
    labels = [a.quarter_label for a in profile.actuals]
    assert labels[0] == "2023Q1" and labels[-1] == "2026Q1"
    assert len(labels) == 13
    for prev, cur in zip(labels, labels[1:]):
        assert _next_quarter_label(prev) == cur, f"non-contiguous {prev}->{cur}"


def test_fy_sum_identity(profile):
    by_label = {a.quarter_label: a for a in profile.actuals}
    for year in (2023, 2024, 2025):
        quarters = [by_label[f"{year}Q{q}"] for q in (1, 2, 3, 4)]
        rev = sum(a.revenue_total for a in quarters)
        ni = sum(a.net_profit for a in quarters)
        assert rev == FY_REVENUE[year], f"FY{year} revenue {rev} != {FY_REVENUE[year]}"
        assert ni == FY_NET_INCOME[year], f"FY{year} NI {ni} != {FY_NET_INCOME[year]}"


def test_eps_derived_matches_as_filed(profile):
    """EPS is derived at load (NI/shares); must match the as-filed diluted EPS."""
    by_label = {a.quarter_label: a for a in profile.actuals}
    for label, eps in AS_FILED_EPS.items():
        derived = by_label[label].eps_diluted
        assert derived is not None
        assert abs(derived - eps) <= max(0.03, abs(eps) * 0.03), (
            f"{label}: derived {derived:.3f} vs as-filed {eps}"
        )


def test_backtest_not_refused(profile):
    """13 contiguous quarters -> the 1-step backtest runs (12 pairs), not REFUSE."""
    bt = backtest_generic(profile)
    assert bt["n"] == 12
