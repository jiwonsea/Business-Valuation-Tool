"""Skill metrics — model error relative to a naive baseline, not in absolute terms.

CLAUDE.md rule: "Model must beat naive-baseline error, not just hit direction."
Absolute MAPE and a standalone direction hit-ratio are unjudgeable without a
reference: on a structurally up-trending memory cycle, "always up" already scores
~90% directional. This module reframes the backtest against two baselines a buy-
side reader actually cares about beating:

  1. Random Walk (RW / persistence): next-quarter forecast = prior-quarter actual.
     RW revenue/eps is exactly the backtest seed, so it is produced under the same
     no-look-ahead loop with zero extra data.
  2. Historical consensus (where available): the *vintage* analyst estimate for
     that quarter, from ConsensusRecord.history — NOT a live snapshot (the ①-B
     verdict found yfinance .KS snapshots ~3x off and circular).

Metrics (lower-is-skill where noted), all point estimates over a small (8Q) sample:
  - MASE      = model MAE / RW MAE.   < 1 → beats persistence.
  - Theil's U2 = model RMSE / RW RMSE. < 1 → beats persistence.
  - skill_score_eps_vs_consensus = 1 - model MAE / consensus MAE. > 0 → beats consensus.
  - surprise_direction_accuracy  = mean[ sign(model - est) == sign(actual - est) ].
        Does the model call the *deviation from consensus* right, not just the level.
  - rw_hit_ratio_direction: RW's own directional hit-ratio, shown beside the model's
        so "model 87.5% vs RW 87.5% → no edge" is visible at a glance.

Pure functions, no IO. Returns a Pydantic model (engine convention; never a DataFrame).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from schemas.models import BacktestSkill


@dataclass(frozen=True)
class SkillRow:
    """One backtest quarter's model, RW (=seed), and actual values.

    rw_revenue / rw_eps ARE the seed (prior-quarter actual) — the random-walk
    forecast for the target quarter. They double as the QoQ-change reference:
    actual_qoq = actual - rw, model_qoq = model - rw.
    """

    quarter_label: str
    actual_revenue: float
    model_revenue: float
    rw_revenue: float
    actual_eps: float | None = None
    model_eps: float | None = None
    rw_eps: float | None = None


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _mase(model_abs: list[float], rw_abs: list[float]) -> float | None:
    """model MAE / RW MAE. None if no rows or RW is a perfect predictor (MAE 0)."""
    if not model_abs or not rw_abs:
        return None
    rw_mae = sum(rw_abs) / len(rw_abs)
    if rw_mae == 0:
        return None
    return (sum(model_abs) / len(model_abs)) / rw_mae


def _theil_u2(model_sq: list[float], rw_sq: list[float]) -> float | None:
    """model RMSE / RW RMSE. None if no rows or RW RMSE 0."""
    if not model_sq or not rw_sq:
        return None
    rw_rmse = sqrt(sum(rw_sq) / len(rw_sq))
    if rw_rmse == 0:
        return None
    return sqrt(sum(model_sq) / len(model_sq)) / rw_rmse


def compute_skill(
    rows: list[SkillRow],
    consensus_history: dict[str, dict[str, float | None]] | None = None,
    *,
    include_trailing: bool = True,
) -> BacktestSkill:
    """Compute naive-baseline-relative skill metrics for a backtest.

    Args:
        rows: Per-quarter model / RW (=seed) / actual values, no look-ahead.
        consensus_history: ConsensusRecord.history — {quarter_label: {actual,
            estimate, surprise_pct}}. Vintage estimates only; never a live snapshot.
            None or sparse → consensus-dependent metrics are None / scored over N.

    Returns:
        BacktestSkill. Every float metric is None when undefined (no rows, no EPS
        data, no consensus for any scored quarter, or a degenerate zero-error
        baseline) — graceful by design given the small sample.
    """
    # --- Revenue: RW vs model absolute and squared errors -------------------
    rev_model_abs: list[float] = []
    rev_rw_abs: list[float] = []
    rev_model_sq: list[float] = []
    rev_rw_sq: list[float] = []
    rw_rev_pct_errors: list[float] = []
    rw_direction_hits: list[float] = []
    for row in rows:
        model_err = row.model_revenue - row.actual_revenue
        rw_err = row.rw_revenue - row.actual_revenue
        rev_model_abs.append(abs(model_err))
        rev_rw_abs.append(abs(rw_err))
        rev_model_sq.append(model_err ** 2)
        rev_rw_sq.append(rw_err ** 2)
        if row.actual_revenue != 0:
            rw_rev_pct_errors.append(abs(rw_err) / abs(row.actual_revenue))
        # RW forecasts zero QoQ change (pred_qoq == 0, treated as >= 0 / "up-flat"),
        # so it "matches" whenever the actual QoQ change is non-negative.
        actual_qoq = row.actual_revenue - row.rw_revenue
        rw_direction_hits.append(1.0 if actual_qoq >= 0 else 0.0)

    # --- EPS: only rows with usable actual + model + rw EPS ------------------
    eps_model_abs: list[float] = []
    eps_rw_abs: list[float] = []
    eps_model_sq: list[float] = []
    eps_rw_sq: list[float] = []
    rw_eps_pct_errors: list[float] = []
    for row in rows:
        if row.actual_eps in (None, 0) or row.model_eps is None or row.rw_eps is None:
            continue
        model_err = row.model_eps - row.actual_eps
        rw_err = row.rw_eps - row.actual_eps
        eps_model_abs.append(abs(model_err))
        eps_rw_abs.append(abs(rw_err))
        eps_model_sq.append(model_err ** 2)
        eps_rw_sq.append(rw_err ** 2)
        rw_eps_pct_errors.append(abs(rw_err) / abs(row.actual_eps))

    # --- Consensus skill + surprise-direction (history-only, vintage) -------
    cons_model_abs: list[float] = []
    cons_est_abs: list[float] = []
    surprise_hits: list[float] = []
    if consensus_history:
        for row in rows:
            if row.actual_eps in (None, 0) or row.model_eps is None:
                continue
            record = consensus_history.get(row.quarter_label)
            if not record:
                continue
            est = record.get("estimate")
            if est is None:
                continue
            actual = row.actual_eps
            cons_model_abs.append(abs(row.model_eps - actual))
            cons_est_abs.append(abs(est - actual))
            surprise_hits.append(
                1.0 if _sign(row.model_eps - est) == _sign(actual - est) else 0.0
            )

    skill_score_eps = None
    cons_est_mae = _mean(cons_est_abs)
    cons_model_mae = _mean(cons_model_abs)
    if cons_est_mae not in (None, 0) and cons_model_mae is not None:
        skill_score_eps = 1.0 - cons_model_mae / cons_est_mae

    trailing_8q = None
    if include_trailing and len(rows) > 8:
        trailing_8q = compute_skill(
            rows[-8:],
            consensus_history=consensus_history,
            include_trailing=False,
        )

    return BacktestSkill(
        naive_rw_revenue_mape=_mean(rw_rev_pct_errors),
        naive_rw_eps_mape=_mean(rw_eps_pct_errors),
        n=len(rows),
        n_eps=len(eps_model_abs),
        mase_revenue=_mase(rev_model_abs, rev_rw_abs),
        mase_eps=_mase(eps_model_abs, eps_rw_abs),
        theil_u2_revenue=_theil_u2(rev_model_sq, rev_rw_sq),
        theil_u2_eps=_theil_u2(eps_model_sq, eps_rw_sq),
        rw_hit_ratio_direction=_mean(rw_direction_hits),
        skill_score_eps_vs_consensus=skill_score_eps,
        surprise_direction_accuracy=_mean(surprise_hits),
        n_surprise_scored=len(surprise_hits),
        trailing_8q=trailing_8q,
    )
