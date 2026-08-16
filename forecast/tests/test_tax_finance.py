"""Tax/finance below-the-line diagnosis + realized-anchored tax-rate guard.

PLAN_tax_finance.md acceptance: the base effective_tax_rate must reproduce the
realized effective rate (tax / pretax), not the legacy 0.20 that over-taxed every
backtest quarter and drove ~-3.9pp of the -10.55% EPS bias. These tests pin the
anchor to committed DART fixtures so a silent revert to 0.20 fails CI.

Deterministic: uses tests/fixtures/ (committed), NOT reports/.cache/ (gitignored).
"""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.ir_loader import load_profile
from scripts.diagnose_tax_finance import (
    ID_NI,
    ID_OP,
    ID_PRETAX,
    ID_TAX,
    _line,
    _rows,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _2024q4_below_the_line() -> dict[str, float]:
    """Extract 2024Q4 standalone below-the-line via annual - 9M, from fixtures."""
    annual = json.load(open(FIXTURES / "sk_hynix_2024q4_dart.json", encoding="utf-8"))
    q3 = json.load(open(FIXTURES / "sk_hynix_2024q3_dart.json", encoding="utf-8"))
    annual_rows, q3_rows = _rows(annual), _rows(q3)
    op = _line(annual_rows, q3_rows, True, ID_OP)
    pretax = _line(annual_rows, q3_rows, True, ID_PRETAX)
    tax = _line(annual_rows, q3_rows, True, ID_TAX)
    ni = _line(annual_rows, q3_rows, True, ID_NI)
    return {"op": op, "pretax": pretax, "tax": tax, "ni": ni}


def test_2024q4_realized_effective_tax_from_fixtures() -> None:
    """Realized effective tax (tax/pretax) for 2024Q4 is ~16.4%, well below 0.20."""
    v = _2024q4_below_the_line()
    effective_tax = v["tax"] / v["pretax"]
    assert abs(effective_tax - 0.1644) < 0.001
    # The below-OP block (pretax - OP) is materially positive this quarter — the
    # net financial / one-off swing the flat net_interest proxy cannot capture.
    block = v["pretax"] - v["op"]
    assert abs(block - 1498.6) < 1.0
    # Pretax - tax must reconcile to reported net profit (extraction sanity).
    assert abs((v["pretax"] - v["tax"]) - v["ni"]) < 0.5


def test_base_tax_rate_is_realized_anchored() -> None:
    """Base effective_tax_rate sits in the realized band, not the legacy 0.20.

    Fails if the anchor is reverted to 0.20 (the over-tax that biased EPS down).
    """
    profile = load_profile(Path(__file__).resolve().parents[1] / "profiles" / "sk_hynix.yaml")
    _assumptions, _margin, finance = profile["scenarios"]["base"]
    # Realized 8Q effective tax averaged ~16.4% (range 12.8-19.8%).
    assert 0.15 <= finance.effective_tax_rate <= 0.18


def test_scenario_tax_ordering_is_coherent() -> None:
    """Bull <= base <= bear effective tax (lower tax = more bullish EPS)."""
    profile = load_profile(Path(__file__).resolve().parents[1] / "profiles" / "sk_hynix.yaml")
    bull = profile["scenarios"]["bull"][2].effective_tax_rate
    base = profile["scenarios"]["base"][2].effective_tax_rate
    bear = profile["scenarios"]["bear"][2].effective_tax_rate
    assert bull <= base <= bear
