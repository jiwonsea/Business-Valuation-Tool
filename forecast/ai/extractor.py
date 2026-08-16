"""Anthropic Claude Haiku 4.5 structured-extraction orchestration (IO).

Determinism contract (Claude-owned, do not weaken):
  - temperature 0.
  - Response disk cache keyed by sha256(model_id + prompt_version + document text).
    Same input never re-hits the API; a cache hit is logged so reruns are visibly
    free and reproducible.
  - The system prompt is sent with cache_control so the Anthropic prompt cache
    discounts the stable instructions across documents.

The actual Anthropic API call (`_call_anthropic`) is the seam for Codex to fill.
Everything around it (cache key, read/write, JSON parse boundary) is fixed here.

SSL: the anthropic SDK uses httpx, which fails on non-ASCII home paths just like
the DART/yfinance clients. `ensure_ssl_env()` must run before importing anthropic.

STATUS: DORMANT (2026-07-31). Reached only through cli.py's Phase-B modes, which
exit early unless a profile carries a `signal_layer` section; none has since
4ebeb7c (2026-07-10). reports/.cache/signal_*.json is empty, i.e. this extractor
has never fed a shipped report. Input completeness is NOT verified upstream
(see pipeline/disclosure_loader.py STATUS) — a half-empty document would be
extracted and cached without error. Do not reactivate without the completeness
contract described there.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

from pipeline._ssl_setup import ensure_ssl_env
from schemas.models import DisclosureDocument
from ai.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_message

ensure_ssl_env()

logger = logging.getLogger(__name__)

MODEL_ID = "claude-haiku-4-5-20251001"
CACHE_DIR = Path("reports/.cache")
MAX_TOKENS = 1536


def _cache_key(model_id: str, prompt_version: str, raw_text: str) -> str:
    """Stable hash identifying one extraction request."""
    payload = f"{model_id}\x00{prompt_version}\x00{raw_text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"signal_{key}.json"


def extract_signal(
    document: DisclosureDocument,
    topic_taxonomy: list[str] | None = None,
    use_cache: bool = True,
) -> dict:
    """Extract the raw structured signal for one disclosure document.

    Returns the parsed JSON object matching ai.prompts.OUTPUT_SCHEMA_HINT. The raw
    dict is intentionally NOT validated here — engine.signal_extractor performs the
    deterministic validation/normalization into an ExtractedSignal.

    Args:
        document: The disclosure/IR document (untrusted text in user turn only).
        topic_taxonomy: Optional candidate-topic hint from the profile.
        use_cache: If True and a cached extraction exists for this exact input,
            return it without calling the API.

    Returns:
        Raw extraction dict: {"topics": [...], "guidance_tone": ..., "surprise_candidates": [...]}.

    Raises:
        RuntimeError: If ANTHROPIC_API_KEY is unset and no cache hit is available.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(MODEL_ID, PROMPT_VERSION, document.raw_text)
    cache_path = _cache_path(key)
    if use_cache and cache_path.exists():
        logger.info("signal cache hit: %s (%s)", document.period_label, cache_path.name)
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY env var is required for live extraction "
            "(no cache hit for this document)"
        )

    user_message = build_user_message(
        document.raw_text,
        document.period_label,
        document.source,
        topic_taxonomy,
    )
    raw = _call_anthropic(SYSTEM_PROMPT, user_message)

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    logger.info("signal extracted + cached: %s", document.period_label)
    return raw


def _call_anthropic(system_prompt: str, user_message: str) -> dict:
    """Call Claude Haiku 4.5 and return the parsed JSON extraction.

    Codex implements this:
      1. `import anthropic` (after ensure_ssl_env, already run at module import).
      2. client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env.
      3. messages.create(
             model=MODEL_ID, max_tokens=MAX_TOKENS, temperature=0,
             system=[{"type": "text", "text": system_prompt,
                      "cache_control": {"type": "ephemeral"}}],
             messages=[{"role": "user", "content": user_message}],
         )
      4. Parse the text block as JSON (strip stray code fences defensively) and
         return the dict. Raise ValueError on unparseable output — do NOT silently
         return an empty/partial dict (silent-failure rule from Phase A).

    Args:
        system_prompt: Stable extraction instructions (prompt-cached).
        user_message: User turn wrapping the untrusted document as data.

    Returns:
        Parsed extraction dict.

    Raises:
        ValueError: If the model output is not valid JSON.
    """
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=MAX_TOKENS,
        temperature=0,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    text_parts: list[str] = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(getattr(block, "text", ""))
    text = "\n".join(text_parts).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Anthropic output was not valid JSON: {text[:200]!r}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Anthropic output must be a JSON object")
    return parsed
