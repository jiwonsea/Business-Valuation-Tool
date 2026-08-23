"""Basis-safe comparison rows for post-earnings scorecards."""

from __future__ import annotations

from collections.abc import Mapping


def compare_bases(
    *,
    base: Mapping[str, float],
    weighted: Mapping[str, float],
    actual: Mapping[str, float],
    consensus: Mapping[str, float],
) -> dict:
    """Return labelled base/weighted errors and separate gap-of-gap fields."""
    metrics = set(base) & set(weighted) & set(actual) & set(consensus)
    if not metrics:
        raise ValueError("basis comparison requires at least one common metric")
    if any(actual[name] == 0 or consensus[name] == 0 for name in metrics):
        raise ValueError("actual and consensus values must be non-zero")

    comparisons = []
    gaps: dict[str, dict[str, float]] = {}
    for basis, forecast in (("base", base), ("weighted", weighted)):
        rows = {
            name: {
                "forecast": forecast[name],
                "actual": actual[name],
                "error_pct": (forecast[name] - actual[name]) / actual[name],
            }
            for name in sorted(metrics)
        }
        comparisons.append({"basis": basis, "metrics": rows})
        gaps[f"gap_of_gap_{basis}"] = {
            name: (forecast[name] - actual[name]) / consensus[name]
            for name in sorted(metrics)
        }
    return {"comparisons": comparisons, **gaps}


def format_gap_of_gap(comparison: Mapping) -> list[str]:
    """Render auditable, explicitly named gap-of-gap output fields."""
    lines = []
    for field in ("gap_of_gap_base", "gap_of_gap_weighted"):
        values = comparison[field]
        rendered = ", ".join(f"{name}={value * 100:+.2f}%p" for name, value in values.items())
        lines.append(f"- `{field}`: {rendered}")
    return lines
