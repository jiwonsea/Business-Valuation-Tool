"""Forward-EPS signal block for the generic `--json` output (v2).

Consumed by ../investment-orchestrator/adapters/forward_eps.py. The block is
BVT-INDEPENDENT by construction: it uses only the forward trajectory, the
naive-baseline (Random-Walk) skill, and the Yahoo consensus gap — never
`valuation_bridge` (the module that feeds BVT DCF).

v2 adds the consensus dimension, which removes v1's bullish bias: a name whose
EPS is rising but sits BELOW consensus is "growing less than already priced" and
maps to neutral, not bullish.

Offline / no consensus -> consensus.direction = "n_a" and the stance falls back
to the v1 trajectory rule. `fetch_consensus_fy1_eps` returns None on any network
error so the block always builds.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

IN_LINE_PCT = 0.02  # |model-vs-consensus gap| within this is "in_line"
_FLAT_BAND = 0.03  # |forward EPS growth| within this is "flat"

# Skill-gate window policy (Item 1, 2026-07). A naive-baseline win on n=3 is a
# coin flip; skill is only *claimable* on a statistically meaningful sample. The
# gate requires MIN_SKILL_N EPS-scored quarters; below that forward-EPS abstains
# (skill UNKNOWN, not assumed). Two windows are reported so a regime turn (e.g. a
# memory-cycle inflection) is visible instead of averaged away by an expanding
# window: the full expanding window and the trailing-8Q window.
MIN_SKILL_N = 8
TRAILING_WINDOW = 8


def _eps_scored_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Backtest rows carrying a usable actual + model EPS pair, in quarter order."""
    scored = [
        row
        for row in rows
        if row.get("actual_eps") not in (None, 0) and row.get("model_eps") is not None
    ]
    scored.sort(key=lambda r: str(r.get("quarter", r.get("quarter_label", ""))))
    return scored


def _mape_pct(pairs: list[tuple[float, float]]) -> float | None:
    """MAPE in percent over (model, actual) pairs; matches generic_cli units."""
    errs = [abs(model - actual) / abs(actual) for model, actual in pairs if actual]
    return 100.0 * sum(errs) / len(errs) if errs else None


def _window_skill(rows: list[dict[str, Any]], window: int | None) -> dict[str, Any]:
    """Naive-baseline EPS skill over the full (window=None) or trailing window.

    Pure: reads only per-row actual/model/rw EPS already present in the backtest
    rows (no look-ahead, no fetch). ``beats_naive`` is None when the window has no
    usable rows OR the rows lack the random-walk (rw_eps) column — the caller then
    falls back to the top-level scalar skill for the full window and reports the
    trailing window as unavailable rather than silently claiming skill.
    """
    scored = _eps_scored_rows(rows)
    if window is not None:
        scored = scored[-window:]
    n = len(scored)
    have_rw = bool(scored) and all(row.get("rw_eps") not in (None, 0) for row in scored)
    model_pairs = [(row["model_eps"], row["actual_eps"]) for row in scored]
    eps_mape = _mape_pct(model_pairs)
    naive_mape = (
        _mape_pct([(row["rw_eps"], row["actual_eps"]) for row in scored]) if have_rw else None
    )
    beats_naive = (
        eps_mape is not None and naive_mape is not None and eps_mape < naive_mape
    )
    return {
        "n": n,
        "eps_mape": eps_mape,
        "naive_rw_eps_mape": naive_mape,
        "beats_naive": beats_naive if (eps_mape is not None and naive_mape is not None) else None,
    }


def _consensus_direction(model_fy1: float | None, consensus_fy1: float | None):
    if not model_fy1 or not consensus_fy1:
        return "n_a", None
    gap = (model_fy1 - consensus_fy1) / consensus_fy1
    if gap > IN_LINE_PCT:
        direction = "above"
    elif gap < -IN_LINE_PCT:
        direction = "below"
    else:
        direction = "in_line"
    return direction, round(gap, 4)


def _trajectory(quarterly_eps: list[float | None]):
    q = [e for e in quarterly_eps if e is not None]
    if len(q) < 2 or not q[0]:
        return "unknown", None, len(q)
    growth = (q[-1] - q[0]) / abs(q[0])
    if growth > _FLAT_BAND:
        direction = "rising"
    elif growth < -_FLAT_BAND:
        direction = "falling"
    else:
        direction = "flat"
    return direction, round(growth, 4), len(q)


def _v2_stance(skill_pass: bool, trajectory: str, consensus_dir: str) -> str:
    if not skill_pass:
        return "neutral"  # no naive-baseline skill -> abstain
    if consensus_dir == "n_a":
        # offline / no consensus -> v1 trajectory rule
        return {"rising": "bullish", "falling": "bearish"}.get(trajectory, "neutral")
    if trajectory == "rising":
        # rising & below/in_line consensus = growth already priced -> neutral (v2 fix)
        return {"above": "bullish", "below": "neutral", "in_line": "neutral"}[consensus_dir]
    if trajectory == "falling":
        return {"below": "bearish", "above": "neutral", "in_line": "bearish"}[consensus_dir]
    return "neutral"


def build_signal_block(
    weighted_annual: list[dict[str, Any]],
    weighted_quarterly: list[dict[str, Any]],
    backtest: dict[str, Any],
    consensus_fy1_eps: float | None = None,
) -> dict[str, Any]:
    """Build the adapter-ready ``signal`` block. Pure + offline-safe.

    Item 1 (skill-gate reliability): ``skill_pass`` now requires BOTH a naive-
    baseline win AND n >= MIN_SKILL_N EPS-scored quarters. On a short window skill
    is UNKNOWN, so the block abstains (stance neutral) instead of assuming the win
    is real. For regime-aware backtests the primary and trailing-8Q windows both
    start inside post-break; the full window remains visible for disagreement
    checks. Profiles without regime windows retain full/trailing behavior.
    """
    rows = backtest.get("rows") or []
    post_window = (backtest.get("windows") or {}).get("post_break")
    primary_rows = post_window.get("rows", []) if post_window else rows
    primary_name = "post_break" if post_window else "full"
    full = _window_skill(rows, window=None)
    primary = _window_skill(primary_rows, window=None)
    trailing = _window_skill(primary_rows, window=TRAILING_WINDOW)

    if post_window:
        fallback_eps_mape = post_window.get("eps_mape")
        fallback_naive_ratio = (post_window.get("skill") or {}).get("naive_rw_eps_mape")
        fallback_naive_mape = (
            fallback_naive_ratio * 100 if fallback_naive_ratio is not None else None
        )
        fallback_n = int(post_window.get("n_eps") or 0)
    else:
        fallback_eps_mape = backtest.get("eps_mape")
        fallback_naive_mape = backtest.get("naive_rw_eps_mape")
        fallback_n = int(backtest.get("n") or 0)

    # Primary-window scalars: prefer row-derived; fall back to the selected
    # window summary (or legacy top-level scalars when no regime window exists).
    eps_mape = primary["eps_mape"] if primary["eps_mape"] is not None else fallback_eps_mape
    naive = (
        primary["naive_rw_eps_mape"]
        if primary["naive_rw_eps_mape"] is not None
        else fallback_naive_mape
    )
    # n: EPS-scored quarters. Prefer the primary row count; otherwise use the
    # selected summary's declared count for legacy callers without usable rows.
    n = primary["n"] or fallback_n

    beats_naive_primary = eps_mape is not None and naive is not None and eps_mape < naive
    beats_naive_trailing = trailing["beats_naive"]
    has_row_skill = bool(primary_rows)
    enough = n >= MIN_SKILL_N
    trailing_ok = beats_naive_trailing is True if has_row_skill else True
    skill_pass = bool(enough and beats_naive_primary and trailing_ok)
    regime_shift = (
        trailing["beats_naive"] is not None
        and primary["beats_naive"] is not None
        and trailing["beats_naive"] != primary["beats_naive"]
    )
    full_vs_primary_disagreement = (
        post_window is not None
        and full["beats_naive"] is not None
        and primary["beats_naive"] is not None
        and full["beats_naive"] != primary["beats_naive"]
    )

    q_eps = [q.get("eps_diluted") for q in weighted_quarterly]
    trajectory, growth, n_q = _trajectory(q_eps)

    model_fy1 = weighted_annual[0].get("eps_basic") if weighted_annual else None
    consensus_dir, gap = _consensus_direction(model_fy1, consensus_fy1_eps)

    stance = _v2_stance(bool(skill_pass), trajectory, consensus_dir)

    return {
        "bvt_independent": True,
        "skill": {
            "n": n,
            "min_n": MIN_SKILL_N,
            "eps_mape": eps_mape,
            "naive_rw_eps_mape": naive,
            "skill_pass": skill_pass,
            "reason": (
                "beats_naive & n>=min_n"
                if skill_pass
                else (
                    "n<min_n (skill unknown -> abstain)"
                    if not enough
                    else (
                        "trailing_8q_does_not_beat_naive"
                        if has_row_skill and beats_naive_primary and beats_naive_trailing is False
                        else "does_not_beat_naive"
                    )
                )
            ),
            "primary_window_name": primary_name,
            "primary_window": primary,
            "full_window": full,
            "trailing_8q": trailing,
            "regime_shift": regime_shift,
            "full_vs_primary_disagreement": full_vs_primary_disagreement,
        },
        "trajectory": {
            "direction": trajectory,
            "growth_pct": growth,
            "n_quarters": n_q,
        },
        "consensus": {
            "metric": "eps_fy1",
            "model": model_fy1,
            "consensus": consensus_fy1_eps,
            "gap_pct": gap,
            "direction": consensus_dir,
        },
        "stance": stance,
    }


def _clean_float(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("raw", value.get("fmt"))
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed) or parsed == 0.0:
        return None
    return parsed


def _earnings_estimate_rows(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []

    source = raw.get("earnings_estimate") if isinstance(raw, dict) else raw
    if source is None:
        return []

    if isinstance(source, list):
        return [row for row in source if isinstance(row, dict)]

    if isinstance(source, dict):
        if all(isinstance(value, dict) for value in source.values()):
            rows = []
            for period, value in source.items():
                row = dict(value)
                row.setdefault("period", period)
                rows.append(row)
            return rows
        return [source]

    if hasattr(source, "reset_index") and hasattr(source, "to_dict"):
        try:
            return source.reset_index().to_dict(orient="records")
        except Exception:
            return []

    return []


def _period_for_target_year(target_fiscal_year: int | None, today: date | None = None) -> str | None:
    """Map the model's first annual forecast label to Yahoo's 0y/+1y periods."""
    if target_fiscal_year is None:
        target_fiscal_year = (today or date.today()).year
    current_year = (today or date.today()).year
    if target_fiscal_year == current_year:
        return "0y"
    if target_fiscal_year == current_year + 1:
        return "+1y"
    return None


def _extract_aligned_annual_eps(
    raw: Any,
    target_fiscal_year: int | None = None,
    *,
    today: date | None = None,
) -> float | None:
    period = _period_for_target_year(target_fiscal_year, today=today)
    if period is None:
        return None

    for row in _earnings_estimate_rows(raw):
        if row.get("period") != period:
            continue
        return _clean_float(row.get("avg"))
    return None


def fetch_consensus_fy1_eps(
    ticker_yahoo: str,
    target_fiscal_year: int | None = None,
) -> float | None:
    """Best-effort aligned FY1 EPS consensus from Yahoo.

    ``target_fiscal_year`` is the model's first annual forecast label. Yahoo
    exposes annual consensus as relative periods (0y/+1y), so any year that
    cannot be mapped confidently returns None rather than comparing the wrong
    period. Any network/offline/schema failure also returns None so the signal
    block always builds.
    """
    try:
        from pipeline.yahoo_fetcher import fetch_consensus  # native EFE fetcher

        raw = fetch_consensus(ticker_yahoo)
        return _extract_aligned_annual_eps(raw, target_fiscal_year)
    except Exception:
        return None
