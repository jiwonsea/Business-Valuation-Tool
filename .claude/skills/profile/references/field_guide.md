# Required/Optional Fields by Industry

## Common Required (All Profiles)
```yaml
company:
  name, legal_status, shares_total, shares_ordinary, analysis_date
segments:
  At least 1 segment (code → {name, multiple})
segment_data:
  At least 1 year including base_year
consolidated:
  At least 1 year including base_year (revenue, op, net_income, assets, liabilities, equity, dep, amort)
wacc_params:
  rf, erp, bu, de, tax, kd_pre, eq_w
dcf_params:
  ebitda_growth_rates (list of 5), tax_rate, terminal_growth
base_year: int
```

## Additional Fields by Industry

### Multi-Segment (SOTP)
- `segments`: 2+ segments, each with `multiple` set
- `segment_data`: per-segment revenue, op, assets required
- `peers`: at least 2-3 peers per segment (segment_code matching)
- `multiples`: segment_code → EV/EBITDA (set same as segments' multiple)

### Financials (DDM/RIM)
```yaml
wacc_params:
  is_financial: true   # Skip Hamada
  eq_w: 100.0          # Ke = WACC
  bu: 0.65             # Equity Beta (market-observed value)
```
- DDM: `ddm_params.dps`, `ddm_params.dividend_growth` required
- RIM: `rim_params.roe_forecasts` (list), `rim_params.terminal_growth`, `rim_params.payout_ratio`
- Cross-validation: `pbv_multiple`, `pe_multiple` recommended
- Can specify `valuation_method: "ddm"` or `"rim"` (if omitted, auto-determined by ROE-Ke spread)

### Growth/Tech (DCF Primary)
- `dcf_params`: growth rates start high → gradual decline pattern
- `ev_revenue_multiple`: required for loss-making company cross-validation
- `ps_multiple`: P/S cross-validation (Optional)

### Holding/REIT (NAV)
- `nav_params.revaluation`: investment asset revaluation adjustment
- REITs: `pffo_multiple`, `ffo` additional (P/FFO cross-validation)

### Unlisted Companies (Scenario-Focused)
- `scenarios`: at least 3 (Base/Bull/Bear)
- `cps_principal`, `cps_years`: required if CPS/RCPS exists
- `net_debt`, `eco_frontier`: net borrowings, eco-frontier adjustments
- Each scenario's `dlom`: liquidity discount (listed=0, unlisted=15~30% typical)

## Template References
Default template: `profiles/_template.yaml`
Financial industry sample: `profiles/kb_financial.yaml`
Multi-segment unlisted sample: `profiles/sk_ecoplant.yaml`
