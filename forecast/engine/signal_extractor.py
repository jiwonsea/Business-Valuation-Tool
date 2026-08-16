"""Deterministic validation/normalization of a raw LLM extraction (pure).

Boundary rule: ai/extractor.py does the (non-deterministic, IO) LLM call; this
module turns its raw dict into a validated ExtractedSignal with NO IO and NO
LLM. Keeping validation here (not in ai/) preserves engine purity and makes the
signal layer unit-testable without an API key.

The tone->sign mapping is fixed here so the predictor and backtest agree.
"""

from __future__ import annotations

from datetime import date

from schemas.models import DisclosureDocument, ExtractedSignal, SignalTone, TopicEmphasis

TONE_TO_SIGN: dict[str, int] = {"up": 1, "flat": 0, "down": -1}
_VALID_POLARITY = {"positive", "neutral", "negative"}


def tone_to_sign(tone: SignalTone) -> int:
    """Map guidance tone to a signed prediction (+1 up / 0 flat / -1 down)."""
    return TONE_TO_SIGN[tone]


def signal_score(signal: ExtractedSignal) -> float:
    """Continuous signal strength for IC: tone sign weighted by topic salience.

    Defined as tone_sign * mean(salience of positive/negative topics). Pure and
    deterministic so the same ExtractedSignal always yields the same score.
    Codex implements per HANDOFF_phase_b.md §signal-score.

    """
    signed_saliences = [
        topic.salience
        for topic in signal.topics
        if topic.polarity in ("positive", "negative")
    ]
    if signed_saliences:
        magnitude = sum(signed_saliences) / len(signed_saliences)
    elif signal.topics:
        magnitude = sum(topic.salience for topic in signal.topics) / len(signal.topics)
    else:
        magnitude = 0.0
    return tone_to_sign(signal.guidance_tone) * magnitude


def build_extracted_signal(
    raw: dict,
    document: DisclosureDocument,
    model_id: str,
    extracted_at: date,
) -> ExtractedSignal:
    """Validate + normalize a raw extraction dict into an ExtractedSignal.

    Deterministic rules (Codex implements, see HANDOFF_phase_b.md §validation):
      - Required keys: "topics", "guidance_tone", "surprise_candidates".
      - guidance_tone must be one of up/flat/down (else ValueError — no silent default).
      - Each topic: clamp salience to [0,1]; polarity in {positive,neutral,negative}
        (else ValueError); drop topics with empty `topic` string.
      - Deduplicate topics by lowercased topic text, keeping the max salience.
      - Sort topics by salience descending.
      - Carry period_label/source from `document` (provenance from the loader,
        not from the model — the model never sets its own provenance).

    Args:
        raw: Parsed dict from ai.extractor.extract_signal.
        document: Source document (provenance + period).
        model_id: e.g. "claude-haiku-4-5-20251001" (recorded for auditability).
        extracted_at: Date the extraction was produced.

    Returns:
        Validated ExtractedSignal.

    Raises:
        ValueError: On malformed/missing fields.
    """
    if not isinstance(raw, dict):
        raise ValueError("raw extraction must be a dict")
    required = {"topics", "guidance_tone", "surprise_candidates"}
    missing = required - set(raw)
    if missing:
        raise ValueError(f"raw extraction missing required keys: {sorted(missing)}")

    guidance_tone = raw["guidance_tone"]
    if guidance_tone not in TONE_TO_SIGN:
        raise ValueError(f"invalid guidance_tone: {guidance_tone!r}")

    raw_topics = raw["topics"]
    if not isinstance(raw_topics, list):
        raise ValueError("topics must be a list")

    deduped: dict[str, TopicEmphasis] = {}
    for item in raw_topics:
        if not isinstance(item, dict):
            raise ValueError("each topic must be a dict")
        topic_text = str(item.get("topic", "")).strip()
        if not topic_text:
            continue
        polarity = item.get("polarity")
        if polarity not in _VALID_POLARITY:
            raise ValueError(f"invalid polarity for topic {topic_text!r}: {polarity!r}")
        try:
            salience = float(item.get("salience", 0.0))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid salience for topic {topic_text!r}") from exc
        salience = max(0.0, min(1.0, salience))
        topic = TopicEmphasis(
            topic=topic_text,
            salience=salience,
            polarity=polarity,
            evidence_quote=str(item.get("evidence_quote", "") or ""),
        )
        key = topic_text.casefold()
        current = deduped.get(key)
        if current is None or topic.salience > current.salience:
            deduped[key] = topic

    surprise_candidates = raw["surprise_candidates"]
    if not isinstance(surprise_candidates, list):
        raise ValueError("surprise_candidates must be a list")

    return ExtractedSignal(
        period_label=document.period_label,
        source=document.source,
        topics=sorted(deduped.values(), key=lambda topic: topic.salience, reverse=True),
        guidance_tone=guidance_tone,
        surprise_candidates=[
            str(candidate).strip()
            for candidate in surprise_candidates
            if str(candidate).strip()
        ],
        extracted_at=extracted_at,
        model_id=model_id,
    )
