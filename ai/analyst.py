"""AI 분석 오케스트레이터 — 6단계 밸류에이션 보조.

1. 기업 식별 (자연어 → corp_code)
2. 부문 분류 (사보 XML → segments)
3. Peer/멀티플 추천
4. WACC 초안 제시
5. 시나리오 설계
6. 리서치 노트 자동 생성
"""

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

from .llm_client import ask, ask_structured
from .prompts import (
    SYSTEM_ANALYST,
    prompt_identify_company,
    prompt_segment_classification,
    prompt_peer_recommendation,
    prompt_wacc_suggestion,
    prompt_scenario_design,
    prompt_research_note,
)

logger = logging.getLogger(__name__)

# ── LLM 응답 디스크 캐시 ──
_LLM_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "llm"
_LLM_CACHE_TTL = 7 * 86400  # 7일


def _cache_key(company: str, step: str, extra: str = "") -> str:
    """캐시 파일명 생성 (company + step + extra 해시)."""
    raw = f"{company}:{step}:{extra}"
    h = hashlib.md5(raw.encode()).hexdigest()[:12]
    safe_name = re.sub(r'[^\w\-]', '_', company)[:30]
    return f"{safe_name}_{step}_{h}.json"


def _get_cached(company: str, step: str, extra: str = "") -> dict | None:
    """캐시에서 LLM 응답 로드. TTL 만료 시 None."""
    path = _LLM_CACHE_DIR / _cache_key(company, step, extra)
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > _LLM_CACHE_TTL:
        path.unlink(missing_ok=True)
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        logger.info("LLM 캐시 적중: %s/%s", company, step)
        return data
    except (json.JSONDecodeError, OSError):
        return None


def _set_cached(company: str, step: str, data: dict, extra: str = ""):
    """LLM 응답을 캐시에 저장."""
    _LLM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _LLM_CACHE_DIR / _cache_key(company, step, extra)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_json(text: str) -> dict:
    """LLM 응답에서 JSON 추출 (3단계 전략).

    1) 직접 json.loads 시도
    2) 코드블록(```json ... ```) 내부 추출
    3) 첫 '{' ~ 마지막 '}' 범위 추출
    """
    text = text.strip()

    # 1단계: 직접 파싱
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2단계: 코드블록 추출
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3단계: 첫 { ~ 마지막 } 범위
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last > first:
        try:
            return json.loads(text[first : last + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"JSON 파싱 실패: {text[:200]}")


def _save_analysis(company_name: str, step: str, result_data: dict, model: str):
    """AI 분석 결과를 Supabase에 저장 (실패 시 무시)."""
    try:
        from db.repository import save_ai_analysis
        save_ai_analysis(company_name, step, result_data, model)
    except Exception:
        logger.debug("AI analysis DB save skipped for [%s] %s", step, company_name)


class AIAnalyst:
    """AI 밸류에이션 보조 애널리스트."""

    def __init__(self, model: str = ""):
        from .llm_client import _ANTHROPIC_DEFAULT_MODEL
        self.model = model or _ANTHROPIC_DEFAULT_MODEL

    def _ask_json(self, prompt: str, system: str, max_tokens: int) -> dict:
        """구조화된 JSON 응답 요청 + 파싱 실패 시 1회 재시도."""
        response = ask_structured(
            prompt, system=system, model=self.model, max_tokens=max_tokens,
        )
        try:
            return _parse_json(response)
        except (json.JSONDecodeError, ValueError):
            logger.warning("JSON 파싱 실패 — 재시도 중")
            retry_prompt = prompt + "\n\n순수 JSON 객체만 출력하세요. 설명 텍스트 없이 JSON만 응답하세요."
            response = ask_structured(
                retry_prompt, system=system, model=self.model, max_tokens=max_tokens,
            )
            return _parse_json(response)

    def identify_company(self, user_input: str) -> dict:
        """Step 1: 자연어 → 기업 식별."""
        cached = _get_cached(user_input, "identify")
        if cached:
            return cached
        prompt = prompt_identify_company(user_input)
        result = self._ask_json(prompt, system=SYSTEM_ANALYST, max_tokens=512)
        _set_cached(user_input, "identify", result)
        _save_analysis(user_input, "identify", result, self.model)
        return result

    def classify_segments(self, company_name: str, revenue_breakdown: str) -> dict:
        """Step 2: 매출 구성 → 부문 분류."""
        cached = _get_cached(company_name, "classify")
        if cached:
            return cached
        prompt = prompt_segment_classification(company_name, revenue_breakdown)
        result = self._ask_json(prompt, system=SYSTEM_ANALYST, max_tokens=1024)
        _set_cached(company_name, "classify", result)
        _save_analysis(company_name, "classify", result, self.model)
        return result

    def recommend_peers(
        self,
        company_name: str,
        segment_code: str,
        segment_name: str,
        segment_description: str = "",
    ) -> dict:
        """Step 3: 부문별 Peer/멀티플 추천."""
        cached = _get_cached(company_name, "peers", extra=segment_code)
        if cached:
            return cached
        prompt = prompt_peer_recommendation(
            company_name, segment_code, segment_name, segment_description
        )
        result = self._ask_json(prompt, system=SYSTEM_ANALYST, max_tokens=1024)
        _set_cached(company_name, "peers", result, extra=segment_code)
        _save_analysis(company_name, "peers", result, self.model)
        return result

    def suggest_wacc(
        self,
        company_name: str,
        de_ratio: float,
        industry: str = "",
    ) -> dict:
        """Step 4: WACC 초안."""
        cached = _get_cached(company_name, "wacc")
        if cached:
            return cached
        prompt = prompt_wacc_suggestion(company_name, de_ratio, industry)
        result = self._ask_json(prompt, system=SYSTEM_ANALYST, max_tokens=512)
        _set_cached(company_name, "wacc", result)
        _save_analysis(company_name, "wacc", result, self.model)
        return result

    def design_scenarios(
        self,
        company_name: str,
        legal_status: str,
        key_issues: str = "",
        valuation_method: str = "dcf_primary",
    ) -> dict:
        """Step 5: 시나리오 설계 (멀티 드라이버)."""
        cached = _get_cached(company_name, "scenarios", extra=valuation_method)
        if cached:
            return cached
        prompt = prompt_scenario_design(
            company_name, legal_status, key_issues, valuation_method,
        )
        result = self._ask_json(prompt, system=SYSTEM_ANALYST, max_tokens=2048)
        _set_cached(company_name, "scenarios", result, extra=valuation_method)
        _save_analysis(company_name, "scenarios", result, self.model)
        return result

    def generate_research_note(
        self,
        company_name: str,
        valuation_summary: str,
    ) -> str:
        """Step 6: 리서치 노트 생성."""
        cached = _get_cached(company_name, "research_note")
        if cached:
            return cached.get("note", "")
        prompt = prompt_research_note(company_name, valuation_summary)
        note = ask(prompt, system=SYSTEM_ANALYST, model=self.model, max_tokens=4096)
        _set_cached(company_name, "research_note", {"note": note})
        _save_analysis(company_name, "research_note", {"note": note}, self.model)
        return note
