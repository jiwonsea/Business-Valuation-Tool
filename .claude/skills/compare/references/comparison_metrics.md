# 비교 지표 목록과 해석

## 핵심 비교 지표

### 가치 지표
| 지표 | 소스 | 비교 용도 |
|------|------|----------|
| `weighted_value` | ValuationResult | 확률가중 주당 가치 (최종 결론) |
| `total_ev` | ValuationResult | Enterprise Value (자본구조 전 비교) |
| `dcf.ev_dcf` | DCFResult | DCF 기업가치 |
| `ddm.equity_per_share` | DDMValuationResult | DDM 주당 가치 (금융주) |
| `rim.per_share` | RIMValuationResult | RIM 주당 가치 (금융주) |
| `nav.per_share` | NAVResult | NAV 주당 가치 (지주사/리츠) |

### 멀티플 지표
| 지표 | 해석 |
|------|------|
| EV/EBITDA | 영업가치 대비 (업종 비교 핵심) |
| P/E | 순이익 대비 (적자 기업 불가) |
| P/BV | 장부가 대비 (금융/자산주 핵심) |
| EV/Revenue | 매출 대비 (적자 성장주 가능) |

### 수익성 지표 (프로필 `consolidated`에서 계산)
| 지표 | 계산 |
|------|------|
| 영업이익률 | op / revenue |
| EBITDA 마진 | (op + dep + amort) / revenue |
| ROE | net_income / equity |
| D/E Ratio | de_ratio (직접 필드) |

### WACC 구성요소
| 지표 | 소스 |
|------|------|
| WACC | wacc.wacc |
| Ke | wacc.ke |
| βL | wacc.bl |
| Kd(세후) | wacc.kd_at |

## 비교 테이블 형식

### 횡단면 (Peer) 비교 예시
```
| 기업 | EV/EBITDA | P/BV | ROE | WACC | 주당가치 |
|------|-----------|------|-----|------|---------|
| A사  | 8.0x      | 1.2x | 12% | 9.5% | 45,000  |
| B사  | 6.5x      | 0.9x | 10% | 10.2%| 32,000  |
```

### 시계열 비교 예시
```
| 분석일 | WACC | EV | 주당가치 | 괴리율 |
|--------|------|----|---------|--------|
| 2025-06| 9.5% | 2.1조 | 45,000 | +15% |
| 2025-12| 10.2%| 1.9조 | 38,000 | -5%  |
```

## DB 조회 함수
- `list_valuations(company_name=, market=, limit=)` — 목록 조회
- `get_valuation(valuation_id)` — 상세 (input_data, result_data JSONB 포함)
- `list_profiles(company_name=)` — 프로필 목록
