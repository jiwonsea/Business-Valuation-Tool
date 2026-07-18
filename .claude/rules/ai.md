---
paths: ["ai/**/*.py"]
---

# AI / LLM Gotchas & Efficiency

LLM-based segment classification, peer recommendation, scenario design (Claude Sonnet 4). Scenario driver definitions live in `_METHOD_DRIVERS` (`ai/prompts.py`) — see `engine.md` for the 3-layer driver contract.

## Circuit Breaker / Fallback

- `ApiGuard.check(provider)` must be in a dedicated `try/except ApiGuardError` block, NOT inside the same `except Exception` as the HTTP call. Mixed handling calls `record_failure()` on circuit-blocked requests, resetting the cooldown timer — circuit never recovers during a run. Pattern: `try: guard.check() / except ApiGuardError: return []` then separate `try: ...http... / except Exception: guard.record_failure()`.
- `ask()` OpenRouter fallback must catch `ApiGuardError` alongside `httpx.HTTPError`. `CircuitOpenError` is a subclass of `ApiGuardError`, not `RuntimeError` — without this, Anthropic fallback never triggers when the openrouter circuit is open (`ai/llm_client.py`).

## Prompt Cache Invalidation

- After changing AI prompts in `ai/prompts.py`, clear `.cache/llm/*_scenarios_*.json` before re-testing — cached responses won't reflect prompt changes.

## Efficiency & Quota

- **Batch LLM calls**: Use `recommend_peers_batch()` for multi-segment companies (1 call vs N segments).
- **System prompt caching**: Static reference content (driver definitions, format specs) belongs in system prompts. Anthropic ephemeral cache gives 90% input cost reduction; OpenRouter gets no cache benefit but shorter user prompts reduce retry cost.
- **News summary caching**: `summarize_key_issues()` results are disk-cached (7-day TTL) via `ai/analyst.py` cache infrastructure.
- **Target: ≤4 LLM calls/company** (classify + peers_batch + wacc + scenarios). Optionality segment detection is merged into the scenarios call — no extra quota. Daily LLM quota: 50 calls.
- **Quota safety net**: `weekly_run.py` auto-trims targets if `len(targets) * 4 > remaining_llm_quota`.

## LLM Telemetry

- E1 telemetry is observation-only and opt-in with `BVT_TELEMETRY=1`; it must not change retry, fallback, cache, or quota behavior.
- With telemetry disabled, return values, exceptions, network behavior, and persistent side effects are unchanged. Context setup and local timing calls still execute, so do not claim an identical instruction path.
- One terminal `attempt` event represents one transmitted HTTP request. Pre-send quota or circuit rejection is a separate `blocked` event.
- `attempt_no` is a step (`call_context`) sequence number spanning primary, retry, parse repair, and provider fallback. Derive retries from `(step, operation, provider)` groups, not from `max(attempt_no) - 1`.
- `pipeline/api_guard.py` is not an LLM telemetry insertion point. Retries naturally re-enter `_ask_anthropic()` or `_ask_openrouter()` and are counted there.
- Controlled runs isolate cache files under `.cache/llm/<BVT_CACHE_NS>/`. With no namespace, the legacy cache directory and cache keys stay unchanged.
- Paid measurement requires a model/attempt cost estimate and explicit user approval through `scripts/e1_measure.py`.
- `latency_ms` measures the transport call before JSONL emission. Sink locking can still increase end-to-end step wall time between attempts; telemetry reports must distinguish transport latency from workflow elapsed time.
