"""Forward call-brief builder (pure).

Turns the most recent ExtractedSignal plus the live consensus dispersion into a
CallBrief: which topics to watch, likely Q&A, where analysts disagree, and a
predicted consensus-revision direction. No IO, no LLM.

The brief's `interpretation` is left empty by design — the analyst writes the
narrative read, exactly like ConsensusGap.interpretation.
"""

from __future__ import annotations

from datetime import date
import math

from schemas.models import CallBrief, ConsensusRecord, ExtractedSignal


def _qna_for_topic(topic: str) -> str:
    lowered = topic.casefold()
    if "hbm" in lowered:
        return f"{topic}: HBM capacity/yield assumptions versus consensus?"
    if "dram" in lowered:
        return f"{topic}: DRAM pricing recovery pace and sustainability?"
    if "nand" in lowered:
        return f"{topic}: NAND supply-demand improvement and margin impact?"
    if "capex" in lowered:
        return f"{topic}: capex timing, mix, and return threshold?"
    return f"{topic}: key assumption gap versus current consensus?"


def _wide_spread_flag(label: str, values: list[float | None]) -> str | None:
    clean = [float(value) for value in values if value is not None and not math.isnan(float(value))]
    if not clean:
        return f"{label}: consensus unavailable"
    if len(clean) < 2:
        return None
    average = sum(clean) / len(clean)
    if average == 0:
        return None
    spread = (max(clean) - min(clean)) / abs(average)
    if spread >= 0.20:
        return f"{label}: wide analyst dispersion ({spread:.1%})"
    return None


def build_call_brief(
    signal: ExtractedSignal,
    consensus: ConsensusRecord,
    target_event_label: str,
    as_of: date,
    top_n_topics: int = 5,
) -> CallBrief:
    """Assemble the forward call-brief from a signal + consensus dispersion.

    Deterministic rules (Codex implements, see HANDOFF_phase_b.md §call-brief):
      - top_topics = signal.topics[:top_n_topics] (already salience-sorted).
      - expected_qna: derive one prompt per high-salience topic and per
        surprise_candidate (template strings, no LLM) — e.g. for a topic
        "HBM capacity": "HBM 캐파/수율 가이던스가 컨센 대비 어디인가?".
      - dispersion_flags: for each period in consensus, flag wide analyst spread
        using (high-low)/|avg| when low/high present, or note "분기 컨센 부재"
        when missing. Also surface the standing yfinance .KS reliability caveat
        from consensus.notes (defect 6) so the brief never implies the consensus
        numbers are trustworthy.
      - predicted_revision_direction: from signal.guidance_tone
        (up/flat/down -> up/flat/down), "n_a" if signal is empty.
      - confidence: simple function of top-topic salience (bounded 0..1).
      - interpretation: "" (user fills).

    Args:
        signal: Latest ExtractedSignal (typically from DART MD&A for the forward view).
        consensus: Live consensus snapshot (dispersion + reliability notes).
        target_event_label: Upcoming event the brief is for, e.g. "2026Q2".
        as_of: Brief generation date.
        top_n_topics: How many topics to surface.

    Returns:
        CallBrief with empty interpretation.

    """
    top_topics = signal.topics[:top_n_topics] if signal else []

    expected_qna = [_qna_for_topic(topic.topic) for topic in top_topics if topic.salience >= 0.5]
    expected_qna.extend(
        f"{candidate}: consensus assumption check?"
        for candidate in signal.surprise_candidates
        if str(candidate).strip()
    )

    dispersion_flags: list[str] = []
    if not consensus.revenue_estimate_quarterly and not consensus.eps_estimate_quarterly:
        dispersion_flags.append("Quarterly consensus unavailable")
    for period in sorted(set(consensus.revenue_estimate_quarterly) | set(consensus.eps_estimate_quarterly)):
        revenue = consensus.revenue_estimate_quarterly.get(period)
        eps = consensus.eps_estimate_quarterly.get(period)
        if revenue is None and eps is None:
            dispersion_flags.append(f"{period}: quarterly consensus unavailable")

    raw = consensus.model_extra or {}
    for metric_name, values_by_period in (
        ("revenue", raw.get("revenue_estimate_quarterly_spread", {})),
        ("eps", raw.get("eps_estimate_quarterly_spread", {})),
    ):
        if isinstance(values_by_period, dict):
            for period, values in values_by_period.items():
                if isinstance(values, dict):
                    flag = _wide_spread_flag(
                        f"{period} {metric_name}",
                        [values.get("low"), values.get("high"), values.get("avg")],
                    )
                    if flag:
                        dispersion_flags.append(flag)

    dispersion_flags.extend(consensus.notes)

    top3 = top_topics[:3]
    confidence = sum(topic.salience for topic in top3) / len(top3) if top3 else 0.0
    confidence = max(0.0, min(1.0, confidence))

    return CallBrief(
        as_of=as_of,
        target_event_label=target_event_label,
        top_topics=top_topics,
        expected_qna=expected_qna,
        dispersion_flags=dispersion_flags,
        predicted_revision_direction=signal.guidance_tone if signal else "n_a",
        confidence=confidence,
        interpretation="",
    )
