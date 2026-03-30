"""LLM 클라이언트 래퍼 — Claude API / OpenRouter 지원."""

import os
from typing import Optional

import anthropic


def get_client() -> anthropic.Anthropic:
    """Anthropic 클라이언트 생성."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
    return anthropic.Anthropic(api_key=key)


def ask(
    prompt: str,
    system: str = "",
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """단일 프롬프트 → 텍스트 응답.

    Args:
        prompt: 사용자 메시지
        system: 시스템 프롬프트
        model: 모델 ID
        max_tokens: 최대 토큰
        temperature: 온도

    Returns:
        응답 텍스트
    """
    client = get_client()
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


def ask_structured(
    prompt: str,
    system: str = "",
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
) -> str:
    """구조화된 응답 요청 (JSON 등).

    temperature=0으로 고정하여 결정론적 출력.
    """
    return ask(prompt, system=system, model=model,
               max_tokens=max_tokens, temperature=0)
