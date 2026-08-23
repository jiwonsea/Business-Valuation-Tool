# 알파벳(구글) (Alphabet Inc.) — 실적 전망 (Generic)

- 티커: `GOOGL` · 통화: USD (USD_million) · 희석주식수: 12,238,000,000
- 시드 분기: 2026Q1 (매출 109,896)
- 전망 구간: 2026Q2부터 4개 분기

## 확률가중 분기 전망

| 분기 | 매출 | 영업이익 | 순이익 | EPS(희석) |
|---|---:|---:|---:|---:|
| 2026Q2 | 115,940 | 40,041 | 34,143 | 2.79 |
| 2026Q3 | 121,765 | 42,087 | 35,892 | 2.93 |
| 2026Q4 | 129,440 | 44,786 | 38,198 | 3.12 |
| 2027Q1 | 135,026 | 46,757 | 39,883 | 3.26 |

## 연간 EPS (시나리오별)

| FY | Bear | Base | Bull | 가중 |
|---|---:|---:|---:|---:|
| 2026 | 7.62 | 8.81 | 10.14 | 8.84 |
| 2027 | 2.68 | 3.24 | 3.87 | 3.26 |

## 오프라인 백테스트 (1-step, seasonally-aware)

- N=7 · 매출 MAPE 5.2% (naive RW 6.5%) · 매출 bias +1.6%
- EPS MAPE 12.0% (naive RW 17.6%) · EPS bias -11.5%
- RW MAPE 매출 6.5% / EPS 17.6% · MASE 매출 0.796 / EPS 0.774 · Theil U2 매출 0.952 / EPS 0.918 · consensus N=0

## Yahoo consensus (fiscal-aware)

- unavailable

## 데이터 출처 / 주의

- actuals는 EDGAR companyfacts as-filed 원본 공시 기준 공식 분기 GAAP (10-Q; Q4는 동일 회계연도 10-K 연간 − Q3 10-Q 9M 차감 복원). GOOGL-1 (2026-07-22).
- 과거 EPS는 저장하지 않고 로드 시 파생: net_profit ÷ 분기별 as-filed 희석주식수 (split_history 없음, 창 전체가 20:1 분할 이후). as-filed EPS·accession은 source에 보존.
- 창은 2024Q2부터: 이전 분기 10-Q는 3개월 희석주식수를 same-accession으로 태깅하지 않아 무결성 규칙상 재구축 불가.
- FY2025 검증: 분기 매출 합 = 402,837 ($402,836M 10-K과 라운딩 오차 1), 순이익 합 = 132,170 (일치).
- 2026Q1 순이익 $62.6bn(순마진 57%)은 OI&E 비상장 지분 평가이익이 크게 반영된 값 — headline EPS 왜곡 주의. generic OP 기반 EPS는 이 일회성 이익을 반영하지 않음(영업 EPS proxy).

_시나리오 확률: bear 25% / base 50% / bull 25%_
