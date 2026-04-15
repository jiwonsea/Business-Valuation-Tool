from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engine.scenario_validator import validate_scenario_differentiation


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "scenario_validator"


@pytest.mark.parametrize(
    ("fixture_name", "status", "codes", "retryable"),
    [
        (
            "zero_diff.yaml",
            "fail",
            {"ev_spread_too_low", "driver_diversity_low"},
            True,
        ),
        (
            "method_scope_violation.yaml",
            "fail",
            {"method_scope_violation"},
            False,
        ),
        (
            "differentiated_sotp.yaml",
            "ok",
            set(),
            False,
        ),
        (
            "asymmetric_only.yaml",
            "warning",
            {"asymmetry_major"},
            False,
        ),
    ],
)
def test_validate_scenario_differentiation_fixture(
    fixture_name: str,
    status: str,
    codes: set[str],
    retryable: bool,
) -> None:
    payload = yaml.safe_load((FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"))

    report = validate_scenario_differentiation(
        payload["scenarios"],
        payload["method"],
        payload["ev_by_scenario"],
    )

    assert report.status == status
    assert {error.code for error in report.errors} == codes
    assert report.retryable is retryable
