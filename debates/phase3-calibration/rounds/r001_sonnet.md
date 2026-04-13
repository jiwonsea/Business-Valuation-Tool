# Sonnet — Pragmatic Implementer

## Q1: knob — (b) sc.prob weights only

Tuning sc.prob is a single float-per-scenario change that maps cleanly to the existing `Σ(post_dlom × sc.prob/100)` aggregation in scenario.py, costs ~5 lines of grid search code, and is identifiable at N=10–100 without multicollinearity — beta and active_driver weights interact via the dampening formula (√N/N), making joint optimization a 3-surface problem that requires 300+ samples before gradient direction is stable.

**Failure mode:** If scenario probs are already reasonable but betas are systematically miscalibrated for a sector (e.g., tech WACC betas too large), prob-only tuning will compensate by compressing the bull/bear spread, producing narrower CIs that look accurate on MAPE but fail the interval score (coverage_rate will drop below 50%).

---

## Q2: metric — MAPE (primary) + coverage_rate from calc_interval_score (secondary)

Both already exist as pure functions in metrics.py — zero implementation cost. MAPE on predicted_value_native vs actual price is the most legible number for a human report ("we were off by X% on average"). Coverage_rate from calc_interval_score catches the case where the point estimate improves but the scenario spread becomes pathologically narrow. Sharpe-like alpha requires a benchmark portfolio and market-neutral assumptions that don't hold for fundamental valuation; hit-rate/direction is too coarse to discriminate between a good calibration and a lucky coin flip at N=30.

**Failure mode:** Using MAPE alone and ignoring coverage_rate will let you declare success while bull/bear scenarios converge to a single point — the report will show tight intervals that never bracket actuals.

---

## Q3: min sample — 10+ for T+3/T+6m, no output suppression (always show + uncertainty flag)

Suppressing output entirely until N=30 means the calibration report is empty for 6–12 months. At N=10 MAPE and coverage_rate are noisy but directionally useful — flag them with a low-confidence warning in the YAML report header rather than refusing to print. The T+12m 30+ threshold is appropriate for the calibration curve (calc_calibration_curve already hard-codes min_total_observations=30), but that is one function; overall report output should not be gated on it.

**Failure mode:** A strict "no output until N=30" rule on T+12m means the first actionable calibration report arrives 12–18 months after launch — by which time users have ignored the tool or tuned probs manually with no record, making the calibration data contaminated.

---

## Q4: out-of-scope — ML models AND walk-forward CV automation AND driver catalog auto-discovery (all three)

Real-time recompute is moot since automation is report-only by locked decision. ML models require labeled training sets we don't have. Walk-forward CV automation is 3–4 weeks of infra (split logic, re-run harness, result storage) — the 1–2 week budget covers only a single static backtest pass. Driver catalog auto-discovery is a Phase 5+ research task. Keep this phase to: read BacktestRecords → compute MAPE + coverage_rate → grid search sc.prob → emit YAML diff report.

**Failure mode:** Including walk-forward CV "just the scaffolding" will consume the entire 2-week budget on split/harness plumbing before a single calibrated number is produced.

---

## Builder's note

The metrics infrastructure is already solid — calc_forecast_price_error, calc_interval_score, and calc_calibration_curve are all pure functions ready to call. The practical bottleneck the other voices likely underweight is data volume per bucket: with market × sector × horizon slices, a corpus of 80 BacktestRecords might yield only 8–12 per bucket after filtering to `is_listed`. That means the sc.prob grid search runs on 8 points at most — which is actually fine for a 3-scenario system (bull/base/bear probs sum to 100, so there's only one free parameter per scenario pair). The real risk is not overfitting but under-differentiation: sector A and sector B may produce identical optimal probs because the sample is too small to separate them. The report must surface bucket N prominently so the human reviewer knows when they're looking at signal vs noise.
