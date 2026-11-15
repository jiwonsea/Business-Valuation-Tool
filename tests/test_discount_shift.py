"""J-4 discount-rate scalar contract (D5) and premium preservation (J-14).

`wacc_adj` shifts the one discount rate a method actually consumes: DCF the
WACC (distress premium included), DDM/RIM the cost of equity, rNPV its
discount rate. The shift is recorded on `ScenarioResult.discount_shift`.
SOTP/NAV/Multiples consume no discount rate: they record nothing and emit
`UNSUPPORTED_DRIVER` instead.

Runner inputs are tests/fixtures/nexus_frozen.yaml with `wacc_adj` set on its
scenarios (the fixture sets no other scalar driver). Expected EVs come from
calling the engine function with `base rate + adj`, so a runner that applies
any other rate fails on the number itself.
"""

import math
from pathlib import Path

import pytest

import valuation_runner
from engine.dcf import calc_dcf
from engine.ddm import calc_ddm
from engine.rim import calc_rim
from engine.rnpv import calc_rnpv
from engine.wacc import calc_wacc
from schemas.models import (
    DDMParams,
    NAVParams,
    PipelineDrug,
    RIMParams,
    RNPVParams,
    WACCParams,
)
from valuation_runner import load_profile, run_valuation

FIXTURES = Path(__file__).parent / "fixtures"
ADJS = {"Bull": -0.5, "Base": 0.0, "Bear": 0.5}
RNPV_RATE = 10.0


def _wacc_params(de: float, eq_w: float) -> WACCParams:
    """The stress case of the J-4 handoff table: rf4 / erp5 / bu1 / tax25 / kd6."""
    return WACCParams(rf=4, erp=5, bu=1, de=de, tax=25, kd_pre=6, eq_w=eq_w)


def _input(method: str, adjs: dict[str, float] = ADJS, **updates):
    """nexus_frozen valued by `method`, with `wacc_adj` set per scenario."""
    vi = load_profile(str(FIXTURES / "nexus_frozen.yaml"))
    scenarios = {
        code: vi.scenarios[code].model_copy(update={"wacc_adj": adj})
        for code, adj in adjs.items()
    }
    return vi.model_copy(
        update={
            "valuation_method": method,
            "scenarios": scenarios,
            "mc_enabled": False,
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
                discount_rate=RNPV_RATE,
            ),
            **updates,
        }
    )


def _engine_ev(method: str, vi, rate: float) -> int:
    """Scenario EV the engine yields at `rate`, every other input from `vi`."""
    cons = vi.consolidated[vi.base_year]
    um = vi.company.unit_multiplier
    if method == "dcf_primary":
        da = cons["dep"] + cons["amort"]
        return calc_dcf(
            cons["op"] + da, da, cons["revenue"], rate, vi.dcf_params, vi.base_year
        ).ev_dcf
    if method == "ddm":
        per_share = calc_ddm(
            vi.ddm_params.dps, vi.ddm_params.dividend_growth, rate
        ).equity_per_share
        return round(per_share * vi.valuation_shares / um) + vi.net_debt
    if method == "rim":
        rim = calc_rim(
            book_value=cons["equity"],
            roe_forecasts=vi.rim_params.roe_forecasts,
            ke=rate,
            terminal_growth=vi.rim_params.terminal_growth,
            shares=vi.valuation_shares,
            unit_multiplier=um,
            payout_ratio=vi.rim_params.payout_ratio,
        )
        return rim.equity_value + vi.net_debt
    params = vi.rnpv_params
    return calc_rnpv(
        pipeline=[drug.model_dump() for drug in params.pipeline],
        discount_rate=rate,
        r_and_d_cost=params.r_and_d_cost,
        decline_rate=params.decline_rate,
        default_margin=params.default_margin,
        tax_rate=params.tax_rate,
    ).enterprise_value


# ── pure function ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("rate_kind", ["wacc", "ke", "discount_rate"])
@pytest.mark.parametrize("adj", [-0.5, 0.0, 0.5])
def test_effective_discount_rate_adds_the_adjustment(rate_kind, adj):
    from engine.discount import effective_discount_rate
    from schemas.models import DiscountShift

    base = 14.7
    applied, shift = effective_discount_rate(base, adj, rate_kind)

    assert applied == base + adj
    assert shift == DiscountShift(
        rate_kind=rate_kind, base_rate=base, adj=adj, applied_rate=base + adj
    )
    if adj == 0:
        assert applied == base


@pytest.mark.parametrize("adj", [math.nan, math.inf, -math.inf])
def test_effective_discount_rate_rejects_non_finite_adjustment(adj):
    from engine.discount import effective_discount_rate

    with pytest.raises(ValueError):
        effective_discount_rate(14.7, adj, "wacc")


def test_hmc_stress_row_moves_up_not_down():
    """hmc's WACC parameters: 5.78 + 0.1838 (HEAD rebuilt it as 2.7794)."""
    from engine.discount import effective_discount_rate

    applied, shift = effective_discount_rate(5.78, 0.1838, "wacc")

    assert applied == 5.78 + 0.1838
    assert applied == pytest.approx(5.9638, abs=1e-12)
    assert shift.applied_rate > shift.base_rate


# ── J-14: the Base distress premium is kept exactly once ─────────────────────

# (de, eq_w, adj, applied WACC, applied Ke, Base premium): handoff section 1.
STRESS_TABLE = [
    (100, 1, -0.5, 4.08, 12.25, 0.0),
    (100, 1, 0.0, 4.58, 12.75, 0.0),
    (100, 1, 0.5, 5.08, 13.25, 0.0),
    (100, 60, -0.5, 8.95, 12.25, 0.0),
    (100, 60, 0.0, 9.45, 12.75, 0.0),
    (100, 60, 0.5, 9.95, 13.25, 0.0),
    (100, 100, -0.5, 12.25, 12.25, 0.0),
    (100, 100, 0.0, 12.75, 12.75, 0.0),
    (100, 100, 0.5, 13.25, 13.25, 0.0),
    (500, 1, -0.5, 7.12, 16.0, 3.0),
    (500, 1, 0.0, 7.62, 16.5, 3.0),
    (500, 1, 0.5, 8.12, 17.0, 3.0),
    (500, 60, -0.5, 14.2, 16.0, 3.0),
    (500, 60, 0.0, 14.7, 16.5, 3.0),
    (500, 60, 0.5, 15.2, 17.0, 3.0),
    (500, 100, -0.5, 19.0, 16.0, 3.0),
    (500, 100, 0.0, 19.5, 16.5, 3.0),
    (500, 100, 0.5, 20.0, 17.0, 3.0),
]


@pytest.mark.parametrize(("de", "eq_w", "adj", "wacc", "ke", "premium"), STRESS_TABLE)
def test_premium_is_kept_and_base_result_is_untouched(de, eq_w, adj, wacc, ke, premium):
    from engine.discount import effective_discount_rate

    params = _wacc_params(de, eq_w)
    base = calc_wacc(params)
    before = base.model_dump()

    applied_wacc, wacc_shift = effective_discount_rate(base.wacc, adj, "wacc")
    applied_ke, ke_shift = effective_discount_rate(base.ke, adj, "ke")

    assert base.model_dump() == before == calc_wacc(params).model_dump()
    assert base.distress_premium == premium
    assert applied_wacc == base.wacc + adj
    assert applied_ke == base.ke + adj
    # 7.62 + 0.5 is 8.120000000000001 in binary floating point
    assert applied_wacc == pytest.approx(wacc, abs=1e-12)
    assert applied_ke == pytest.approx(ke, abs=1e-12)
    assert (wacc_shift.base_rate, wacc_shift.adj) == (base.wacc, adj)
    assert (ke_shift.base_rate, ke_shift.adj) == (base.ke, adj)


@pytest.mark.parametrize(("de", "eq_w"), [(100, 60), (500, 60), (500, 100)])
def test_engine_values_fall_as_the_rate_rises(de, eq_w):
    from engine.discount import effective_discount_rate

    vi = _input("dcf_primary")
    base = calc_wacc(_wacc_params(de, eq_w))
    dcf, ddm, rim = [], [], []
    for adj in (-0.5, 0.0, 0.5):
        wacc, _ = effective_discount_rate(base.wacc, adj, "wacc")
        ke, _ = effective_discount_rate(base.ke, adj, "ke")
        dcf.append(_engine_ev("dcf_primary", vi, wacc))
        ddm.append(_engine_ev("ddm", vi, ke))
        rim.append(_engine_ev("rim", vi, ke))

    for values in (dcf, ddm, rim):
        assert values[0] > values[1] > values[2]


# ── runner: each method shifts the rate it consumes ──────────────────────────


def test_dcf_scenarios_use_base_wacc_plus_adjustment_with_premium():
    """R1: de 500 / eq_w 60. HEAD rebuilt the WACC and lost the 3.0 premium."""
    vi = _input("dcf_primary", wacc_params=_wacc_params(500, 60))

    result = run_valuation(vi)

    assert result.wacc.model_dump() == {
        "bl": 2.5,
        "ke": 16.5,
        "kd_at": 4.5,
        "wacc": 14.7,
        "distress_premium": 3.0,
    }
    evs = {code: sc.total_ev for code, sc in result.scenarios.items()}
    # HEAD: Bull 13974 (WACC 11.4), Bear 13132 (WACC 12.0) -- Bear above Base
    assert evs == {"Bull": 10733, "Base": 10299, "Bear": 9900}
    for code, adj in ADJS.items():
        shift = result.scenarios[code].discount_shift
        assert shift.rate_kind == "wacc"
        assert (shift.base_rate, shift.adj) == (14.7, adj)
        assert shift.applied_rate == 14.7 + adj
        assert evs[code] == _engine_ev("dcf_primary", vi, 14.7 + adj)
    assert result.scenarios["Bear"].discount_shift.applied_rate == pytest.approx(15.2)
    assert result.scenarios["Bull"].discount_shift.applied_rate == pytest.approx(14.2)


def test_dcf_adjustment_is_not_scaled_by_equity_weight():
    """R2: de 100 / eq_w 60, no premium. HEAD moved the WACC by 0.30, not 0.50."""
    vi = _input("dcf_primary", wacc_params=_wacc_params(100, 60))

    result = run_valuation(vi)

    assert (result.wacc.wacc, result.wacc.distress_premium) == (9.45, 0.0)
    evs = {code: sc.total_ev for code, sc in result.scenarios.items()}
    # HEAD: Bull 18315 (WACC 9.15), Bear 16923 (WACC 9.75)
    assert evs == {"Bull": 18826, "Base": 17591, "Bear": 16505}
    bear = result.scenarios["Bear"].discount_shift
    assert bear.applied_rate == 9.45 + 0.5
    assert bear.applied_rate == pytest.approx(9.95)


def test_dcf_all_equity_adjustment_matches_cost_of_equity():
    """eq_w 100 and no premium: WACC is Ke, so both readings agree."""
    result = run_valuation(_input("dcf_primary", wacc_params=_wacc_params(100, 100)))

    assert result.wacc.wacc == result.wacc.ke == 12.75
    for code, adj in ADJS.items():
        shift = result.scenarios[code].discount_shift
        assert shift.applied_rate == result.wacc.ke + adj == result.wacc.wacc + adj


@pytest.mark.parametrize(
    ("method", "rate_kind"),
    [("ddm", "ke"), ("rim", "ke"), ("rnpv", "discount_rate")],
)
def test_equity_and_pipeline_methods_shift_their_own_rate(method, rate_kind):
    vi = _input(method)

    result = run_valuation(vi)

    assert result.primary_method == method
    base_rate = RNPV_RATE if method == "rnpv" else result.wacc.ke
    assert result.wacc.model_dump() == calc_wacc(vi.wacc_params).model_dump()
    evs = []
    for code, adj in ADJS.items():
        scenario = result.scenarios[code]
        shift = scenario.discount_shift
        assert shift.rate_kind == rate_kind
        assert (shift.base_rate, shift.adj) == (base_rate, adj)
        assert shift.applied_rate == base_rate + adj
        assert scenario.total_ev == _engine_ev(method, vi, base_rate + adj)
        evs.append(scenario.total_ev)
    assert evs[0] > evs[1] > evs[2]  # Bull (-0.5) > Base > Bear (+0.5)


def test_rnpv_pinned_scenario_values():
    """rNPV keeps its formula (discount_rate + wacc_adj): 9.5 / 10.0 / 10.5."""
    result = run_valuation(_input("rnpv"))

    assert {code: sc.total_ev for code, sc in result.scenarios.items()} == {
        "Bull": 1376,
        "Base": 1347,
        "Bear": 1318,
    }
    assert result.scenarios["Bear"].discount_shift.applied_rate == 10.5


@pytest.mark.parametrize("method", ["sotp", "nav", "multiples"])
def test_methods_without_a_discount_rate_record_no_shift(method):
    result = run_valuation(_input(method))

    assert result.primary_method == method
    assert [sc.discount_shift for sc in result.scenarios.values()] == [None] * 3
    warnings = [w for w in result.engine_warnings if w.code == "UNSUPPORTED_DRIVER"]
    assert len(warnings) == 1
    assert warnings[0].fields == {
        "driver": "wacc_adj",
        "method": method,
        "scenarios": "Bull,Bear",
    }
    assert "Bull -0.50%p, Bear +0.50%p" in warnings[0].message


def test_zero_adjustment_is_still_recorded_and_not_warned():
    zero = {"Bull": 0.0, "Base": 0.0, "Bear": 0.0}

    dcf = run_valuation(_input("dcf_primary", zero))
    sotp = run_valuation(_input("sotp", zero))

    for scenario in dcf.scenarios.values():
        shift = scenario.discount_shift
        assert (shift.rate_kind, shift.adj) == ("wacc", 0.0)
        assert shift.applied_rate == shift.base_rate == dcf.wacc.wacc
    for result in (dcf, sotp):
        assert "UNSUPPORTED_DRIVER" not in {w.code for w in result.engine_warnings}


# ── the old helper is gone, the three layers agree ───────────────────────────


def test_per_scenario_wacc_rebuild_helper_is_removed():
    assert not hasattr(valuation_runner, "_adjust_wacc")


def test_driver_layers_agree_on_which_methods_take_wacc_adj():
    from ai.prompts import _METHOD_DRIVERS
    from engine.scenario_validator import _METHOD_ALLOWED_DRIVERS
    from schemas.models import DISCOUNT_RATE_METHODS

    assert DISCOUNT_RATE_METHODS == {"dcf_primary", "dcf", "ddm", "rim", "rnpv"}
    for layer in (_METHOD_ALLOWED_DRIVERS, _METHOD_DRIVERS):
        for method, drivers in layer.items():
            assert ("wacc_adj" in drivers) == (method in DISCOUNT_RATE_METHODS), method
