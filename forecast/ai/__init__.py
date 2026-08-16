"""LLM-backed extraction layer (IO).

Isolated from `engine/` (pure, deterministic) per the project rule: all LLM/HTTP
side effects live in `pipeline/` or `ai/`. Deterministic validation of the raw
extraction happens in `engine/signal_extractor.py`, not here.
"""
