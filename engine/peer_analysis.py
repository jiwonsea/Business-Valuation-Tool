"""Peer 분석 엔진 — 멀티플 통계 산출 및 자동 조회.

Peer 기업의 EV/EBITDA를 부문별로 집계하여 median, mean, Q1/Q3을 산출한다.
ticker가 있는 Peer는 Yahoo Finance에서 실시간 멀티플을 조회할 수 있다.
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
    """부문별 Peer 멀티플 통계 산출.

    Args:
        peers: PeerCompany 리스트
        multiples: segment code → 적용된 EV/EBITDA 멀티플
        seg_names: segment code → 부문명 (optional)

    Returns:
        부문별 PeerSegmentStats 리스트
    """
    from schemas.models import PeerSegmentStats

    if not peers:
        return []

    # 부문별 그룹핑
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


def fetch_peer_multiples(peers: list[PeerCompany]) -> list[PeerCompany]:
    """Deprecated: pipeline.peer_fetcher.fetch_peer_multiples()로 이동.

    engine 모듈의 순수 함수 규칙을 유지하기 위해 IO 로직을 pipeline으로 분리.
    하위 호환을 위해 re-export만 유지.
    """
    from pipeline.peer_fetcher import fetch_peer_multiples as _fetch
    return _fetch(peers)
