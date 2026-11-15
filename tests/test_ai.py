"""AI module unit tests — _parse_json parsing robustness + two-pass scenario design.

Does not call the LLM API; tests pure parsing logic and prompt generation only.
"""

import re

import pytest
from ai.analyst import _parse_json
from ai.prompts import (
    SYSTEM_ANALYST_DRIVERS,
    _format_market_signals,
    prompt_scenario_classify,
    prompt_scenario_design,
    prompt_scenario_refine,
)
from schemas.models import MarketSignals


class TestParseJson:
    """_parse_json 3-stage parsing strategy tests."""

    def test_pure_json(self):
        """Direct parsing of a pure JSON string."""
        text = '{"company_name": "삼성전자", "stock_code": "005930"}'
        result = _parse_json(text)
        assert result["company_name"] == "삼성전자"
        assert result["stock_code"] == "005930"

    def test_code_block_json(self):
        """Extract JSON from ```json ... ``` code block."""
        text = '```json\n{"rf": 3.5, "erp": 7.0}\n```'
        result = _parse_json(text)
        assert result["rf"] == 3.5
        assert result["erp"] == 7.0

    def test_code_block_no_lang(self):
        """Extract JSON from ``` ... ``` code block (no language specified)."""
        text = '```\n{"segments": [{"code": "SEG1"}]}\n```'
        result = _parse_json(text)
        assert result["segments"][0]["code"] == "SEG1"

    def test_json_with_surrounding_text(self):
        """Extract JSON surrounded by explanatory text."""
        text = '분석 결과입니다:\n{"confidence": "high", "wacc_estimate": 8.5}\n이상입니다.'
        result = _parse_json(text)
        assert result["confidence"] == "high"
        assert result["wacc_estimate"] == 8.5

    def test_nested_json(self):
        """Parse complex JSON with nested structure."""
        text = """{
    "scenarios": [
        {
            "code": "A",
            "name": "Base Case",
            "drivers": {"growth_adj_pct": 0, "wacc_adj": 0}
        }
    ],
    "rationale": "테스트"
}"""
        result = _parse_json(text)
        assert len(result["scenarios"]) == 1
        assert result["scenarios"][0]["drivers"]["growth_adj_pct"] == 0

    def test_invalid_json_raises(self):
        """Unparseable text raises ValueError."""
        with pytest.raises((ValueError, Exception)):
            _parse_json("이것은 JSON이 아닙니다.")

    def test_whitespace_around_json(self):
        """Handle JSON with leading/trailing whitespace."""
        text = '  \n  {"key": "value"}  \n  '
        result = _parse_json(text)
        assert result["key"] == "value"

    def test_code_block_with_extra_text(self):
        """Code block preceded by explanatory text."""
        text = '다음은 결과입니다:\n```json\n{"name": "SK에코플랜트"}\n```\n끝.'
        result = _parse_json(text)
        assert result["name"] == "SK에코플랜트"


class TestTwoPassPrompts:
    """Two-pass scenario prompts generate correct structure."""

    def test_classify_prompt_has_required_sections(self):
        """Pass 1 prompt includes scenario_draft output format."""
        prompt = prompt_scenario_classify(
            "삼성전자",
            "상장",
            "금리 인상 우려",
            "dcf_primary",
        )
        assert "scenario_draft" in prompt
        assert "prob_range" in prompt
        assert "driver_directions" in prompt
        assert "CLASSIFICATION" in prompt

    def test_classify_prompt_no_news(self):
        """Pass 1 prompt works without news."""
        prompt = prompt_scenario_classify(
            "삼성전자",
            "상장",
            "",
            "dcf_primary",
        )
        assert "scenario_draft" in prompt
        assert "news_issues" not in prompt

    def test_classify_prompt_includes_driver_names(self):
        """Pass 1 prompt lists available drivers for the method."""
        prompt = prompt_scenario_classify(
            "삼성전자",
            "상장",
            "",
            "dcf_primary",
        )
        assert "growth_adj_pct" in prompt
        assert "wacc_adj" in prompt

    def test_classify_prompt_ddm_method(self):
        """Pass 1 prompt adapts drivers to DDM method."""
        prompt = prompt_scenario_classify(
            "삼성전자",
            "상장",
            "",
            "ddm",
        )
        assert "ddm_growth" in prompt
        # DDM driver list should not include DCF-specific drivers
        assert "terminal_growth_adj" not in prompt

    def test_refine_prompt_includes_draft(self):
        """Pass 2 prompt embeds the classification draft."""
        draft = {
            "scenario_draft": [
                {
                    "code": "Bull",
                    "name": "Bull Case",
                    "prob_range": [25, 35],
                    "driver_directions": {"growth_adj_pct": "up"},
                },
                {
                    "code": "Base",
                    "name": "Base Case",
                    "prob_range": [35, 45],
                    "driver_directions": {},
                },
            ]
        }
        prompt = prompt_scenario_refine(
            "삼성전자",
            "상장",
            "",
            draft,
            "dcf_primary",
        )
        assert "classification_draft" in prompt
        assert "Bull Case" in prompt
        assert "prob_range" in prompt

    def test_refine_prompt_with_news(self):
        """Pass 2 prompt includes news and news_driver format when key_issues given."""
        draft = {"scenario_draft": []}
        prompt = prompt_scenario_refine(
            "삼성전자",
            "상장",
            "금리 인상 관련 뉴스",
            draft,
            "dcf_primary",
        )
        assert "news_issues" in prompt
        assert "active_drivers" in prompt

    def test_refine_prompt_has_driver_ranges(self):
        """Pass 2 prompt includes driver range table."""
        draft = {"scenario_draft": []}
        prompt = prompt_scenario_refine(
            "삼성전자",
            "상장",
            "",
            draft,
            "dcf_primary",
        )
        assert "driver_ranges" in prompt
        assert "[-50, 100]" in prompt  # growth_adj_pct range


RATE_SIGNALS = MarketSignals(fed_funds_rate=5.25, us_10y_yield=4.35)
RATE_GUIDANCE = "wacc_adj should reflect current rate environment"
# A Pass-1 answer (or an older cached one) that still names wacc_adj
PASS1_DRAFT = {
    "news_drivers": [{"id": "rate_hike", "effects": {"wacc_adj": 0.5}}],
    "scenario_draft": [
        {
            "code": "Bull",
            "prob_range": [25, 35],
            "driver_directions": {"growth_adj_pct": "up", "wacc_adj": "down"},
        }
    ],
}


def _scenario_prompts(method: str, key_issues: str) -> dict[str, str]:
    """The three scenario prompts for one method, with rate signals attached."""
    codes = ["SEG1", "SEG2"]
    return {
        "design": prompt_scenario_design(
            "삼성전자",
            "상장",
            key_issues,
            method,
            signals=RATE_SIGNALS,
            segment_codes=codes,
        ),
        "classify": prompt_scenario_classify(
            "삼성전자", "상장", key_issues, method, signals=RATE_SIGNALS
        ),
        "refine": prompt_scenario_refine(
            "삼성전자",
            "상장",
            key_issues,
            PASS1_DRAFT,
            method,
            signals=RATE_SIGNALS,
            segment_codes=codes,
        ),
    }


class TestDiscountRateDriverByMethod:
    """wacc_adj is offered only to methods that consume a discount rate (J-4)."""

    @pytest.mark.parametrize("method", ["sotp", "multiples", "nav"])
    @pytest.mark.parametrize("key_issues", ["", "금리 인상 관련 뉴스"])
    def test_methods_without_a_discount_rate_never_see_wacc_adj(
        self, method, key_issues
    ):
        for name, prompt in _scenario_prompts(method, key_issues).items():
            assert "wacc_adj" not in prompt, name
            assert "- Rate environment: reflect through" in prompt, name

    @pytest.mark.parametrize("method", ["dcf_primary", "ddm", "rim", "rnpv"])
    @pytest.mark.parametrize("key_issues", ["", "금리 인상 관련 뉴스"])
    def test_discount_rate_methods_keep_wacc_adj(self, method, key_issues):
        for name, prompt in _scenario_prompts(method, key_issues).items():
            assert "wacc_adj" in prompt, name
            assert RATE_GUIDANCE in prompt, name
            assert "- Rate environment: reflect through" not in prompt, name

    @pytest.mark.parametrize("method", ["sotp", "multiples", "nav"])
    def test_refine_drops_wacc_adj_from_the_draft_without_changing_it(self, method):
        import copy

        draft = copy.deepcopy(PASS1_DRAFT)

        prompt = prompt_scenario_refine("삼성전자", "상장", "", draft, method)

        assert "wacc_adj" not in prompt
        assert (
            '"driver_directions": {\n        "growth_adj_pct": "up"\n      }' in prompt
        )
        assert '"effects": {}' in prompt
        assert draft == PASS1_DRAFT

    def test_refine_keeps_the_draft_as_is_for_a_discount_rate_method(self):
        prompt = prompt_scenario_refine("삼성전자", "상장", "", PASS1_DRAFT, "ddm")

        assert '"wacc_adj": "down"' in prompt
        assert '"wacc_adj": 0.5' in prompt

    def test_market_signal_rate_guidance_follows_the_method(self):
        assert RATE_GUIDANCE in _format_market_signals(RATE_SIGNALS)
        assert RATE_GUIDANCE in _format_market_signals(RATE_SIGNALS, "dcf_primary")
        for method in ("sotp", "multiples", "nav"):
            block = _format_market_signals(RATE_SIGNALS, method)
            assert "wacc_adj" not in block
            assert "- Rate environment: reflect through" in block

    def test_system_driver_reference_lists_wacc_adj_per_method(self):
        blocks = dict(
            re.findall(r"^(\w+):\n((?:  - .*\n?)+)", SYSTEM_ANALYST_DRIVERS, re.M)
        )
        assert sorted(blocks) == [
            "dcf_primary",
            "ddm",
            "multiples",
            "nav",
            "rim",
            "sotp",
        ]
        with_wacc_adj = {m for m, text in blocks.items() if "wacc_adj" in text}
        assert with_wacc_adj == {"dcf_primary", "ddm", "rim"}
        assert (
            "applied WACC = Base WACC + adj; Base includes any distress premium"
            in blocks["dcf_primary"]
        )
        for method in ("ddm", "rim"):
            assert "applied Ke = Base Ke + adj" in blocks[method]
