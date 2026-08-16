"""Signal event-study backtest (pure).

Tests whether the text signal at each earnings event T0 predicts the company's
market-adjusted abnormal return around that event.

Non-circularity:
  - Inputs are only text-derived signals and observed prices.
  - No realized financials, revenue, or actuals enter this function.

CAR definition:
  r_t = close_t / close_{t-1} - 1
  AR_t = r_t(stock) - r_t(market)
  CAR[T0->T+k] = sum AR over the k post-event trading days.
"""

from __future__ import annotations

from datetime import date

from engine.signal_extractor import signal_score, tone_to_sign
from schemas.models import ExtractedSignal, SignalBacktestResult, SignalEventResult


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _car(
    t0: date,
    days: int,
    trading_days: list[date],
    stock_closes: dict[date, float],
    market_closes: dict[date, float],
) -> float | None:
    try:
        start_index = trading_days.index(t0)
    except ValueError:
        return None
    if start_index + days >= len(trading_days):
        return None

    total = 0.0
    for offset in range(1, days + 1):
        day = trading_days[start_index + offset]
        previous_day = trading_days[start_index + offset - 1]
        if day not in market_closes or previous_day not in market_closes:
            return None
        previous_stock = stock_closes.get(previous_day)
        current_stock = stock_closes.get(day)
        previous_market = market_closes.get(previous_day)
        current_market = market_closes.get(day)
        if (
            previous_stock in (None, 0)
            or current_stock is None
            or previous_market in (None, 0)
            or current_market is None
        ):
            return None
        total += (current_stock / previous_stock - 1.0) - (
            current_market / previous_market - 1.0
        )
    return total


def run_signal_backtest(
    signals: dict[str, ExtractedSignal],
    event_dates: dict[str, date],
    stock_closes: dict[date, float],
    market_closes: dict[date, float],
    primary_days: int = 1,
    secondary_days: int = 5,
) -> SignalBacktestResult:
    """Run the CAR event study over event labels with both signals and dates."""
    labels = sorted(set(signals) & set(event_dates))
    if not labels:
        raise ValueError("signals and event_dates share no event labels")

    trading_days = sorted(stock_closes)
    if not trading_days:
        raise ValueError("stock_closes is empty")

    events: list[SignalEventResult] = []
    for label in labels:
        event_date = event_dates[label]
        t0 = next((day for day in trading_days if day >= event_date), None)
        if t0 is None:
            continue

        signal = signals[label]
        car_t1 = _car(t0, primary_days, trading_days, stock_closes, market_closes)
        car_t5 = _car(t0, secondary_days, trading_days, stock_closes, market_closes)
        predicted_sign = tone_to_sign(signal.guidance_tone)
        score = signal_score(signal)
        realized_sign_t1 = _sign(car_t1) if car_t1 is not None else None
        direction_match_t1 = (
            None if car_t1 is None or predicted_sign == 0 else realized_sign_t1 == predicted_sign
        )

        events.append(
            SignalEventResult(
                event_label=label,
                t0=t0,
                car_t1=car_t1,
                car_t5=car_t5,
                signal_tone=signal.guidance_tone,
                signal_score=score,
                predicted_sign=predicted_sign,
                realized_sign_t1=realized_sign_t1,
                direction_match_t1=direction_match_t1,
            )
        )

    scored_matches = [
        event.direction_match_t1
        for event in events
        if event.direction_match_t1 is not None
    ]
    sample_n = len(scored_matches)
    directional_hit_ratio = (
        sum(1 for matched in scored_matches if matched) / sample_n if sample_n else 0.0
    )

    information_coefficient: float | None = None
    pairs = [(event.signal_score, event.car_t1) for event in events if event.car_t1 is not None]
    if len(pairs) >= 3:
        import pandas as pd

        corr = pd.Series([score for score, _ in pairs]).corr(
            pd.Series([car for _, car in pairs]),
            method="spearman",
        )
        if pd.notna(corr):
            information_coefficient = float(corr)

    calibration: dict[str, float] = {}
    if events:
        calibration["mean_abs_score"] = sum(abs(event.signal_score) for event in events) / len(events)

    return SignalBacktestResult(
        events=events,
        sample_n=sample_n,
        directional_hit_ratio=directional_hit_ratio,
        information_coefficient=information_coefficient,
        calibration=calibration,
        window_primary=f"T+{primary_days}d",
    )
