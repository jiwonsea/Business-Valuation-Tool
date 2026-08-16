"""NVDA-2 stage 2a: shared skill, regime windows, and historical shares."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from engine.generic_forecast import run_generic_forecast
from engine.generic_signal import build_signal_block
from generic_cli import backtest_generic, load_generic_profile, render_markdown
from schemas.generic import GenericProfile

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load(name: str) -> GenericProfile:
    return load_generic_profile(REPO_ROOT / "profiles" / f"{name}.generic.yaml")


@pytest.mark.parametrize("name", ["nvda", "tsla"])
def test_shared_skill_rw_mape_matches_legacy_percent(name: str) -> None:
    backtest = backtest_generic(_load(name))
    skill = backtest["skill"]

    assert backtest["naive_rw_revenue_mape"] == pytest.approx(
        skill["naive_rw_revenue_mape"] * 100
    )
    assert backtest["naive_rw_eps_mape"] == pytest.approx(
        skill["naive_rw_eps_mape"] * 100
    )
    assert skill["skill_score_eps_vs_consensus"] is None
    assert skill["n_surprise_scored"] == 0


@pytest.mark.parametrize("name", ["nvda", "tsla"])
def test_regime_windows_partition_full_rows_and_ape_numerators(name: str) -> None:
    backtest = backtest_generic(_load(name))
    full = backtest["windows"]["full"]
    pre = backtest["windows"]["pre_break"]
    post = backtest["windows"]["post_break"]

    full_quarters = [row["quarter"] for row in full["rows"]]
    partition_quarters = [row["quarter"] for row in pre["rows"] + post["rows"]]
    assert partition_quarters == full_quarters
    assert len(set(partition_quarters)) == len(partition_quarters)
    assert full["n"] == pre["n"] + post["n"]
    assert full["n_eps"] == pre["n_eps"] + post["n_eps"]
    assert post["rows"][0]["quarter"] == "2023Q2"
    assert all(row["quarter"] < "2023Q2" for row in pre["rows"])

    def revenue_ape_numerator(rows: list[dict]) -> float:
        return sum(
            abs(row["model_rev"] - row["actual_rev"]) / abs(row["actual_rev"])
            for row in rows
            if row["actual_rev"]
        )

    def eps_ape_numerator(rows: list[dict]) -> float:
        return sum(
            abs(row["model_eps"] - row["actual_eps"]) / abs(row["actual_eps"])
            for row in rows
            if row.get("actual_eps") not in (None, 0) and row.get("model_eps") is not None
        )

    assert revenue_ape_numerator(full["rows"]) == pytest.approx(
        revenue_ape_numerator(pre["rows"]) + revenue_ape_numerator(post["rows"])
    )
    assert eps_ape_numerator(full["rows"]) == pytest.approx(
        eps_ape_numerator(pre["rows"]) + eps_ape_numerator(post["rows"])
    )


def _profile(actuals: list[dict], **overrides) -> GenericProfile:
    raw = dict(
        name="Test Co",
        name_kr="테스트",
        ticker="TST",
        currency="USD",
        reporting_unit="USD_million",
        fiscal_year_end_month=12,
        weighted_avg_diluted=1_000_000_000,
        seed=dict(quarter_label="2025Q4", revenue_total=1000.0),
        window=dict(start_quarter="2026Q1", n_quarters=4),
        actuals=actuals,
        bear=dict(probability=0.25, revenue_growth_qoq=[0.0] * 4, op_margin=0.10, effective_tax_rate=0.20),
        base=dict(probability=0.50, revenue_growth_qoq=[0.0] * 4, op_margin=0.20, effective_tax_rate=0.20),
        bull=dict(probability=0.25, revenue_growth_qoq=[0.0] * 4, op_margin=0.30, effective_tax_rate=0.20),
    )
    raw.update(overrides)
    return GenericProfile.model_validate(raw)


def test_historical_model_eps_uses_split_adjusted_prior_shares() -> None:
    profile = _profile(
        actuals=[
            dict(
                quarter_label="2025Q3",
                period_end=date(2025, 9, 30),
                revenue_total=1000.0,
                net_profit=100.0,
                diluted_shares=100_000_000,
            ),
            dict(
                quarter_label="2025Q4",
                period_end=date(2025, 12, 31),
                revenue_total=1000.0,
                net_profit=100.0,
                diluted_shares=210_000_000,
            ),
        ],
        split_history=[{"date": date(2025, 10, 1), "ratio": 2}],
    )

    row = backtest_generic(profile)["rows"][0]
    assert row["model_eps_share_count"] == pytest.approx(200_000_000)
    assert row["model_eps_share_convention"] == "prior_quarter_split_adjusted"
    assert row["model_eps"] == pytest.approx(160.0 * 1_000_000 / 200_000_000)


def test_historical_model_eps_falls_back_to_fixed_forward_shares() -> None:
    profile = _profile(
        actuals=[
            dict(quarter_label="2025Q3", revenue_total=1000.0, eps_diluted=0.10),
            dict(quarter_label="2025Q4", revenue_total=1000.0, eps_diluted=0.11),
        ]
    )

    row = backtest_generic(profile)["rows"][0]
    assert row["model_eps_share_count"] == pytest.approx(1_000_000_000)
    assert row["model_eps_share_convention"] == "fixed_forward_fallback"


def test_signal_uses_post_break_as_primary_window() -> None:
    rows = []
    for index in range(10):
        actual = 10.0
        rows.append(
            {
                "quarter": f"202{index // 4}Q{index % 4 + 1}",
                "actual_eps": actual,
                "model_eps": 15.0 if index < 2 else 10.1,
                "rw_eps": 11.0,
            }
        )
    backtest = {
        "n": 10,
        "rows": rows,
        "windows": {"post_break": {"rows": rows[2:]}},
    }
    annual = [{"fiscal_year": 2026, "eps_basic": 11.0}]
    quarterly = [
        {"quarter_label": "2026Q1", "eps_diluted": 2.0},
        {"quarter_label": "2026Q4", "eps_diluted": 2.6},
    ]

    skill = build_signal_block(annual, quarterly, backtest)["skill"]
    assert skill["primary_window_name"] == "post_break"
    assert skill["primary_window"]["n"] == 8
    assert skill["full_window"]["beats_naive"] is False
    assert skill["primary_window"]["beats_naive"] is True
    assert skill["full_vs_primary_disagreement"] is True
    assert skill["skill_pass"] is True


def test_signal_without_regime_windows_keeps_full_as_primary() -> None:
    rows = [
        {"quarter": f"202{i // 4}Q{i % 4 + 1}", "actual_eps": 10.0, "model_eps": 10.1, "rw_eps": 11.0}
        for i in range(8)
    ]
    annual = [{"fiscal_year": 2026, "eps_basic": 11.0}]
    quarterly = [
        {"quarter_label": "2026Q1", "eps_diluted": 2.0},
        {"quarter_label": "2026Q4", "eps_diluted": 2.6},
    ]

    skill = build_signal_block(annual, quarterly, {"n": 8, "rows": rows})["skill"]
    assert skill["primary_window_name"] == "full"
    assert skill["primary_window"] == skill["full_window"]
    assert skill["full_vs_primary_disagreement"] is False


def test_report_formats_skill_mape_ratios_as_percent() -> None:
    profile = _load("nvda")
    backtest = backtest_generic(profile)
    report = render_markdown(profile, run_generic_forecast(profile), backtest)
    post_skill = backtest["windows"]["post_break"]["skill"]
    expected = (
        f"RW MAPE 매출 {post_skill['naive_rw_revenue_mape'] * 100:.1f}% / "
        f"EPS {post_skill['naive_rw_eps_mape'] * 100:.1f}%"
    )
    assert expected in report
