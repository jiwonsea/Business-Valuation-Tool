from pathlib import Path

import pytest
import yaml

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
        tax_rate_basis=overrides.pop("tax_rate_basis", "normalized"),
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
