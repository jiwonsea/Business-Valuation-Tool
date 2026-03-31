"""LLM 클라이언트 래퍼 — Anthropic API / OpenRouter 지원.

우선순위:
1. OPENROUTER_API_KEY 설정 시 → OpenRouter (다양한 모델 선택 가능)
2. ANTHROPIC_API_KEY 설정 시 → Anthropic 직접 호출
3. 둘 다 없으면 → RuntimeError
"""

import json
import os
from typing import Optional

# OpenRouter 기본 모델 (무료/저가 모델로 시작, 필요 시 변경)
_OPENROUTER_DEFAULT_MODEL = "anthropic/claude-sonnet-4"
_ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-20250514"


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
    """Anthropic API 직접 호출."""
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
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
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

    resp = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=120,
    )
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
