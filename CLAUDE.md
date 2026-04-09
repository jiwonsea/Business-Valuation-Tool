# CLAUDE.md

@~/.claude/CLAUDE.md

## Project

KR/US company valuation platform. Pure-function engine + Pydantic schemas + YAML profiles + AI-assisted analysis. Python 3.11+.

## Architecture

```
ValuationInput (YAML) → run_valuation() → ValuationResult → print_report() / Excel
```

- `engine/` — Pure functions (no IO). `method_selector.py` auto-selects methodology by company type.
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

- **Auto method selection**: `engine/method_selector.py` branches to SOTP/DCF/DDM/RIM/NAV based on segment count, industry, ROE/Ke. Financials use ROE-Ke spread for DDM/RIM auto-selection. Manual override (`valuation_method`) takes priority.
- **Reverse DCF / Narrative→Numbers (Damodaran)**: When |market - intrinsic gap| ≥ 20%, `gap_diagnostics.py` auto-extracts implied WACC, TGR, or growth multiplier the market is pricing in. Primary DCF use case for optionality-heavy stocks — decoding market assumptions, not finding a 'correct' price target. If gap ≥ 50%, also re-verify raw data and assumptions.
- **Scenarios/probabilities**: AI proposes, but user makes final decisions.
- **Scenario probability grounding**: LLM-generated probabilities must be anchored to historical base rates and driver reference ranges. Pure LLM hallucination without empirical grounding produces identical distributions across companies. See `memory/reference_valuation_scenario_research.md` for Damodaran/McKinsey/Morgan Stanley frameworks.
- **Scenario SOTP**: Bull/Bear scenarios must assign different EV/EBITDA multiples per segment — not only `growth_adj_pct`. Identical multiples across scenarios produce identical outputs (design omission, not a code bug). Software/platform segments use higher multiples in Bull, lower in Bear. Per-scenario WACC differentiation is approximated via multiple differences (higher multiple ≈ lower implied discount rate) — explicit per-scenario WACC not implemented.
- **Scenario driver 3-layer contract**: AI prompt (`_METHOD_DRIVERS` in `ai/prompts.py`), YAML persistence (`profile_generator.py`), and runtime (`valuation_runner.py`) must agree on which drivers each method supports. SOTP uses `segment_multiples`/`segment_ebitda`/`segment_revenue`/`growth_adj_pct`; DCF uses `growth_adj_pct`/`wacc_adj`/`terminal_growth_adj`; each method has its own set. Adding a new driver requires updating all three layers.
- **Optionality stock DCF**: DCF assumes predictable cash flow path — unsuitable as sole method for binary-outcome segments (FSD, Robotics, autonomous fleet) where payoff is explosive-or-0. Terminal value typically exceeds 60% of total EV, causing extreme WACC/g sensitivity. Use DCF only as reverse engineering tool to decode market assumptions.
- **SOTP optionality segments**: Pre-profit segments use `method: ev_revenue` (EV = Revenue × EV/Revenue multiple). Distress discount is excluded for ev_revenue segments — comp multiples already embed balance sheet risk. EV/Revenue multiple ranges: Emerging tech 5-10x, Platform/SaaS 12-20x, Hyper-growth leader 25x+. `segment_revenue` provides per-scenario revenue overrides.
- **Real Options (B-S) → REJECTED** for individual segment valuation: stock IV already embeds the optionality being valued (circular), total stock IV cannot be disaggregated per segment (FSD vs. Robotaxi), and GBM assumption is violated by discrete binary outcomes. Exception (sanity check only): IV premium over sector average ≈ aggregate optionality premium the market prices in — compare directionally against reverse DCF implied growth multiplier.
- **Currency units**: Auto-determined from financial statement scale (`engine/units.py`). No hardcoding.

## Conventions

- English code/comments; Korean user-facing output.
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

## Efficiency

- **Batch LLM calls**: Use `recommend_peers_batch()` for multi-segment companies (1 call vs N segments).
- **System prompt caching**: Static reference content (driver definitions, format specs) belongs in system prompts. Anthropic ephemeral cache gives 90% input cost reduction; OpenRouter gets no cache benefit but shorter user prompts reduce retry cost.
- **Persistent ticker cache**: KR ticker → KOSPI/KOSDAQ resolution persists to `.cache/kr_tickers.json`. No TTL needed (exchange assignments are permanent).
- **Pipeline data sharing**: Scoring phase `market_cap_usd` flows into valuation via `scored_data` parameter in `auto_analyze()`.
- **News summary caching**: `summarize_key_issues()` results are disk-cached (7-day TTL) via `ai/analyst.py` cache infrastructure.
- **Target: ≤4 LLM calls/company** (classify + peers_batch + wacc + scenarios). Optionality segment detection is merged into the scenarios call — no extra quota. Daily LLM quota: 50 calls.
- **Quota safety net**: `weekly_run.py` auto-trims targets if `len(targets) * 4 > remaining_llm_quota`.

## Gotchas

- `per_share()` propagates negative equity (no zero-clamping). Distress scenarios yield negative per-share values. DLOM is not applied to negative equity.
- No hardcoding `* 1_000_000` → use `engine.units.per_share()`.
- No hardcoding segment codes ("HI", "ALC", etc.) in sensitivity analysis.
- New YAML profile fields must always be Optional with defaults (backward compatibility).
- NAV/Multiples: `market_sentiment_pct` is `elif` (mutually exclusive) with `nav_discount`/`ev_multiple` to prevent double-counting. RIM/DCF/DDM/SOTP apply it cumulatively (`if`). Do not unify — the asymmetry is intentional.
- `NewsDriver.effects` is `dict[str, float]` (scalar-only). Structured per-segment overrides (`segment_multiples`, `segment_ebitda`) go directly on `ScenarioParams`, not through the news_drivers→resolve_drivers path.
- `--auto` overwrites the entire profile YAML. Never use on hand-crafted test profiles (`_template`, `nav_test`, `multiples_test`, `kb_financial_rim`) or profiles with manual `valuation_method` override (e.g., `kb_financial` DDM).
- After changing AI prompts in `ai/prompts.py`, clear `.cache/llm/*_scenarios_*.json` before re-testing — cached responses won't reflect prompt changes.
- Silent zero defaults: `liabilities: 0` or `de_ratio: 0` in consolidated data is almost always a data ingestion error for operating companies — verify before running valuation.
- SOTP path uses `effective_multiples` (distress-adjusted), not `vi.multiples`. New code touching SOTP calculation (scenarios, sensitivity, Monte Carlo) must use `effective_multiples` — using raw `vi.multiples` bypasses distress discount silently.
- `consolidated` dict does NOT contain WACC params (`kd_pre`, `rf`, `erp`). Those live on `vi.wacc_params`. Reading `consolidated.get("kd_pre", fallback)` silently returns fallback — pass WACC params explicitly.
- Monte Carlo DCF TV variation (`ev *= dcf_ev_sample/dcf_ev_base`) applies only to `ev_ebitda_part`. `ev_revenue_part` is added after TV adjustment — revenue-based optionality is independent of DCF terminal value assumptions.
- `segment_method_override` (ev_revenue→ev_ebitda transition) requires `segment_ebitda` for the transitioned segment in the same scenario — D&A re-allocation alone yields near-zero EBITDA for formerly-excluded segments.
- `console_report.py` `is_mixed` must stay in sync with `_needs_method_dispatch()` in valuation_runner — both should trigger on any non-default method (ev_revenue, pbv, pe). Equity Bridge display is conditional on pbv/pe only.
- `get_client()` returns `None` silently when `SUPABASE_URL`/`SUPABASE_KEY` are missing. DB-dependent features (backtest, save_valuation) degrade silently — check `.env` exists before debugging "empty results."
- Cross-validation DCF calls in non-DCF methods (Multiples/NAV) are now guarded with try/except. When adding new cross-validation paths, follow the same pattern — `calc_dcf()` raises `ValueError` on `ebitda<=0` or `WACC<=TG`.
- `rcps_repay` is `Optional[int] = None` (like `cps_repay`). Use `_derive_rcps_repay(ref_sc, vi)` for all RCPS repay calculations — it handles IRR-based compounding when explicit repay is absent. Raw `sc.rcps_repay or 0` drops compounding. The `is not None` vs `> 0` distinction is load-bearing for explicit-zero overrides.
- Mixed-method SOTP Monte Carlo must use `effective_net_debt` (via `net_debt_override`), not `vi.net_debt`. PBV/PE segment equity values already embed net_debt — using full net_debt double-deducts.
- PBV/PE segments are cross-cutting: changes touch SOTP (`sotp.py`), MC (`monte_carlo.py` skip logic), sensitivity (`sensitivity.py` fixed_ev + same_seg guard), and scenario equity bridge (`valuation_runner.py` net_debt add-back). Test all four when modifying PBV/PE behavior.
- DCF terminal value uses normalized FCFF (NOPAT − ΔNWC, excluding capex-fade artifact from projection years). Raw last-year FCFF overstates TV when capex_fade < 1.0.
- **Equity-direct methods (DDM, RIM, P/E, P/BV) output equity, not EV.** calc_scenario currently assumes EV input and subtracts net_debt → double-deduction. F-P1-1~3 pending: `is_equity_direct` flag needed in calc_scenario to skip net_debt bridge for these methods.
- Sensitivity multiples grid: when row_seg == col_seg, col_ev must be 0 to prevent double-counting the same segment's EV contribution.
- `segment_multiples`/`segment_ebitda`/`segment_revenue` keys in scenario YAML must be segment codes (`SEG1`, `AUTONOMOUS_DRIVING`), not human-readable names. LLM frequently generates Korean labels or ticker names instead. `load_profile()` warns on mismatch but doesn't auto-fix — verify keys after `--auto` generation.
