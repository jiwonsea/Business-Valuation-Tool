# 샌디스크 (Sandisk Corporation) — 실적 전망 (Generic)

- 티커: `SNDK` · 통화: USD (USD_million) · 희석주식수: 158,000,000
- 시드 분기: 2026Q3 (매출 5,950)
- 전망 구간: 2026Q4부터 4개 분기

## 확률가중 분기 전망

| 분기 | 매출 | 영업이익 | 순이익 | EPS(희석) |
|---|---:|---:|---:|---:|
| 2026Q4 | 9,044 | 6,984 | 6,026 | 38.14 |
| 2027Q1 | 10,648 | 8,260 | 7,040 | 44.56 |
| 2027Q2 | 11,430 | 8,762 | 7,488 | 47.39 |
| 2027Q3 | 11,465 | 8,568 | 7,344 | 46.48 |

## 연간 EPS (시나리오별)

| FY | Bear | Base | Bull | 가중 |
|---|---:|---:|---:|---:|
| 2026 | 30.39 | 38.57 | 45.02 | 38.14 |
| 2027 | 69.88 | 140.56 | 202.76 | 138.44 |

## 오프라인 백테스트 (1-step, seasonally-aware)

- **Post-break (headline)** · N=5 (EPS 5) · 매출 MAPE 17.7% / bias -12.3% · EPS MAPE 177.4% / bias -168.8%
  - RW MAPE 매출 22.4% / EPS 1738.8% · MASE 매출 0.859 / EPS 0.817 · Theil U2 매출 0.954 / EPS 0.988 · consensus N=0
- **Full window** · N=10 (EPS 10) · 매출 MAPE 10.8% / bias -4.2% · EPS MAPE 137.5% / bias -72.0%
  - RW MAPE 매출 13.2% / EPS 1020.4% · MASE 매출 0.872 / EPS 0.806 · Theil U2 매출 0.955 / EPS 0.988 · consensus N=0
- **Pre-break** · N=5 (EPS 5) · 매출 MAPE 4.0% / bias +4.0% · EPS MAPE 97.6% / bias +24.7%
  - RW MAPE 매출 4.1% / EPS 302.1% · MASE 매출 1.043 / EPS 0.714 · Theil U2 매출 1.165 / EPS 0.982 · consensus N=0

## Yahoo consensus (fiscal-aware)

- unavailable

## 데이터 출처 / 주의

- 라벨 계약: 6월(52/53주) 결산 → 모델 라벨 NQq = 회계 FY(N)Q(q). 동결 대상 2026Q4 = FY2026 Q4 = 2026-04-04~2026-07-03 ≈ 달력 2026 Q2. 컨센서스·리포트·테스트 모두 회계기준 라벨로 통일(NVDA/MSFT/AAPL형 조인 오프셋 리스크). tests/test_sndk_profile.py에서 명시 검증.
- actuals = EDGAR XBRL companyconcept as-filed (CIK 0002023554). Q4는 FY(10-K) − 9M(Q3 10-Q)로 복원, FY2024Q1은 같은 accession 내 H1 − Q2. WebFetch 수집(샌드박스 httpx는 data.sec.gov 403). 화이트블롭 companyfacts + 바이트 SHA-256은 호스트 후속(00-COMMON.md §7).
- FY 합 항등식 4건 모두 정확 일치: FY2024 매출 1533+1665+1705+1760=6,663 / NI −518−301+27+120=−672 / OP −487−245+65+199=−468. FY2025 매출 1883+1876+1695+1901=7,355 / NI 211+104−1933−23=−1,641 / OP 291+195−1881+18=−1,377. 9M FY2026 매출 2308+3025+5950=11,283 / NI 112+803+3615=4,530.
- EPS는 저장하지 않고 로드 시 파생(net_profit ÷ as-filed 희석주식수, 분할 없음). 파생값이 as-filed와 전 분기 일치: 2026Q3 23.025≈23.03 · 2026Q2 5.147≈5.15 · 2026Q1 0.752≈0.75 · 2025Q4 −0.159≈−0.16 · 2025Q3 −13.331≈−13.33 · 2025Q1 1.455≈1.46.
- ⚠️ 표본 부족 + 레짐 브레이크: 2025-02-21 WDC 분사. 완전 독립 분기는 2025Q3~2026Q3의 5개뿐(regime_break_quarter=2025Q3). 2025Q2 이전은 SNDK 자체 accession의 카브아웃/결합 비교치다(제3자 재구성 아님). 1-step 백테스트의 나이브 RW·계절 슬롯이 빈약 → MASE/Theil은 방향 참고용, LOW_SKILL 표기 대상.
- ⚠️ 하이퍼사이클에서 나이브 RW는 강한 벤치마크다(DELTA §2.1). backtest_methodology는 의도적으로 사후지식 없는 중앙값 앵커라 GAAP 영업이익률이 4분기 만에 +0.9%→+69.1%로 움직인 구간을 추종할 수 없다. MASE/Theil이 1을 넘으면 숨기지 말고 기록한다.
- ⚠️ backtest↔forward 결합: backtest_methodology 블록이 있으므로 backtest_generic은 base가 아니라 이 블록을 소비한다(generic_cli.py:135-145). 따라서 forward 시나리오를 고쳐도 백테스트는 움직이지 않는다 — GEV/TXN에서 발화한 _slot 계절 오정렬의 구조적 차단.
- shape(계절 벡터) 가중치를 사실상 0으로 낮춘 판단은 YAML 파라미터가 아니라 이 주석과 FROZEN §(f)에만 존재한다. 종목 고유 하드코딩으로 흐를 위험이 있어 Codex 6축 §6에 정면으로 부친다(프로파일 레벨 `seasonality_weight` 파라미터로 표현 가능한가).
- below-OP = Flash Ventures(키옥시아 합작 팹) 지분법 손익 + FX + 평가손익. ⚠️ 별도 지분법 손익계산서 라인은 존재하지 않는다 — 10-Q 확인 결과 SanDisk는 Kioxia Holdings 지분을 직접 보유하지 않고, Flash Ventures(Flash Partners/Alliance/Forward) 지분 $201M + 대여금 $483M을 보유하며 지분법 손실은 'Other income (expense), net'에 섞여 들어간다(현금흐름표 add-back 'Equity loss in investees, net of dividends received' 9M $58M). 리스 보증 ¥158B(≈$993M)은 부외. R2에 따라 base 0 · 광폭 밴드.
- 가이던스(2026-04-30 8-K EX-99.1): 매출 $7,750~8,250M · GAAP GM 78.9~80.9% · GAAP opex $523~558M · GAAP 이자·기타순 +$12~32M · 비GAAP 세금 $775~875M · 비GAAP 희석 EPS $30.00~33.00 · 희석주식수 ~158M. GAAP EPS 가이던스는 제시되지 않았다(N/A).
- 컨센서스(비GAAP 기준, as-of 2026-07-30~08-03): 매출 $8.30B(Zacks, 2026-08-03) ~ $8.42B(TipRanks, 애널리스트 17인, 2026-07-31); 비GAAP 희석 EPS $34.24(Zacks, 2026-08-03, 30일간 +2.8% 상향) ~ $34.67(FactSet/TipRanks) ~ $34.80(TipRanks 2026-08-04). 유일한 GAAP 컨센은 Hudson Labs $33.17(2026-07-13). 전년동기(FY25Q4) 매출 $1,901M · GAAP EPS −$0.16 · 비GAAP EPS $0.29.
- R5 브릿지: 본 엔진 산출은 GAAP. FQ4 비GAAP 제외항목은 가이던스 각주 기준 SBC(GM $4~6M + opex $43~58M) + 종속기업 지분매각 대가 현재가치 할인 상각 $2M = 합계 $45~62M(세전, 중간 ~$53.5M) → 희석 158M주 기준 약 +$0.34/주. 즉 비GAAP EPS ≈ GAAP EPS + $0.30~0.35 (FQ3 실측 갭 $0.38, FQ2 $1.05).
- weighted_avg_diluted 158M은 회사 가이던스치. $6B 자사주(2026-04-30 이사회 승인, 만료 없음)는 집행 실적이 아직 공시된 바 없어 감소 효과를 반영하지 않았다. 실제 희석주식수는 145→149→156→157로 계속 상승 중이라 자사주 효과가 나타나도 상쇄될 수 있다.

_시나리오 확률: bear 25% / base 50% / bull 25%_
