"""Structured LLM prompts for valuation analysis."""

SYSTEM_ANALYST = """\
<role>
Expert analyst specializing in KR/US company valuations.
Expertise: SOTP, DCF, DDM, RIM, NAV, relative valuation.
Markets: Korea (KOSPI/KOSDAQ, DART filings) and global peer comparison.
</role>

<response_rules>
- Respond in Korean. Target the level of reports directly used by Korean financial professionals.
- Amounts in millions KRW, ratios in %. This follows standard valuation report formatting.
- When JSON is requested, output pure JSON only. No code blocks (```) or explanation text. Downstream code parses the output directly.
- Cite evidence for all figures. Mark uncertain items as "확인 필요". Audit trails are essential for valuation decisions.
- For complex judgments, reason step-by-step before concluding.
</response_rules>"""

SYSTEM_DISCOVERY = """\
<role>
Financial market news analysis expert. Extracts key information from news that impacts company valuations.
</role>
<response_rules>
- Write in Korean. Use original names for English proper nouns.
- Include news source dates in all judgments.
- When JSON is requested, output pure JSON only. No code blocks or explanation text.
</response_rules>"""


def prompt_identify_company(user_input: str) -> str:
    """Natural language → company identification prompt."""
    return f"""\
<user_input>{user_input}</user_input>

Identify the target company for analysis from the input above.
First extract identification clues (company name, ticker, industry) from the input, then determine the official company name and DART registration name.
If the input uses abbreviations or is ambiguous, select the most widely known company.

<example>
Input: "에코플랜트"
Output: {{"company_name": "SK에코플랜트", "dart_name": "에스케이에코플랜트", "stock_code": null, "legal_status": "비상장", "industry": "환경/에너지 플랜트"}}
</example>

<output_format>
{{
    "company_name": "Official company name",
    "dart_name": "DART registration name (e.g., 에스케이에코플랜트)",
    "stock_code": "Stock code (listed) or null",
    "legal_status": "상장 or 비상장",
    "industry": "Industry classification"
}}
</output_format>"""


def prompt_segment_classification(
    company_name: str,
    revenue_breakdown: str,
) -> str:
    """Segment classification prompt."""
    return f"""\
<company>{company_name}</company>
<revenue_data>
{revenue_breakdown}
</revenue_data>

Based on the revenue breakdown above, propose segment classifications suitable for valuation.
Classify by revenue share, profitability differences, and applicable peer groups.
Consolidate items with similar business characteristics into a single segment.
Also suggest an appropriate EV/EBITDA peer group for each segment.

<output_format>
{{
    "segments": [
        {{
            "code": "SEG1",
            "name": "Segment name",
            "revenue_share_pct": 50.0,
            "peer_group": "Comparable company group description",
            "suggested_multiple_range": "8.0~12.0x"
        }}
    ]
}}
</output_format>"""


def prompt_peer_recommendation(
    company_name: str,
    segment_code: str,
    segment_name: str,
    segment_description: str,
) -> str:
    """Peer company and multiple recommendation prompt."""
    return f"""\
<company>{company_name}</company>
<segment>
Code: {segment_code}
Segment: {segment_name}
Description: {segment_description}
</segment>

Recommend 5+ domestic and international peer companies suitable for this segment.
Select peers by industry classification, revenue scale, and business structure similarity (in that order).
Prioritize Korean listed companies; include international peers when business structure is highly similar.
Since peer multiples are a critical input for SOTP valuation, verify that each EV/EBITDA is realistic.

<output_format>
{{
    "peers": [
        {{"name": "Company name", "ev_ebitda": 10.0, "notes": "Selection rationale and multiple source"}}
    ],
    "recommended_multiple": 10.0,
    "multiple_range": [8.0, 12.0],
    "rationale": "Recommendation rationale"
}}
</output_format>"""


def prompt_wacc_suggestion(
    company_name: str,
    de_ratio: float,
    industry: str,
) -> str:
    """WACC draft suggestion prompt."""
    return f"""\
<company>{company_name}</company>
<financial_context>
D/E ratio: {de_ratio:.1f}%
Industry: {industry}
</financial_context>

Estimate the WACC components for this company.
Reason step-by-step in the following order:
1) Risk-free rate (Rf): Based on Korea 10Y government bond yield
2) Equity risk premium (ERP): Based on Damodaran or Korea market empirical data
3) Unlevered beta (Bu): Based on peer average unlevered beta in the same industry
4) Cost of debt (Kd): Based on credit rating and spread
5) Final WACC calculation

Cite Korea market-based evidence for each parameter.

<output_format>
{{
    "rf": 3.5,
    "rf_source": "Based on 10Y govt bond",
    "erp": 7.0,
    "erp_source": "Korea market ERP rationale",
    "bu": 0.75,
    "bu_source": "Peer avg unlevered beta rationale",
    "kd_pre": 5.0,
    "kd_source": "Credit rating/spread rationale",
    "tax": 22.0,
    "wacc_estimate": 8.5,
    "confidence": "high/medium/low"
}}
</output_format>"""


_METHOD_DRIVERS: dict[str, dict[str, str]] = {
    "dcf_primary": {
        "growth_adj_pct": "EBITDA growth rate % adjustment (e.g., +20 → base growth × 1.2, -25 → × 0.75)",
        "terminal_growth_adj": "Terminal growth rate absolute adjustment %p (e.g., +0.3 → TGR + 0.3%p)",
        "wacc_adj": "WACC %p adjustment (e.g., +0.5 → WACC + 0.5%p)",
        "market_sentiment_pct": "Market sentiment EV % adjustment (e.g., +5 → EV × 1.05)",
    },
    "sotp": {
        "market_sentiment_pct": "Market sentiment EV % adjustment (e.g., +5 → EV × 1.05)",
        "wacc_adj": "WACC %p adjustment (applied to cross-validation DCF)",
    },
    "ddm": {
        "ddm_growth": "Dividend growth rate override (%, absolute. e.g., 4.0 → 4% growth)",
        "wacc_adj": "Ke %p adjustment (e.g., +0.5 → Ke + 0.5%p)",
    },
    "rim": {
        "rim_roe_adj": "ROE %p adjustment (e.g., -1.0 → all ROE -1%p)",
        "wacc_adj": "Ke %p adjustment (e.g., +0.5 → Ke + 0.5%p)",
    },
    "nav": {
        "nav_discount": "Holding company discount (%, e.g., 30 → NAV × 0.7)",
        "market_sentiment_pct": "Market sentiment EV % adjustment",
    },
    "multiples": {
        "ev_multiple": "Applied multiple override (absolute, e.g., 8.5)",
        "market_sentiment_pct": "Market sentiment EV % adjustment",
        "wacc_adj": "WACC %p adjustment (applied to cross-validation DCF)",
    },
}


def prompt_scenario_design(
    company_name: str,
    legal_status: str,
    key_issues: str,
    valuation_method: str = "dcf_primary",
) -> str:
    """Scenario design prompt.

    If key_issues is empty, generates a generic prompt; otherwise generates a news-driven prompt.
    Available driver list varies by valuation_method.
    """
    drivers_info = _METHOD_DRIVERS.get(valuation_method, _METHOD_DRIVERS["dcf_primary"])
    driver_desc = "\n".join(f"  - {k}: {v}" for k, v in drivers_info.items())
    driver_json = ", ".join(f'"{k}": 0' for k in drivers_info)
    rationale_json = ", ".join(f'"{k}": "rationale"' for k in drivers_info)

    if key_issues.strip():
        # News-driven scenario design (multi-variable news drivers)
        effect_json = ", ".join(f'"{k}": 0' for k in drivers_info)
        return f"""\
<company>{company_name}</company>
<context>
Listed status: {legal_status}
Valuation method: {valuation_method}
</context>

<news_issues>
{key_issues}
</news_issues>

Design 2-4 valuation scenarios for this company reflecting the news issues above.

<instructions>
Design using multi-variable news drivers (multiple regression approach):
Step 1: Extract 2-5 independent news_drivers from the key news issues
Step 2: Quantify the partial effect of each driver on financial variables
Step 3: For each scenario, decide which drivers to apply at what intensity (weight, 0~1)

When allocating probabilities, separate macro, industry, and company-specific factors and assess each factor's likelihood.
Specify related news issues concretely in key_assumptions.
DLOM (liquidity discount) should reflect listed status and per-scenario liquidity risk.
</instructions>

<example>
"50bp rate hike" driver → effects: {{wacc_adj: +0.5, growth_adj_pct: -10}}
"Tariff shock" driver → effects: {{growth_adj_pct: -15, market_sentiment_pct: -5}}
Bear scenario: both drivers at weight 1.0 → combined effects applied
Base scenario: rate hike only at weight 0.5 → half effect applied
</example>

<available_drivers>
Available effect keys ({valuation_method} method):
{driver_desc}
</available_drivers>

<output_format>
{{
    "news_drivers": [
        {{
            "id": "driver_id",
            "name": "News event name",
            "category": "macro | industry | company",
            "effects": {{{effect_json}}},
            "rationale": "Rationale for this driver's partial effects"
        }}
    ],
    "scenarios": [
        {{
            "code": "A",
            "name": "Scenario name",
            "prob": 30,
            "probability_rationale": "Rationale for this probability allocation",
            "description": "Scenario description",
            "dlom": 0,
            "key_assumptions": ["News-based assumption 1", "Assumption 2"],
            "active_drivers": {{"driver_id": 1.0}}
        }}
    ],
    "rationale": "Overall scenario design rationale",
    "news_factors_considered": ["Summary of key news issues reflected"]
}}
</output_format>"""

    # Generic scenario design (multi-driver)
    return f"""\
<company>{company_name}</company>
<context>
Listed status: {legal_status}
Valuation method: {valuation_method}
</context>

Design 2-4 valuation scenarios suitable for this company.
Include probability, key assumptions, and DLOM (liquidity discount) applicability for each scenario.

<instructions>
Set quantitative drivers for each scenario.
Base Case: all drivers at 0. Bull/Bear: adjust in appropriate direction.
When allocating probabilities, separate macro, industry, and company-specific factors and cite rationale.
</instructions>

<available_drivers>
Available drivers ({valuation_method} method):
{driver_desc}
</available_drivers>

<output_format>
{{
    "scenarios": [
        {{
            "code": "A",
            "name": "Scenario name",
            "prob": 30,
            "description": "Scenario description",
            "dlom": 0,
            "key_assumptions": ["Assumption 1", "Assumption 2"],
            "drivers": {{{driver_json}}},
            "driver_rationale": {{{rationale_json}}}
        }}
    ],
    "rationale": "Scenario design rationale"
}}
</output_format>"""


def prompt_research_note(
    company_name: str,
    valuation_summary: str,
) -> str:
    """Research note auto-generation prompt."""
    return f"""\
<company>{company_name}</company>
<valuation_data>
{valuation_summary}
</valuation_data>

Based on the valuation analysis results above, write a professional research note.
Write in Korean markdown format with the professional tone of a securities analyst research note.

<output_structure>
1. Investment opinion (one-line summary)
2. Key valuation summary (SOTP + DCF)
3. Risk/opportunity factors by scenario
4. Multiple justification review
5. Key monitoring points
</output_structure>"""
