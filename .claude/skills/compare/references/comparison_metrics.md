# Comparison Metrics and Interpretation

## Core Comparison Metrics

### Value Metrics
| Metric | Source | Comparison Purpose |
|--------|--------|-------------------|
| `weighted_value` | ValuationResult | Probability-weighted per-share value (final conclusion) |
| `total_ev` | ValuationResult | Enterprise Value (pre-capital structure comparison) |
| `dcf.ev_dcf` | DCFResult | DCF enterprise value |
| `ddm.equity_per_share` | DDMValuationResult | DDM per-share value (financials) |
| `rim.per_share` | RIMValuationResult | RIM per-share value (financials) |
| `nav.per_share` | NAVResult | NAV per-share value (holding/REIT) |

### Multiple Metrics
| Metric | Interpretation |
|--------|---------------|
| EV/EBITDA | Relative to operating value (key for industry comparison) |
| P/E | Relative to net income (not applicable for loss-making) |
| P/BV | Relative to book value (key for financials/asset-heavy) |
| EV/Revenue | Relative to revenue (works for loss-making growth companies) |

### Profitability Metrics (Calculated from profile `consolidated`)
| Metric | Calculation |
|--------|------------|
| Operating margin | op / revenue |
| EBITDA margin | (op + dep + amort) / revenue |
| ROE | net_income / equity |
| D/E Ratio | de_ratio (direct field) |

### WACC Components
| Metric | Source |
|--------|--------|
| WACC | wacc.wacc |
| Ke | wacc.ke |
| βL | wacc.bl |
| Kd (after-tax) | wacc.kd_at |

## Comparison Table Formats

### Cross-Sectional (Peer) Comparison Example
```
| Company | EV/EBITDA | P/BV | ROE | WACC | Per-Share Value |
|---------|-----------|------|-----|------|----------------|
| Co. A   | 8.0x      | 1.2x | 12% | 9.5% | 45,000         |
| Co. B   | 6.5x      | 0.9x | 10% | 10.2%| 32,000         |
```

### Time-Series Comparison Example
```
| Analysis Date | WACC | EV   | Per-Share Value | Gap Ratio |
|--------------|------|------|----------------|-----------|
| 2025-06      | 9.5% | 2.1T | 45,000         | +15%      |
| 2025-12      | 10.2%| 1.9T | 38,000         | -5%       |
```

## DB Query Functions
- `list_valuations(company_name=, market=, limit=)` — list query
- `get_valuation(valuation_id)` — detail (includes input_data, result_data JSONB)
- `list_profiles(company_name=)` — profile list
