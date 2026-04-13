# Phase 3 — Calibration Infrastructure (SPEC)

**Status:** spec confirmed 2026-04-13. Implementation is a separate session.
**Predecessor commit:** `2203856` (Phase 1+2 complete, 578 tests pass)

## Background
Phase 1 (engine audit) and Phase 2 (`engine/distress.py`, scenario improvements) shipped. The remaining backlog item — "calibration infrastructure" in `memory/project_valuation_tool_audit.md` — has no concrete spec. Phase 3 closes that.

The valuation engine is already news-driven via `engine/drivers.py`:
- `NewsDriver.effects: dict[field, beta]` defines per-driver causal coefficients.
- `ScenarioParams.active_drivers: dict[driver_id, weight 0~1]` selects which drivers fire per scenario at what intensity.
- Aggregation: `Y = Σ(weight × beta)` with √N/N correlation dampening.
- `engine/scenario.py` weights scenarios by `sc.prob` and sums.

Backtest infra (`backtest/{models,metrics,dataset,price_tracker,report}.py`) already captures `ScenarioSnapshot` per analysis and joins with realized prices at T+3/6/12m.

## Goal
Produce a calibration **report** that recommends adjustments to scenario probabilities (`sc.prob`) at the **market × sector** level, using realized stock prices as ground truth. Humans manually promote recommendations into `profiles/*.yaml`.

## Locked decisions (user-confirmed in interview)

| Item | Decision |
|---|---|
| Ground truth | Realized stock price T+3/6/12m (already collected by `backtest/price_tracker.py`) |
| Scope | Market(KR/US) × Sector common parameters — NOT per-ticker |
| Automation | Report-only. Profiles updated manually. Pipeline does not auto-write yaml |
| Scenario engine | Already news-driven via `NewsDriver` + `active_drivers` + `sc.prob` |

## Decisions resolved by 6-model cross debate
Full debate transcript: `debates/phase3-calibration/`. Vote tally + dissent in `debates/phase3-calibration/synthesis.md`.

### Tuning knob → `sc.prob`
Tune Bull/Base/Bear probability weights at the (market × sector) level. Beta tuning and `active_drivers` weight tuning are deferred to Phase 4.
- **Why:** beta lives inside √N/N dampening, requiring N>300 for stable gradients. With realistic bucket size 10–30 records, only `sc.prob` is identifiable (one free parameter per scenario pair).
- **Range constraint:** each scenario prob ∈ [5, 90], sum-to-100 enforced.
- **Dissent (preserved):** Gemini and Codex argued for beta tuning citing structural identifiability — valid once N grows. Backlog entry added below.

### Success metrics → MAPE (primary) + coverage_rate (secondary)
- **MAPE** on `predicted_value_native` vs realized price — primary optimization target. Already implemented in `backtest/metrics.py`.
- **coverage_rate** from `calc_interval_score` — secondary check that 95% scenario range actually brackets realized prices. Catches the failure where MAPE improves by collapsing bull/bear spread.
- **RMSE + hit-rate** — reported as diagnostics in the report header, not optimization targets.
- **Why:** all four debaters voted MAPE; coverage_rate prevents pathologically narrow CIs that pure MAPE rewards.

### Minimum sample threshold → tiered, no hard suppression
| Tier | Condition | Confidence label |
|---|---|---|
| stable | N ≥ 30 with T+12m elapsed | `stable` |
| preliminary | N ≥ 10 with T+3 or T+6m elapsed | `preliminary` |
| insufficient | N < 10 | `insufficient` (recommendations omitted, raw N reported) |

The existing `calc_calibration_curve` internal `min_total_observations=30` gate stays as-is, but the overall report is not gated on it.
- **Why:** blocking output until 12m matures means no actionable report for 12–18 months. Synthesis of Qwen's tiered approach + Sonnet's always-emit-with-flag.

### Out of scope (this phase)
Explicitly **excluded**:
- ML models (XGBoost / NN / Bayesian inference)
- Walk-forward CV automation (split logic, re-run harness, result storage)
- Driver catalog auto-discovery (no new `NewsDriver` ids generated)

Real-time recompute is moot — already excluded by locked report-only decision.
- **Why:** all three are scope explosions that consume the 1–2 week budget on plumbing instead of shipping.

## Architecture sketch

### New module: `calibration/`
```
calibration/
├── __init__.py
├── tuner.py          # grid search over sc.prob per (market, sector)
├── grid.py           # bucket aggregation: BacktestRecord → (market, sector, horizon) groups
├── report.py         # emit YAML diff report (current vs recommended)
└── tests/
```

### Interfaces with existing code
| New module function | Reads from | Writes to |
|---|---|---|
| `grid.bucket_records()` | `backtest/dataset.py` (load BacktestRecords) | in-memory groups |
| `tuner.search_sc_prob()` | `backtest/metrics.py` (MAPE, coverage_rate) | per-bucket optimal probs |
| `report.emit_yaml_diff()` | `profiles/*.yaml` (current values) | `output/calibration/YYYY-MM-DD.md` |

### Data flow
```
BacktestRecords (existing)
    → bucket by (market, sector, horizon)
    → for each bucket: grid search sc.prob (∈[5,90], sum=100, step=5)
    → loss = MAPE; secondary check: coverage_rate ≥ 60%
    → tag with confidence tier (stable/preliminary/insufficient)
    → emit markdown report: current sc.prob vs recommended, with diff and confidence label
    → human reads report, manually edits profiles/*.yaml
```

### What we do NOT add
- No CLI command for auto-apply.
- No new schema fields in `profiles/*.yaml`.
- No new database tables (BacktestRecords table already exists).
- No new external API calls.

## Verification (for the implementation session)
1. Unit tests for `calibration/tuner.py`: deterministic grid search on synthetic 30-record bucket recovers planted optimal probs within ±5pp.
2. Unit tests for `calibration/grid.py`: bucket boundaries correctly partition known fixture records.
3. Integration test: full pipeline on existing test profiles produces a non-empty report with at least one `stable`-tier recommendation.
4. Smoke run: `python -m calibration.report` against current `output/backtest/` data produces report under `output/calibration/`. Manual review confirms recommendations are sensible vs known sector behavior.
5. All 578 existing tests still pass (no regression in engine/backtest modules).

## Phase 4 backlog (NOT this phase)
- Beta tuning of `NewsDriver.effects` once per-bucket N exceeds 300.
- `active_drivers` weight tuning with shrinkage prior toward sector mean.
- Walk-forward CV harness for honest out-of-sample validation.
- Bayesian hierarchical model: sector-level beta prior + per-name prob fine-tune.

## Appendix: 6-model cross debate raw outputs
- `debates/phase3-calibration/context.md` — debate setup
- `debates/phase3-calibration/rounds/r001_gemini.md`
- `debates/phase3-calibration/rounds/r001_codex.md`
- `debates/phase3-calibration/rounds/r001_qwen.md`
- `debates/phase3-calibration/rounds/r001_sonnet.md`
- `debates/phase3-calibration/synthesis.md` — vote tally and dissent
