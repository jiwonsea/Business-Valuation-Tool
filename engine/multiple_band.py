"""Historical multiple band — pure statistics over point-in-time observations.

REPORTING REFERENCE ONLY — NOT A VALUATION INPUT.
Contract (HANDOFF_CODEX_phase2_impl_scope_2026-07-18 §7-1, no relaxation):

- The Phase 1 debate REJECTED wiring P1/P2 into the valuation engine. Nothing
  in run_valuation / method_selector / valuation_runner may import this
  module; a grep test (tests/test_multiple_band.py) pins that rule.
- Pure function contract (engine/ rule): no IO, no network, no state. Inputs
  are frozen Pydantic observations built by pipeline/timeseries.py from the
  point-in-time contract (basis="original", available_at<=t, no
  interpolation); this module only aggregates them.
- Statistics are computed only from actual observations. n_obs==0 yields an
  empty band (all stats None) — a band is never fabricated, and renderers
  must show "이력 부족(N=x)" for small n (threshold: MIN_OBS_FOR_BAND).
- Labels are restricted to LTM P/B·P/S by the models themselves
  (require_allowed_multiple_label).
"""

from __future__ import annotations

from statistics import quantiles
from typing import Optional, Sequence

from schemas.point_in_time import ExcludedYear, HistoricalBand, MultipleObservation

# Below this many observations the band is rendered as "이력 부족(N=x)"
# instead of a usable reference range (§4 AC — P3 empty-state precedent).
MIN_OBS_FOR_BAND: int = 5


def build_band(
    label: str,
    company: str,
    observations: Sequence[MultipleObservation],
    excluded: Sequence[ExcludedYear] = (),
) -> HistoricalBand:
    """Aggregate observations into a percentile band (min/p25/median/p75/max).

    Deterministic: quantiles use the "inclusive" method (linear interpolation
    over the observed sample — no distributional assumption). n_obs==1
    collapses all five statistics onto the single observation. Observations
    are sorted by fiscal_year for stable rendering.
    """
    for ob in observations:
        if ob.label != label:
            raise ValueError(
                f"build_band({label!r}): 관측 라벨 불일치 {ob.label!r} "
                f"(FY{ob.fiscal_year}) — 라벨 혼합 밴드 금지."
            )
        if ob.company != company:
            raise ValueError(
                f"build_band({company!r}): 관측 회사 불일치 {ob.company!r} "
                f"(FY{ob.fiscal_year})."
            )

    obs = tuple(sorted(observations, key=lambda o: o.fiscal_year))
    exc = tuple(sorted(excluded, key=lambda e: e.fiscal_year))
    values = [o.multiple for o in obs]

    if not values:
        return HistoricalBand(
            label=label, company=company, n_obs=0, observations=(), excluded=exc
        )

    if len(values) == 1:
        v = values[0]
        b_min = p25 = med = p75 = b_max = v
    else:
        p25, med, p75 = quantiles(values, n=4, method="inclusive")
        b_min, b_max = min(values), max(values)

    return HistoricalBand(
        label=label,
        company=company,
        n_obs=len(values),
        band_min=b_min,
        p25=p25,
        median=med,
        p75=p75,
        band_max=b_max,
        observations=obs,
        excluded=exc,
    )


def percentile_rank(band: HistoricalBand, current: float) -> Optional[float]:
    """Fraction of historical observations <= current (0.0-1.0).

    None when the band has no observations. Mid-rank convention for ties
    ((less + 0.5 * equal) / n) so identical values do not read as 0% or 100%.
    """
    if band.n_obs == 0:
        return None
    values = [o.multiple for o in band.observations]
    less = sum(1 for v in values if v < current)
    equal = sum(1 for v in values if v == current)
    return (less + 0.5 * equal) / len(values)


def band_verdict(band: HistoricalBand, current: Optional[float]) -> str:
    """Korean one-line position verdict for reporting (참고용).

    "이력 부족(N=x)" below MIN_OBS_FOR_BAND — the band is shown but not
    interpreted. Otherwise the current multiple is placed against the
    historical quartiles. current=None yields "현재 배수 없음".
    """
    if band.n_obs < MIN_OBS_FOR_BAND:
        return f"이력 부족(N={band.n_obs})"
    if current is None:
        return "현재 배수 없음"
    if current < band.band_min:
        return "역사적 밴드 하단 이탈"
    if current > band.band_max:
        return "역사적 밴드 상단 이탈"
    if current <= band.p25:
        return "역사적 하위 25% 구간"
    if current >= band.p75:
        return "역사적 상위 25% 구간"
    return "역사적 중간 구간"
