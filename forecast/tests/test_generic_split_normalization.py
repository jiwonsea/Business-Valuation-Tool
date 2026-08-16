"""NVDA-1c: split_history normalization + derived EPS + no implied-shares seams.

The last block loads the committed NVDA/TSLA profiles and asserts the exact
property whose violation started this workstream: NI-implied diluted shares
must sit on ONE (current) basis across the whole window — no 0.62B → 2.5B →
24.5B steps at data-assembly boundaries.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from schemas.generic import GenericProfile

REPO_ROOT = Path(__file__).resolve().parent.parent

NVDA_SPLITS = [
    {"date": date(2021, 7, 20), "ratio": 4},   # 4:1, Jul 2021
    {"date": date(2024, 6, 10), "ratio": 10},  # 10:1, Jun 2024
]


def _profile(**overrides) -> GenericProfile:
    base = dict(
        name="Test Co",
        name_kr="테스트",
        ticker="TST",
        currency="USD",
        reporting_unit="USD_million",
        fiscal_year_end_month=1,
        weighted_avg_diluted=24_490_000_000,
        seed=dict(quarter_label="2026Q1", revenue_total=81615.0),
        window=dict(start_quarter="2026Q2", n_quarters=4),
        actuals=[],
        split_history=NVDA_SPLITS,
        bear=dict(probability=0.25, revenue_growth_qoq=[0.0] * 4, op_margin=0.5, effective_tax_rate=0.15),
        base=dict(probability=0.50, revenue_growth_qoq=[0.05] * 4, op_margin=0.6, effective_tax_rate=0.15),
        bull=dict(probability=0.25, revenue_growth_qoq=[0.10] * 4, op_margin=0.65, effective_tax_rate=0.15),
    )
    base.update(overrides)
    return GenericProfile.model_validate(base)


def test_split_factor_compounds_only_later_splits():
    p = _profile()
    assert p.split_factor(date(2019, 10, 27)) == pytest.approx(40.0)  # before both
    assert p.split_factor(date(2021, 8, 1)) == pytest.approx(10.0)    # after 4:1, before 10:1
    assert p.split_factor(date(2024, 7, 28)) == pytest.approx(1.0)    # after both


def test_eps_derived_from_as_filed_shares_on_current_basis():
    # NVDA FY2020Q3: NI $899M, as-filed diluted 618M shares (as-filed EPS 1.45).
    p = _profile(
        actuals=[
            dict(
                quarter_label="2019Q3",
                revenue_total=3014.0,
                net_profit=899.0,
                period_end=date(2019, 10, 27),
                diluted_shares=618e6,
            )
        ]
    )
    a = p.actuals[0]
    assert a.eps_diluted == pytest.approx(899e6 / (618e6 * 40))  # ≈ 0.0364, current basis
    # Real dilution preserved: NOT NI / fixed 24.49B (= 0.0367).
    assert a.eps_diluted != pytest.approx(899e6 / 24.49e9, rel=1e-3)


def test_derived_eps_overrides_stored_eps_fact():
    # Storing a (mixed-basis) EPS fact next to diluted_shares must NOT win.
    p = _profile(
        actuals=[
            dict(
                quarter_label="2019Q3",
                revenue_total=3014.0,
                net_profit=899.0,
                eps_diluted=1.45,  # as-filed pre-split fact — the old bug
                period_end=date(2019, 10, 27),
                diluted_shares=618e6,
            )
        ]
    )
    assert p.actuals[0].eps_diluted == pytest.approx(899e6 / (618e6 * 40))


def test_diluted_shares_without_period_end_rejected():
    with pytest.raises(ValueError, match="period_end"):
        _profile(actuals=[dict(quarter_label="2019Q3", revenue_total=3014.0, net_profit=899.0, diluted_shares=618e6)])


def test_legacy_profile_without_shares_keeps_stored_eps():
    p = _profile(actuals=[dict(quarter_label="2019Q3", revenue_total=3014.0, eps_diluted=0.11)])
    assert p.actuals[0].eps_diluted == pytest.approx(0.11)


# ---------- Seam checks on the committed real profiles ----------


def _load(name: str) -> GenericProfile:
    with open(REPO_ROOT / "profiles" / name, encoding="utf-8") as fh:
        return GenericProfile.model_validate(yaml.safe_load(fh))


def _implied_shares(profile: GenericProfile) -> list[float]:
    out = []
    for a in profile.actuals:
        assert a.net_profit is not None and a.eps_diluted, f"{a.quarter_label}: missing NI/EPS"
        out.append(a.net_profit * profile.unit_scale / a.eps_diluted)
    return out


@pytest.mark.parametrize(
    "profile_name,low,high",
    [("nvda.generic.yaml", 20e9, 30e9), ("tsla.generic.yaml", 2.5e9, 3.7e9)],
)
def test_no_implied_share_seams_in_committed_profiles(profile_name, low, high):
    profile = _load(profile_name)
    implied = _implied_shares(profile)
    assert len(implied) >= 20
    # One basis across the whole window…
    assert all(low <= s <= high for s in implied), [f"{s:,.0f}" for s in implied]
    # …and no step seams between adjacent quarters (old profile stepped 4x/10x).
    for prev, cur in zip(implied, implied[1:]):
        assert max(prev, cur) / min(prev, cur) < 1.2


def test_committed_profiles_are_contiguous():
    from generic_cli import backtest_generic

    for name in ("nvda.generic.yaml", "tsla.generic.yaml"):
        bt = backtest_generic(_load(name))
        assert bt.get("revenue_mape") is not None, f"{name}: {bt.get('note')}"
        assert bt["n"] == 26  # 27 contiguous quarters -> 26 one-step pairs
