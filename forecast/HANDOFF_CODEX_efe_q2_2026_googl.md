# HANDOFF (Codex) — EFE Q2 2026: GOOGL data rebuild + pre-print freeze

Date: 2026-07-22 (Cowork sandbox). Base HEAD `9d7200c`. Memory-path 9Q invariant
verified UNCHANGED: `BacktestResult` sha256 `077ecb10…933c` ✓. Suite: **191 passed**
(186 prior incl. DART-cache anchor test + 5 new GOOGL). No engine/schema code changed.

## 1. What shipped (GOOGL-1)
- **`profiles/googl.generic.yaml` fully rebuilt.** actuals replaced with 8 contiguous
  as-filed EDGAR quarters **2024Q2..2026Q1** (period_end + as-filed diluted_shares;
  Q4 = 10-K − 9M for 2024Q4/2025Q4). EPS derived at load. `split_history: []` —
  whole window is post the 20:1 split (2022-07-15); the split falls between 2022Q2's
  period-end and its filing, so period-end keying would be unsafe → window starts
  after it by construction. Forward scenarios re-anchored (research-sourced, see §3).
  `weighted_avg_diluted` 12,150,000,000 → **12,238,000,000** (2026Q1 as-filed).
- **Window rationale (why not longer):** Alphabet's pre-2024Q2 interim 10-Qs do NOT
  tag a same-accession 3-month diluted-share denominator under
  `WeightedAverageNumberOfDilutedSharesOutstanding` (only YTD/FY, or later-year
  restated comparatives). Under the same-accession integrity rule those quarters
  cannot be assembled, so the clean span is 2024Q2+. N=7 backtest pairs.
- **`scripts/_build_googl_cache.py`** (new, one-off): assembles the derived
  concept-slice cache `reports/.cache/edgar_companyfacts_CIK0001652044.json` from
  SEC companyconcept rows fetched via the sanctioned web tool (data.sec.gov proxy-403
  for processes). Rows: as-filed + comparatives, periods ending ≥ 2024-06-30 + 9M/FY.
- **`tests/test_googl_profile.py`** (new, 5 tests): contiguity+post-split window,
  single share basis / no seams, derived-EPS == as-filed, FY2025 sum identity,
  backtest scores & beats naive-RW revenue.
- **`reports/googl_q2_2026_forecast_FROZEN.md`** (pre-print freeze, delivered to user).
- Regenerated `reports/googl_generic_forecast.md` + `.json`.

## 2. Verification (independent-reproduce, don't trust claims)
- `python scripts/build_generic_actuals.py --cik 1652044 --fye-month 12 --start 2024Q2 --end 2026Q1`
  → 8 contiguous quarters, "FY sum identity + as-filed EPS coherence green".
- Backtest (N=7): rev MAPE **5.2%** (naive RW 6.5%; MASE 0.80 / Theil 0.95),
  EPS MAPE **12.0%** (RW 17.6%; MASE 0.77 / Theil 0.92), EPS bias **−11.5%**
  (structural OI&E omission — NOT an anchor-fixable bias; risk-band, like SK Hynix
  below-OP block).
- `python scripts/verify_9q_sha.py` → `077ecb10…933c` MATCH (sandbox, CPython≤3.11).
- `python -m pytest -q` → 191 passed.

## 3. Forward assumptions (research-sourced, as-of 2026-07-22, pre-print)
Smooth top-down (NOT seasonal — see freeze §f: engine backtest slot convention is
calendar-quarter-of-target while forward is step-from-seed; a seasonal vector is
mis-phased and loses to RW). base growth [0.055,0.05,0.06,0.045], op_margin 0.345
(2026Q1 realized 36.1%, FY2025 ~32.5%), tax 0.16. bear/bull bracket the consensus
range. Consensus ref (Yahoo as-of 2026-07-09 / Alphastreet): Q2 2026 rev $116.74bn,
adj EPS $2.87. Model Q2: rev $115.9bn (−0.7%), OP $40.0bn (34.5%), adj/op-EPS $2.79
(−2.8%). GAAP EPS deliberately NOT forecast (Anthropic OI&E; BofA ~$80bn markup →
GAAP EPS ~$8.4). See FROZEN (d) 3-layer gap.

## 4. Host follow-ups
1. Commit GOOGL-1: `git add profiles/googl.generic.yaml tests/test_googl_profile.py
   scripts/_build_googl_cache.py reports/googl_q2_2026_forecast_FROZEN.md
   reports/googl_generic_forecast.md reports/googl_generic_forecast.json
   HANDOFF_CODEX_efe_q2_2026_googl.md` (`reports/.cache/*` gitignored).
2. On host: delete the derived cache, run `edgar_fetcher.fetch_companyfacts(1652044)`
   (set `SEC_EDGAR_USER_AGENT`) for the full audited blob; re-run build_generic_actuals
   (expect identical actuals) + tests. Optionally extend history pre-2024Q2 only if the
   full blob exposes same-accession 3-month diluted shares there.
3. **Post-print scoring** (after 2026-07-22 ~20:00 UTC release): actual from 10-Q/IR;
   score **revenue / OP / adjusted-EPS** (GAAP EPS separately due to OI&E); 4-lever
   generic attribution (revenue / op-margin / OP→NI conversion incl. OI&E+tax / shares).
   Confirm which pre-registered swing factor fired.

## 5. 6-axis cross-check request (Codex)
정확성(as-filed 값·FY 항등식), 건전성(same-accession 규율·split 없음 정당성),
회귀안전(9Q sha·191 green), 범위규율(엔진/스키마 미변경, 프로파일+테스트+캐시만),
검증가능성(build_generic_actuals 재현), 유지보수성(window 주석·provenance).
Cowork의 "diff 0 / green" 주장 그대로 믿지 말고 독립 재현 요망.
