# PROMPT — NVDA-2 stage 2a implementation (Codex, host)

Basis: `PLAN_nvda2.md` rev-1 §2a (contracts binding, integrated from
`REVIEW_nvda2_codex.md` — your own verdict) · repo at `2ac4d58` + uncommitted
docs. Implement stage 2a ONLY. Do not start 2b/2c.

## 0. Housekeeping commit FIRST (user-delegated — the user does not use git)

Commit the pending docs as one commit before touching code:
`PLAN_nvda2.md`, `HANDOFF_nvda2_review.md`, `REVIEW_nvda2_codex.md`,
`PLAN_nvda2_execution.md`, `PROMPT_nvda2_2a.md`, plus the user-owned edits to
`PLAN_nvidia_application.md`, `HANDOFF_nvidia_review.md`, `README.md`
(include as-is, do not modify). Message:
`docs: NVDA-2 plan rev-1 + Codex review + multi-model execution protocol`.
Note: `.gitattributes` LF normalization may produce a one-time renormalization
diff — acceptable.

## 1. Scope

Generic path only: `schemas/generic.py`, `backtest_generic` (its module),
`engine/generic_signal.py`, `generic_cli.py`, MD report rendering for the
generic path, tests. Memory path untouched — 9Q `BacktestResult` sha256 must
remain `077ecb10…933c`. All new assumptions in YAML, `extra="forbid"` kept.

## 2. Deliverables (contracts from PLAN rev-1 §2a — verbatim binding)

1. **Skill block.** Map `backtest_generic` rows → `engine/skill_metrics.SkillRow`,
   reuse `compute_skill` as-is. `skill` block keeps 0–1 ratios; legacy
   percent keys unchanged; % formatting only at report render; ratio units
   documented.
2. **Split windows.** Optional `regime_break_quarter` on `GenericProfile`
   (set `"2023Q2"` in `profiles/nvda.generic.yaml` and
   `profiles/tsla.generic.yaml` with a sourcing comment). Output schema
   (STABLE — 2b will only fill consensus fields):
   `backtest = {legacy scalars, rows, skill, windows:{full, pre_break,
   post_break}}`, each window ≥ {n, n_eps, mape, bias, skill}. Boundary row
   scores post-side. No field → output shape gains nothing, behavior
   unchanged.
3. **Signal consistency.** `generic_signal` primary skill = post-break;
   trailing-8Q = last 8 rows inside post-break; full-vs-post disagreement
   surfaced separately; profiles without the field keep current behavior.
4. **Min-N.** Reuse existing `MIN_SKILL_N = 8`. Metrics always displayed with
   n; n < 8 → descriptive only (no stance gate); consensus fields None in 2a.
5. **Share convention (b).** Historical model EPS:
   `prev.diluted_shares × split_factor(prev.period_end)`; missing shares →
   explicit fallback to fixed forward shares; record applied convention;
   forward-forecast fixed shares unchanged.

## 3. Tests (add; full `pytest -q` must be green)

- SkillRow equivalence: `legacy naive_rw_*_mape == skill.* × 100`, NVDA+TSLA.
- Partition identity: row sets, n, and APE numerators of pre∪post reproduce
  full (never averaging per-window MAPEs); boundary 2023Q2 post-side; no
  duplicates.
- Signal primary window = post-break when field set; unchanged when absent.
- Share convention: prior-quarter shares picked, split-adjusted; fallback
  path when shares missing; schema failure when `diluted_shares` without
  `period_end`.
- Report renders % from ratios (single formatting site).

## 4. Verify & measure

- `pytest -q` green; 9Q memory-path sha unchanged.
- `python generic_cli.py --profile profiles/nvda.generic.yaml --json` (and
  TSLA) BEFORE and AFTER → record in new `HANDOFF_nvda2.md`: full/pre/post
  {n, n_eps, rev+EPS MAPE, bias, MASE, Theil} plus share-convention
  before/after delta. Measure, no presumed targets.

## 5. Exit

Commit stage 2a (code+tests+profiles+HANDOFF) as its own commit. Report back
for Cowork verification: diff summary (files + line counts), test count
before/after, the before/after metrics table, any deviation from the
contracts above with reasoning. Cowork FAIL → fix-loop commit follows.
