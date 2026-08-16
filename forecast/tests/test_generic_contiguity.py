"""NVDA-1b: backtest_generic must refuse non-contiguous actuals (no Q3→Q1 joins)."""

from __future__ import annotations

from generic_cli import backtest_generic
from schemas.generic import GenericProfile


def _profile(actuals: list[dict]) -> GenericProfile:
    return GenericProfile.model_validate(
        dict(
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
            base=dict(probability=0.50, revenue_growth_qoq=[0.05] * 4, op_margin=0.20, effective_tax_rate=0.20),
            bull=dict(probability=0.25, revenue_growth_qoq=[0.10] * 4, op_margin=0.30, effective_tax_rate=0.20),
        )
    )


def test_q3_to_q1_join_is_refused():
    # The exact defect the old NVDA profile had: no Q4 rows anywhere.
    p = _profile(
        [
            dict(quarter_label="2024Q2", revenue_total=900.0, eps_diluted=0.09),
            dict(quarter_label="2024Q3", revenue_total=950.0, eps_diluted=0.10),
            dict(quarter_label="2025Q1", revenue_total=1000.0, eps_diluted=0.11),
        ]
    )
    bt = backtest_generic(p)
    assert bt["n"] == 0
    assert "2024Q3 → 2025Q1" in bt["note"]
    assert "revenue_mape" not in bt  # no metrics computed on a broken join


def test_year_boundary_q4_to_q1_is_contiguous():
    p = _profile(
        [
            dict(quarter_label="2024Q3", revenue_total=900.0, eps_diluted=0.09),
            dict(quarter_label="2024Q4", revenue_total=950.0, eps_diluted=0.10),
            dict(quarter_label="2025Q1", revenue_total=1000.0, eps_diluted=0.11),
        ]
    )
    bt = backtest_generic(p)
    assert bt["n"] == 2
    assert bt["revenue_mape"] is not None


def test_duplicate_labels_are_refused():
    p = _profile(
        [
            dict(quarter_label="2024Q3", revenue_total=900.0),
            dict(quarter_label="2024Q3", revenue_total=910.0),
            dict(quarter_label="2024Q4", revenue_total=950.0),
        ]
    )
    bt = backtest_generic(p)
    assert bt["n"] == 0 and "비연속" in bt["note"]
