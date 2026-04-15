# CLAUDE.md

@~/.claude/CLAUDE.md

## Project

KR/US company valuation platform. Pure-function engine + Pydantic schemas + YAML profiles + AI-assisted analysis. Python 3.11+.

## Architecture

```
ValuationInput (YAML) → run_valuation() → ValuationResult → print_report() / Excel
```

- `engine/` — Pure functions (no IO). `method_selector.py` auto-selects methodology by company type. `rnpv.py` — risk-adjusted NPV for pharma/biotech pipeline valuation. `quality.py` — composite 0-100 quality score (`calc_quality_score()`); rNPV restructures cv_convergence bucket (DCF excluded) and market_alignment bucket (15+10 split).
- `schemas/models.py` — Pydantic models. Core contract: `ValuationInput` → `ValuationResult`.
- `pipeline/` — Data collection (DART, SEC EDGAR, Yahoo Finance). IO only here.
- `ai/` — LLM-based segment classification, peer recommendation, scenario design (Claude Sonnet 4).
- `db/` — Supabase integration. `client.py` (singleton), `repository.py` (CRUD), `migrations.sql` (DDL).
- `output/` — Excel 7-sheet (assumptions, D&A, SOTP, scenarios, DCF, sensitivity, cross-validation).
- `scheduler/` — Weekly auto news collection + valuation. `weekly_run.py` (pipeline), `scoring.py` (importance).
- `cli.py` — CLI entry point + `run_valuation()` (SOTP/DCF branching).
- `orchestrator.py` — Profile → valuation → Excel pipeline wrapper.
- `app.py` — Streamlit web UI.

## Commands

```bash
python cli.py --profile profiles/sk_ecoplant.yaml        # profile-based
python cli.py --profile profiles/sk_ecoplant.yaml --excel # Excel output
python cli.py --company "AAPL"                            # auto-fetch (US)
python cli.py --company "삼성E&A"                          # auto-fetch (KR, needs DART_API_KEY)
python cli.py --company "MSFT" --auto                     # with AI analysis
python cli.py --discover --market KR                      # news-based company discovery
python cli.py --weekly                                    # weekly auto-analysis (KR+US, 3 companies)
python cli.py --weekly --markets KR --max-companies 5     # specify market/count
python cli.py --weekly --dry-run                          # discovery only, skip valuation
python cli.py --backtest --backtest-min-age 90            # calibration backtesting report
python -m scheduler.weekly_run                            # direct module execution

streamlit run app.py                                      # web UI
pytest tests/                                             # tests
pip install -e ".[dev,pipeline,ai,ui,db]"                  # install dependencies
```

## Workflow Rules

- **Session-start backlog validation**: Before acting on NEXT_SESSION_PROMPT items, check whether they were already resolved in another session. Review `git log --oneline -15` and inspect the files/functions named in the prompt before starting work. If already resolved, refresh the backlog first.
- **Regression audit timestamp check**: Weekly artifacts under `valuation-results/YYYY-MM-DD(...)/` and `logs/weekly_YYYYMMDD.log` are frozen snapshots of pipeline state at run time. Before diagnosing a "regression bug" from an old artifact, compare its mtime against `git log -- <file>` for the suspect code — stale snapshots masquerade as regressions already fixed upstream.
- **Auto method selection**: `engine/method_selector.py` branches to SOTP/DCF/DDM/RIM/NAV based on segment count, industry, ROE/Ke. Financials use ROE-Ke spread for DDM/RIM auto-selection. Manual override (`valuation_method`) takes priority.
- **Reverse DCF / Narrative→Numbers (Damodaran)**: When |market - intrinsic gap| ≥ 20%, `gap_diagnostics.py` auto-extracts implied WACC, TGR, or growth multiplier the market is pricing in. Primary DCF use case for optionality-heavy stocks — decoding market assumptions, not finding a 'correct' price target. If gap ≥ 50%, also re-verify raw data and assumptions.
- **Scenarios/probabilities**: AI proposes, but user makes final decisions.
- **Weekly auto-scenario 괴리율 (spread) calibration**: Weekly auto-generated Bull/Bear EV gap > 2x base EV indicates over-fit AI driver values — YAML profile calibration is the primary correction mechanism (SKHynix 4/12 confirmed). Review individual driver magnitudes against `_METHOD_DRIVERS` ranges after each weekly run. `segment_multiples` Bull/Bear ratio should not exceed 2x; if AI generates 5x Bear / 20x Bull, cap at 2x spread.
- **Scenario probability grounding**: LLM-generated probabilities must be anchored to historical base rates and driver reference ranges. Pure LLM hallucination without empirical grounding produces identical distributions across companies. See `memory/reference_valuation_scenario_research.md` for Damodaran/McKinsey/Morgan Stanley frameworks.
- **Scenario SOTP**: Bull/Bear scenarios must assign different EV/EBITDA multiples per segment — not only `growth_adj_pct`. Identical multiples across scenarios produce identical outputs (design omission, not a code bug). Software/platform segments use higher multiples in Bull, lower in Bear. Per-scenario WACC differentiation is approximated via multiple differences (higher multiple ≈ lower implied discount rate) — explicit per-scenario WACC not implemented.
- **Scenario driver 3-layer contract**: AI prompt (`_METHOD_DRIVERS` in `ai/prompts.py`), YAML persistence (`profile_generator.py`), and runtime (`valuation_runner.py`) must agree on which drivers each method supports. SOTP uses `segment_multiples`/`segment_ebitda`/`segment_revenue`/`growth_adj_pct`; DCF uses `growth_adj_pct`/`wacc_adj`/`terminal_growth_adj`; each method has its own set. Adding a new driver requires updating all three layers.
- **Optionality stock DCF**: DCF assumes predictable cash flow path — unsuitable as sole method for binary-outcome segments (FSD, Robotics, autonomous fleet) where payoff is explosive-or-0. Terminal value typically exceeds 60% of total EV, causing extreme WACC/g sensitivity. Use DCF only as reverse engineering tool to decode market assumptions.
- **SOTP optionality segments**: Pre-profit segments use `method: ev_revenue` (EV = Revenue × EV/Revenue multiple). Distress discount is excluded for ev_revenue segments — comp multiples already embed balance sheet risk. EV/Revenue multiple ranges: Emerging tech 5-10x, Platform/SaaS 12-20x, Hyper-growth leader 25x+. `segment_revenue` provides per-scenario revenue overrides.
- **Real Options (B-S) → REJECTED** for individual segment valuation: stock IV already embeds the optionality being valued (circular), total stock IV cannot be disaggregated per segment (FSD vs. Robotaxi), and GBM assumption is violated by discrete binary outcomes. Exception (sanity check only): IV premium over sector average ≈ aggregate optionality premium the market prices in — compare directionally against reverse DCF implied growth multiplier.
- **Currency units**: Auto-determined from financial statement scale (`engine/units.py`). No hardcoding.

## rNPV Engine Rules

- **Revenue curve**: Ramp-up → Plateau → Decline (patent expiry). Three branches:
  - `existing_revenue >= peak_sales`: plateau at existing, then decline
  - `0 < existing_revenue < peak_sales`: ramp from existing to peak, plateau, then decline (Wegovy case)
  - `existing_revenue == 0`: ramp from 0 to peak, plateau, then decline
- **PoS override**: drug-level `success_prob` takes priority over `PHASE_POS` lookup table
- **R&D cost**: `r_and_d_cost=0` means R&D is embedded in operating margin (no deduction). Setting both `r_and_d_cost > 0` AND high `default_margin` risks double-counting.
- **NPV discount**: `_npv()` starts at t=0 (first cash flow undiscounted). This is intentional — `launch_year_offset` handles pre-launch zeros, so t=0 is the launch year.
- **enterprise_value = pipeline_value**: `existing_revenue_value` is already included in `total_rnpv` (approved drugs have PoS=1.0). The `existing_revenue_value` field is a reporting-only subset — do not add it to `pipeline_value`.
- **Decline base**: Decline always starts from `peak_sales` unless `existing_revenue >= peak_sales` (then from `existing_revenue`). Never from a mid-ramp value.
- **Scenario drivers**: `growth_adj_pct` adjusts peak sales, `wacc_adj` adjusts discount rate, `pos_override` dict (`{drug_name: 0-1}`) overrides per-drug PoS. All three are independent and composable.
- **patent_expiry_years**: Total remaining commercial life — ramp + plateau + decline all fit within this window. NOT "years until decline starts." If ramp+plateau exceeds this value, decline phase is skipped (edge case, no current profiles trigger this).
- **Excel output**: rNPV produces two extra sheets — "rNPV Pipeline" (summary table + equity bridge) and "Revenue Curves" (year-by-year revenue per drug, chart-ready data).
- **cash_flows vs revenue_curve**: `DrugCashFlow.cash_flows` = after-tax operating profit (revenue × margin × (1-tax)). `revenue_curve` = raw revenue projection. Excel Revenue Curves sheet uses `revenue_curve`, not `cash_flows`.
- **Reverse rNPV**: `engine/reverse_rnpv.py` — binary search for implied PoS scale, peak-sales scale, and discount rate that reconcile model EV with market EV. Called from `cli.py:_attach_reverse_rnpv()` when primary_method=="rnpv" and market price available. Result stored in `ValuationResult.reverse_rnpv`.
- **rNPV Sensitivity**: `sensitivity_rnpv()` = discount rate × PoS scale 2D table (uses `sensitivity_primary` slot). `sensitivity_rnpv_tornado()` = per-drug ±20% peak sales impact on per-share value (stored in `ValuationResult.rnpv_tornado`).
- **PoS cap in reverse/sensitivity**: When scaling PoS uniformly, approved drugs (PoS=1.0) are already capped — only pipeline drugs' PoS can increase. This limits the range of achievable EV via PoS-only scaling when approved drugs dominate.
- **Per-drug solo PoS**: `solve_implied_per_drug_pos()` uses direct algebraic solve (not binary search) — rNPV is linear in each drug's PoS: `implied_pos = gap / npv_i + base_pos`. O(1) total (single `calc_rnpv` call). Filter: `success_prob < 1.0`. Returns `solvable=False` when implied_pos outside [0, 1], with `max_ev_contribution` showing the drug's max marginal EV at PoS=1.0. Results are NOT additive across drugs.

## Conventions

- English code/comments; Korean user-facing output.
- **Excel filename — local vs remote**: local files (`output/excel_builder.py:56`) use the Korean convention `{company}_밸류에이션_모델.xlsx` (e.g., `삼성전자_밸류에이션_모델.xlsx`) for human readability in the results folder. Supabase-uploaded filenames (`_upload_excels_to_storage` in `scheduler/weekly_run.py`) use `CamelCase(MM-DD)_valuation.xlsx` to avoid Windows/URL encoding issues: `_to_camel()` strips `co.`/`corp.`/`inc.`/`ltd.` suffixes, title-cases remaining words, joins first 3; date is pulled from the week folder via `(\d{2})-(\d{2})`. Examples: `SamsungElectronics(04-12)_valuation.xlsx`, `AAPL(04-12)_valuation.xlsx`. Do not expect local and remote names to match.
- Env vars: `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `DART_API_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `SUPABASE_URL`, `SUPABASE_KEY`
- `engine/` functions must be pure (no IO, no state). `import httpx`, `requests` etc. forbidden.
- IO contract: `ValuationInput` → `ValuationResult` (`schemas/models.py`).
- New YAML profile fields must be Optional with defaults (backward compatibility).
- Pydantic models are immutable inputs: never assign fields directly (`obj.field = x`). Use `obj.model_copy(update={...})` to create modified copies.

## Testing

```bash
pytest tests/                    # all
pytest tests/test_engine.py -k "test_sk_wacc"  # individual
```

- Engine pure function tests: fixed input → exact value assertion OK.
- Pipeline E2E tests: range-based validation. Avoid exact-value regression since methodology may vary by company type.
- **`profiles/` is AI-regenerated, not a test fixture**: the weekly pipeline rewrites `profiles/*.yaml` (scenario codes drift Bull/Base/Bear ↔ A/B/C/D), so tests that load from `profiles/` with hardcoded keys break after every run. Fix by moving test-owned YAML into `tests/fixtures/`. Current casualty: `TestScenarioDriverRoundTrip::test_sotp_segment_multiples_differentiate_ev` and `::test_yaml_segment_multiples_round_trip` — deselect with `--deselect tests/test_engine.py::TestScenarioDriverRoundTrip` until fixtures are split.
- **DB repository tests** use a Fake Supabase query builder pattern (`tests/test_backtest_repository.py` — records every chained `.select/.or_/.eq/.upsert/.execute` call, returns fake data). Reuse for new `db/*_repository.py` tests instead of mocking each call site.

## Efficiency

- **Batch LLM calls**: Use `recommend_peers_batch()` for multi-segment companies (1 call vs N segments).
- **System prompt caching**: Static reference content (driver definitions, format specs) belongs in system prompts. Anthropic ephemeral cache gives 90% input cost reduction; OpenRouter gets no cache benefit but shorter user prompts reduce retry cost.
- **Persistent ticker cache**: KR ticker → KOSPI/KOSDAQ resolution persists to `.cache/kr_tickers.json`. No TTL needed (exchange assignments are permanent).
- **Pipeline data sharing**: Scoring phase `market_cap_usd` flows into valuation via `scored_data` parameter in `auto_analyze()`.
- **News summary caching**: `summarize_key_issues()` results are disk-cached (7-day TTL) via `ai/analyst.py` cache infrastructure.
- **Target: ≤4 LLM calls/company** (classify + peers_batch + wacc + scenarios). Optionality segment detection is merged into the scenarios call — no extra quota. Daily LLM quota: 50 calls.
- **Quota safety net**: `weekly_run.py` auto-trims targets if `len(targets) * 4 > remaining_llm_quota`.

## Distress Discount Engine Rules

- **Cap = 25% (default)**: Damodaran empirical studies show public-company peer-multiple haircuts cluster at 20-25% median, ~30% at 90th percentile. 35%+ applies only to Chapter 11 / near-bankruptcy proceedings, not going-concern SOTP. Profiles needing >25% must set `distress_max_discount` explicitly in YAML.
- **Cyclical 1-year loss exemption**: `loss_streak` counts consecutive years with EBITDA (op + dep + amort) < 0, not net_income — avoids penalising one-off items (tax, FX, impairment); `op` is post-D&A so add-back is correct. `loss_streak == 1` triggers no penalty for auto/steel/shipping/semiconductor/oil/construction/chemical industries (`_CYCLICAL_KEYWORDS` in `distress.py`). 2-year streak → 5% (vs 10% for non-cyclical). 3+ years → 15% regardless.
- **Segment-level differentiation**: `apply_distress_discount()` supports three tiers — `exempt_segments` (0% haircut: ev_revenue, distress_exempt), `healthy_segments` (50% of discount: profitable + significant asset share), and default (full discount). `valuation_runner.py` auto-populates `healthy` when `len(segments) >= 3 and distress.applied` — a segment qualifies only if `op > 0` AND `asset_share >= _HEALTHY_MIN_ASSET_SHARE_PCT` (20%). When all segment `assets` are 0 (missing data), falls back to `op > 0` only.
- **ev_revenue segments always exempt**: distress discount is excluded for ev_revenue segments because comp multiples already embed balance sheet risk.

## Gotchas

- `reverse_rnpv.gap_pct = (model_ev - target_ev) / target_ev * 100`. `gap_pct < 0` ⟹ market > model ⟹ "시장 낙관". Label is counterintuitive — do NOT invert. Verified in engine/reverse_rnpv.py:307.
- `per_share()` propagates negative equity (no zero-clamping). Distress scenarios yield negative per-share values. DLOM is not applied to negative equity. `build_holding_discount_bridge` records this case in `HoldingDiscountBridge.warnings` so reviewers can distinguish policy from omission.
- No hardcoding `* 1_000_000` → use `engine.units.per_share()`.
- No hardcoding segment codes ("HI", "ALC", etc.) in sensitivity analysis.
- New YAML profile fields must always be Optional with defaults (backward compatibility).
- NAV/Multiples: `market_sentiment_pct` is `elif` (mutually exclusive) with `nav_discount`/`ev_multiple` to prevent double-counting. RIM/DCF/DDM/SOTP apply it cumulatively (`if`). Do not unify — the asymmetry is intentional.
- `NewsDriver.effects` is `dict[str, float]` (scalar-only). Structured per-segment overrides (`segment_multiples`, `segment_ebitda`) go directly on `ScenarioParams`, not through the news_drivers→resolve_drivers path.
- `--auto` overwrites the entire profile YAML. Never use on hand-crafted test profiles (`_template`, `nav_test`, `multiples_test`, `kb_financial_rim`) or profiles with manual `valuation_method` override (e.g., `kb_financial` DDM).
- After changing AI prompts in `ai/prompts.py`, clear `.cache/llm/*_scenarios_*.json` before re-testing — cached responses won't reflect prompt changes.
- Silent zero defaults: `liabilities: 0` or `de_ratio: 0` in consolidated data is almost always a data ingestion error for operating companies — verify before running valuation.
- DART `parse_financial_statements()` includes `capex` key only when a matching PPE-acquisition account is found in CF items; if absent, key is not created and `profile_generator` falls back to `capex_to_da=1.10`. DART investing outflows are reported negative — stored via `abs()`.
- `get_market_cap()` (`pipeline/yahoo_finance.py`) returns raw currency units (full KRW or USD, not millions). `scoring.py _fetch_market_cap_usd` divides raw KRW by `_KRW_TO_USD=1350` — do not pre-convert to millions before passing.
- `pipeline/yfinance_fetcher.py` calls `yf.Ticker().info` which may return price but omit `marketCap` for KR tickers. When `market_cap_raw == 0`, the KR path breaks out of the retry loop and falls back to `get_quote_summary()`. The `if market == "KR" and not market_cap_raw: break` guard enables this fallback — do not remove it.
- Two bucket functions exist and are NOT parallel: `infer_valuation_bucket` (engine/method_selector.py) derives the rich bucket from live `ValuationInput` (primary_method + industry + has_holding_structure + has_optionality_segments) and is written to `prediction_snapshots.valuation_bucket` at save time; `classify_bucket` (backtest/buckets.py) only reads that stored value back. Because the migration added the column with DEFAULT `'plain_operating'`, snapshots saved before commit `1668243` silently carry `plain_operating` even when they should be `financials` / `holding_governance_sensitive` / `optionality_heavy` — backtest bucket breakdowns are biased toward `plain_operating` until pre-feature rows are re-run through the current pipeline.
- `db/migrations_backtest.sql` owns the `prediction_snapshots` schema. When adding new columns written by `db/backtest_repository.py` to `prediction_snapshots`, add a corresponding `ALTER TABLE prediction_snapshots ADD COLUMN IF NOT EXISTS` to `migrations_backtest.sql` in the same commit — missing columns cause the save to log an exception and return `None`. Committing the migration file does NOT apply it to Supabase — manually run in Supabase SQL Editor or execute `supabase db push` after commit. Otherwise runtime fails with PGRST204 'column not found' (sk_ecoplant.yaml 2026-04-15 regression).
- Valuation entry paths diverge on DB persistence: `orchestrator.run_from_profile` (called from `cli.py --profile`) calls `_save_to_db`; `pipeline.profile_generator.auto_analyze` (called from `cli.py --company` and `scheduler/weekly_run.py`) does NOT. Both produce identical `ValuationResult`, only persistence differs. Any new save/snapshot/log-to-DB call must be wired into BOTH paths, or the asymmetry documented explicitly in this file. Weekly pipeline's missing snapshots trace to this gap.
- `estimate_borrowings()` is called inside `parse_financial_statements()` — `gross_borr`/`net_borr` are included in the DART result automatically. Calling it again externally on the same items double-counts debt.
- SOTP path uses `effective_multiples` (distress-adjusted), not `vi.multiples`. New code touching SOTP calculation (scenarios, sensitivity, Monte Carlo) must use `effective_multiples` — using raw `vi.multiples` bypasses distress discount silently.
- `consolidated` dict does NOT contain WACC params (`kd_pre`, `rf`, `erp`). Those live on `vi.wacc_params`. Reading `consolidated.get("kd_pre", fallback)` silently returns fallback — pass WACC params explicitly.
- Monte Carlo DCF TV variation (`ev *= dcf_ev_sample/dcf_ev_base`) applies only to `ev_ebitda_part`. `ev_revenue_part` is added after TV adjustment — revenue-based optionality is independent of DCF terminal value assumptions.
- Monte Carlo multiples sampling uses **lognormal** (Damodaran standard: always ≥ 0, right-skewed). Parameters are derived from desired mean/std: `sigma_ln = sqrt(ln(1 + (s/m)²))`, `mu_ln = ln(m) - 0.5*sigma_ln²`. Falls back to normal+floor when `mu <= 0 or sigma <= 0`.
- Monte Carlo negative equity is preserved in full-distribution statistics (mean, percentiles). Histogram display filters negatives out. `pct_negative` counts true negatives before any filtering. Do NOT clamp `ps = max(ps, 0)` — this upward-biases all statistics. `MonteCarloResult.pct_negative` must be explicitly copied in `_mc_raw_to_result()` — omission silently defaults to 0.
- Per-scenario MC (`_run_monte_carlo` inner loop) must pass `cps_dividend_rate=vi.cps_dividend_rate`. Missing it defaults to 0.0, making effective IRR = full IRR (overstates CPS repayment when `cps_dividend_rate > 0`).
- `segment_method_override` (ev_revenue→ev_ebitda transition) requires `segment_ebitda` for the transitioned segment in the same scenario — D&A re-allocation alone yields near-zero EBITDA for formerly-excluded segments.
- `console_report.py` `is_mixed` must stay in sync with `_needs_method_dispatch()` in valuation_runner — both should trigger on any non-default method (ev_revenue, pbv, pe). Equity Bridge display is conditional on pbv/pe only.
- `get_client()` returns `None` silently when `SUPABASE_URL`/`SUPABASE_KEY` are missing. DB-dependent features (backtest, save_valuation) degrade silently — check `.env` exists before debugging "empty results."
- Cross-validation DCF calls in non-DCF methods (Multiples/NAV) are now guarded with try/except. When adding new cross-validation paths, follow the same pattern — `calc_dcf()` raises `ValueError` on `ebitda<=0` or `WACC<=TG`.
- `ApiGuard.check(provider)` must be in a dedicated `try/except ApiGuardError` block, NOT inside the same `except Exception` as the HTTP call. Mixed handling calls `record_failure()` on circuit-blocked requests, resetting the cooldown timer — circuit never recovers during a run. Pattern: `try: guard.check() / except ApiGuardError: return []` then separate `try: ...http... / except Exception: guard.record_failure()`.
- `ask()` OpenRouter fallback must catch `ApiGuardError` alongside `httpx.HTTPError`. `CircuitOpenError` is a subclass of `ApiGuardError`, not `RuntimeError` — without this, Anthropic fallback never triggers when the openrouter circuit is open (`ai/llm_client.py`).
- `rcps_repay` is `Optional[int] = None` (like `cps_repay`). Use `_derive_rcps_repay(ref_sc, vi)` for all RCPS repay calculations — it handles IRR-based compounding when explicit repay is absent. Raw `sc.rcps_repay or 0` drops compounding. The `is not None` vs `> 0` distinction is load-bearing for explicit-zero overrides. `_derive_rcps_repay` no longer requires `sc.irr is not None`; when `irr` is None it mirrors `calc_scenario`'s `(sc.irr or 0)` fallback — so RCPS principal is included in MC equity bridge even for scenarios with no explicit IRR.
- Mixed-method SOTP Monte Carlo must use `effective_net_debt` (via `net_debt_override`), not `vi.net_debt`. PBV/PE segment equity values already embed net_debt — using full net_debt double-deducts.
- PBV/PE segments are cross-cutting: changes touch SOTP (`sotp.py`), MC (`monte_carlo.py` skip logic), sensitivity (`sensitivity.py` fixed_ev + same_seg guard), and scenario equity bridge (`valuation_runner.py` net_debt add-back). Test all four when modifying PBV/PE behavior.
- DCF terminal value uses normalized FCFF (NOPAT − ΔNWC, excluding capex-fade artifact from projection years). Raw last-year FCFF overstates TV when capex_to_da > 1. **MC DCF TV resampling** (`_run_monte_carlo` in `valuation_runner.py`) must use the same normalized FCFF (`last_p.nopat - last_p.delta_nwc`), not `last_p.fcff` — raw FCFF perpetuates capex deviations into all MC TV samples.
- **RIM terminal value**: `terminal_ri_base = BV_n * (last_roe - ke)` is already RI_{n+1} (using BV_n = beginning of period n+1). Do NOT apply extra `*(1+g)` — that would compute RI_{n+2}, overstating TV by `(1+g)` for ROE>ke and understating for ROE<ke.
- **MC DCF TV spread guard**: `run_monte_carlo` enforces a minimum WACC-TG spread of 0.5% (`_MIN_SPREAD=0.005`) before computing sampled TV. Without it, samples where w−g < 0.1% produce TV 50x+ base, creating fat-tail distortion in MC distribution even when ratio is clipped to 3x.
- **Equity-direct methods (DDM, RIM, P/E, P/BV) output equity, not EV.** DDM/RIM add `net_debt` to convert equity→EV before `calc_scenario` (so the bridge subtracts it back correctly). NAV passes CPS/RCPS=0 because K-IFRS `total_liabilities` already includes them.
- DDM scenario loop must replicate the base `ke <= 0` guard explicitly (`if sc_ke <= 0: raise ValueError`). `calc_ddm` only checks `k <= g` — when `sc_ke < 0` AND `sc_growth < 0`, `k - g > 0` passes silently and returns a garbage equity value with negative cost of equity.
- Sensitivity multiples grid: when row_seg == col_seg, col_ev must be 0 to prevent double-counting the same segment's EV contribution.
- `segment_multiples`/`segment_ebitda`/`segment_revenue` keys in scenario YAML must be segment codes (`SEG1`, `AUTONOMOUS_DRIVING`), not human-readable names. LLM frequently generates Korean labels or ticker names instead. `load_profile()` warns on mismatch but doesn't auto-fix — verify keys after `--auto` generation.
- `pos_override` keys are drug name strings (exact match against YAML pipeline `name` field). Renaming a drug in YAML without updating scenario `pos_override` keys silently drops the override.
- `DCFParams.revenue_growth_rates`: optional separate revenue growth schedule. When provided, revenue projection uses it instead of `ebitda_growth_rates`. This feeds `delta_NWC` calculations correctly when margin expands/contracts. Falls back to `ebitda_growth_rates` when omitted (fully backward-compatible). Pad last value if shorter than `ebitda_growth_rates`.
- `cross_validate(sotp_ev_ebitda_only=...)`: when SOTP mixes EV-based (ev_ebitda, ev_revenue) and equity-based (pbv, pe) segments, `total_ev` includes equity values that inflate the implied EV/EBITDA multiple. Pass `sum(r.ev for r in sotp.values() if not r.is_equity_based)` as `sotp_ev_ebitda_only` — used only for implied multiple calculation; equity bridge still uses full `sotp_ev`. Both SOTP and DCF cross-validation paths in `valuation_runner.py` pass this.
- `sensitivity_multiple_range` propagates negative per-share values when equity < 0 (same as `calc_scenario`). Guard is `shares > 0` only — do NOT gate on `eq > 0`.
- `_write_assumption_drivers` writes exactly ONE row (no `r` return). New valuation method branches must fit a single row, or the function signature must be extended to return `r`.
- rNPV cross-validation: the first CV item is labeled `"SOTP (EV/EBITDA)"` but holds the rNPV primary EV (passed as `sotp_ev` to `cross_validate()`). The DCF entry is exactly `"DCF (FCFF)"` — used in `_RNPV_EXCLUDED_CV_METHODS` in `engine/quality.py` to exclude it from rNPV convergence scoring.
- **Quality score rNPV restructuring**: For `primary_method=="rnpv"`, `cv_convergence` (25pts) is NOT a single CV — it's `rnpv_weighted_cv` (0-10, DCF excluded) + `rnpv_pipeline_diversity` (0-8) + `rnpv_pos_grounding` (0-6) + `rnpv_scenario_coverage` (0-1, pos_override in ≥1 scenario). Similarly `market_alignment` splits into price gap (0-15) + `rnpv_reverse_consistency` (0-10). Standard `_cv_convergence_score()` is NOT called for rNPV. `format_quality_report()` in `engine/quality.py` handles both modes; called from `console_report.py`.
- **DDM/RIM `market_sentiment_pct` must apply to equity, not pseudo-EV.** `sc_ev = equity + net_debt` in DDM/RIM paths. Applying sentiment to sc_ev amplifies by leverage (9x D/E + 10% sentiment → 100% equity gain instead of 10%). Fix: apply to `sc_eq` before adding `net_debt`. Verified that `valuation_runner.py` now tracks `sc_eq` separately for both DDM and RIM.
- **`ScenarioParams.cps_irr` / `rcps_irr`**: Optional per-instrument IRR fields. When set, CPS uses `cps_irr`, RCPS uses `rcps_irr`; both fall back to `irr` when their specific field is None. This separation is load-bearing when CPS and RCPS investors have different return requirements. `_derive_rcps_repay`, `calc_scenario`, and MC `irr` parameter all honor this hierarchy.
- **Distress ICR prefers actual `interest_expense` over estimate.** `calc_distress_discount` checks `base.get("interest_expense", 0)` first; falls back to `gross_borr × kd_pre / 100` when absent. yfinance (US) provides this automatically; DART parser now extracts `이자비용`/`금융비용`/`금융원가` for KR companies. Do not remove the fallback — many older profiles and manual YAMLs won't have this field.
- **`sensitivity_irr_dlom` triggers for CPS or RCPS** (not CPS-only). Caller guard is `if vi.cps_principal > 0 or vi.rcps_principal > 0`. When `rcps_principal > 0` is passed, RCPS repayment is recomputed per-IRR inside the loop (same as CPS). When `rcps_principal == 0`, the precomputed `rcps_repay` scalar is used unchanged (backward-compatible).
- `output/sheets/rnpv.py` Peak Revenue and summary sections must iterate `rnpv.drug_results` (all drugs), not `drugs_with_curves` (subset that only includes drugs with computed revenue curves). `drugs_with_curves` silently omits early-stage pipeline drugs that have a PoS but no revenue curve.
- `rnpv_pct` calculation in `output/sheets/rnpv.py` uses `!= 0` guard (not `> 0`). When `total_rnpv < 0` (all drugs net-negative NPV), the `> 0` guard silently zeros all drug percentages; `!= 0` correctly computes negative proportions.
- Weekly pipeline outputs to `valuation-results/YYYY-MM-DD(Month Xth week)/`. `_weekly_summary.json` is the regression-detection entry point — check `discoveries[].companies` (filter/buffer efficacy) and `valuations[].status` (`no_result` = regression per market). Filenames in that folder reveal whether Excel naming convention is actually applied in production runs.
- Windows `python -c` one-liners that emit Korean fail with `UnicodeEncodeError: 'cp949'`. Prefix shell call with `PYTHONIOENCODING=utf-8` AND rewrap stdout: `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')`. Running as a saved `.py` script usually avoids this; inline `-c` invocation does not.
- Ad-hoc DB probes (`python -c`, one-off `scripts/*.py`) must call `from dotenv import load_dotenv; load_dotenv()` before `get_client()` — CLI entry points load .env automatically but ad-hoc probes don't, so `get_client()` returns `None` silently and debugging misreads as "table empty."
- Supabase column drift check: `.select("*")` silently omits columns missing from the live DB, and `snap.get("col")` returns `None` — hiding schema/migration drift. To verify a column exists, `client.table(t).select("col_name").limit(1).execute()` — raises PostgREST 42703 when absent. Seen with `prediction_snapshots.primary_method` (defined in `migrations_backtest.sql` but not applied to prod), causing calibration to bucket every record as `sector='unknown'`. Column existence (no 42703) does not prove save writes it — the `save_*` row dict may omit the field, so the column stays at its DEFAULT. Verify by reading a freshly-written row and asserting the expected non-default value. Seen: `prediction_snapshots.market_signals_version` column added but `save_prediction_snapshot` row dict omits it → all snapshots stay at 0.
- `getattr(result, "x", 0) or 1` truthy-coalescing erases an explicit `0`. For version/state int fields where 0 is meaningful (e.g. `market_signals_version`), use `v = getattr(result, "x", None); v = 1 if v is None else v`. Seen in `save_prediction_snapshot` — coerced legitimate 0 into 1, silently relabeling pre-Phase-4 A/B test rows.
- `backtest_outcomes.analysis_date` and `prediction_snapshots.analysis_date` both carry the same date (outcomes copies at insert time). When `list_outcomes_needing_refresh` inner-joins snapshots, read from the joined path — the snapshot is authoritative; the outcomes copy can drift if anyone backfills or rewrites it. The join becomes inert if the parser reads the top-level outcomes column.
- `calibration.tuner._baseline_probs_from_records` must aggregate PER-RECORD role mass (sum probs within each role per record, then mean across records). Per-scenario averaging undercounts `base` when a profile has 4+ scenarios collapsing multiple entries into `base` — e.g. probs 10/20/30/40 become base=(20+30)/2=25, total 75 instead of 100, distorting baseline_mape, shift size, and the recommendation gate.
- `calibration.walk_forward.tune_walk_forward` aggregate — suppressed folds carry `test_mape=None` by contract; the mean must fall back to `baseline_test_mape` (docstring: "suppressed folds contribute baseline test MAPE only"). Dropping `None` silently biases `mean_test_mape` and `overfitting_gap` toward only the folds that emitted a recommendation.
- Weight/ratio `[0,1]` range checks must use `math.isfinite(w)` guard first. `w < 0 or w > 1` returns False for NaN/inf (all NaN comparisons are False), silently ingesting poisoned values into shrinkage/aggregation. Seen in `calibration/driver_shrinkage.py`.
- PostgREST paged fetches (`.range(offset, end)` loops) must emit a truncation warning when `max_rows` cap is hit without a short page. Python `while...else` detects this: the `else` branch runs only when the loop exited via condition, not `break`. Silent cap replacement is just a different silent-truncation bug. Seen in `db/backtest_repository.list_outcomes_needing_refresh`.
