"""Unit tests for engine/relative_metrics.py (pure functions)."""

import math

from engine.relative_metrics import (
    OK,
    CAUTION,
    NA,
    trailing_pe,
    price_to_book,
    ev_ebitda,
    ev_sales,
    dividend_yield,
    peg,
    pegy,
    justified_pe,
    justified_pb,
    multiple_verdict,
)


# ── Tier 1: current-price ratios ──────────────────────────────────────────


def test_trailing_pe_basic():
    m = trailing_pe(price=100.0, eps=5.0)
    assert m.status == OK
    assert m.value == 20.0


def test_trailing_pe_negative_earnings_na():
    m = trailing_pe(price=100.0, eps=-2.0)
    assert m.status == NA
    assert m.value is None


def test_price_to_book_capital_impairment_na():
    m = price_to_book(price=100.0, book_value_per_share=-10.0)
    assert m.status == NA


def test_ev_ebitda_includes_net_debt():
    m = ev_ebitda(market_cap=800, net_debt=200, ebitda=100)
    assert m.value == 10.0  # (800+200)/100


def test_ev_sales_negative_net_debt():
    m = ev_sales(market_cap=1000, net_debt=-100, revenue=300)
    assert m.value == round(900 / 300, 2)


def test_dividend_yield_zero_dividend_is_ok():
    m = dividend_yield(dps=0.0, price=50.0)
    assert m.status == OK
    assert m.value == 0.0


# ── Tier 2: PEG / PEGY guardrails ─────────────────────────────────────────


def test_peg_basic():
    m = peg(pe=20.0, growth_pct=10.0, growth_source="analyst")
    assert m.status == OK
    assert m.value == 2.0
    assert "analyst" in m.note


def test_peg_low_growth_na():
    m = peg(pe=20.0, growth_pct=1.0)
    assert m.status == NA
    assert m.value is None


def test_peg_negative_earnings_na():
    m = peg(pe=-5.0, growth_pct=15.0)
    assert m.status == NA


def test_peg_financial_caution():
    m = peg(pe=12.0, growth_pct=6.0, is_financial=True)
    assert m.status == CAUTION
    assert m.value == 2.0  # value still computed, but flagged


def test_peg_cyclical_caution():
    m = peg(pe=8.0, growth_pct=4.0, is_cyclical=True)
    assert m.status == CAUTION


def test_pegy_adds_yield_to_denominator():
    # PEG would be 20/4 = 5.0 (looks expensive); PEGY with 3% yield = 20/7
    m = pegy(pe=20.0, growth_pct=4.0, dividend_yield_pct=3.0)
    assert m.status == OK
    assert m.value == round(20.0 / 7.0, 2)


def test_pegy_low_combined_denominator_na():
    m = pegy(pe=20.0, growth_pct=1.0, dividend_yield_pct=0.5)
    assert m.status == NA


# ── Tier 3: justified multiples ───────────────────────────────────────────


def test_justified_pe_gordon():
    # payout 50%, g 3%, ke 9% -> 0.5*1.03/(0.09-0.03) = 8.583...
    m = justified_pe(payout_ratio_pct=50.0, growth_pct=3.0, ke_pct=9.0)
    assert m.status == OK
    assert math.isclose(m.value, round(0.5 * 1.03 / 0.06, 2), rel_tol=1e-9)


def test_justified_pe_narrow_spread_na():
    m = justified_pe(payout_ratio_pct=50.0, growth_pct=8.8, ke_pct=9.0)
    assert m.status == NA


def test_justified_pb_roe_driven():
    # ROE 15%, g 3%, ke 9% -> (0.15-0.03)/(0.09-0.03) = 2.0
    m = justified_pb(roe_pct=15.0, growth_pct=3.0, ke_pct=9.0)
    assert m.status == OK
    assert m.value == 2.0


def test_justified_pb_below_one_when_roe_below_ke():
    m = justified_pb(roe_pct=6.0, growth_pct=2.0, ke_pct=9.0)
    assert m.value < 1.0  # value destroyer trades below book


def test_justified_pb_non_positive_is_not_reported():
    m = justified_pb(roe_pct=-2.0, growth_pct=2.0, ke_pct=9.0)
    assert m.status == NA
    assert m.value is None
    assert "0 이하" in m.note


# ── verdict ───────────────────────────────────────────────────────────────


def test_verdict_undervalued():
    v = multiple_verdict("P/B", actual=1.0, justified=2.0)
    assert v.verdict == "저평가"
    assert v.gap_pct == -50.0


def test_verdict_overvalued():
    v = multiple_verdict("P/E", actual=30.0, justified=10.0)
    assert v.verdict == "고평가"


def test_verdict_fair_within_band():
    v = multiple_verdict("P/E", actual=10.5, justified=10.0)
    assert v.verdict == "적정"


def test_verdict_missing_data():
    v = multiple_verdict("P/E", actual=None, justified=10.0)
    assert v.verdict == "판단불가"
