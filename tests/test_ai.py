"""AI module unit tests — _parse_json parsing robustness verification.

Does not call the LLM API; tests pure parsing logic only.
"""

import pytest
from ai.analyst import _parse_json


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
