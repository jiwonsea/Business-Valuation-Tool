"""Native per-share precision and probability-contract regressions."""

import itertools
import json
import math
from pathlib import Path

import pytest

from engine.monte_carlo import MCInput, run_monte_carlo
from engine.scenario import calc_scenario
from schemas.models import ScenarioParams

FIXTURES = Path(__file__).parent / "fixtures"


def scenario(prob=50, shares=2_897_483_196, dlom=0, code="Base"):
    return ScenarioParams(
        code=code, name=code, prob=prob, ipo="N", shares=shares, dlom=dlom
    )


@pytest.mark.parametrize("equity,shares", [(30251, 2_897_483_196), (1290, 396_786_259)])
def test_identical_scenarios_preserve_fractional_value(equity, shares):
    results = [
        calc_scenario(scenario(p, shares), equity, 0, 0, 0, 0) for p in (50, 25, 25)
    ]
    exact = equity * 1_000_000 / shares
    assert math.fsum(r.weighted for r in results) == pytest.approx(exact, rel=1e-12)
    assert all(r.post_dlom == pytest.approx(exact, rel=1e-12) for r in results)


def test_small_mc_distribution_retains_fractional_percentiles():
    params = MCInput(
        multiple_params={"S": (1, 0.01)},
        wacc_mean=10,
        wacc_std=0,
        dlom_mean=0,
        dlom_std=0,
        tg_mean=2,
        tg_std=0,
        n_sims=2000,
        seed=42,
    )
    result = run_monte_carlo(params, {"S": 3}, 0, 0, 0, 0, 0, 0, 1, unit_multiplier=1)
    assert result.p5 < result.median < result.p95
    assert any(x != round(x) for x in result.distribution)


@pytest.mark.parametrize(
    "probs", [(50, 25, 24.95), (50, 25, 25), (50, 25, 25.05), (100,), (60, 40.05)]
)
def test_runner_normalizes_probabilities(probs):
    from valuation_runner import load_profile, run_valuation

    vi = load_profile(str(FIXTURES / "nexus_frozen.yaml"))
    base = next(iter(vi.scenarios.values()))
    scenarios = {
        str(i): base.model_copy(update={"code": str(i), "prob": prob})
        for i, prob in enumerate(probs)
    }
    result = run_valuation(vi.model_copy(update={"scenarios": scenarios}))
    assert math.fsum(
        sc.prob_effective_pct for sc in result.scenarios.values()
    ) == pytest.approx(100)
    assert result.prob_normalization_factor == pytest.approx(100 / math.fsum(probs))
    assert result.weighted_value == pytest.approx(
        math.fsum(sc.weighted for sc in result.scenarios.values())
    )
    posts = [sc.post_dlom for sc in result.scenarios.values()]
    assert min(posts) <= result.weighted_value + 1e-9 <= max(posts) + 1e-8


@pytest.mark.parametrize("value", [0, float("nan"), float("inf")])
def test_invalid_probability_total_is_rejected(value):
    from valuation_runner import _probability_factor

    with pytest.raises(ValueError):
        _probability_factor({"Base": scenario().model_copy(update={"prob": value})})


@pytest.mark.parametrize(
    "currency,eqs,dlom,probs",
    list(
        itertools.product(
            ("KRW", "USD", "JPY"),
            ((3, 7, 11), (-11, -7, -3), (-3, 0, 11)),
            (0, 15, 100),
            ((50, 25, 24.95), (50, 25, 25), (50, 25, 25.05)),
        )
    ),
)
def test_normalized_weight_invariants(currency, eqs, dlom, probs):
    factor = 100 / math.fsum(probs)
    results = [
        calc_scenario(
            scenario(p, 7, dlom, str(i)),
            eq,
            0,
            0,
            0,
            0,
            unit_multiplier=1,
            prob_weight=p * factor,
        )
        for i, (p, eq) in enumerate(zip(probs, eqs))
    ]
    weighted = math.fsum(r.weighted for r in results)
    epsilon = 1e-9 * max(1, abs(weighted))
    assert (
        min(r.post_dlom for r in results) - epsilon
        <= weighted
        <= max(r.post_dlom for r in results) + epsilon
    )
    assert math.fsum(r.weighted for r in reversed(results)) == weighted
    for r, p, eq in zip(results, probs, eqs):
        exact = eq / 7 * (1 - dlom / 100) if eq > 0 else eq / 7
        assert r.post_dlom == pytest.approx(exact)
        assert r.prob_input_pct == p
        assert r.prob_effective_pct == pytest.approx(p * factor)


@pytest.mark.parametrize(
    "value,currency,expected",
    [
        (2.5, "JPY", "3"),
        (-2.5, "KRW", "-3"),
        (2.675, "USD", "2.68"),
        (0.005, "USD", "0.01"),
        (314499.5, "KRW", "314,500"),
        (1e12, "USD", "1,000,000,000,000.00"),
        (3.2511, "HKD", "3.25"),
    ],
)
def test_display_rounding(value, currency, expected):
    from engine.units import format_per_share

    assert format_per_share(value, currency) == expected


def test_fixed_integer_inputs_match_full_precision_oracles():
    fixture = json.loads(
        (FIXTURES / "j1_per_share_expected.json").read_text(encoding="utf-8")
    )
    for case in fixture["cases"]:
        results = [
            calc_scenario(
                scenario(sc["prob"], sc["shares"], sc["dlom"], code),
                sc["equity"],
                0,
                0,
                0,
                0,
                unit_multiplier=case["unit_multiplier"],
            )
            for code, sc in case["scenarios"].items()
        ]
        assert math.fsum(r.weighted for r in results) == pytest.approx(
            case["expected_exact"], rel=1e-12
        )


def test_explicit_zero_probability_weight_stays_zero():
    result = calc_scenario(scenario(), 10, 0, 0, 0, 0, prob_weight=0)
    assert result.prob_effective_pct == 0
    assert result.weighted == 0


@pytest.mark.parametrize("value", [3, 3.2511, "3.2511"])
def test_history_and_backtest_accept_native_numeric_json(value):
    from schemas.history import ValuationHistoryRecord
    from backtest.models import ScenarioSnapshot

    assert ValuationHistoryRecord(weighted_value=value).weighted_value == float(value)
    sc = ScenarioSnapshot(
        code="Base", name="Base", prob=100, pre_dlom=value, post_dlom=value
    )
    assert sc.post_dlom == float(value)
    assert sc.prob_input is None


def test_result_json_preserves_fractional_values():
    from schemas.models import ValuationResult
    from valuation_runner import load_profile, run_valuation

    result = run_valuation(load_profile(str(FIXTURES / "nexus_frozen.yaml")))
    copied = ValuationResult.model_validate(result.model_dump(mode="json"))
    assert copied == result
    assert copied.weighted_value != round(copied.weighted_value)


def test_holding_postprocessing_uses_effective_probability():
    from valuation_runner import _apply_holding_discount_to_scenario

    r = calc_scenario(
        scenario(50.05, 7, 15), 30, 0, 0, 0, 0, unit_multiplier=1, prob_weight=50
    )
    modified = _apply_holding_discount_to_scenario(r, 19, 15, r.prob_effective_pct, 1)
    assert modified.post_dlom == pytest.approx(19 / 7 * 0.85)
    assert modified.weighted == pytest.approx(modified.post_dlom * 0.5)
    assert modified.prob_input_pct == 50.05


@pytest.mark.parametrize(
    "method", ["sotp", "dcf_primary", "ddm", "rim", "nav", "multiples", "rnpv"]
)
@pytest.mark.parametrize("has_scenarios", [True, False])
def test_all_methods_and_empty_scenarios_keep_native_float_contract(
    method, has_scenarios
):
    from schemas.models import DDMParams, RIMParams, NAVParams, RNPVParams, PipelineDrug
    from valuation_runner import load_profile, run_valuation

    vi = load_profile(str(FIXTURES / "nexus_frozen.yaml"))
    vi = vi.model_copy(
        update={
            "valuation_method": method,
            "ddm_params": DDMParams(dps=1.2345, dividend_growth=2),
            "rim_params": RIMParams(roe_forecasts=[10, 11, 12], terminal_growth=1),
            "nav_params": NAVParams(),
            "rnpv_params": RNPVParams(
                pipeline=[
                    PipelineDrug(
                        name="Fixed",
                        phase="approved",
                        peak_sales=1000,
                        patent_expiry_years=10,
                    )
                ],
                discount_rate=10,
            ),
            "scenarios": vi.scenarios if has_scenarios else {},
        }
    )
    result = run_valuation(vi)
    assert result.primary_method == method
    assert isinstance(result.weighted_value, float)
    assert result.prob_normalization_factor == 1
    if has_scenarios:
        assert len(result.scenarios) == len(vi.scenarios)
        assert (
            math.fsum(r.weighted for r in result.scenarios.values())
            == result.weighted_value
        )
        for code, r in result.scenarios.items():
            assert isinstance(r.equity_value, int)
            expected = r.equity_value * vi.company.unit_multiplier / r.shares
            if r.equity_value > 0:
                expected *= 1 - vi.scenarios[code].dlom / 100
            assert r.post_dlom == pytest.approx(expected)
    else:
        assert result.scenarios == {}


@pytest.mark.parametrize("valuation_id", [None, "v-1"])
def test_shared_saver_emits_one_failure_line_for_cli_and_auto_paths(
    valuation_id, capsys
):
    from types import SimpleNamespace
    from unittest.mock import patch
    from orchestrator import _save_to_db

    vi = SimpleNamespace(draft=False, company=SimpleNamespace(name="Synthetic"))
    result = SimpleNamespace(draft=False)
    with (
        patch("db.repository.save_valuation", return_value=valuation_id),
        patch("db.backtest_repository.save_prediction_snapshot", return_value=None),
        patch("db.client.get_client", return_value=object()),
    ):
        assert _save_to_db(vi, result) is None
    assert capsys.readouterr().out.count("[DB] 저장 실패:") == 1
