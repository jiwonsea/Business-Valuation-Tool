"""Tests for engine.segment_revenue.project_quarterly_revenue.

Codex: fill in with at least:
  - happy path: 1Q seed + 4Q assumptions -> 4 forecast quarters
  - HBM share blending edge case (0% and 100%)
  - quarter label rollover (Q4 -> Q1 next year)
"""

from __future__ import annotations

import pytest

from datetime import date

from engine.segment_revenue import _next_quarter_label, project_quarterly_revenue
from schemas.models import MarginBaseline, QuarterlyActual, SegmentAssumptions, SegmentForecast


def _actual(label: str = "2025Q4") -> QuarterlyActual:
    return QuarterlyActual(
        quarter_label=label,
        period_end=date(2025, 12, 31),
        revenue_total=100.0,
        revenue_by_segment=[
            SegmentForecast(segment_id="dram", revenue=60.0),
            SegmentForecast(segment_id="nand", revenue=30.0),
            SegmentForecast(segment_id="other", revenue=10.0),
        ],
        gross_profit=40.0,
        operating_profit=25.0,
        net_profit=20.0,
    )


def _assumptions(hbm: list[float] | None = None) -> SegmentAssumptions:
    return SegmentAssumptions(
        dram_bit_growth_qoq=[0.0, 0.0, 0.0, 0.0],
        dram_hbm_share_qoq=hbm or [0.5, 0.5, 0.5, 0.5],
        dram_hbm_asp_yoy=0.0,
        dram_ddr_asp_qoq=[0.0, 0.0, 0.0, 0.0],
        nand_bit_growth_qoq=[0.0, 0.0, 0.0, 0.0],
        nand_asp_qoq=[0.0, 0.0, 0.0, 0.0],
        other_revenue_growth_qoq=[0.0, 0.0, 0.0, 0.0],
    )


def test_project_quarterly_revenue_happy_path():
    result = project_quarterly_revenue(_actual(), MarginBaseline(dram_blended_asp=1.0, nand_blended_asp=1.0), _assumptions(), 4)

    assert [q.quarter_label for q in result] == ["2026Q1", "2026Q2", "2026Q3", "2026Q4"]
    assert result[0].revenue_total == pytest.approx(100.0)
    assert result[0].hbm_share == pytest.approx(0.5)
    assert result[0].asp_hbm == pytest.approx(1.0)
    assert result[0].asp_ddr == pytest.approx(1.0)
    assert result[0].asp_nand == pytest.approx(1.0)
    assert result[0].margin_periods_since_anchor == 1


def test_project_quarterly_revenue_stamps_asp_indexes():
    assumptions = SegmentAssumptions(
        dram_bit_growth_qoq=[0.0, 0.0],
        dram_hbm_share_qoq=[0.5, 0.5],
        dram_hbm_asp_yoy=0.20,
        dram_ddr_asp_qoq=[0.10, 0.10],
        nand_bit_growth_qoq=[0.0, 0.0],
        nand_asp_qoq=[-0.10, 0.20],
        other_revenue_growth_qoq=[0.0, 0.0],
    )

    result = project_quarterly_revenue(
        _actual(),
        MarginBaseline(dram_blended_asp=1.0, nand_blended_asp=1.0),
        assumptions,
        2,
    )

    assert result[0].asp_hbm == pytest.approx(1.05)
    assert result[0].asp_ddr == pytest.approx(1.10)
    assert result[0].asp_nand == pytest.approx(0.90)
    assert result[1].asp_hbm == pytest.approx(1.05 * 1.05)
    assert result[1].asp_ddr == pytest.approx(1.10 * 1.10)
    assert result[1].asp_nand == pytest.approx(0.90 * 1.20)


def test_hbm_share_zero_and_one():
    result = project_quarterly_revenue(_actual(), MarginBaseline(dram_blended_asp=1.0, nand_blended_asp=1.0), _assumptions([0.0, 1.0, 0.0, 1.0]), 2)

    assert result[0].revenue_by_segment[0].revenue == pytest.approx(60.0)
    assert result[1].revenue_by_segment[0].revenue == pytest.approx(60.0)
    assert [q.hbm_share for q in result] == [0.0, 1.0]


def test_quarter_rollover():
    assert _next_quarter_label("2026Q4") == "2027Q1"
