"""LLM client wrapper -- Anthropic API / OpenRouter support.

Priority:
1. OPENROUTER_API_KEY set -> OpenRouter (various model selection)
2. ANTHROPIC_API_KEY set -> Direct Anthropic call
3. Neither set -> RuntimeError
"""

import atexit
import logging
import os
import threading
import time

import httpx

logger = logging.getLogger(__name__)

_openrouter_client = httpx.Client(timeout=120)
atexit.register(_openrouter_client.close)

_anthropic_lock = threading.Lock()
_anthropic_client = None


def _get_anthropic_client(api_key: str):
    """Lazy singleton Anthropic client (thread-safe, reuses connection pool)."""
    global _anthropic_client
    if _anthropic_client is None:
        with _anthropic_lock:
            if _anthropic_client is None:
                import anthropic

                _anthropic_client = anthropic.Anthropic(api_key=api_key)
                atexit.register(_anthropic_client.close)
    return _anthropic_client


# OpenRouter default model (start with free/low-cost, change as needed)
_OPENROUTER_DEFAULT_MODEL = "anthropic/claude-sonnet-4"
_ANTHROPIC_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# Model tiers for mixed strategy (Haiku for routine, Sonnet for reasoning)
MODEL_LIGHT = "claude-haiku-4-5-20251001"  # classify, peers, wacc
MODEL_HEAVY = "claude-sonnet-4-6"  # scenarios, research notes

_OPENROUTER_MODEL_MAP = {
    MODEL_LIGHT: "anthropic/claude-haiku-4.5",
    MODEL_HEAVY: "anthropic/claude-sonnet-4.6",
}


def _resolve_anthropic_model(model: str) -> str:
    """Resolve a logical model tier to a direct Anthropic model ID."""
    resolved = (
        os.getenv("BVT_ANTHROPIC_MODEL_HEAVY", MODEL_HEAVY)
        if model == MODEL_HEAVY
        else model
    )
    if "/" in resolved:
        raise ValueError(f"Anthropic model ID must not contain '/': {resolved}")
    return resolved


def _resolve_openrouter_model(model: str) -> str:
    """Resolve a logical model tier to an OpenRouter provider/model slug."""
    if model == MODEL_HEAVY:
        resolved = os.getenv(
            "BVT_OPENROUTER_MODEL_HEAVY", _OPENROUTER_MODEL_MAP[MODEL_HEAVY]
        )
    else:
        resolved = _OPENROUTER_MODEL_MAP.get(model, model)
    if "/" not in resolved:
        raise ValueError(f"OpenRouter model slug must contain '/': {resolved}")
    return resolved


def _get_provider() -> str:
    """Determine the available LLM provider."""
    if os.getenv("OPENROUTER_API_KEY"):
        return "openrouter"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    raise RuntimeError(
        "LLM API 키가 설정되지 않았습니다. "
        "OPENROUTER_API_KEY 또는 ANTHROPIC_API_KEY를 .env에 추가하세요."
    )


from pipeline.api_guard import (
    ApiGuardError,
    CircuitOpenError,
    QuotaExceededError,
    api_guard,
)
from .telemetry import emit, emit_blocked, fallback, is_fallback, next_attempt_no


def _error_outcome(exc: Exception) -> str:
    return "timeout" if isinstance(exc, httpx.TimeoutException) else "http_error"


def _blocked_outcome(exc: ApiGuardError) -> str:
    if isinstance(exc, CircuitOpenError):
        return "circuit_open"
    if isinstance(exc, QuotaExceededError):
        return "quota_exceeded"
    logger.warning("Unknown ApiGuardError subtype: %s", type(exc).__name__)
    return "unknown"


@api_guard("anthropic")
def _ask_anthropic(
    prompt: str,
    system: str = "",
    model: str = _ANTHROPIC_DEFAULT_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """Direct Anthropic API call (automatic prompt caching)."""

    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")

    model = _resolve_anthropic_model(model)
    client = _get_anthropic_client(key)
    messages = [{"role": "user", "content": prompt}]

    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if system:
        # Prompt caching: 90% input cost reduction when reusing system prompts
        kwargs["system"] = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    attempt_no = next_attempt_no()
    started = time.perf_counter()
    try:
        response = client.messages.create(**kwargs)
    except Exception as exc:
        emit(
            "attempt",
            provider="anthropic",
            model=model,
            attempt_no=attempt_no,
            is_fallback=is_fallback(),
            input_tokens=None,
            output_tokens=None,
            cache_read_tokens=None,
            latency_ms=round((time.perf_counter() - started) * 1000),
            outcome=_error_outcome(exc),
            est_cost_usd=None,
        )
        raise

    # Usage logging -- token usage + cache hit tracking
    usage = response.usage
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
    logger.info(
        "Anthropic [%s] 입력=%d (캐시읽기=%d, 캐시생성=%d), 출력=%d",
        model,
        usage.input_tokens,
        cache_read,
        cache_create,
        usage.output_tokens,
    )
    emit(
        "attempt",
        provider="anthropic",
        model=model,
        attempt_no=attempt_no,
        is_fallback=is_fallback(),
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=cache_read,
        latency_ms=round((time.perf_counter() - started) * 1000),
        outcome="success",
        est_cost_usd=None,
    )
    emit(
        "llm_response_meta",
        provider="anthropic",
        model=model,
        completion_tokens=usage.output_tokens,
        stop_reason=getattr(response, "stop_reason", None),
    )

    return response.content[0].text


@api_guard("openrouter")
def _ask_openrouter(
    prompt: str,
    system: str = "",
    model: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.3,
    json_mode: bool = False,
) -> str:
    """OpenRouter API call (OpenAI-compatible format)."""

    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY 환경변수가 설정되지 않았습니다.")

    if not model:
        model = os.getenv("OPENROUTER_MODEL", _OPENROUTER_DEFAULT_MODEL)
    model = _resolve_openrouter_model(model)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    attempt_no = next_attempt_no()
    started = time.perf_counter()
    try:
        resp = _openrouter_client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
        )
    except Exception as exc:
        emit(
            "attempt",
            provider="openrouter",
            model=model,
            attempt_no=attempt_no,
            is_fallback=is_fallback(),
            input_tokens=None,
            output_tokens=None,
            cache_read_tokens=None,
            latency_ms=round((time.perf_counter() - started) * 1000),
            outcome=_error_outcome(exc),
            est_cost_usd=None,
        )
        raise
    if resp.status_code >= 400:
        logger.error("OpenRouter %d [%s]: %s", resp.status_code, model, resp.text[:500])
    try:
        resp.raise_for_status()
    except Exception as exc:
        emit(
            "attempt",
            provider="openrouter",
            model=model,
            attempt_no=attempt_no,
            is_fallback=is_fallback(),
            input_tokens=None,
            output_tokens=None,
            cache_read_tokens=None,
            latency_ms=round((time.perf_counter() - started) * 1000),
            outcome=_error_outcome(exc),
            est_cost_usd=None,
        )
        raise
    try:
        data = resp.json()
    except Exception:
        emit(
            "attempt",
            provider="openrouter",
            model=model,
            attempt_no=attempt_no,
            is_fallback=is_fallback(),
            input_tokens=None,
            output_tokens=None,
            cache_read_tokens=None,
            latency_ms=round((time.perf_counter() - started) * 1000),
            outcome="parse_error",
            est_cost_usd=None,
        )
        raise

    if "error" in data:
        emit(
            "attempt", provider="openrouter", model=model, attempt_no=attempt_no,
            is_fallback=is_fallback(), input_tokens=None, output_tokens=None,
            cache_read_tokens=None,
            latency_ms=round((time.perf_counter() - started) * 1000),
            outcome="http_error", est_cost_usd=None,
        )
        raise RuntimeError(f"OpenRouter error: {data['error']}")

    choices = data.get("choices")
    if not choices:
        emit(
            "attempt", provider="openrouter", model=model, attempt_no=attempt_no,
            is_fallback=is_fallback(), input_tokens=None, output_tokens=None,
            cache_read_tokens=None,
            latency_ms=round((time.perf_counter() - started) * 1000),
            outcome="parse_error", est_cost_usd=None,
        )
        raise RuntimeError(f"OpenRouter returned empty choices: {data}")

    usage = data.get("usage", {})
    emit(
        "attempt",
        provider="openrouter",
        model=model,
        attempt_no=attempt_no,
        is_fallback=is_fallback(),
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
        cache_read_tokens=None,
        latency_ms=round((time.perf_counter() - started) * 1000),
        outcome="success",
        est_cost_usd=None,
    )
    emit(
        "llm_response_meta",
        provider="openrouter",
        model=model,
        completion_tokens=usage.get("completion_tokens"),
        stop_reason=choices[0].get("finish_reason"),
    )
    return choices[0]["message"]["content"]


def ask(
    prompt: str,
    system: str = "",
    model: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """Single prompt -> text response. Auto-selects provider.

    Args:
        prompt: User message
        system: System prompt
        model: Model ID (uses provider default if empty)
        max_tokens: Maximum tokens
        temperature: Temperature

    Returns:
        Response text
    """
    provider = _get_provider()

    if provider == "openrouter":
        try:
            return _ask_openrouter(prompt, system, model, max_tokens, temperature)
        except (
            httpx.HTTPError,
            httpx.TimeoutException,
            RuntimeError,
            ApiGuardError,
        ) as e:
            if isinstance(e, ApiGuardError):
                emit_blocked("openrouter", model or _OPENROUTER_DEFAULT_MODEL, _blocked_outcome(e))
            # Fallback to Anthropic when OpenRouter fails or circuit is open
            if os.getenv("ANTHROPIC_API_KEY"):
                logger.warning("OpenRouter failed (%s) — falling back to Anthropic", e)
                anthropic_model = model or _ANTHROPIC_DEFAULT_MODEL
                try:
                    with fallback():
                        return _ask_anthropic(
                            prompt, system, anthropic_model, max_tokens, temperature
                        )
                except ApiGuardError as fallback_err:
                    emit_blocked("anthropic", anthropic_model, _blocked_outcome(fallback_err))
                    raise fallback_err from e
                except Exception as fallback_err:
                    raise fallback_err from e
            raise
    else:
        anthropic_model = model or _ANTHROPIC_DEFAULT_MODEL
        try:
            return _ask_anthropic(prompt, system, anthropic_model, max_tokens, temperature)
        except ApiGuardError as exc:
            emit_blocked("anthropic", anthropic_model, _blocked_outcome(exc))
            raise


def ask_structured(
    prompt: str,
    system: str = "",
    model: str = "",
    max_tokens: int = 4096,
) -> str:
    """Request structured response (JSON, etc.).

    Fixed temperature=0 for deterministic output.
    Uses response_format=json_object on OpenRouter to prevent markdown wrapping and truncation.
    """
    provider = _get_provider()
    if provider == "openrouter":
        try:
            return _ask_openrouter(
                prompt, system, model, max_tokens, temperature=0, json_mode=True
            )
        except (httpx.HTTPError, httpx.TimeoutException, RuntimeError, ApiGuardError) as e:
            if isinstance(e, ApiGuardError):
                emit_blocked("openrouter", model or _OPENROUTER_DEFAULT_MODEL, _blocked_outcome(e))
            if os.getenv("ANTHROPIC_API_KEY"):
                logger.warning("OpenRouter failed (%s) — falling back to Anthropic", e)
                anthropic_model = model or _ANTHROPIC_DEFAULT_MODEL
                try:
                    with fallback():
                        return _ask_anthropic(
                            prompt, system, anthropic_model, max_tokens, temperature=0
                        )
                except ApiGuardError as fallback_err:
                    emit_blocked("anthropic", anthropic_model, _blocked_outcome(fallback_err))
                    raise fallback_err from e
            raise
    anthropic_model = model or _ANTHROPIC_DEFAULT_MODEL
    try:
        return _ask_anthropic(prompt, system, anthropic_model, max_tokens, temperature=0)
    except ApiGuardError as exc:
        emit_blocked("anthropic", anthropic_model, _blocked_outcome(exc))
        raise
