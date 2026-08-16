"""Item 2 — cyclical driver library: generic spread-to-margin model + registry."""

from __future__ import annotations

import math

import pytest

from engine.cyclical_drivers import (
    DriverInputs,
    available_sectors,
    get_driver,
    project_margin_path,
    spread_series,
)


def _inputs(out, cost, base=0.30, passthrough=0.5) -> DriverInputs:
    return DriverInputs(output_prices=out, input_costs=cost, base_margin=base, passthrough=passthrough)


def test_anchor_period_reproduces_base_margin() -> None:
    path = project_margin_path(_inputs([100, 110], [40, 40]))
    assert path[0] == pytest.approx(0.30)  # period 0 == base by construction


def test_widening_spread_raises_margin() -> None:
    # spread: 60 -> 80 (+20), passthrough 0.5 -> +10.0 margin
    path = project_margin_path(_inputs([100, 120], [40, 40], base=0.30, passthrough=0.5))
    assert path[1] == pytest.approx(0.30 + 0.5 * 20)


def test_narrowing_spread_lowers_margin() -> None:
    path = project_margin_path(_inputs([100, 90], [40, 40], base=0.30, passthrough=0.5))
    assert path[1] < path[0]


def test_passthrough_scales_sensitivity() -> None:
    lo = project_margin_path(_inputs([100, 120], [40, 40], passthrough=0.2))
    hi = project_margin_path(_inputs([100, 120], [40, 40], passthrough=0.8))
    assert (hi[1] - hi[0]) > (lo[1] - lo[0])


def test_input_cost_rise_compresses_margin() -> None:
    # output flat, input cost rises -> spread narrows -> margin falls
    path = project_margin_path(_inputs([100, 100], [40, 60], passthrough=0.5))
    assert path[1] == pytest.approx(0.30 + 0.5 * (-20))


def test_spread_series_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        spread_series(_inputs([1, 2, 3], [1, 2]))


def test_empty_inputs_return_empty_path() -> None:
    assert project_margin_path(_inputs([], [])) == []


def test_registry_covers_spec_sectors() -> None:
    expected = {
        "memory_semis", "autos", "chemicals", "steel",
        "shipping", "oil_gas", "batteries", "airlines",
    }
    assert expected.issubset(set(available_sectors()))


def test_each_driver_has_output_and_input_roles() -> None:
    for sector in available_sectors():
        d = get_driver(sector)
        roles = {s.role for s in d.data_sources()}
        assert "output_price" in roles
        assert "input_cost" in roles


def test_paywalled_gaps_flagged_where_expected() -> None:
    # memory ASP (TrendForce) and chemicals ethylene/PX (Platts) are paywalled.
    assert "DRAM/NAND contract ASP" in get_driver("memory_semis").paywalled_gaps()
    assert get_driver("chemicals").paywalled_gaps()
    # oil & gas is fully public -> no paywalled gaps.
    assert get_driver("oil_gas").paywalled_gaps() == []


def test_unknown_sector_raises() -> None:
    with pytest.raises(KeyError):
        get_driver("nonexistent")


def test_driver_project_matches_free_function() -> None:
    inp = _inputs([100, 130], [40, 45])
    d = get_driver("steel")
    assert d.project(inp) == project_margin_path(inp)
