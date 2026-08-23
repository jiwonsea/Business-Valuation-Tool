# HANDOFF — PLAN_nvda2.md Codex Review

Date: 2026-07-11 · Author: Cowork session · For: Codex feasibility review (host)
Basis: NVDA-1 shipped at `2ac4d58` (see `HANDOFF_nvda1.md`; 164 tests green,
9Q sha `077ecb10…933c` verified). Under review: `PLAN_nvda2.md` (metrics parity
on the generic path). The review verdict is binding where it corrects the plan,
same contract as `REVIEW_nvidia_codex.md`.

## 1. What changed since your last review (facts to re-anchor on)

- NVDA/TSLA `actuals` are now official as-filed standalone quarters, 27
  contiguous each, per-quarter as-filed diluted shares, EPS derived at load via
  `split_history` (current basis). `backtest_generic` refuses non-contiguous
  actuals.
- Clean-data measurements (N=26): NVDA rev MAPE 9.9% (RW 13.9%) bias −4.1%;
  EPS MAPE 95.0% (RW 30.6%) bias **+81.5%**. Sub-window 2023Q2+ (N=12):
  EPS MAPE 16.5% (RW 24.7%) bias −12.5%. Your predicted regime-break exposure
  materialized almost exactly (−45.8% was artifact; the honest full-window
  error is a constant-margin overshoot of pre-supercycle quarters).
- TSLA 2023Q2+ EPS: MAPE 72.1% (RW 123.0%) bias +42.1% — still noisy, as the
  profile's own notes warn.
- Sandbox constraint discovered: `data.sec.gov` 403s for processes; the two
  committed profiles were built from DERIVED concept-slice caches (as-filed
  originals only, FY-sum identity verified). Host must refetch full blobs and
  confirm reproduction before NVDA-2 metrics are quoted externally.

## 2. Claims to verify FIRST (block 2a if wrong)

1. **SkillRow conversion is lossless.** `backtest_generic` rows
   (`actual_rev/model_rev/rw_rev`, optional `*_eps`) map 1:1 onto
   `engine/skill_metrics.SkillRow`; `compute_skill`'s legacy-consistency:
   `naive_rw_revenue_mape` from compute_skill should equal the existing
   `naive_rw_eps_mape`/`naive_rw_revenue_mape` fields already emitted by
   `backtest_generic` (same pairs, same definition). If not identical,
   something is double-counting eps-None rows.
2. **Window partition identity.** With `regime_break_quarter: "2023Q2"`,
   pre_break ∪ post_break row sets must partition the full window (boundary
   row inclusive on the post side — the 2023Q2 target scored WITH post-break
   assumptions context), and each block's pairs must reproduce the full-window
   pairs when unioned. (The 2023Q2+ numbers above were computed by filtering
   `bt["rows"]` on `quarter >= "2023Q2"` — string compare is safe for the
   YYYYQq format, but confirm.)

## 3. Questions for Codex

1. **Split-window reporting.** Dual-window (pre/post) with post-break as
   headline vs scoring ONLY from 2023Q2 (full-window relegated to a
   footnote)? And: `regime_break_quarter` as a `GenericProfile` field
   (extra="forbid", explicit-assumptions) vs a CLI flag? PLAN proposes
   profile field + dual-window with post-break headline.
2. **Model-EPS share convention in `backtest_generic`.** Today: fixed forward
   `weighted_avg_diluted` for every historical model EPS. Options:
   (a) keep + document wedge; (b) prior-quarter as-filed shares,
   split-adjusted (no-lookahead, mirrors memory path's seed-implied
   convention); (c) target-quarter shares (rejected: lookahead). PLAN
   proposes (b). Is the added profile-schema coupling (backtest reads
   actuals' diluted_shares) acceptable, or does (a)'s simplicity win given
   NVDA's ≤2% wedge (TSLA's is ~25% in 2019–20, though)?
3. **N=12 skill stability.** MASE/Theil on 12 points (and consensus skill on
   ~4 vintage quarters) — acceptable as point estimates with n displayed, or
   should the skill block be suppressed below some n? PLAN proposes n ≥ 6
   for skill, no CI.
4. **0q anchoring.** PLAN anchors Yahoo `0q` to (latest actual period_end →
   next fiscal quarter), cross-checked against `earnings_history`'s latest
   reported quarter; disagreement → quality note + None (refuse-don't-guess).
   Any failure mode this misses (e.g. yfinance rolling 0q mid-day on report
   date; off-cycle 8-K restatements)?
5. **Attribution lever count vs data.** 4-lever needs actual OperatingIncomeLoss
   ingested into `GenericActualQuarter` (host full-blob regeneration).
   Fallback: 3-lever {revenue, net margin, shares} works with committed data
   today. Ship 3-lever now and upgrade to 4-lever after host refetch, or wait
   and do 4-lever once? (Attribution is already agreed-deprioritized within
   NVDA-2.)
6. **Issuer-neutral quality gates.** Proposed: unit coherence (0q revenue
   estimate within 0.3×–3× of latest actual) + implied net margin inside the
   realized min/max from `actuals` ± buffer (how much buffer? ±10pp?). Sanity:
   NVDA's realized net margin range 2019Q3..2026Q1 is ~10%–71%, so a fixed
   60% cap would false-positive exactly as you warned. Better formulation?
7. **Sequencing.** 2a (skill+windows) → 2b (consensus) → 2c (attribution),
   with 2a shipping RW-relative metrics before 2b lands consensus vintages.
   Any reason to invert 2a/2b (e.g. consensus join contract influencing the
   skill-block schema)?

## 4. Agreed workflow

1. This doc + `PLAN_nvda2.md` → Codex review on host (repo at `2ac4d58`,
   tree clean apart from user-owned edits to HANDOFF_nvidia_review.md /
   PLAN_nvidia_application.md / README.md — do not touch those).
2. Host precondition in parallel: full companyfacts refetch → regenerate →
   diff vs committed actuals (expect byte-identical blocks; TSLA gains
   as-filed EPS provenance strings only).
3. Review survives → NVDA-2 implementation in a fresh session (2a→2b→2c,
   verify each stage before the next; per-session commit).
4. Session exit protocol unchanged: full pytest + 9Q sha match + HANDOFF +
   memory note.
