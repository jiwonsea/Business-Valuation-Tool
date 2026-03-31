# Scenario Design Patterns

## Probability Allocation Rules
- Sum = exactly 100% (tolerance 0.1%p)
- Base Case gets highest probability (typically 40~60%)
- Extreme scenarios (Bull/Bear) each 15~30%

## Listed Company Pattern
```yaml
scenarios:
  Base:   {prob: 50, ipo: "상장", dlom: 0, shares: <total_shares>}
  Bull:   {prob: 25, ipo: "상장", dlom: 0, shares: <total_shares>}
  Bear:   {prob: 25, ipo: "상장", dlom: 0, shares: <total_shares>}
```
- Listed companies: `dlom: 0` (no liquidity discount)
- `shares` is the same across all scenarios (total issued shares)
- Scenario differences: multiples, growth rate assumptions (separate profile or described in desc)

## Unlisted Company Pattern (With CPS/RCPS)
```yaml
scenarios:
  A:  # IPO success
    prob: 20
    ipo: "성공"
    dlom: 0
    shares: <total_shares>       # Including CPS conversion
    cps_repay: 0                 # Converted, so no repayment
  B:  # IPO failure + FI friendly
    prob: 45
    ipo: "불발"
    irr: 5.0                    # FI required return
    dlom: 20
    shares: <ordinary_only>      # CPS redeemed and extinguished
    cps_repay: null              # null = auto-calculate based on IRR
    rcps_repay: 490000
  C:  # IPO failure + FI dispute
    prob: 35
    ipo: "불발"
    irr: 12.0
    dlom: 25
    shares: <ordinary_only>
    cps_repay: null
    rcps_repay: 575000
```

### Key Notes
- IPO success: `shares` = total issued shares (CPS converted), `cps_repay: 0`
- IPO failure: `shares` = ordinary only (CPS extinguished), `cps_repay: null` (IRR-based auto-calc) or direct amount
- `irr` field: used only in IPO failure scenarios. FI's required return rate.
- `cps_repay: null` vs `cps_repay: 0`: null = IRR-based auto-calc, 0 = no repayment

## Unlisted Company Pattern (Simple Structure, No CPS)
```yaml
scenarios:
  Base:  {prob: 50, ipo: "N/A", dlom: 20, shares: <total_shares>}
  Bull:  {prob: 25, ipo: "N/A", dlom: 15, shares: <total_shares>}
  Bear:  {prob: 25, ipo: "N/A", dlom: 25, shares: <total_shares>}
```
- `dlom`: liquidity discount for unlisted (typically 15~30%)
- Bull has lower DLOM, Bear has higher DLOM

## DLOM Range Reference
| Situation | DLOM Range |
|-----------|-----------|
| Listed | 0% |
| Unlisted (high IPO likelihood) | 10~15% |
| Unlisted (general) | 15~25% |
| Unlisted (very low liquidity) | 25~35% |
