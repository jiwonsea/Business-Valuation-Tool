from __future__ import annotations

from datetime import date

import pytest

from engine.attribution import attribute_eps_error
from schemas.models import QuarterlyActual, QuarterlyForecast, SegmentForecast

SHARES = 1_000_000_000  # 1e9 → eps = net_profit(KRW bn) × 1e9 / 1e9 = net_profit(KRW bn)


def _actual(
    *,
    revenue: float,
    gp_margin: float,
    op_conv: float,
    ni_conv: float,
    shares: int = SHARES,
) -> QuarterlyActual:
    gp = revenue * gp_margin
    op = gp * op_conv
    ni = op * ni_conv
    return QuarterlyActual(
        quarter_label="2025Q1",
        period_end=date(2025, 3, 31),
        revenue_total=revenue,
        revenue_by_segment=[SegmentForecast(segment_id="dram", revenue=revenue)],
        gross_profit=gp,
        operating_profit=op,
        net_profit=ni,
        eps_basic=ni * 1_000_000_000.0 / shares,
    )


def _forecast(
    *,
    revenue: float,
    gp_margin: float,
    op_conv: float,
    ni_conv: float,
) -> QuarterlyForecast:
    gp = revenue * gp_margin
    op = gp * op_conv
    ni = op * ni_conv
    return QuarterlyForecast(
        quarter_label="2025Q1",
        revenue_total=revenue,
        revenue_by_segment=[SegmentForecast(segment_id="dram", revenue=revenue)],
        gross_profit=gp,
        operating_profit=op,
        net_profit=ni,
        gp_margin=gp_margin,
        op_margin=gp_margin * op_conv,
        np_margin=ni / revenue,
        eps_basic=ni * 1_000_000_000.0 / SHARES,
    )


def test_contributions_sum_to_total_error():
    # Every lever differs between model and actual.
    actual = _actual(revenue=100.0, gp_margin=0.40, op_conv=0.6, ni_conv=0.8)
    forecast = _forecast(revenue=120.0, gp_margin=0.45, op_conv=0.7, ni_conv=0.75)

    attr = attribute_eps_error(actual, forecast, SHARES)

    total = (
        attr.contrib_revenue
        + attr.contrib_gross_margin
        + attr.contrib_opex
        + attr.contrib_tax_finance
        + attr.contrib_shares
    )
    assert total == pytest.approx(attr.eps_error_total)


def test_perfect_model_zero_error():
    actual = _actual(revenue=100.0, gp_margin=0.40, op_conv=0.6, ni_conv=0.8)
    forecast = _forecast(revenue=100.0, gp_margin=0.40, op_conv=0.6, ni_conv=0.8)

    attr = attribute_eps_error(actual, forecast, SHARES)

    assert attr.eps_error_total == pytest.approx(0.0)
    assert attr.contrib_revenue == pytest.approx(0.0)
    assert attr.contrib_gross_margin == pytest.approx(0.0)
    assert attr.contrib_opex == pytest.approx(0.0)
    assert attr.contrib_tax_finance == pytest.approx(0.0)
    assert attr.contrib_shares == pytest.approx(0.0)


def test_revenue_only_error_localizes_to_revenue():
    actual = _actual(revenue=100.0, gp_margin=0.40, op_conv=0.6, ni_conv=0.8)
    forecast = _forecast(revenue=110.0, gp_margin=0.40, op_conv=0.6, ni_conv=0.8)

    attr = attribute_eps_error(actual, forecast, SHARES)

    assert attr.contrib_revenue == pytest.approx(0.10)  # +10% revenue → +10% EPS
    assert attr.contrib_gross_margin == pytest.approx(0.0)
    assert attr.contrib_opex == pytest.approx(0.0)
    assert attr.contrib_tax_finance == pytest.approx(0.0)
    assert attr.contrib_shares == pytest.approx(0.0)


def test_gross_margin_only_error_localizes():
    actual = _actual(revenue=100.0, gp_margin=0.40, op_conv=0.6, ni_conv=0.8)
    forecast = _forecast(revenue=100.0, gp_margin=0.50, op_conv=0.6, ni_conv=0.8)

    attr = attribute_eps_error(actual, forecast, SHARES)

    assert attr.contrib_gross_margin == pytest.approx(0.25)  # 0.50/0.40 − 1
    assert attr.contrib_revenue == pytest.approx(0.0)
    assert attr.contrib_opex == pytest.approx(0.0)
    assert attr.contrib_tax_finance == pytest.approx(0.0)
    assert attr.contrib_shares == pytest.approx(0.0)


def test_share_count_only_error_localizes_to_shares():
    # Model uses a smaller (wrong) fixed share count than actual implied → EPS overshoot.
    actual = _actual(revenue=100.0, gp_margin=0.40, op_conv=0.6, ni_conv=0.8, shares=int(SHARES * 1.1))
    forecast = _forecast(revenue=100.0, gp_margin=0.40, op_conv=0.6, ni_conv=0.8)

    attr = attribute_eps_error(actual, forecast, SHARES)

    assert attr.contrib_shares == pytest.approx(attr.eps_error_total)
    assert attr.contrib_revenue == pytest.approx(0.0)
    assert attr.contrib_gross_margin == pytest.approx(0.0)
    assert attr.actual_implied_basic_shares == pytest.approx(SHARES * 1.1, rel=1e-6)


def test_missing_actual_eps_raises():
    actual = _actual(revenue=100.0, gp_margin=0.40, op_conv=0.6, ni_conv=0.8)
    actual = actual.model_copy(update={"eps_basic": None})
    forecast = _forecast(revenue=100.0, gp_margin=0.40, op_conv=0.6, ni_conv=0.8)

    with pytest.raises(ValueError):
        attribute_eps_error(actual, forecast, SHARES)
