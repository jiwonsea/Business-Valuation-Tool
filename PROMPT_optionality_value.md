# PROMPT — Optionality-Aware Intrinsic Value (Tier 2, BVT engine)

> **Run this inside `business-valuation-tool/`.** Standalone task for a BVT session (Claude or Codex).
> **Author of request**: 2026-07-08, arising from the investment-orchestrator work. Sibling context: `../investment-orchestrator/HANDOFF_codex_optionality.md` (the adapter-side Tier 0/1 reframe that consumes this).
> **Prerequisite reading**: `HANDOFF_quality_optionality_2026-07-06.md`, `docs/RELIABILITY_REVIEW_2026-07-06.md`, `engine/quality.py`, `engine/scenario.py`, `engine/gap_diagnostics.py`, `schemas/models.py` (`ValuationResult`, `CrossValidationItem`, `ScenarioResult`, `GapDiagnostics`), `backtest/`.

---

## 0. Problem statement

The 2026-07-06 optionality work fixed the **quality score** (excluded DCF from convergence for optionality names) but deliberately did **not** touch the **intrinsic value** itself. As a result, `weighted_value` remains DCF/floor-anchored, and for every high-optionality name the intrinsic value sits 25–71% below market:

| Name | intrinsic (floor) | market | gap | `_dcf_ratio` (DCF ÷ median multiple) |
|---|---|---|---|---|
| 삼성전자 | ₩172,333 | ₩309,500 | −44% | 38% |
| AAPL | $114 | $298 | −62% | 40% |
| AMZN | $147 | $244 | −40% | 33% |
| NVDA | $145 | $194 | −25% | 36% |
| TSLA | $116 | $397 | −71% | 3% |

BVT's own docs already call this value a "하한 근사 (floor approximation)." Downstream consumers (the orchestrator) then misread the floor as a fair-value point estimate and flag everything as overvalued. This prompt makes the **value** optionality-aware, so BVT emits a defensible *range and central estimate* for convex names, not just a floor.

**Non-goal / guardrail:** do NOT re-weight until intrinsic ≈ market for everything. That destroys the tool's entire purpose (a valuation that always agrees with price is worthless) and is the "confidence laundering" failure mode. The target is a **calibrated** central estimate that sits between the DCF floor and the market-multiple ceiling, justified by scenario structure — validated on the backtest, not by eyeballing.

---

## 1. What BVT already has (reuse, don't rebuild)

- `result.cross_validations: list[CrossValidationItem]` — each has `per_share` per method (DCF, P/E, EV/Revenue, EV/EBITDA, P/BV). The market-multiple ceiling is already computed.
- `result.scenarios` — Bear/Base/Bull `ScenarioResult.per_share`.
- `engine/quality.py` — the `_dcf_ratio < 0.7` optionality detector and `_has_optionality_segments`. Precedent: `_OPTIONALITY_EXCLUDED_CV_METHODS`, and the rNPV precedent `_RNPV_EXCLUDED_CV_METHODS` ("EBITDA-based TV misses pipeline option value").
- `engine/gap_diagnostics.py` — already classifies the gap into a `category`, including `"optionality_premium"` vs `"market_pessimism"` vs `"wacc_overestimated"` / `"growth_underestimated"`.
- `backtest/` — MAPE, gap-closure, interval score, calibration curve, A/B comparison. **This is the acceptance gate.**

You are wiring existing signals into the value blend, not inventing new machinery.

---

## 2. Tasks

### T1 — Optionality-aware method reweighting in `weighted_value`
- In the value-blending path (`engine/scenario.py` / wherever `weighted_value` is finalized), detect optionality the same way `quality.py` does (structural `optionality` segment OR economic `_dcf_ratio < 0.7` OR `gap_diagnostics.category == "optionality_premium"`).
- For optionality names, produce the intrinsic value as a **blend that down-weights DCF toward the market-multiple / growth methods**, rather than a DCF/EBITDA-anchored point. Two acceptable designs — pick per data:
  1. **Method reweighting**: weight cross-validation methods by an evidence rule (e.g. drop or down-weight DCF when `_dcf_ratio < 0.7`, matching the convergence exclusion already used for the quality score), yielding a central estimate between floor and multiple-ceiling.
  2. **Explicit growth-option term**: generalize the rNPV pipeline-option precedent to a bounded growth-option value added to the DCF base (bounded and falsifiable, not open-ended).
- **Belt & suspenders**: non-optionality names (MSFT/AAPL-non-flagged, 비성장) must have `weighted_value` **unchanged** — assert this with a regression guard, exactly as the 2026-07-06 quality fix did (scores unchanged for non-optionality).

### T2 — Emit the range, not just the point
- Ensure `ValuationResult` (and the console + any `--json`) exposes a **valuation band**: conservative floor (DCF/Bear), central optionality-aware estimate, optimistic ceiling (Bull / market-multiple), and the `gap_diagnostics.category`. Downstream (orchestrator adapter) should be able to consume floor/central/ceiling without re-deriving them.

### T3 — `--json` export (also unblocks the orchestrator's Tier 1)
- Add a machine-readable output mode (this is the top item in `../investment-orchestrator/NEEDS_UPSTREAM.md`). Required fields: company, ticker, market, analysis_date, `weighted_value`, floor/central/ceiling band, per-method `cross_validations[].per_share`, scenario per-shares + probs, `quality` score/grade, `gap_diagnostics.category`, market_price, data freshness.

### T4 — Validate on the backtest (the real gate)
- Run `backtest/` A/B: intrinsic v0 (current floor) vs v1 (optionality-aware). The reweighting is accepted **only if it improves calibration** — MAPE / interval-score / gap-closure against realized outcomes — not merely if it raises values toward market. If v1 raises values but worsens calibration, it is wrong; report and revert.
- Explicitly check the non-optionality regression guard holds.

---

## 3. Acceptance criteria
1. Optionality names get a central estimate strictly **between** DCF floor and market-multiple ceiling, with the band exposed on `ValuationResult` + console + `--json`.
2. Non-optionality names: `weighted_value` and quality unchanged (regression test).
3. `--json` emits the full band + cross-vals + gap category.
4. Backtest A/B shows **calibration improvement** (or the change is reverted with findings written up). Value moving toward market is not, by itself, acceptance.
5. 삼성전자 remains below market even after reweighting **if** its Bull scenario is below market (genuinely stretched must stay flagged — this is the correctness check that the fix didn't just inflate everything).
6. Known pre-existing failure `TestFullPipeline::test_sk_ecoplant_profile` (WACC drift, unrelated) may remain; all other engine/quality tests pass.

## 4. Review questions
1. Reweighting vs explicit growth-option term — which does the backtest favor, and why?
2. Is the `_dcf_ratio < 0.7` threshold right for value reweighting, or does the value fix need a different (likely more conservative) threshold than the quality-score exclusion?
3. Does the optionality-aware value ever cross above market for a name the backtest later shows was overpriced (false BUY)? Quantify the risk.
4. Should the central estimate be probability-weighted across scenarios differently for convex names (fatter Bull tail), and does that help calibration?
