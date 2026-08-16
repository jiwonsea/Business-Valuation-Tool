"""Signal extractor deterministic validation/normalization tests."""

from __future__ import annotations

from datetime import date

import pytest

from engine.signal_extractor import TONE_TO_SIGN, build_extracted_signal, signal_score, tone_to_sign
from schemas.models import DisclosureDocument, ExtractedSignal, TopicEmphasis


def _doc() -> DisclosureDocument:
    return DisclosureDocument(
        source="ir_deck",
        doc_date=date(2025, 1, 23),
        period_label="2024Q4",
        raw_text="HBM update, DRAM pricing.",
        char_count_kr=0,
    )


def test_tone_to_sign_mapping():
    assert tone_to_sign("up") == 1
    assert tone_to_sign("flat") == 0
    assert tone_to_sign("down") == -1
    assert TONE_TO_SIGN == {"up": 1, "flat": 0, "down": -1}


def test_extracted_signal_schema_roundtrip():
    sig = ExtractedSignal(
        period_label="2024Q4",
        source="ir_deck",
        topics=[TopicEmphasis(topic="HBM", salience=0.8, polarity="positive")],
        guidance_tone="up",
        surprise_candidates=["HBM"],
        extracted_at=date(2025, 1, 23),
        model_id="fixture",
    )
    assert ExtractedSignal.model_validate(sig.model_dump()) == sig


def test_build_validates_and_sorts_topics():
    raw = {
        "topics": [
            {"topic": "DRAM", "salience": 0.4, "polarity": "positive", "evidence_quote": ""},
            {"topic": "HBM", "salience": 1.5, "polarity": "positive", "evidence_quote": ""},
            {"topic": "HBM", "salience": 0.9, "polarity": "positive", "evidence_quote": ""},
        ],
        "guidance_tone": "up",
        "surprise_candidates": ["HBM"],
    }
    sig = build_extracted_signal(raw, _doc(), "fixture", date(2025, 1, 23))
    assert [t.topic for t in sig.topics][0] == "HBM"
    assert sig.topics[0].salience == 1.0
    assert len([t for t in sig.topics if t.topic == "HBM"]) == 1
    assert sig.period_label == "2024Q4"


def test_build_rejects_bad_tone():
    raw = {"topics": [], "guidance_tone": "sideways", "surprise_candidates": []}
    with pytest.raises(ValueError):
        build_extracted_signal(raw, _doc(), "fixture", date(2025, 1, 23))


def test_signal_score_sign_follows_tone():
    down = ExtractedSignal(
        period_label="2025Q1",
        source="ir_deck",
        topics=[TopicEmphasis(topic="DRAM", salience=0.7, polarity="negative")],
        guidance_tone="down",
        surprise_candidates=[],
        extracted_at=date(2025, 4, 24),
        model_id="fixture",
    )
    assert signal_score(down) < 0
