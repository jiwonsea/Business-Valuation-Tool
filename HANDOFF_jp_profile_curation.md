# HANDOFF → Codex — JP profile curation + draft-profile guard

> **From**: Claude (Opus 4.8), 2026-07-08
> **To**: Codex (machine)
> **Context**: the JP/EDINET plumbing works (702 BVT / 89 orchestrator / 5 EDINET
> tests green), but `profiles/7203_t.yaml` and `6758_t.yaml` are **uncurated
> auto-generated drafts** — unfilled TODOs, no segments, placeholder `multiple: 10.0`,
> no scenario params, default WACC. So the "extremely aggressive Toyota DCF" is not a
> deep bug: it is placeholder assumptions + a low JP WACC not matched by a low JP
> terminal growth. The band is therefore untrustworthy until the profile is curated
> the way US/KR profiles were.

## Diagnosis (verified by reading the profile)
```
# TODO: Add segment data, multiples, and scenario parameters
segments:
  MAIN: { multiple: 10.0 }   # TODO: Set appropriate EV/EBITDA multiple
```
No segments, placeholder multiple, no scenarios → the DCF runs on defaults. Combined
with a JP risk-free (~1% JGB) low WACC and a US/KR-inherited terminal growth, the
WACC–growth spread is too wide → the DCF explodes.

## Task A — curate the JP large-cap profiles (7203, 6758)
Bring them to US/KR parity:
- **Segments** from EDINET consolidated segment data (Toyota: automotive / financial
  services / other).
- **Peer multiples**: add JP/global auto + electronics comps (reuse `peer_fetcher`
  with JP peers) so the cross-val `[멀티플 교차검증]` table has independent `[P]`
  values, not just market-derived `[T]`.
- **Scenario params** (Bear/Base/Bull) with JP-appropriate assumptions.

## Task B — JP WACC ↔ terminal-growth consistency (the root of the explosion)
- A low JP discount rate MUST pair with a **low JP terminal growth** (Japan's low
  nominal GDP growth), not the US/KR default. Check `macro_data.py` terminal-growth
  by market — it likely inherits a US/KR value for JP.
- Verify beta/ERP for JP: `engine` WACC inputs should use JP risk-free + JP ERP, and
  the resulting WACC–g spread should land the DCF within a sane range of the peer
  multiples (not 2–3× above).

## Task C — draft-profile guard (don't trade on a stub)
Any profile still carrying draft markers (TODO comments, missing `segments`/
`scenarios`, placeholder multiples) must be treated as **not investable**:
- BVT sets quality to **F** and emits a `draft: true` flag in console + `--json`.
- The orchestrator adapter already caps conviction to low for D/F grades; extend it
  to **force `stance = neutral`** when the draft flag / grade F is present, so a
  stub profile can never produce a confident BUY. (Small change in
  `../investment-orchestrator/adapters/fundamentals.py::parsed_to_signal`.)

## Validate
1. After curation, Toyota + Sony intrinsic band is sane vs the live `.T` price, and
   the DCF per-share is within ~[0.7, 1.5]× the independent peer-multiple median
   (i.e. no longer an extreme outlier).
2. `decide 7203.T` yields a band stance whose conviction reflects a real (not draft)
   quality grade, with the JP tax note attached.
3. An intentionally-draft profile → grade F + `draft:true` → orchestrator returns
   neutral/low (abstains).

## Acceptance
1. 7203/6758 profiles have real segments, `[P]` peer multiples, scenarios, JP WACC.
2. JP terminal growth is JP-specific; DCF no longer explodes.
3. Draft guard: uncurated profile → not investable (F + draft flag → orchestrator neutral).
4. BVT + orchestrator suites stay green; add a curated-vs-draft test.

## Review questions
1. Is JP terminal growth currently inherited from US/KR in `macro_data.py`? Fix if so.
2. Are JP peers available to `peer_fetcher`, or do they need a JP comp list?
3. Should JP stay OUT of any live-traded watchlist until Task A/B pass? (Recommended
   yes — plumbing ≠ trustworthy band.)

## Posture until done
JP is **plumbed but not investable**. Keep `.T` names out of the live universe /
decision log until curation + WACC consistency land. US + KR remain the live markets.
