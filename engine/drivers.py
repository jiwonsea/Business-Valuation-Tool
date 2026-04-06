"""Multi-variable news driver resolution: Y = sum(beta_i * X_i) with correlation dampening.

Pure function that aggregates partial effects (beta) of news events (independent variables)
with scenario-specific weights (X) and applies them to ScenarioParams driver fields.

When multiple drivers affect the same field, a square-root dampening factor is applied:
  dampened = raw_sum * sqrt(N) / N  (where N = number of contributing drivers)
This accounts for correlation between drivers — purely additive effects overestimate
the combined impact when drivers are not truly independent.
"""

from __future__ import annotations

import math

from schemas.models import NewsDriver, ScenarioParams

# Dampening disabled for these fields (absolute overrides, not additive adjustments)
_NO_DAMPEN_FIELDS = frozenset({"ddm_growth", "ev_multiple"})


def resolve_drivers(
    sc: ScenarioParams,
    news_drivers: list[NewsDriver],
    dampen: bool = True,
) -> ScenarioParams:
    """Aggregate news driver effects and apply to ScenarioParams fields.

    If active_drivers is None, return sc unchanged (backward compatible).
    If active_drivers is an empty dict, all drivers are inactive (Base Case).

    Args:
        sc: Scenario parameters with active_drivers mapping.
        news_drivers: Catalog of available news drivers.
        dampen: Apply correlation dampening when multiple drivers affect the same field.
            Dampening factor: sqrt(N)/N where N = number of contributing drivers.
            Disabled for absolute-override fields (ddm_growth, ev_multiple).
    """
    if sc.active_drivers is None:
        return sc

    driver_map = {nd.id: nd for nd in news_drivers}
    # Track per-field: list of (weighted_effect, label)
    per_field: dict[str, list[tuple[float, str]]] = {}

    for driver_id, weight in sc.active_drivers.items():
        nd = driver_map.get(driver_id)
        if nd is None:
            continue
        for field, effect in nd.effects.items():
            pct = f"{weight:.0%}" if weight != 1.0 else "100%"
            label = f"{nd.name}({pct}): {effect:+.2f}"
            per_field.setdefault(field, []).append((weight * effect, label))

    updates: dict[str, object] = {}
    driver_rationale: dict[str, str] = {}

    for field, contributions in per_field.items():
        raw_sum = sum(c[0] for c in contributions)
        n = len(contributions)

        # Apply correlation dampening: sqrt(N)/N when N > 1
        if dampen and n > 1 and field not in _NO_DAMPEN_FIELDS:
            factor = math.sqrt(n) / n
            dampened = raw_sum * factor
            rationale_suffix = f" → 상관감쇠 √{n}/{n}={factor:.2f} → {dampened:+.4f}"
        else:
            dampened = raw_sum
            rationale_suffix = ""

        updates[field] = round(dampened, 4)
        parts = " + ".join(c[1] for c in contributions)
        driver_rationale[field] = parts + rationale_suffix

    if driver_rationale:
        updates["driver_rationale"] = driver_rationale

    return sc.model_copy(update=updates)
