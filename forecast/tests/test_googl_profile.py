"""GOOGL-1 (2026-07-22): integrity checks on the committed googl.generic profile.

Alphabet's actuals were rebuilt from EDGAR as-filed originals (2024Q2..2026Q2,
9 contiguous quarters, Q4s restored). Unlike NVDA/TSLA the whole window is POST
the 20:1 split (2022-07-15) so split_history is EMPTY and shares sit on a single
basis. These tests pin: single-basis diluted shares, no seams, derived-EPS ==
as-filed, contiguity/backtest-scores, and the FY2025 sum identity.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from schemas.generic import GenericProfile

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load() -> GenericProfile:
    with open(REPO_ROOT / "profiles" / "googl.generic.yaml", encoding="utf-8") as fh:
        return GenericProfile.model_validate(yaml.safe_load(fh))


def test_googl_window_is_contiguous_and_post_split():
    p = _load()
    labels = [a.quarter_label for a in p.actuals]
    assert labels == [
        "2024Q2", "2024Q3", "2024Q4", "2025Q1",
        "2025Q2", "2025Q3", "2025Q4", "2026Q1",
        "2026Q2",
    ]
    # Whole window post the 20:1 split -> no split adjustment applied.
    assert p.split_history == []


def test_googl_single_share_basis_no_seams():
    p = _load()
    implied = [a.net_profit * p.unit_scale / a.eps_diluted for a in p.actuals]
    # One basis across the window (post-split ~12.2-12.5B diluted).
    assert all(12.0e9 <= s <= 12.6e9 for s in implied), [f"{s:,.0f}" for s in implied]
    for prev, cur in zip(implied, implied[1:]):
        assert max(prev, cur) / min(prev, cur) < 1.05  # no split/basis step


def test_googl_derived_eps_matches_as_filed():
    p = _load()
    by_label = {a.quarter_label: a for a in p.actuals}
    # NI / as-filed diluted shares == derived EPS == as-filed EPS in `source`.
    assert by_label["2024Q2"].eps_diluted == pytest.approx(1.89, abs=0.01)
    assert by_label["2025Q1"].eps_diluted == pytest.approx(2.81, abs=0.01)
    assert by_label["2026Q1"].eps_diluted == pytest.approx(5.11, abs=0.01)
    assert by_label["2026Q2"].eps_diluted == pytest.approx(9.11, abs=0.01)
    assert by_label["2026Q2"].net_profit == 112193
    assert by_label["2026Q2"].diluted_shares == 12_309_000_000
    assert "0001652044-26-000071" in by_label["2026Q2"].source


def test_googl_postprint_actual_does_not_roll_forward_window():
    p = _load()
    assert p.seed.quarter_label == "2026Q1"
    assert p.window.start_quarter == "2026Q2"


def test_googl_fy2025_sum_identity():
    p = _load()
    by = {a.quarter_label: a for a in p.actuals}
    q = ["2025Q1", "2025Q2", "2025Q3", "2025Q4"]
    rev_sum = sum(by[x].revenue_total for x in q)
    ni_sum = sum(by[x].net_profit for x in q)
    assert rev_sum == pytest.approx(402836, abs=2)   # 10-K FY2025 revenue
    assert ni_sum == pytest.approx(132170, abs=2)    # 10-K FY2025 net income


def test_googl_backtest_scores_and_beats_naive_revenue():
    from generic_cli import backtest_generic

    bt = backtest_generic(_load())
    assert bt.get("revenue_mape") is not None, bt.get("note")
    assert bt["n"] == 8  # 9 contiguous quarters -> 8 one-step pairs
    # Revenue model must beat the naive random walk (the model's real edge).
    assert bt["revenue_mape"] < bt["naive_rw_revenue_mape"]
