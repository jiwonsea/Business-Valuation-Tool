# Currency Unit Selection Rules

## Auto-Detection Logic (`engine/units.py`)

### Korea (KR)
| Revenue Scale (in millions KRW) | Display Unit | unit_multiplier |
|--------------------------------|-------------|----------------|
| < 10,000 (under 10B KRW) | 백만원 | 1,000,000 |
| 10,000 ~ 1,000,000 (10B~1T KRW) | 억원 | 100,000,000 |
| > 1,000,000 (over 1T KRW) | 백만원 | 1,000,000 |

> Large-cap companies (over 1T KRW) conventionally use millions KRW in financial statements

### US
| Revenue Scale | Display Unit | unit_multiplier |
|--------------|-------------|----------------|
| All | $M | 1,000,000 |

> US convention always uses $M (millions)

## Per-Share Conversion
```python
per_share = equity * unit_multiplier / shares
```

## YAML Override
Profile can directly specify `unit_multiplier` (overrides auto-detection).
