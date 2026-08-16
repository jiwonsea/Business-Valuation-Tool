"""VST-1 (2026-08-04): integrity + forecast checks for profiles/vst.generic.yaml.

Guards the EDGAR-sourced actuals block (contiguity, FY-sum identity, derived-EPS
coherence, no-split) and the frozen 2026Q2 calibration, plus the T1 invariant
that motivates this profile's whole design: for a merchant IPP the consolidated
GAAP operating margin is NOT an anchorable quantity (DELTA §R1 degrades here).
Pure/offline: loads the real profile only.
"""

from __future__ import annotations

import re
import statistics
from pathlib import Path

import pytest

from generic_cli import backtest_generic, load_generic_profile

REPO_ROOT = Path(__file__).resolve().parent.parent

# as-filed consolidated GAAP operating income, USD millions, 2023Q1..2026Q1.
# Quarterly 10-Q tags; Q4 = same-FY 10-K annual minus Q3 10-Q 9M.
GAAP_OP = [1131, 591, 834, 102, 86, 808, 2588, 599, -120, 515, 1037, 474, 1499]


def _load():
    return load_generic_profile(REPO_ROOT / "profiles" / "vst.generic.yaml")


def test_profile_loads_and_header_contract():
    p = _load()
    assert p.ticker == "VST"
    assert p.fiscal_year_end_month == 12  # calendar filer, no consensus-join offset
    assert p.reporting_unit == "USD_million"
    assert p.split_history == []
    assert p.seed.quarter_label == "2026Q1"
    assert p.seed.revenue_total == 5640
    assert p.window.start_quarter == "2026Q2" and p.window.n_quarters == 4
    assert p.weighted_avg_diluted == 338_000_000


def test_actuals_are_13_contiguous_calendar_quarters():
    p = _load()
    labels = [a.quarter_label for a in p.actuals]
    assert labels == [
        f"{y}Q{q}" for y in (2023, 2024, 2025) for q in (1, 2, 3, 4)
    ] + ["2026Q1"]
    assert len(labels) == 13  # >= 13 is the backtest_generic minimum


def test_fy_sum_identity_holds_for_revenue_and_ni_to_common():
    p = _load()
    by_year: dict[int, list] = {}
    for a in p.actuals:
        by_year.setdefault(int(a.quarter_label[:4]), []).append(a)
    # as-filed FY totals: revenue, net income attributable to common stock
    expected = {2023: (14779, 1343), 2024: (17224, 2467), 2025: (17738, 752)}
    for year, (fy_rev, fy_ni) in expected.items():
        rows = by_year[year]
        assert len(rows) == 4, year
        # $1M rounding tolerance is documented in the profile notes (2023 revenue)
        assert sum(r.revenue_total for r in rows) == pytest.approx(fy_rev, abs=1), year
        assert sum(r.net_profit for r in rows) == fy_ni, year


def test_derived_eps_matches_as_filed_within_tolerance():
    p = _load()
    checked = 0
    for a in p.actuals:
        m = re.search(r"as-filed diluted EPS ([0-9.]+)", a.source)
        if not m:
            continue  # Q4 rows and rows tagged only with NI carry no as-filed EPS
        assert a.eps_diluted == pytest.approx(float(m.group(1)), abs=0.03), a.quarter_label
        checked += 1
    assert checked >= 6


def test_net_profit_is_the_after_preferred_common_basis():
    # net_profit CONTRACT: NI attributable to common (post preferred dividends),
    # so 2025Q1 must be the -317 loss-to-common, not the +? consolidated figure.
    p = _load()
    rows = {a.quarter_label: a for a in p.actuals}
    assert rows["2025Q1"].net_profit == -317
    assert rows["2026Q1"].net_profit == 980
    assert rows["2026Q1"].eps_diluted == pytest.approx(2.87, abs=0.01)


def test_T1_gaap_op_margin_is_not_anchorable():
    """The invariant this whole profile exists to record.

    A merchant IPP marks its hedge book through revenue AND cost of revenue, so
    quarterly GAAP operating margin is a function of forward-curve marks. If a
    future edit ever makes this series look anchorable, the (C)+(A) verdict in
    reports/vst_q2_2026_forecast_FROZEN.md must be revisited, not silently kept.
    """
    p = _load()
    rev = [a.revenue_total for a in p.actuals]
    assert len(rev) == len(GAAP_OP)
    margins = [op / r for op, r in zip(GAAP_OP, rev)]
    mean = statistics.fmean(margins)
    stdev = statistics.stdev(margins)
    assert min(margins) < 0 < max(margins)          # sign flips inside the window
    assert stdev / mean > 0.5                        # CV ~0.70: dispersion > half the level
    assert max(margins) - min(margins) > 0.40        # >40pp peak-to-trough


def test_forward_base_2026q2_calibration_is_frozen():
    p = _load()
    base = p.base
    # growth[0] de-MTMs the seed (+$723M unrealized gain) AND carries physical
    # growth; it is NOT a seasonal number. Frozen target: $4,800M.
    rev_q2 = p.seed.revenue_total * (1 + base.revenue_growth_qoq[0])
    assert rev_q2 == pytest.approx(4800, abs=5)
    op = rev_q2 * base.margin(1)[0]
    assert op == pytest.approx(1041, abs=10)         # adj EBITDA 1680 - D&A 620 - AC 20
    pretax = op + base.net_interest(1)[0] * rev_q2
    net = pretax * (1 - base.tax(1)[0])
    eps = net * 1_000_000 / p.weighted_avg_diluted
    assert eps == pytest.approx(1.75, abs=0.03)      # FROZEN base GAAP diluted EPS


def test_backtest_uses_calendar_slots_and_records_the_eps_failure():
    # DELTA §R4: seasonal issuer -> backtest_methodology must exist and be a
    # 4-slot calendar vector, distinct from the positional forward vectors.
    p = _load()
    bm = p.backtest_methodology
    assert bm is not None
    assert len(bm.revenue_growth_qoq) == 4
    assert len(bm.op_margin) == 4
    assert bm.revenue_growth_qoq != p.base.revenue_growth_qoq

    bt = backtest_generic(p)          # dict; *_mape are in PERCENT
    assert bt["n"] >= 12
    # Revenue is forecastable; GAAP EPS is not. Both beat naive RW, but the
    # absolute EPS error is an order of magnitude worse than the mature issuers
    # in this repo (TXN / SK Hynix ~10%). That gap IS the T1 finding.
    assert bt["revenue_mape"] < 20.0
    assert bt["eps_mape"] > 50.0
    assert bt["eps_mape"] < bt["naive_rw_eps_mape"]
