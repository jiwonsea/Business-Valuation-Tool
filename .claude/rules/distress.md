---
paths: ["engine/distress.py"]
---

# Distress Discount Engine Rules

- **Cap = 25% (default)**: Damodaran empirical studies show public-company peer-multiple haircuts cluster at 20-25% median, ~30% at 90th percentile. 35%+ applies only to Chapter 11 / near-bankruptcy proceedings, not going-concern SOTP. Profiles needing >25% must set `distress_max_discount` explicitly in YAML.
- **Cyclical 1-year loss exemption**: `loss_streak` counts consecutive years with EBITDA (op + dep + amort) < 0, not net_income — avoids penalising one-off items (tax, FX, impairment); `op` is post-D&A so add-back is correct. `loss_streak == 1` triggers no penalty for auto/steel/shipping/semiconductor/oil/construction/chemical industries (`_CYCLICAL_KEYWORDS` in `distress.py`). 2-year streak → 5% (vs 10% for non-cyclical). 3+ years → 15% regardless.
- **Segment-level differentiation**: `apply_distress_discount()` supports three tiers — `exempt_segments` (0% haircut: ev_revenue, distress_exempt), `healthy_segments` (50% of discount: profitable + significant asset share), and default (full discount). `valuation_runner.py` auto-populates `healthy` when `len(segments) >= 3 and distress.applied` — a segment qualifies only if `op > 0` AND `asset_share >= _HEALTHY_MIN_ASSET_SHARE_PCT` (20%). When all segment `assets` are 0 (missing data), falls back to `op > 0` only.
- **ev_revenue segments always exempt**: distress discount is excluded for ev_revenue segments because comp multiples already embed balance sheet risk.
- **Distress ICR prefers actual `interest_expense` over estimate.** `calc_distress_discount` checks `base.get("interest_expense", 0)` first; falls back to `gross_borr × kd_pre / 100` when absent. yfinance (US) provides this automatically; DART parser now extracts `이자비용`/`금융비용`/`금융원가` for KR companies. Do not remove the fallback — many older profiles and manual YAMLs won't have this field.
