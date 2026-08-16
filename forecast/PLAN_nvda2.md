# PLAN — NVDA-2: Metrics parity on the generic path

Date: 2026-07-11 · rev-1 2026-07-21 · Status: APPROVED (conditional) —
Codex verdict `REVIEW_nvda2_codex.md`; its six binding corrections are
integrated below. Execution protocol: `PLAN_nvda2_execution.md`.
Precedes: `PLAN_nvidia_application.md` §5 NVDA-2 (Codex-reviewed scope), updated
with what NVDA-1 actually measured (`HANDOFF_nvda1.md`, commit `2ac4d58`).
Scope: generic path only (`generic_cli.py`, `schemas/generic.py`,
`engine/generic_signal.py`, new modules below). Memory-path 9Q invariant
(`077ecb10…933c`) must stay bit-identical throughout.

**Binding precondition (host):** replace the two derived EDGAR caches with full
companyfacts blobs and confirm `scripts/build_generic_actuals.py` reproduces the
committed NVDA/TSLA actuals identically. NVDA-2 implementation may start before
this, but no NVDA-2 metric is quoted externally until it passes.

## 1. The question

NVDA-1 made the data honest; the metrics layer is not yet. Three gaps, in
priority order:

1. The generic backtest reports absolute MAPE/bias only — no naive-baseline
   (MASE/Theil) or consensus-relative skill, i.e. the exact failure the memory
   path already fixed ("Model must beat naive-baseline error").
2. The full 2019Q3–2026Q1 window now *visibly* straddles the AI-supercycle
   regime break. Measured on clean data: NVDA full-window EPS bias **+81.5%**
   (constant 62% op-margin assumption applied to ~25–35%-margin FY2020–23
   quarters) vs **−12.5% / EPS MAPE 16.5% (RW 24.7%)** on 2023Q2+ (N=12).
   Full-window EPS skill is honest but not decision-useful; without split-window
   scoring the headline number misleads in the OTHER direction now.
3. Consensus gap for NVDA needs Yahoo vintages joined on the FISCAL calendar —
   `to_consensus_record`'s `0q → as_of calendar quarter` join silently
   mis-labels a Jan-ending filer, and its `.KS` quality gates false-positive on
   NVDA's genuine >50% net margin (Codex #4, binding).

## 2. Workstreams (ordered; verify each before the next)

### 2a — Skill metrics + split-window scoring (Codex-approved; contracts binding)
- Reuse `engine/skill_metrics.compute_skill` as-is. Codex-verified: rows map
  1:1 onto `SkillRow` (N=26 both profiles, no eps-None double-count). Keep
  the legacy MAPE/bias keys; ADD a `skill` block to the backtest dict.
  **Units contract (Codex correction #1):** `BacktestSkill` keeps 0–1 ratios
  (memory-path convention); legacy keys stay percent; % formatting happens
  only at report render; equivalence test asserts `legacy == skill × 100`;
  ratio units documented on the fields.
- Split-window: optional `regime_break_quarter: "2023Q2"` as `GenericProfile`
  field (CLI flag rejected — non-reproducible for the same profile). Stable
  schema is FIXED in 2a so 2b only fills the consensus leg (Codex Q7):
  `backtest = {legacy scalars, rows, skill, windows:{full, pre_break,
  post_break}}`, each window ≥ {n, n_eps, mape, bias, skill}. Boundary row
  (2023Q2) scores on the post side. Partition test combines row sets, sample
  counts, and APE numerators to reproduce full-window values — never
  averages of per-window MAPEs. No profile field → behavior unchanged.
- **Signal consistency (Codex correction #2):** report/console headline =
  post-break, but `engine/generic_signal.py` must judge on the SAME window:
  signal primary skill = post-break; trailing-8Q = last 8 rows inside
  post-break; JSON preserves all three windows; full-vs-post regime
  disagreement displayed separately; profiles without the field keep the
  current full/trailing behavior.
- **Min-N (Codex correction #3):** unify on existing `MIN_SKILL_N = 8` — do
  not introduce 6. MASE/Theil/RW-MAPE always displayed with n; n < 8 →
  descriptive only, no skill claim or stance gate; n ≥ 8 → gate allowed;
  consensus N≈4 displayable but never a "beats consensus" verdict; always
  show `n_surprise_scored`.
- EPS-model share convention — option (b) APPROVED (Codex correction #4):
  historical model EPS uses `prev.diluted_shares ×
  split_factor(prev.period_end)` (no-lookahead; mirrors memory-path
  seed-implied convention). Missing shares → explicit fallback to fixed
  forward shares; `diluted_shares` without `period_end` keeps failing schema
  validation; record the applied convention per row or in HANDOFF; the
  forward forecast's fixed-share assumption is unchanged. This moves generic
  backtest numbers → measure before/after in the same session, table
  mandatory.
- Consensus-leg inputs (`consensus_history`) arrive only after 2b; 2a ships
  RW-relative metrics first with consensus fields None.

### 2b — Fiscal-aware consensus normalization
- Reuse `pipeline/yahoo_fetcher.fetch_consensus` raw parsing as-is. Do NOT
  touch `to_consensus_record` (memory path). New `pipeline/generic_consensus.py`:
  `to_generic_consensus_record(raw_yahoo, profile, as_of) -> ConsensusRecord`.
- Quarter mapping: anchor `0q` to the NEXT fiscal quarter after the profile's
  latest actual `period_end` (pure as_of arithmetic is the bug being
  replaced). Fiscal → model label via
  `pipeline.edgar_fetcher.model_label_for_period` (the NVDA-1b contract, one
  implementation). `0y/+1y` map to fiscal years by the same anchor, keyed as
  fiscal-year INTEGERS (`ConsensusRecord` annual key is `dict[int, …]`; the
  earlier `FY{fiscal_year}` string label conflicted with schema — Codex
  correction #5).
- **Anchor guard (Codex Q4, binding):** map 0q only when the latest actual
  `period_end` equals the latest `earnings_history` end. Mismatch or missing
  history → forward quarterly consensus None ONLY (keep
  independently-normalizable historical consensus rows); annual also None
  when the anchor is uncertain; refuse snapshots whose as_of predates the
  latest actual period_end; revenue vs EPS 0q/+1q period-set mismatch =
  quality failure; cache preserves fetch timestamp/as_of.
- `earnings_history` rows join on their own quarter-END dates → fiscal → model
  labels (never calendar-quarter string matching).
- `quality_notes` contract kept; thresholds issuer-neutral, concretized per
  Codex Q6: unit gate `0.3 ≤ consensus_0q_revenue / latest_actual_revenue ≤
  3.0`; implied-net-margin gate `realized_min − 10pp ≤ implied ≤ realized_max
  + 10pp` (buffer default 10pp; NVDA realized ~9.8%–71.5%, so this avoids
  the fixed-60%-cap false positive). Share denominator and unit_scale
  explicit per profile. Missing revenue or EPS → gate not run, NOT a quality
  failure. Gate failure → suppress the consensus value but preserve the
  original + failure reason as audit info. Documented as a unit/join-error
  detector, not an economic-plausibility judge. No market-suffix logic.
- Live Yahoo is host-only (sandbox 403): tests use synthetic raw fixtures;
  vintage snapshots cached `reports/.cache/yahoo_NVDA_{date}.json` (existing
  pattern) so skill's consensus leg replays offline.

### 2c — 4-lever generic attribution (deprioritized within NVDA-2)
- Separate `engine/generic_attribution.py` + result model — do NOT parametrize
  the 5-lever memory bridge by lever count (Codex #5, binding). Bridge:
  `EPS = revenue × (OP/rev) × (NI/OP) × (scale/shares)` → levers
  {revenue, op_margin, OP→NI conversion, shares}, sequential substitution in
  that order, telescoping to the total relative EPS error (same convention as
  `engine/attribution.py`). Waterfall MD rendering reused; label explicitly
  "opex lever 없음 — generic 경로는 GP를 분해하지 않음" + "사후 귀인 — 예측
  신호 아님".
- **Data gap:** `GenericActualQuarter` has no `operating_profit`. 4-lever needs
  actual OP → extend `edgar_fetcher` concepts with `OperatingIncomeLoss`,
  regenerate actuals from the host full blob. **Codex ruling (correction
  #6): no interim 3-lever release.** OP data incomplete after the host
  refetch → DEFER 2c; 3-lever allowed only as an internal diagnostic, never
  a published output contract. Implement 4-lever once, after OP is confirmed.

### 2d — Explicitly OUT of scope
- Rebuilding aapl/msft/googl/amzn/meta actuals (mechanical via
  `scripts/build_generic_actuals.py`, separate session; their backtests
  correctly refuse until then). samsung.generic is DART-territory, not EDGAR.
- NVDA-3 reporting parity (still deferred; a polished report would visually
  reinforce numbers whose contract 2a/2b are about to change).
- Valuation-bridge elasticity (still blocked on BVT).

## 3. Risks
- **Small post-break sample:** N=12 (EPS N=12) — MASE/Theil are point
  estimates; a single quarter can move them materially. Mitigation: report n
  inside every window block; metrics always displayed; skill claims / stance
  gates require n ≥ 8 (existing `MIN_SKILL_N`); no CI theater.
- **0q anchoring drift:** if Yahoo has already rolled to the next quarter but
  the profile's actuals lag (or vice versa), the anchor mis-joins by one
  quarter. Mitigation: cross-check `earnings_history`'s latest reported
  quarter against the profile's last actual; disagreement → quality note +
  consensus fields None (refuse, don't guess) — same philosophy as the
  contiguity guard.
- **53-week fiscal edge:** `model_label_for_period` raises on a
  February-ending quarter (never occurred for NVDA; documented, not handled).
- **Share-convention flip (2a)** changes published generic backtest numbers
  again — one methodology change, measured once, in the same commit as its
  tests; before/after table mandatory.
- Memory-path regression risk ~0 (no shared code paths touched), but the sha
  check stays in the session-exit protocol regardless.

## 4. Verification protocol (every sub-stage)
- `pytest -q` full suite green (new tests per stage: SkillRow conversion
  equivalence vs legacy MAPE fields; window-split partition sums; 0q anchor
  mapping incl. Jan-ending cases; quality-gate no-false-positive on NVDA
  margins; attribution telescoping identity).
- `python generic_cli.py --profile profiles/nvda.generic.yaml [--json]`
  before/after per stage → `HANDOFF_nvda2.md` (measure, no presumed targets).
- Memory path: 9Q `BacktestResult` sha256 == `077ecb10…933c`.
- Session exit: per-session commit; HANDOFF updated; memory note updated.
