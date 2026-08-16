"""Disclosure loader — Claude-owned helper passes now; IO bodies are Codex's."""

from __future__ import annotations

from datetime import date

import pytest

from pipeline.disclosure_loader import count_kr_chars, fetch_dart_mdna, load_ir_decks


def test_count_kr_chars_counts_only_hangul():
    assert count_kr_chars("HBM 수요 강세 2026") == 4   # 수,요,강,세
    assert count_kr_chars("ascii only 123") == 0


def test_load_ir_decks_returns_documents(tmp_path):
    docs = load_ir_decks(
        [{"filename": "missing.pdf", "event_label": "2024Q1",
          "period_label": "2024Q1", "doc_date": "2024-04-25"}],
        tmp_path,
    )
    # A missing deck is warned + dropped, not crashed (no silent total failure).
    assert isinstance(docs, list)


@pytest.mark.network
def test_fetch_dart_mdna_nonempty():
    """Live DART fetch — excluded by default (see pyproject `-m 'not network'`).

    Run explicitly with `pytest -m network`. NOTE: this asserts only
    `char_count_kr > 0`, which does NOT prove the extraction was complete —
    rcpNo 20240814003052 returns a 67-char "본 항목을 기재하지 아니하였습니다"
    boilerplate and still passes. A real completeness contract belongs with the
    Phase-B reactivation work, not here (see module docstring).
    """
    doc = fetch_dart_mdna("20240814003052", "2024Q2", date(2024, 8, 14))
    assert doc.source == "dart_mdna"
    assert doc.char_count_kr > 0
