"""AI 분석 오케스트레이터 — 6단계 밸류에이션 보조.

1. 기업 식별 (자연어 → corp_code)
2. 부문 분류 (사보 XML → segments)
3. Peer/멀티플 추천
4. WACC 초안 제시
5. 시나리오 설계
6. 리서치 노트 자동 생성
"""

import json
import logging
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


def _parse_json(text: str) -> dict:
    """LLM 응답에서 JSON 추출."""
    # 코드블록 제거
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


def _save_analysis(company_name: str, step: str, result_data: dict, model: str):
    """AI 분석 결과를 Supabase에 저장 (실패 시 무시)."""
    try:
        from db.repository import save_ai_analysis
        save_ai_analysis(company_name, step, result_data, model)
    except Exception:
        logger.debug("AI analysis DB save skipped for [%s] %s", step, company_name)


class AIAnalyst:
    """AI 밸류에이션 보조 애널리스트."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model

    def identify_company(self, user_input: str) -> dict:
        """Step 1: 자연어 → 기업 식별."""
        prompt = prompt_identify_company(user_input)
        response = ask_structured(prompt, system=SYSTEM_ANALYST, model=self.model)
        result = _parse_json(response)
        _save_analysis(user_input, "identify", result, self.model)
        return result

    def classify_segments(self, company_name: str, revenue_breakdown: str) -> dict:
        """Step 2: 매출 구성 → 부문 분류."""
        prompt = prompt_segment_classification(company_name, revenue_breakdown)
        response = ask_structured(prompt, system=SYSTEM_ANALYST, model=self.model)
        result = _parse_json(response)
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
        prompt = prompt_peer_recommendation(
            company_name, segment_code, segment_name, segment_description
        )
        response = ask_structured(prompt, system=SYSTEM_ANALYST, model=self.model)
        result = _parse_json(response)
        _save_analysis(company_name, "peers", result, self.model)
        return result

    def suggest_wacc(
        self,
        company_name: str,
        de_ratio: float,
        industry: str = "",
    ) -> dict:
        """Step 4: WACC 초안."""
        prompt = prompt_wacc_suggestion(company_name, de_ratio, industry)
        response = ask_structured(prompt, system=SYSTEM_ANALYST, model=self.model)
        result = _parse_json(response)
        _save_analysis(company_name, "wacc", result, self.model)
        return result

    def design_scenarios(
        self,
        company_name: str,
        legal_status: str,
        key_issues: str = "",
    ) -> dict:
        """Step 5: 시나리오 설계."""
        prompt = prompt_scenario_design(company_name, legal_status, key_issues)
        response = ask_structured(prompt, system=SYSTEM_ANALYST, model=self.model)
        result = _parse_json(response)
        _save_analysis(company_name, "scenarios", result, self.model)
        return result

    def generate_research_note(
        self,
        company_name: str,
        valuation_summary: str,
    ) -> str:
        """Step 6: 리서치 노트 생성."""
        prompt = prompt_research_note(company_name, valuation_summary)
        note = ask(prompt, system=SYSTEM_ANALYST, model=self.model, max_tokens=8192)
        _save_analysis(company_name, "research_note", {"note": note}, self.model)
        return note
