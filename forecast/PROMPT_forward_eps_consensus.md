# PROMPT — Consensus dimension in generic `--json` (forward-EPS signal v2)

> **Run this inside `earnings-forecast-engine/`.** Standalone task for an EFE session.
> **Consumer**: `../investment-orchestrator/adapters/forward_eps.py` (v1) already consumes the existing `generic_cli.py --json`. This adds the one dimension v1 lacks.
> **Prerequisite reading**: `engine/consensus_diff.py`, `engine/skill_metrics.py`, `engine/valuation_bridge.py`, `generic_cli.py`, `CLAUDE.md` ("Model must beat naive-baseline error").

---

## 0. Why

The orchestrator's forward-EPS signal (v1) uses forward trajectory + naive-baseline skill only. It is genuinely independent of BVT (it excludes `valuation_bridge`) and correctly abstains when the model fails to beat naive (verified: Samsung abstains, NVDA/AAPL/TSLA pass). **But v1 has a known bias: forward EPS usually rises for growth names, so almost everything skill-passing reads bullish.** It cannot tell "growing" from "growing more/less than the market already prices."

The fix is the **consensus gap**: is the model's forward EPS *above or below* Yahoo consensus? A name whose EPS rises but sits *below* consensus is bearish-relative-to-expectations even though it grows. `engine/consensus_diff.py` already computes this per period; it is simply not in the `--json`.

**Guardrail:** do NOT let the consensus dimension override the naive-baseline skill gate. Consensus-relative direction is only meaningful when the model has skill (MASE < 1 / beats RW). Keep the abstain-on-no-skill behavior.

---

## 1. Tasks

### T1 — Add a `signal` block to `generic_cli.py --json`
Emit a compact, adapter-ready block alongside the existing `weighted_annual` / `weighted_quarterly` / `backtest`:

```jsonc
"signal": {
  "bvt_independent": true,                    // asserts: excludes valuation_bridge
  "skill": {
    "eps_mape": 10.56, "naive_rw_eps_mape": 14.71,
    "mase_eps": 0.72, "theil_u2_eps": 0.80,   // from engine/skill_metrics.py
    "skill_vs_consensus_eps": 0.15,           // 1 - modelMAE/consensusMAE; >0 beats consensus
    "skill_pass": true                         // eps beats naive RW
  },
  "consensus": [                               // from engine/consensus_diff.py
    {"period": "FY2026", "metric": "eps", "model": 7.20, "consensus": 6.60,
     "gap_pct": 0.091, "direction": "above"}   // above | below | in_line | n_a
  ],
  "trajectory": {"direction": "rising", "growth_pct": 0.216, "n_quarters": 4}
}
```

- Reuse `compute_consensus_gap` and `compute_skill`; do not recompute.
- When consensus is unavailable (offline / no Yahoo), emit `direction: "n_a"` and null gaps — never fabricate. `bvt_independent` must stay `true`: if any field would require `valuation_bridge`, omit it.

### T2 — Do the same for the native `cli.py` (SK Hynix) path
So `sk_hynix` gets a `signal` block too (native memory model). Same schema.

### T3 — Offline degradation + test
- With no network, the `signal` block still emits skill + trajectory; consensus is `n_a`. The v1 adapter already handles this (it ignores consensus today).
- Add a test asserting the `signal` block shape and that `skill_pass` matches `eps_mape < naive_rw_eps_mape`.

## 2. Then (orchestrator side, separate small change)
Upgrade `adapters/forward_eps.py` to v2: when `consensus[].direction` is present and `skill_pass`, fold it in — `rising & above` → strong bullish; `rising & below` → neutral/bearish (growth already priced); `falling & below` → bearish. This removes the v1 bullish bias and gives the reconcile node a sharper premium adjudication.

## 3. Acceptance
1. `generic_cli.py --profile profiles/nvda.generic.yaml --json` emits the `signal` block with `bvt_independent: true`, skill (incl. MASE/Theil), consensus (or `n_a` offline), trajectory.
2. `skill_pass` equals `eps_mape < naive_rw_eps_mape` on every profile.
3. Offline run still succeeds with `consensus.direction = "n_a"`.
4. No field in the `signal` block derives from `valuation_bridge` (independence preserved).

## 4. Review questions
1. Is `skill_vs_consensus_eps` stable enough on the small (~3–8Q) sample to gate direction, or should it be advisory only?
2. For KR names (`.KS`), Yahoo consensus reliability is low (per EFE README) — should the consensus block carry a per-market reliability flag so the adapter can discount it?
