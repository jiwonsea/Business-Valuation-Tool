# 지이 버노바 (GE Vernova Inc.) — 실적 전망 (Generic)

- 티커: `GEV` · 통화: USD (USD_million) · 희석주식수: 272,000,000
- 시드 분기: 2026Q1 (매출 9,339)
- 전망 구간: 2026Q2부터 4개 분기

## 확률가중 분기 전망

| 분기 | 매출 | 영업이익 | 순이익 | EPS(희석) |
|---|---:|---:|---:|---:|
| 2026Q2 | 10,717 | 955 | 856 | 3.15 |
| 2026Q3 | 11,741 | 1,051 | 942 | 3.46 |
| 2026Q4 | 13,221 | 1,189 | 1,065 | 3.92 |
| 2027Q1 | 10,295 | 931 | 834 | 3.07 |

## 연간 EPS (시나리오별)

| FY | Bear | Base | Bull | 가중 |
|---|---:|---:|---:|---:|
| 2026 | 6.00 | 10.81 | 14.48 | 10.53 |
| 2027 | 1.62 | 3.14 | 4.38 | 3.07 |

## 오프라인 백테스트 (1-step, seasonally-aware)

- N=8 · 매출 MAPE 20.3% (naive RW 14.2%) · 매출 bias +3.1%
- EPS MAPE 190.8% (naive RW 241.0%) · EPS bias -82.3%
- RW MAPE 매출 14.2% / EPS 241.0% · MASE 매출 1.479 / EPS 1.175 · Theil U2 매출 1.787 / EPS 1.255 · consensus N=4

## Yahoo consensus (fiscal-aware)

- snapshot as-of: 2026-07-22
- 2026Q2: revenue 10,769.50 · EPS 3.18
- 2026Q3: revenue 11,953.19 · EPS 4.31
- FY2026: revenue 45,483.06 · EPS 30.69
- FY2027: revenue 51,907.37 · EPS 24.43

## 데이터 출처 / 주의

- actuals는 EDGAR companyfacts as-filed 원본 공시 기준 공식 분기 GAAP (CIK 1996810; 10-Q, Q4는 동일 회계연도 10-K 연간 − Q3 10-Q 9M 차감 복원). WebFetch로 수집(샌드박스 httpx는 data.sec.gov 403). 화이트블롭 재빌드(scripts/build_generic_actuals.py)는 호스트 후속.
- 과거 EPS는 저장하지 않고 로드 시 파생: net_profit ÷ 분기별 as-filed 희석주식수(분할 없음). as-filed EPS·accession은 source에 보존. 파생 EPS는 as-filed와 전 분기 일치(2024Q2 4.65·2025Q2 1.86·2025Q3 1.64·2025Q1 0.91·2024Q1 -0.47·2024Q3 -0.35; Q4 파생 2024Q4 1.72≈FY−9M 1.73).
- FY 합 항등식 검증: FY2024 매출 34,936≈34,935(+$1M 반올림)·NI −130+1294−96+484=1,552 정확. FY2025 매출 8032+9111+9969+10956=38,068 정확·NI 254+514+452+3664=4,884 정확.
- 라벨 계약: 12월 결산 → fiscal FYNQq = model NQq (오프셋 없음).
- ⚠️ 표본 부족: 독립 상장 후 ~8분기(2024Q2~)뿐. 1-step 백테스트의 나이브 RW·계절 슬롯이 빈약 → skill(MASE/Theil)은 방향 참고용, 낮은 신뢰도. regime_break=2024Q2.
- ⚠️ 세금 왜곡: 2025Q4·2026Q1 reported NI는 일회성 이연법인세 valuation allowance 환입으로 부풀려짐(2026Q1 NI $4,745M vs 영업이익 $179M). 파생 EPS(2025Q4 13.4·2026Q1 17.4)는 실제이나 반복 불가 → 백테스트 EPS 오차의 주범(구조적, 리스크밴드行). 전방 세율은 정상화(~22%) 가정.
- 컨센서스(Zacks/Yahoo, as-of 2026-07-15경): 2026Q2 매출 $10.77B(+18.2% YoY)·GAAP 희석 EPS $3.17(+70.4% YoY). 세그먼트: Power $5.54B(+16.5%)·Wind $1.90B(-15.4%)·Electrification $3.45B(+56.8%). analyst 수 미표기.

_시나리오 확률: bear 25% / base 50% / bull 25%_
