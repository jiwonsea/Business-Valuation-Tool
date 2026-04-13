# Debate: Phase 3 Calibration Spec — 4 unresolved decisions

## User-locked decisions (NOT debated)
- Ground truth: realized stock price T+3/6/12m (collected by `backtest/price_tracker.py`)
- Scope: Market(KR/US) × Sector common parameters (NOT per-ticker)
- Automation: report-only, manual yaml application
- Scenario engine: news-driven (NewsDriver beta + active_drivers weight + sc.prob)

## Engine architecture (verbatim)
- `engine/drivers.py`: `NewsDriver.effects: dict[field, beta]`; `ScenarioParams.active_drivers: dict[driver_id, weight 0~1]`. Aggregation `Y=Σ(weight×beta)` with √N/N dampening.
- Tunable fields: wacc_adj, growth_adj_pct, terminal_growth_adj, market_sentiment_pct, ev_multiple (absolute), ddm_growth (absolute)
- `engine/scenario.py`: final = Σ(post_dlom × sc.prob/100), typically 3 scenarios
- `backtest/models.py`: `ScenarioSnapshot` per-scenario, `BacktestRecord` pairs with realized prices
- `backtest/metrics.py`: MAPE/RMSE pure functions exist
- Sample size: realistically 10–100 records per (market×sector×horizon) bucket

## 4 questions

### Q1: Tuning knob
Pick which to tune among: (a) `NewsDriver.effects` beta, (b) `sc.prob` weights, (c) `active_drivers` weight, (d) all three hierarchically (beta as sector prior, prob/weight per-name fine-tune). Consider identifiability with 10–100 samples, overfitting, interpretability, scope creep (we're sector-level, not per-ticker).

### Q2: Success metric
Pick from MAPE/RMSE / Hit-rate (direction) / Scenario coverage (95% CI hit) / Sharpe-like (signal alpha). Multi-select ok. Justify against T+3/6/12m horizons and "report for human" use case.

### Q3: Minimum sample threshold
30+ × 12m elapsed / 10+ T+3-6m / no threshold (always output + uncertainty). Statistical power vs user utility.

### Q4: Out-of-scope (this phase)
Pick which to exclude: ML models / real-time recompute / walk-forward CV automation / driver catalog auto-discovery. We want a phase that ships in 1–2 weeks.

## Required output per model (≤500 words total across all 4)
For each Q: recommendation + 1-line reasoning + one specific failure mode if wrong choice.
