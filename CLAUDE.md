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
- **Optionality stock DCF**: DCF assumes predictable cash flow path — unsuitable as sole method for binary-outcome segments (FSD, Robotics, autonomous fleet) where payoff is explosive-or-0. Terminal value typically exceeds 60% of total EV, causing extreme WACC/g sensitivity. Use DCF only as reverse engineering tool to decode market assumptions.
- **SOTP optionality segments**: Software/platform/SaaS segments (FSD, Robotics) warrant higher EV/EBITDA or P/S multiples than manufacturing. Assign separate segment codes with elevated multiples to capture monetization optionality not reflected in current EBITDA.
- **Real Options (B-S) → REJECTED** for individual segment valuation: stock IV already embeds the optionality being valued (circular), total stock IV cannot be disaggregated per segment (FSD vs. Robotaxi), and GBM assumption is violated by discrete binary outcomes. Exception (sanity check only): IV premium over sector average ≈ aggregate optionality premium the market prices in — compare directionally against reverse DCF implied growth multiplier.
- **Currency units**: Auto-determined from financial statement scale (`engine/units.py`). No hardcoding.

## Conventions

- English code/comments; Korean user-facing output.
- Env vars: `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `DART_API_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `SUPABASE_URL`, `SUPABASE_KEY`
- `engine/` functions must be pure (no IO, no state). `import httpx`, `requests` etc. forbidden.
- IO contract: `ValuationInput` → `ValuationResult` (`schemas/models.py`).
- New YAML profile fields must be Optional with defaults (backward compatibility).

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
