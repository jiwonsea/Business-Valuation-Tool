# CLAUDE.md

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
python -m scheduler.weekly_run                            # direct module execution

streamlit run app.py                                      # web UI
pytest tests/                                             # tests
pip install -e ".[dev,pipeline,ai,ui,db]"                  # install dependencies
```

## Workflow Rules

1. **Think before execute**: For non-trivial tasks, propose structure/approach first, then execute after confirmation.
2. **Auto method selection**: `engine/method_selector.py` branches to SOTP/DCF/DDM/RIM/NAV based on segment count, industry, ROE/Ke. Financials use ROE-Ke spread for DDM/RIM auto-selection. Manual override (`valuation_method`) takes priority.
3. **Gap check**: After valuing listed companies, compare to market price. If deviation exceeds +/-50%, re-verify data/assumptions.
4. **Scenarios/probabilities**: AI proposes, but user makes final decisions.
5. **Currency units**: Auto-determined from financial statement scale (`engine/units.py`). No hardcoding.

## Conventions

- **English-first**: All code, comments, docstrings, log messages, plan files, and SKILL.md files must be in English for token efficiency. User-facing output (print messages to end users, CLI prompts) stays in Korean.
- `.env` must never be committed to git (blocked by PreCommit hook).
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

## Gotchas

- No hardcoding `* 1_000_000` → use `engine.units.per_share()`.
- No hardcoding segment codes ("HI", "ALC", etc.) in sensitivity analysis.
- New YAML profile fields must always be Optional with defaults (backward compatibility).
