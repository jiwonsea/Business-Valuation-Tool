"""Fiscal-aware Yahoo consensus normalization for generic-company profiles."""

from __future__ import annotations

import math
from calendar import monthrange
from datetime import date
from typing import Any

from pipeline.edgar_fetcher import model_label_for_period
from schemas.generic import GenericProfile
from schemas.models import ConsensusRecord

_FORWARD_QUARTERS = ("0q", "+1q")
_FORWARD_YEARS = ("0y", "+1y")


def _clean(value: object) -> float | None:
    if isinstance(value, dict):
        value = value.get("raw", value.get("fmt"))
    if value in (None, ""):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _rows(raw: object) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if isinstance(raw, dict):
        rows: list[dict[str, Any]] = []
        for period, value in raw.items():
            if not isinstance(value, dict):
                continue
            row = dict(value)
            row.setdefault("period", period)
            rows.append(row)
        return rows
    return []


def _period_values(raw: object, periods: tuple[str, ...]) -> dict[str, float | None]:
    return {
        str(row["period"]): _clean(row.get("avg"))
        for row in _rows(raw)
        if row.get("period") in periods
    }


def _period_end(row: dict[str, Any]) -> date | None:
    value = row.get("quarter") or row.get("period")
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _advance_quarter_end(period_end: date, count: int = 1) -> date:
    month_index = period_end.year * 12 + period_end.month - 1 + count * 3
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(period_end.day, monthrange(year, month)[1])
    return date(year, month, day)


def _fiscal_year(period_end: date, fiscal_year_end_month: int) -> int:
    return period_end.year + (1 if period_end.month > fiscal_year_end_month else 0)


def _quality_failure(notes: list[str], quality_notes: list[str], message: str) -> None:
    notes.append(message)
    quality_notes.append(message)


def to_generic_consensus_record(
    raw_yahoo: dict[str, Any],
    profile: GenericProfile,
    as_of: date,
) -> ConsensusRecord:
    """Normalize Yahoo estimates against the profile's fiscal calendar.

    Args:
        raw_yahoo: Raw output from ``pipeline.yahoo_fetcher.fetch_consensus``.
        profile: Generic issuer profile containing actual period ends and units.
        as_of: Snapshot date preserved alongside the cached fetch timestamp.

    Returns:
        Fiscal-aware ``ConsensusRecord``. Unsafe forward joins are explicit
        ``None`` values; independently mappable history remains available.

    Raises:
        ValueError: If actual period-end data is missing or ``as_of`` predates
            the latest actual period end.
    """
    dated_actuals = [actual for actual in profile.actuals if actual.period_end is not None]
    if not dated_actuals:
        raise ValueError("generic consensus requires at least one actual period_end")
    latest_actual = max(dated_actuals, key=lambda actual: actual.period_end)
    if as_of < latest_actual.period_end:
        raise ValueError(
            f"consensus as_of {as_of} predates latest actual period_end {latest_actual.period_end}"
        )

    notes: list[str] = []
    quality_notes: list[str] = []
    next_ends = [_advance_quarter_end(latest_actual.period_end, offset) for offset in (1, 2)]
    quarter_labels = [
        model_label_for_period(period_end, profile.fiscal_year_end_month)
        for period_end in next_ends
    ]
    fiscal_year = _fiscal_year(next_ends[0], profile.fiscal_year_end_month)
    annual_years = [fiscal_year, fiscal_year + 1]

    history_rows = _rows(raw_yahoo.get("earnings_history"))
    history: dict[str, dict[str, float | None]] = {}
    history_ends: list[date] = []
    for row in history_rows:
        end = _period_end(row)
        if end is None:
            continue
        history_ends.append(end)
        label = model_label_for_period(end, profile.fiscal_year_end_month)
        history[label] = {
            "actual": _clean(row.get("epsActual")),
            "estimate": _clean(row.get("epsEstimate")),
            "surprise_pct": _clean(row.get("surprisePercent")),
        }

    revenue_q_raw = _period_values(raw_yahoo.get("revenue_estimate"), _FORWARD_QUARTERS)
    eps_q_raw = _period_values(raw_yahoo.get("earnings_estimate"), _FORWARD_QUARTERS)
    revenue_y_raw = _period_values(raw_yahoo.get("revenue_estimate"), _FORWARD_YEARS)
    eps_y_raw = _period_values(raw_yahoo.get("earnings_estimate"), _FORWARD_YEARS)

    latest_history_end = max(history_ends) if history_ends else None
    latest_actual_label = model_label_for_period(
        latest_actual.period_end, profile.fiscal_year_end_month
    )
    latest_history_label = (
        model_label_for_period(latest_history_end, profile.fiscal_year_end_month)
        if latest_history_end is not None
        else None
    )
    anchor_safe = latest_history_label == latest_actual_label
    if not anchor_safe:
        reason = (
            "earnings_history missing; forward consensus anchor refused"
            if latest_history_end is None
            else (
                f"latest earnings_history end {latest_history_end} != latest actual "
                f"period_end {latest_actual.period_end}; forward consensus anchor refused"
            )
        )
        _quality_failure(notes, quality_notes, reason)

    revenue_periods = set(revenue_q_raw)
    eps_periods = set(eps_q_raw)
    if revenue_periods != eps_periods:
        _quality_failure(
            notes,
            quality_notes,
            f"quarterly period-set mismatch: revenue={sorted(revenue_periods)}, eps={sorted(eps_periods)}",
        )
        anchor_safe = False

    revenue_q: dict[str, float | None] = {label: None for label in quarter_labels}
    eps_q: dict[str, float | None] = {label: None for label in quarter_labels}
    revenue_y: dict[int, float | None] = {year: None for year in annual_years}
    eps_y: dict[int, float | None] = {year: None for year in annual_years}

    if anchor_safe:
        for index, period in enumerate(_FORWARD_QUARTERS):
            revenue = revenue_q_raw.get(period)
            revenue_q[quarter_labels[index]] = (
                revenue / profile.unit_scale if revenue is not None else None
            )
            eps_q[quarter_labels[index]] = eps_q_raw.get(period)
        for index, period in enumerate(_FORWARD_YEARS):
            revenue = revenue_y_raw.get(period)
            revenue_y[annual_years[index]] = (
                revenue / profile.unit_scale if revenue is not None else None
            )
            eps_y[annual_years[index]] = eps_y_raw.get(period)

        first_label = quarter_labels[0]
        first_revenue = revenue_q[first_label]
        if first_revenue is not None and latest_actual.revenue_total:
            ratio = first_revenue / latest_actual.revenue_total
            if not 0.3 <= ratio <= 3.0:
                _quality_failure(
                    notes,
                    quality_notes,
                    (
                        f"0q revenue unit gate failed: original={first_revenue:g} "
                        f"{profile.reporting_unit}, latest={latest_actual.revenue_total:g}, ratio={ratio:.3f}"
                    ),
                )
                revenue_q[first_label] = None

        realized_margins = [
            actual.net_profit / actual.revenue_total
            for actual in profile.actuals
            if actual.net_profit is not None and actual.revenue_total
        ]
        if realized_margins:
            lower = min(realized_margins) - 0.10
            upper = max(realized_margins) + 0.10
            pairs: list[tuple[str, float | None, float | None, dict, object]] = []
            for label in quarter_labels:
                pairs.append((label, revenue_q[label], eps_q[label], eps_q, label))
            for year in annual_years:
                pairs.append((str(year), revenue_y[year], eps_y[year], eps_y, year))
            for label, revenue, eps, target, key in pairs:
                if revenue in (None, 0) or eps is None:
                    continue
                implied_margin = (eps * profile.weighted_avg_diluted / profile.unit_scale) / revenue
                if not lower <= implied_margin <= upper:
                    _quality_failure(
                        notes,
                        quality_notes,
                        (
                            f"{label} implied net-margin gate failed: original EPS={eps:g}, "
                            f"margin={implied_margin:.3f}, allowed=[{lower:.3f}, {upper:.3f}]"
                        ),
                    )
                    target[key] = None

    if all(value is None for value in revenue_q.values()):
        notes.append("quarterly revenue consensus unavailable")
    if all(value is None for value in eps_q.values()):
        notes.append("quarterly EPS consensus unavailable")

    return ConsensusRecord(
        ticker=profile.ticker,
        as_of=as_of,
        revenue_estimate_quarterly=revenue_q,
        eps_estimate_quarterly=eps_q,
        revenue_estimate_annual=revenue_y,
        eps_estimate_annual=eps_y,
        history=history,
        notes=notes,
        quality_notes=quality_notes,
    )
