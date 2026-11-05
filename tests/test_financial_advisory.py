"""Financial routing advisories report signals without changing valuation policy."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from engine.financial_advisory import build_financial_routing_advisories
from engine.method_selector import _FINANCIAL_KEYWORDS
from valuation_runner import load_profile, run_valuation


def _financial_input():
    vi = load_profile(str(Path(__file__).parent / "fixtures" / "msft_frozen.yaml"))
    names = ["Consumer Banking", "Investment Banking", "Financial Services"]
    segments = {
        code: {**info, "name": name, "method": "ev_ebitda"}
        for (code, info), name in zip(vi.segments.items(), names, strict=True)
    }
    return vi.model_copy(
        update={
            "valuation_method": "auto",
            "segments": segments,
            "news_drivers": [],
            "mc_enabled": False,
            "industry": "",
            "net_debt": 0,
        }
    )


def test_financial_sotp_requires_advisory_review():
    result = run_valuation(_financial_input())
    warnings = [
        w for w in result.engine_warnings if w.code == "FINANCIAL_ROUTING_ADVISORY"
    ]
    assert any(w.severity == "review" for w in warnings)
    assert result.review_required is True


def _build(vi, method="sotp"):
    return build_financial_routing_advisories(
        vi, SimpleNamespace(primary_method=method)
    )


def test_a1_order_fields_and_default_method():
    vi = _financial_input()
    warnings = _build(vi)
    a1 = [w for w in warnings if w.scope.startswith("segment:")]
    assert [w.scope for w in a1] == [f"segment:{c}" for c in sorted(vi.segments)]
    for warning in a1:
        segment = vi.segments[warning.scope.removeprefix("segment:")]
        assert warning.severity == "review"
        assert warning.fields["segment_name"] == segment["name"]
        assert warning.fields["segment_method"] == "ev_ebitda"
        assert warning.fields["keyword_hit"] in _FINANCIAL_KEYWORDS
        assert warning.fields["keyword_hit"] in segment["name"].lower()
        assert warning.fields["manual_override"] is False
    implicit = {
        c: {k: v for k, v in info.items() if k != "method"}
        for c, info in vi.segments.items()
    }
    assert [
        w.model_dump() for w in _build(vi.model_copy(update={"segments": implicit}))
    ] == [w.model_dump() for w in warnings]


@pytest.mark.parametrize("method", ["pbv", "pe"])
def test_equity_based_financial_segments_have_no_a1(method):
    vi = _financial_input()
    segments = {c: {**info, "method": method} for c, info in vi.segments.items()}
    warnings = _build(vi.model_copy(update={"segments": segments}))
    assert not any(w.scope.startswith("segment:") for w in warnings)
    assert [w.scope for w in warnings] == [
        "input"
    ]  # Signal disagreement remains visible.


def test_manual_override_downgrades_review_without_changing_route():
    vi = _financial_input().model_copy(update={"valuation_method": "sotp"})
    result = run_valuation(vi)
    assert result.primary_method == "sotp"
    warnings = [
        w for w in result.engine_warnings if w.code == "FINANCIAL_ROUTING_ADVISORY"
    ]
    assert warnings and all(w.severity == "warning" for w in warnings)
    assert result.review_required is False
    assert all(
        w.fields["manual_override"] is True
        for w in warnings
        if w.scope.startswith("segment:")
    )


@pytest.mark.parametrize("signal", ["code", "keyword", "wacc"])
@pytest.mark.parametrize("method", ["sotp", "dcf_primary", "ddm", "rim"])
def test_a2_company_signals_and_financial_methods(signal, method):
    vi = _financial_input()
    if signal == "code":
        vi = vi.model_copy(update={"industry_code": "SIC:6021"})
    elif signal == "keyword":
        vi = vi.model_copy(update={"industry": "Bank"})
    else:
        vi = vi.model_copy(
            update={
                "wacc_params": vi.wacc_params.model_copy(update={"is_financial": True})
            }
        )
    warnings = _build(vi, method)
    a2 = [w for w in warnings if w.scope == "result"]
    assert bool(a2) is (method not in {"ddm", "rim"})
    if a2:
        assert a2[0].severity == "review"
        assert a2[0].fields["primary_method"] == method
        assert a2[0].fields["manual_override"] is False
        assert all(not isinstance(value, dict) for value in a2[0].fields.values())


def test_a2_manual_override_and_order():
    vi = _financial_input().model_copy(
        update={"industry_code": "SIC:6021", "valuation_method": "sotp"}
    )
    warnings = _build(vi)
    assert [w.scope for w in warnings] == [
        "segment:IC",
        "segment:MPC",
        "segment:PBP",
        "result",
        "input",
    ]
    assert all(w.severity == "warning" for w in warnings)


def test_a3_excludes_unknown_code_and_keeps_ratio_and_de():
    vi = _financial_input()
    warning = next(w for w in _build(vi) if w.scope == "input")
    assert warning.severity == "warning"
    assert "industry_code_financial" not in warning.fields
    assert None not in warning.fields.values()
    assert warning.fields == {
        "industry_keyword": False,
        "wacc_is_financial": False,
        "financial_segments": "3/3",
        "de_ratio": vi.consolidated[vi.base_year]["de_ratio"],
    }


def test_a3_all_signals_agree_and_unknown_is_not_false():
    vi = _financial_input().model_copy(update={"industry": "Bank"})
    vi = vi.model_copy(
        update={"wacc_params": vi.wacc_params.model_copy(update={"is_financial": True})}
    )
    assert not any(w.scope == "input" for w in _build(vi))
    vi = vi.model_copy(update={"industry_code": "SIC:6021"})
    assert not any(w.scope == "input" for w in _build(vi))
    ordinary = load_profile(
        str(Path(__file__).parent / "fixtures" / "msft_frozen.yaml")
    )
    assert _build(ordinary) == []


def test_advisory_does_not_require_majority_financial_revenue():
    vi = _financial_input()
    segments = {c: {**info, "name": "Manufacturing"} for c, info in vi.segments.items()}
    segments["MPC"]["name"] = "Insurance"
    warnings = _build(vi.model_copy(update={"segments": segments}))
    assert [w.scope for w in warnings] == ["segment:MPC", "input"]
    assert warnings[-1].fields["financial_segments"] == "1/3"


def test_advisory_is_pure_and_gate_quality_remain_identical():
    vi = _financial_input()
    result = run_valuation(vi)
    input_before = vi.model_dump(mode="json")
    result_before = result.model_dump(mode="json")
    assert _build(vi)
    build_financial_routing_advisories(vi, result)
    assert vi.model_dump(mode="json") == input_before
    assert result.model_dump(mode="json") == result_before
