"""Multi-variable news driver resolution: Y = sum(beta_i * X_i).

Pure function that aggregates partial effects (beta) of news events (independent variables)
with scenario-specific weights (X) and applies them to ScenarioParams driver fields.
"""

from __future__ import annotations

from schemas.models import NewsDriver, ScenarioParams


def resolve_drivers(
    sc: ScenarioParams,
    news_drivers: list[NewsDriver],
) -> ScenarioParams:
    """Aggregate news driver effects and apply to ScenarioParams fields.

    If active_drivers is None, return sc unchanged (backward compatible).
    If active_drivers is an empty dict, all drivers are inactive (Base Case).
    """
    if sc.active_drivers is None:
        return sc

    driver_map = {nd.id: nd for nd in news_drivers}
    totals: dict[str, float] = {}
    rationale_parts: dict[str, list[str]] = {}

    for driver_id, weight in sc.active_drivers.items():
        nd = driver_map.get(driver_id)
        if nd is None:
            continue
        for field, effect in nd.effects.items():
            totals[field] = totals.get(field, 0.0) + weight * effect
            pct = f"{weight:.0%}" if weight != 1.0 else "100%"
            rationale_parts.setdefault(field, []).append(
                f"{nd.name}({pct}): {effect:+.2f}"
            )

    updates: dict[str, object] = {}
    driver_rationale: dict[str, str] = {}
    for field, total in totals.items():
        updates[field] = round(total, 4)
        driver_rationale[field] = " + ".join(rationale_parts[field])

    if driver_rationale:
        updates["driver_rationale"] = driver_rationale

    return sc.model_copy(update=updates)
