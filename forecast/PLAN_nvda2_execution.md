# PLAN — NVDA-2 execution: Codex×Cowork multi-model workflow

Date: 2026-07-21 · Status: ACTIVE
Scope decision (user, 2026-07-21): NVDA-2 only; roles = **Codex implements
(host) / Cowork verifies (sandbox)**. Technical content lives in
`PLAN_nvda2.md`; this doc is the execution protocol only.

## Role split

| | Codex (host) | Cowork (sandbox) |
|---|---|---|
| Network | live Yahoo/EDGAR, full-blob refetch | offline only (DART/EDGAR caches, fixtures) |
| Work | review PLAN, implement 2a→2b→2c, host pytest | write per-stage prompts, integrate review verdict, independent verification, HANDOFF/memory |
| Git | commits (user-delegated 2026-07-21 — user does not use git) | read-only; verifies post-commit |

User shuttles: Codex verdict/diff summaries → Cowork; Cowork prompts/verdicts → Codex.

## Steps

**0. Freeze the tree (Codex, host).** SUPERSEDED 2026-07-21: user delegated
all git work to Codex. Docs commit folded into `PROMPT_nvda2_2a.md` step 0;
review (step 1) ran against `2ac4d58` + uncommitted docs, read-only — done.

**1. Codex review (host).** Feed Codex: `HANDOFF_nvda2_review.md` +
`PLAN_nvda2.md` (repo at the step-0 commit). It must answer Q1–Q7 (§3 of the
handoff) and verify the two §2 blocking claims (SkillRow losslessness, window
partition identity). Paste the verdict back here.

**2. Cowork integrates verdict.** Verdict is binding where it corrects the
plan (same contract as `REVIEW_nvidia_codex.md`). Cowork saves it as
`REVIEW_nvda2_codex.md`, revises `PLAN_nvda2.md` → rev-1, and writes the
stage-2a implementation prompt `PROMPT_nvda2_2a.md` (binding contracts, test
list, before/after measurement table skeleton).

**3. Host precondition (Codex, parallel with 1–2).** Full companyfacts
refetch (`SEC_EDGAR_USER_AGENT`) → `scripts/build_generic_actuals.py` →
diff vs committed NVDA/TSLA actuals. Expected: byte-identical blocks (TSLA
gains as-filed EPS provenance strings only). **Gate: no NVDA-2 metric is
quoted externally until this passes.** Implementation may start before it.

**4. Implement per stage (Codex), verify per stage (Cowork).**
Order 2a → 2b → 2c, one stage per Codex session, next stage only after
Cowork PASS:
- Codex: implement from `PROMPT_nvda2_{stage}.md`, run full `pytest -q` on
  host, report diff summary + before/after numbers.
- Cowork: fresh-read changed files off the mount (stale-mount gotcha —
  re-sync via new-file+cp if content looks truncated), independently run
  `pytest -q`, 9Q sha check (`077ecb10…933c`), `generic_cli` on cached
  profiles, stage-specific identity checks (2a: window partition + SkillRow
  equivalence vs legacy MAPE fields; 2b: 0q anchor incl. Jan-FYE cases,
  quality-gate no-false-positive on NVDA margins; 2c: telescoping identity).
- Codex commits its own stage (Cowork verification runs post-commit; FAIL →
  fix-loop commit with the failing evidence; regression → stop and isolate
  before new work). Cowork PASS → next stage prompt.

**5. Exit (per stage and final).** Update `HANDOFF_nvda2.md` (measured
numbers only, no presumed targets), memory note, per-session commit. Final:
README metric refresh only after step-3 gate passes.

## Verification ownership

Cowork's PASS is required even though Codex ran pytest — independent
environment, and Cowork owns the invariants: 9Q memory-path sha, backtest
refusal behavior on non-rebuilt generic profiles, `extra="forbid"` schema
discipline, no hardcoded assumptions outside YAML.

## Out of scope (unchanged from PLAN_nvda2 §2d)

Other generic profile rebuilds, NVDA-3 reporting parity, valuation-bridge
elasticity (BVT-blocked), EFE-2.
