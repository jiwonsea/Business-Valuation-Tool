# Review Skill

## Description
TRIGGER when: user mentions "결과 검증", "괴리율 확인", "sanity check", "결과가 이상해", "result validation", "gap check".
DO NOT TRIGGER when: running valuation (→ /valuation), profile creation (→ /profile), news analysis (→ /discover).

## Overview
Validates the reasonableness of valuation results. Market price comparison, assumption review, cross-validation analysis.

## File References
- [references/sanity_checks.md](references/sanity_checks.md) — Validation checklist with threshold criteria per item

## Gotchas
- Unlisted companies cannot be compared to market price — focus on cross-validation
- If deviation exceeds +/-50%, must suggest re-reviewing assumptions
- Warn if WACC is abnormally high or low (< 5% or > 20%)
