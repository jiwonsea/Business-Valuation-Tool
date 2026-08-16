"""ai.extractor — reproducibility contract (cache key) is Claude-owned + tested now.

The Anthropic call itself (_call_anthropic) is Codex's; not exercised here.
"""

from __future__ import annotations

from ai.extractor import MODEL_ID, _cache_key
from ai.prompts import PROMPT_VERSION


def test_cache_key_is_deterministic_and_text_sensitive():
    a = _cache_key(MODEL_ID, PROMPT_VERSION, "HBM 수요 강세")
    b = _cache_key(MODEL_ID, PROMPT_VERSION, "HBM 수요 강세")
    c = _cache_key(MODEL_ID, PROMPT_VERSION, "DRAM 가격 약세")
    assert a == b          # same input -> same key (reproducible reruns)
    assert a != c          # different document -> different key
    assert len(a) == 64    # sha256 hex


def test_cache_key_changes_with_prompt_version():
    assert _cache_key(MODEL_ID, "v1", "x") != _cache_key(MODEL_ID, "v2", "x")
