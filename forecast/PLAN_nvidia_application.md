# PLAN — Applying EFE beyond memory: NVIDIA as the test case

Date: 2026-07-10 · **Codex-reviewed 2026-07-10 (`REVIEW_nvidia_codex.md`) —
review decisions integrated below; the review is binding where it corrects
this plan.**
Scope: `earnings-forecast-engine` generic path (`schemas/generic.py`,
`engine/generic_forecast.py`, `generic_cli.py`, `profiles/nvda.generic.yaml`)
Basis: `HANDOFF_generic_engine.md` (2026-07-06 session), current
`reports/nvda_generic_forecast.md`

## 1. The question

Can the SK Hynix pipeline generalize to non-memory companies — and what does
NVIDIA specifically need? Short answer: the **memory driver chain must not be
ported** (it would be a fake model for NVDA), the **generic path is already the
honest model shape**, and the real work is (a) fixing two data-integrity defects
in the NVDA history, (b) lifting the diagnostic layers (skill metrics,
attribution, risk band, consensus gap) onto the generic path, (c) reporting
parity. The engine code was never the barrier; **driver observability** is.

## 2. Why the memory chain does not port

The SK Hynix chain works because each stage is externally observable:

| Stage (memory path)                  | Observability for SK Hynix              | NVIDIA equivalent                        |
|--------------------------------------|-----------------------------------------|------------------------------------------|
| bit growth × ASP per segment         | TrendForce/industry feeds, quarterly IR  | No unit×ASP disclosure (only segment revenue) |
| HBM share / premium mix              | IR + industry research                   | DC vs Gaming revenue only, coarse        |
| Cost-decline margin chain            | Commodity cost curves, mean-reverting    | No physical cost curve; margin = mix+pricing power |
| DART quarterly detail                | Official, cached, rate-limited API       | EDGAR companyfacts (10-Q GAAP)           |
| KR consensus vintage                 | Yahoo .KS (gated) / FnGuide (P1)         | Yahoo NVDA — rich analyst coverage       |

A bottom-up NVDA model (GPU units × ASP) would require assumption-heavy inputs
with no independent feed to validate against — exactly the "looks more precise
than it is" failure PLAN_skill_adoption.md §5 warns about. Revenue-growth-vector
× op-margin (the generic path) states its ignorance honestly.

**Decision rule for future companies:** give a company a physical driver chain
only if an independent industry feed exists for the physical driver (bits, ASP,
wafer starts, subscriber counts…). Otherwise it goes on the generic path.

## 3. Current NVDA output — evaluation (reports/nvda_generic_forecast.md)

Forward window rolls from 2026Q1 seed (rev $81.6bn); weighted 2026 quarters
$89–108bn, EPS $1.94→$2.36. Backtest N=19: rev MAPE 14.2% vs naive RW 18.5%
(beats RW), EPS MAPE 46.9% vs RW 67.4%, **EPS bias −45.8%**.

Three data-integrity defects dominate that EPS number (all Codex-confirmed):

1. **Mixed-basis EPS history (measured, Codex-reproduced).** NI-implied
   diluted shares step 0.62B → 2.49–2.54B → 24.4–25.0B with seams at 2020Q2
   and 2023Q2 — data-assembly boundaries, NOT the actual split dates (4:1
   Jul 2021, 10:1 Jun 2024). The EPS column was assembled from
   differently-adjusted sources. Mechanism (Codex correction — the original
   "companyfacts is not split-adjusted" wording was inaccurate): companyfacts
   holds BOTH the as-filed fact and later filings' retroactively split-adjusted
   comparatives for the same period (e.g. quarter ended 2020-10-25: 2.12
   as-filed vs 0.53 in a post-4:1 10-Q; quarter ended 2024-04-28: 5.98 vs
   0.60 post-10:1). Naive "first/last fact" selection mixes bases — exactly
   what happened here. Fix requires accession + period + split history
   together; note old quarters may have NO post-10:1 comparative at all.
2. **Q4 missing entirely + wrong-year labels (Codex finding).** The `actuals`
   block has no Q4 row in any year, and some rows' `quarter_label` doesn't
   match the accession's actual period-end year. The 1-step backtest treats
   sorted-adjacent rows as consecutive, so Q3→Q1 joins corrupt RW baseline,
   seasonal slot matching, and every MAPE/MASE/Theil on the current numbers.
   Fix: restore standalone Q4 = annual − 9M (same accession), add a
   quarter-contiguity validation.
3. **Partial circularity (known, HANDOFF §데이터 provenance).** Quarterly
   `actuals` were derived from reported FY totals → backtest revenue MAPE is
   optimistic. Replace with independently reported 10-Q quarters.

Model-shape limits (acceptable, but disclose): constant base margins across a
2019–2026 window that contains a regime break (FY2023→ AI supercycle, op margin
~25%→62%); labels are calendar-quarter approximations of a Jan-ending fiscal
year (~1 month offset — matters when aligning Yahoo consensus quarters).

## 4. Component portability matrix

| Layer                                   | Status on generic path | Work to port |
|-----------------------------------------|------------------------|--------------|
| EPS bridge / scenario weighting / annual agg | Already shared (`QuarterlyForecast`) | none |
| Skill metrics (MASE / Theil / vs-consensus) | Not wired (generic_cli has own 1-step MAPE) | small — reuse `engine/skill_metrics.py` |
| **EPS-error attribution (EFE-1 waterfall)** | Blocked: generic sets `gross_profit=0` → 5-lever bridge undefined | small — DECIDED (Codex): separate 4-lever generic function (rev / OP margin / OP→NI / shares); do not parametrize the 5-lever memory version |
| Below-OP risk band                      | Portable as-is (band over EPS points)  | small |
| Consensus gap                           | Not wired; Yahoo NVDA coverage is rich and reliable (vs sparse .KS) | medium — fiscal-quarter mis-join AND `.KS`-specific quality gate both block as-is reuse (see NVDA-2) |
| Valuation bridge                        | Portable; elasticity remains DRAFT     | none until BVT sensitivity lands |
| HTML/Plotly report                      | Memory-path only; generic emits MD     | medium — generic branch in `output/*` |
| Backtest honesty (no-lookahead, rolling seed) | generic backtest is 1-step slot-matched, weaker than memory 9Q protocol | medium |
| Segment bit×ASP chain, margin cost chain, DART fetcher | memory/Korea-specific | **do not port** |

## 5. Workstreams

### NVDA-1: Data integrity (host — network required)

Codex-ordered sub-stages; **backtest numbers are invalid until all three pass**:

- **1a — companyfacts normalization.** New `pipeline/edgar_fetcher.py`:
  cache the whole companyfacts blob per CIK (one request preserves every
  concept + later comparatives for accession audit; concept slices as derived
  caches if needed). Do NOT share the DART fetcher body (different auth /
  response shape / rate behavior); share only a tiny HTTP helper (UA, timeout,
  bounded retry, atomic cache write) if duplication actually appears.
  Extractor keeps `start/end/fy/fp/form/filed/accn/frame`; a standalone
  quarter's revenue·NI·COGS·shares should come from the same accession where
  possible; never mix disclosure vintages when deriving Q2/Q3/Q4 from YTD.
- **1b — Q4 restoration + label contract.** Standalone Q4 = annual − 9M (same
  accession); fix wrong-year labels; explicit fiscal↔model label mapping for
  the Jan-ending fiscal year; quarter-contiguity validation before any
  backtest runs.
- **1c — shares normalization + derived EPS.** Add `split_history:
  [{date, ratio}]` to `GenericProfile` (explicit-assumptions convention,
  auditable), applied in a normalization layer. Collect per-quarter
  `WeightedAverageNumberOfDilutedSharesOutstanding`, split-adjust to current
  basis, then DERIVE `eps_diluted = net_profit × unit_scale /
  adjusted_diluted_shares` at load. Do NOT recompute historical EPS with the
  fixed forward 24.49B (that would erase real dilution/buyback variation).
  Keep original as-filed EPS + accession as provenance notes.
- Fix Tesla NI/EPS (known HANDOFF item) in the same pass.
- Verification: re-run `generic_cli.py --profile profiles/nvda.generic.yaml`
  and document before/after. No numeric acceptance guarantee — the −45.8%
  bias is split-artifact + label-artifact mixed, so measure, don't presume
  (Codex: single-digit-bias expectation was not warranted).

### NVDA-2: Metrics parity (sandbox-able once NVDA-1 data is cached)
- Reuse `engine/skill_metrics.py` (Codex-confirmed: `backtest_generic` rows
  carry rw_rev/rw_eps and convert directly; no memory-path import cycle).
  Keep the legacy MAPE/bias fields for compatibility and ADD the skill block —
  minimal change. Only after NVDA-1b's contiguous labels land.
- Consensus gap: do NOT reuse `to_consensus_record` as-is (Codex): its 0q/+1q →
  calendar-quarter join silently mis-joins a Jan-ending fiscal year, its
  quality messages are `.KS`-specific, and the implied-net-margin >60% check
  would false-positive on NVDA's genuine margins. Reuse the raw Yahoo parsing;
  add a separate, tested normalization keyed to the profile's fiscal calendar
  (period-end ↔ fiscal label ↔ model label). Keep the `quality_notes` contract
  but make thresholds issuer-neutral (company margin range + unit coherence,
  not market suffix).
- Attribution: separate 4-lever generic function (revenue / OP margin /
  OP→NI conversion / shares) matching what the generic model actually
  predicts — do NOT parametrize the 5-lever memory version by lever count
  (Codex). Deprioritized within NVDA-2; waterfall rendering reused as-is.

### NVDA-3: Reporting parity (sandbox)
- Generic branch in `output/html_builder.py` + `plotly_charts.py`: fan,
  scenario compare, risk band, attribution waterfall, consensus gap table.
  Keep MD as the fallback. Same "사후 귀인 — 예측 신호 아님" labeling contract.

Priority: NVDA-1 ≫ NVDA-2 > NVDA-3 (Codex-endorsed). NVDA-1 is prerequisite —
every metric computed before it is polluted by the basis seams, the missing
Q4s, and circularity. NVDA-3 explicitly deferred until the data/metrics
contract is stable: a polished report would visually reinforce wrong numbers.

## 6. Risks
- **Comparative-coverage gap (Codex):** companyfacts' "latest fact per period"
  is NOT guaranteed to be on today's basis — old quarters may never appear in
  a post-10:1 filing's comparatives. This is why 1c derives EPS from NI +
  split-adjusted shares instead of selecting an EPS fact.
- **Regime non-stationarity:** a backtest window straddling FY2023 punishes any
  constant-margin model; report split-window metrics (pre/post 2023Q1) rather
  than blending, or start the scored window at 2023Q2.
- **Fiscal offset:** silently joining calendar-labeled model quarters to Yahoo
  fiscal quarters would corrupt the consensus gap — make the mapping explicit
  and tested.
- **Attribution mis-read:** on the generic path the "opex" lever does not exist
  (no GP decomposition); label levers accordingly so the waterfall never implies
  a decomposition the model didn't make.
- Keep generic ↔ memory paths fully separated (HANDOFF design contract);
  the 9Q SK Hynix invariant must stay bit-identical through all three
  workstreams (baseline sha256 recorded 2026-07-10).

## 7. Verification
- `pytest tests/test_generic_forecast.py -q` + new fetcher/alignment/contiguity
  tests (1a: same-accession consistency; 1b: no Q3→Q1 joins; 1c: implied
  shares monotonic-smooth after normalization, no seams).
- `python generic_cli.py --profile profiles/nvda.generic.yaml` before/after
  NVDA-1 — record the measured bias change in the HANDOFF (no presumed target).
- Memory path regression: `pytest -q` full suite + 9Q backtest sha256 match
  (`077ecb10…933c`).
