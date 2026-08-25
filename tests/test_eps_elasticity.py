import math
from pathlib import Path

import pytest
import yaml

from engine.dcf import calc_dcf
from engine.eps_elasticity import measure_eps_elasticity
from schemas.models import DCFParams

FIXTURE = Path(__file__).parent / "fixtures" / "eps_elasticity_sk_hynix.yaml"


@pytest.fixture
def inputs() -> dict:
    data = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    data["dcf_params"] = DCFParams(**data["dcf_params"])
    return data


def measure(inputs: dict, shock_pct: float, **overrides):
    return measure_eps_elasticity(
        **inputs,
        shock_pct=shock_pct,
        tax_rate_pct=overrides.pop("tax_rate_pct", 22.0),
        **overrides,
    )


def test_recurring_shock_is_linear_across_signed_magnitudes(inputs) -> None:
    values = [
        measure(inputs, shock).elasticity_fv
        for shock in (-0.10, -0.05, -0.02, 0.02, 0.05, 0.10)
    ]
    assert max(values) - min(values) < 2e-6


def test_fv_elasticity_includes_equity_leverage(inputs) -> None:
    result = measure(inputs, 0.05)
    equity = result.ev_base - inputs["net_debt"]
    assert result.elasticity_fv / result.elasticity_ev == pytest.approx(
        result.ev_base / equity
    )


def test_normalized_sk_hynix_fixture_regression(inputs) -> None:
    result = measure(inputs, 0.05)
    assert result.elasticity_fv == pytest.approx(1.304693, abs=1e-6)
    assert result.fv_base == pytest.approx(673116.10, abs=0.01)
    assert inputs["dcf_params"].tax_rate == 9.1
    assert result.tax_rate_pct == 22.0


def test_negative_shock_preserves_direction(inputs) -> None:
    result = measure(inputs, -0.05)
    assert result.fv_shocked < result.fv_base


def test_zero_shock_is_rejected(inputs) -> None:
    with pytest.raises(ValueError, match="non-zero"):
        measure(inputs, 0.0)


def test_nonpositive_shocked_ebitda_is_rejected(inputs) -> None:
    with pytest.raises(ValueError, match="shocked EBITDA"):
        measure(inputs, -2.0)


def test_invalid_wacc_terminal_spread_is_propagated(inputs) -> None:
    invalid = {**inputs, "wacc_pct": 2.0}
    with pytest.raises(ValueError, match="WACC"):
        measure(invalid, 0.05)


def test_tax_rate_basis_is_derived_from_override_presence(inputs) -> None:
    normalized = measure(inputs, 0.05, tax_rate_pct=22.0)
    profile_as_is = measure(inputs, 0.05, tax_rate_pct=None)

    assert normalized.tax_rate_basis == "normalized"
    assert profile_as_is.tax_rate_basis == "profile_as_is"
    assert profile_as_is.tax_rate_pct == 9.1


def test_explicit_override_equal_to_profile_rate_is_still_normalized(inputs) -> None:
    result = measure(inputs, 0.05, tax_rate_pct=9.1)

    assert result.tax_rate_basis == "normalized"


def test_nonpositive_base_equity_is_rejected(inputs) -> None:
    ev_base = measure(inputs, 0.05).ev_base

    with pytest.raises(
        ValueError, match="base equity value must be positive"
    ) as exc_info:
        measure({**inputs, "net_debt": ev_base + 1}, 0.05)

    message = str(exc_info.value)
    assert "ev_base=" in message
    assert "net_debt=" in message
    assert "equity_base=" in message


def test_zero_base_equity_is_rejected(inputs) -> None:
    ev_base = measure(inputs, 0.05).ev_base

    with pytest.raises(ValueError, match="base equity value must be positive"):
        measure({**inputs, "net_debt": ev_base}, 0.05)


def test_nonpositive_base_ev_is_rejected(inputs) -> None:
    da_base = 70_000_000
    params = inputs["dcf_params"].model_copy(update={"tax_rate": 22.0})
    base = calc_dcf(
        inputs["ebitda_base"],
        da_base,
        inputs["revenue_base"],
        inputs["wacc_pct"],
        params,
        inputs["base_year"],
    )
    assert da_base > inputs["ebitda_base"]
    assert base.ev_dcf <= 0

    with pytest.raises(ValueError, match="base enterprise value must be positive"):
        measure({**inputs, "da_base": da_base}, 0.05)


def test_negative_shocked_equity_is_allowed(inputs) -> None:
    shock_pct = -0.02
    base = measure(inputs, shock_pct)
    net_debt = base.ev_base - 1
    ebitda_shocked = round(
        inputs["ebitda_base"] + inputs["net_income_base"] * shock_pct / (1 - 22.0 / 100)
    )
    assert ebitda_shocked > 0

    result = measure({**inputs, "net_debt": net_debt}, shock_pct)

    assert result.ev_base - net_debt > 0
    assert result.ev_shocked - net_debt < 0
    assert math.isfinite(result.elasticity_fv)
    assert result.fv_shocked < result.fv_base


def test_positive_shock_never_yields_negative_fv_elasticity(inputs) -> None:
    ev_base = measure(inputs, 0.05).ev_base

    with pytest.raises(ValueError, match="base equity value must be positive"):
        measure({**inputs, "net_debt": ev_base + 1}, 0.05)
