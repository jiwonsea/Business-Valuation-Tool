"""Console rendering for historical LTM multiple bands (reporting-only).

Standalone module (console_report.py untouched — band output exists only
behind the --band flag, so the default console stays byte-identical, §7.1 #8).
Korean user-facing output per project convention.
"""

from __future__ import annotations

from typing import Optional

from engine.multiple_band import MIN_OBS_FOR_BAND, band_verdict, percentile_rank
from schemas.point_in_time import HistoricalBand


def _fmt(v: Optional[float]) -> str:
    return f"{v:.2f}x" if v is not None else "—"


def print_band_reports(
    bands: list[HistoricalBand], current: Optional[dict[str, float]] = None
) -> None:
    """Print historical band summary (참고용 — 밸류에이션 입력 아님)."""
    current = current or {}
    print("\n" + "=" * 62)
    print("역사적 배수 밴드 (LTM, point-in-time — 참고용)")
    print("=" * 62)
    for band in bands:
        cur = current.get(band.label)
        print(f"\n[{band.label}] {band.company} — 관측 {band.n_obs}건")
        if band.n_obs == 0:
            print("  이력 부족(N=0) — 밴드 미산출")
        else:
            print(
                f"  min {_fmt(band.band_min)} | p25 {_fmt(band.p25)} | "
                f"median {_fmt(band.median)} | p75 {_fmt(band.p75)} | "
                f"max {_fmt(band.band_max)}"
            )
            if band.n_obs < MIN_OBS_FOR_BAND:
                print(f"  ⚠ 이력 부족(N={band.n_obs}) — 해석 비권장")
            verdict = band_verdict(band, cur)
            if cur is not None:
                rank = percentile_rank(band, cur)
                rank_txt = f", 역사적 백분위 {rank * 100:.0f}%" if rank is not None else ""
                print(f"  현재 {_fmt(cur)} → {verdict}{rank_txt}")
            else:
                print("  현재 배수 없음 — 위치 판정 생략")
        for exc in band.excluded:
            reason = (
                exc.price_reason.value
                if exc.price_reason
                else (
                    f"missing:{','.join(exc.missing_accounts)}"
                    if exc.missing_accounts
                    else exc.note
                )
            )
            print(f"  제외 FY{exc.fiscal_year}: {reason}")
    print("\n* 최초 공시값·접수일 raw close 기준. 보간·소급 없음. 밸류에이션 입력 아님.")
