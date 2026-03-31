"""AI analysis orchestrator -- 6-step valuation assistant.

1. Company identification (natural language -> corp_code)
2. Segment classification (annual report XML -> segments)
3. Peer/multiple recommendation
4. WACC draft suggestion
5. Scenario design
6. Automated research note generation
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

# ── LLM response disk cache ──
_LLM_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "llm"
_LLM_CACHE_TTL = 7 * 86400  # 7일


def _cache_key(company: str, step: str, extra: str = "") -> str:
    """Generate cache filename (company + step + extra hash)."""
    raw = f"{company}:{step}:{extra}"
    h = hashlib.md5(raw.encode()).hexdigest()[:12]
    safe_name = re.sub(r'[^\w\-]', '_', company)[:30]
    return f"{safe_name}_{step}_{h}.json"


def _get_cached(company: str, step: str, extra: str = "") -> dict | None:
    """Load LLM response from cache. Returns None if TTL expired."""
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
    """Save LLM response to cache."""
    _LLM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _LLM_CACHE_DIR / _cache_key(company, step, extra)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_json(text: str) -> dict:
    """Extract JSON from LLM response (3-stage strategy).

    1) Direct json.loads attempt
    2) Extract from code block (```json ... ```)
    3) Extract from first '{' to last '}' range
    """
    text = text.strip()

    # Stage 1: direct parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Stage 2: code block extraction
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Stage 3: first { to last } range
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last > first:
        try:
            return json.loads(text[first : last + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"JSON 파싱 실패: {text[:200]}")


def _save_analysis(company_name: str, step: str, result_data: dict, model: str):
    """Save AI analysis result to Supabase (silently ignore on failure)."""
    try:
        from db.repository import save_ai_analysis
        save_ai_analysis(company_name, step, result_data, model)
    except Exception:
        logger.debug("AI analysis DB save skipped for [%s] %s", step, company_name)


class AIAnalyst:
    """AI-powered valuation assistant analyst."""

    def __init__(self, model: str = ""):
        from .llm_client import _ANTHROPIC_DEFAULT_MODEL
        self.model = model or _ANTHROPIC_DEFAULT_MODEL

    def _ask_json(self, prompt: str, system: str, max_tokens: int) -> dict:
        """Request structured JSON response + retry once on parse failure."""
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
        """Step 1: Natural language -> company identification."""
        cached = _get_cached(user_input, "identify")
        if cached:
            return cached
        prompt = prompt_identify_company(user_input)
        result = self._ask_json(prompt, system=SYSTEM_ANALYST, max_tokens=512)
        _set_cached(user_input, "identify", result)
        _save_analysis(user_input, "identify", result, self.model)
        return result

    def classify_segments(self, company_name: str, revenue_breakdown: str) -> dict:
        """Step 2: Revenue breakdown -> segment classification."""
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
        """Step 3: Per-segment peer/multiple recommendation."""
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
        """Step 4: WACC draft."""
        cached = _get_cached(company_name, "wacc")
        if cached:
            return cached
        prompt = prompt_wacc_suggestion(company_name, de_ratio, industry)
        result = self._ask_json(prompt, system=SYSTEM_ANALYST, max_tokens=1024)
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
        """Step 5: Scenario design (multi-driver)."""
        cached = _get_cached(company_name, "scenarios", extra=valuation_method)
        if cached:
            return cached
        prompt = prompt_scenario_design(
            company_name, legal_status, key_issues, valuation_method,
        )
        result = self._ask_json(prompt, system=SYSTEM_ANALYST, max_tokens=3072)
        _set_cached(company_name, "scenarios", result, extra=valuation_method)
        _save_analysis(company_name, "scenarios", result, self.model)
        return result

    def generate_research_note(
        self,
        company_name: str,
        valuation_summary: str,
    ) -> str:
        """Step 6: Research note generation."""
        cached = _get_cached(company_name, "research_note")
        if cached:
            return cached.get("note", "")
        prompt = prompt_research_note(company_name, valuation_summary)
        note = ask(prompt, system=SYSTEM_ANALYST, model=self.model, max_tokens=4096)
        _set_cached(company_name, "research_note", {"note": note})
        _save_analysis(company_name, "research_note", {"note": note}, self.model)
        return note
