"""TXN-1 (2026-07-22): integrity + forecast checks for profiles/txn.generic.yaml.

Guards the EDGAR-sourced actuals block (contiguity, FY-sum identity, derived-EPS
coherence, no-split) and the forward Q2 2026 calibration so a later hand-edit of
the profile can't silently corrupt the frozen-forecast basis. Pure/offline:
loads the real profile and the gitignored derived companyfacts cache when present.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.generic_forecast import run_generic_forecast
from generic_cli import backtest_generic, load_generic_profile

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load():
    return load_generic_profile(REPO_ROOT / "profiles" / "txn.generic.yaml")


def test_profile_loads_and_header_contract():
    p = _load()
    assert p.ticker == "TXN"
    assert p.fiscal_year_end_month == 12  # calendar filer, no consensus-join offset
    assert p.reporting_unit == "USD_million"
    assert p.split_history == []  # no splits in the covered window
    assert p.seed.quarter_label == "2026Q1"
    assert p.window.start_quarter == "2026Q2" and p.window.n_quarters == 4


def test_actuals_are_21_contiguous_calendar_quarters():
    p = _load()
    labels = [a.quarter_label for a in p.actuals]
    assert labels == [
        f"{y}Q{q}" for y in range(2021, 2026) for q in (1, 2, 3, 4)
    ] + ["2026Q1"]
    assert len(labels) == 21


def test_derived_eps_matches_as_filed_within_tolerance():
    # NVDA-1c: eps_diluted is DERIVED from net_profit / diluted_shares at load;
    # it must reconcile to the as-filed EPS preserved in each row's source.
    import re

    p = _load()
    for a in p.actuals:
        m = re.search(r"as-filed EPS ([0-9.]+)", a.source)
        if not m:
            continue  # Q4 rows carry no as-filed quarterly EPS
        as_filed = float(m.group(1))
        assert a.eps_diluted == pytest.approx(as_filed, abs=0.03), a.quarter_label


def test_fy_sum_identity_holds_for_revenue_and_ni():
    # The four standalone quarters of each complete FY must sum to that year's
    # reported 10-K totals (the guard build_generic_actuals enforced at build).
    p = _load()
    by_label = {a.quarter_label: a for a in p.actuals}
    fy_reported = {  # (revenue_total, net_profit) in USD_million, from 10-Ks
        2021: (18344, 7769),
        2022: (20028, 8749),
        2023: (17519, 6510),
        2024: (15641, 4799),
        2025: (17682, 5001),
    }
    for year, (rev, ni) in fy_reported.items():
        qs = [by_label[f"{year}Q{q}"] for q in (1, 2, 3, 4)]
        assert sum(a.revenue_total for a in qs) == pytest.approx(rev)
        assert sum(a.net_profit for a in qs) == pytest.approx(ni)


def test_derived_cache_present_and_shaped():
    # The EDGAR cache under reports/.cache/ is gitignored (reproducible via
    # scripts/build_generic_actuals.py or host fetch_companyfacts), so a fresh
    # checkout / CI may not have it — skip rather than hard-fail, matching the
    # suite's tolerance of absent caches. When present, sanity-check its shape.
    cache = REPO_ROOT / "reports" / ".cache" / "edgar_companyfacts_CIK0000097476.json"
    if not cache.exists():
        pytest.skip("derived EDGAR cache absent (gitignored) — rebuild to populate")
    blob = json.loads(cache.read_text(encoding="utf-8"))
    gaap = blob["facts"]["us-gaap"]
    assert "NetIncomeLoss" in gaap
    assert "RevenueFromContractWithCustomerExcludingAssessedTax" in gaap


def test_backtest_reports_three_regime_windows():
    bt = backtest_generic(_load())
    assert set(bt["windows"]) == {"full", "pre_break", "post_break"}
    assert bt["windows"]["full"]["n"] == 20  # 21 actuals -> 20 one-step pairs
    # post-break (recovery regime) is the relevant skill read; revenue tracks
    # persistence rather than badly trailing it.
    assert bt["windows"]["post_break"]["skill"]["mase_revenue"] < 1.1


def test_forward_q2_2026_lands_near_guidance_and_consensus():
    # Frozen-forecast anchor: base Q2 2026 EPS at the company guide midpoint
    # ($1.91) / Street ($1.92); weighted revenue within the $5.0-5.4B guide.
    p = _load()
    fc = run_generic_forecast(p)
    q2 = fc.weighted_quarterly[0]
    assert q2.quarter_label == "2026Q2"
    assert 5000 <= q2.revenue_total <= 5400
    assert 1.80 <= (q2.eps_diluted or 0.0) <= 2.00
    base_q2 = fc.scenarios_quarterly["base"][0]
    assert base_q2.eps_diluted == pytest.approx(1.91, abs=0.05)
