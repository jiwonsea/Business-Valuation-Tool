"""Pure calibration helpers for cyclical spread drivers.

Skill-gate consistency (Item 1): a driver only *claims* skill when it beats the
naive persistence baseline AND the scored sample is large enough to mean something
(n >= MIN_SKILL_N). `beats_naive` stays the raw MAE comparison; `skill_pass` is the
gated verdict consumers should act on — mirroring engine.generic_signal so the
cyclical path cannot confidently pass on a coin-flip sample.
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_SKILL_N = 8  # scored one-step points required to claim skill (matches generic gate)


@dataclass(frozen=True)
class DriverSkill:
    n: int
    passthrough: float
    model_mae: float | None
    naive_mae: float | None
    beats_naive: bool          # raw: model MAE < naive MAE
    skill_pass: bool           # gated: beats_naive AND n >= min_n
    min_n: int                 # the n threshold applied
    reason: str


def calibrate_passthrough(spreads: list[float], margins: list[float]) -> float:
    """OLS slope of margin change versus spread change.

    The intercept is the anchor margin, matching ``project_margin_path``. Inputs
    should already be period-aligned and index-normalized by the IO layer.
    """
    if len(spreads) != len(margins):
        raise ValueError("spreads and margins must have the same length")
    if len(spreads) < 2:
        return 0.0
    x0 = spreads[0]
    y0 = margins[0]
    xs = [x - x0 for x in spreads]
    ys = [y - y0 for y in margins]
    denom = sum(x * x for x in xs)
    if denom == 0:
        return 0.0
    return sum(x * y for x, y in zip(xs, ys)) / denom


def expanding_driver_skill(
    spreads: list[float],
    margins: list[float],
    *,
    min_train: int = 8,
    min_n: int = MIN_SKILL_N,
) -> DriverSkill:
    """One-step expanding-window skill versus margin persistence.

    For each target period, fit passthrough on all prior periods, predict the
    target margin from the first-period anchor and target spread, and compare
    absolute error to a random-walk margin forecast (prior actual margin).

    ``skill_pass`` requires the model to beat naive AND at least ``min_n`` scored
    one-step points, so a thin win on a short overlap abstains rather than claims
    skill — the same policy the generic forward-EPS gate applies.
    """
    if len(spreads) != len(margins):
        raise ValueError("spreads and margins must have the same length")
    model_abs: list[float] = []
    naive_abs: list[float] = []
    last_slope = 0.0
    for idx in range(min_train, len(spreads)):
        train_spreads = spreads[:idx]
        train_margins = margins[:idx]
        last_slope = calibrate_passthrough(train_spreads, train_margins)
        pred = train_margins[0] + last_slope * (spreads[idx] - train_spreads[0])
        naive = margins[idx - 1]
        actual = margins[idx]
        model_abs.append(abs(pred - actual))
        naive_abs.append(abs(naive - actual))
    model_mae = sum(model_abs) / len(model_abs) if model_abs else None
    naive_mae = sum(naive_abs) / len(naive_abs) if naive_abs else None
    n = len(model_abs)
    beats = model_mae is not None and naive_mae not in (None, 0) and model_mae < naive_mae
    enough = n >= min_n
    skill_pass = bool(beats and enough)
    if skill_pass:
        reason = "beats_naive & n>=min_n"
    elif not enough:
        reason = f"n={n}<min_n={min_n} (skill unknown -> abstain)"
    else:
        reason = "does_not_beat_naive"
    return DriverSkill(
        n=n,
        passthrough=last_slope,
        model_mae=model_mae,
        naive_mae=naive_mae,
        beats_naive=bool(beats),
        skill_pass=skill_pass,
        min_n=min_n,
        reason=reason,
    )
