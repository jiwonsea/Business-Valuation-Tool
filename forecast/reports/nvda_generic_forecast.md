# 엔비디아 (NVIDIA Corporation) — 실적 전망 (Generic)

- 티커: `NVDA` · 통화: USD (USD_million) · 희석주식수: 24,490,000,000
- 시드 분기: 2026Q1 (매출 81,615)
- 전망 구간: 2026Q2부터 4개 분기

## 확률가중 분기 전망

| 분기 | 매출 | 영업이익 | 순이익 | EPS(희석) |
|---|---:|---:|---:|---:|
| 2026Q2 | 89,368 | 55,272 | 47,617 | 1.94 |
| 2026Q3 | 96,196 | 59,572 | 51,328 | 2.10 |
| 2026Q4 | 102,431 | 63,509 | 54,725 | 2.23 |
| 2027Q1 | 107,856 | 66,942 | 57,689 | 2.36 |

## 연간 EPS (시나리오별)

| FY | Bear | Base | Bull | 가중 |
|---|---:|---:|---:|---:|
| 2026 | 5.19 | 6.35 | 7.21 | 6.27 |
| 2027 | 1.75 | 2.40 | 2.86 | 2.36 |

## 오프라인 백테스트 (1-step, seasonally-aware)

- **Post-break (headline)** · N=12 (EPS 12) · 매출 MAPE 11.5% / bias -11.2% · EPS MAPE 17.3% / bias -13.5%
  - RW MAPE 매출 17.6% / EPS 24.7% · MASE 매출 0.592 / EPS 0.836 · Theil U2 매출 0.621 / EPS 0.998 · consensus N=4
- **Full window** · N=26 (EPS 26) · 매출 MAPE 9.9% / bias -4.1% · EPS MAPE 91.6% / bias +77.4%
  - RW MAPE 매출 13.9% / EPS 30.6% · MASE 매출 0.609 / EPS 1.081 · Theil U2 매출 0.628 / EPS 1.038 · consensus N=4
- **Pre-break** · N=14 (EPS 14) · 매출 MAPE 8.6% / bias +2.0% · EPS MAPE 155.3% / bias +155.3%
  - RW MAPE 매출 10.7% / EPS 35.7% · MASE 매출 0.754 / EPS 3.537 · Theil U2 매출 0.990 / EPS 3.175 · consensus N=0

## Yahoo consensus (fiscal-aware)

- snapshot as-of: 2026-08-05
- 2026Q2: revenue 91,846.10 · EPS 2.08
- 2026Q3: revenue 103,131.21 · EPS 2.35
- FY2027: revenue 393,852.73 · EPS 9.00
- FY2028: revenue 561,509.44 · EPS 12.89

## 데이터 출처 / 주의

- actuals는 EDGAR companyfacts as-filed 원본 공시 기준 공식 분기 GAAP (10-Q; Q4는 동일 회계연도 10-K 연간 − Q3 10-Q 9M 차감 복원). NVDA-1 (2026-07-11).
- 과거 EPS는 저장하지 않고 로드 시 파생: net_profit ÷ (as-filed 분기별 희석주식수 × split_history 조정, 현재 기준). as-filed EPS·accession은 source에 보존.
- 라벨 계약: 1월 결산 → fiscal FY(N)Qq = model (N-1)Qq (캘린더 분기 근사, ~1개월 오프셋). 1월 종료 분기는 전년 Q4.
- FY2026(2026-01 종료) 검증: 분기 매출 합 = $215,938M, 순이익 합 = $120,067M (10-K 0001045810-26-000021과 일치).

_시나리오 확률: bear 25% / base 50% / bull 25%_
