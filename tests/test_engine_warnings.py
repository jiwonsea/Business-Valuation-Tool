"""Structured engine warning contract; fixed inputs live in tests/fixtures."""

from pathlib import Path

import pytest

from engine.warnings import WARNING_CODES, WARNING_ORDER, make_warning
from output.console_report import print_report
from schemas.models import EngineWarning, HoldingStructure
from valuation_runner import load_profile, run_valuation


FIXTURES = Path(__file__).parent / "fixtures"


def _input(**updates):
    vi = load_profile(str(FIXTURES / "msft_frozen.yaml"))
    return vi.model_copy(update={"mc_enabled": False, "news_drivers": [], **updates})


def test_negative_equity_requires_review():
    result = run_valuation(_input(net_debt=1_000_000_000))
    warnings = [
        w for w in result.engine_warnings if w.code == "NEGATIVE_SCENARIO_EQUITY"
    ]
    assert len(warnings) == len(result.scenarios)
    assert result.review_required is True
    for warning in warnings:
        scenario = result.scenarios[warning.scope.removeprefix("scenario:")]
        assert warning.fields == {
            "equity_value": scenario.equity_value,
            "post_dlom": scenario.post_dlom,
            "prob_effective_pct": scenario.prob_effective_pct,
        }


def test_dcf_growth_fallback_records_base_ev():
    vi = _input(valuation_method="dcf_primary")
    scenario = vi.scenarios["Base"].model_copy(
        update={"terminal_growth_adj": 100, "wacc_adj": -20, "market_sentiment_pct": 0}
    )
    vi = vi.model_copy(update={"scenarios": {"Base": scenario}})
    result = run_valuation(vi)
    warning = next(
        w for w in result.engine_warnings if w.code == "DCF_SCENARIO_FALLBACK"
    )
    assert warning.fields["used_base_ev"] is True
    assert warning.fields["reason"] == "wacc<=tg"
    assert result.scenarios["Base"].total_ev == result.total_ev


def test_dcf_wacc_only_fallback_records_base_ev():
    vi = _input(valuation_method="dcf_primary")
    scenario = vi.scenarios["Base"].model_copy(update={"wacc_adj": -20})
    result = run_valuation(vi.model_copy(update={"scenarios": {"Base": scenario}}))
    warning = next(
        w for w in result.engine_warnings if w.code == "DCF_SCENARIO_FALLBACK"
    )
    assert warning.scope == "scenario:Base"
    assert warning.fields["used_base_ev"] is True
    assert warning.fields["terminal_growth"] == vi.dcf_params.terminal_growth
    assert warning.fields["applied_wacc"] <= warning.fields["terminal_growth"]
    assert warning.fields["applied_wacc"] == result.wacc.wacc - 20  # Base WACC + adj
    assert result.scenarios["Base"].total_ev == result.total_ev


@pytest.mark.parametrize("growth_adj", [0, 10])
def test_dcf_exception_reason_is_one_line(monkeypatch, growth_adj):
    import valuation_runner

    original = valuation_runner.calc_dcf
    calls = 0

    def fail_scenario(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("synthetic\nfailure")
        return original(*args, **kwargs)

    vi = _input(valuation_method="dcf_primary")
    scenario = vi.scenarios["Base"].model_copy(
        update={"wacc_adj": 0.1, "growth_adj_pct": growth_adj}
    )
    monkeypatch.setattr(valuation_runner, "calc_dcf", fail_scenario)
    result = run_valuation(vi.model_copy(update={"scenarios": {"Base": scenario}}))
    warning = next(
        w for w in result.engine_warnings if w.code == "DCF_SCENARIO_FALLBACK"
    )
    assert warning.fields["reason"] == "synthetic failure"
    assert result.scenarios["Base"].total_ev == result.total_ev


def test_clamp_and_wide_spread_fields_and_legacy_strings(tmp_path):
    import yaml

    raw = yaml.safe_load((FIXTURES / "msft_frozen.yaml").read_text(encoding="utf-8"))
    raw["scenarios"]["Bull"]["segment_multiples"]["PBP"] = 66.0
    path = tmp_path / "wide.yaml"
    for allow in [False, True]:
        raw.update(curated=True, allow_wide_scenario_spread=allow)
        path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
        vi = load_profile(str(path))
        warning = vi.engine_warnings[0]
        assert warning.scope == "scenario:Bull/segment:PBP"
        if allow:
            assert warning.code == "WIDE_SPREAD_ALLOWED"
            assert warning.fields == {
                "value": 66.0,
                "original_ratio": 3.0,
                "cap_ratio": 2.0,
            }
        else:
            assert warning.code == "SCENARIO_MULTIPLE_CLAMPED"
            assert warning.fields == {
                "original": 66.0,
                "applied": 44.0,
                "floor": 22.0,
                "original_ratio": 3.0,
                "cap_ratio": 2.0,
            }
        assert vi.scenario_spread_warnings == [warning.message]
        assert "engine_warnings" not in vi.model_dump()


def test_share_count_fields_and_legacy_message(tmp_path):
    import yaml

    raw = yaml.safe_load((FIXTURES / "msft_frozen.yaml").read_text(encoding="utf-8"))
    raw["company"]["treasury_shares"] = 100
    path = tmp_path / "shares.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    vi = load_profile(str(path))
    warning = next(w for w in vi.engine_warnings if w.code == "SHARE_COUNT_MISMATCH")
    assert warning.fields == {
        "applied_shares": 7425629076,
        "outstanding": 7425628976,
        "treasury_shares": 100,
        "difference": 100,
    }
    assert (
        vi.share_count_warnings
        == [
            "적용 주식수 7,425,629,076 ≠ 유통주식수 7,425,628,976"
            " (자기주식 100 포함) — 시나리오 shares가 의도적 설정인지 확인"
        ]
        == [warning.message]
    )
    result = run_valuation(vi)
    assert warning in result.engine_warnings


@pytest.mark.parametrize("probability, expected", [(100.05, True), (100, False)])
def test_probability_normalization(probability, expected):
    vi = _input()
    scenario = vi.scenarios["Base"].model_copy(update={"prob": probability})
    result = run_valuation(vi.model_copy(update={"scenarios": {"Base": scenario}}))
    warnings = [w for w in result.engine_warnings if w.code == "PROB_NORMALIZED"]
    assert bool(warnings) is expected
    if expected:
        assert warnings[0].fields == {
            "factor": result.prob_normalization_factor,
            "prob_sum": probability,
        }


def test_holding_warnings_match_bridge_and_negative_postprocessing():
    vi = _input(net_debt=1_000_000_000)
    vi = vi.model_copy(
        update={
            "company": vi.company.model_copy(
                update={"holding_structure": HoldingStructure(enabled=True)}
            ),
            "scenarios": {"Base": vi.scenarios["Base"]},
        }
    )
    result = run_valuation(vi)
    warnings = [w for w in result.engine_warnings if w.code == "HOLDING_BRIDGE"]
    assert len(warnings) == len(result.holding_discount.warnings) == 1
    assert [w.message for w in warnings] == result.holding_discount.warnings
    assert warnings[0].fields == {"message_index": 0}
    negative = next(
        w for w in result.engine_warnings if w.code == "NEGATIVE_SCENARIO_EQUITY"
    )
    assert negative.fields["equity_value"] == result.holding_discount.net_equity_value


def test_distress_multiple_fields_are_engine_values():
    vi = _input()
    cons = {year: dict(values) for year, values in vi.consolidated.items()}
    cons[vi.base_year]["de_ratio"] = 300
    result = run_valuation(vi.model_copy(update={"consolidated": cons}))
    warnings = [
        w for w in result.engine_warnings if w.code == "DISTRESS_MULTIPLE_APPLIED"
    ]
    assert warnings
    for warning in warnings:
        segment = warning.scope.removeprefix("segment:")
        assert warning.fields == {
            "original": vi.multiples[segment],
            "applied": result.sotp[segment].multiple,
        }


def test_console_groups_identical_holding_messages_without_losing_scopes(capsys):
    vi = _input(net_debt=1_000_000_000)
    vi = vi.model_copy(
        update={
            "company": vi.company.model_copy(
                update={"holding_structure": HoldingStructure(enabled=True)}
            ),
        }
    )
    result = run_valuation(vi)
    warnings = [w for w in result.engine_warnings if w.code == "HOLDING_BRIDGE"]
    assert len(warnings) == len(result.scenarios) == 3
    assert len({w.message for w in warnings}) == 1
    print_report(vi, result)
    text = capsys.readouterr().out
    assert text.count(warnings[0].message) == 1
    assert "[HOLDING_BRIDGE] scenario:Base, scenario:Bear, scenario:Bull — " in text
    assert f"[경고 {len(result.engine_warnings)}건]" in text


def test_registry_and_model_validation():
    reserved = {
        "FINANCIAL_ROUTING_ADVISORY",
        "UNSUPPORTED_DRIVER",
        "NEGATIVE_GROWTH_ADJ",
    }
    assert reserved <= WARNING_CODES
    assert isinstance(WARNING_CODES, frozenset)
    for build in [
        make_warning,
        lambda code, scope, message: EngineWarning(
            code=code, scope=scope, message=message, severity="warning"
        ),
    ]:
        with pytest.raises(ValueError, match="Unregistered"):
            build("UNKNOWN", "result", "unknown")
    assert (
        make_warning("FINANCIAL_ROUTING_ADVISORY", "result", "reserved").severity
        == "review"
    )
    warning = make_warning("PROB_NORMALIZED", "result", "override", severity="review")
    assert warning.severity == "review"


def test_console_once_sorted_and_zero(capsys):
    vi = _input(net_debt=1_000_000_000)
    result = run_valuation(vi)
    print_report(vi, result)
    text = capsys.readouterr().out
    assert text.count(f"[경고 {len(result.engine_warnings)}건]") == 1
    warnings = sorted(
        result.engine_warnings, key=lambda w: (WARNING_ORDER.index(w.code), w.scope)
    )
    positions = []
    for warning in warnings:
        assert text.count(warning.message) == 1
        symbol = "⛔" if warning.severity == "review" else "⚠"
        positions.append(
            text.index(f"{symbol} [{warning.code}] {warning.scope} — {warning.message}")
        )
    assert positions == sorted(positions)
    assert positions[-1] < text.index("[WACC (Base)]")
    vi = _input()
    result = run_valuation(vi)
    assert result.engine_warnings == []
    assert result.review_required is False
    print_report(vi, result)
    assert "[경고 " not in capsys.readouterr().out


def test_legacy_sotp_wacc_adj_is_reported_once_as_unsupported(capsys):
    """msft_frozen is valued by SOTP; its news drivers resolve to a wacc_adj."""
    vi = load_profile(str(FIXTURES / "msft_frozen.yaml"))
    vi = vi.model_copy(update={"mc_enabled": False})
    result = run_valuation(vi)

    assert result.primary_method == "sotp"
    warnings = [w for w in result.engine_warnings if w.code == "UNSUPPORTED_DRIVER"]
    assert len(warnings) == 1
    assert (warnings[0].severity, warnings[0].scope) == ("warning", "input")
    assert warnings[0].message == (
        "wacc_adj는 sotp에서 적용되지 않습니다(할인율 미변경) — "
        "Base +0.01%p, Bull -0.13%p, Bear +0.32%p"
    )
    assert warnings[0].fields == {
        "driver": "wacc_adj",
        "method": "sotp",
        "scenarios": "Base,Bull,Bear",
    }
    assert result.review_required is False
    assert [sc.discount_shift for sc in result.scenarios.values()] == [None] * 3
    print_report(vi, result)
    text = capsys.readouterr().out
    assert text.count("[UNSUPPORTED_DRIVER]") == 1
    assert text.count("[WACC (Base)]") == 1


@pytest.mark.parametrize(
    "name, weighted, posts, mc",
    [
        # Source: HEAD 1ad245f, pre-edit j2_baseline_before.json (2026-11-03).
        # MC expectations captured on Windows; rel=1e-12 allows platform ULP differences.
        (
            "nexus",
            362.4787576144978,
            [444.93432423610506, 891.1219499847914, 18.123722853504596],
            [
                437.76612093839685,
                429.4941769024705,
                121.85738207073165,
                253.53982488655174,
                651.3024811270269,
                0.0,
            ],
        ),
        (
            "msft",
            530.0961062978902,
            [507.35768800741533, 701.2227444580212, 367.84748767324504],
            [
                425.8682571918532,
                405.00085123107306,
                112.64948831968178,
                289.10026801750064,
                627.4475941589227,
                0.0,
            ],
        ),
    ],
)
def test_frozen_numerical_contract(name, weighted, posts, mc):
    result = run_valuation(load_profile(str(FIXTURES / f"{name}_frozen.yaml")))
    assert result.weighted_value == weighted
    assert [s.post_dlom for s in result.scenarios.values()] == posts
    mc_actual = [
        getattr(result.monte_carlo, field)
        for field in ["mean", "median", "std", "p5", "p95", "pct_negative"]
    ]
    assert mc_actual == pytest.approx(mc, rel=1e-12, abs=0.0)
