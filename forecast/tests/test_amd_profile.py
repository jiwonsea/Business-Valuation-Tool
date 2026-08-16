"""AMD-1 (2026-08-05 KST): integrity + forecast checks for profiles/amd.generic.yaml.

Guards the EDGAR-sourced actuals block (contiguity, FY-sum identity, derived-EPS
coherence, no-split) and the frozen 2026Q2 calibration so a later hand-edit of the
profile can't silently corrupt the frozen-forecast basis. Pure/offline: loads the
real profile only.

Mirrors tests/test_txn_profile.py. The AMD-specific additions are:
  - the R2 contract (base scenario below-OP anchored at exactly 0.0) is asserted,
    because the FROZEN report pre-registers an A/B on precisely that choice;
  - the R1 contract (revenue level anchored to guidance x measured beat, not to a
    historical average) is asserted as a band around the company guide midpoint;
  - the R4 contract (backtest_methodology present, calendar-slot ordered) is
    asserted because AMD's Q1 seed makes the forward and backtest vectors differ
    by one seasonal position.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from engine.generic_forecast import run_generic_forecast
from generic_cli import backtest_generic, load_generic_profile

REPO_ROOT = Path(__file__).resolve().parent.parent

# Company guidance for fiscal Q2 2026, from the Q1'26 8-K EX-99.1 outlook
# paragraph: "revenue to be approximately $11.2 billion, plus or minus $300
# million... Non-GAAP gross margin ... approximately 56%."
GUIDE_MID = 11200.0
GUIDE_LOW = 10900.0
GUIDE_HIGH = 11500.0


def _load():
    return load_generic_profile(REPO_ROOT / "profiles" / "amd.generic.yaml")


def test_profile_loads_and_header_contract():
    p = _load()
    assert p.ticker == "AMD"
    assert p.fiscal_year_end_month == 12  # calendar filer, no consensus-join offset
    assert p.reporting_unit == "USD_million"
    assert p.split_history == []  # last AMD split was 2000, outside the window
    assert p.seed.quarter_label == "2026Q1"
    assert p.seed.revenue_total == 10253
    assert p.window.start_quarter == "2026Q2" and p.window.n_quarters == 4


def test_actuals_are_9_contiguous_calendar_quarters():
    p = _load()
    labels = [a.quarter_label for a in p.actuals]
    assert labels == [
        f"{y}Q{q}" for y in (2024, 2025) for q in (1, 2, 3, 4)
    ] + ["2026Q1"]
    assert len(labels) == 9


def test_derived_eps_matches_as_filed_within_tolerance():
    # NVDA-1c: eps_diluted is DERIVED from net_profit / diluted_shares at load;
    # it must reconcile to the as-filed EPS preserved in each row's source.
    p = _load()
    checked = 0
    for a in p.actuals:
        m = re.search(r"as-filed EPS ([0-9.]+)", a.source)
        if not m:
            continue  # Q4 rows carry no as-filed quarterly EPS fact
        as_filed = float(m.group(1))
        assert a.eps_diluted == pytest.approx(as_filed, abs=0.01), a.quarter_label
        checked += 1
    assert checked == 7  # 9 quarters minus the two reconstructed Q4s


def test_reconstructed_q4_eps_matches_as_reported():
    # The two Q4 rows carry DERIVED share counts (AMD tags only a YTD weighted
    # average in the 10-K). Both must still reproduce the as-reported GAAP EPS,
    # which is the only external check available on the derivation.
    p = _load()
    by_label = {a.quarter_label: a for a in p.actuals}
    assert by_label["2024Q4"].eps_diluted == pytest.approx(0.29, abs=0.01)
    assert by_label["2025Q4"].eps_diluted == pytest.approx(0.92, abs=0.01)


def test_fy_sum_identity_holds_for_revenue_and_ni():
    # The four standalone quarters of each complete FY must sum to that year's
    # reported 10-K totals (Q4 = 10-K annual minus same-FY 9M 10-Q).
    p = _load()
    by_label = {a.quarter_label: a for a in p.actuals}
    fy_reported = {  # (revenue_total, net_profit) in USD_million, from 10-Ks
        2024: (25785, 1641),
        2025: (34639, 4335),
    }
    for year, (rev, ni) in fy_reported.items():
        qs = [by_label[f"{year}Q{q}"] for q in (1, 2, 3, 4)]
        assert sum(a.revenue_total for a in qs) == pytest.approx(rev)
        assert sum(a.net_profit for a in qs) == pytest.approx(ni)


def test_r4_backtest_methodology_is_present_and_calendar_ordered():
    # R4 (START-DELTA): the forward vector is positional from a Q1 seed while
    # backtest_generic indexes by calendar slot, so a separate block is required.
    p = _load()
    bm = p.backtest_methodology
    assert bm is not None
    assert len(bm.revenue_growth_qoq) == 4
    # Calendar-slot shape: Q1 is the seasonal down-quarter, Q3 the strongest.
    q1, q2, q3, q4 = bm.revenue_growth_qoq
    assert q1 < 0 < q2 < q4 < q3


def test_r2_below_op_base_is_exactly_zero():
    # R2 (START-DELTA): the below-OP block is anchor-free with base 0 and a wide
    # band. The FROZEN report pre-registers an A/B on this exact choice, so it is
    # a contract, not a tunable.
    p = _load()
    assert p.base.net_interest_pct_of_revenue == 0.0
    assert p.bear.net_interest_pct_of_revenue < 0.0
    assert p.bull.net_interest_pct_of_revenue > 0.0


def test_r3_tax_rates_differ_across_scenarios():
    # R3 (START-DELTA): a single tax anchor is forbidden; AMD's GAAP ETR has
    # printed 11.0% / 14.8% / 14.9% / 21.9% and one n.m. quarter.
    p = _load()
    rates = {p.bear.effective_tax_rate, p.base.effective_tax_rate, p.bull.effective_tax_rate}
    assert len(rates) == 3
    assert p.bull.effective_tax_rate < p.base.effective_tax_rate < p.bear.effective_tax_rate


def test_r1_revenue_level_anchored_to_guidance_not_history():
    # R1 (START-DELTA): "level은 최신 actual/가이던스". Every scenario's 2026Q2
    # revenue must sit in a sane neighbourhood of the company guide, and base must
    # sit ABOVE the midpoint (AMD beat its own midpoint 4/4 in the trailing year).
    p = _load()
    seed = p.seed.revenue_total
    rev = {s: seed * (1 + getattr(p, s).revenue_growth_qoq[0]) for s in ("bear", "base", "bull")}
    assert GUIDE_LOW - 200 <= rev["bear"] <= GUIDE_MID
    assert GUIDE_MID < rev["base"] <= GUIDE_HIGH + 300
    assert rev["bull"] > rev["base"]
    # base is +4.0% over the midpoint: below the trailing-4Q mean beat (+5.43%)
    # and just above the smallest observed beat (+3.85%).
    assert rev["base"] / GUIDE_MID == pytest.approx(1.040, abs=0.005)


def test_backtest_reports_three_regime_windows():
    bt = backtest_generic(_load())
    assert set(bt["windows"]) == {"full", "pre_break", "post_break"}
    assert bt["windows"]["full"]["n"] == 8  # 9 actuals -> 8 one-step pairs
    # Revenue tracks the calendar-slot fit closely (in-sample by construction —
    # see the FROZEN report's honesty note; this guards regression, not skill).
    assert bt["windows"]["post_break"]["skill"]["mase_revenue"] < 1.0


def test_frozen_q2_2026_forecast_values():
    # Frozen-forecast anchor (reports/amd_q2_2026_forecast_FROZEN.md, sha256
    # c82117da... of the profile). Any drift here invalidates the frozen report.
    p = _load()
    fc = run_generic_forecast(p)
    q2 = fc.weighted_quarterly[0]
    assert q2.quarter_label == "2026Q2"
    assert q2.revenue_total == pytest.approx(11600.3, abs=1.0)
    assert (q2.eps_diluted or 0.0) == pytest.approx(1.11, abs=0.01)

    base_q2 = fc.scenarios_quarterly["base"][0]
    bear_q2 = fc.scenarios_quarterly["bear"][0]
    bull_q2 = fc.scenarios_quarterly["bull"][0]
    assert base_q2.revenue_total == pytest.approx(11650.5, abs=1.0)
    assert base_q2.eps_diluted == pytest.approx(1.075, abs=0.005)
    assert bear_q2.eps_diluted == pytest.approx(0.758, abs=0.005)
    assert bull_q2.eps_diluted == pytest.approx(1.526, abs=0.005)

    # Band width / base, recorded in the FROZEN report for calibration (R6).
    band = (bull_q2.eps_diluted - bear_q2.eps_diluted) / base_q2.eps_diluted
    assert band == pytest.approx(0.714, abs=0.01)
