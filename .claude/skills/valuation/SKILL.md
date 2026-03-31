# Valuation Skill

## Description
TRIGGER when: user mentions "밸류에이션 실행", "기업 분석", "기업가치 평가", "run valuation", "--profile", "--company".
DO NOT TRIGGER when: profile creation (→ /profile), news analysis (→ /discover), result validation (→ /review), report output (→ /report).

## Overview
Runs valuation from a YAML profile or company name input. Methodology is auto-selected based on company characteristics; user can override.

## File References
Detailed guides in this folder. Read only when needed:
- [references/method_guide.md](references/method_guide.md) — Method selection criteria by industry + SOTP/DCF/DDM/RIM/NAV summary
- [references/unit_rules.md](references/unit_rules.md) — Currency unit auto-detection logic + per-share conversion rules

## Gotchas
- Never hardcode `* 1_000_000` → use `per_share()`
- engine/ functions must be pure (no IO)
- AI proposes scenarios/probabilities, but user makes final decisions
