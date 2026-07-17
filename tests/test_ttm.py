from pathlib import Path

import pytest
import yaml

from engine.ttm import AnnualFacts, FactValue, InterimYtdFacts, roll_ttm
from pipeline.edgar_parser import extract_quarterly_facts
from valuation_runner import load_profile


def _fact(value, start, end):
    return FactValue(value=value, period_start=start, period_end=end, source={})


def test_nvda_frozen_ttm_rollup():
    raw = yaml.safe_load(
        Path("tests/fixtures/nvda_ttm_inputs.yaml").read_text(encoding="utf-8")
    )
    annual_raw = raw["annual"]
    prior_raw = raw["prior_ytd"]
    current_raw = raw["current_ytd"]
    fields = tuple(raw["expected"])

    annual = AnnualFacts(
        fiscal_year=annual_raw["fiscal_year"],
        fields={
            key: _fact(value, annual_raw["period_start"], annual_raw["period_end"])
            for key, value in annual_raw["values"].items()
        },
    )
    prior = InterimYtdFacts(
        fiscal_year=prior_raw["fiscal_year"],
        fiscal_period=prior_raw["fiscal_period"],
        fields={
            key: _fact(value, prior_raw["period_start"], prior_raw["period_end"])
            for key, value in prior_raw["values"].items()
        },
    )
    current = InterimYtdFacts(
        fiscal_year=current_raw["fiscal_year"],
        fiscal_period=current_raw["fiscal_period"],
        fields={
            key: _fact(value, current_raw["period_start"], current_raw["period_end"])
            for key, value in current_raw["values"].items()
        },
    )

    assert roll_ttm(annual, prior, current, fields).fields == raw["expected"]


def test_ttm_rejects_missing_instead_of_treating_it_as_zero():
    annual = AnnualFacts(2025, {"revenue": _fact(100, "2024-01-01", "2024-12-31")})
    prior = InterimYtdFacts(2025, "Q1", {})
    current = InterimYtdFacts(2026, "Q1", {})
    with pytest.raises(ValueError, match="missing"):
        roll_ttm(annual, prior, current, ("revenue",))


def test_quarter_parser_prefers_reported_discrete_over_ytd():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "fy": 2026, "fp": "Q2", "form": "10-Q",
                                "start": "2025-01-27", "end": "2025-07-27",
                                "filed": "2025-08-27", "accn": "a", "val": 90_805_000_000,
                            },
                            {
                                "fy": 2026, "fp": "Q2", "form": "10-Q",
                                "start": "2025-04-28", "end": "2025-07-27",
                                "filed": "2025-08-27", "accn": "a", "val": 46_743_000_000,
                            },
                        ]
                    }
                }
            }
        }
    }
    result = extract_quarterly_facts(facts, ["Revenues"], 2026, "Q2")
    assert result["value"] == 46_743
    assert result["kind"] == "reported_discrete"


def test_financial_anchor_defaults_to_fy_for_legacy_fixture():
    vi = load_profile("tests/fixtures/msft_frozen.yaml")
    assert vi.financial_anchor == "fy"
    assert vi.consolidated[vi.base_year]["revenue"] == 281_724


def test_nvda_ttm_anchor_is_consumed_without_overwriting_fy_audit_copy():
    vi = load_profile("profiles/nvda.yaml")
    assert vi.financial_anchor == "ttm"
    assert vi.consolidated[vi.base_year]["revenue"] == 253_491
    assert vi.consolidated[vi.base_year]["net_income"] == 159_613
    assert vi.fy_base_financials["revenue"] == 215_938
