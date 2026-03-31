# Profile Skill

## Description
TRIGGER when: user mentions "프로필 만들어", "YAML 생성", "가정값 수정", "시나리오 추가/변경", "create profile", "template", or requests a profile for a new company analysis.
DO NOT TRIGGER when: running valuation with a completed profile (→ /valuation), news-based company recommendation (→ /discover).

## Overview
Creates or modifies YAML profiles. A profile is the YAML representation of the `ValuationInput` schema and serves as the sole input for valuation execution.

## Workflow
1. Confirm company name, industry, listed/unlisted status with user
2. Industry → determine methodology per `method_selector.py` criteria → decide required fields
3. Collect financial data (user-provided or auto-fetch via DART/SEC)
4. Generate YAML draft → user review → save

## File References
Detailed guides in this folder. Read only when needed:
- [references/field_guide.md](references/field_guide.md) — Required/optional field map by industry
- [references/scenario_patterns.md](references/scenario_patterns.md) — Scenario design patterns and probability allocation rules

## Gotchas
- New fields must always be `Optional + default`. Existing profiles must not break.
- `shares` field: applied share count may differ per scenario (depending on CPS conversion). Always explicitly set `scenarios.*.shares`.
- Scenario probability sum must be exactly 100%. `ValuationInput.validate_inputs()` validates with 0.1%p tolerance.
- Financial industry profiles: `wacc_params.is_financial: true`, `eq_w: 100.0` (Ke=WACC). `bu` is direct Equity Beta input (Hamada not applied).
- Year keys in `segment_data` and `consolidated` must include `base_year`. Missing causes runtime error.
- `net_debt` is in display-unit basis (if profile is in millions KRW, net_debt is in millions KRW). Never hardcode `* 1_000_000`.
- `peers` list `segment_code` must exactly match `segments` dict keys.
