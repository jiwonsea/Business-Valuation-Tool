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
from typing import Callable

from .llm_client import ask, ask_structured, MODEL_LIGHT, MODEL_HEAVY
from .prompts import (
    SYSTEM_ANALYST,
    SYSTEM_ANALYST_DRIVERS,
    prompt_identify_company,
    prompt_segment_classification,
    prompt_peer_recommendation,
    prompt_peer_recommendation_batch,
    prompt_wacc_suggestion,
    prompt_scenario_design,
    prompt_scenario_classify,
    prompt_scenario_refine,
    prompt_research_note,
)

logger = logging.getLogger(__name__)

# ── Optionality pre-screen (no LLM cost) ──
_OPTIONALITY_KEYWORDS = [
    "autonomous", "fsd", "full self-driving", "robotaxi", "humanoid", "optimus",
    "robot", "biotech", "drug pipeline", "clinical trial", "phase 3", "phase 2",
    "space", "fusion", "ai platform", "self-driving", "waymo", "generative ai",
    "autonomous vehicle", "large language model", "foundation model",
]


def _has_optionality_trigger(
    company_name: str,
    industry: str,
    news: str,
    ev_rev_multiple: float = 0.0,
) -> bool:
    """Rule-based pre-screen — returns True if optionality segment generation should be attempted."""
    text = f"{company_name} {industry} {news}".lower()
    return (
        any(kw in text for kw in _OPTIONALITY_KEYWORDS)
        or ev_rev_multiple > 10.0
    )


# ── LLM response disk cache ──
_LLM_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "llm"
_LLM_CACHE_TTL = 3 * 86400  # 3 days (financial data changes frequently)


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

    def _ask_json(self, prompt: str, system: str, max_tokens: int, model: str = "") -> dict:
        """Request structured JSON response + retry once on parse failure."""
        use_model = model or self.model
        response = ask_structured(
            prompt, system=system, model=use_model, max_tokens=max_tokens,
        )
        try:
            return _parse_json(response)
        except (json.JSONDecodeError, ValueError):
            logger.warning("JSON 파싱 실패 — 재시도 중")
            retry_prompt = prompt + "\n\n순수 JSON 객체만 출력하세요. 설명 텍스트 없이 JSON만 응답하세요."
            response = ask_structured(
                retry_prompt, system=system, model=use_model, max_tokens=max_tokens,
            )
            return _parse_json(response)

    def _cached_json_step(
        self,
        company: str,
        step: str,
        prompt_fn: Callable[[], str],
        system: str = SYSTEM_ANALYST,
        max_tokens: int = 1024,
        extra: str = "",
        model: str = "",
    ) -> dict:
        """Common pattern: check cache -> ask LLM JSON -> save cache + DB -> return.

        Args:
            company: Company name (cache key primary)
            step: Step identifier (cache key secondary)
            prompt_fn: Zero-arg callable returning the prompt string (lazy, skipped on cache hit)
            system: System prompt
            max_tokens: Max tokens for LLM response
            extra: Additional cache key discriminator
            model: Model override for this step (empty = self.model)
        """
        cached = _get_cached(company, step, extra)
        if cached:
            return cached
        use_model = model or self.model
        result = self._ask_json(prompt_fn(), system=system, max_tokens=max_tokens, model=use_model)
        _set_cached(company, step, result, extra)
        _save_analysis(company, step, result, use_model)
        return result

    def identify_company(self, user_input: str) -> dict:
        """Step 1: Natural language -> company identification."""
        return self._cached_json_step(
            user_input, "identify",
            lambda: prompt_identify_company(user_input),
            max_tokens=512, model=MODEL_LIGHT,
        )

    def classify_segments(self, company_name: str, revenue_breakdown: str) -> dict:
        """Step 2: Revenue breakdown -> segment classification."""
        return self._cached_json_step(
            company_name, "classify",
            lambda: prompt_segment_classification(company_name, revenue_breakdown),
            model=MODEL_LIGHT,
        )

    def recommend_peers(
        self,
        company_name: str,
        segment_code: str,
        segment_name: str,
        segment_description: str = "",
    ) -> dict:
        """Step 3: Per-segment peer/multiple recommendation."""
        return self._cached_json_step(
            company_name, "peers",
            lambda: prompt_peer_recommendation(
                company_name, segment_code, segment_name, segment_description,
            ),
            extra=segment_code, model=MODEL_LIGHT,
        )

    def recommend_peers_batch(
        self,
        company_name: str,
        segments: list[dict],
        market: str = "KR",
    ) -> dict:
        """Step 3 (batch): Peer/multiple recommendation for all segments in one call.

        Returns {segment_code: {peers, recommended_multiple, multiple_range, rationale}}.
        """
        codes_joined = ",".join(
            sorted(s.get("code", "MAIN") for s in segments)
        )
        result = self._cached_json_step(
            company_name, "peers_batch",
            lambda: prompt_peer_recommendation_batch(company_name, segments),
            max_tokens=2048, extra=codes_joined, model=MODEL_LIGHT,
        )
        from ai.validators import validate_peers
        result, warnings = validate_peers(result, market)
        for w in warnings:
            logger.warning("[peers] %s: %s", company_name, w)
        return result

    def suggest_wacc(
        self,
        company_name: str,
        de_ratio: float,
        industry: str = "",
        market: str = "KR",
    ) -> dict:
        """Step 4: WACC draft."""
        result = self._cached_json_step(
            company_name, "wacc",
            lambda: prompt_wacc_suggestion(company_name, de_ratio, industry),
            model=MODEL_LIGHT,
        )
        from ai.validators import validate_wacc
        result, warnings = validate_wacc(result, market)
        for w in warnings:
            logger.warning("[wacc] %s: %s", company_name, w)
        return result

    def design_scenarios(
        self,
        company_name: str,
        legal_status: str,
        key_issues: str = "",
        valuation_method: str = "dcf_primary",
        industry: str = "",
        ev_rev_multiple: float = 0.0,
        currency_unit: str = "$M",
        two_pass: bool = False,
        signals=None,
        segment_codes: list[str] | None = None,
    ) -> dict:
        """Step 5: Scenario design (multi-driver) with optional optionality segment detection.

        Cache key includes key_issues hash so different news produces fresh scenarios.
        Optionality segments are generated in the same call (no extra LLM quota) when
        a rule-based pre-screen detects binary-outcome business lines.

        Args:
            two_pass: If True, uses Haiku for classification draft (Pass 1) then
                Sonnet for precision refinement (Pass 2). Logs token cost comparison.
            signals: MarketSignals for prompt context injection (Phase 4).
        """
        if two_pass:
            return self._design_scenarios_two_pass(
                company_name, legal_status, key_issues, valuation_method,
                industry, ev_rev_multiple, currency_unit, signals=signals,
            )

        include_opt = _has_optionality_trigger(company_name, industry, key_issues, ev_rev_multiple)
        if include_opt:
            logger.info("[scenarios] Optionality trigger detected for %s — requesting segment generation", company_name)

        # Include key_issues content hash in cache key for invalidation
        issues_hash = hashlib.md5(key_issues.encode()).hexdigest()[:8] if key_issues else ""
        opt_flag = "opt1" if include_opt else "opt0"
        extra = f"{valuation_method}:{issues_hash}:{opt_flag}"
        system = SYSTEM_ANALYST + "\n" + SYSTEM_ANALYST_DRIVERS
        result = self._cached_json_step(
            company_name, "scenarios",
            lambda: prompt_scenario_design(
                company_name, legal_status, key_issues, valuation_method,
                include_optionality=include_opt, currency_unit=currency_unit,
                signals=signals, segment_codes=segment_codes,
            ),
            system=system, max_tokens=4096, extra=extra, model=MODEL_HEAVY,
        )
        from ai.validators import validate_scenarios
        scenarios = result.get("scenarios", result)
        validated, warnings = validate_scenarios(scenarios)
        if scenarios is not result:
            result["scenarios"] = validated
        else:
            result = validated
        for w in warnings:
            logger.warning("[scenarios] %s: %s", company_name, w)

        # Signal-aware validation (advisory warnings only)
        if signals is not None:
            from ai.validators import validate_scenarios_with_signals
            sc_list = validated if isinstance(validated, list) else list(validated.values()) if isinstance(validated, dict) else []
            sig_warnings = validate_scenarios_with_signals(sc_list, signals)
            for w in sig_warnings:
                logger.warning("[scenarios:signals] %s: %s", company_name, w)

        return result

    def _design_scenarios_two_pass(
        self,
        company_name: str,
        legal_status: str,
        key_issues: str,
        valuation_method: str,
        industry: str,
        ev_rev_multiple: float,
        currency_unit: str,
        signals=None,
    ) -> dict:
        """Two-pass scenario design: Haiku classification → Sonnet refinement.

        Pass 1 (Haiku): Fast/cheap classification — scenario codes, probability ranges,
        driver directions, narrative summaries.
        Pass 2 (Sonnet): Precision refinement — exact driver values, probabilities,
        detailed rationale, optionality segments.
        """
        include_opt = _has_optionality_trigger(company_name, industry, key_issues, ev_rev_multiple)
        if include_opt:
            logger.info("[scenarios:2pass] Optionality trigger detected for %s", company_name)

        issues_hash = hashlib.md5(key_issues.encode()).hexdigest()[:8] if key_issues else ""
        opt_flag = "opt1" if include_opt else "opt0"

        # ── Pass 1: Haiku classification draft ──
        pass1_extra = f"2pass_p1:{valuation_method}:{issues_hash}"
        system_p1 = SYSTEM_ANALYST
        draft = self._cached_json_step(
            company_name, "scenarios_draft",
            lambda: prompt_scenario_classify(
                company_name, legal_status, key_issues, valuation_method, currency_unit,
                signals=signals,
            ),
            system=system_p1, max_tokens=2048, extra=pass1_extra, model=MODEL_LIGHT,
        )

        # Validate draft structure
        from ai.validators import validate_scenario_draft
        draft, draft_warnings = validate_scenario_draft(draft)
        for w in draft_warnings:
            logger.warning("[scenarios:2pass:draft] %s: %s", company_name, w)

        logger.info(
            "[scenarios:2pass] Pass 1 complete for %s — %d scenarios classified",
            company_name, len(draft.get("scenario_draft", [])),
        )

        # ── Pass 2: Sonnet precision refinement ──
        pass2_extra = f"2pass_p2:{valuation_method}:{issues_hash}:{opt_flag}"
        system_p2 = SYSTEM_ANALYST + "\n" + SYSTEM_ANALYST_DRIVERS
        result = self._cached_json_step(
            company_name, "scenarios_refined",
            lambda: prompt_scenario_refine(
                company_name, legal_status, key_issues, draft,
                valuation_method, include_optionality=include_opt, currency_unit=currency_unit,
                signals=signals,
            ),
            system=system_p2, max_tokens=4096, extra=pass2_extra, model=MODEL_HEAVY,
        )

        # ── Validate final output ──
        from ai.validators import validate_scenarios
        scenarios = result.get("scenarios", result)
        validated, warnings = validate_scenarios(scenarios)
        if scenarios is not result:
            result["scenarios"] = validated
        else:
            result = validated
        for w in warnings:
            logger.warning("[scenarios:2pass] %s: %s", company_name, w)

        # Signal-aware validation (advisory warnings only)
        if signals is not None:
            from ai.validators import validate_scenarios_with_signals
            sc_list = validated if isinstance(validated, list) else list(validated.values()) if isinstance(validated, dict) else []
            sig_warnings = validate_scenarios_with_signals(sc_list, signals)
            for w in sig_warnings:
                logger.warning("[scenarios:2pass:signals] %s: %s", company_name, w)

        # Tag output as two-pass for downstream tracing
        if isinstance(result, dict):
            result["_two_pass"] = True

        return result

    def generate_research_note(
        self,
        company_name: str,
        valuation_summary: str,
    ) -> str:
        """Step 6: Research note generation (returns markdown text, not JSON)."""
        cached = _get_cached(company_name, "research_note")
        if cached:
            return cached.get("note", "")
        prompt = prompt_research_note(company_name, valuation_summary)
        note = ask(prompt, system=SYSTEM_ANALYST, model=MODEL_HEAVY, max_tokens=4096)
        _set_cached(company_name, "research_note", {"note": note})
        _save_analysis(company_name, "research_note", {"note": note}, self.model)
        return note
