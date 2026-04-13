# Synthesis — Phase 3 Calibration Spec (4 decisions)

## Vote tally

| Q | Gemini 🟡 | Codex 🔴 | Qwen 🟤 | Sonnet 🟠 | Consensus |
|---|---|---|---|---|---|
| Q1 knob | beta | beta | hierarchical | sc.prob | **Split** |
| Q2 metric | MAPE+coverage | MAPE+RMSE+hit | MAPE+hit | MAPE+coverage | **MAPE primary, +coverage** |
| Q3 min N | 10+ short-horizon | 30+ × 12m | tiered (10/30) | 10+ no-suppress + flag | **Tiered + always-show** |
| Q4 exclude | (cut off) | all 4 | ML + catalog | ML + WF-CV + catalog | **ML + WF-CV + catalog** |

## Where it splits and why
**Q1 is the real fork.** Beta-tuners (Gemini, Codex) argue identifiability flows from one structural layer; Sonnet's pragmatic counter is that beta lives inside √N/N dampening so its gradient is unstable below N=300, while sc.prob has only one free parameter per scenario pair and is identifiable at N=10. Qwen wants both with shrinkage but admits "if hierarchy isn't penalized → unidentifiable noise" — and we have no shrinkage infra.

**Sonnet's pragmatic argument wins on data-volume grounds:** the bucket math is brutal. 80 records ÷ (2 markets × 5 sectors × 3 horizons) = ~3 per bucket worst case, ~10 typical. Beta tuning on this is fitting noise. sc.prob tuning at sector-level (collapse horizon) gives ~25 per bucket — actually viable. **Recommend (b) sc.prob as Phase 3, beta tuning deferred to Phase 4 once N>300.**

**Q2 — MAPE unanimous, coverage_rate is the right secondary.** Three voices want a directional/spread sanity check; coverage_rate (Sonnet, Gemini) catches the "narrow CI looks accurate" failure that pure MAPE rewards, better than hit-rate which is too coarse at small N. RMSE adds little over MAPE for a human-facing report. **Recommend MAPE primary + coverage_rate secondary.**

**Q3 — tiered threshold reconciles all four.** Qwen's tiered approach (10+ short, 30+ long) plus Sonnet's "always emit, flag low-N" is the synthesis. Codex's blanket 30+ is too strict for short horizons; Gemini's 10+ everywhere ignores T+12m noise. **Recommend: emit always, gate confidence label by tier (10+ T+3/6m = "preliminary", 30+ T+12m = "stable").**

**Q4 — ML + walk-forward + catalog auto-discovery excluded.** Real-time recompute is moot under locked report-only decision. **Recommend exclude all three; explicitly defer walk-forward CV to a Phase 3.5 follow-on.**

## Final recommendations

| Q | Decision |
|---|---|
| Tuning knob | **sc.prob** (single free param per scenario pair, tractable at N=10–30) |
| Loss / metric | **MAPE primary, coverage_rate secondary** (both already in `backtest/metrics.py`) |
| Min sample | **Always emit. Confidence label = "preliminary" (N≥10 T+3/6m) → "stable" (N≥30 T+12m). No hard suppression** |
| Out of scope | **ML models, walk-forward CV automation, driver catalog auto-discovery** |

## Dissent preserved
- **Beta tuning (Gemini+Codex):** valid Phase 4 target once N>300 per bucket. Add to backlog.
- **RMSE (Codex):** include as a third reported number even if not the optimization target — cheap and surfaces large misses.
- **Hit-rate (Qwen, Codex secondary):** include as diagnostic in report header, not optimization target.
