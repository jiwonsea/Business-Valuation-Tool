# HANDOFF — PLAN_nvidia_application.md Codex Review

Date: 2026-07-10 · Author: Cowork session · For: Codex feasibility review (host)
Scope: `earnings-forecast-engine` generic path only. Memory path (SK Hynix 9Q
invariant, baseline sha256 `077ecb10…933c` recorded 2026-07-10) must stay
bit-identical through everything below.

## 1. What is being reviewed

`PLAN_nvidia_application.md` (commit 13a7e47): applicability analysis of EFE
beyond memory, NVIDIA as test case. Verdict reached in the Cowork session:

- **Do not port** the memory driver chain (bit×ASP×HBM, margin cost chain,
  DART). NVDA has no unit×ASP disclosure → a bottom-up chain would be
  unverifiable fake precision. Decision rule: physical driver chain only when
  an independent industry feed exists for the physical driver.
- The existing generic path (`engine/generic_forecast.py`) is the honest model
  shape for NVDA; the work is data integrity + diagnostic-layer parity, not
  engine work.
- Workstreams: NVDA-1 (data integrity, host) ≫ NVDA-2 (metrics parity) >
  NVDA-3 (reporting parity).

## 2. Key claim for Codex to verify FIRST (blocks everything)

**Split-unadjusted EPS history in `profiles/nvda.generic.yaml`.**

Evidence from the Cowork session: 2019Q3 row has NI $899M, eps_diluted 1.45.
With the profile's fixed 24.49B diluted shares: 899e6 × 1e6_scale… → model EPS
≈ 0.037. Reported 1.45 ÷ 0.037 ≈ 40 = (4:1 split Jul 2021) × (10:1 split
Jun 2024). Same factor reproduces on other pre-2021 rows. Conclusion: the
`actuals` EPS column mixes three share bases across the window, and the
backtest's **EPS bias −45.8% / MAPE 46.9% is dominated by this artifact, not
model error**.

**MEASURED in-session (yaml → NI×1e6/eps), so this part is already verified —
Codex should re-derive independently but the numbers are:**

| rows | implied diluted shares | basis |
|---|---|---|
| 2019Q3–2020Q1 | 0.62B | pre-both-splits (×40 vs current) |
| 2020Q2–2023Q1 | 2.49–2.54B | post-4:1 only (×10) |
| 2023Q2–2026Q1 | 24.4–25.0B | current basis (×1) |

The basis transitions at **2020Q2 and 2023Q2 — NOT at the actual split dates
(Jul 2021 4:1, Jun 2024 10:1)** — i.e. the EPS column was assembled from
differently-adjusted sources at arbitrary seams. Mixed-basis, worse than
merely "unadjusted". Every backtest EPS metric over this window is polluted.

Codex checks:
1. Re-derive the implied-shares table above independently; confirm the seams.
2. Confirm EDGAR companyfacts `EarningsPerShareDiluted` is as-filed (NOT
   retroactively split-adjusted) — this determines whether NVDA-1 must carry a
   `split_history:` adjustment or can pull an adjusted series from elsewhere
   (yfinance quarterly EPS IS back-adjusted; mixing the two sources without
   declaring the basis is exactly how this bug was created).
3. Decide the canonical basis for stored `actuals` (recommend: current basis,
   i.e. back-adjust everything to today's share count, provenance-noted) and
   whether NI (unaffected by splits) + adjusted shares should replace stored
   EPS entirely, with EPS always derived at load.

## 3. Secondary claims to sanity-check

- **Circularity:** quarterly `actuals` partially derived from FY totals
  (known, HANDOFF_generic_engine.md) → rev MAPE 14.2% is optimistic. Fix =
  independent 10-Q quarters via new `pipeline/edgar_fetcher.py` with
  dart_fetcher-style caching.
- **Fiscal offset:** NVDA FY ends late Jan; profile labels are calendar
  approximations. Yahoo consensus quarters are fiscal. PLAN proposes an
  explicit `fiscal_quarter_offset` / label↔fiscal map, tested. Confirm no
  silent join anywhere today.
- **Regime break:** 2019–2026 window straddles the FY2023+ AI supercycle
  (op margin ~25%→62%). PLAN proposes split-window metrics (pre/post 2023Q1)
  or scoring from 2023Q2. Codex: pick one and justify.
- **Attribution on generic path:** `gross_profit=0` by design → EFE-1's
  5-lever bridge is undefined. PLAN offers (a) 4-lever variant
  (rev / OP conv / tax-fin / shares) now, or (b) ingest CostOfRevenue in
  NVDA-1 and keep 5 levers. Codex: which, and is a lever-count-parametrized
  `attribute_eps_error` worth it vs a separate generic variant?

## 4. Questions for Codex

1. NVDA-1 schema: `split_history:` block in `GenericProfile`
   (`[{date, ratio}]`, applied at load) vs storing pre-adjusted values with
   provenance notes only — which fits the `extra="forbid"` / explicit-
   assumptions convention better?
2. `pipeline/edgar_fetcher.py`: companyfacts JSON is one blob per company —
   cache whole-blob (simple, large) or per-concept slices (dart_fetcher
   pattern)? Rate/UA requirements are trivial vs DART; any reason to share the
   retry/backoff helper?
3. NVDA-2: reuse `engine/skill_metrics.py` requires pairs in its expected
   shape — confirm `backtest_generic` rows convert cleanly (they carry
   rw_rev/rw_eps already) and no memory-path import cycle appears.
4. Consensus vintage for NVDA: yfinance vintage history for US tickers is
   richer than .KS — is the existing `to_consensus_record` quality gate
   (`quality_notes`) reusable as-is, or does it encode .KS-specific checks?
5. Priority/effort ranking of NVDA-1/2/3 as split by the PLAN; anything to cut
   or merge. NVDA-3 (generic HTML branch) is portfolio-visible but largest —
   defensible to defer?
6. Any accuracy risk missed — especially whether split-adjusting EPS while
   leaving `weighted_avg_diluted` fixed at 24.49B is coherent for the forward
   window (it is the CURRENT share count, so forward EPS is fine; only the
   backtest comparison needed the historical basis fix). Confirm.

## 5. Agreed workflow

1. This doc → Codex review on host (repo is committed through 13a7e47; working
   tree clean, 146 tests green).
2. If the split-basis finding survives review → NVDA-1 implementation session
   on host (network needed for EDGAR); then NVDA-2 (sandbox-able once cached),
   then decide NVDA-3.
3. Every session ends: `pytest -q` full suite + memory-path 9Q sha256 match +
   commit per-session (git hygiene now clean — keep it that way).
