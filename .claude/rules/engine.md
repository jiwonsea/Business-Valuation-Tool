---
paths: ["engine/**/*.py", "schemas/models.py"]
---

# Engine Gotchas & Method/Scenario Rules

`engine/` functions must be pure (no IO, no state). `import httpx`, `requests` etc. forbidden. IO contract: `ValuationInput` → `ValuationResult` (`schemas/models.py`). Pydantic models are immutable inputs: never assign fields directly (`obj.field = x`). Use `obj.model_copy(update={...})`.

For rNPV specifics see `rnpv.md`; distress see `distress.md`; Monte Carlo see `monte-carlo.md`.

## Method & Scenario Selection

- **Auto method selection**: `engine/method_selector.py` branches to SOTP/DCF/DDM/RIM/NAV based on segment count, industry, ROE/Ke. Financials use ROE-Ke spread for DDM/RIM auto-selection. Manual override (`valuation_method`) takes priority.
- **Reverse DCF / Narrative→Numbers (Damodaran)**: When |market - intrinsic gap| ≥ 20%, `gap_diagnostics.py` auto-extracts implied WACC, TGR, or growth multiplier the market is pricing in. Primary DCF use case for optionality-heavy stocks — decoding market assumptions, not finding a 'correct' price target. If gap ≥ 50%, also re-verify raw data and assumptions.
- **Scenarios/probabilities**: AI proposes, but user makes final decisions.
- **Scenario probability grounding**: LLM-generated probabilities must be anchored to historical base rates and driver reference ranges. Pure LLM hallucination without empirical grounding produces identical distributions across companies. See `memory/reference_valuation_scenario_research.md` for Damodaran/McKinsey/Morgan Stanley frameworks.
- **Weekly auto-scenario 괴리율 (spread) calibration**: Weekly auto-generated Bull/Bear EV gap > 2x base EV indicates over-fit AI driver values — YAML profile calibration is the primary correction mechanism (SKHynix 4/12 confirmed). Review individual driver magnitudes against `_METHOD_DRIVERS` ranges after each weekly run. `segment_multiples` Bull/Bear ratio should not exceed 2x; if AI generates 5x Bear / 20x Bull, cap at 2x spread.
- **Scenario SOTP**: Bull/Bear scenarios must assign different EV/EBITDA multiples per segment — not only `growth_adj_pct`. Identical multiples across scenarios produce identical outputs (design omission, not a code bug). Software/platform segments use higher multiples in Bull, lower in Bear. Per-scenario WACC differentiation is approximated via multiple differences (higher multiple ≈ lower implied discount rate) — explicit per-scenario WACC not implemented.
- **Scenario driver 3-layer contract**: AI prompt (`_METHOD_DRIVERS` in `ai/prompts.py`), YAML persistence (`profile_generator.py`), and runtime (`valuation_runner.py`) must agree on which drivers each method supports. SOTP uses `segment_multiples`/`segment_ebitda`/`segment_revenue`/`growth_adj_pct`; DCF uses `growth_adj_pct`/`wacc_adj`/`terminal_growth_adj`; each method has its own set. Adding a new driver requires updating all three layers.
- **Scenario differentiation is already enforced — do NOT rebuild it.** `engine/scenario_validator.py` (`validate_scenario_differentiation`) + `profile_generator.py` post-generation check + quota-aware LLM repair loop enforce EV spread ≥1.3x / ≥2 differentiated drivers / Bull>Base>Bear direction / asymmetry, shipped commit `9db3339` (2026-04-15). A profile showing **identical Bull=Base=Bear EV is almost always a stale profile generated before that commit** (e.g. `035420.yaml` NAVER), NOT a missing feature or engine bug — verify generation date via `git log -- <profile>` before diagnosing. Engine driver application (`wacc_adj`/`growth_adj_pct`/`terminal_growth_adj`/`market_sentiment_pct`) is verified working in `valuation_runner.py:891-980`. Fix = regenerate the profile (`--auto`), not new code. The 4 permanent zero-diff exceptions are hand-crafted fixtures excluded by design (`kb_financial`, `kb_financial_rim`, `multiples_test`, `nav_test`).
- **Optionality stock DCF**: DCF assumes predictable cash flow path — unsuitable as sole method for binary-outcome segments (FSD, Robotics, autonomous fleet) where payoff is explosive-or-0. Terminal value typically exceeds 60% of total EV, causing extreme WACC/g sensitivity. Use DCF only as reverse engineering tool to decode market assumptions.
- **SOTP optionality segments**: Pre-profit segments use `method: ev_revenue` (EV = Revenue × EV/Revenue multiple). Distress discount is excluded for ev_revenue segments — comp multiples already embed balance sheet risk. EV/Revenue multiple ranges: Emerging tech 5-10x, Platform/SaaS 12-20x, Hyper-growth leader 25x+. `segment_revenue` provides per-scenario revenue overrides.
- **Real Options (B-S) → REJECTED** for individual segment valuation: stock IV already embeds the optionality being valued (circular), total stock IV cannot be disaggregated per segment (FSD vs. Robotaxi), and GBM assumption is violated by discrete binary outcomes. Exception (sanity check only): IV premium over sector average ≈ aggregate optionality premium the market prices in — compare directionally against reverse DCF implied growth multiplier.
- **Currency units**: `detect_unit()` fixes KR/US/JP storage to millions. Explicit non-million profiles must use a valid `currency_unit` ↔ `unit_multiplier` pair enforced by `CompanyProfile`.

## Core Numeric Gotchas

- No hardcoding `* 1_000_000` → use `engine.units.per_share()`.
- No hardcoding segment codes ("HI", "ALC", etc.) in sensitivity analysis.
- `segment_multiples`/`segment_ebitda`/`segment_revenue` keys in scenario YAML must be segment codes (`SEG1`, `AUTONOMOUS_DRIVING`), not human-readable names. LLM frequently generates Korean labels or ticker names instead. `load_profile()` warns on mismatch but doesn't auto-fix — verify keys after `--auto` generation.
- `per_share()` propagates negative equity (no zero-clamping). Distress scenarios yield negative per-share values. DLOM is not applied to negative equity. `build_holding_discount_bridge` records this case in `HoldingDiscountBridge.warnings` so reviewers can distinguish policy from omission.
- `sensitivity_multiple_range` propagates negative per-share values when equity < 0 (same as `calc_scenario`). Guard is `shares > 0` only — do NOT gate on `eq > 0`.
- Sensitivity multiples grid: when row_seg == col_seg, col_ev must be 0 to prevent double-counting the same segment's EV contribution.

## Method-Specific Gotchas

- NAV/Multiples: `market_sentiment_pct` is `elif` (mutually exclusive) with `nav_discount`/`ev_multiple` to prevent double-counting. RIM/DCF/DDM/SOTP apply it cumulatively (`if`). Do not unify — the asymmetry is intentional.
- **DDM/RIM `market_sentiment_pct` must apply to equity, not pseudo-EV.** `sc_ev = equity + net_debt` in DDM/RIM paths. Applying sentiment to sc_ev amplifies by leverage (9x D/E + 10% sentiment → 100% equity gain instead of 10%). Fix: apply to `sc_eq` before adding `net_debt`. Verified that `valuation_runner.py` now tracks `sc_eq` separately for both DDM and RIM.
- **Equity-direct methods (DDM, RIM, P/E, P/BV) output equity, not EV.** DDM/RIM add `net_debt` to convert equity→EV before `calc_scenario` (so the bridge subtracts it back correctly). NAV passes CPS/RCPS=0 because K-IFRS `total_liabilities` already includes them.
- DDM scenario loop must replicate the base `ke <= 0` guard explicitly (`if sc_ke <= 0: raise ValueError`). `calc_ddm` only checks `k <= g` — when `sc_ke < 0` AND `sc_growth < 0`, `k - g > 0` passes silently and returns a garbage equity value with negative cost of equity.
- **RIM terminal value**: `terminal_ri_base = BV_n * (last_roe - ke)` is already RI_{n+1} (using BV_n = beginning of period n+1). Do NOT apply extra `*(1+g)` — that would compute RI_{n+2}, overstating TV by `(1+g)` for ROE>ke and understating for ROE<ke.
- DCF terminal value uses normalized FCFF (NOPAT − ΔNWC, excluding capex-fade artifact from projection years). Raw last-year FCFF overstates TV when capex_to_da > 1. (MC TV resampling must use the same normalized FCFF — see `monte-carlo.md`.)
- `DCFParams.revenue_growth_rates`: optional separate revenue growth schedule. When provided, revenue projection uses it instead of `ebitda_growth_rates`. This feeds `delta_NWC` calculations correctly when margin expands/contracts. Falls back to `ebitda_growth_rates` when omitted (fully backward-compatible). Pad last value if shorter than `ebitda_growth_rates`.

## SOTP / Distress / PBV·PE Interplay

- SOTP path uses `effective_multiples` (distress-adjusted), not `vi.multiples`. New code touching SOTP calculation (scenarios, sensitivity, Monte Carlo) must use `effective_multiples` — using raw `vi.multiples` bypasses distress discount silently.
- PBV/PE segments are cross-cutting: changes touch SOTP (`sotp.py`), MC (`monte_carlo.py` skip logic), sensitivity (`sensitivity.py` fixed_ev + same_seg guard), and scenario equity bridge (`valuation_runner.py` net_debt add-back). Test all four when modifying PBV/PE behavior.
- `segment_method_override` (ev_revenue→ev_ebitda transition) requires `segment_ebitda` for the transitioned segment in the same scenario — D&A re-allocation alone yields near-zero EBITDA for formerly-excluded segments.
- `cross_validate(sotp_ev_ebitda_only=...)`: when SOTP mixes EV-based (ev_ebitda, ev_revenue) and equity-based (pbv, pe) segments, `total_ev` includes equity values that inflate the implied EV/EBITDA multiple. Pass `sum(r.ev for r in sotp.values() if not r.is_equity_based)` as `sotp_ev_ebitda_only` — used only for implied multiple calculation; equity bridge still uses full `sotp_ev`. Both SOTP and DCF cross-validation paths in `valuation_runner.py` pass this.
- Cross-validation DCF calls in non-DCF methods (Multiples/NAV) are now guarded with try/except. When adding new cross-validation paths, follow the same pattern — `calc_dcf()` raises `ValueError` on `ebitda<=0` or `WACC<=TG`.

## Scenario Drivers & Convertibles

- `NewsDriver.effects` is `dict[str, float]` (scalar-only). Structured per-segment overrides (`segment_multiples`, `segment_ebitda`) go directly on `ScenarioParams`, not through the news_drivers→resolve_drivers path.
- `rcps_repay` is `Optional[int] = None` (like `cps_repay`). Use `_derive_rcps_repay(ref_sc, vi)` for all RCPS repay calculations — it handles IRR-based compounding when explicit repay is absent. Raw `sc.rcps_repay or 0` drops compounding. The `is not None` vs `> 0` distinction is load-bearing for explicit-zero overrides. `_derive_rcps_repay` no longer requires `sc.irr is not None`; when `irr` is None it mirrors `calc_scenario`'s `(sc.irr or 0)` fallback.
- **`ScenarioParams.cps_irr` / `rcps_irr`**: Optional per-instrument IRR fields. When set, CPS uses `cps_irr`, RCPS uses `rcps_irr`; both fall back to `irr` when their specific field is None. This separation is load-bearing when CPS and RCPS investors have different return requirements. `_derive_rcps_repay`, `calc_scenario`, and MC `irr` parameter all honor this hierarchy.
- `sensitivity_irr_dlom` triggers for CPS or RCPS (not CPS-only). Caller guard is `if vi.cps_principal > 0 or vi.rcps_principal > 0`. When `rcps_principal > 0` is passed, RCPS repayment is recomputed per-IRR inside the loop (same as CPS). When `rcps_principal == 0`, the precomputed `rcps_repay` scalar is used unchanged (backward-compatible).
- `consolidated` dict does NOT contain WACC params (`kd_pre`, `rf`, `erp`). Those live on `vi.wacc_params`. Reading `consolidated.get("kd_pre", fallback)` silently returns fallback — pass WACC params explicitly.
- Silent zero defaults: `liabilities: 0` or `de_ratio: 0` in consolidated data is almost always a data ingestion error for operating companies — verify before running valuation.

## Units — prevent silent 100x per-share errors

- `detect_unit()` does not infer storage units from revenue scale. KR=`백만원`, US=`$M`, JP=`百万円`; all use `unit_multiplier=1_000_000`.
- Explicit alternate units remain supported only as consistent pairs, e.g. `억원 ↔ 100_000_000`, `$B ↔ 1_000_000_000`. `CompanyProfile` rejects known-label mismatches at load time.
- `per_share()` remains multiplier-agnostic. Never hardcode `* 1_000_000`; validate the profile pair and pass `company.unit_multiplier`.

## SOTP scenario multiples are silently clamped (not a bug — read before designing scenarios)

- `load_profile()` caps every scenario's `segment_multiples[seg]` at **2.0× the per-segment minimum across all scenarios** (`valuation_runner.py:315-352`, `_SOTP_MAX_RATIO = 2.0`). The Bear multiple therefore sets the ceiling for Bull.
- The 2.0× limit is the entire Bear→Bull budget: `(Base/Bear) × (Bull/Base) = Bull/Bear ≤ 2.0`. Because quality scoring requires `Bull/Base ≥ 1.20`, setting `Base/Bear > 2.0/1.20 = 1.667` makes a quality deduction mathematically unavoidable. Keep Base/Bear at or below 1.667 when both the clamp and quality threshold must pass.
- Consequence: a hand-authored Bull of 3.0 against a Bear of 0.8 is rewritten to **1.6**, collapsing Bull onto Base and producing a degenerate model (Bull/Base EV spread 1.05x) that still *prints as if it ran*. It logs at INFO, which the CLI does not surface.
- **Design scenarios inside the 2x band from the start** (e.g. Bear 1.0 / Base 1.5 / Bull 2.0). If a genuinely wider spread is warranted, compute it outside the engine and report it explicitly as an uncapped sensitivity — do not raise `_SOTP_MAX_RATIO` to fit one company.
- Verify after every `load_profile()`: `{k: sc.segment_multiples for k, sc in vi.scenarios.items()}` should equal what the YAML says.
