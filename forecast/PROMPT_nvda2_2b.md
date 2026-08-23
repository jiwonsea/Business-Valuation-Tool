# PROMPT — NVDA-2 stage 2b implementation (Codex, host)

Basis: `PLAN_nvda2.md` rev-1 §2b (contracts binding per `REVIEW_nvda2_codex.md`
Q4/Q6/Q7) · stage 2a PASSED Cowork verification 2026-07-21 (see
`HANDOFF_nvda2.md` §2). Implement stage 2b ONLY; 2c stays deferred pending the
host full-blob OP check.

## 0. Housekeeping commit FIRST

Commit the Cowork verification artifacts as-is:
`scripts/verify_9q_sha.py` (canonical 9Q SHA recipe — resolves the
reproduction gap you flagged; run it once on the host to confirm MATCH and
note the result in the commit message), `HANDOFF_nvda2.md` (verification
section), `PROMPT_nvda2_2b.md`. Message:
`docs: 2a Cowork verification PASS + canonical 9Q sha recipe script`.

## 1. Scope

New `pipeline/generic_consensus.py` + tests + generic report/JSON consensus
fields. Do NOT touch `pipeline/consensus_loader.to_consensus_record` (memory
path) or `pipeline/yahoo_fetcher.fetch_consensus` raw parsing. Memory-path 9Q
invariant: `python scripts/verify_9q_sha.py` must exit 0 before and after.

## 2. Deliverables (PLAN rev-1 §2b — verbatim binding)

1. `to_generic_consensus_record(raw_yahoo, profile, as_of) -> ConsensusRecord`.
   Quarter mapping: 0q anchored to the NEXT fiscal quarter after the
   profile's latest actual `period_end`; fiscal → model label via
   `pipeline.edgar_fetcher.model_label_for_period` (single implementation).
   `earnings_history` rows join on their own quarter-end dates → fiscal →
   model labels (never calendar-quarter strings). Annual keys = fiscal-year
   INTEGERS (`dict[int, …]` schema; no `FY…` strings).
2. **Anchor guard:** map 0q only when latest actual `period_end` == latest
   earnings-history end. Mismatch/missing history → forward quarterly
   consensus None ONLY (keep independently-normalizable historical rows);
   annual also None when anchor uncertain; refuse snapshots whose as_of
   predates the latest actual period_end; revenue vs EPS 0q/+1q period-set
   mismatch = quality failure; cache preserves fetch timestamp/as_of.
3. **Quality gates (issuer-neutral, unit/join-error detector — not an
   economic judge):** unit gate `0.3 ≤ consensus_0q_revenue /
   latest_actual_revenue ≤ 3.0`; margin gate `realized_min − 10pp ≤ implied
   ≤ realized_max + 10pp` (realized range from profile `actuals`); share
   denominator + unit_scale explicit per profile; missing revenue or EPS →
   gate not run, NOT a failure; gate failure → suppress value, preserve
   original + reason as audit info in `quality_notes`.
4. **Skill wiring (Q7):** fill the consensus-related fields of the EXISTING
   skill structure from 2a — no new consensus-skill schema. Consensus N
   displayed with `n_surprise_scored`; never a "beats consensus" claim below
   `MIN_SKILL_N = 8`.
5. Live Yahoo is host-only: tests use synthetic raw fixtures (include
   Jan-FYE mapping cases, anchor-mismatch refusal, each gate's
   pass/fail/not-run branch); cache vintage snapshots
   `reports/.cache/yahoo_NVDA_{date}.json` (existing pattern) so the
   consensus leg replays offline in the sandbox.

## 3. Verify & measure

Full `pytest -q` green; `scripts/verify_9q_sha.py` exit 0; NVDA (+TSLA if
consensus available) before/after consensus fields + quality_notes recorded
in `HANDOFF_nvda2.md` §2b. Fetch one real NVDA Yahoo snapshot on the host,
cache it, and report what the anchor guard did with it (mapped or refused,
and why). Measure, no presumed targets.

## 4. Exit

Commit stage 2b as its own commit. Report back for Cowork verification: diff
summary, test count before/after, the cached snapshot's join outcome, any
contract deviations with reasoning.
