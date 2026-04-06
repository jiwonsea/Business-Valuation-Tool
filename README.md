# Business Valuation Tool

AI-powered corporate valuation platform supporting Korean (KOSPI/KOSDAQ) and US (NYSE/NASDAQ) markets. Combines quantitative financial modeling with LLM-driven scenario analysis to produce institutional-grade valuation reports.

**22,000+ lines of Python** | **365 tests** | **6 valuation methods** | **21 company profiles**

## Highlights

- **End-to-end automation**: Company name → data collection → AI analysis → probability-weighted valuation → Excel report
- **Dual-market data pipeline**: DART OpenAPI (Korea) + SEC EDGAR XBRL (US) + Yahoo Finance
- **Two-Pass scenario design**: Haiku classification → Sonnet refinement with multi-variable news drivers and correlation dampening
- **Market data calibration**: FRED macro signals, analyst consensus, FinBERT sentiment, and options IV injected into scenario prompts to anchor LLM outputs against observable data
- **Backtesting infrastructure**: Prediction snapshots at T0 → outcome tracking at T+3m/6m/12m → 6 calibration metrics with A/B comparison

## Valuation Methods

| Method | Use Case | Key Inputs |
|--------|----------|------------|
| **SOTP** (Sum-of-the-Parts) | Multi-segment conglomerates | Segment EBITDA × EV/EBITDA multiples, D&A allocation by asset weight |
| **DCF** (Discounted Cash Flow) | Single-segment operating companies | FCFF 5-year projection + Gordon Growth / Exit Multiple terminal value |
| **DDM** (Dividend Discount Model) | Banks, insurance, mature dividend payers | DPS + growth rate, Total Payout variant for US financials |
| **RIM** (Residual Income Model) | BV-based financial sector valuation | ROE forecasts, book value, cost of equity |
| **NAV** (Net Asset Value) | Holding companies, REITs, asset-heavy | Revaluation adjustments, holding company discount |
| **Multiples** (Relative Valuation) | Quick comparable analysis | EV/EBITDA, P/E, P/BV, EV/Revenue, P/S, P/FFO |

Auto-selection via `engine/method_selector.py`: multi-segment → SOTP, financials → DDM/RIM, single-segment → DCF.

## Architecture

```
cli.py                CLI entry point (5 modes: profile, company, discover, weekly, backtest)
app.py                Streamlit web UI (8 tabs)
orchestrator.py       Profile → valuation → Excel pipeline
valuation_runner.py   Method dispatch (SOTP/DCF/DDM/RIM/NAV/Multiples)

engine/          19 modules — pure calculation (no IO, no state)
├── wacc.py              CAPM with Hamada beta unlevering, size premium
├── sotp.py              D&A allocation + segment EV aggregation
├── dcf.py               FCFF projection + dual terminal value (Gordon + Exit Multiple)
├── scenario.py          Dynamic equity bridge + DLOM + probability weighting
├── drivers.py           Multi-variable news driver resolution (√N/N dampening)
├── sensitivity.py       3× two-way sensitivity tables
├── monte_carlo.py       Stochastic simulation (10K runs default)
├── gap_diagnostics.py   Reverse-DCF gap analysis (implied WACC/TGR/growth)
├── quality.py           0-100 quality score with grade (A-F)
├── ddm.py               Gordon Growth DDM + Total Payout variant
├── rim.py               Residual Income Model with terminal RI
├── nav.py               Net Asset Value with revaluation
├── growth.py            Revenue/EBITDA growth rate estimation
├── multiples.py         5-method cross-validation
├── peer_analysis.py     Per-segment peer statistics (median, IQR)
├── market_comparison.py Intrinsic vs market price gap (±50% warning)
├── method_selector.py   Auto-routing by company characteristics
├── units.py             Auto-detect display unit by revenue scale
└── __init__.py

schemas/         Pydantic v2 models (ValuationInput ↔ ValuationResult)
├── models.py            30+ models including MarketSignals, NewsDriver, ScenarioParams

pipeline/        15 modules — external data collection and processing
├── data_fetcher.py      Unified multi-market data adapter
├── dart_client.py       DART OpenAPI client (KR financials)
├── edgar_client.py      SEC EDGAR XBRL client (US financials)
├── yahoo_finance.py     Stock info, market cap, analyst data
├── yfinance_fetcher.py  3-year financials, KR ticker resolution
├── market_data.py       KRX market data + 38.co.kr OTC data
├── macro_data.py        FRED terminal growth, effective tax rate
├── market_signals.py    Phase 4: FRED/analyst/sentiment/IV aggregator
├── sentiment.py         FinBERT news sentiment (optional, lazy-loaded)
├── peer_fetcher.py      Yahoo Finance peer multiples
├── profile_generator.py Auto-fetch + AI-enriched YAML generation
├── api_guard.py         Rate limiting + circuit breaker + exp backoff
└── ...

ai/              5 modules — LLM orchestration
├── analyst.py           6-step AI analyst (identify → classify → peers → WACC → scenarios → note)
├── prompts.py           Structured prompts with market signals injection
├── validators.py        Deterministic post-LLM validation (ranges, consistency, signals cross-check)
├── llm_client.py        Anthropic/OpenRouter dual-model client with caching
└── __init__.py

backtest/        6 modules — calibration infrastructure
├── metrics.py           Forecast Error (MAPE), Gap Closure, Interval Score, Calibration Curve
├── price_tracker.py     Outcome price fetching at T+3m/6m/12m
├── dataset.py           Build BacktestRecord from Supabase snapshots
├── report.py            Console report + A/B comparison (signals v0 vs v1)
├── models.py            BacktestRecord, ScenarioSnapshot
└── __init__.py

discovery/       News-driven company recommendation pipeline
scheduler/       Weekly automation (news → scoring → valuation → delivery)
output/          Excel builder (7-sheet workbook with charts)
db/              Supabase persistence (valuations, snapshots, outcomes)
```

## Key Design Decisions

**Multi-variable news drivers with correlation dampening**
Instead of asking the LLM to produce final scenario numbers directly, drivers are extracted as independent variables with partial effects. When multiple drivers affect the same field, a √N/N dampening factor prevents overestimation from correlated inputs.

**Two-Pass scenario design**
Pass 1 (Haiku, cheap): classify scenario codes, probability ranges, driver directions.
Pass 2 (Sonnet, precise): refine exact numeric values, probability rationale with conditional decomposition (P(macro) × P(industry|macro) × P(company|industry)).

**Market signals as LLM context, not post-processing**
FRED macro data, analyst consensus, FinBERT sentiment, and options IV are rendered into `<market_signals>` XML blocks and injected into the LLM prompt. This lets the model reason about observable data rather than hallucinating base rates, while deterministic validators cross-check outputs afterward.

**Graceful degradation everywhere**
Every external data source is wrapped with `api_guard` (rate limiting + circuit breaker). Every signal in `MarketSignals` is Optional. FinBERT requires `transformers[torch]` but the tool works without it. The system never blocks on a single API failure.

## Quick Start

```bash
# Install
pip install -e ".[dev,pipeline,ai]"

# Profile-based valuation
python cli.py --profile profiles/sk_ecoplant.yaml --excel

# Auto-fetch (company name or ticker)
python cli.py --company "AAPL"
python cli.py --company "삼성전자"

# AI end-to-end analysis
python cli.py --company "MSFT" --auto

# News-based discovery
python cli.py --discover --market KR

# Weekly automation
python cli.py --weekly --markets KR,US --max-per-market 5

# Backtesting calibration report
python cli.py --backtest --backtest-min-age 90

# Web UI
streamlit run app.py

# Tests
pytest tests/  # 365 tests
```

## Environment Variables

| Variable | Required For | Purpose |
|----------|-------------|---------|
| `DART_API_KEY` | KR companies | DART OpenAPI financial data |
| `ANTHROPIC_API_KEY` or `OPENROUTER_API_KEY` | `--auto` mode | LLM analysis (Claude Sonnet/Haiku) |
| `NAVER_CLIENT_ID` + `NAVER_CLIENT_SECRET` | `--discover --market KR` | Naver News API |
| `SUPABASE_URL` + `SUPABASE_KEY` | `--backtest`, DB persistence | Supabase PostgREST |

## Company Profiles

21 pre-built profiles spanning Korean and US markets:

**Korea**: SK Ecoplant, Samsung Electronics (005930), Hyundai Motor (005380), SK Hynix (000660), Naver (035420), LG Energy Solution (051910), Curocell (346010), KB Financial

**US**: Apple, Amazon, Microsoft, Nvidia, Tesla, Google, Johnson & Johnson, Chevron, Pfizer

## Tech Stack

Python 3.11+ | Pydantic v2 | httpx | NumPy | Pandas | openpyxl | PyYAML | Anthropic SDK | yfinance | Streamlit | Plotly | Supabase | defusedxml | transformers (optional)

## Testing

365 tests covering engine calculations, pipeline data fetching, AI prompt/validator logic, backtest metrics, market signals integration, and scheduler workflows. All external API calls are mocked in tests.

```
tests/test_engine.py            88 tests  — pure calculation correctness
tests/test_validators.py        38 tests  — AI output validation rules
tests/test_backtest.py          28 tests  — calibration metrics
tests/test_market_signals.py    25 tests  — Phase 4 market data integration
tests/test_pipeline.py          24 tests  — data fetching logic
tests/test_api_guard.py         24 tests  — rate limiting / circuit breaker
tests/test_scheduler.py         24 tests  — weekly automation
tests/test_quality.py           31 tests  — quality scoring
tests/test_ai.py                15 tests  — prompt generation / LLM client
tests/test_pipeline_integration.py  15 tests  — end-to-end pipeline
```
