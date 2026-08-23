# HANDOFF — NVDA-2 stage 2a: skill metrics + regime windows

Date: 2026-07-21
Scope: `PLAN_nvda2.md` rev-1 §2a only
Baseline: `2ac4d58`; docs housekeeping commit `3710248`

## 1. Delivered contracts

- Generic backtest rows map 1:1 to shared `SkillRow`; `compute_skill` remains
  unchanged. Legacy MAPE fields remain percent while `skill` MAPE fields remain
  0–1 ratios. The report owns the single ratio-to-percent formatting site.
- `GenericProfile.regime_break_quarter` is optional and `extra="forbid"`
  remains active. NVDA/TSLA set `2023Q2`, with the AI-supercycle sourcing
  comment required by `REVIEW_nvda2_codex.md` §1.2.
- Profiles with a regime break emit `windows.full/pre_break/post_break`; each
  contains rows, `n`, `n_eps`, percent MAPE/bias, and ratio-based skill.
  Profiles without the field emit no `windows` key.
- The generic signal uses post-break as its primary skill window and takes its
  trailing 8Q from inside post-break. Full-vs-primary disagreement is explicit.
  Profiles without regime windows retain full/trailing behavior.
- Historical model EPS uses prior-quarter as-filed diluted shares adjusted to
  the current split basis. Legacy rows without shares explicitly fall back to
  the fixed forward count. The forward forecast still uses its fixed share
  assumption.
- Consensus-dependent skill fields are `None`/N=0 in stage 2a.

## 2. Verification

### Tests

| Check | Before | After |
|---|---:|---:|
| Full pytest | 164 passed | 173 passed |
| Added tests | — | 9 |
| Targeted 2a + adjacent suites | — | 27 passed |

`python -m pytest -q`: **173 passed in 25.77s**.

New tests cover NVDA/TSLA legacy-to-skill unit equivalence, exact row/count/APE
partition identity, 2023Q2 boundary placement, signal primary/fallback behavior,
split-adjusted prior shares, fixed-share fallback, and report percent rendering.
The existing schema test continues to verify that `diluted_shares` without
`period_end` fails validation.

### Memory-path invariant

No memory-path file differs from `2ac4d58`:

```text
git diff 2ac4d58 -- engine/backtest.py schemas/models.py profiles/sk_hynix.yaml pipeline/ir_loader.py pipeline/dart_fetcher.py pipeline/consensus_loader.py
# no output
```

The 9Q core values reproduce the NVDA-1 handoff exactly: revenue MAPE 8.99%,
EPS MAPE 10.39%, EPS bias -3.58%. The documented SHA
`077ecb10986a5f2a7e81b31dc595ae47077b8ed7d6fb3ababfb1d5073891933c`
did **not** reproduce from the currently available caches: every stored Yahoo
vintage produced `b979d79f...f6e7`; `consensus_history=None` produced
`eb6688a1...2674`. Because all memory-path inputs/code tracked by git are
unchanged, this is an undocumented hash-fixture/vintage reproduction gap, not
a generic-path code diff. Cowork must independently run its canonical SHA
recipe before PASS.

**RESOLVED (Cowork, 2026-07-21):** the canonical recipe's consensus leg uses
`tests/fixtures/sk_hynix_yahoo_estimates.json` (2026-05-30 snapshot), NOT the
`reports/.cache` yahoo vintages — this was recorded only in Cowork session
memory (EFE-1 exit, 2026-07-10), hence the host reproduction gap. Now
codified as `scripts/verify_9q_sha.py`: run post-2a in the sandbox →
`077ecb10…933c` MATCH (rev MAPE 8.9875% / EPS MAPE 10.3856% / bias −3.5751%).
Memory-path invariant CONFIRMED intact. Yahoo-vintage-based runs legitimately
produce different hashes (different consensus input) and are not invariant
violations.

**Root cause of host/sandbox sha skew (diagnosed 2026-07-21, byte-diff of
`--dump` outputs):** identical inputs and code produce JSON differing in
exactly two bytes-worth of float ULPs — `eps_mape` (…305 vs …304) and
`bias_revenue` (…036 vs …0373). Both are aggregate means; CPython ≥ 3.12
switched builtin `sum()` to Neumaier compensated summation, so the host
(3.14.3/win32, pydantic 2.12.5) and sandbox (3.10.12/linux, pydantic 2.13.4)
differ in the last ULP of summed floats. Semantically identical; not a
regression. `scripts/verify_9q_sha.py` now carries one canonical sha per
environment family (`KNOWN_GOOD`): sandbox `077ecb10…933c`, host
`b979d79f…f6e7`. Regression = a hash not in KNOWN_GOOD under a stable
environment. Codex's earlier vintage-based hashes coinciding with the
fixture-based host hash is expected: the fixture is the 2026-05-30 vintage.

### Cowork independent verification (2026-07-21) — stage 2a: PASS

Sandbox, post-`9908180`: full `pytest -q` 173 passed (matches host); 9Q
canonical sha MATCH via the recipe above; NVDA+TSLA JSON identity checks all
green — `legacy == skill × 100` (rev & EPS), window partition 26 = 14 + 12
with APE-numerator union reproducing full-window MAPE, boundary 2023Q2
post-side, no duplicate quarters, all 52 rows `prior_quarter_split_adjusted`
(no fallback), signal primary = post_break (values equal the post_break
window block), `MIN_SKILL_N = 8`, trailing-8Q numerically equal to the last 8
post-break rows (2024Q2→2026Q1), `full_vs_primary_disagreement = true` on
both profiles.

## 3. Before/after measurements

All error MAPE/bias columns are percent. MASE and Theil U2 are ratios. These are
stage measurements only; PLAN's full-companyfacts host gate still prohibits
external metric quotation.

### NVDA

| Window | N | Rev MAPE | Rev bias | EPS MAPE | EPS bias | MASE rev | MASE EPS | Theil rev | Theil EPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Full before | 26 | 9.92 | -4.11 | 94.97 | +81.54 | 0.609 | 1.081 | 0.628 | 1.043 |
| Full after | 26 | 9.92 | -4.11 | 91.59 | +77.37 | 0.609 | 1.081 | 0.628 | 1.038 |
| Pre before | 14 | 8.56 | +1.97 | 162.19 | +162.19 | 0.754 | 3.729 | 0.990 | 3.328 |
| Pre after | 14 | 8.56 | +1.97 | 155.25 | +155.25 | 0.754 | 3.537 | 0.990 | 3.175 |
| Post before | 12 | 11.50 | -11.20 | 16.55 | -12.55 | 0.592 | 0.817 | 0.621 | 0.998 |
| Post after | 12 | 11.50 | -11.20 | 17.31 | -13.49 | 0.592 | 0.836 | 0.621 | 0.998 |

Share convention: fixed forward 24.49B before → prior-quarter split-adjusted
as-filed shares after. All 26 after rows report
`prior_quarter_split_adjusted`; no fallback was needed.

Signal after: primary=`post_break`, N=12, skill pass=true; full EPS MAPE does
not beat RW while post-break does, so `full_vs_primary_disagreement=true`.

### TSLA

| Window | N | Rev MAPE | Rev bias | EPS MAPE | EPS bias | MASE rev | MASE EPS | Theil rev | Theil EPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Full before | 26 | 10.76 | +0.04 | 161.62 | +114.23 | 0.846 | 0.989 | 0.874 | 0.834 |
| Full after | 26 | 10.76 | +0.04 | 196.43 | +150.48 | 0.846 | 0.991 | 0.874 | 0.829 |
| Pre before | 14 | 9.98 | -4.61 | 238.32 | +176.09 | 0.708 | 1.807 | 0.737 | 1.849 |
| Pre after | 14 | 9.98 | -4.61 | 303.14 | +242.63 | 0.708 | 1.830 | 0.737 | 1.827 |
| Post before | 12 | 11.67 | +5.46 | 72.12 | +42.05 | 0.949 | 0.671 | 0.935 | 0.715 |
| Post after | 12 | 11.67 | +5.46 | 71.94 | +42.98 | 0.949 | 0.665 | 0.935 | 0.712 |

Share convention: fixed forward 3.538B before → prior-quarter split-adjusted
as-filed shares after. All 26 after rows report
`prior_quarter_split_adjusted`; no fallback was needed. The much worse early
window EPS percentage errors are measured consequences of removing the fixed
forward-share wedge, not presumed targets.

Signal after: primary=`post_break`, N=12, skill pass=true; full EPS MAPE does
not beat RW while post-break does, so `full_vs_primary_disagreement=true`.

## 4. CLI/report behavior

```text
NVDA: backtest post-break N=12, revenue MAPE 11.5%, EPS MAPE 17.3%
TSLA: backtest post-break N=12, revenue MAPE 11.7%, EPS MAPE 71.9%
```

Both JSON files preserve top-level legacy metrics plus `skill`, `rows`, and all
three windows. Markdown reports show post-break first, retain full/pre windows,
display `n`/`n_eps`, MASE/Theil, ratio-derived RW MAPE percentages, and
consensus N=0.

## 5. Scope boundary

No 2c attribution work was started.

## 6. Stage 2b — fiscal-aware generic consensus

Implemented on host 2026-07-21 from `PROMPT_nvda2_2b.md`. The memory-path
`pipeline.consensus_loader.to_consensus_record` and its Yahoo parsing contract
were not changed.

### Delivered

- New `pipeline/generic_consensus.py` normalizes Yahoo relative periods against
  each profile's fiscal calendar. Forward model labels reuse
  `pipeline.edgar_fetcher.model_label_for_period`; annual keys are fiscal-year
  integers.
- The anchor guard requires exact equality between latest profile actual
  `period_end` and latest Yahoo earnings-history end. Missing/mismatched anchors
  retain independently mapped history but emit explicit `None` forward values.
- Snapshots whose `as_of` predates the latest actual raise `ValueError`.
  Revenue/EPS quarterly period-set mismatch is a quality failure and refuses
  the forward join.
- Issuer-neutral gates are implemented as specified: 0q revenue ratio
  0.3x–3.0x and realized net-margin range ±10pp. Missing gate inputs do not
  fail. Suppressed originals and reasons remain in `quality_notes`.
- Generic backtest skill now receives normalized vintage history through the
  existing `BacktestSkill` schema. `n_surprise_scored` is displayed; no new
  consensus-skill schema or sub-8 claim was introduced.
- New Yahoo fetches preserve `as_of` plus an ISO UTC `fetch_timestamp` in the
  existing daily cache payload. The NVDA host snapshot contains both fields.
- Generic JSON adds `consensus` and `consensus_fetch_timestamp`; Markdown adds
  fiscal-aware quarterly/annual values and quality notes.

### Verification

| Check | Before 2b | After 2b |
|---|---:|---:|
| Full pytest | 173 passed | 186 passed |
| Added tests | — | 13 |
| 9Q host canonical | `b979d79f…f6e7` MATCH | `b979d79f…f6e7` MATCH |

Synthetic tests cover Jan-FYE and calendar-FYE labels, integer annual keys,
history date mapping, missing/mismatched anchors, stale `as_of`, quarterly
period-set mismatch, unit/margin pass-fail-not-run branches, existing-skill
wiring, report rendering, and cache metadata persistence.

### Live NVDA snapshot outcome

Cache: `reports/.cache/yahoo_NVDA_20260721.json` (gitignored), fetched once on
host with `as_of=2026-07-21` and a UTC fetch timestamp.

**REFUSED by anchor guard:** profile latest actual ends `2026-04-26`, while
Yahoo's latest earnings-history index is `2026-04-30`. Exact equality is the
binding contract, so forward quarterly labels `2026Q2/2026Q3` and annual keys
`2027/2028` are retained with `None` values. The four independently mapped
history rows (`2025Q2`–`2026Q1`) remain available.

| NVDA consensus field | Before 2b | After 2b |
|---|---:|---:|
| Forward quarterly/annual record | absent | explicit None (anchor refused) |
| `n_surprise_scored`, full/post | 0 / 0 | 4 / 4 |
| `skill_score_eps_vs_consensus`, full/post | None / None | -0.5066 / -0.5066 |
| Quality notes | absent | latest history 2026-04-30 != actual 2026-04-26 |
| Fetch metadata in cache/JSON | absent | as_of + UTC timestamp |

The negative consensus skill is a descriptive N=4 point estimate only; it is
not rendered as a “beats consensus” claim because `MIN_SKILL_N=8`.

### Available TSLA legacy snapshot

The existing same-day TSLA cache predates the new metadata fields, so no
timestamp was fabricated and no new TSLA network fetch was made. Offline
normalization was nevertheless measurable: latest actual/history both end
`2026-03-31`, therefore the join **MAPPED** to `2026Q2/2026Q3` and fiscal years
2026/2027 with no quality notes. Full/post `n_surprise_scored=4` and descriptive
consensus skill is -0.0420.

### Cowork independent verification (2026-07-21) — stage 2b: FAIL (one item), fix-loop

**Blocking:** `pipeline/yahoo_fetcher.py` uses `from datetime import UTC` —
Python ≥ 3.11 only. The sandbox canonical environment (3.10.12) fails test
collection on 3 modules (`generic_cli` imports `yahoo_fetcher` at module
level). Fix: `from datetime import date, datetime, timezone` +
`datetime.now(timezone.utc)`. With that one-line substitution applied
locally, the sandbox run is fully green: **186 passed**,
`scripts/verify_9q_sha.py` exit 0 (sandbox canonical), offline NVDA replay
reproduces the host report exactly — refusal note preserved verbatim in
`notes` + `quality_notes`, forward quarterly `2026Q2/2026Q3` and annual
`2027/2028` explicit None, history `2025Q2–2026Q1` kept,
`n_surprise_scored=4`, consensus skill −0.5066 descriptive-only (no claim
under `MIN_SKILL_N=8`). `yahoo_fetcher` diff is metadata-add only (as_of +
UTC timestamp at fetch), raw parsing untouched — in-scope. 12 consensus
tests cover Jan-FYE mapping, anchor/missing-history refusal, period-set
mismatch, and every gate branch (suppress+audit / not-run-not-failure).
The local substitution was REVERTED after verification; tree matches
`9d7200c` apart from Cowork-run report regenerations.

**Contract question for Codex (follow-up, not blocking the fix-loop):** the
exact-date anchor equality refused NVDA on `2026-04-26` (fiscal quarter end,
last-Sunday convention) vs `2026-04-30` (Yahoo month-end convention). For
non-calendar-month-end filers this guard refuses ALWAYS, making forward
consensus permanently unavailable for the primary test case. Proposed
amendment: compare fiscal-quarter identity instead of raw dates —
`model_label_for_period(history_end) == model_label_for_period(actual_end)`
— which still refuses genuine quarter mismatches (the actual roll-skew
failure modes in REVIEW Q4) but tolerates known period-end labeling
conventions. Codex authored the guard; its ruling governs.

### Fix-loop resolution (2026-07-23) — stage 2b: PASS

Codex `8277469`: py3.10-compatible datetime (verified: no `datetime.UTC`
remnants); anchor-guard ruling APPROVED and implemented as fiscal-quarter
identity comparison, with a same-quarter month-end-convention regression
test. Cowork re-verification (sandbox): **224 passed**, `verify_9q_sha.py`
exit 0 (sandbox canonical), and the previously-refused NVDA snapshot
(2026-04-26 vs 2026-04-30) now **MAPS** — forward `2026Q2/2026Q3` revenue+EPS
populated, annual keys int `2027/2028`, `quality_notes` empty, history
`2025Q2–2026Q1` and N=4 descriptive consensus skill (−0.5066) unchanged.
Note: the offline replay required a today-aliased cache copy
(`yahoo_NVDA_20260723.json`, content = the 2026-07-21 snapshot); the sandbox
cannot delete it — if a LIVE NVDA run happens on the host on 2026-07-23,
delete it first, otherwise it is inert from 2026-07-24 onward.

**NVDA-2 status after 2b:** 2a + 2b complete and verified. Remaining: host
full-companyfacts refetch + reproduction gate (blocks external quoting of
all NVDA-2 metrics), then the `OperatingIncomeLoss` availability check that
decides 2c (4-lever once, or defer — no interim 3-lever, per REVIEW Q5).
