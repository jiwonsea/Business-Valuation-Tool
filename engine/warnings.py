"""Pure warning registry and construction helper; calculation stays in the runner."""

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from schemas.models import EngineWarning


WARNING_SEVERITIES: dict[str, Literal["info", "warning", "review"]] = {
    "SCENARIO_MULTIPLE_CLAMPED": "warning",
    "WIDE_SPREAD_ALLOWED": "info",
    "SHARE_COUNT_MISMATCH": "warning",
    "NEGATIVE_SCENARIO_EQUITY": "review",
    "DCF_SCENARIO_FALLBACK": "warning",
    "PROB_NORMALIZED": "info",
    "HOLDING_BRIDGE": "warning",
    "DISTRESS_MULTIPLE_APPLIED": "info",
    "FINANCIAL_ROUTING_ADVISORY": "review",
    "UNSUPPORTED_DRIVER": "warning",
    "NEGATIVE_GROWTH_ADJ": "warning",
}
WARNING_CODES = frozenset(WARNING_SEVERITIES)
WARNING_ORDER = tuple(WARNING_SEVERITIES)


def make_warning(
    code: str,
    scope: str,
    message: str,
    severity: Literal["info", "warning", "review"] | None = None,
    **fields: float | int | str | bool | None,
) -> "EngineWarning":
    """Build a registered warning without importing schemas at module load time."""
    from schemas.models import EngineWarning

    if code not in WARNING_CODES:
        raise ValueError(f"Unregistered engine warning code: {code}")
    return EngineWarning(
        code=code,
        severity=severity if severity is not None else WARNING_SEVERITIES[code],
        scope=scope,
        message=message,
        fields=fields,
    )
