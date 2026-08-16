"""Output-only EPS scenarios for identified below-OP events.

These scenarios never mutate ``QuarterlyForecast`` and are not inputs to the
backtest, risk band, or valuation bridge. Probability is an analyst judgment,
not a statistically estimated frequency.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from schemas.models import BelowOpEvent, BelowOpEventScenario, EventAdjustedEpsQuarter


def build_event_adjusted_eps(
    eps_points: Sequence[tuple[str, float | None]],
    weighted_avg_basic_shares: int,
    events: Sequence[BelowOpEvent],
    calculation_as_of: date,
    effective_tax_rate: float | None = None,
) -> BelowOpEventScenario:
    """Build a judgment-weighted EPS scenario without moving forecast EPS.

    Args:
        eps_points: Forecast ``(period_label, basic EPS)`` pairs.
        weighted_avg_basic_shares: Denominator for converting KRW bn to basic EPS.
        events: Identified below-OP events validated for lookahead.
        calculation_as_of: Point-in-time cutoff for numeric event information.
        effective_tax_rate: Tax rate applied only to ``basis="pre_tax"`` events.

    Returns:
        Separate per-quarter event-adjusted EPS plus the event audit register.

    Raises:
        ValueError: If shares are invalid, numeric information is lookahead, or a
            pre-tax event has no usable tax rate.
    """
    if weighted_avg_basic_shares <= 0:
        raise ValueError("weighted_avg_basic_shares must be positive")

    event_list = list(events)
    for event in event_list:
        if event.amount_as_of > calculation_as_of:
            raise ValueError(
                f"below_op_event {event.id} amount_as_of {event.amount_as_of} exceeds "
                f"calculation_as_of {calculation_as_of} — amount lookahead"
            )
        if event.basis == "pre_tax" and effective_tax_rate is None:
            raise ValueError(
                f"below_op_event {event.id} basis=pre_tax requires effective_tax_rate"
            )
    if effective_tax_rate is not None and not 0.0 <= effective_tax_rate <= 1.0:
        raise ValueError("effective_tax_rate must be between 0 and 1")

    def net_income_amount(event: BelowOpEvent) -> float:
        if event.basis == "pre_tax":
            assert effective_tax_rate is not None
            return event.amount_krw_bn * (1.0 - effective_tax_rate)
        return event.amount_krw_bn

    quarters: list[EventAdjustedEpsQuarter] = []
    for period_label, eps_point in eps_points:
        if eps_point is None:
            continue
        period_events = [
            event for event in event_list if event.target_period_label == period_label
        ]
        if not period_events:
            continue
        realized_adjustment = sum(
            net_income_amount(event) * 1_000_000_000
            / weighted_avg_basic_shares
            for event in period_events
        )
        expected_adjustment = sum(
            net_income_amount(event) * 1_000_000_000 * event.probability
            / weighted_avg_basic_shares
            for event in period_events
        )
        quarters.append(
            EventAdjustedEpsQuarter(
                period_label=period_label,
                eps_no_event=eps_point,
                eps_if_realized=eps_point + realized_adjustment,
                eps_expected=eps_point + expected_adjustment,
                events=period_events,
            )
        )
    return BelowOpEventScenario(quarters=quarters, events=event_list)
