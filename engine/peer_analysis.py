"""Peer analysis engine -- multiple statistics computation and auto-lookup.

Aggregates peer companies' EV/EBITDA by segment to compute median, mean, Q1/Q3.
Peers with tickers can fetch real-time multiples from Yahoo Finance.
"""

from __future__ import annotations

import logging
import statistics
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schemas.models import PeerCompany, PeerSegmentStats

logger = logging.getLogger(__name__)


def calc_peer_stats(
    peers: list[PeerCompany],
    multiples: dict[str, float],
    seg_names: dict[str, str] | None = None,
) -> list[PeerSegmentStats]:
    """Compute per-segment peer multiple statistics.

    Args:
        peers: List of PeerCompany
        multiples: segment code -> applied EV/EBITDA multiple
        seg_names: segment code -> segment name (optional)

    Returns:
        List of PeerSegmentStats per segment
    """
    from schemas.models import PeerSegmentStats

    if not peers:
        return []

    # Group by segment
    by_seg: dict[str, list[float]] = {}
    for p in peers:
        if p.ev_ebitda > 0:
            by_seg.setdefault(p.segment_code, []).append(p.ev_ebitda)

    results = []
    for code, vals in sorted(by_seg.items()):
        vals_sorted = sorted(vals)
        n = len(vals_sorted)
        name = (seg_names or {}).get(code, code)

        if n == 0:
            continue

        mean_val = statistics.mean(vals_sorted)
        median_val = statistics.median(vals_sorted)

        if n >= 4:
            q1 = statistics.median(vals_sorted[: n // 2])
            q3 = statistics.median(vals_sorted[(n + 1) // 2:])
        elif n >= 2:
            q1 = vals_sorted[0]
            q3 = vals_sorted[-1]
        else:
            q1 = q3 = vals_sorted[0]

        results.append(PeerSegmentStats(
            segment_code=code,
            segment_name=name,
            count=n,
            ev_ebitda_median=round(median_val, 1),
            ev_ebitda_mean=round(mean_val, 1),
            ev_ebitda_q1=round(q1, 1),
            ev_ebitda_q3=round(q3, 1),
            ev_ebitda_min=round(min(vals_sorted), 1),
            ev_ebitda_max=round(max(vals_sorted), 1),
            applied_multiple=multiples.get(code, 0.0),
        ))

    return results


