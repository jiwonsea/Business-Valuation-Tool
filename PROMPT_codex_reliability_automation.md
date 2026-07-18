# CODEX PROMPT — Model reliability + automation lifecycle (execution)

Paste into a fresh Codex session on the HOST (network + DART/EDGAR/EDINET/yfinance
available). You are picking up execution from a design+pure-logic pass. The pure
interfaces, gate rules, dual-skill shape, and refresh adjudication are **already
built and unit-tested offline**; your job is the network-heavy execution around
them. Do NOT rewrite the pure modules — extend them additively and keep every
existing test green.

Repos (siblings): `earnings-forecast-engine` (EFE), `business-valuation-tool`
(BVT), `investment-orchestrator`. Full design rationale:
`business-valuation-tool/NEXT_SESSION_reliability_automation.md` — read it first.

## Guardrails (non-negotiable)
1. **Never wire auto order-execution.** Automate decision generation + re-seed
   only. `refresh_gate.executes_order` stays False (Phase A). Humans execute.
2. **Fail → abstain, never a confident trade.** Any auto-generated / auto-refreshed
   profile that fails the investability gate (Item 3) or Codex review must end
   `draft: true` → orchestrator abstains. This is the whole safety story.
3. **No fabricated data.** Paywalled series (TrendForce, Platts, IHS/BNEF) are
   marked gaps in `EFE/engine/cyclical_drivers/sectors.py`. Use the declared
   `public_fallback` or leave the gap explicit — do not invent numbers.
4. Keep pure logic pure (no IO inside the gate / driver math / adjudicator).
5. After each item: run the named tests; they must stay green. Report a diff.

## Setup
```
pip install -r EFE/requirements.txt -r BVT/requirements-lock.txt
# EFE tests need: pydantic pytest yfinance ; BVT: + scipy httpx ; orch: typer python-dotenv pyyaml
```
Sanity (already-green pure tests):
```
cd EFE && pytest tests/test_generic_signal_skill_gate.py tests/test_cyclical_drivers.py -q
cd ../business-valuation-tool && pytest tests/test_investability_gate.py -q
cd ../investment-orchestrator && pytest tests/test_refresh_gate.py -q
```

---

## Phase 1 — Backtest window data (Item 1) · do first, upgrades live names
Pure gate is done in `EFE/engine/generic_signal.py` (`MIN_SKILL_N=8`, dual-window,
`regime_shift`) + per-row `rw_eps` in `generic_cli.py`. You supply the data.

1. For each live profile (SK Hynix, Samsung, M7), expand historical `actuals`
   from ~3 to an **expanding window up to ~20 quarters (min 8)** using
   **independent reported quarters** from DART/EDGAR/EDINET — NOT annual÷4
   (removes the §3-C circularity in `docs/RELIABILITY_REVIEW_2026-07-06.md`).
2. Memory-path parity: add trailing-8Q skill + `n` to
   `EFE/engine/skill_metrics.py::compute_skill` and `schemas.models.BacktestSkill`
   (additive fields; respect `extra="forbid"`), mirroring the generic block.
3. (Optional) apply the n≥8 abstain to `orchestrator/adapters/forward_eps.py` v1
   fallback; if you do, update `tests/test_forward_eps_v2.py::test_v1_fallback...`.

**Done when:** every live name reports `n>=8`, full + trailing-8Q skill; a name
with no trailing edge flips to `stance:neutral`. Re-run each name; commit profiles.

## Phase 2 — Investability gate wiring (Item 3) · the safety spine, wire early
Pure gate done: `BVT/engine/investability_gate.py`
(`evaluate_investability`, `apply_gate_to_profile`, `gate_inputs_from_profile`).

1. Wire it into `BVT/valuation_runner.py` (near `_is_draft_profile`, ~L471) and/or
   `pipeline/profile_generator.py`: a real run computes `dcf_value`,
   `peer_median_value` (via `calibration/peer_fetcher.py` comp set),
   `quality_grade`, `consolidated_revenue` → `gate_inputs_from_profile` →
   `apply_gate_to_profile`. Confirm extractor field names
   (`segments[].revenue/multiple/id`, `primary_method`) match the schema; fix if not.
2. Run on all 9 live profiles: currently-investable names must still pass; any
   draft/stub name forced to `draft: true`.
3. **Decision to make + encode:** optionality names deliberately floor DCF 30–40%
   below peers. Do they block on the [0.7,1.5] band, or widen the band for
   `optionality_flag` names? Adversarially review and implement your call, with a test.

**Done when:** the gate runs in the real pipeline, 9 names classified correctly,
optionality decision encoded + tested.

## Phase 3 — Cyclical price feeds + calibration (Item 2)
Pure interface + 8-sector registry done: `EFE/engine/cyclical_drivers/`.

1. Implement fetchers for the **public** series first: crude futures (oil_gas),
   iron ore + CME HRC (steel), BDI (shipping), jet fuel/EIA (airlines), LME
   Li/Ni/Co (batteries input). Leave paywalled series as declared gaps.
2. **Calibrate** `default_passthrough` per name on the (now ≥8Q) backtest. The
   skill gate still governs: a driver forecast must beat naive or the name
   abstains — this tests whether the price-cycle read actually forecasts.
3. Wire a driver-based margin path end-to-end for one public-data pilot (steel or
   shipping); then confirm the memory path reproduces existing SK Hynix output.

**Done when:** at least one public-data cyclical produces a driver-based forecast
that passes the skill gate; paywalled gaps remain explicit.

## Phase 4 — Earnings-driven auto-refresh (Item 4) · last
Pure DUE brain (`orchestrator/schedule/earnings_refresh.py`) + adjudicator
(`schedule/refresh_gate.py::adjudicate_refresh`) done. Wire the middle.

1. In `schedule/refresh.py::run_due_refresh`, between "decide succeeded" and
   "persist state": (a) re-seed EFE/BVT with the new quarter (KR 잠정실적 + DART/
   EDGAR), (b) run the Item 3 gate on the re-seeded profile, (c) run your
   adversarial parallel eval, then call `adjudicate_refresh(...)` and log the card
   with its `effective_action` + `confident`. Persist `last_refreshed` from it.
2. Make the re-seed earnings-driven (reuse `BVT/scheduler/weekly_run.py` infra);
   wire `earnings_calendar.build_universe` to real Yahoo/DART earnings dates.
3. Verify: a DUE name with a passing re-seed logs a confident card; a DUE name
   failing the gate logs a **neutral HOLD**, persists `last_refreshed`, emits **no
   order**.

## Report back
For each phase: files changed, test results, data-source coverage (public vs
paywalled gaps), and any threshold/judgment decisions you made (esp. the Phase 2
optionality-band call). Flag anything where the data made a check unreachable.
