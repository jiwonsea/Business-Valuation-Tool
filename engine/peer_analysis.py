"""Peer 분석 엔진 — 멀티플 통계 산출 및 자동 조회.

Peer 기업의 EV/EBITDA를 부문별로 집계하여 median, mean, Q1/Q3을 산출한다.
ticker가 있는 Peer는 Yahoo Finance에서 실시간 멀티플을 조회할 수 있다.
"""

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schemas.models import PeerCompany, PeerSegmentStats


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
    """ticker가 있는 Peer의 멀티플을 Yahoo Finance에서 자동 조회.

    원본 리스트를 변경하지 않고, 업데이트된 새 리스트를 반환한다.
    조회 실패 시 기존 수동 데이터를 유지한다.
    """
    from pipeline.yahoo_finance import get_quote_summary

    updated = []
    for p in peers:
        if p.ticker:
            try:
                data = get_quote_summary(p.ticker)
                if data:
                    p = p.model_copy(update={
                        "ev_ebitda": data.get("ev_ebitda") or p.ev_ebitda,
                        "market_cap": data.get("market_cap"),
                        "enterprise_value": data.get("enterprise_value"),
                        "trailing_pe": data.get("trailing_pe"),
                        "forward_pe": data.get("forward_pe"),
                        "beta": data.get("beta"),
                        "source": "yahoo",
                    })
            except Exception:
                pass  # 조회 실패 시 수동 데이터 유지
        updated.append(p)
    return updated
