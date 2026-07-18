# CODEX PROMPT — Round 2 (unblocked: DART key + Yahoo SSL fixed)

Paste into a fresh Codex session on the HOST. Round 1 wired the reachable logic;
this round finishes the three items that were blocked on credentials/environment,
now fixed. Read `NEXT_SESSION_reliability_automation.md` +
`PROMPT_codex_reliability_automation.md` for full context. Guardrails unchanged:
never auto-execute orders; fail → abstain; no fabricated data; keep tests green.

## Two blockers were fixed in code this session — verify then use
1. **DART key now loads.** `EFE/pipeline/dart_fetcher.py` calls
   `load_dotenv(repo_root/.env)` at import (existing env wins). Both `BVT/.env`
   and `EFE/.env` hold a real 40-char `DART_API_KEY`. Confirm:
   `python -c "import pipeline.dart_fetcher, os; print(bool(os.getenv('DART_API_KEY')))"`
   → True. If your host shell doesn't auto-load .env, this now covers it.
2. **Yahoo SSL cert path fixed.** `EFE/engine/cyclical_drivers/public_feeds.py`
   now calls `ensure_ssl_env()` (ASCII-safe CA bundle) BEFORE importing yfinance —
   the Korean-home-path curl_cffi cert failure. Verify a real fetch:
   `python -c "from engine.cyclical_drivers.public_feeds import fetch_yahoo_monthly as f; print(len(f('crude_wti', period='2y')))"`
   → non-zero. If still failing, check `CURL_CA_BUNDLE`/`SSL_CERT_FILE` point at the
   ASCII copy and that `C:\temp\earnings_forecast\cacert.pem` is writable.

## Task A — Korean DART window expansion (Item 1, was blocked on the key)
Samsung/SK Hynix generic actuals stayed n=3. With the key now loading:
1. Fetch independent reported quarters via `pipeline/dart_fetcher.py` and expand
   Samsung (+ any KR generic) `actuals` to an expanding window up to ~20 (min 8) —
   independent reported quarters, NOT annual÷4.
2. Regenerate the profile + JSON/MD reports; confirm `n>=8`, full + trailing-8Q
   skill populated, and `skill_pass` reflects real dual-window skill.
3. Do the SK Hynix memory-path dual-skill parity (trailing-8Q + n in
   `skill_metrics.compute_skill` / `BacktestSkill`) if not already done.

## Task B — Cyclical public-data pilot (Item 2, was blocked on SSL)
1. With SSL fixed, run the public feeds (crude, HRC/iron ore, LME metals) and
   build `DriverInputs` for one pilot (steel or oil_gas — fully public).
2. Calibrate `default_passthrough` on the ≥8Q backtest; the skill gate decides —
   it must beat naive or the name abstains. Keep paywalled series as explicit gaps
   (`public_feeds.EXPLICIT_GAPS`); do not fabricate.
3. Confirm the memory path still reproduces existing SK Hynix output.

## Task C — Earnings-driven re-seed (Item 4, remaining)
Adjudicator (`schedule/refresh_gate.py`) + wiring in `schedule/refresh.py` are in.
Finish the actual re-seed: on DUE, fetch the new quarter's actuals (KR 잠정실적 +
DART/EDGAR now that the key loads) → re-seed EFE/BVT profile → re-run decide →
gate + Codex eval → `adjudicate_refresh`. Wire `earnings_calendar.build_universe`
to real earnings dates. Verify: passing re-seed = confident card; failing gate =
neutral HOLD + persisted freshness + no order.

## Task D — Verify two gate false-negative risks (Item 3 refinement)
The gate correctly abstains on optionality DCF/peer gaps and un-curated KR names —
leave those. But check for over-conservatism against REAL cross-vals:
1. `valuation_runner._peer_median_per_share` filters non-DCF cross-vals with a
   positive `per_share`. Confirm the abstaining names actually have per-share
   cross-vals; if any are EV-only, add an EV→equity→per-share bridge so "missing
   peer median" isn't a false block.
2. The 5% segment-reconciliation tolerance: confirm real SOTP profiles include the
   "other/elimination" residual in the segment sum before a miss becomes a block.
   Widen tolerance or include the residual if legitimate profiles false-fail.
Add a test for whichever you change. These only affect over-conservatism (never
capital), so bias toward keeping the gate strict when in doubt.

## Task E — Diagnose the Stop hook (exited code 1)
Round 1 ended with a Stop-hook failure. It is NOT a syntax error in the new files
(verified valid). Run the hook's command directly (full test suite or lint/format
gate), capture output, and report the real cause. Fix if it's a genuine regression;
otherwise note it's a pre-existing/unrelated failure.

## Report back
Per task: commands run, real fetch counts (DART quarters, Yahoo points), test
results, calibration/threshold decisions, and the Stop-hook root cause.
