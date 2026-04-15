from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from schemas.models import ValidationError, ValidationReport

_METHOD_ALLOWED_DRIVERS = {
    "sotp": {
        "segment_multiples",
        "segment_ebitda",
        "segment_revenue",
        "growth_adj_pct",
        "wacc_adj",
        "market_sentiment_pct",
        "dlom",
    },
    "dcf": {
        "growth_adj_pct",
        "wacc_adj",
        "terminal_growth_adj",
        "market_sentiment_pct",
        "dlom",
    },
    "dcf_primary": {
        "growth_adj_pct",
        "wacc_adj",
        "terminal_growth_adj",
        "market_sentiment_pct",
        "dlom",
    },
    "ddm": {"growth_adj_pct", "wacc_adj", "market_sentiment_pct", "dlom"},
    "rim": {"growth_adj_pct", "wacc_adj", "market_sentiment_pct", "dlom"},
    "nav": {"market_sentiment_pct", "dlom"},
    "multiples": {"market_sentiment_pct", "dlom"},
    "rnpv": {"growth_adj_pct", "wacc_adj", "pos_override", "market_sentiment_pct"},
}

_POSITIVE_DRIVERS = {
    "segment_multiples",
    "segment_revenue",
    "growth_adj_pct",
    "terminal_growth_adj",
    "market_sentiment_pct",
}
_NEGATIVE_DRIVERS = {"wacc_adj", "dlom"}
_STRUCTURED_DRIVERS = {
    "segment_ebitda",
    "segment_revenue",
    "segment_multiples",
    "pos_override",
}
_REQUIRED_SCENARIOS = ("Bull", "Base", "Bear")


def _scenario_lookup(
    scenarios: Mapping[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[ValidationError]]:
    errors: list[ValidationError] = []
    normalized = {str(code).lower(): (str(code), data) for code, data in scenarios.items()}
    resolved: dict[str, dict[str, Any]] = {}
    for required in _REQUIRED_SCENARIOS:
        hit = normalized.get(required.lower())
        if hit is None:
            errors.append(
                ValidationError(
                    path=f"scenarios.{required}",
                    code="missing_required",
                    message=f"required scenario '{required}' is missing",
                )
            )
            continue
        _, payload = hit
        resolved[required] = payload if isinstance(payload, dict) else {}
    return resolved, errors


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_zero_like(value: Any) -> bool:
    if value is None:
        return True
    if _is_number(value):
        return float(value) == 0.0
    if isinstance(value, Mapping):
        return not value or all(_is_zero_like(v) for v in value.values())
    return False


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted((str(k), _canonical_value(v)) for k, v in value.items()))
    if _is_number(value):
        return float(value)
    return value


def _materially_differentiated(values: list[Any]) -> bool:
    if len({_canonical_value(v) for v in values}) <= 1:
        return False
    material = {_canonical_value(v) for v in values if not _is_zero_like(v)}
    return len(material) >= 2


def _validate_driver_types(
    scenarios: Mapping[str, dict[str, Any]],
    method: str,
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    allowed = _METHOD_ALLOWED_DRIVERS.get(method, _METHOD_ALLOWED_DRIVERS.get("dcf_primary", set()))
    known = allowed | _STRUCTURED_DRIVERS | _POSITIVE_DRIVERS | _NEGATIVE_DRIVERS
    for scenario_code, scenario in scenarios.items():
        for driver, value in scenario.items():
            if driver not in known:
                continue
            if driver in _STRUCTURED_DRIVERS:
                if value is not None and not isinstance(value, Mapping):
                    errors.append(
                        ValidationError(
                            path=f"scenarios.{scenario_code}.{driver}",
                            code="type_mismatch",
                            message=f"{driver} must be an object/dict when present",
                        )
                    )
                continue
            if value is not None and not _is_number(value):
                errors.append(
                    ValidationError(
                        path=f"scenarios.{scenario_code}.{driver}",
                        code="type_mismatch",
                        message=f"{driver} must be numeric when present",
                    )
                )
    return errors


def validate_scenario_differentiation(
    scenarios: Mapping[str, dict[str, Any]],
    method: str,
    ev_by_scenario: Mapping[str, float],
) -> ValidationReport:
    """Validate scenario differentiation quality without side effects."""
    resolved, contract_errors = _scenario_lookup(scenarios)
    if contract_errors:
        return ValidationReport(status="fail", errors=contract_errors, retryable=False)

    contract_errors.extend(_validate_driver_types(resolved, method))
    if method != "sotp":
        for scenario_code, scenario in resolved.items():
            if scenario.get("segment_ebitda") is not None:
                contract_errors.append(
                    ValidationError(
                        path=f"scenarios.{scenario_code}.segment_ebitda",
                        code="method_scope_violation",
                        message="segment_ebitda is allowed only for sotp scenarios",
                    )
                )
    if contract_errors:
        return ValidationReport(status="fail", errors=contract_errors, retryable=False)

    allowed = _METHOD_ALLOWED_DRIVERS.get(method, _METHOD_ALLOWED_DRIVERS.get("dcf_primary", set()))
    quality_errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    bull_ev = ev_by_scenario.get("Bull")
    base_ev = ev_by_scenario.get("Base")
    bear_ev = ev_by_scenario.get("Bear")
    if not all(_is_number(v) for v in (bull_ev, base_ev, bear_ev)):
        quality_errors.append(
            ValidationError(
                path="ev_by_scenario",
                code="type_mismatch",
                message="Bull/Base/Bear EV values must all be numeric",
            )
        )
        return ValidationReport(status="fail", errors=quality_errors, retryable=False)

    bull_ev = float(bull_ev)
    base_ev = float(base_ev)
    bear_ev = float(bear_ev)
    if bear_ev <= 0 or bull_ev / bear_ev < 1.3:
        quality_errors.append(
            ValidationError(
                path="ev_by_scenario",
                code="ev_spread_too_low",
                message=f"bull/bear EV spread must be >= 1.3x but got {bull_ev:.4g}/{bear_ev:.4g}",
            )
        )

    differentiated = 0
    for driver in allowed:
        values = [resolved[code].get(driver) for code in _REQUIRED_SCENARIOS]
        if _materially_differentiated(values):
            differentiated += 1
    if differentiated < 2:
        quality_errors.append(
            ValidationError(
                path="scenarios",
                code="driver_diversity_low",
                message=f"need at least 2 materially differentiated drivers, found {differentiated}",
            )
        )

    if len({bull_ev, base_ev, bear_ev}) > 1 and not (bull_ev > base_ev > bear_ev):
        quality_errors.append(
            ValidationError(
                path="ev_by_scenario",
                code="direction_violation",
                message=f"EV should trend Bull > Base > Bear but got {bull_ev:.4g}/{base_ev:.4g}/{bear_ev:.4g}",
            )
        )

    for driver in sorted(allowed & (_POSITIVE_DRIVERS | _NEGATIVE_DRIVERS)):
        if driver in _STRUCTURED_DRIVERS:
            continue
        bull = resolved["Bull"].get(driver)
        base = resolved["Base"].get(driver)
        bear = resolved["Bear"].get(driver)
        if not all(_is_number(v) for v in (bull, base, bear)):
            continue
        if driver in _POSITIVE_DRIVERS and not (float(bull) >= float(base) >= float(bear)):
            quality_errors.append(
                ValidationError(
                    path=f"scenarios.{driver}",
                    code="direction_violation",
                    message=(
                        f"{driver} should trend Bull>=Base>=Bear but got "
                        f"{float(bull):.4g}/{float(base):.4g}/{float(bear):.4g}"
                    ),
                )
            )
        if driver in _NEGATIVE_DRIVERS and not (float(bull) <= float(base) <= float(bear)):
            quality_errors.append(
                ValidationError(
                    path=f"scenarios.{driver}",
                    code="direction_violation",
                    message=(
                        f"{driver} should trend Bull<=Base<=Bear but got "
                        f"{float(bull):.4g}/{float(base):.4g}/{float(bear):.4g}"
                    ),
                )
            )

    bull_gap = abs(bull_ev - base_ev)
    bear_gap = abs(base_ev - bear_ev)
    if bull_gap > 0 or bear_gap > 0:
        ratio = float("inf") if bear_gap == 0 else bull_gap / bear_gap
        if ratio > 3 or ratio < (1 / 3):
            warnings.append(
                ValidationError(
                    path="ev_by_scenario",
                    code="asymmetry_major",
                    message=f"Bull-Base vs Base-Bear asymmetry is too large ({bull_gap:.4g} vs {bear_gap:.4g})",
                )
            )

    if quality_errors:
        return ValidationReport(status="fail", errors=quality_errors, retryable=True)
    if warnings:
        return ValidationReport(status="warning", errors=warnings, retryable=False)
    return ValidationReport(status="ok", errors=[], retryable=False)
