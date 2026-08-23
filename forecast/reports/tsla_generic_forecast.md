# 테슬라 (Tesla, Inc.) — 실적 전망 (Generic)

- 티커: `TSLA` · 통화: USD (USD_million) · 희석주식수: 3,538,000,000
- 시드 분기: 2026Q1 (매출 22,387)
- 전망 구간: 2026Q2부터 4개 분기

## 확률가중 분기 전망

| 분기 | 매출 | 영업이익 | 순이익 | EPS(희석) |
|---|---:|---:|---:|---:|
| 2026Q2 | 26,808 | 1,697 | 1,490 | 0.42 |
| 2026Q3 | 28,180 | 1,807 | 1,594 | 0.45 |
| 2026Q4 | 30,500 | 1,981 | 1,755 | 0.50 |
| 2027Q1 | 27,556 | 1,816 | 1,617 | 0.46 |

## 연간 EPS (시나리오별)

| FY | Bear | Base | Bull | 가중 |
|---|---:|---:|---:|---:|
| 2026 | 0.36 | 1.23 | 2.65 | 1.37 |
| 2027 | 0.10 | 0.40 | 0.93 | 0.46 |

## 오프라인 백테스트 (1-step, seasonally-aware)

- **Post-break (headline)** · N=12 (EPS 12) · 매출 MAPE 7.7% / bias +1.5% · EPS MAPE 53.2% / bias -18.9%
  - RW MAPE 매출 12.4% / EPS 123.0% · MASE 매출 0.643 / EPS 0.780 · Theil U2 매출 0.641 / EPS 0.802 · consensus N=3
- **Full window** · N=26 (EPS 26) · 매출 MAPE 11.6% / bias -3.8% · EPS MAPE 121.1% / bias +40.1%
  - RW MAPE 매출 13.2% / EPS 101.4% · MASE 매출 0.862 / EPS 1.178 · Theil U2 매출 0.841 / EPS 0.977 · consensus N=3
- **Pre-break** · N=14 (EPS 14) · 매출 MAPE 14.9% / bias -8.4% · EPS MAPE 179.4% / bias +90.6%
  - RW MAPE 매출 13.8% / EPS 82.9% · MASE 매출 1.152 / EPS 2.204 · Theil U2 매출 1.140 / EPS 2.350 · consensus N=0

## Yahoo consensus (fiscal-aware)

- snapshot as-of: 2026-08-05
- 2026Q2: revenue N/A · EPS N/A
- 2026Q3: revenue N/A · EPS N/A
- FY2026: revenue N/A · EPS N/A
- FY2027: revenue N/A · EPS N/A
- quality: latest earnings_history end 2026-06-30 != latest actual period_end 2026-03-31; forward consensus anchor refused

## 데이터 출처 / 주의

- actuals는 EDGAR companyfacts as-filed 원본 공시 기준 공식 분기 GAAP (10-Q; Q4는 동일 회계연도 10-K 연간 − Q3 10-Q 9M 차감 복원). 구 프로파일의 NI/EPS LOW-CONFIDENCE 추정 해소 (NVDA-1 세션, 2026-07-11).
- 과거 EPS는 로드 시 파생: net_profit ÷ (as-filed 분기별 희석주식수 × split_history 조정, 현재 기준). FY2024 분기는 FY2025 공시에서 소급 재작성됨 — as-filed 원본 유지(point-in-time 백테스트 정합).
- 테슬라는 규제 크레딧·기타수익 변동으로 순이익 예측 오차가 큼 — 결과 해석 주의(마진 가정 신뢰도 낮음).
- FSD/로보택시 옵션가치는 top-down 마진 모델로 포착 불가 — BVT 옵셔널리티 SOTP 참조.

_시나리오 확률: bear 25% / base 50% / bull 25%_
