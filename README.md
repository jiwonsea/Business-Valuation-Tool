# Korean Valuation Tool

AI-assisted corporate valuation platform for Korean and US companies.

SOTP (Sum-of-the-Parts) + DCF (Discounted Cash Flow) cross-validation with probability-weighted scenario analysis.

## Features

- **Dual-market support**: Korea (DART OpenAPI) and US (SEC EDGAR XBRL)
- **Auto-detection**: Company name or ticker input automatically routes to the correct data source
- **SOTP valuation**: Segment-level EBITDA x EV/EBITDA multiples with D&A allocation by asset weight
- **DCF cross-validation**: FCFF-based 5-year projection + Gordon Growth terminal value
- **Scenario analysis**: Probability-weighted per-share value across multiple scenarios
- **Sensitivity analysis**: 3 two-way tables (multiples, IRR/DLOM, WACC/terminal growth)
- **Excel export**: 7-sheet workbook with charts, heatmaps, and conditional formatting
- **AI analyst**: Claude API integration for peer recommendation, WACC estimation, scenario design
- **Streamlit UI**: Interactive web dashboard with Plotly charts

## Quick Start

```bash
pip install pydantic pyyaml openpyxl httpx

# Profile-based valuation
python cli.py --profile profiles/sk_ecoplant.yaml --excel

# Auto-fetch mode (US company)
python cli.py --company "AAPL"

# Auto-fetch mode (Korean company, requires DART_API_KEY)
python cli.py --company "삼성E&A"

# Web UI
pip install streamlit plotly
streamlit run app.py
```

## Architecture

```
engine/       Pure calculation functions (no IO, currency-agnostic)
pipeline/     Data collection (DART for KR, SEC EDGAR for US, Yahoo Finance)
schemas/      Pydantic models for type-safe data contracts
ai/           Claude API integration for AI-assisted analysis
output/       Excel builder (7-sheet workbook)
profiles/     YAML company profiles
```

The engine is completely decoupled from data sources — the same WACC, SOTP, DCF, and scenario calculations work for any company regardless of market or currency.

## Origin

This project was generalized from the [SK에코플랜트 기업가치평가](../SK에코플랜트%20기업가치평가/) prototype — a 1,500-line monolithic valuation model for a single Korean company. The methodology, calculation logic, and Excel output structure were extracted and parameterized into a reusable platform.

## Validation

The SK Ecoplant profile (`profiles/sk_ecoplant.yaml`) serves as a regression test. All hardcoded data was migrated from the original model, and the output must match exactly:

```
Probability-weighted per-share value: 39,892 KRW
```

## Tech Stack

Python 3.11+, Pydantic v2, openpyxl, httpx, PyYAML, Anthropic SDK, Streamlit, Plotly
