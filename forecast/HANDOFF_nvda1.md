# HANDOFF — NVDA-1 Data Integrity (1a/1b/1c)

Date: 2026-07-11 · Session: Cowork · Scope: `PLAN_nvidia_application.md` §5
Workstream NVDA-1 only; `REVIEW_nvidia_codex.md` decisions binding.
Memory-path 9Q invariant verified UNCHANGED: `BacktestResult.model_dump_json()`
sha256 = `077ecb10986a5f2a7e81b31dc595ae47077b8ed7d6fb3ababfb1d5073891933c` ✓
(rev MAPE 8.99% / EPS MAPE 10.39% / bias −3.58%). Full suite: **164 passed**
(146 before + 18 new).

## 1. What shipped

### 1a — `pipeline/edgar_fetcher.py` (new)
- `fetch_companyfacts(cik)`: whole-blob per-CIK cache
  (`reports/.cache/edgar_companyfacts_CIK{cik:0>10}.json`), own UA
  (`SEC_EDGAR_USER_AGENT` env), 60s timeout, 3-try linear backoff, atomic
  write (tmp + `os.replace`). DART fetcher body NOT shared (per review).
- `iter_facts` preserves `start/end/fy/fp/form/filed/accn/frame`.
- `build_standalone_quarters`: Q1–Q3 from direct 3M facts with ALL required
  items (revenue·NI·diluted shares; COGS/EPS optional) from ONE accession —
  accessions tried in filed order, so the as-filed original wins and later
  split-adjusted comparatives are never mixed in.
- EPS facts are never selected as data (mixed-basis trap; old quarters can
  lack current-basis comparatives entirely). As-filed EPS kept as provenance.

### 1b — Q4 restoration + label contract + contiguity guard
- Q4 = 10-K annual − same-FY Q3 10-Q 9M (both ORIGINAL filings → no
  disclosure-vintage mixing; rev/NI are split-invariant flows). Q4 diluted
  shares = 4×FY − 3×9M with a 0.5×–2× plausibility guard against basis mixing.
- `model_label_for_period` (period-END-date keyed; companyfacts `fy/fp` tag
  the FILING, not the fact — unreliable): Jan-ending FY(N) Qq → model (N-1)Qq;
  the late-Jan quarter is the PREVIOUS calendar year's Q4. Dec-ending is the
  identity. Documented in both profiles.
- `generic_cli.backtest_generic` now REFUSES non-contiguous actuals (the old
  Q3→Q1 silent join) with a loud note instead of scoring a broken series.

### 1c — `split_history` + derived EPS + per-quarter shares
- `schemas/generic.py`: `SplitEvent {date, ratio}`, `GenericProfile.split_history`,
  `GenericActualQuarter.{period_end, diluted_shares}`. At load, when
  `diluted_shares` is present, `eps_diluted` is DERIVED =
  `net_profit × unit_scale / (as-filed shares × split_factor(period_end))` —
  stored EPS is ignored; real dilution/buyback preserved (fixed forward
  24.49B is NOT applied to history, per review #6). Legacy profiles without
  `diluted_shares` behave bit-identically.
- `profiles/nvda.generic.yaml` / `profiles/tsla.generic.yaml`: actuals fully
  regenerated from EDGAR as-filed originals — 27 contiguous quarters each
  (2019Q3..2026Q1, Q4s restored, wrong-year labels fixed), per-quarter as-filed
  diluted shares, accession-level provenance per row.
  NVDA splits: 4:1 2021-07-20, 10:1 2024-06-10. TSLA: 5:1 2020-08-31,
  3:1 2022-08-25.
- Tesla NI/EPS fixed with actual 10-Q/10-K values (old profile mixed restated
  comparatives and estimates; e.g. 2024Q2 1,400 → as-filed 1,478; 2021Q3 EPS
  0.48 → derived 0.48c basis corrected). FY2024 restatement (FY2025 filings:
  Q1 1129→1390, Q2 1478→1400, Q3 2167→2173) deliberately NOT taken — as-filed
  point-in-time actuals; FY2024 10-K total (7,091) matches the as-filed
  quarterly sum, so Q4 = 2,317 is vintage-consistent.
  Forward `weighted_avg_diluted` 3.5e9 (approx placeholder) → 3,538,000,000
  (latest as-filed, 2026Q1 10-Q).
- `scripts/build_generic_actuals.py` (new): regenerates an actuals block and
  FAILS unless (a) labels contiguous, (b) 4-quarter sums == FY facts for rev &
  NI, (c) NI/shares ≈ as-filed EPS per quarter. Both profiles verified green.

### New tests (18)
`tests/test_edgar_fetcher.py` — same-accession discipline incl. fall-through,
as-filed-vs-comparative selection, label contract (incl. early-May Q1 end,
Jan→prior-year Q4), Q4 = annual−9M, basis-mixing guard.
`tests/test_generic_contiguity.py` — Q3→Q1 join refused; year-boundary Q4→Q1
accepted; duplicate labels refused.
`tests/test_generic_split_normalization.py` — split factor compounding,
derived-EPS override, missing-period_end rejection, legacy passthrough, and
**no implied-share seams in the committed NVDA/TSLA profiles** (one basis,
adjacent ratio < 1.2, N=26 pairs scored).

## 2. Measurements (no targets were presumed — Codex: measure, don't assume)

Weighted FY EPS (forward, unchanged model): NVDA 2026 6.27 / 2027 2.36
(before == after); TSLA 2026 1.31→1.30 / 2027 0.53→0.52 (forward share fix).

| Backtest (1-step) | NVDA before | NVDA after | TSLA before | TSLA after |
|---|---|---|---|---|
| N | 19 (Q3→Q1 joins) | 26 (contiguous) | 19 | 26 |
| rev MAPE / naive RW | 14.2% / 18.5% | **9.9% / 13.9%** | 13.0% / 14.5% | **10.8% / 13.2%** |
| rev bias | −7.5% | −4.1% | −3.3% | +0.0% |
| EPS MAPE / naive RW | 46.9% / 67.4% | **95.0% / 30.6%** | 83.0% / 106.4% | **161.6% / 101.4%** |
| EPS bias | −45.8% | **+81.5%** | +24.8% | +114.2% |

Sub-window 2023Q2+ (post AI-supercycle regime break, N=12):

| | rev MAPE / bias | EPS MAPE / naive RW / bias |
|---|---|---|
| NVDA | 11.5% / −11.2% | **16.5% / 24.7% / −12.5%** |
| TSLA | 11.7% / +5.5% | 72.1% / 123.0% / +42.1% |

Interpretation (matches PLAN §3/§6 predictions):
- The old −45.8% EPS bias was indeed dominated by the mixed-basis artifact —
  with clean data the full-window bias FLIPS to +81.5%: today's base
  assumptions (op margin 62%) grossly overshoot pre-FY2023 quarters where
  NVDA's op margin was ~25–35%. That is the REGIME BREAK, now visible instead
  of hidden under a share-basis bug. Full-window EPS numbers are honest but
  not decision-useful; on 2023Q2+ the model beats RW on EPS (16.5% vs 24.7%)
  with single-digit-adjacent bias.
- Revenue MAPE improved and still beats RW after removing circularity (rev
  actuals are now official 10-Q, not FY-total splits) and fixing the joins.
- → NVDA-2 must implement split-window scoring (pre/post 2023Q1) or start the
  scored window at 2023Q2, as PLAN §6 already proposed.

## 3. Sandbox constraint + host follow-ups

The Cowork sandbox egress proxy 403-blocks `data.sec.gov` for processes; the
sanctioned web-fetch tool works. The caches in `reports/.cache/edgar_*.json`
are therefore **derived concept-slice caches** (blob-shaped, as-filed original
accessions only, window-filtered — see `_derived_note` inside each; the
generator's FY-sum identity check passed on both, so values are
internally consistent). `reports/.cache/` is gitignored, as with DART.

Host follow-ups (any order):
1. `SEC_EDGAR_USER_AGENT="name (email)"` in `.env`; delete the two derived
   caches; run `fetch_companyfacts` for CIK 1045810 / 1318605 to replace them
   with full audited blobs; re-run `scripts/build_generic_actuals.py` for both
   (expect identical actuals) and the seam tests.
2. TSLA as-filed EPS provenance (omitted from the derived cache): full blob
   makes `eps_diluted_as_filed` populate in the generator output.
3. NOTICED BUT NOT TOUCHING: `backtest_generic` model-EPS bridge still uses
   the FIXED forward share count for model EPS on historical quarters — fine
   for NVDA (24.4–25.4B range) but up to ~25% off for TSLA 2019–20; a
   per-quarter model-shares choice is NVDA-2 methodology territory.
4. NOTICED BUT NOT TOUCHING: aapl/msft/googl/amzn/meta/samsung `.generic`
   profiles still have gap-ridden actuals — the new contiguity guard now
   refuses their backtests (correct: those numbers were Q3→Q1-corrupted).
   Rebuild via `scripts/build_generic_actuals.py` when each is next touched.

## 4. Files changed
- new: `pipeline/edgar_fetcher.py`, `scripts/build_generic_actuals.py`,
  `tests/test_edgar_fetcher.py`, `tests/test_generic_contiguity.py`,
  `tests/test_generic_split_normalization.py`, `HANDOFF_nvda1.md`
- modified: `schemas/generic.py` (SplitEvent/split_history/derived EPS),
  `generic_cli.py` (contiguity guard), `profiles/nvda.generic.yaml`,
  `profiles/tsla.generic.yaml`, `reports/{nvda,tsla}_generic_forecast.md`
- untracked (gitignored): `reports/.cache/edgar_companyfacts_CIK*.json`
- memory path: zero diffs; 9Q sha256 match re-verified post-change.
