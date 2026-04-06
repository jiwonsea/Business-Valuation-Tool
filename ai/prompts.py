"""Structured LLM prompts for valuation analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schemas.models import MarketSignals

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


def prompt_peer_recommendation_batch(
    company_name: str,
    segments: list[dict],
) -> str:
    """Batch peer recommendation prompt for multiple segments in a single LLM call.

    Each segment dict should have: code, name, peer_group (description).
    """
    seg_lines = "\n".join(
        f"  - Code: {s.get('code', 'MAIN')}, "
        f"Segment: {s.get('name', 'Main')}, "
        f"Description: {s.get('peer_group', '')}"
        for s in segments
    )
    seg_codes = ", ".join(s.get("code", "MAIN") for s in segments)
    return f"""\
<company>{company_name}</company>
<segments>
{seg_lines}
</segments>

Recommend 5+ domestic and international peer companies for EACH segment above.
Select peers by industry classification, revenue scale, and business structure similarity (in that order).
Prioritize Korean listed companies; include international peers when business structure is highly similar.
Since peer multiples are a critical input for SOTP valuation, verify that each EV/EBITDA is realistic.

<output_format>
{{
    "{seg_codes.split(', ')[0]}": {{
        "peers": [
            {{"name": "Company name", "ev_ebitda": 10.0, "notes": "Selection rationale and multiple source"}}
        ],
        "recommended_multiple": 10.0,
        "multiple_range": [8.0, 12.0],
        "rationale": "Recommendation rationale"
    }},
    ... (one entry per segment code: {seg_codes})
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


SYSTEM_ANALYST_DRIVERS = """\
<driver_reference>
Available valuation scenario drivers by method:

dcf_primary:
  - growth_adj_pct: EBITDA growth rate % adjustment (e.g., +20 → base growth × 1.2, -25 → × 0.75)
  - terminal_growth_adj: Terminal growth rate absolute adjustment %p (e.g., +0.3 → TGR + 0.3%p)
  - wacc_adj: WACC %p adjustment (e.g., +0.5 → WACC + 0.5%p)
  - market_sentiment_pct: Market sentiment EV % adjustment (e.g., +5 → EV × 1.05)

sotp:
  - market_sentiment_pct: Market sentiment EV % adjustment (e.g., +5 → EV × 1.05)
  - wacc_adj: WACC %p adjustment (applied to cross-validation DCF)

ddm:
  - ddm_growth: Dividend growth rate override (%, absolute. e.g., 4.0 → 4% growth)
  - wacc_adj: Ke %p adjustment (e.g., +0.5 → Ke + 0.5%p)

rim:
  - rim_roe_adj: ROE %p adjustment (e.g., -1.0 → all ROE -1%p)
  - wacc_adj: Ke %p adjustment (e.g., +0.5 → Ke + 0.5%p)

nav:
  - nav_discount: Holding company discount (%, e.g., 30 → NAV × 0.7)
  - market_sentiment_pct: Market sentiment EV % adjustment

multiples:
  - ev_multiple: Applied multiple override (absolute, e.g., 8.5)
  - market_sentiment_pct: Market sentiment EV % adjustment
  - wacc_adj: WACC %p adjustment (applied to cross-validation DCF)
</driver_reference>"""

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


def _optionality_instructions(currency_unit: str = "$M") -> str:
    """Shared optionality segment detection instructions for scenario design prompts."""
    return f"""
<optionality_detection>
If this company has binary-outcome business segments where payoff is explosive-or-0
(examples: autonomous driving, robotaxi fleet, humanoid robots, drug pipeline, AI platform,
space launch, nuclear fusion), identify them as optionality segments.

For each optionality segment, estimate EBITDA in {currency_unit} per scenario using:
  TAM × penetration_rate × operating_margin = EBITDA estimate

CRITICAL: Use the EXACT SAME scenario codes defined in "scenarios" above (e.g. if scenarios use "Bull","Base","Bear" then scenario_ebitda keys must be "Bull","Base","Bear").

Add to output (omit if no optionality segments found):
"optionality_segments": [
  {{
    "code": "SEG_OPT1",
    "name": "Descriptive segment name (e.g. FSD / Full Self-Driving)",
    "multiple": <SaaS/platform multiple, typically 25-50x EV/EBITDA>,
    "scenario_ebitda": {{
      "<scenario_code_bull>": <ebitda in {currency_unit}, full deployment>,
      "<scenario_code_base>": <ebitda in {currency_unit}, partial deployment>,
      "<scenario_code_bear>": 0
    }},
    "rationale": "TAM × penetration × margin math, e.g. $500B TAM × 3% × 25% = $3.75B"
  }}
]
</optionality_detection>"""


def _sanitize_news(text: str) -> str:
    """Strip control chars and truncate to prevent prompt injection from news content."""
    import re
    # Remove XML/HTML-like tags and control characters
    cleaned = re.sub(r"<[^>]*>", "", text)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
    # Truncate excessively long input
    if len(cleaned) > 8000:
        cleaned = cleaned[:8000] + "\n... (truncated)"
    return cleaned


def _driver_range_table(drivers_info: dict[str, str]) -> str:
    """Generate a driver range reference table for the LLM."""
    rows = []
    for k, desc in drivers_info.items():
        bounds = _DRIVER_BOUNDS.get(k)
        if bounds:
            rows.append(f"  - {k}: [{bounds[0]}, {bounds[1]}] — {desc}")
        else:
            rows.append(f"  - {k}: {desc}")
    return "\n".join(rows)


# Reasonable bounds for driver values (shared with validators)
_DRIVER_BOUNDS: dict[str, tuple[float, float]] = {
    "growth_adj_pct": (-50, 100),
    "terminal_growth_adj": (-2.0, 2.0),
    "wacc_adj": (-3.0, 3.0),
    "market_sentiment_pct": (-30, 30),
    "ddm_growth": (0.0, 15.0),
    "rim_roe_adj": (-10.0, 10.0),
    "ev_multiple": (1.0, 50.0),
    "nav_discount": (0.0, 60.0),
}


def prompt_scenario_design(
    company_name: str,
    legal_status: str,
    key_issues: str,
    valuation_method: str = "dcf_primary",
    include_optionality: bool = False,
    currency_unit: str = "$M",
    signals: MarketSignals | None = None,
) -> str:
    """Scenario design prompt.

    If key_issues is empty, generates a generic prompt; otherwise generates a news-driven prompt.
    Available driver list varies by valuation_method.
    """
    drivers_info = _METHOD_DRIVERS.get(valuation_method, _METHOD_DRIVERS["dcf_primary"])
    driver_json = ", ".join(f'"{k}": 0' for k in drivers_info)
    rationale_json = ", ".join(f'"{k}": "rationale"' for k in drivers_info)
    driver_table = _driver_range_table(drivers_info)
    signals_block = _format_market_signals(signals)

    if key_issues.strip():
        sanitized_issues = _sanitize_news(key_issues)
        # News-driven scenario design (multi-variable news drivers)
        effect_json = ", ".join(f'"{k}": 0' for k in drivers_info)
        return f"""\
<company>{company_name}</company>
<context>
Listed status: {legal_status}
Valuation method: {valuation_method}
</context>
{signals_block}
<driver_ranges>
{driver_table}
All driver values MUST stay within these ranges. Values outside will be rejected.
</driver_ranges>

<news_issues>
{sanitized_issues}
</news_issues>

Design 2-4 valuation scenarios for this company reflecting the news issues above.

<instructions>
Design using multi-variable news drivers (multiple regression approach):
Step 1: Extract 2-5 independent news_drivers from the key news issues (title + description)
Step 2: Quantify the partial effect of each driver on financial variables within the allowed ranges above
Step 3: For each scenario, decide which drivers to apply at what intensity (weight, 0~1)

PROBABILITY ASSIGNMENT (mandatory reasoning chain):
1. Anchor: Start from base rate — the historical frequency of similar events occurring
   (e.g., "Fed rate hikes > 50bp occurred in 3 of last 10 cycles = ~30% base rate")
2. Decompose: Break each scenario probability into conditional factors:
   P(scenario) = P(macro_condition) × P(industry_impact | macro) × P(company_response | industry)
3. Show the multiplication chain in probability_rationale
4. Base Case probability MUST be 30-50%. No single scenario may exceed 60%.
5. Verify: all probabilities sum to exactly 100%

CORRELATION AWARENESS:
When multiple drivers affect the same financial variable, note the interaction.
Correlated drivers (e.g., rate hike + credit tightening) applied together will be dampened
by a correlation factor downstream — design scenarios assuming independent partial effects.

Each scenario MUST include a "description" field (2-3 sentences) explaining the narrative.
For listed (상장) companies, DLOM MUST be 0 for ALL scenarios. DLOM only applies to unlisted (비상장) companies.
</instructions>

<example>
"50bp rate hike" driver → effects: {{wacc_adj: +0.5, growth_adj_pct: -10}}
"Tariff shock" driver → effects: {{growth_adj_pct: -15, market_sentiment_pct: -5}}
Bear scenario: both drivers at weight 1.0 → combined effects applied
  probability_rationale: "P(aggressive hike)=30% × P(tariff escalation|hike)=50% × P(margin hit|tariff)=80% ≈ 12%, rounded to 15%"
Base scenario: rate hike only at weight 0.5 → half effect applied
</example>

<output_format>
{{
    "news_drivers": [
        {{
            "id": "driver_id",
            "name": "News event name",
            "category": "macro | industry | company",
            "effects": {{{effect_json}}},
            "rationale": "Rationale for this driver's partial effects with evidence/base rate"
        }}
    ],
    "scenarios": [
        {{
            "code": "A",
            "name": "Scenario name",
            "prob": 30,
            "probability_rationale": "Base rate: X%. Conditional decomposition: P(A)×P(B|A)×P(C|B) = Y%",
            "description": "2-3 sentence scenario narrative",
            "dlom": 0,
            "key_assumptions": ["News-based assumption 1", "Assumption 2"],
            "active_drivers": {{"driver_id": 1.0}}
        }}
    ],
    "rationale": "Overall scenario design rationale",
    "news_factors_considered": ["Summary of key news issues reflected"]
}}
</output_format>""" + (f"\n{_optionality_instructions(currency_unit)}" if include_optionality else "")

    # Generic scenario design (multi-driver)
    return f"""\
<company>{company_name}</company>
<context>
Listed status: {legal_status}
Valuation method: {valuation_method}
</context>
{signals_block}
<driver_ranges>
{driver_table}
All driver values MUST stay within these ranges. Values outside will be rejected.
</driver_ranges>

Design 2-4 valuation scenarios suitable for this company.
Include probability, key assumptions, and DLOM (liquidity discount) applicability for each scenario.

<instructions>
Set quantitative drivers for each scenario within the allowed ranges above.
Base Case: all drivers at 0. Bull/Bear: adjust in appropriate direction.

PROBABILITY ASSIGNMENT (mandatory reasoning chain):
1. Anchor: Start from base rate — the historical frequency of similar macro/industry conditions
2. Decompose: P(scenario) = P(macro) × P(industry | macro) × P(company | industry)
3. Base Case probability MUST be 30-50%. No single scenario may exceed 60%.
4. Show the reasoning chain in probability_rationale.

CORRELATION AWARENESS:
If two drivers affect the same variable (e.g., growth_adj_pct and terminal_growth_adj both reduce growth),
note this in driver_rationale. Correlated effects will be dampened downstream.

Each scenario MUST include a "description" field (2-3 sentences) explaining the narrative.
</instructions>

<output_format>
{{
    "scenarios": [
        {{
            "code": "A",
            "name": "Scenario name",
            "prob": 30,
            "probability_rationale": "Base rate: X%. Conditional: P(A)×P(B|A) = Y%",
            "description": "2-3 sentence scenario narrative",
            "dlom": 0,
            "key_assumptions": ["Assumption 1", "Assumption 2"],
            "drivers": {{{driver_json}}},
            "driver_rationale": {{{rationale_json}}}
        }}
    ],
    "rationale": "Scenario design rationale"
}}
</output_format>""" + (f"\n{_optionality_instructions(currency_unit)}" if include_optionality else "")


# ── Market Signals Formatter (Phase 4) ──

def _format_market_signals(signals: MarketSignals | None) -> str:
    """Render MarketSignals into an XML block for prompt injection.

    Returns empty string if signals is None or has no data.
    """
    if signals is None or not signals.has_any():
        return ""

    lines = []

    # Macro
    macro_parts = []
    if signals.fed_funds_rate is not None:
        macro_parts.append(f"Fed Funds: {signals.fed_funds_rate:.2f}%")
    if signals.us_10y_yield is not None:
        macro_parts.append(f"10Y Treasury: {signals.us_10y_yield:.2f}%")
    if signals.breakeven_inflation is not None:
        macro_parts.append(f"Breakeven Inflation: {signals.breakeven_inflation:.2f}%")
    if signals.credit_spread_baa is not None:
        macro_parts.append(f"BAA Credit Spread: {signals.credit_spread_baa:.2f}%")
    if signals.vix is not None:
        macro_parts.append(f"VIX: {signals.vix:.1f}")
    if macro_parts:
        ts = signals.fetched_at[:10] if signals.fetched_at else "N/A"
        lines.append(f"MACRO (source: FRED, as of {ts}):")
        lines.append("  " + " | ".join(macro_parts))

    # Analyst Consensus
    if signals.target_mean is not None:
        analyst_parts = [f"Target: {signals.target_mean:.1f}"]
        if signals.target_low is not None and signals.target_high is not None:
            analyst_parts.append(f"(range: {signals.target_low:.1f}-{signals.target_high:.1f})")
        if signals.recommendation:
            analyst_parts.append(signals.recommendation.capitalize())
        n_str = f"N={signals.analyst_count}" if signals.analyst_count else "N=?"
        lines.append(f"ANALYST CONSENSUS ({n_str}):")
        lines.append("  " + " ".join(analyst_parts))

    # Sentiment
    if signals.news_sentiment_score is not None:
        n = signals.sentiment_article_count or 0
        lines.append(f"NEWS SENTIMENT (FinBERT, {n}건):")
        lines.append(f"  Score: {signals.news_sentiment_score:+.2f} ({signals.sentiment_label or 'N/A'})")

    # Options IV
    if signals.iv_30d_atm is not None:
        iv_parts = [f"IV: {signals.iv_30d_atm:.1f}%"]
        if signals.iv_percentile is not None:
            iv_parts.append(f"(percentile: {signals.iv_percentile:.0f}th vs 1Y)")
        if signals.put_call_ratio is not None:
            iv_parts.append(f"P/C Ratio: {signals.put_call_ratio:.2f}")
        lines.append("OPTIONS MARKET (30-day ATM):")
        lines.append("  " + " | ".join(iv_parts))

    # Calibration guidance
    guidance = []
    if signals.fed_funds_rate is not None or signals.us_10y_yield is not None:
        guidance.append("- wacc_adj should reflect current rate environment relative to long-term average")
    if signals.vix is not None and signals.vix > 25:
        guidance.append("- VIX is elevated — widen scenario spread (Bull-Bear gap should be larger)")
    if signals.target_mean is not None:
        guidance.append("- Weighted value should be within reasonable distance of analyst consensus target")
    if signals.news_sentiment_score is not None:
        if signals.news_sentiment_score > 0.3:
            guidance.append("- News sentiment is positive — Bull scenario probability may be warranted higher")
        elif signals.news_sentiment_score < -0.3:
            guidance.append("- News sentiment is negative — Bear scenario probability may be warranted higher")
    if guidance:
        lines.append("CALIBRATION GUIDANCE:")
        lines.extend(guidance)

    if not lines:
        return ""

    return "\n<market_signals>\n" + "\n".join(lines) + "\n</market_signals>\n"


def prompt_scenario_classify(
    company_name: str,
    legal_status: str,
    key_issues: str,
    valuation_method: str = "dcf_primary",
    currency_unit: str = "$M",
    signals: MarketSignals | None = None,
) -> str:
    """Pass 1 (Haiku): Lightweight scenario classification draft.

    Outputs scenario codes, names, probability ranges, and key driver directions
    WITHOUT precise numeric values. Designed for fast, cheap execution.
    """
    drivers_info = _METHOD_DRIVERS.get(valuation_method, _METHOD_DRIVERS["dcf_primary"])
    driver_names = ", ".join(drivers_info.keys())

    news_block = ""
    if key_issues.strip():
        sanitized_issues = _sanitize_news(key_issues)
        news_block = f"""
<news_issues>
{sanitized_issues}
</news_issues>
"""

    signals_block = _format_market_signals(signals)

    return f"""\
<company>{company_name}</company>
<context>
Listed status: {legal_status}
Valuation method: {valuation_method}
</context>
{signals_block}{news_block}
Classify 2-4 valuation scenarios for this company.
This is a CLASSIFICATION step only — provide directional guidance, not precise values.

<instructions>
For each scenario:
1. Assign a short code (e.g., "Bull", "Base", "Bear") and descriptive name
2. Estimate probability RANGE (e.g., 25-35%) — not a single number
3. List the key drivers that matter (from: {driver_names}) and their DIRECTION (↑/↓/→)
4. Write a 1-sentence narrative summary
5. If news is provided, extract 2-5 key news_driver themes (id + name + category)

PROBABILITY GUIDELINES:
- Base Case range MUST include 30-50% (e.g., 35-45%)
- No single scenario upper bound may exceed 60%
- Ranges should overlap minimally

For listed (상장) companies, DLOM MUST be 0.
</instructions>

<output_format>
{{
    "news_drivers": [
        {{
            "id": "driver_id",
            "name": "News event name",
            "category": "macro | industry | company"
        }}
    ],
    "scenario_draft": [
        {{
            "code": "Bull",
            "name": "Scenario name",
            "prob_range": [25, 35],
            "narrative": "1-sentence scenario summary",
            "dlom": 0,
            "driver_directions": {{"growth_adj_pct": "up", "wacc_adj": "down"}},
            "key_assumptions": ["Assumption 1", "Assumption 2"]
        }}
    ],
    "classification_rationale": "Why these scenarios were chosen"
}}
</output_format>"""


def prompt_scenario_refine(
    company_name: str,
    legal_status: str,
    key_issues: str,
    draft: dict,
    valuation_method: str = "dcf_primary",
    include_optionality: bool = False,
    currency_unit: str = "$M",
    signals: MarketSignals | None = None,
) -> str:
    """Pass 2 (Sonnet): Refine a scenario classification draft into a full design.

    Takes the Pass 1 draft and produces precise driver values, exact probabilities,
    descriptions, and rationale.
    """
    import json as _json

    drivers_info = _METHOD_DRIVERS.get(valuation_method, _METHOD_DRIVERS["dcf_primary"])
    driver_json = ", ".join(f'"{k}": 0' for k in drivers_info)
    rationale_json = ", ".join(f'"{k}": "rationale"' for k in drivers_info)
    driver_table = _driver_range_table(drivers_info)

    draft_str = _json.dumps(draft, ensure_ascii=False, indent=2)

    news_block = ""
    if key_issues.strip():
        sanitized_issues = _sanitize_news(key_issues)
        news_block = f"""
<news_issues>
{sanitized_issues}
</news_issues>
"""
        effect_json = ", ".join(f'"{k}": 0' for k in drivers_info)
        news_driver_format = f"""
    "news_drivers": [
        {{
            "id": "driver_id",
            "name": "News event name",
            "category": "macro | industry | company",
            "effects": {{{effect_json}}},
            "rationale": "Rationale with evidence/base rate"
        }}
    ],"""
        scenario_driver_key = '"active_drivers": {"driver_id": 1.0}'
    else:
        news_driver_format = ""
        scenario_driver_key = f'"drivers": {{{driver_json}}},\n            "driver_rationale": {{{rationale_json}}}'

    signals_block = _format_market_signals(signals)

    return f"""\
<company>{company_name}</company>
<context>
Listed status: {legal_status}
Valuation method: {valuation_method}
</context>
{signals_block}
<driver_ranges>
{driver_table}
All driver values MUST stay within these ranges. Values outside will be rejected.
</driver_ranges>
{news_block}
<classification_draft>
{draft_str}
</classification_draft>

Refine the scenario classification draft above into a FULL scenario design.
You MUST use the exact scenario codes and structure from the draft.

<instructions>
For each scenario from the draft:
1. Convert the probability RANGE into a single precise probability (pick within the range)
2. Convert driver DIRECTIONS into precise numeric values within the allowed ranges
3. Expand the narrative into a 2-3 sentence description
4. Add detailed probability_rationale using conditional decomposition:
   P(scenario) = P(macro) × P(industry|macro) × P(company|industry)
5. Verify: all probabilities sum to exactly 100%
6. Base Case probability MUST be 30-50%. No single scenario may exceed 60%.

If news_drivers are present in the draft, quantify their partial effects on financial variables.

CORRELATION AWARENESS:
When multiple drivers affect the same financial variable, note the interaction.
Correlated drivers applied together will be dampened by a correlation factor downstream.
</instructions>

<output_format>
{{{news_driver_format}
    "scenarios": [
        {{
            "code": "A",
            "name": "Scenario name",
            "prob": 30,
            "probability_rationale": "Base rate: X%. Conditional: P(A)×P(B|A) = Y%",
            "description": "2-3 sentence scenario narrative",
            "dlom": 0,
            "key_assumptions": ["Assumption 1", "Assumption 2"],
            {scenario_driver_key}
        }}
    ],
    "rationale": "Overall scenario design rationale"
}}
</output_format>""" + (f"\n{_optionality_instructions(currency_unit)}" if include_optionality else "")


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
