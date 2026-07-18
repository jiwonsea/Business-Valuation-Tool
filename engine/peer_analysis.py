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
    segment_methods: dict[str, str] | None = None,
) -> list[PeerSegmentStats]:
    """Compute per-segment peer multiple statistics.

    Args:
        peers: List of PeerCompany
        multiples: segment code -> applied multiple
        seg_names: segment code -> segment name (optional)
        segment_methods: segment code -> valuation method (default EV/EBITDA)

    Returns:
        List of PeerSegmentStats per segment
    """
    from schemas.models import PeerSegmentStats

    if not peers:
        return []

    method_fields = {
        "ev_ebitda": ("ev_ebitda", "EV/EBITDA"),
        "ev_revenue": ("ev_revenue", "EV/Sales"),
        "pbv": ("pbv", "P/BV"),
        "pe": ("trailing_pe", "P/E (TTM)"),
    }

    # Group peer records by segment first; the method-specific field is selected below.
    by_seg: dict[str, list[PeerCompany]] = {}
    for p in peers:
        by_seg.setdefault(p.segment_code, []).append(p)

    results = []
    for code, seg_peers in sorted(by_seg.items()):
        method = (segment_methods or {}).get(code, "ev_ebitda")
        field, label = method_fields.get(method, ("ev_ebitda", "EV/EBITDA"))
        vals = [
            value
            for peer in seg_peers
            if (value := getattr(peer, field, None)) is not None and value > 0
        ]
        vals_sorted = sorted(vals)
        n = len(vals_sorted)
        name = (seg_names or {}).get(code, code)
        applied = multiples.get(code, 0.0)

        if n == 0:
            results.append(
                PeerSegmentStats(
                    segment_code=code,
                    segment_name=name,
                    count=0,
                    multiple_method=method,
                    multiple_label=label,
                    applied_multiple=applied,
                    warning=f"{label}가 있는 peer 없음 — 적용 배수와 비교 생략",
                )
            )
            continue

        mean_val = statistics.mean(vals_sorted)
        median_val = statistics.median(vals_sorted)

        if n >= 4:
            q1 = statistics.median(vals_sorted[: n // 2])
            q3 = statistics.median(vals_sorted[(n + 1) // 2 :])
        elif n >= 2:
            q1 = vals_sorted[0]
            q3 = vals_sorted[-1]
        else:
            q1 = q3 = vals_sorted[0]

        precision = 1 if method == "ev_ebitda" else 3
        rounded_mean = round(mean_val, precision)
        rounded_median = round(median_val, precision)
        rounded_q1 = round(q1, precision)
        rounded_q3 = round(q3, precision)
        rounded_min = round(min(vals_sorted), precision)
        rounded_max = round(max(vals_sorted), precision)
        premium, position, why = explain_multiple(
            applied=applied,
            median=rounded_median,
            q1=rounded_q1,
            q3=rounded_q3,
            lo=rounded_min,
            hi=rounded_max,
            n=n,
            precision=precision,
        )

        legacy = {}
        if method == "ev_ebitda":
            legacy = {
                "ev_ebitda_median": rounded_median,
                "ev_ebitda_mean": rounded_mean,
                "ev_ebitda_q1": rounded_q1,
                "ev_ebitda_q3": rounded_q3,
                "ev_ebitda_min": rounded_min,
                "ev_ebitda_max": rounded_max,
            }
        results.append(
            PeerSegmentStats(
                segment_code=code,
                segment_name=name,
                count=n,
                multiple_method=method,
                multiple_label=label,
                multiple_median=rounded_median,
                multiple_mean=rounded_mean,
                multiple_q1=rounded_q1,
                multiple_q3=rounded_q3,
                multiple_min=rounded_min,
                multiple_max=rounded_max,
                applied_multiple=applied,
                premium_pct=premium,
                band_position=position,
                rationale=why,
                **legacy,
            )
        )

    return results


def explain_multiple(
    applied: float,
    median: float,
    q1: float,
    q3: float,
    lo: float,
    hi: float,
    n: int,
    precision: int = 1,
) -> tuple[float, str, str]:
    """Explain WHY the applied multiple sits where it sits, vs the peer set.

    Rule-based and deterministic -- no LLM. Answers three questions a reviewer
    always asks: how far from the median, is it inside the interquartile band,
    and is the peer set even large enough to have a meaningful median.

    Returns:
        (premium_pct, band_position, rationale)
    """
    if applied <= 0:
        return 0.0, "", "적용 멀티플 미설정 — 부문 평가방법이 EV/EBITDA가 아닐 수 있음"
    if median <= 0:
        return 0.0, "", (
            f"peer 멀티플 없음 (N={n}) — 적용값 {applied:.{precision}f}x는 "
            "별도 근거 필요"
        )

    premium = round((applied / median - 1) * 100, 1)

    if applied < lo or applied > hi:
        position = "레인지 밖"
    elif applied < q1:
        position = "Q1 미만"
    elif applied <= median:
        position = "Q1~중앙값"
    elif applied <= q3:
        position = "중앙값~Q3"
    else:
        position = "Q3 초과"

    # 1) where it sits vs median
    if abs(premium) < 2.0:
        head = f"peer 중앙값 {median:.{precision}f}x 채택"
    elif premium > 0:
        head = f"peer 중앙값 {median:.{precision}f}x 대비 +{premium:.1f}% 프리미엄"
    else:
        head = f"peer 중앙값 {median:.{precision}f}x 대비 {premium:.1f}% 할인"

    # 2) inside the band or not — this is what makes it defensible
    if position == "레인지 밖":
        band = (
            f"peer 레인지({lo:.{precision}f}~{hi:.{precision}f}x) 밖 — "
            "별도 정당화 필수"
        )
    elif position in ("Q1 미만", "Q3 초과"):
        band = (
            f"IQR({q1:.{precision}f}~{q3:.{precision}f}x) 밖, 레인지 내 — "
            "프리미엄/할인 사유 명시 필요"
        )
    else:
        band = (
            f"IQR({q1:.{precision}f}~{q3:.{precision}f}x) 내 — "
            "통계적으로 방어 가능"
        )

    # 3) sample size caveat
    if n == 1:
        tail = "N=1 — 중앙값 의미 없음, 단일 비교기업 의존"
    elif n < 4:
        tail = f"N={n} — 표본 부족, 사분위수는 min/max 대용"
    else:
        tail = f"N={n}"

    return premium, position, f"{head} · {band} · {tail}"
