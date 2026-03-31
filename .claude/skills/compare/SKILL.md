# Compare Skill

## Description
TRIGGER when: user mentions "비교해줘", "A vs B", "peer 대비 어떤지", "업종 평균 대비", "이전 분석과 비교", "멀티플 비교표", "compare", "cross-company comparison", "vs previous analysis".
DO NOT TRIGGER when: single company valuation (→ /valuation), profile creation (→ /profile).

## Overview
Compares valuation results across multiple companies or across time periods for the same company. Uses YAML profiles, DB-stored results, or current session results as comparison sources.

## Comparison Types
1. **Cross-sectional** — Same period, different companies (Peer comparison)
2. **Time-series** — Same company, different periods (assumption change tracking)
3. **Methodology** — Same company, different methodology results (deep cross-validation)

## Workflow
1. Identify comparison targets (profile files / DB query / current session)
2. Determine comparison type (cross-sectional / time-series / methodology)
3. Extract key metrics → generate comparison table
4. Analyze difference drivers + present insights

## File References
- [references/comparison_metrics.md](references/comparison_metrics.md) — Available metrics list and interpretation guide

## Gotchas
- When comparing companies with different units, must unify units first. If `currency_unit` is "백만원" vs "억원", absolute value comparison is impossible.
- If `SUPABASE_URL`/`SUPABASE_KEY` are not set on DB query, graceful skip. Don't throw errors; inform "DB not connected".
- In peer multiple comparison, distinguish `peer_stats.applied_multiple` from `ev_ebitda_median`. Applied is the actually-used value; median is the statistical value.
- In time-series comparison, if `analysis_date` differs, macro environment (interest rates, ERP) may also differ. Don't attribute WACC changes solely to company factors.
