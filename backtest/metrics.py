"""Calibration metrics — pure functions, no IO."""

from __future__ import annotations

import math
from typing import Optional

from .models import BacktestRecord


def _get_valid_records(
    records: list[BacktestRecord],
    horizon: str,
) -> list[tuple[BacktestRecord, float]]:
    """Filter records with valid price at the given horizon.

    Returns list of (record, actual_price) tuples.
    """
    result = []
    for r in records:
        if not r.is_listed:
            continue
        price = r.get_price(horizon)
        if price is not None and price > 0:
            result.append((r, price))
    return result


# ── 6-1. Forecast-to-Price Error ──


def calc_forecast_price_error(
    records: list[BacktestRecord],
    horizon: str = "t6m",
) -> dict:
    """Compute forecast-to-price error metrics with currency normalization.

    Returns:
        {mape, median_ape, log_ratio_mean, n}
    """
    valid = _get_valid_records(records, horizon)
    if not valid:
        return {"mape": None, "median_ape": None, "log_ratio_mean": None, "n": 0}

    apes = []
    log_ratios = []

    for r, actual in valid:
        predicted = r.predicted_value_native
        if predicted <= 0:
            continue

        ape = abs(predicted - actual) / actual
        apes.append(ape)

        log_ratios.append(math.log(predicted / actual))

    if not apes:
        return {"mape": None, "median_ape": None, "log_ratio_mean": None, "n": 0}

    apes_sorted = sorted(apes)
    n = len(apes)
    mid = n // 2
    median_ape = apes_sorted[mid] if n % 2 else (apes_sorted[mid - 1] + apes_sorted[mid]) / 2

    return {
        "mape": sum(apes) / n,
        "median_ape": median_ape,
        "log_ratio_mean": sum(log_ratios) / len(log_ratios),
        "n": n,
    }


# ── 6-2. Gap Closure Rate ──


def calc_gap_closure(
    records: list[BacktestRecord],
    horizon: str = "t6m",
) -> dict:
    """Measure how much the market-intrinsic gap closed over the horizon.

    Gap closure = (price_horizon - price_t0) / (predicted_native - price_t0)
    - 1.0 = market fully converged to intrinsic value
    - 0.0 = no movement
    - negative = gap widened

    Returns:
        {mean_closure, median_closure, positive_closure_rate, n}
    """
    valid = _get_valid_records(records, horizon)
    if not valid:
        return {"mean_closure": None, "median_closure": None, "positive_closure_rate": None, "n": 0}

    closures = []

    for r, price_horizon in valid:
        price_t0 = r.price_at_prediction or r.price_t0
        if price_t0 is None or price_t0 <= 0:
            continue

        predicted = r.predicted_value_native
        gap = predicted - price_t0
        if abs(gap) < 1e-6:  # No gap to close
            continue

        closure = (price_horizon - price_t0) / gap
        closures.append(closure)

    if not closures:
        return {"mean_closure": None, "median_closure": None, "positive_closure_rate": None, "n": 0}

    closures_sorted = sorted(closures)
    n = len(closures)
    mid = n // 2
    median = closures_sorted[mid] if n % 2 else (closures_sorted[mid - 1] + closures_sorted[mid]) / 2

    positive_count = sum(1 for c in closures if c > 0)

    return {
        "mean_closure": sum(closures) / n,
        "median_closure": median,
        "positive_closure_rate": positive_count / n,
        "n": n,
    }


# ── 6-3. Interval Score ──


def calc_interval_score(
    records: list[BacktestRecord],
    horizon: str = "t6m",
) -> dict:
    """Evaluate scenario range coverage and precision.

    Uses the scenario value range [min(post_dlom), max(post_dlom)] as
    the prediction interval. Measures:
    - Coverage rate: fraction of actuals falling within the interval
    - Mean interval width: average width as % of predicted value
    - Pinball loss: asymmetric quantile-based calibration measure

    Returns:
        {coverage_rate, mean_interval_width, pinball_loss, n}
    """
    valid = _get_valid_records(records, horizon)
    if not valid:
        return {"coverage_rate": None, "mean_interval_width": None, "pinball_loss": None, "n": 0}

    covered_count = 0
    widths = []
    pinball_losses = []
    n_with_scenarios = 0

    for r, actual in valid:
        rng = r.scenario_range_native()
        if rng is None:
            continue

        n_with_scenarios += 1
        lo, hi = rng

        # Coverage
        if lo <= actual <= hi:
            covered_count += 1

        # Width as percentage of predicted
        predicted = r.predicted_value_native
        if predicted > 0:
            width = (hi - lo) / predicted
            widths.append(width)

        # Pinball loss for each scenario quantile
        for s in r.scenarios:
            scenario_val = s.post_dlom * r.unit_multiplier
            # Treat scenario probability as the quantile level
            tau = s.prob / 100.0
            error = actual - scenario_val
            if error >= 0:
                pinball_losses.append(tau * error)
            else:
                pinball_losses.append((1 - tau) * abs(error))

    if n_with_scenarios == 0:
        return {"coverage_rate": None, "mean_interval_width": None, "pinball_loss": None, "n": 0}

    return {
        "coverage_rate": covered_count / n_with_scenarios,
        "mean_interval_width": sum(widths) / len(widths) if widths else None,
        "pinball_loss": sum(pinball_losses) / len(pinball_losses) if pinball_losses else None,
        "n": n_with_scenarios,
    }


# ── 6-4. Calibration Curve ──


def calc_calibration_curve(
    records: list[BacktestRecord],
    horizon: str = "t6m",
    n_bins: int = 5,
    min_bin_samples: int = 10,
    min_total_observations: int = 30,
) -> Optional[list[dict]]:
    """Compute calibration curve: assigned probability vs realized frequency.

    A scenario is "realized" if the actual price falls within ±15% of that
    scenario's post_dlom value (in native currency).

    Returns None if insufficient data. Otherwise list of dicts:
    [{bin_label, bin_lo, bin_hi, assigned_prob_mean, realized_freq, count}]
    """
    valid = _get_valid_records(records, horizon)

    # Collect all (assigned_prob, realized_bool) pairs
    observations: list[tuple[float, bool]] = []

    for r, actual in valid:
        if not r.scenarios:
            continue
        for s in r.scenarios:
            scenario_val = s.post_dlom * r.unit_multiplier
            if scenario_val <= 0:
                continue
            # Realized if actual is within ±15% of scenario value
            tolerance = 0.15 * scenario_val
            realized = abs(actual - scenario_val) <= tolerance
            observations.append((s.prob, realized))

    if len(observations) < min_total_observations:
        return None

    # Create bins
    bin_width = 100.0 / n_bins
    bins: list[dict] = []

    for i in range(n_bins):
        lo = i * bin_width
        hi = (i + 1) * bin_width

        bin_obs = [(p, r) for p, r in observations if lo <= p < hi or (i == n_bins - 1 and p == hi)]
        if len(bin_obs) < min_bin_samples:
            continue

        assigned_mean = sum(p for p, _ in bin_obs) / len(bin_obs)
        realized_count = sum(1 for _, r in bin_obs if r)
        realized_freq = realized_count / len(bin_obs)

        bins.append({
            "bin_label": f"{lo:.0f}-{hi:.0f}%",
            "bin_lo": lo,
            "bin_hi": hi,
            "assigned_prob_mean": assigned_mean,
            "realized_freq": realized_freq * 100,  # Convert to %
            "count": len(bin_obs),
        })

    return bins if bins else None
