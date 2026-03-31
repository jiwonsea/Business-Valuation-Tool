# Korean Valuation Tool

AI-assisted corporate valuation platform for Korean and US companies.

Automatic method selection (SOTP / DCF / DDM) based on company characteristics, with probability-weighted scenario analysis, cross-validation, and market price gap detection.

## Features

- **Dual-market support**: Korea (DART OpenAPI) and US (SEC EDGAR XBRL)
- **Auto-detection**: Company name or ticker → automatic market routing + listed/unlisted classification
- **Method routing**: Multi-segment → SOTP, single-segment → DCF, financials → DDM (auto or manual override)
- **SOTP valuation**: Segment-level EBITDA × EV/EBITDA multiples with D&A allocation by asset weight
- **DCF valuation**: FCFF-based 5-year projection + Gordon Growth terminal value
- **Scenario analysis**: Probability-weighted per-share value across multiple scenarios (IPO, FI, Bear/Bull)
- **Market price gap**: Automatic comparison with listed stock price, ±50% deviation warning
- **Sensitivity analysis**: 3 two-way tables (multiples, IRR/DLOM, WACC/terminal growth)
- **Cross-validation**: 5 methods (SOTP, DCF, EV/Revenue, P/E, P/BV) football field comparison
- **Peer analysis**: Per-segment peer multiple statistics (median, Q1/Q3) with Yahoo Finance auto-fetch
- **Monte Carlo**: Stochastic simulation with configurable parameters
- **Excel export**: 7-sheet workbook with charts, heatmaps, and conditional formatting
- **AI analyst**: Claude API integration for segment classification, peer recommendation, scenario design
- **Streamlit UI**: Interactive web dashboard with Plotly charts (8 tabs)
- **News discovery**: AI-powered market news analysis → company recommendation → YAML generation

## Quick Start

```bash
pip install -e ".[dev,pipeline,ai,ui]"

# Profile-based valuation
python cli.py --profile profiles/sk_ecoplant.yaml --excel

# Auto-fetch (US)
python cli.py --company "AAPL"

# Auto-fetch (Korean, requires DART_API_KEY)
python cli.py --company "삼성E&A"

# AI-powered end-to-end analysis
python cli.py --company "MSFT" --auto

# News-based discovery
python cli.py --discover --market KR

# Web UI
streamlit run app.py

# Tests
pytest tests/
```

## Architecture

```
cli.py            CLI entry point + run_valuation() with SOTP/DCF routing
app.py            Streamlit web UI (8 tabs: scenarios, SOTP, DCF, sensitivity,
                  cross-validation, peers, Monte Carlo, summary)
orchestrator.py   Profile → valuation → Excel pipeline wrapper

engine/           Pure calculation functions (no IO, no state)
├── method_selector.py   Auto-select SOTP/DCF/DDM by company type
├── wacc.py              CAPM-based WACC
├── sotp.py              D&A allocation + segment EV
├── dcf.py               FCFF 5-year projection + Gordon Growth
├── scenario.py          Equity bridge + DLOM + probability weighting
├── sensitivity.py       3× two-way sensitivity tables
├── multiples.py         EV/Revenue, P/E, P/BV cross-validation
├── peer_analysis.py     Per-segment peer statistics
├── monte_carlo.py       Stochastic simulation
├── market_comparison.py Intrinsic vs market price gap analysis
├── ddm.py               Gordon Growth DDM (financials)
└── units.py             Auto-detect display unit by revenue scale

schemas/          Pydantic v2 models (ValuationInput → ValuationResult)
pipeline/         Data collection (DART, SEC EDGAR, Yahoo Finance, 38.co.kr)
ai/               Claude API integration (6-step analyst)
output/           Excel builder (7-sheet workbook)
profiles/         YAML company profiles
tests/            Unit + integration tests
```

## Method Selection

| Company Type | Primary | Cross-Validation |
|-------------|---------|-----------------|
| Multi-segment | SOTP (EV/EBITDA) | DCF, EV/Revenue |
| Single-segment | DCF (FCFF) | EV/Revenue, P/E, P/BV |
| Financial | DDM or P/BV | P/E |
| Manual override | `valuation_method` in YAML | All applicable |

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `DART_API_KEY` | KR companies | DART OpenAPI access |
| `ANTHROPIC_API_KEY` | `--auto` mode | Claude AI analyst |
| `NAVER_CLIENT_ID` | `--discover --market KR` | Naver News API |
| `NAVER_CLIENT_SECRET` | `--discover --market KR` | Naver News API |

## Tech Stack

Python 3.11+, Pydantic v2, openpyxl, httpx, NumPy, Pandas, PyYAML, Anthropic SDK, Streamlit, Plotly
