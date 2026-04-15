"""Backtest valuation bucket helpers."""

from __future__ import annotations


def classify_bucket(
    primary_method: str | None,
    valuation_bucket: str | None = None,
) -> str:
    """Return a stable valuation bucket for reporting."""
    if valuation_bucket:
        return valuation_bucket

    method = primary_method or "unknown"
    if method in ("ddm", "rim"):
        return "financials"
    if method == "nav":
        return "asset_heavy_reit_nav"
    return "plain_operating"
