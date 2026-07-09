"""Integration tests for the relative-valuation diagnostic wiring.

Verifies that valuation_runner._build_relative_valuation assembles the
ValuationResult.relative_valuation panel from a live ValuationInput, honouring:
  * sector guardrails (financial -> PEG/PEGY CAUTION),
  * fetched relative_inputs (analyst-consensus growth, forward/trailing EPS),
  * low-growth NA suppression,
  * justified-multiple verdicts.

Fixture lives in tests/fixtures/ (profiles/ is AI-regenerated -- see CLAUDE.md).
"""

from pathlib import Path

from valuation_runner import load_profile, _build_relative_valuation
from engine.wacc import calc_wacc
from schemas.models import ValuationResult, RelativeInputs

_FIXTURE = str(Path(__file__).parent / "fixtures" / "relative_financial.yaml")


def _build(vi, primary_method="multiples"):
    wr = calc_wacc(vi.wacc_params)
    res = ValuationResult(primary_method=primary_method, wacc=wr)
    return _build_relative_valuation(vi, res, wr)


def _ratio(rv, name):
    return next((m for m in rv.ratios if m.name == name), None)


def test_market_price_and_relative_inputs_loaded():
    vi = load_profile(_FIXTURE)
    assert vi.market_price == 80000
    assert vi.relative_inputs is not None
    assert vi.relative_inputs.forward_eps == 10000.0
    assert vi.relative_inputs.earnings_growth == 5.5


def test_financial_peg_is_caution():
    vi = load_profile(_FIXTURE)
    rv = _build(vi)
    assert rv is not None
    peg = _ratio(rv, "PEG")
    assert peg is not None and peg.status == "caution"
    assert "금융업" in peg.note


def test_consensus_growth_source_used():
    vi = load_profile(_FIXTURE)
    rv = _build(vi)
    assert rv.growth_source == "analyst consensus"
    assert rv.growth_pct == 5.5


def test_forward_pe_present_from_fetched_eps():
    vi = load_profile(_FIXTURE)
    rv = _build(vi)
    fwd = _ratio(rv, "Fwd P/E")
    assert fwd is not None and fwd.value is not None


def test_trailing_pe_prefers_fetched_eps():
    vi = load_profile(_FIXTURE)
    rv = _build(vi)
    pe = _ratio(rv, "P/E")
    # 80000 / 9000 (fetched trailing_eps) == 8.89
    assert pe is not None and pe.value == round(80000 / 9000.0, 2)


def test_low_growth_makes_peg_na():
    vi = load_profile(_FIXTURE)
    vi = vi.model_copy(
        update={"relative_inputs": RelativeInputs(trailing_eps=9000.0, earnings_growth=1.0)}
    )
    rv = _build(vi)
    peg = _ratio(rv, "PEG")
    assert peg is not None and peg.status == "na" and peg.value is None


def test_no_market_price_skips_layer():
    vi = load_profile(_FIXTURE)
    vi = vi.model_copy(update={"market_price": None})
    assert _build(vi) is None


def test_justified_verdicts_present():
    vi = load_profile(_FIXTURE)
    rv = _build(vi)
    # payout absent -> only P/B verdict (ROE-driven); ensure verdict list is well-formed
    for v in rv.verdicts:
        assert v.verdict in ("저평가", "적정", "고평가", "판단불가")
