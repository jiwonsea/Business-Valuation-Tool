# HANDOFF → Codex — Japan financials via EDINET (third BVT source)

> **From**: Claude (Opus 4.8), 2026-07-08
> **To**: Codex (networked machine)
> **Goal**: give Japanese large caps a BVT valuation band by adding EDINET (Japan's
> FSA XBRL disclosure) as a third financials source alongside SEC EDGAR (US) and
> DART (KR). This is what unblocks direct JP holdings; JP tax is already in the
> orchestrator ledger (`ledger/tax.py`, this session — 22% Korean overseas CGT +
> 15% Korea-Japan treaty dividend, no Japan-side CGT on non-resident listed gains).
> **Read first**: `pipeline/edgar_client.py`, `pipeline/dart_client.py`,
> `pipeline/data_fetcher.py`, `engine/method_selector.py`,
> `../investment-orchestrator/studies/market_data_coverage.md`.

## Context / scope
- Coverage reality (see the coverage study): JP prices exist (yfinance `.T`) but
  fundamentals need a regulator feed and consensus is large-cap-only. So JP is
  **large-cap only**, and forward-EPS will often abstain — **BVT carries JP, like KR**.
- v1 target: 2–3 liquid names (e.g. Toyota 7203, Sony 6758) end-to-end, not full
  market coverage.

## Task A — `pipeline/edinet_client.py`
Mirror `edgar_client.py`:
- Use the **EDINET API v2** (FSA): document list endpoint → find the latest
  有価証券報告書 (annual securities report) / 四半期報告書 (quarterly) for a filer;
  download the XBRL ZIP.
- **Code mapping**: securities code (4-digit, e.g. 7203) → EDINET code / filer.
  EDINET publishes a code list (EdinetcodeDlInfo); cache it.
- Parse the XBRL for the fields BVT profiles need: revenue, operating income,
  EBITDA inputs (D&A), net income, EPS, book value, shares outstanding, segment
  data if available. Use the standard EDINET/IFRS or Japanese-GAAP taxonomy tags.
- **Units & FX**: Japanese statements are typically in 百万円 (millions of JPY) and
  many issuers have a **March fiscal-year end** — normalize units and set the
  analysis/fiscal dates correctly (this feeds BVT's `analysis_date`, which the
  orchestrator replay freezes on).

## Task B — wire into the data pipeline + profile generation
- `data_fetcher.py`: route `.T` / Japan tickers to `edinet_client` (as EDGAR↔US,
  DART↔KR). Keep Yahoo Finance for price/market cap.
- Extend `profile_generator.py` to emit a JP profile YAML (`market: JP`, `currency:
  JPY`, `currency_unit` appropriate) from EDINET data — same shape BVT already runs.
- `method_selector.py`: JP large caps are single-segment operating companies →
  DCF / multiples like US; confirm no KR/US-specific assumptions leak.

## Task C — validate end to end
1. Generate a profile for **7203 (Toyota)** and **6758 (Sony)** from EDINET.
2. Run BVT → confirm a sane intrinsic band vs the live `.T` price (Yahoo), and that
   the console `[멀티플 교차검증]` + scenarios populate so the orchestrator's
   `_compute_band` works (the optionality band reframe is source-agnostic).
3. In the orchestrator, `decide 7203.T` should now produce a card with a BVT band
   **and the JP tax note** (already implemented). forward-EPS will likely abstain
   (thin `.T` consensus) → reconcile leaves BVT's stance — expected.

## Acceptance
1. `edinet_client` fetches + parses a JP annual report to the fields BVT needs;
   JPY units and March FY handled.
2. Toyota + Sony profiles valuate in BVT with a populated cross-val table + scenarios.
3. Orchestrator `decide` on a `.T` name yields a band-based stance + JP tax note.
4. Non-JP paths (EDGAR/DART) unchanged (regression).
5. Tests: EDINET parsing on a saved fixture (offline); no live calls in tests.

## Review questions
1. Japanese-GAAP vs IFRS filers use different XBRL taxonomies — does the parser need
   to handle both, or restrict v1 to IFRS filers (many large caps)?
2. EDINET consolidated vs non-consolidated statements — pick consolidated; confirm
   the tag selection.
3. Should EFE also get JP generic profiles (forward-EPS) for the few large caps with
   usable Yahoo consensus, or defer (BVT-only for JP in v1)?

## Follow-on (not this handoff)
- EFE JP generic profiles (optional, consensus-permitting).
- Broaden beyond 2–3 names once the pipeline is proven.
