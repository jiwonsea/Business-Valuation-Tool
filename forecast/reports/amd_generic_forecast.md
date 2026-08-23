# AMD (Advanced Micro Devices, Inc.) — 실적 전망 (Generic)

- 티커: `AMD` · 통화: USD (USD_million) · 희석주식수: 1,658,000,000
- 시드 분기: 2026Q1 (매출 10,253)
- 전망 구간: 2026Q2부터 4개 분기

## 확률가중 분기 전망

| 분기 | 매출 | 영업이익 | 순이익 | EPS(희석) |
|---|---:|---:|---:|---:|
| 2026Q2 | 11,600 | 2,100 | 1,838 | 1.11 |
| 2026Q3 | 12,456 | 2,315 | 2,032 | 1.23 |
| 2026Q4 | 13,107 | 2,513 | 2,209 | 1.33 |
| 2027Q1 | 12,844 | 2,274 | 2,008 | 1.21 |

## 연간 EPS (시나리오별)

| FY | Bear | Base | Bull | 가중 |
|---|---:|---:|---:|---:|
| 2026 | 2.27 | 3.54 | 5.32 | 3.67 |
| 2027 | 0.63 | 1.16 | 1.90 | 1.21 |

## 오프라인 백테스트 (1-step, seasonally-aware)

- **Post-break (headline)** · N=3 (EPS 3) · 매출 MAPE 1.1% / bias -0.7% · EPS MAPE 12.8% / bias -12.8%
  - RW MAPE 매출 9.0% / EPS 18.7% · MASE 매출 0.125 / EPS 0.688 · Theil U2 매출 0.106 / EPS 0.647 · consensus N=0
- **Full window** · N=8 (EPS 8) · 매출 MAPE 1.2% / bias +0.0% · EPS MAPE 38.0% / bias -4.0%
  - RW MAPE 매출 8.1% / EPS 35.7% · MASE 매출 0.150 / EPS 0.994 · Theil U2 매출 0.126 / EPS 1.169 · consensus N=0
- **Pre-break** · N=5 (EPS 5) · 매출 MAPE 1.3% / bias +0.5% · EPS MAPE 53.1% / bias +1.3%
  - RW MAPE 매출 7.6% / EPS 46.0% · MASE 매출 0.174 / EPS 1.166 · Theil U2 매출 0.156 / EPS 1.354 · consensus N=0

## Yahoo consensus (fiscal-aware)

- unavailable

## 데이터 출처 / 주의

- actuals는 EDGAR companyfacts as-filed 원본 공시 기준 공식 분기 GAAP (10-Q; Q4는 동일 회계연도 10-K 연간 − 9M 10-Q 차감 복원). AMD-1 (2026-08-05 KST). 9개 분기 2024Q1..2026Q1 FY합 항등식(매출·순이익)+EPS 정합성(9/9 센트 단위 일치)+연속성 검증 통과.
- 샌드박스 프록시가 data.sec.gov를 프로세스에 403 → WebFetch companyconcept 전사(as-filed 원본 accession only). WebFetch는 markdown 변환본이라 원문 바이트 SHA-256 계산 불가 — START-COMMON §7의 샌드박스 예외에 따라 '바이트 보존 미완 — 호스트 필요'로 명시. 호스트에서 fetch_companyfacts(2488) 풀 블롭 재수집 권장.
- 과거 EPS는 저장하지 않고 로드 시 파생: net_profit ÷ 분기별 as-filed 희석주식수. 분할 이력 없음(split_history 비어있음, 마지막 분할 2000년). as-filed EPS·accession은 source에 보존.
- 라벨 계약: 12월 결산(12월 마지막 토요일) 캘린더 filer → fiscal FY(N)Qq = model NQq (오프셋 없음).
- 2024Q4·2025Q4 희석주식수는 파생값이다(AMD는 10-K에 YTD 가중평균만 태그). 4×FY−3×9M으로 복원했고, 2025Q4는 Q4'25 보도자료 표의 1,649M로 교체, 2024Q4의 1,634M은 보고된 GAAP EPS $0.29를 정확히 재현한다.
- 총마진(GM) 분해는 generic 경로에 없음(gross_profit 미모델링). non-GAAP GM 포인트 추정과 GAAP↔non-GAAP 브릿지는 FROZEN 리포트의 애널리스트 레이어에 별도 기재(R5 계약).
- ⚠ SF3 미해결: OpenAI 전략적 워런트(보도 기준 최대 ~1.6억주)의 회계처리를 2026Q1 10-Q(0000002488-26-000076)에서 확인하지 못했다. contra-revenue인지 비용인지 자본거래인지에 따라 매출 레버 또는 주식수 레버에 직접 타격한다. 추정으로 메우지 않고 '미확인'으로 두고 밴드에 반영했다.
- ⚠ SF4 기저왜곡: 전년 동기 2025Q2는 MI308 중국 수출규제로 약 $800M 재고·관련 충당을 인식해 GAAP 영업손실 −$134M, GAAP GM 39.8%를 기록했다. 따라서 2026Q2의 YoY 성장률·마진 개선폭은 기저효과로 부풀려 보인다 — 반드시 QoQ를 병기할 것.
- 2026Q1 참고: 매출 $10,253M, GAAP GM 52.82%, GAAP OP $1,476M(14.40%), 이자비용 −$37M, 기타수익 +$165M, 세전 $1,604M, 법인세 $238M(ETR 14.84%), 지분법이익 $6M, 중단영업 +$11M, 순이익 $1,383M, 희석 EPS $0.84, 희석주식수 1,650M. non-GAAP: GP $5,685M(55.4%), opex $3,145M, OP $2,540M, EPS $1.37. 세그먼트 매출 DC $5,775M / Client $2,885M / Gaming $720M / Embedded $873M, 세그먼트 OP DC $1,599M / Client+Gaming $575M / Embedded $338M (10-Q 0000002488-26-000076 · 8-K EX-99.1 q12026991.htm).
- 중단영업(ZT Manufacturing Business 매각, 10-Q Note 5)이 below-OP 노이즈원으로 추가됐다: 2025Q4 −$109M, 2026Q1 +$11M. generic 경로는 이를 모델링하지 않으므로 밴드로만 흡수된다.

_시나리오 확률: bear 25% / base 50% / bull 25%_
