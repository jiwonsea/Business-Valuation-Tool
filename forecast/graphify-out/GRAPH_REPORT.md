# Graph Report - F:\dev\Portfolio\earnings-forecast-engine  (2026-06-04)

## Corpus Check
- 51 files · ~35,901 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 374 nodes · 984 edges · 26 communities detected
- Extraction: 46% EXTRACTED · 54% INFERRED · 0% AMBIGUOUS · INFERRED: 535 edges (avg confidence: 0.61)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]

## God Nodes (most connected - your core abstractions)
1. `MarginBaseline` - 39 edges
2. `SegmentForecast` - 34 edges
3. `QuarterlyForecast` - 34 edges
4. `QuarterlyActual` - 32 edges
5. `BacktestResult` - 32 edges
6. `main()` - 31 edges
7. `SegmentAssumptions` - 29 edges
8. `DisclosureDocument` - 28 edges
9. `ScenarioTree` - 27 edges
10. `MarginAssumptions` - 23 edges

## Surprising Connections (you probably didn't know these)
- `DisclosureDocument` --uses--> `Signal backtest — CAR event study.  Includes a non-circularity guard (passes now`  [INFERRED]
  F:\dev\Portfolio\earnings-forecast-engine\schemas\models.py → F:\dev\Portfolio\earnings-forecast-engine\tests\test_signal_backtest.py
- `main()` --calls--> `load_profile()`  [INFERRED]
  F:\dev\Portfolio\earnings-forecast-engine\cli.py → F:\dev\Portfolio\earnings-forecast-engine\pipeline\ir_loader.py
- `main()` --calls--> `extract_quarterly_actual()`  [INFERRED]
  F:\dev\Portfolio\earnings-forecast-engine\cli.py → F:\dev\Portfolio\earnings-forecast-engine\pipeline\dart_fetcher.py
- `main()` --calls--> `fetch_quarterly_actuals_series()`  [INFERRED]
  F:\dev\Portfolio\earnings-forecast-engine\cli.py → F:\dev\Portfolio\earnings-forecast-engine\pipeline\dart_fetcher.py
- `main()` --calls--> `MarginBaseline`  [INFERRED]
  F:\dev\Portfolio\earnings-forecast-engine\cli.py → F:\dev\Portfolio\earnings-forecast-engine\schemas\models.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (48): Primary HTML report — Jinja2 template + inline Plotly figures.  Self-contained s, Render the full HTML report to out_path.      Args:         out_path: Target fil, render_html_report(), Markdown summary report — GitHub README embed + cover letter quotation source., Render the MD summary.      Args:         out_path: Target file path (.md)., Render the MD summary.      Args:         out_path: Target file path (.md)., render_md_report(), AnnualForecast (+40 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (46): extract_quarterly_actual(), fetch_quarterly_actuals_series(), fetch_quarterly_financials(), DART OpenAPI client — quarterly / semi-annual / annual financial statements.  En, Map a DART report response to a QuarterlyActual dict., Fetch a single fnlttSinglAcntAll.json response.      Args:         corp_code: 8-, Fetch a single fnlttSinglAcntAll.json response., Fetch annual/interim reports and return standalone quarterly actuals.      DART (+38 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (32): count_kr_chars(), _extract_tree_value(), fetch_dart_mdna(), _find_mdna_params(), _get_with_retry(), _html_to_text(), load_ir_decks(), Disclosure / IR text loader.  Phase B uses two sources:   - local IR deck PDFs, (+24 more)

### Community 3 - "Community 3"
Cohesion: 0.15
Nodes (27): Retrospective backtest of the forecast methodology.  For each historical quarter, Run retrospective backtest over the most recent N quarters.      Args:         h, Return one-quarter assumptions with realized ASP and HBM share.      Args:, Run retrospective backtest over the most recent N quarters.      Args:         h, Run retrospective backtest over the most recent N quarters.      Args:         h, BaseModel, Pydantic v2 data models for earnings-forecast-engine., load_profile() (+19 more)

### Community 4 - "Community 4"
Cohesion: 0.1
Nodes (28): compute_consensus_gap(), Model (base case) vs Yahoo consensus gap calculation.  Per-period: model_value,, Compare base-case model output to consensus per quarter and per fiscal year., _clean(), _forward_quarters_from_as_of(), Normalize raw Yahoo response into ConsensusRecord.  Maps yfinance field names to, Convert a yfinance response dict to a typed ConsensusRecord.      Args:, Convert a yfinance response dict to a typed ConsensusRecord.      Args: (+20 more)

### Community 5 - "Community 5"
Cohesion: 0.12
Nodes (28): ExtractedSignal, One topic the disclosure text emphasizes, with salience and polarity., Deterministic, validated structured signal from one DisclosureDocument.      Pro, One backtest event: text signal at T0 vs realized market-adjusted CAR., SignalEventResult, TopicEmphasis, _car(), Signal event-study backtest (pure).  Tests whether the text signal at each earni (+20 more)

### Community 6 - "Community 6"
Cohesion: 0.12
Nodes (29): _actual_for_quarter(), _actuals_through_quarter(), _event_dates_from_yahoo(), _load_call_brief_fixtures(), _load_daily_closes(), _load_signal_backtest_fixtures(), main(), parse_args() (+21 more)

### Community 7 - "Community 7"
Cohesion: 0.23
Nodes (22): _avg(), _realized_price_assumptions(), run_backtest(), project_eps(), Net profit → EPS bridge.  EPS_basic = NI / weighted_avg_basic_shares EPS_diluted, Populate eps_basic / eps_diluted on each forecast quarter.      Args:         fo, apply_taxes_and_finance(), Tax + non-operating finance line projection.  NI = OP × (1 - effective_tax_rate) (+14 more)

### Community 8 - "Community 8"
Cohesion: 0.27
Nodes (16): _cost_per_bit_margin(), project_margins(), GP / OP margin projection using an ASP-cycle function.  GP margin = baseline + c, Populate GP / OP / NP margins on each forecast quarter.      Args:         reven, AnchorMargins, MarginBaseline, Prior 4Q averages used as baseline for cyclical margin function., Scenario-independent historical margin anchor for the cost-per-bit chain. (+8 more)

### Community 9 - "Community 9"
Cohesion: 0.26
Nodes (16): _ensure_parent(), _number(), _pct(), Call-brief and signal-backtest renderers., Render the call brief as Markdown., Render the signal backtest as a Markdown table., Render the signal backtest as a self-contained HTML table., Render the call brief to a self-contained HTML file. (+8 more)

### Community 10 - "Community 10"
Cohesion: 0.22
Nodes (7): Shared pytest fixtures., Real DART fnlttSinglAcntAll response — SK Hynix 2024 annual (reprt_code 11011, C, Real DART fnlttSinglAcntAll response — SK Hynix 2024 Q3 (reprt_code 11014, CFS)., Real yfinance consensus snapshot for 000660.KS (captured 2026-05-30).      Conse, sk_hynix_dart_q3_raw(), sk_hynix_dart_raw(), sk_hynix_yahoo_raw()

### Community 11 - "Community 11"
Cohesion: 0.4
Nodes (5): find_chrome(), html_to_pdf(), Chrome headless wrapper — HTML report -> PDF.  Reuses the career/_build_pdf.py p, Locate chrome.exe on Windows. Returns None if not installed., Convert an HTML report to PDF via Chrome headless.      Args:         html_path:

### Community 12 - "Community 12"
Cohesion: 0.5
Nodes (3): ensure_ssl_env(), TLS CA bundle setup for libraries that fail on non-ASCII home paths., Set CA bundle environment variables before http/yfinance imports.

### Community 13 - "Community 13"
Cohesion: 1.0
Nodes (0): 

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (1): Fetch analyst consensus snapshot for a ticker.      Pulls from yfinance Ticker(t

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (1): Fetch quarterly price history for context (forecast chart overlay).      Args:

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (1): Prior 4Q averages used as baseline for cyclical margin function.

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (1): Prior 4Q averages used as baseline for cyclical margin function.

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (1): Historical quarterly result from DART. Used for backtest and baseline.

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (1): Forward projection. Same shape as QuarterlyActual but with scenario tag.

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (1): Snapshot of analyst consensus from yfinance.

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): Model (base case) vs consensus, per period.

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): Historical quarterly result from DART. Used for backtest and baseline.

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Forward projection. Same shape as QuarterlyActual but with scenario tag.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Snapshot of analyst consensus from yfinance.

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Model (base case) vs consensus, per period.

## Knowledge Gaps
- **50 isolated node(s):** `CLI entry point.  Usage:     python cli.py --company sk_hynix     python cli.py`, `Extraction prompts for the consensus signal layer.  Claude owns the prompt conte`, `Assemble the user-turn message wrapping the (untrusted) document text.      Args`, `Tax + non-operating finance line projection.  NI = OP × (1 - effective_tax_rate)`, `Chrome headless wrapper — HTML report -> PDF.  Reuses the career/_build_pdf.py p` (+45 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 13`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 14`** (1 nodes): `Fetch analyst consensus snapshot for a ticker.      Pulls from yfinance Ticker(t`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (1 nodes): `Fetch quarterly price history for context (forecast chart overlay).      Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (1 nodes): `Prior 4Q averages used as baseline for cyclical margin function.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (1 nodes): `Prior 4Q averages used as baseline for cyclical margin function.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (1 nodes): `Historical quarterly result from DART. Used for backtest and baseline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `Forward projection. Same shape as QuarterlyActual but with scenario tag.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `Snapshot of analyst consensus from yfinance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `Model (base case) vs consensus, per period.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `Historical quarterly result from DART. Used for backtest and baseline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `Forward projection. Same shape as QuarterlyActual but with scenario tag.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `Snapshot of analyst consensus from yfinance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `Model (base case) vs consensus, per period.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `main()` connect `Community 6` to `Community 0`, `Community 1`, `Community 3`, `Community 4`, `Community 7`, `Community 8`, `Community 11`?**
  _High betweenness centrality (0.217) - this node is a cross-community bridge._
- **Why does `DisclosureDocument` connect `Community 2` to `Community 3`, `Community 4`, `Community 5`, `Community 6`?**
  _High betweenness centrality (0.127) - this node is a cross-community bridge._
- **Why does `run_signal_backtest_mode()` connect `Community 6` to `Community 9`, `Community 2`, `Community 3`, `Community 5`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Are the 36 inferred relationships involving `MarginBaseline` (e.g. with `Map a fetch_price_history payload to {date: close} for CAR computation.` and `Map fetch_earnings_dates payload to {event_label: announcement date}.      event`) actually correct?**
  _`MarginBaseline` has 36 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `SegmentForecast` (e.g. with `Scenario tree construction and probability weighting.  Bear / Base / Bull cases` and `Group quarterly forecasts into fiscal-year buckets and sum P&L lines.      Args:`) actually correct?**
  _`SegmentForecast` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `QuarterlyForecast` (e.g. with `Net profit → EPS bridge.  EPS_basic = NI / weighted_avg_basic_shares EPS_diluted` and `Populate eps_basic / eps_diluted on each forecast quarter.      Args:         fo`) actually correct?**
  _`QuarterlyForecast` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `QuarterlyActual` (e.g. with `Map a fetch_price_history payload to {date: close} for CAR computation.` and `Map fetch_earnings_dates payload to {event_label: announcement date}.      event`) actually correct?**
  _`QuarterlyActual` has 29 INFERRED edges - model-reasoned connections that need verification._