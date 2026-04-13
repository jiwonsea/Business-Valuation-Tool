"""Grid search over scenario probability triples (bull, base, bear).

The grid lives on the simplex {(p_bull, p_base, p_bear) | sum=100,
each ∈ [PROB_BOUNDS], step=GRID_STEP}. Loss is MAPE on
predicted_value_native vs realized price; coverage_rate is a secondary
diagnostic carried alongside the recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from backtest.models import BacktestRecord

from .grid import Bucket, ROLES, classify_scenarios

PROB_BOUNDS: tuple[int, int] = (5, 90)
GRID_STEP: int = 5

# Confidence tier sample-size thresholds (see SPEC §Minimum sample threshold).
N_STABLE: int = 30
N_PRELIMINARY: int = 10

# Minimum MAPE improvement required to emit a recommendation.
# Without these gates, grid search can pick an extreme (e.g. 5/90/5) over the
# baseline (25/50/25) on a fractional MAPE tie — advising a large prob shift
# for no real gain.
MIN_REL_MAPE_IMPROVEMENT: float = 0.05  # 5% relative drop
MIN_ABS_MAPE_IMPROVEMENT: float = 0.005  # 0.5pp absolute drop


@dataclass
class Recommendation:
    bucket_key: tuple[str, str, str]  # (market, sector, horizon)
    n: int
    tier: str  # 'stable' | 'preliminary' | 'insufficient'
    baseline: dict[str, float]  # mean current probs across the bucket {bull,base,bear}
    recommended: dict[str, float] | None  # {'bull': p, 'base': p, 'bear': p}
    baseline_mape: float | None
    recommended_mape: float | None
    baseline_coverage: float | None
    recommended_coverage: float | None
    notes: list[str]


def enumerate_prob_grid(
    *,
    bounds: tuple[int, int] = PROB_BOUNDS,
    step: int = GRID_STEP,
) -> list[tuple[int, int, int]]:
    """All (bull, base, bear) integer triples with sum=100 and each in [lo, hi]."""
    lo, hi = bounds
    points: list[tuple[int, int, int]] = []
    for p_bull in range(lo, hi + 1, step):
        for p_base in range(lo, hi + 1, step):
            p_bear = 100 - p_bull - p_base
            if lo <= p_bear <= hi and p_bear % step == 0:
                points.append((p_bull, p_base, p_bear))
    return points


def _role_means(record: BacktestRecord) -> dict[str, float | None]:
    """Mean post_dlom in native currency per role for a record. None if role empty."""
    classified = classify_scenarios(record.scenarios)
    out: dict[str, float | None] = {}
    for role in ROLES:
        members = classified[role]
        if not members:
            out[role] = None
            continue
        out[role] = sum(s.post_dlom for s in members) / len(members) * record.unit_multiplier
    return out


def predict_with_probs(
    record: BacktestRecord,
    probs: dict[str, float],
) -> float | None:
    """Re-weight a record's scenarios by role probabilities (percentages).

    Returns None if no role mass aligns with the record's available roles.
    Probabilities are renormalised across the roles actually present so a
    record missing 'base' (e.g. 2-scenario profile) still produces a value.
    """
    means = _role_means(record)
    available = {role: probs[role] for role in ROLES if means.get(role) is not None}
    if not available:
        return None
    total = sum(available.values())
    if total <= 0:
        return None
    weighted = sum(means[role] * w / total for role, w in available.items())
    return float(weighted)


def _record_role_range(record: BacktestRecord) -> tuple[float, float] | None:
    """[min, max] post_dlom in native currency across the bull/base/bear means."""
    means = [v for v in _role_means(record).values() if v is not None]
    if not means:
        return None
    return (min(means), max(means))


def _bucket_loss(
    records: Iterable[BacktestRecord],
    probs: dict[str, float],
    horizon: str,
) -> tuple[float | None, float | None]:
    """(MAPE, coverage_rate) for the bucket under the given prob mix.

    coverage_rate uses the bull/bear role-mean range as the prediction interval.
    Both values are None when no record produces a usable prediction.
    """
    apes: list[float] = []
    covered = 0
    counted = 0
    for r in records:
        actual = r.get_price(horizon)
        if actual is None or actual <= 0:
            continue
        predicted = predict_with_probs(r, probs)
        if predicted is None or predicted <= 0:
            continue
        apes.append(abs(predicted - actual) / actual)
        rng = _record_role_range(r)
        if rng is not None:
            counted += 1
            lo, hi = rng
            if lo <= actual <= hi:
                covered += 1
    if not apes:
        return None, None
    mape = sum(apes) / len(apes)
    coverage = covered / counted if counted else None
    return mape, coverage


def _baseline_probs_from_records(records: Iterable[BacktestRecord]) -> dict[str, float]:
    """Mean prob per role across the bucket's records (the 'current' state)."""
    sums = {role: 0.0 for role in ROLES}
    counts = {role: 0 for role in ROLES}
    for r in records:
        classified = classify_scenarios(r.scenarios)
        for role, members in classified.items():
            for s in members:
                sums[role] += s.prob
                counts[role] += 1
    out: dict[str, float] = {}
    for role in ROLES:
        out[role] = (sums[role] / counts[role]) if counts[role] else 0.0
    return out


def confidence_tier(n: int, horizon: str) -> str:
    """Map (sample size, horizon maturity) → tier label per SPEC.

    - ``stable``: N≥30 and horizon is the matured T+12m endpoint.
    - ``preliminary``: N≥10 (any horizon) — early-but-actionable signal.
    - ``insufficient``: N<10.
    """
    if n >= N_STABLE and horizon == "t12m":
        return "stable"
    if n >= N_PRELIMINARY:
        return "preliminary"
    return "insufficient"


def search_sc_prob(bucket: Bucket) -> Recommendation:
    """Grid-search the optimal (bull, base, bear) prob mix for one bucket."""
    market, sector, horizon = bucket.key
    n = bucket.n
    tier = confidence_tier(n, horizon)
    notes: list[str] = []

    baseline = _baseline_probs_from_records(bucket.records)
    baseline_mape, baseline_coverage = _bucket_loss(bucket.records, baseline, horizon)

    if tier == "insufficient":
        notes.append(f"sample size {n} below N≥{N_PRELIMINARY}; recommendation suppressed")
        return Recommendation(
            bucket_key=(market, sector, horizon),
            n=n,
            tier=tier,
            baseline=baseline,
            recommended=None,
            baseline_mape=baseline_mape,
            recommended_mape=None,
            baseline_coverage=baseline_coverage,
            recommended_coverage=None,
            notes=notes,
        )

    grid = enumerate_prob_grid()
    best: tuple[tuple[int, int, int], float, float | None] | None = None
    for triple in grid:
        probs = {"bull": triple[0], "base": triple[1], "bear": triple[2]}
        mape, coverage = _bucket_loss(bucket.records, probs, horizon)
        if mape is None:
            continue
        if best is None or mape < best[1]:
            best = (triple, mape, coverage)

    if best is None:
        notes.append("no grid point produced a valid prediction")
        return Recommendation(
            bucket_key=(market, sector, horizon),
            n=n,
            tier=tier,
            baseline=baseline,
            recommended=None,
            baseline_mape=baseline_mape,
            recommended_mape=None,
            baseline_coverage=baseline_coverage,
            recommended_coverage=None,
            notes=notes,
        )

    triple, best_mape, best_coverage = best
    recommended: dict[str, float] | None = {
        "bull": float(triple[0]), "base": float(triple[1]), "bear": float(triple[2]),
    }

    if best_coverage is not None and best_coverage < 0.60:
        notes.append(
            f"coverage_rate={best_coverage:.0%} below 60% — scenario range may be too narrow"
        )

    # Gate: require material MAPE improvement before recommending a shift.
    if baseline_mape is not None:
        abs_delta = baseline_mape - best_mape
        rel_delta = abs_delta / baseline_mape if baseline_mape > 0 else 0.0
        if abs_delta < MIN_ABS_MAPE_IMPROVEMENT or rel_delta < MIN_REL_MAPE_IMPROVEMENT:
            notes.append(
                f"MAPE improvement {rel_delta:+.1%} "
                f"({abs_delta * 100:+.2f}pp) below threshold "
                f"(≥{MIN_REL_MAPE_IMPROVEMENT:.0%} rel, "
                f"≥{MIN_ABS_MAPE_IMPROVEMENT * 100:.1f}pp abs) — keep baseline"
            )
            recommended = None
            best_mape = None  # suppress recommended_mape display
            best_coverage = None

    return Recommendation(
        bucket_key=(market, sector, horizon),
        n=n,
        tier=tier,
        baseline=baseline,
        recommended=recommended,
        baseline_mape=baseline_mape,
        recommended_mape=best_mape,
        baseline_coverage=baseline_coverage,
        recommended_coverage=best_coverage,
        notes=notes,
    )
