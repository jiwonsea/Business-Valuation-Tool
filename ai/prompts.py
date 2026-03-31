"""구조화된 LLM 프롬프트 — 밸류에이션 분석 보조."""

SYSTEM_ANALYST = """당신은 한국 기업 밸류에이션 전문 애널리스트입니다.
응답 규칙:
- 한국어로 답변
- 수치는 백만원 단위, 비율은 % 단위
- JSON 요청 시 코드블록 없이 순수 JSON만 출력
- 근거 없는 추정 금지, 불확실한 경우 "확인 필요" 표시"""


def prompt_identify_company(user_input: str) -> str:
    """자연어 → 기업 식별 프롬프트."""
    return f"""사용자 입력: "{user_input}"

이 입력에서 분석 대상 기업을 식별하세요.
다음 JSON 형식으로 응답:
{{
    "company_name": "정식 회사명",
    "dart_name": "DART 등록명 (예: 에스케이에코플랜트)",
    "stock_code": "종목코드 (상장사) 또는 null",
    "legal_status": "상장" 또는 "비상장",
    "industry": "업종 분류"
}}"""


def prompt_segment_classification(
    company_name: str,
    revenue_breakdown: str,
) -> str:
    """부문 분류 프롬프트."""
    return f"""기업: {company_name}
매출 구성:
{revenue_breakdown}

위 매출 구성을 기반으로 밸류에이션에 적합한 부문(segment) 분류를 제안하세요.
각 부문에 적절한 EV/EBITDA peer 그룹도 함께 제시하세요.

JSON 형식:
{{
    "segments": [
        {{
            "code": "SEG1",
            "name": "부문명",
            "revenue_share_pct": 50.0,
            "peer_group": "유사기업군 설명",
            "suggested_multiple_range": "8.0~12.0x"
        }}
    ]
}}"""


def prompt_peer_recommendation(
    company_name: str,
    segment_code: str,
    segment_name: str,
    segment_description: str,
) -> str:
    """Peer 기업 및 멀티플 추천 프롬프트."""
    return f"""기업: {company_name}
분석 부문: {segment_code} - {segment_name}
부문 설명: {segment_description}

이 부문에 적합한 국내외 Peer 기업을 5개 이상 추천하고,
각 기업의 최근 EV/EBITDA 멀티플을 제시하세요.
최종적으로 적용할 적정 멀티플 범위와 추천값을 제안하세요.

JSON 형식:
{{
    "peers": [
        {{"name": "기업명", "ev_ebitda": 10.0, "notes": "근거"}}
    ],
    "recommended_multiple": 10.0,
    "multiple_range": [8.0, 12.0],
    "rationale": "추천 근거"
}}"""


def prompt_wacc_suggestion(
    company_name: str,
    de_ratio: float,
    industry: str,
) -> str:
    """WACC 초안 프롬프트."""
    return f"""기업: {company_name}
부채비율: {de_ratio:.1f}%
업종: {industry}

이 기업의 WACC 구성요소를 추정하세요.
한국 시장 기준으로 각 파라미터의 근거를 제시하세요.

JSON 형식:
{{
    "rf": 3.5,
    "rf_source": "국고채 10Y 기준",
    "erp": 7.0,
    "erp_source": "한국 시장 ERP 근거",
    "bu": 0.75,
    "bu_source": "Peer 평균 Unlevered Beta 근거",
    "kd_pre": 5.0,
    "kd_source": "신용등급/스프레드 근거",
    "tax": 22.0,
    "wacc_estimate": 8.5,
    "confidence": "high/medium/low"
}}"""


_METHOD_DRIVERS: dict[str, dict[str, str]] = {
    "dcf_primary": {
        "growth_adj_pct": "EBITDA 성장률 % 조정 (e.g., +20 → 기본 성장률 × 1.2, -25 → × 0.75)",
        "terminal_growth_adj": "영구성장률 절대 조정 %p (e.g., +0.3 → TGR + 0.3%p)",
        "wacc_adj": "WACC %p 조정 (e.g., +0.5 → WACC + 0.5%p)",
        "market_sentiment_pct": "시장 심리 EV % 조정 (e.g., +5 → EV × 1.05)",
    },
    "sotp": {
        "market_sentiment_pct": "시장 심리 EV % 조정 (e.g., +5 → EV × 1.05)",
        "wacc_adj": "WACC %p 조정 (교차검증 DCF에 반영)",
    },
    "ddm": {
        "ddm_growth": "배당성장률 override (%, 절대값. e.g., 4.0 → 4% 성장)",
        "wacc_adj": "Ke %p 조정 (e.g., +0.5 → Ke + 0.5%p)",
    },
    "rim": {
        "rim_roe_adj": "ROE %p 조정 (e.g., -1.0 → 전체 ROE -1%p)",
        "wacc_adj": "Ke %p 조정 (e.g., +0.5 → Ke + 0.5%p)",
    },
    "nav": {
        "nav_discount": "지주할인율 (%, e.g., 30 → NAV × 0.7)",
        "market_sentiment_pct": "시장 심리 EV % 조정",
    },
    "multiples": {
        "ev_multiple": "적용 멀티플 override (절대값, e.g., 8.5)",
        "market_sentiment_pct": "시장 심리 EV % 조정",
        "wacc_adj": "WACC %p 조정 (교차검증 DCF에 반영)",
    },
}


def prompt_scenario_design(
    company_name: str,
    legal_status: str,
    key_issues: str,
    valuation_method: str = "dcf_primary",
) -> str:
    """시나리오 설계 프롬프트.

    key_issues가 비어있으면 범용 프롬프트, 있으면 뉴스 기반 근거 프롬프트 생성.
    valuation_method에 따라 AI가 설정할 수 있는 드라이버 목록이 달라짐.
    """
    drivers_info = _METHOD_DRIVERS.get(valuation_method, _METHOD_DRIVERS["dcf_primary"])
    driver_desc = "\n".join(f"  - {k}: {v}" for k, v in drivers_info.items())
    driver_json = ", ".join(f'"{k}": 0' for k in drivers_info)
    rationale_json = ", ".join(f'"{k}": "근거"' for k in drivers_info)

    if key_issues.strip():
        # 뉴스 기반 시나리오 설계 (멀티 드라이버)
        return f"""기업: {company_name}
상장여부: {legal_status}
적용 밸류에이션 방법론: {valuation_method}

최근 1개월간 수집된 핵심 이슈:
{key_issues}

위 이슈들을 반드시 시나리오에 반영하여, 이 기업에 적합한 밸류에이션 시나리오 2~4개를 설계하세요.

요구사항:
- 각 시나리오의 확률은 위 이슈들의 실현 가능성과 시장 상황을 근거로 할당
- key_assumptions에 관련 뉴스 이슈를 구체적으로 명시
- probability_rationale에 해당 확률을 할당한 근거를 설명
- DLOM(비상장 할인)은 상장여부와 시나리오별 유동성 리스크를 반영
- **중요 — 멀티 드라이버**: 각 시나리오에 정량적 drivers를 설정하세요.
  하나의 뉴스 이벤트가 여러 드라이버에 동시에 영향을 줄 수 있습니다.
  예시: "금리 인상" → wacc_adj: +0.5, growth_adj_pct: -10, terminal_growth_adj: -0.3
  Base Case는 drivers를 모두 0으로, Bull/Bear는 방향성에 맞게 설정하세요.
- driver_rationale에 각 드라이버 값의 근거를 뉴스 이슈와 연결하여 설명

사용 가능한 드라이버 ({valuation_method} 방법론):
{driver_desc}

JSON 형식:
{{
    "scenarios": [
        {{
            "code": "A",
            "name": "시나리오명",
            "prob": 30,
            "probability_rationale": "이 확률을 할당한 근거 (뉴스/시장 상황 기반)",
            "description": "시나리오 설명",
            "dlom": 0,
            "key_assumptions": ["뉴스 기반 가정1", "가정2"],
            "drivers": {{{driver_json}}},
            "driver_rationale": {{{rationale_json}}}
        }}
    ],
    "rationale": "전체 시나리오 구성 근거",
    "news_factors_considered": ["반영된 주요 뉴스 이슈 요약"]
}}"""

    # 범용 시나리오 설계 (멀티 드라이버)
    return f"""기업: {company_name}
상장여부: {legal_status}
적용 밸류에이션 방법론: {valuation_method}

이 기업에 적합한 밸류에이션 시나리오 2~4개를 설계하세요.
각 시나리오의 확률, 핵심 가정, DLOM(비상장 할인) 적용 여부를 포함하세요.

**중요 — 멀티 드라이버**: 각 시나리오에 정량적 drivers를 설정하세요.
Base Case는 drivers를 모두 0으로, Bull/Bear는 방향성에 맞게 설정하세요.

사용 가능한 드라이버 ({valuation_method} 방법론):
{driver_desc}

JSON 형식:
{{
    "scenarios": [
        {{
            "code": "A",
            "name": "시나리오명",
            "prob": 30,
            "description": "시나리오 설명",
            "dlom": 0,
            "key_assumptions": ["가정1", "가정2"],
            "drivers": {{{driver_json}}},
            "driver_rationale": {{{rationale_json}}}
        }}
    ],
    "rationale": "시나리오 구성 근거"
}}"""


def prompt_research_note(
    company_name: str,
    valuation_summary: str,
) -> str:
    """리서치 노트 자동 생성 프롬프트."""
    return f"""다음 밸류에이션 분석 결과를 기반으로 전문 리서치 노트를 작성하세요.

기업: {company_name}
분석 결과:
{valuation_summary}

포함 사항:
1. 투자 의견 (한 줄 요약)
2. 핵심 밸류에이션 요약 (SOTP + DCF)
3. 시나리오별 리스크/기회 요인
4. 멀티플 정당성 검토
5. 주요 모니터링 포인트

형식: 마크다운, 전문 애널리스트 톤, 한국어"""
