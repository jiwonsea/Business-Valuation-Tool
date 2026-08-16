"""Below-OP EPS risk band + overlay seam (PLAN_tax_finance_overlay.md §3.1/§3.2).

The below-OP block (net financial / FX valuation / one-offs) swings hard quarter
to quarter (-1,516 .. +3,407 KRW bn over the 8Q backtest) and is macro-driven, so
it is deliberately kept OUT of the EPS point estimate. This module expresses that
volatility two ways, both as pure functions that never mutate the forecast:

  - ``robust_half_width`` — a robust scale of the realized below-OP block
    contribution (block_term / NI), the calibration math that seeds the profile's
    ``risk_band.half_width_pct`` draft. MAD-based so the 2025Q3 outlier cannot blow
    the width up; ``trimmed`` is offered for the user method comparison.
  - ``build_eps_risk_band`` — wraps an EPS point estimate in a ± band and attaches
    date-tagged overlays as annotations.

Overlay consumption (fair-value / DCF adjustment) is intentionally left as a
documented SEAM (see ``overlay_valuation_seam`` and ``SEAM_NOTE``): the valuation
consumer is engine/valuation_bridge.py, still a stub, so wiring it here would pull
in an unimplemented DCF (PLAN §3.0). This module surfaces overlays only.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from typing import Literal

from schemas.models import EpsRiskBand, EpsRiskBandQuarter, Overlay

# The 1.4826 factor rescales the median absolute deviation to a standard-deviation
# equivalent under normality, giving an outlier-resistant ~1-sigma scale.
_MAD_TO_SIGMA = 1.4826

SEAM_NOTE = (
    "Overlays are surfaced as risk annotations only; fair-value/DCF consumption is "
    "delegated to engine/valuation_bridge.py (PLAN_tax_finance_overlay.md §3.0/§5)."
)


def robust_half_width(
    block_contrib: Sequence[float],
    k: float = 1.0,
    method: Literal["mad", "trimmed"] = "mad",
) -> float:
    """Robust half-width of the below-OP block contribution distribution.

    Args:
        block_contrib: Realized per-quarter block_term / NI (share of actual NI),
            from scripts/diagnose_tax_finance.py.
        k: Width multiplier on the robust scale (k=1 ~ one robust sigma).
        method: ``"mad"`` -> 1.4826 × MAD × k (default, outlier-resistant);
            ``"trimmed"`` -> population std of the sample with min & max removed × k.

    Returns:
        Non-negative half-width as a fraction of the EPS point estimate.

    Raises:
        ValueError: Empty input, an unknown method, or < 3 points for ``trimmed``.
    """
    values = list(block_contrib)
    if not values:
        raise ValueError("block_contrib must be non-empty")
    if method == "mad":
        median = statistics.median(values)
        mad = statistics.median([abs(v - median) for v in values])
        scale = _MAD_TO_SIGMA * mad
    elif method == "trimmed":
        if len(values) < 3:
            raise ValueError("trimmed method needs at least 3 points")
        trimmed = sorted(values)[1:-1]
        scale = statistics.pstdev(trimmed)
    else:
        raise ValueError(f"unknown method {method!r} (expected 'mad' or 'trimmed')")
    return scale * k


def overlay_valuation_seam(overlays: Sequence[Overlay] | None) -> list[Overlay]:
    """SEAM (not yet consumed): return overlays unchanged as the annotation payload.

    The actual fair-value / DCF adjustment from these overlays is delegated to
    engine/valuation_bridge.py (still a stub). Centralising the pass-through here
    marks the single point a future valuation workstream wires in, without giving
    overlays any EPS or band effect today.
    """
    return list(overlays or [])


def build_eps_risk_band(
    eps_points: Sequence[tuple[str, float | None]],
    half_width_pct: float,
    method: Literal["mad", "trimmed"],
    k: float,
    overlays: Sequence[Overlay] | None = None,
    scenario: Literal["bear", "base", "bull", "weighted"] = "weighted",
) -> EpsRiskBand:
    """Wrap each EPS point estimate in a ± below-OP band, plus overlay annotations.

    The band is ``eps_point ± |eps_point| × half_width_pct`` (symmetric, sign-safe).
    EPS points are echoed verbatim — this function never recomputes EPS, so the
    point estimate stays bit-identical.

    Args:
        eps_points: (period_label, eps) pairs; quarters with ``eps is None`` are
            skipped (no band without a point).
        half_width_pct: User-owned band half-width (profile YAML draft), seeded by
            ``robust_half_width``.
        method, k: Provenance of ``half_width_pct`` (recorded, not recomputed here).
        overlays: Date-tagged overlays surfaced as annotations (seam only).
        scenario: Which point-estimate path the band wraps.

    Returns:
        EpsRiskBand with one EpsRiskBandQuarter per non-null EPS point.
    """
    quarters: list[EpsRiskBandQuarter] = []
    for label, eps in eps_points:
        if eps is None:
            continue
        spread = abs(eps) * half_width_pct
        quarters.append(
            EpsRiskBandQuarter(
                period_label=label,
                eps_point=eps,
                eps_lower=eps - spread,
                eps_upper=eps + spread,
            )
        )
    return EpsRiskBand(
        scenario=scenario,
        method=method,
        k=k,
        half_width_pct=half_width_pct,
        quarters=quarters,
        overlays=overlay_valuation_seam(overlays),
        seam_note=SEAM_NOTE,
    )
