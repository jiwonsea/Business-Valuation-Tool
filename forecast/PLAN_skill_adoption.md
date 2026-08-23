# PLAN — Finance-Skill Methodology Adoption

Date: 2026-07-10
Scope: `earnings-forecast-engine` (EFE) + `business-valuation-tool` (BVT)
Basis: `HANDOFF_skill_adoption.md`

## Feasibility verdict

Selective adoption passes. Wholesale replacement remains rejected.

The Cowork finance skills are prompt/methodology templates, not deterministic
calculation engines. EFE/BVT engines should stay authoritative for math,
backtests, valuation, and attribution. The useful parts are reporting structure,
reconciliation categories, and narrative discipline.

## Answers to Codex review questions

### 1. A1 data model

Optional per-segment actual driver fields are acceptable, with skip-if-absent.

Recommended shape:

```yaml
historical_segment_actuals:
  "2026Q1":
    dram:
      bit_growth_qoq: 0.60
      asp_qoq: 0.65
      hbm_share: 0.45
    nand:
      bit_growth_qoq: 0.12
      asp_qoq: 0.575
    other:
      revenue_growth_qoq: 0.01
```

Do not overload existing `historical_drivers`; it already feeds the margin chain
and backtest methodology. A1 must be a diagnostic input only. Absence should
return `None` / empty nested attribution and leave current backtest outputs
bit-identical.

Coupling risk exists only if these actuals are reused inside `run_backtest` or
forward projection. Keep them out of `SegmentAssumptions`, `HistoricalDriver`,
and forecast generation.

### 2. A1 exact-sum math

Exact-sum nested decomposition is feasible without a residual bucket, but only if
the nested block is scaled to the existing `contrib_revenue`.

Design:

1. Keep current `attribute_eps_error()` as the top-level source of truth.
2. Build a separate revenue-only bridge from modeled segment revenues to actual
   segment revenues.
3. Compute deterministic sub-effects in a fixed order, for example:
   segment mix/size, DRAM volume, DRAM ASP, HBM mix, NAND volume, NAND ASP, other.
4. Let raw sub-effects telescope to the revenue delta in revenue units.
5. Convert to EPS-error contribution by multiplying each raw sub-effect by:

```text
top_level.contrib_revenue / sum(raw_revenue_sub_effects)
```

If the denominator is zero or required actual drivers are missing, skip the
nested block. This preserves:

```text
sum(nested_revenue_contribs) == DriverAttribution.contrib_revenue
```

No residual bucket is needed if the nested bridge covers the same revenue delta.
If actual disclosure lacks enough fields to reconstruct segment revenue exactly,
do not force it; mark the nested block unavailable.

### 3. A4 BVT placement

Create `pipeline/reconciliation.py` in BVT and call it from
`pipeline/profile_generator.py` before YAML persistence in `--auto`.

Reason:

- Separate module keeps source comparison reusable from CLI, tests, and weekly
  automation.
- `profile_generator.py` is already the point where DART/EDGAR/yfinance facts
  are merged into a profile.
- Existing BVT pattern supports local deterministic validators with warnings and
  structured reports.

Default behavior should warn, not block. Block only for hard identity/unit
failures that can produce materially wrong per-share valuation, especially:

- share count mismatch above 25%,
- market cap implied by `price * shares` differing from fetched market cap by
  above 25% when both are present,
- revenue / OP unit mismatch above 100% where periods and definitions match.

For `--auto`, write reconciliation results into the profile under a
`data_reconciliation:` section and print warnings. Add a later `--strict-data`
flag if blocking becomes useful.

### 4. Priority and effort

Priority:

1. A4 BVT reconciliation gate — highest defect-prevention value; known shares
   bug class; moderate effort.
2. A2 EFE waterfall rendering — low risk, visible portfolio value; small effort.
3. A1 EFE nested revenue attribution — high narrative value but data-dependent;
   medium/high effort.
4. A3 narrative quality gate — useful, but false positives need care; small
   prompt/validator effort.
5. A5 one-off checklist — minor taxonomy/prompt polish; defer or fold into A3.

Cut or defer A5 as a standalone workstream. It is not worth its own implementation
session.

### 5. Accuracy risks

A3 false rejects are real, especially for Korean narrative. Use warnings first,
not hard rejection. Do not reject merely because a phrase appears; require a
combination of vague phrase plus missing number/evidence.

Additional A1 risk: manual actual driver fields can look more precise than they
are. Every nested revenue attribution row should carry `source` and `confidence`
or a simple `is_manual: true` flag in the rendered report.

Additional A2 risk: waterfall charts can imply causality. Label them as
post-mortem attribution / bridge, not forecast signal.

## Workstreams

### Workstream EFE-1: Waterfall rendering (A2)

Goal: render existing top-level attribution as Plotly waterfall charts without
changing engine outputs.

Files likely touched:

- `output/plotly_charts.py`
- `output/html_builder.py`
- `tests/test_plotly_charts.py`
- possibly `cli.py` only if attribution data is not currently passed to output

Verification:

- `pytest tests/test_attribution.py tests/test_plotly_charts.py -q`
- existing 9Q backtest metrics must remain bit-identical.

### Workstream EFE-2: Optional nested revenue attribution (A1)

Goal: add diagnostic-only nested segment revenue attribution when optional
historical actual drivers are present.

Files likely touched:

- `schemas/models.py`
- `pipeline/ir_loader.py`
- `engine/attribution.py` or new `engine/revenue_attribution.py`
- `tests/test_attribution.py`
- `profiles/sk_hynix.yaml` only after user approves manual actual fields

Rules:

- No changes to forward forecast math.
- No changes to `run_backtest` methodology assumptions.
- Skip gracefully when optional actuals are absent.
- Nested contributions must sum to existing `contrib_revenue`.

Verification:

- `pytest tests/test_attribution.py tests/test_backtest.py -q`
- compare serialized backtest result before/after for profiles without
  `historical_segment_actuals`.

### Workstream BVT-1: Cross-source reconciliation (A4)

Goal: detect DART/EDGAR/yfinance market-data mismatches before auto profiles
silently encode bad shares or units.

Files likely touched:

- `pipeline/reconciliation.py`
- `pipeline/profile_generator.py`
- `schemas/models.py` only if a typed reconciliation report is worth the churn
- `tests/test_pipeline.py` or new `tests/test_reconciliation.py`

Default mode:

- warn and persist report;
- block only hard identity/unit/share failures;
- keep strict blocking behind a future explicit flag if needed.

Verification:

- `pytest tests/test_pipeline.py tests/test_api_guard.py -q`
- synthetic fixture for 2x shares mismatch.

### Workstream Prompt-1: Narrative discipline (A3 + A5)

Goal: add prompt guidance and local warning validator for vague/unquantified
LLM commentary.

Files likely touched:

- EFE `ai/prompts.py` only for extraction/commentary prompts that actually
  generate narrative
- BVT `ai/prompts.py`
- BVT `ai/validators.py`
- relevant AI validator tests

Rules:

- Validator returns warnings first; no hard fail for Korean text.
- No extra LLM calls.
- Bump any prompt/cache version where cache keys depend on prompt text.

Verification:

- `pytest tests/test_validators.py tests/test_ai.py -q` in BVT
- EFE extractor tests if EFE prompt text changes.

## Recommended sequence

Start with BVT-1, then EFE-1, then EFE-2. Fold Prompt-1 into whichever repo is
already open after those two deterministic workstreams are green.

Suggested next prompt:

```text
F:/dev/Portfolio/business-valuation-tool 프로젝트. PLAN_skill_adoption.md의 BVT-1만 구현해줘. 먼저 현재 profile_generator 데이터 흐름을 읽고, pipeline/reconciliation.py + 테스트를 추가하되 기본 동작은 warn/persist로 해줘.
```
