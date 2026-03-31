"""LLM client wrapper -- Anthropic API / OpenRouter support.

Priority:
1. OPENROUTER_API_KEY set -> OpenRouter (various model selection)
2. ANTHROPIC_API_KEY set -> Direct Anthropic call
3. Neither set -> RuntimeError
"""

import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

# OpenRouter default model (start with free/low-cost, change as needed)
_OPENROUTER_DEFAULT_MODEL = "anthropic/claude-sonnet-4"
_ANTHROPIC_DEFAULT_MODEL = "claude-haiku-4-5-20250414"


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


def _ask_anthropic(
    prompt: str,
    system: str = "",
    model: str = _ANTHROPIC_DEFAULT_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """Direct Anthropic API call (automatic prompt caching)."""
    import anthropic

    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")

    client = anthropic.Anthropic(api_key=key)
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

    response = client.messages.create(**kwargs)

    # Usage logging -- token usage + cache hit tracking
    usage = response.usage
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
    logger.info(
        "Anthropic [%s] 입력=%d (캐시읽기=%d, 캐시생성=%d), 출력=%d",
        model, usage.input_tokens, cache_read, cache_create, usage.output_tokens,
    )

    return response.content[0].text


def _ask_openrouter(
    prompt: str,
    system: str = "",
    model: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """OpenRouter API call (OpenAI-compatible format)."""
    import httpx

    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY 환경변수가 설정되지 않았습니다.")

    # Ignore direct Anthropic model IDs -> use OpenRouter default model
    if not model or model.startswith("claude-"):
        model = os.getenv("OPENROUTER_MODEL", _OPENROUTER_DEFAULT_MODEL)

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
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    # 429 rate limit handling: up to 5 retries (Retry-After header first, fallback exponential)
    max_retries = 5
    for attempt in range(max_retries + 1):
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        if resp.status_code != 429 or attempt == max_retries:
            break
        retry_after = resp.headers.get("retry-after")
        wait = int(retry_after) if retry_after and retry_after.isdigit() else 10 * (attempt + 1)
        logger.warning("OpenRouter rate limit — %ds 후 재시도 (%d/%d)", wait, attempt + 1, max_retries)
        time.sleep(wait)

    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise RuntimeError(f"OpenRouter 에러: {data['error']}")

    return data["choices"][0]["message"]["content"]


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
        return _ask_openrouter(prompt, system, model, max_tokens, temperature)
    else:
        anthropic_model = model or _ANTHROPIC_DEFAULT_MODEL
        return _ask_anthropic(prompt, system, anthropic_model, max_tokens, temperature)


def ask_structured(
    prompt: str,
    system: str = "",
    model: str = "",
    max_tokens: int = 4096,
) -> str:
    """Request structured response (JSON, etc.).

    Fixed temperature=0 for deterministic output.
    """
    return ask(prompt, system=system, model=model,
               max_tokens=max_tokens, temperature=0)
