# 텍사스 인스트루먼트 (Texas Instruments Incorporated) — 실적 전망 (Generic)

- 티커: `TXN` · 통화: USD (USD_million) · 희석주식수: 912,000,000
- 시드 분기: 2026Q1 (매출 4,825)
- 전망 구간: 2026Q2부터 4개 분기

## 확률가중 분기 전망

| 분기 | 매출 | 영업이익 | 순이익 | EPS(희석) |
|---|---:|---:|---:|---:|
| 2026Q2 | 5,207 | 2,072 | 1,721 | 1.89 |
| 2026Q3 | 5,379 | 2,189 | 1,820 | 2.00 |
| 2026Q4 | 5,206 | 2,016 | 1,672 | 1.83 |
| 2027Q1 | 5,312 | 1,997 | 1,655 | 1.81 |

## 연간 EPS (시나리오별)

| FY | Bear | Base | Bull | 가중 |
|---|---:|---:|---:|---:|
| 2026 | 4.94 | 5.79 | 6.35 | 5.72 |
| 2027 | 1.53 | 1.82 | 2.08 | 1.81 |

## 오프라인 백테스트 (1-step, seasonally-aware)

- **Post-break (headline)** · N=5 (EPS 5) · 매출 MAPE 6.2% / bias +0.2% · EPS MAPE 13.4% / bias +13.4%
  - RW MAPE 매출 6.4% / EPS 11.4% · MASE 매출 0.950 / EPS 1.044 · Theil U2 매출 0.987 / EPS 1.002 · consensus N=4
- **Full window** · N=20 (EPS 20) · 매출 MAPE 6.9% / bias +2.4% · EPS MAPE 17.0% / bias -4.1%
  - RW MAPE 매출 5.6% / EPS 9.9% · MASE 매출 1.211 / EPS 1.939 · Theil U2 매출 1.279 / EPS 1.848 · consensus N=4
- **Pre-break** · N=15 (EPS 15) · 매출 MAPE 7.1% / bias +3.1% · EPS MAPE 18.1% / bias -9.9%
  - RW MAPE 매출 5.3% / EPS 9.4% · MASE 매출 1.320 / EPS 2.262 · Theil U2 매출 1.383 / EPS 2.090 · consensus N=0

## Yahoo consensus (fiscal-aware)

- snapshot as-of: 2026-07-22
- 2026Q2: revenue 5,237.29 · EPS 1.94
- 2026Q3: revenue 5,592.04 · EPS 2.16
- FY2026: revenue 21,129.79 · EPS 7.77
- FY2027: revenue 23,608.08 · EPS 9.01

## 데이터 출처 / 주의

- actuals는 EDGAR companyfacts as-filed 원본 공시 기준 공식 분기 GAAP (10-Q; Q4는 동일 회계연도 10-K 연간 − 9M 10-Q 차감 복원). TXN-1 (2026-07-22). 21개 분기 2021Q1..2026Q1 FY합 항등식+EPS 정합성+연속성 검증 통과.
- 샌드박스 프록시가 data.sec.gov를 프로세스에 403 → web_fetch companyconcept 전사로 파생 캐시(as-filed 원본 accession only) 구축. 호스트에서는 파생 캐시 삭제 후 fetch_companyfacts(97476) 풀 블롭 재수집 권장.
- 과거 EPS는 저장하지 않고 로드 시 파생: net_profit ÷ 분기별 as-filed 희석주식수. 분할 이력 없음(split_history 비어있음). as-filed EPS·accession은 source에 보존.
- 라벨 계약: 12월 결산 캘린더 filer → fiscal FY(N)Qq = model NQq (오프셋 없음).
- 총마진(GM) 분해는 generic 경로에 없음(gross_profit=0 의도적). GM 포인트 추정은 FROZEN 리포트의 애널리스트 레이어(감가상각 vs 가동률 순효과)로 별도 기재.
- Q1'26 참고: 매출 $4,825M, NI $1,545M, EPS $1.68, GM 57.96%, OP마진 37.4%, 감가상각 $541M, capex $676M (10-Q 0000097476-26-000101).

_시나리오 확률: bear 25% / base 50% / bull 25%_
