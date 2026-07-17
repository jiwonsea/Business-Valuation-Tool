"""Collect comparable peer beta observations during profile curation."""

from __future__ import annotations

from datetime import date

from engine.peer_beta import judge_company_beta
from pipeline.beta_observation import collect_beta_observation
from schemas.models import PeerBetaEntry, PeerBetaSnapshot


def collect_peer_beta_snapshot(
    candidates: list[dict],
    analysis_date: date,
    *,
    company_raw_bl: float,
    benchmark: str,
    frequency: str,
    calculation_method: str,
) -> PeerBetaSnapshot:
    entries: list[PeerBetaEntry] = []
    for candidate in candidates:
        name = str(candidate["name"])
        ticker = candidate.get("ticker")
        segment_code = candidate.get("segment_code")
        reason = None
        if candidate.get("entity_type", "listed_company") != "listed_company":
            reason = "not_independent_listed_company"
        elif not ticker:
            reason = "missing_ticker"
        elif candidate.get("market") != "US":
            reason = "benchmark_mismatch"
        elif not candidate.get("core_business_match", False):
            reason = "industry_mismatch"
        elif not candidate.get("qualification_reason"):
            reason = "missing_industry_qualification_basis"
        if reason:
            entries.append(PeerBetaEntry(
                name=name, ticker=ticker, segment_code=segment_code,
                qualified=False, exclusion_reason=reason,
            ))
            continue
        try:
            observation, digest, _ = collect_beta_observation(
                str(ticker), "US", analysis_date, benchmark=benchmark
            )
            entries.append(PeerBetaEntry(
                name=name,
                ticker=str(ticker),
                segment_code=segment_code,
                qualified=True,
                qualification_reason=str(candidate["qualification_reason"]),
                raw_levered_beta=observation.raw_levered_beta,
                blume_adjusted=observation.blume(),
                window_start=observation.window_start,
                window_end=observation.window_end,
                frequency=observation.frequency,
                benchmark=observation.benchmark,
                observation_count=observation.observation_count,
                calculation_method=observation.calculation_method,
                source_hash=digest,
            ))
        except Exception as exc:
            entries.append(PeerBetaEntry(
                name=name, ticker=str(ticker), segment_code=segment_code,
                qualified=False,
                exclusion_reason=f"observation_failed:{type(exc).__name__}",
            ))
    judgement = judge_company_beta(
        company_raw_bl,
        entries,
        benchmark=benchmark,
        frequency=frequency,
        calculation_method=calculation_method,
    )
    return PeerBetaSnapshot(
        as_of=analysis_date,
        candidates=entries,
        judgement=judgement,
    )
