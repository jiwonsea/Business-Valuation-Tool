"""Call-brief builder tests."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from engine.signal_extractor import build_extracted_signal
from engine.signal_predictor import build_call_brief
from schemas.models import ConsensusRecord, DisclosureDocument

FIXTURES = Path(__file__).parent / "fixtures"


def _signal():
    with open(FIXTURES / "call_brief_fixture.json", encoding="utf-8") as f:
        fx = json.load(f)
    doc = DisclosureDocument.model_validate(fx["document"])
    return build_extracted_signal(fx["extraction"], doc, "fixture", date(2026, 5, 15))


def _consensus():
    return ConsensusRecord(
        ticker="000660.KS",
        as_of=date(2026, 5, 15),
        revenue_estimate_quarterly={"2026Q2": 30000.0},
        eps_estimate_quarterly={"2026Q2": 9000.0},
        revenue_estimate_annual={2026: 120000.0},
        eps_estimate_annual={2026: 35000.0},
        notes=["yfinance .KS consensus unreliable: implied net margin >60%"],
    )


def test_call_brief_interpretation_blank_and_tone_propagates():
    brief = build_call_brief(_signal(), _consensus(), "2026Q2", date(2026, 5, 15))
    assert brief.interpretation == ""
    assert brief.predicted_revision_direction == "up"
    assert brief.top_topics
    assert brief.target_event_label == "2026Q2"


def test_call_brief_surfaces_consensus_unreliability():
    brief = build_call_brief(_signal(), _consensus(), "2026Q2", date(2026, 5, 15))
    assert any("unreliable" in flag.lower() for flag in brief.dispersion_flags)
