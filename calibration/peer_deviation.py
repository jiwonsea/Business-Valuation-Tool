"""Compute deviation between engine-estimated multiples and peer medians.

Pure, no IO. Inputs: list of ``PeerMultiples`` plus engine-side values
(``pe_multiple``, ``ev_revenue_multiple``, per-scenario EV/EBITDA).

Confidence tier rules (Phase 3 SPEC):
  - stable: peer N >= 10
  - preliminary: peer N >= 5
  - insufficient: N < 5 → deviation suppressed

P/E adds a positive-earnings gate: peers with ``trailing_pe <= 0`` are dropped
before stats because negative earnings produce undefined / misleading multiples.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from .peer_fetcher import PeerMultiples

N_STABLE = 10
N_PRELIMINARY = 5


def _tier(n: int) -> str:
    if n >= N_STABLE:
        return "stable"
    if n >= N_PRELIMINARY:
        return "preliminary"
    return "insufficient"


@dataclass(frozen=True)
class PeerStats:
    """Robust summary statistics for one multiple across a peer group."""

    n: int
    median: float | None
    q1: float | None
    q3: float | None
    tier: str


def calc_stats(values: list[float]) -> PeerStats:
    """Median / Q1 / Q3 over positive-finite values.

    Mirrors the quartile convention in ``engine/peer_analysis.calc_peer_stats``
    so reports stay consistent with internal peer analytics.
    """
    cleaned = sorted(v for v in values if v is not None and v > 0)
    n = len(cleaned)
    tier = _tier(n)
    if n == 0:
        return PeerStats(n=0, median=None, q1=None, q3=None, tier=tier)

    median = statistics.median(cleaned)
    if n >= 4:
        q1 = statistics.median(cleaned[: n // 2])
        q3 = statistics.median(cleaned[(n + 1) // 2 :])
    elif n >= 2:
        q1, q3 = cleaned[0], cleaned[-1]
    else:
        q1 = q3 = cleaned[0]
    return PeerStats(n=n, median=round(median, 2), q1=round(q1, 2), q3=round(q3, 2), tier=tier)


@dataclass(frozen=True)
class Deviation:
    """Engine estimate vs peer median for one multiple."""

    multiple_type: str  # 'ev_ebitda' | 'ev_revenue' | 'trailing_pe' | 'forward_pe'
    scope: str  # free-form label, e.g. 'profile', 'scenario A', 'SEG1'
    engine_value: float | None
    stats: PeerStats
    deviation_pct: float | None  # (engine - median) / median * 100
    zscore_iqr: float | None  # (engine - median) / (IQR/1.35), robust z proxy
    flag: str  # '✓' | '⚠️' | '—'
    notes: list[str] = field(default_factory=list)


# IQR / 1.35 ≈ 1σ under normal assumption — robust to outliers.
_IQR_Z_SCALE = 1.35
# Flag threshold: 25% deviation OR |z| ≥ 1.5.
DEV_FLAG_PCT = 25.0
DEV_FLAG_Z = 1.5


def _compute_one(
    multiple_type: str,
    scope: str,
    engine_value: float | None,
    peer_values: list[float],
    extra_notes: list[str] | None = None,
) -> Deviation:
    stats = calc_stats(peer_values)
    notes = list(extra_notes or [])

    if stats.tier == "insufficient":
        notes.append(f"peer N={stats.n} < {N_PRELIMINARY}; deviation suppressed")
        return Deviation(
            multiple_type=multiple_type,
            scope=scope,
            engine_value=engine_value,
            stats=stats,
            deviation_pct=None,
            zscore_iqr=None,
            flag="—",
            notes=notes,
        )

    if engine_value is None or stats.median is None or stats.median == 0:
        return Deviation(
            multiple_type=multiple_type,
            scope=scope,
            engine_value=engine_value,
            stats=stats,
            deviation_pct=None,
            zscore_iqr=None,
            flag="—",
            notes=notes,
        )

    dev_pct = (engine_value - stats.median) / stats.median * 100.0
    iqr = (stats.q3 or 0) - (stats.q1 or 0)
    if iqr > 0:
        z = (engine_value - stats.median) / (iqr / _IQR_Z_SCALE)
    else:
        z = None

    is_flagged = abs(dev_pct) >= DEV_FLAG_PCT or (z is not None and abs(z) >= DEV_FLAG_Z)
    if stats.tier == "preliminary":
        notes.append("preliminary (N<10) — treat as directional signal")
    flag = "⚠️" if is_flagged else "✓"

    return Deviation(
        multiple_type=multiple_type,
        scope=scope,
        engine_value=engine_value,
        stats=stats,
        deviation_pct=round(dev_pct, 1),
        zscore_iqr=round(z, 2) if z is not None else None,
        flag=flag,
        notes=notes,
    )


def compute_profile_deviations(
    peers: list[PeerMultiples],
    *,
    pe_multiple: float | None,
    ev_revenue_multiple: float | None,
    scenario_ev_ebitda: dict[str, float] | None = None,
) -> list[Deviation]:
    """Main entry — produce one ``Deviation`` row per (multiple_type, scope).

    Args:
        peers: Peer multiples fetched via ``peer_fetcher``.
        pe_multiple: Engine-side profile P/E multiple (compared to trailing_pe).
        ev_revenue_multiple: Engine-side EV/Revenue.
        scenario_ev_ebitda: {scenario_label: applied_multiple} for per-scenario rows.

    Peer lists pass the P/E gate (positive earnings) by taking ``trailing_pe`` /
    ``forward_pe`` only when > 0. ``calc_stats`` already drops non-positive values.
    """
    rows: list[Deviation] = []

    ev_ebitda_vals = [p.ev_ebitda for p in peers if p.ev_ebitda is not None]
    ev_rev_vals = [p.ev_revenue for p in peers if p.ev_revenue is not None]
    trailing_pe_vals = [p.trailing_pe for p in peers if p.trailing_pe is not None]
    forward_pe_vals = [p.forward_pe for p in peers if p.forward_pe is not None]

    rows.append(
        _compute_one("ev_revenue", "profile", ev_revenue_multiple, ev_rev_vals)
    )
    rows.append(
        _compute_one(
            "trailing_pe",
            "profile",
            pe_multiple,
            trailing_pe_vals,
            extra_notes=["positive-earnings gate applied"],
        )
    )
    rows.append(
        _compute_one(
            "forward_pe",
            "profile",
            pe_multiple,
            forward_pe_vals,
            extra_notes=["positive-earnings gate applied"],
        )
    )

    if scenario_ev_ebitda:
        for scenario_label, applied in sorted(scenario_ev_ebitda.items()):
            rows.append(
                _compute_one(
                    "ev_ebitda",
                    f"scenario {scenario_label}",
                    applied,
                    ev_ebitda_vals,
                )
            )
    else:
        rows.append(_compute_one("ev_ebitda", "profile", None, ev_ebitda_vals))

    return rows
