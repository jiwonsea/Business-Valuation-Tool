# HANDOFF — Cowork Finance-Skill Adoption Feasibility (BVT + EFE)

Date: 2026-07-10 · Author: Cowork session · For: Codex feasibility review
Scope: both repos — `earnings-forecast-engine` (EFE) and `business-valuation-tool` (BVT)

## 1. Context and premise correction

User hypothesis: the Cowork `finance:financial-statements` skill is "more accurate and
efficient than our programs" and should be adopted.

**Finding: the premise does not hold as stated.** All `finance:*` skills were inspected
(full SKILL.md read for `financial-statements`, `variance-analysis`, `reconciliation`;
descriptions for the rest). They are **markdown prompt templates — zero computation
code**. They guide an LLM to format output and follow a methodology checklist. They have
no engine, no backtest, no determinism. For valuation/forecast math they are strictly
*less* accurate than BVT/EFE's pure-function engines (LLM freeform arithmetic vs tested
deterministic code). Wholesale replacement is rejected.

**What does hold:** the skills encode solid FP&A *methodology* (decomposition frameworks,
materiality thresholds, narrative standards, reconciliation categorization) that can be
ported into our code/prompts as structure — engine math untouched. Selective adoption is
the proposal below.

Note: EFE's `engine/attribution.py` already does exact telescoping lever attribution
(contributions sum to total error by construction). This is *stronger* than the skill's
residual-based price/volume split. Items below extend, not replace, it.

## 2. Candidate adoption items (for Codex feasibility review)

### A1 — EFE: segment-level P×V×Mix decomposition inside the revenue lever
- Source: `variance-analysis` skill (three-way volume/price/mix decomposition).
- Today: attribution treats revenue as a single lever. Proposal: decompose the revenue
  error into DRAM/NAND/other bit-volume vs ASP vs mix effects, nested under the existing
  telescoping structure (segment block must still sum to the revenue lever exactly —
  keep our exact-sum property, do not adopt the skill's residual allocation).
- Value: interview-grade narrative ("rev miss = 60% volume, 40% ASP"), directly serves
  the consensus-gap thesis.
- Risk/dependency: needs per-segment bit growth + ASP *actuals*. DART does not provide
  them; SK Hynix IR discloses bit growth QoQ in earnings calls → manual `assumptions:`
  entries in the profile (existing pattern). Feasibility question for Codex: acceptable
  as Optional profile fields with graceful skip when absent?

### A2 — EFE: waterfall/bridge rendering in HTML + MD reports
- Source: `variance-analysis` (waterfall methodology, bridge reconciliation table).
- Today: attribution numbers exist but no waterfall visual. Proposal: Plotly waterfall
  (a) forecast→actual EPS attribution per backtest quarter, (b) consensus→model gap.
  Include the reconciliation check (start + drivers = end) as a rendered assertion.
- Output layer only → zero accuracy risk. Keep single-file HTML < 5MB rule.

### A3 — Both repos: narrative quality gate for LLM-generated commentary
- Source: `variance-analysis` narrative checklist + anti-patterns (circular, vague,
  unquantified "timing"/"one-time", "various small items").
- Proposal: embed the checklist into (a) EFE report commentary template, (b) BVT `ai/`
  scenario-design / peer-rationale prompts, plus a lightweight validator (regex/keyword
  reject of anti-patterns) on LLM output before it reaches reports.
- Fits BVT's existing prompt/validator pair pattern. Respects LLM quota (no extra calls;
  validation is local).

### A4 — BVT: cross-source data reconciliation gate (DART vs Yahoo)
- Source: `reconciliation` skill (categorize differences: timing / definitional-unit /
  requires-investigation; thresholds; trending).
- Today: pipeline pulls DART + Yahoo/yfinance with known drift issues (e.g. GOOGL shares
  2x flag from 2026-07-06 review; EFE `.KS` consensus quality gated via `quality_notes`).
  Proposal: a `pipeline/` reconciliation step comparing overlapping fields (revenue, OP,
  shares, market cap) across sources; categorized diff report; threshold breach → warn
  or block `--auto` profile generation.
- Value: directly attacks a known bug class (shares 2x). Pure `pipeline/` (IO layer);
  engine untouched.

### A5 — (minor) one-off/adjustment checklist for earnings normalization
- Source: `financial-statements` period-end adjustments list (SBC, impairment, FX
  revaluation, restructuring, discontinued ops).
- Proposal: use as a structured checklist in BVT's AI earnings-normalization prompt and
  as EFE `quality_notes` taxonomy. Prompt-only change.

## 3. Rejected (domain mismatch — do not adopt)
`journal-entry`, `journal-entry-prep`, `close-management`, `reconciliation`'s bank/IC
workflows, `audit-support`, `sox-testing`: corporate close/controls processes, not
valuation/forecasting. `financial-statements` statement-generation workflow itself:
duplicates what DART/EDGAR already give us as actuals. HR skills: irrelevant.
Non-finance Cowork skills: `xlsx` (BVT already ships 7-sheet Excel via openpyxl),
`schedule` (BVT scheduler/ exists; sandbox lacks network). `skill-creator` — packaging
BVT/EFE methodology as a custom skill is a separate portfolio-presentation track, out of
scope here.

## 4. Questions for Codex
1. A1 data model: Optional per-segment actuals in profile YAML with skip-if-absent —
   consistent with backward-compat convention? Any coupling risk with the pinned
   backtest methodology assumptions (see "backtest↔forward coupling" open problem)?
2. A1 math: nested exact-sum decomposition design — confirm it can preserve the
   telescoping property (segment effects sum to revenue lever) without a residual bucket.
3. A4 placement: best hook point in BVT pipeline (`profile_generator` pre-write? separate
   `pipeline/reconcile.py`?) and whether breach should block or only warn under `--auto`.
4. Priority/effort ranking of A1–A5; anything to cut.
5. Any accuracy risk I missed (esp. A3 validator false-rejecting good Korean narrative).

## 5. Agreed workflow (user-defined)
1. This doc → Codex feasibility review (host).
2. If passed → write `PLAN_skill_adoption.md` (plan mode, fresh session per workstream —
   likely split: EFE A1+A2 / BVT A4 / A3+A5 prompts).
3. PLAN → Codex review → implement → pytest + `--dry-run` verify (9Q backtest must stay
   bit-identical for A2/A3/A5; A1 adds fields but must not move existing levers).
