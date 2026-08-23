# HANDOFF → Codex — Fix `fetch_consensus_fy1_eps` (new Yahoo shape)

> **From**: Claude (Opus 4.8), 2026-07-08
> **To**: Codex (on a networked machine — this needs live Yahoo to validate)
> **File**: `earnings-forecast-engine/engine/generic_signal.py` → `fetch_consensus_fy1_eps`
> **Why**: it currently returns None for NVDA/Samsung, so `signal.consensus.direction`
> is always `"n_a"` and the forward-EPS adapter silently runs as v1 (bullish-biased)
> instead of the consensus-aware v2. Root cause (Codex finding): Yahoo moved the data
> from `earningsTrend.trend` to `earnings_estimate`.

---

## Goal
`fetch_consensus_fy1_eps(ticker)` returns the analyst-consensus **EPS for the same
fiscal year the model forecasts** (a float), or `None` only when consensus is
genuinely unavailable. No fabrication; None must stay a clean, silent fallback.

## What to change
1. **Use the current source.** Pull consensus from the present Yahoo/yfinance
   surface — most likely `yfinance.Ticker(ticker).earnings_estimate` (a DataFrame
   indexed by period: `0q`, `+1q`, `0y`, `+1y`; column `avg`). If EFE already has a
   `pipeline.yahoo_fetcher`, check whether it needs the same update and reuse it;
   otherwise call yfinance directly. Keep the whole body in `try/except` → `None`.
2. **Align the fiscal year (correctness, not cosmetic).** The gap is
   `model_fy1_eps` (`weighted_annual[0]`) vs consensus for **that same fiscal year**.
   Do NOT blindly grab `+1y`. Map the model's `weighted_annual[0].fiscal_year` to the
   correct Yahoo period (`0y` = current FY, `+1y` = next FY) so you compare like with
   like. A mismatched year makes the gap meaningless. If you cannot confidently align
   the year, return `None` rather than compare the wrong period.
3. **Robustness**: handle DataFrame vs dict, `NaN`/`None` → `None`, and missing
   periods → `None`. For KR tickers (`.KS`/`.KQ`) Yahoo consensus is often absent/low
   quality (EFE README) — returning `None` there is acceptable and expected.

## Validate (must do online)
- `python - <<'PY'` calling `fetch_consensus_fy1_eps` for **NVDA, AAPL, 005930.KS**:
  NVDA/AAPL should return a sane FY EPS (e.g. NVDA ~7, AAPL ~8, not 0/None); 005930.KS
  may legitimately be None.
- `python generic_cli.py --profile profiles/nvda.generic.yaml --json` → confirm
  `signal.consensus.direction` is now `above`/`below`/`in_line` (NOT `n_a`) and
  `signal.consensus.gap_pct` is populated.
- Confirm the orchestrator side flips: a name that was v1-bullish but sits **below**
  consensus should now read `neutral` (the v2 correction). Spot-check one.

## Tests (keep offline-safe)
- Add a unit test that monkeypatches the fetch to return a known DataFrame/dict and
  asserts `fetch_consensus_fy1_eps` extracts the aligned-FY `avg`. Do not hit the
  network in tests.
- Existing `investment-orchestrator` v2 tests already cover the mapping given a
  block; this only needs the fetch-extraction test on the EFE side.
- Run `pytest` in both repos → green.

## Acceptance
1. `fetch_consensus_fy1_eps("NVDA")` returns a real FY1 EPS online; `.KS` may be None.
2. Fiscal-year alignment is correct (model FY == consensus FY compared).
3. `generic_cli --json` emits a non-`n_a` consensus for names with data.
4. A below-consensus growth name now maps to `neutral` in the forward-EPS adapter.
5. Offline path still returns `None` cleanly (no crash, block still builds with `n_a`).
6. Both repos' test suites pass.

## Note for NEEDS_UPSTREAM.md
Leave the separate item (dated forecast-as-of history export for honest replay) as
already recorded — that is NOT part of this fix.
