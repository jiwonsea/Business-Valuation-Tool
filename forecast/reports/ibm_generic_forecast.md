# IBM (International Business Machines) — 실적 전망 (Generic)

- 티커: `IBM` · 통화: USD (USD_million) · 희석주식수: 955,000,000
- 시드 분기: 2026Q1 (매출 15,917)
- 전망 구간: 2026Q2부터 4개 분기

## 확률가중 분기 전망

| 분기 | 매출 | 영업이익 | 순이익 | EPS(희석) |
|---|---:|---:|---:|---:|
| 2026Q2 | 17,525 | 2,754 | 2,246 | 2.35 |
| 2026Q3 | 16,695 | 2,216 | 1,794 | 1.88 |
| 2026Q4 | 19,715 | 4,485 | 3,704 | 3.88 |
| 2027Q1 | 16,152 | 1,604 | 1,279 | 1.34 |

## 연간 EPS (시나리오별)

| FY | Bear | Base | Bull | 가중 |
|---|---:|---:|---:|---:|
| 2026 | 7.01 | 8.29 | 9.31 | 8.11 |
| 2027 | 1.10 | 1.37 | 1.63 | 1.34 |

## 오프라인 백테스트 (1-step, seasonally-aware)

- N=12 · 매출 MAPE 25.9% (naive RW 13.0%) · 매출 bias +3.3%
- EPS MAPE 165.9% (naive RW 138.3%) · EPS bias -73.4%
- RW MAPE 매출 13.0% / EPS 138.3% · MASE 매출 1.980 / EPS 1.013 · Theil U2 매출 1.861 / EPS 0.990 · consensus N=0

## Yahoo consensus (fiscal-aware)

- unavailable

## 데이터 출처 / 주의

- actuals=EDGAR companyfacts as-filed 원본 공식 분기 GAAP (CIK 0000051143; 10-Q 3M; Q4=10-K FY − 9M, 동일 회계연도 원본). FY 합계 항등식(매출·순이익) FY2023/24/25 정확 일치 검증. EFE Q2-2026 배치 2026-07-22.
- 과거 EPS 미저장·로드 시 파생: net_profit ÷ 분기별 희석주식수(무분할). as-filed EPS·accession은 source에 보존.
- 라벨 계약: 12월 결산 → fiscal FY(N)Qq = model NQq (오프셋 없음). 컨센서스 조인에 회계연도 시프트 불필요.
- op_margin은 GAAP 순이익 계절성을 재현하는 축약형(reduced-form) 마진이며, IBM 보고 비GAAP operating margin이 아님. 엔진은 GAAP 순이익/EPS를 산출; GAAP→operating(비GAAP) 브릿지(+~$0.60/분기: 취득무형 상각·연금·workforce; Confluent/HashiCorp로 확대)는 FROZEN 리포트에서 적용.
- 2024Q3 순손실(-330M)은 ~$2.7B 연금 정산 charge에 기인한 below-OP 일회성 — generic이 예측 못하는 구조적 항목의 대표 사례(리스크밴드 대상).
- 샌드박스 data.sec.gov 403 → WebFetch로 companyconcept 슬라이스 수집, FY 항등식 수기 교차검증. 호스트에서 build_generic_actuals.py --cik 51143 --fye-month 12 로 정규 캐시+자동검증 재생성 권장.

_시나리오 확률: bear 30% / base 50% / bull 20%_
