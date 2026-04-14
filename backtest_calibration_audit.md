## db/backtest_repository.py
- `db/backtest_repository.py:59`  
  ` "market_signals_version": getattr(result, "market_signals_version", 0) or 1` forces any falsy value, including an explicit `0`, to be written as `1`. That breaks the documented contract where `0` means “pre-Phase 4 / no signals”, so A/B backtests against legacy rows will be silently mislabeled.  
  Suggested fix direction: preserve an explicit `0` and only default when the attribute is actually missing/`None`.  
  Severity: `P0`

- `db/backtest_repository.py:167-170`  
  `update_backtest_prices()` returns `True` without checking whether the update matched any row:  
  `client.table("backtest_outcomes").update(price_data).eq("id", outcome_id).execute(); return True`  
  If `outcome_id` is wrong, the row was deleted, or the backend returns zero affected rows, callers treat the refresh as successful and keep going with stale data.  
  Suggested fix direction: inspect the response and fail when no row was updated.  
  Severity: `P1`

- `db/backtest_repository.py:214-216`  
  `list_outcomes_needing_refresh()` hard-caps results with `.limit(200)` and has no pagination. If there are more than 200 overdue rows, everything after the first page is silently skipped and never refreshed by callers that invoke this once per run.  
  Suggested fix direction: page until exhaustion or make the caller drive pagination explicitly.  
  Severity: `P1`

## db/migrations_backtest.sql
- No findings.

## backtest/models.py
- No findings.

## backtest/metrics.py
- `backtest/metrics.py:262`  
  `bin_width = 100.0 / n_bins` has no guard for `n_bins <= 0`. A caller passing `0` or a negative value raises at runtime instead of returning a clear validation error.  
  Suggested fix direction: validate `n_bins >= 1` at function entry and raise a targeted `ValueError`.  
  Severity: `P2`

## calibration/grid.py
- No findings.

## calibration/tuner.py
- `calibration/tuner.py:145-151`  
  `_baseline_probs_from_records()` computes the baseline as the mean `prob` of scenarios inside each role:  
  `out[role] = (sums[role] / counts[role]) if counts[role] else 0.0`  
  For 4+ scenario profiles, multiple scenarios collapse into `"base"`, so averaging undercounts that role’s total probability mass. Example: probs `10/20/30/40` become `bear=10, base=(20+30)/2=25, bull=40`, summing to `75` instead of `100`. That distorts `baseline_mape`, shift size, and the recommendation gate.  
  Suggested fix direction: aggregate per-record role mass first, then average normalized bull/base/bear totals across records.  
  Severity: `P0`

## calibration/walk_forward.py
- `calibration/walk_forward.py:120-123, 181-197`  
  `_evaluate_on_test()` returns `(None, baseline_mape)` when a recommendation is suppressed, and `tune_walk_forward()` then excludes that fold from `mean_test_mape`/`overfitting_gap` by filtering out `None`. That contradicts the docstring (“suppressed folds contribute baseline test MAPE only”) and biases aggregate test performance toward only folds that emitted recommendations.  
  Suggested fix direction: use baseline test MAPE as the fold’s `test_mape` when no recommendation is emitted, or track separate aggregate series explicitly.  
  Severity: `P0`

- `calibration/walk_forward.py:83-100`  
  Splits are built by slicing a date-sorted list, but nothing prevents the same `analysis_date` from appearing on both sides of a fold boundary. With multiple records on one day, train and test are no longer “strictly earlier vs later”, which leaks same-date information into the train slice.  
  Suggested fix direction: advance fold boundaries on date changes so a single `analysis_date` never straddles train/test.  
  Severity: `P1`

- `calibration/walk_forward.py:399-402`  
  CLI `main()` runs `tune_walk_forward(listed, ...)` over all listed records at once instead of per `(market, sector)` bucket. That produces one mixed recommendation/score across heterogeneous buckets, which is inconsistent with the tuner/report contract elsewhere and can hide opposing bucket-level behavior.  
  Suggested fix direction: bucket records first and run walk-forward per bucket.  
  Severity: `P1`

## calibration/driver_shrinkage.py
- `calibration/driver_shrinkage.py:118`  
  `weight=_clip01(weight)` silently clamps malformed YAML weights into `[0, 1]`. If a profile accidentally ships `1.5` or `-0.2`, calibration proceeds on altered data with no error, producing recommendations from inputs that never actually existed in the profiles.  
  Suggested fix direction: treat out-of-range weights as invalid input and surface a warning/error instead of mutating them silently.  
  Severity: `P1`

## calibration/report.py
- No findings.
