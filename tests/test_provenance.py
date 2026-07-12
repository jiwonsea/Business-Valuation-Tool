"""P0-0 — provenance contract tests (PLAN_deep_research.md §1, §2.1, §2.4, §3).

Scope: types + backward compatibility only. P0-0 changes no behaviour; if a valuation
number moves because of this commit, the change went out of scope.

Contract revisions after CODEX review:
  1. NetDebtComponents.reconciled is 3-state and computed, never auto-derived.
  2. Source enforces minimum provenance in the type (P5), not by convention.
  3. DeclaredAssumption requires an *identified* human approver, a date, and sensitivity.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from schemas.models import ValuationInput
from schemas.provenance import (
    LEGACY_VERSION,
    NORMALIZATION_VERSION,
    DeclaredAssumption,
    FallbackConstant,
    NetDebtComponents,
    Source,
    assert_observed_only,
)
from valuation_runner import load_profile

FIXTURE = Path(__file__).parent / "fixtures" / "msft_frozen.yaml"

DGS10 = "https://fred.stlouisfed.org/series/DGS10"

# A fully-provenanced observation — the minimum the type accepts.
OBSERVED = dict(source="FRED", as_of=date(2026, 7, 10), url=DGS10)


def _rebuild(**overrides) -> ValuationInput:
    """Re-validate a frozen profile with extra fields (model_copy skips validators)."""
    base = load_profile(str(FIXTURE)).model_dump()
    base.update(overrides)
    return ValuationInput.model_validate(base)


# ── Source: minimum provenance enforced by the type (P5) ──


def test_observed_source_requires_as_of():
    with pytest.raises(ValidationError, match="as_of"):
        Source(value=4.56, source="FRED", url=DGS10)


def test_observed_source_requires_document_reference():
    with pytest.raises(ValidationError, match="accession"):
        Source(value=4.56, source="FRED", as_of=date(2026, 7, 10))


def test_derived_source_requires_an_upstream_reference():
    with pytest.raises(ValidationError, match="derived_from"):
        Source(
            value=253_491, source="SEC EDGAR", as_of=date(2026, 5, 28), method="derived"
        )

    ok = Source(
        value=253_491,
        source="SEC EDGAR",
        as_of=date(2026, 5, 28),
        method="derived",
        derived_from=["0001045810-26-000052", "0001045810-26-000021"],
    )
    assert ok.method == "derived"


@pytest.mark.parametrize("kind", ["manual", "fallback constant"])
def test_manual_and_fallback_are_not_observation_channels(kind):
    """A human-entered number is a DeclaredAssumption; a failed fetch is a FallbackConstant."""
    with pytest.raises(ValidationError):
        Source(value=4.56, source=kind, as_of=date(2026, 7, 10), url="x")


def test_fully_provenanced_observation_is_accepted():
    src = Source(value=4.56, **OBSERVED)
    assert src.method == "observed"
    assert src.stale is False


# ── P1: an assumption may not masquerade as an observation ──


def test_assumption_sources_rejects_declared_assumption_method():
    smuggled = {
        "terminal_growth": Source(value=2.9, method="declared_assumption", source="FRED")
    }

    with pytest.raises(ValueError, match="관측치가 아닙니다"):
        assert_observed_only(smuggled)

    with pytest.raises(ValidationError):
        _rebuild(assumption_sources=smuggled)


def test_assumption_sources_accepts_observed_and_derived():
    vi = _rebuild(
        assumption_sources={
            "rf": Source(value=4.56, **OBSERVED),
            "ttm_revenue": Source(
                value=253_491,
                source="SEC EDGAR",
                as_of=date(2026, 5, 28),
                method="derived",
                derived_from=["0001045810-26-000052"],
            ),
        }
    )
    assert set(vi.assumption_sources) == {"rf", "ttm_revenue"}


# ── DeclaredAssumption: LLM proposes, an identified human approves ──


def _assumption(**over):
    kw = dict(
        value=2.5,
        rationale="장기 명목성장률 = 실질 1.8% + 인플레 목표 2.0% 하한",
        proposed_by="llm:claude-sonnet-4",
        approved_by="human:jiwon",
        at=date(2026, 7, 12),
    )
    kw.update(over)
    return DeclaredAssumption(**kw)


def test_declared_assumption_happy_path():
    a = _assumption()
    assert a.sensitivity_required is True
    assert a.proposed_by.startswith("llm:")
    assert a.approved_by == "human:jiwon"


@pytest.mark.parametrize("bad", ["", "   "])
def test_declared_assumption_requires_rationale(bad):
    with pytest.raises(ValidationError):
        _assumption(rationale=bad)


@pytest.mark.parametrize("bad", ["", "   ", "llm:claude-sonnet-4", "claude", "jiwon"])
def test_declared_assumption_requires_human_approval(bad):
    """An LLM cannot approve its own assumption (PLAN §1)."""
    with pytest.raises(ValidationError):
        _assumption(approved_by=bad)


@pytest.mark.parametrize("bad", ["human:", "human:   ", "human:\t", "human:\n"])
def test_declared_assumption_rejects_anonymous_human_approval(bad):
    """'human:' 접두사만으로는 누가 승인했는지 감사할 수 없다."""
    with pytest.raises(ValidationError, match="승인자 식별자"):
        _assumption(approved_by=bad)


def test_declared_assumption_requires_a_date():
    with pytest.raises(ValidationError):
        DeclaredAssumption(value=2.5, rationale="x", approved_by="human:jiwon")


def test_sensitivity_cannot_be_waived():
    """§2.6: 민감도는 옵션이 아니다."""
    with pytest.raises(ValidationError):
        _assumption(sensitivity_required=False)


# ── §2.4: a fallback constant is neither an observation nor an assumption ──


def test_fallback_constant_records_why_and_when():
    fb = FallbackConstant(
        value=4.20, reason="FRED DGS10 timeout x3", as_of=date(2026, 7, 5), ttl_days=7
    )
    assert fb.stale is True  # stale until proven otherwise


@pytest.mark.parametrize("over", [{"reason": ""}, {"reason": "  "}, {"ttl_days": 0}, {"ttl_days": -1}])
def test_fallback_constant_rejects_undocumented_fallback(over):
    kw = dict(value=4.20, reason="timeout", as_of=date(2026, 7, 5), ttl_days=7)
    kw.update(over)
    with pytest.raises(ValidationError):
        FallbackConstant(**kw)


# ── NetDebtComponents: 3-state reconciliation ──


def test_empty_components_are_not_reconciled_they_are_unknowable():
    """Regression: the empty object used to report reconciled=True (vacuous truth)."""
    nd = NetDebtComponents()
    assert nd.reconciled is None
    assert nd.expected_net_debt() is None
    assert nd.has_components is False


def test_components_without_independent_total_cannot_be_reconciled():
    nd = NetDebtComponents(
        cash=13_237, marketable_debt_securities=37_098, gross_borrowings=8_470
    )
    assert nd.expected_net_debt() == -41_865
    assert nd.net_debt is None
    assert nd.reconciled is None  # nothing to check the components against


def test_one_sided_components_cannot_be_reconciled():
    """Imputing the missing side (borrowings=0) would be fabrication, not normalization."""
    nd = NetDebtComponents(cash=13_237, net_debt=-13_237)
    assert nd.has_components is False
    assert nd.expected_net_debt() is None
    assert nd.reconciled is None


def test_mismatch_flags_unreconciled_without_raising():
    nd = NetDebtComponents(
        cash=13_237,
        marketable_debt_securities=37_098,
        gross_borrowings=8_470,
        net_debt=-40_000,  # wrong on purpose
    )
    assert nd.reconciled is False
    assert nd.expected_net_debt() == -41_865


def test_nvda_net_debt_reconciles():
    """PLAN §2.1 / §0 — NVDA is net *cash* $41.9B."""
    nd = NetDebtComponents(
        cash=13_237,
        marketable_debt_securities=37_098,
        gross_borrowings=8_470,
        net_debt=-41_865,
    )
    assert nd.deductible_cash == 50_335
    assert nd.expected_net_debt() == -41_865
    assert nd.reconciled is True


def test_excluded_buckets_do_not_enter_the_sum():
    """Restricted cash and marketable *equity* securities are recorded, not deducted."""
    nd = NetDebtComponents(
        cash=13_237,
        marketable_debt_securities=37_098,
        gross_borrowings=8_470,
        net_debt=-41_865,
        restricted_cash_excluded=500,
        equity_securities_excluded=21_100,  # -> upside bridge, not net debt
    )
    assert nd.reconciled is True
    assert nd.deductible_cash == 50_335


def test_reconciled_survives_a_serialization_round_trip():
    """computed_field: reconciled cannot be forged by writing it into the payload."""
    nd = NetDebtComponents(
        cash=13_237,
        marketable_debt_securities=37_098,
        gross_borrowings=8_470,
        net_debt=-40_000,
    )
    dumped = nd.model_dump()
    assert dumped["reconciled"] is False

    forged = {**dumped, "reconciled": True}
    assert NetDebtComponents.model_validate(forged).reconciled is False


# ── Backward compatibility: pre-P0 profiles load unchanged ──


def test_legacy_profile_loads_with_legacy_defaults():
    vi = load_profile(str(FIXTURE))

    assert vi.normalization_version == LEGACY_VERSION
    assert vi.normalization_version != NORMALIZATION_VERSION
    assert vi.net_debt_components is None
    assert vi.assumption_sources == {}
    assert vi.declared_assumptions == {}
    assert vi.segment_disclosure_level == "none"

    # legacy scalar untouched — P0-0 adds a slot, it does not normalize anything
    assert vi.net_debt == 30_346


def test_segment_disclosure_level_rejects_unknown_value():
    with pytest.raises(ValidationError):
        _rebuild(segment_disclosure_level="L4")
