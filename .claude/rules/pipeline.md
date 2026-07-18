---
paths: ["pipeline/**/*.py"]
---

# Pipeline (Data Collection) Gotchas

IO lives here (DART, SEC EDGAR, Yahoo Finance). `engine/` stays pure.

## Profile Generation

- `--auto` overwrites the entire profile YAML. Never use on hand-crafted test profiles (`_template`, `nav_test`, `multiples_test`, `kb_financial_rim`) or profiles with manual `valuation_method` override (e.g., `kb_financial` DDM).
- Silent zero defaults: `liabilities: 0` or `de_ratio: 0` in consolidated data is almost always a data ingestion error for operating companies — verify before running valuation.

## DART (KR)

- DART `parse_financial_statements()` includes `capex` key only when a matching PPE-acquisition account is found in CF items; if absent, key is not created and `profile_generator` falls back to `capex_to_da=1.10`. DART investing outflows are reported negative — stored via `abs()`.
- `estimate_borrowings()` is called inside `parse_financial_statements()` — `gross_borr`/`net_borr` are included in the DART result automatically. Calling it again externally on the same items double-counts debt.

## Yahoo Finance / yfinance

- `get_market_cap()` (`pipeline/yahoo_finance.py`) returns raw currency units (full KRW or USD, not millions). `scoring.py _fetch_market_cap_usd` divides raw KRW by `_KRW_TO_USD=1350` — do not pre-convert to millions before passing.
- `pipeline/yfinance_fetcher.py` calls `yf.Ticker().info` which may return price but omit `marketCap` for KR tickers. When `market_cap_raw == 0`, the KR path breaks out of the retry loop and falls back to `get_quote_summary()`. The `if market == "KR" and not market_cap_raw: break` guard enables this fallback — do not remove it.

## Caching & Data Sharing

- **Persistent ticker cache**: KR ticker → KOSPI/KOSDAQ resolution persists to `.cache/kr_tickers.json`. No TTL needed (exchange assignments are permanent).
- **Pipeline data sharing**: Scoring phase `market_cap_usd` flows into valuation via `scored_data` parameter in `auto_analyze()`.
