"""SNDK (Sandisk) FY2026 Q4 profile guards.

SanDisk is this repo's first NON-DECEMBER fiscal-year generic issuer, so the
label contract carries real risk: the frozen target is FISCAL Q4 FY2026
(2026-04-04..2026-07-03), which is CALENDAR Q2 2026. A model that silently
treats "2026Q4" as calendar Q4 would join consensus, seasonality and actuals a
half-year out of phase.

These tests pin, in order:
  1. data integrity of the actuals block (contiguity, FY-sum identities,
     derived-EPS == as-filed EPS),
  2. the fiscal<->calendar label mapping itself,
  3. the R4 separation of the calendar-slot backtest vector from the positional
     forward vectors,
  4. the forward chain against a hand recomputation of rev x (1 + g).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
import yaml

from engine.generic_forecast import run_generic_forecast
from generic_cli import backtest_generic
from schemas.generic import GenericProfile

PROFILE_PATH = "profiles/sndk.generic.yaml"


@pytest.fixture(scope="module")
def profile() -> GenericProfile:
    with open(PROFILE_PATH, encoding="utf-8") as handle:
        return GenericProfile(**yaml.safe_load(handle))


# ---------------------------------------------------------------------------
# 1. Actuals integrity
# ---------------------------------------------------------------------------


def test_actuals_are_contiguous_fiscal_quarters(profile: GenericProfile) -> None:
    labels = [a.quarter_label for a in profile.actuals]
    assert labels == [
        "2024Q1", "2024Q2", "2024Q3", "2024Q4",
        "2025Q1", "2025Q2", "2025Q3", "2025Q4",
        "2026Q1", "2026Q2", "2026Q3",
    ]
    # period_end must increase strictly with the label order.
    ends = [a.period_end for a in profile.actuals]
    assert all(a is not None for a in ends)
    assert ends == sorted(ends)


@pytest.mark.parametrize(
    "fiscal_year, expected_revenue, expected_net_profit",
    [
        (2024, 6663, -672),   # FY2024 10-K 0002023554-25-000034
        (2025, 7355, -1641),  # FY2025 10-K 0002023554-25-000034
    ],
)
def test_fiscal_year_sums_tie_to_the_10k(
    profile: GenericProfile, fiscal_year: int, expected_revenue: int, expected_net_profit: int
) -> None:
    rows = [a for a in profile.actuals if a.quarter_label.startswith(str(fiscal_year))]
    assert len(rows) == 4
    assert sum(a.revenue_total for a in rows) == expected_revenue
    assert sum(a.net_profit for a in rows) == expected_net_profit


def test_nine_month_fy2026_ties_to_the_q3_10q(profile: GenericProfile) -> None:
    """9M FY2026 per 10-Q 0001628280-26-029401: revenue 11,283 / net income 4,530."""
    rows = [a for a in profile.actuals if a.quarter_label in {"2026Q1", "2026Q2", "2026Q3"}]
    assert sum(a.revenue_total for a in rows) == 11283
    assert sum(a.net_profit for a in rows) == 4530


@pytest.mark.parametrize(
    "label, as_filed_eps",
    [
        ("2025Q1", 1.46),
        ("2025Q3", -13.33),
        ("2025Q4", -0.16),
        ("2026Q1", 0.75),
        ("2026Q2", 5.15),
        ("2026Q3", 23.03),
    ],
)
def test_derived_eps_reproduces_as_filed_eps(
    profile: GenericProfile, label: str, as_filed_eps: float
) -> None:
    """NVDA-1c: EPS is derived from NI / as-filed diluted shares, never selected."""
    row = next(a for a in profile.actuals if a.quarter_label == label)
    assert row.eps_diluted == pytest.approx(as_filed_eps, abs=0.01)


# ---------------------------------------------------------------------------
# 2. Fiscal <-> calendar label mapping (the non-December-filer trap)
# ---------------------------------------------------------------------------


def _fiscal_label_for(period_end: date, fye_month: int) -> str:
    """Fiscal FY/quarter label for a period END date, for a `fye_month` filer.

    A 52/53-week filer's quarter ends on the nearest Friday, so the end date can
    spill up to ~6 days into the FOLLOWING month (SanDisk FY2026 Q1 ended
    2025-10-03, Q4 ends 2026-07-03). Backing the date up by 7 days puts it
    unambiguously inside its anchor month, after which the mapping is arithmetic.
    """
    anchor = period_end - timedelta(days=7)
    quarter = ((anchor.month - (fye_month + 1)) % 12) // 3 + 1
    fiscal_year = anchor.year + 1 if anchor.month > fye_month else anchor.year
    return f"{fiscal_year}Q{quarter}"


def test_fiscal_label_maps_to_calendar_quarter(profile: GenericProfile) -> None:
    """Every actual's stored label must equal the label derived from period_end."""
    for row in profile.actuals:
        assert _fiscal_label_for(row.period_end, profile.fiscal_year_end_month) == (
            row.quarter_label
        ), f"{row.quarter_label} vs period_end {row.period_end}"


def test_frozen_target_is_fiscal_q4_but_calendar_q2() -> None:
    """The trap, pinned: FY2026 Q4 ends 2026-07-03 and spans calendar Q2 2026.

    The label digit (4) must NOT be read as a calendar quarter. If someone later
    relabels the profile on a calendar basis this test fails loudly.
    """
    fq4_end = date(2026, 7, 3)
    fq4_start = date(2026, 4, 4)
    assert _fiscal_label_for(fq4_end, 6) == "2026Q4"
    # Calendar quarter of the period MIDPOINT is Q2, not Q4.
    midpoint = fq4_start + (fq4_end - fq4_start) / 2
    assert (midpoint.month - 1) // 3 + 1 == 2
    # And the seed quarter FY2026 Q3 is calendar Q1 2026.
    assert _fiscal_label_for(date(2026, 4, 3), 6) == "2026Q3"


def test_window_starts_at_the_frozen_target(profile: GenericProfile) -> None:
    assert profile.seed.quarter_label == "2026Q3"
    assert profile.window.start_quarter == "2026Q4"
    assert profile.window.n_quarters == 4
    assert profile.fiscal_year_end_month == 6


# ---------------------------------------------------------------------------
# 3. R4 — calendar-slot backtest vector kept separate from forward positional
# ---------------------------------------------------------------------------


def test_backtest_methodology_is_present_and_slot_ordered(profile: GenericProfile) -> None:
    """DELTA §R4: a non-December filer MUST carry backtest_methodology.

    Its vector is indexed by FISCAL quarter [FQ1..FQ4] because
    generic_cli._slot() reads the label digit; the forward vectors are
    POSITIONAL from the seed ([FQ4, FQ1, FQ2, FQ3]) and must therefore differ.
    """
    assert profile.backtest_methodology is not None
    assert len(profile.backtest_methodology.revenue_growth_qoq) == 4
    assert profile.backtest_methodology.revenue_growth_qoq != profile.base.revenue_growth_qoq


def test_backtest_runs_and_is_not_refused(profile: GenericProfile) -> None:
    result = backtest_generic(profile)
    assert result.get("n") == 10, result.get("note")
    assert "note" not in result
    windows = result.get("windows")
    assert windows is not None
    assert windows["post_break"]["n"] == 5
    assert windows["pre_break"]["n"] == 5
    assert windows["full"]["n"] == 10


def test_backtest_is_immune_to_forward_scenario_edits(profile: GenericProfile) -> None:
    """The structural fix: mutating base must NOT move the backtest."""
    before = backtest_generic(profile)["revenue_mape"]
    original = list(profile.base.revenue_growth_qoq)
    try:
        profile.base.revenue_growth_qoq = [0.99, 0.99, 0.99, 0.99]
        after = backtest_generic(profile)["revenue_mape"]
    finally:
        profile.base.revenue_growth_qoq = original
    assert before == after


# ---------------------------------------------------------------------------
# 4. Forward chain hand-check
# ---------------------------------------------------------------------------


def test_forward_chain_matches_hand_calculation(profile: GenericProfile) -> None:
    """rev_i = rev_{i-1} x (1+g_i); op = rev x m; net = (op + ni x rev) x (1-t)."""
    forecast = run_generic_forecast(profile)
    n = profile.window.n_quarters
    for name in ("bear", "base", "bull"):
        assumptions = getattr(profile, name)
        growth = assumptions.growth(n)
        margin = assumptions.margin(n)
        tax = assumptions.tax(n)
        net_int = assumptions.net_interest(n)
        revenue = profile.seed.revenue_total
        for i, quarter in enumerate(forecast.scenarios_quarterly[name]):
            revenue = revenue * (1.0 + growth[i])
            op = revenue * margin[i]
            net = (op + net_int[i] * revenue) * (1.0 - tax[i])
            eps = net * profile.unit_scale / profile.weighted_avg_diluted
            assert quarter.revenue_total == pytest.approx(revenue, rel=1e-12)
            assert quarter.operating_profit == pytest.approx(op, rel=1e-12)
            assert quarter.net_profit == pytest.approx(net, rel=1e-12)
            assert quarter.eps_diluted == pytest.approx(eps, rel=1e-12)


def test_frozen_fq4_point_estimates(profile: GenericProfile) -> None:
    """Pin the frozen FY2026 Q4 numbers so a later profile edit is visible."""
    forecast = run_generic_forecast(profile)
    by_scenario = {
        name: next(q for q in forecast.scenarios_quarterly[name] if q.quarter_label == "2026Q4")
        for name in ("bear", "base", "bull")
    }
    assert by_scenario["bear"].revenue_total == pytest.approx(8092.0, abs=0.5)
    assert by_scenario["base"].revenue_total == pytest.approx(9044.0, abs=0.5)
    assert by_scenario["bull"].revenue_total == pytest.approx(9996.0, abs=0.5)
    assert by_scenario["bear"].eps_diluted == pytest.approx(30.39, abs=0.01)
    assert by_scenario["base"].eps_diluted == pytest.approx(38.57, abs=0.01)
    assert by_scenario["bull"].eps_diluted == pytest.approx(45.02, abs=0.01)

    weighted = next(q for q in forecast.weighted_quarterly if q.quarter_label == "2026Q4")
    assert weighted.revenue_total == pytest.approx(9044.0, abs=0.5)
    assert weighted.eps_diluted == pytest.approx(38.14, abs=0.01)


def test_base_revenue_sits_above_guidance_and_consensus(profile: GenericProfile) -> None:
    """Documents the call itself: base is a beat vs both the guide and the Street.

    Guidance midpoint 8,000 (8-K EX-99.1 2026-04-30); consensus band 8,300-8,420
    (Zacks 2026-08-03 / TipRanks 2026-07-31). Bear must still land inside the
    guided range rather than below it.
    """
    forecast = run_generic_forecast(profile)
    fq4 = {
        name: next(q for q in forecast.scenarios_quarterly[name] if q.quarter_label == "2026Q4")
        for name in ("bear", "base", "bull")
    }
    assert 7750.0 <= fq4["bear"].revenue_total <= 8250.0
    assert fq4["base"].revenue_total > 8420.0
    assert fq4["bull"].revenue_total > fq4["base"].revenue_total
