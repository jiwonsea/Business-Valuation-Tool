---
paths: ["db/**/*.py", "backtest/**/*.py", "calibration/**/*.py"]
---

# DB, Backtest & Calibration Gotchas

## Setup & Silent Degradation

- `get_client()` returns `None` silently when `SUPABASE_URL`/`SUPABASE_KEY` are missing. DB-dependent features (backtest, save_valuation) degrade silently — check `.env` exists before debugging "empty results."
- Ad-hoc DB probes (`python -c`, one-off `scripts/*.py`) must call `from dotenv import load_dotenv; load_dotenv()` before `get_client()` — CLI entry points load .env automatically but ad-hoc probes don't, so `get_client()` returns `None` silently and debugging misreads as "table empty."

## Persistence Path Asymmetry

- Valuation entry paths diverge on DB persistence: `orchestrator.run_from_profile` (called from `cli.py --profile`) calls `_save_to_db`; `pipeline.profile_generator.auto_analyze` (called from `cli.py --company` and `scheduler/weekly_run.py`) does NOT. Both produce identical `ValuationResult`, only persistence differs. Any new save/snapshot/log-to-DB call must be wired into BOTH paths, or the asymmetry documented explicitly. Weekly pipeline's missing snapshots trace to this gap.

## Schema / Migration Drift

- `db/migrations_backtest.sql` owns the `prediction_snapshots` schema. When adding new columns written by `db/backtest_repository.py` to `prediction_snapshots`, add a corresponding `ALTER TABLE prediction_snapshots ADD COLUMN IF NOT EXISTS` to `migrations_backtest.sql` in the same commit — missing columns cause the save to log an exception and return `None`. Committing the migration file does NOT apply it to Supabase — manually run in Supabase SQL Editor or execute `supabase db push` after commit. Otherwise runtime fails with PGRST204 'column not found' (sk_ecoplant.yaml 2026-04-15 regression).
- Supabase column drift check: `.select("*")` silently omits columns missing from the live DB, and `snap.get("col")` returns `None` — hiding schema/migration drift. To verify a column exists, `client.table(t).select("col_name").limit(1).execute()` — raises PostgREST 42703 when absent. Seen with `prediction_snapshots.primary_method` (defined in `migrations_backtest.sql` but not applied to prod), causing calibration to bucket every record as `sector='unknown'`. Column existence (no 42703) does not prove save writes it — the `save_*` row dict may omit the field, so the column stays at its DEFAULT. Verify by reading a freshly-written row and asserting the expected non-default value. Seen: `prediction_snapshots.market_signals_version` column added but `save_prediction_snapshot` row dict omits it → all snapshots stay at 0.
- `getattr(result, "x", 0) or 1` truthy-coalescing erases an explicit `0`. For version/state int fields where 0 is meaningful (e.g. `market_signals_version`), use `v = getattr(result, "x", None); v = 1 if v is None else v`. Seen in `save_prediction_snapshot` — coerced legitimate 0 into 1, silently relabeling pre-Phase-4 A/B test rows.

## Buckets & Backtest Reads

- Two bucket functions exist and are NOT parallel: `infer_valuation_bucket` (engine/method_selector.py) derives the rich bucket from live `ValuationInput` (primary_method + industry + has_holding_structure + has_optionality_segments) and is written to `prediction_snapshots.valuation_bucket` at save time; `classify_bucket` (backtest/buckets.py) only reads that stored value back. Because the migration added the column with DEFAULT `'plain_operating'`, snapshots saved before commit `1668243` silently carry `plain_operating` even when they should be `financials` / `holding_governance_sensitive` / `optionality_heavy` — backtest bucket breakdowns are biased toward `plain_operating` until pre-feature rows are re-run through the current pipeline.
- `backtest_outcomes.analysis_date` and `prediction_snapshots.analysis_date` both carry the same date (outcomes copies at insert time). When `list_outcomes_needing_refresh` inner-joins snapshots, read from the joined path — the snapshot is authoritative; the outcomes copy can drift if anyone backfills or rewrites it. The join becomes inert if the parser reads the top-level outcomes column.
- PostgREST paged fetches (`.range(offset, end)` loops) must emit a truncation warning when `max_rows` cap is hit without a short page. Python `while...else` detects this: the `else` branch runs only when the loop exited via condition, not `break`. Silent cap replacement is just a different silent-truncation bug. Seen in `db/backtest_repository.list_outcomes_needing_refresh`.

## Calibration

- `calibration.tuner._baseline_probs_from_records` must aggregate PER-RECORD role mass (sum probs within each role per record, then mean across records). Per-scenario averaging undercounts `base` when a profile has 4+ scenarios collapsing multiple entries into `base` — e.g. probs 10/20/30/40 become base=(20+30)/2=25, total 75 instead of 100, distorting baseline_mape, shift size, and the recommendation gate.
- `calibration.walk_forward.tune_walk_forward` aggregate — suppressed folds carry `test_mape=None` by contract; the mean must fall back to `baseline_test_mape` (docstring: "suppressed folds contribute baseline test MAPE only"). Dropping `None` silently biases `mean_test_mape` and `overfitting_gap` toward only the folds that emitted a recommendation.
- Weight/ratio `[0,1]` range checks must use `math.isfinite(w)` guard first. `w < 0 or w > 1` returns False for NaN/inf (all NaN comparisons are False), silently ingesting poisoned values into shrinkage/aggregation. Seen in `calibration/driver_shrinkage.py`.
