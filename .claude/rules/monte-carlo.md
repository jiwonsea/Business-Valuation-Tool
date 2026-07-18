---
paths: ["engine/monte_carlo.py", "engine/valuation_runner.py"]
---

# Monte Carlo Gotchas

- Monte Carlo DCF TV variation (`ev *= dcf_ev_sample/dcf_ev_base`) applies only to `ev_ebitda_part`. `ev_revenue_part` is added after TV adjustment — revenue-based optionality is independent of DCF terminal value assumptions.
- Monte Carlo multiples sampling uses **lognormal** (Damodaran standard: always ≥ 0, right-skewed). Parameters are derived from desired mean/std: `sigma_ln = sqrt(ln(1 + (s/m)²))`, `mu_ln = ln(m) - 0.5*sigma_ln²`. Falls back to normal+floor when `mu <= 0 or sigma <= 0`.
- Monte Carlo negative equity is preserved in full-distribution statistics (mean, percentiles). Histogram display filters negatives out. `pct_negative` counts true negatives before any filtering. Do NOT clamp `ps = max(ps, 0)` — this upward-biases all statistics. `MonteCarloResult.pct_negative` must be explicitly copied in `_mc_raw_to_result()` — omission silently defaults to 0.
- Per-scenario MC (`_run_monte_carlo` inner loop) must pass `cps_dividend_rate=vi.cps_dividend_rate`. Missing it defaults to 0.0, making effective IRR = full IRR (overstates CPS repayment when `cps_dividend_rate > 0`).
- Mixed-method SOTP Monte Carlo must use `effective_net_debt` (via `net_debt_override`), not `vi.net_debt`. PBV/PE segment equity values already embed net_debt — using full net_debt double-deducts.
- **MC DCF TV resampling** (`_run_monte_carlo` in `valuation_runner.py`) must use the same normalized FCFF (`last_p.nopat - last_p.delta_nwc`), not `last_p.fcff` — raw FCFF perpetuates capex deviations into all MC TV samples.
- **MC DCF TV spread guard**: `run_monte_carlo` enforces a minimum WACC-TG spread of 0.5% (`_MIN_SPREAD=0.005`) before computing sampled TV. Without it, samples where w−g < 0.1% produce TV 50x+ base, creating fat-tail distortion in MC distribution even when ratio is clipped to 3x.
