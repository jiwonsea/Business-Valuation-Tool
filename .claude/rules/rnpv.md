---
paths: ["engine/rnpv.py", "engine/reverse_rnpv.py", "engine/quality.py", "output/sheets/rnpv.py"]
---

# rNPV Engine Rules & Gotchas

Risk-adjusted NPV for pharma/biotech pipeline valuation.

## Revenue Curve & Cash Flows

- **Revenue curve**: Ramp-up → Plateau → Decline (patent expiry). Three branches:
  - `existing_revenue >= peak_sales`: plateau at existing, then decline
  - `0 < existing_revenue < peak_sales`: ramp from existing to peak, plateau, then decline (Wegovy case)
  - `existing_revenue == 0`: ramp from 0 to peak, plateau, then decline
- **Decline base**: Decline always starts from `peak_sales` unless `existing_revenue >= peak_sales` (then from `existing_revenue`). Never from a mid-ramp value.
- **patent_expiry_years**: Total remaining commercial life — ramp + plateau + decline all fit within this window. NOT "years until decline starts." If ramp+plateau exceeds this value, decline phase is skipped (edge case, no current profiles trigger this).
- **cash_flows vs revenue_curve**: `DrugCashFlow.cash_flows` = after-tax operating profit (revenue × margin × (1-tax)). `revenue_curve` = raw revenue projection. Excel Revenue Curves sheet uses `revenue_curve`, not `cash_flows`.

## PoS, R&D, NPV

- **PoS override**: drug-level `success_prob` takes priority over `PHASE_POS` lookup table.
- **R&D cost**: `r_and_d_cost=0` means R&D is embedded in operating margin (no deduction). Setting both `r_and_d_cost > 0` AND high `default_margin` risks double-counting.
- **NPV discount**: `_npv()` starts at t=0 (first cash flow undiscounted). This is intentional — `launch_year_offset` handles pre-launch zeros, so t=0 is the launch year.
- **enterprise_value = pipeline_value**: `existing_revenue_value` is already included in `total_rnpv` (approved drugs have PoS=1.0). The `existing_revenue_value` field is a reporting-only subset — do not add it to `pipeline_value`.
- **PoS cap in reverse/sensitivity**: When scaling PoS uniformly, approved drugs (PoS=1.0) are already capped — only pipeline drugs' PoS can increase. This limits the range of achievable EV via PoS-only scaling when approved drugs dominate.

## Scenario Drivers

- **Scenario drivers**: `growth_adj_pct` adjusts peak sales, `wacc_adj` adjusts discount rate, `pos_override` dict (`{drug_name: 0-1}`) overrides per-drug PoS. All three are independent and composable.
- `pos_override` keys are drug name strings (exact match against YAML pipeline `name` field). Renaming a drug in YAML without updating scenario `pos_override` keys silently drops the override.

## Reverse rNPV & Sensitivity

- **Reverse rNPV**: `engine/reverse_rnpv.py` — binary search for implied PoS scale, peak-sales scale, and discount rate that reconcile model EV with market EV. Called from `cli.py:_attach_reverse_rnpv()` when primary_method=="rnpv" and market price available. Result stored in `ValuationResult.reverse_rnpv`.
- **rNPV Sensitivity**: `sensitivity_rnpv()` = discount rate × PoS scale 2D table (uses `sensitivity_primary` slot). `sensitivity_rnpv_tornado()` = per-drug ±20% peak sales impact on per-share value (stored in `ValuationResult.rnpv_tornado`).
- **Per-drug solo PoS**: `solve_implied_per_drug_pos()` uses direct algebraic solve (not binary search) — rNPV is linear in each drug's PoS: `implied_pos = gap / npv_i + base_pos`. O(1) total (single `calc_rnpv` call). Filter: `success_prob < 1.0`. Returns `solvable=False` when implied_pos outside [0, 1], with `max_ev_contribution` showing the drug's max marginal EV at PoS=1.0. Results are NOT additive across drugs.
- `reverse_rnpv.gap_pct = (model_ev - target_ev) / target_ev * 100`. `gap_pct < 0` ⟹ market > model ⟹ "시장 낙관". Label is counterintuitive — do NOT invert. Verified in engine/reverse_rnpv.py:307.

## Excel Output (output/sheets/rnpv.py)

- **Excel output**: rNPV produces two extra sheets — "rNPV Pipeline" (summary table + equity bridge) and "Revenue Curves" (year-by-year revenue per drug, chart-ready data).
- `output/sheets/rnpv.py` Peak Revenue and summary sections must iterate `rnpv.drug_results` (all drugs), not `drugs_with_curves` (subset that only includes drugs with computed revenue curves). `drugs_with_curves` silently omits early-stage pipeline drugs that have a PoS but no revenue curve.
- `rnpv_pct` calculation in `output/sheets/rnpv.py` uses `!= 0` guard (not `> 0`). When `total_rnpv < 0` (all drugs net-negative NPV), the `> 0` guard silently zeros all drug percentages; `!= 0` correctly computes negative proportions.

## Cross-Validation & Quality Score

- rNPV cross-validation: the first CV item is labeled `"SOTP (EV/EBITDA)"` but holds the rNPV primary EV (passed as `sotp_ev` to `cross_validate()`). The DCF entry is exactly `"DCF (FCFF)"` — used in `_RNPV_EXCLUDED_CV_METHODS` in `engine/quality.py` to exclude it from rNPV convergence scoring.
- **Quality score rNPV restructuring**: For `primary_method=="rnpv"`, `cv_convergence` (25pts) is NOT a single CV — it's `rnpv_weighted_cv` (0-10, DCF excluded) + `rnpv_pipeline_diversity` (0-8) + `rnpv_pos_grounding` (0-6) + `rnpv_scenario_coverage` (0-1, pos_override in ≥1 scenario). Similarly `market_alignment` splits into price gap (0-15) + `rnpv_reverse_consistency` (0-10). Standard `_cv_convergence_score()` is NOT called for rNPV. `format_quality_report()` in `engine/quality.py` handles both modes; called from `console_report.py`.
