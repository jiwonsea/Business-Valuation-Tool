"""LLM 클라이언트 래퍼 — Anthropic API / OpenRouter 지원.

우선순위:
1. OPENROUTER_API_KEY 설정 시 → OpenRouter (다양한 모델 선택 가능)
2. ANTHROPIC_API_KEY 설정 시 → Anthropic 직접 호출
3. 둘 다 없으면 → RuntimeError
"""

import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

# OpenRouter 기본 모델 (무료/저가 모델로 시작, 필요 시 변경)
_OPENROUTER_DEFAULT_MODEL = "anthropic/claude-sonnet-4"
_ANTHROPIC_DEFAULT_MODEL = "claude-haiku-4-5-20250414"


def _get_provider() -> str:
    """사용 가능한 LLM 프로바이더 판별."""
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
    """Anthropic API 직접 호출 (프롬프트 캐싱 자동 적용)."""
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
        # 프롬프트 캐싱: 동일 시스템 프롬프트 반복 시 입력 비용 90% 절감
        kwargs["system"] = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    response = client.messages.create(**kwargs)

    # Usage 로깅 — 토큰 사용량 + 캐시 적중 추적
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
    """OpenRouter API 호출 (OpenAI 호환 형식)."""
    import httpx

    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY 환경변수가 설정되지 않았습니다.")

    # Anthropic 직접 모델 ID가 넘어오면 무시 → OpenRouter 기본 모델 사용
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

    # 429 rate limit 대응: 최대 5회 재시도 (Retry-After 헤더 우선, fallback exponential)
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
    """단일 프롬프트 → 텍스트 응답. 프로바이더 자동 선택.

    Args:
        prompt: 사용자 메시지
        system: 시스템 프롬프트
        model: 모델 ID (비어있으면 프로바이더별 기본값)
        max_tokens: 최대 토큰
        temperature: 온도

    Returns:
        응답 텍스트
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
    """구조화된 응답 요청 (JSON 등).

    temperature=0으로 고정하여 결정론적 출력.
    """
    return ask(prompt, system=system, model=model,
               max_tokens=max_tokens, temperature=0)
