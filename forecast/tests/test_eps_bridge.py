"""Tests for engine.eps_bridge.project_eps."""

from __future__ import annotations

import pytest

from engine.eps_bridge import project_eps
from schemas.models import QuarterlyForecast, SegmentForecast, SharesOutstanding


def test_eps_simple_division():
    """EPS = NI / weighted_avg_shares for each forecast quarter."""
    forecast = QuarterlyForecast(
        quarter_label="2026Q1",
        revenue_total=100.0,
        revenue_by_segment=[SegmentForecast(segment_id="dram", revenue=100.0)],
        gross_profit=40.0,
        operating_profit=30.0,
        net_profit=10.0,
        gp_margin=0.4,
        op_margin=0.3,
        np_margin=0.1,
    )

    result = project_eps([forecast], SharesOutstanding(weighted_avg_basic=1_000_000, weighted_avg_diluted=2_000_000))

    assert result[0].eps_basic == pytest.approx(10_000.0)
    assert result[0].eps_diluted == pytest.approx(5_000.0)
