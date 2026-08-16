# IBM 2026 Q2 실적 예측 — 프린트-전 동결 (FROZEN)

> **이 문서는 IBM 2026 Q2 실적 발표 이전에 동결된 예측 기록이다.** 발표 후 사후확증을 방지하기 위한 ex-ante 증빙.

| 항목 | 값 |
|---|---|
| **동결 시각 (UTC)** | 2026-07-22T06:30:43Z |
| **동결 시각 (KST)** | 2026-07-22 15:30:43 KST |
| **발표 예정** | 2026-07-22 미국 장 마감 후 (≈ KST 2026-07-23 새벽) → 동결은 발표 **전** |
| **git HEAD (base)** | `9d7200ca62af5b421cfc8db985ffa09e85fadbb1` (branch `main`) |
| **신규 파일 (미커밋)** | `profiles/ibm.generic.yaml`, `tests/test_ibm_generic.py` — 호스트에서 커밋 예정 |
| **프로파일 sha256** | `cc7921b36e013648ab935f220b51213445799cda28999ee259845794a97667ee` (`profiles/ibm.generic.yaml`) |
| **엔진** | `generic_cli.py` (top-down generic 경로) · seed 2026Q1 (매출 $15,917M, GAAP EPS $1.28) |
| **통화/단위** | USD, millions (EPS는 USD/주) |

---

## 🛠 ERRATUM (2026-07-22, 동결 후 정정 — Codex canonical 검증)

발표 **전** 동결 직후, 호스트 Codex가 `build_generic_actuals.py`(EDGAR whole-blob canonical)로 재생성해 **데이터 오기 1건**을 확인했다. 샌드박스 WebFetch 요약 단계에서 FY2024 매출이 $1M 잘못 전사됐다.

| 항목 | 동결 원본 (cc7921b3…) | 정정 (canonical) |
|---|--:|--:|
| 2024Q4 매출 | 17,553 | **17,554** |
| FY2024 매출(파생 합) | 62,753 | **62,754** |
| 프로파일 sha256 | `cc7921b3…67ee` | **`b727f85c…72fb`** |

- **헤드라인 예측 불변**: 예측은 seed(2026Q1) 기반 → (a)~(f) 수치·가중 Q2 매출 $17,524.6M·GAAP EPS $2.352·operating ~$2.95 **전부 그대로**. 2024Q4는 백테스트에만 관여, $1M(0.006%)라 MAPE 무변(매출 25.9%/EPS 165.9% Codex 재현).
- FY 합계 항등식은 정정 후에도 정확 일치(FY2024 = 62,754). 테스트 `FY_REVENUE[2024]` 동반 정정 → `pytest tests/test_ibm_generic.py` 5/5 green.
- 원 동결 sha(cc7921b3)는 감사추적을 위해 상단 메타표에 보존. **커밋 대상 = 정정본(b727f85c).**

---

## ⚠️ 동결 무결성 주의 (반드시 먼저 읽을 것)

이 예측은 **순수 ex-ante(발표 전)** 를 목표로 한다. 단, 리서치 과정에서 **2026-07-14경 IBM 부정적 사전신호(주가 급락) 정황**이 2차 매체(aggregator)들에서 관측됐다. 사실 여부와 무관하게, 본 동결은 **그 신호를 예측 입력에서 의도적으로 배제**하고 오로지 (1) 우리 모델과 (2) **프린트-전 컨센서스(≈ 7/13 vintage)** 만으로 작성했다. 즉 "정답을 보고 맞춘" 것이 아니라 모델의 사전 예측력을 그대로 박제한다. → 만약 7/14 사전신호가 실제였다면 순수 ex-ante 창은 **일부 훼손**된 것이며, 사후 채점 시 이 점을 감안해 "예측 신호"가 아니라 "정황 오염된 사후 귀인"으로 라벨링해야 한다.

---

## (a) 총매출·희석 EPS 포인트 추정 + 시나리오

확률: **bear 0.30 / base 0.50 / bull 0.20** (스윙 팩터가 하방으로 비대칭 → bear 가중 상향).
EPS는 **GAAP(모델 산출)** 와 **operating(비GAAP, 컨센 기준)** 을 병기. operating = GAAP + 브릿지(취득무형 상각·연금·workforce; +$0.55~0.63/분기, Confluent/HashiCorp로 확대).

### 2026 Q2 (채점 대상 분기)

| 시나리오 | 매출 ($M) | YoY | GAAP EPS | operating EPS(비GAAP) | 근거 |
|---|---:|---:|---:|---:|---|
| Bear (0.30) | 17,111 | +0.8% | 2.08 | ~2.63 | z17 조기 롤오버, Consulting 위축, TP 침식 |
| **Base (0.50)** | **17,588** | **+3.6%** | **2.40** | **~3.00** | Software 두자릿수 지속, Infra 감속, FX 순풍 |
| Bull (0.20) | 17,986 | +5.9% | 2.66 | ~3.29 | Software 재가속 + z17 견조 + FX 확대 |
| **확률가중** | **17,525** | **+3.2%** | **2.35** | **~2.95** | — |

- **YoY 기준선**: 2025 Q2 매출 $16,977M · GAAP EPS $2.31 · operating EPS $2.80.
- 단위·통화: **USD millions / USD per diluted share**. forward 희석주식수 955.0M 고정.

### forward 4개 분기 (확률가중, 엔진 산출)

| 분기 | 매출 ($M) | 순이익(GAAP, $M) | GAAP EPS | operating EPS(≈+브릿지) |
|---|---:|---:|---:|---:|
| 2026Q2 | 17,525 | 2,246 | 2.35 | ~2.95 |
| 2026Q3 | 16,695 | 1,794 | 1.88 | ~2.45 |
| 2026Q4 | 19,715 | 3,704 | 3.88 | ~4.5 |
| 2027Q1 | 16,152 | 1,279 | 1.34 | ~1.9 |

- **FY2026 GAAP EPS(참고)** ≈ Q1 실적 $1.28 + Q2~Q4 예측 $8.11 = **~$9.4**. operating FY2026는 가이던스-정합 **~$11.7–11.9** 범위(연간 브릿지는 분기 합과 다름 — Q4 세금 이산으로 GAAP>operating 경향).
- 표의 "operating EPS"는 리포트 단계 브릿지 적용값(엔진은 GAAP만 산출). Q3/Q4/Q1 브릿지는 개략치.

---

## (b) 세그먼트별 매출·마진 예측 — 비트/미스가 날 지점

generic 엔진은 세그먼트를 분해하지 않는다(총매출×마진 top-down). 아래는 모델-외부 **판단 기반** 세그먼트 콜(2025 Q2 대략 앵커 대비). 총합은 base 총매출과 정합.

| 세그먼트 | 2026Q2 예측($B, base) | YoY(reported) | 코멘트 / 스윙 |
|---|---:|---:|---|
| **Software** | ~8.0 | +8~10% | 성장·마진 견인. Red Hat·Data(watsonx) 두자릿수 유지. **Transaction Processing(메인프레임 부착 SW)** 이 스윙 — Q1 +2% CC로 이미 감속. |
| **Consulting** | ~5.45 | +2~4% (CC ~보합) | 매크로/재량지출 약세, genAI 사이닝이 backlog엔 잡히나 매출 전환 지연. 상방 제한. |
| **Infrastructure** | ~3.85 | **−4~−8%** | **최대 스윙 라인.** z17 메인프레임이 2025 강한 램프를 lap → YoY 마이너스 전환. IBM Z 감속 폭이 비트/미스를 좌우. |
| **Financing** | ~0.20 | ~보합 | 경미, 무의미. |

- **마진**: base는 계절 GAAP 순마진 Q2 ~13%(2025 Q2 12.9%에서 소폭 개선; operating leverage + 자사주). Software 믹스 상승은 마진 우호, Infra 감속은 중립.
- **핵심 (b)·(d) 질문 = "Software 두자릿수 성장 지속?"**: base는 **reported 두자릿수 근접(+8~10%), CC는 한 자릿수 후반**으로 본다. TP 감속이 두자릿수 이탈 리스크의 진원.

---

## (c) 가이던스 방향 예측

- **FY2026 매출 성장 가이던스(>5% 상수통화)**: base **유지**. bear에선 하향 리스크(특히 CC 또는 Consulting).
- **FY2026 FCF 가이던스 ~$15.7B**: IBM 서사의 중심. base **유지**, bull은 소폭 상향 뉘앙스. FCF는 EPS보다 주가 반응이 큰 변수.
- **FX**: 경영진은 FY2026 ~+0.5~1.0%p reported 순풍을 반영. 달러 추가 약세면 reported 상방이나 **CC(underlying)와의 괴리 확대** → 질적으로는 경계 신호.
- 주의: IBM은 분기 가이던스를 주지 않음(연간 가이던스). 따라서 (c)의 채점은 **FY 가이던스 상향/유지/하향** 기준.

---

## (d) 컨센서스 대비 우리 위치

프린트-전 컨센(≈7/13): **매출 ~$17.85B**(Zacks 저단 $17.59B) · **operating EPS ~$3.01**.

| 지표 | 컨센(프린트-전) | 우리 base | 우리 가중 | 위치 | 확신도 |
|---|---:|---:|---:|---|---|
| 매출 | ~$17.85B | $17.59B | $17.53B | **하회** (−약 1.8%) | 중 |
| operating EPS | ~$3.01 | ~$3.00 | ~$2.95 | base ≈부합 / 가중 소폭 하회 | 중 |
| GAAP EPS | (별도 컨센 희소) | $2.40 | $2.35 | — | 중 |

- **정의 차이 명시**: 우리 엔진은 **GAAP 순이익/EPS**를 예측한다. 컨센 $3.01은 **operating(비GAAP)**. 직접 비교는 **+$0.60 브릿지 적용 후에만** 유효.
- **하회 근거**: (1) Infrastructure z17 YoY 감속, (2) Consulting 매크로 약세·딜 슬리피지, (3) AI 백로그($12.5B+)→매출 전환 지연. **상쇄**: Software 강세 + FX 순풍.
- 이게 EFE의 존재 이유(consensus↔intrinsic gap): 이번엔 **매출·operating EPS 모두 컨센 소폭 하회**하는 차별화된 뷰.

---

## (e) 컨퍼런스콜 Q&A 예상 토픽

- **메인프레임/z17 사이클 위치**와 2H 궤적(Infra 마이너스 전환 방어 논리).
- **Software TP 감속** 및 **watsonx/genAI 매출 전환**($12.5B+ 누적 book of business의 top-line 기여).
- **Consulting 수요환경**·딜 슬리피지·backlog 전환율.
- **Confluent/HashiCorp** 기여와 **희석(~$600M FY 드래그)**.
- **FCF 가이던스·FX** 가정, **operating leverage/마진** 확장 지속성.
- **자본배분**(31년 연속 배당 인상 방어).

---

## (f) 우리를 틀리게 만들 스윙 팩터 (사전등록)

1. **Infrastructure / 메인프레임 z17 타이밍 (최우선).** Q2 IBM Z YoY가 예상보다 급락(강한 comp 부담)하거나 반대로 여전히 강세면 매출이 base에서 크게 이탈. 우리 base는 이미 Infra YoY 마이너스를 반영 → **양방향 스윙**.
2. **below-OP 블록 (GAAP↔operating 브릿지).** 연금(2024Q3 −$2.7B 정산 charge 선례), workforce rebalancing, 취득무형 상각, **이산 세금항목**(2025Q4 사례)이 GAAP EPS를 크게 흔든다. 우리는 GAAP를 예측하므로 **이 블록이 최대 오차원**이며, operating 브릿지 크기 오판도 여기서 발생.
- 보조: **FX**(달러 약세=reported 순풍이나 CC 괴리 확대), **Consulting 재량지출** 급랭.

---

## 방법론·백테스트 주의 (채점 시 참조)

- **엔진 내장 generic 백테스트가 IBM에서 왜곡됨.** `generic_cli.backtest_generic`의 `_slot`은 계절 성장벡터를 **캘린더-분기**로 슬롯 매칭하는데, IBM은 12월 결산이고 forward window가 **Q2에서 시작** → `project_scenario`의 **positional(시드부터 순차)** 순서와 **1분기 회전 불일치**. 계절성이 강한 IBM에서 이 잠복 버그가 발화해 매출 MAPE가 25.9%로 뻥튀기(엔진 리포트값). NVDA는 성장이 완만해 은폐됨.
- **정렬 교정한 독립 1-step 백테스트(캘린더-정합)**: **매출 MAPE 1.4% (naive RW 13.0%)**, **EPS MAPE 62.2% (RW 138.3%)**. 매출은 RW 대비 뚜렷한 skill. EPS 절대 MAPE가 높은 건 IBM **GAAP EPS 자체의 변동성**(2024Q3 순손실·Q4 세금 이산으로 분모 급변) — 구조적, 리스크밴드 대상.
- **NOTICED BUT NOT TOUCHING**: `generic_cli.py::backtest_generic` `_slot` (Dec-filer × Q2-window 오정렬). 공유 코드라 이번 세션 미수정(호스트 워크스트림; NVDA/TSLA 회귀 위험). forward **예측치는 positional로 올바르며** 본 동결의 헤드라인 수치는 정확.
- **데이터 무결성**: actuals는 EDGAR companyfacts as-filed 원본(CIK 51143; Revenues/NetIncomeLoss/DilutedShares). Q1–Q3 3M 직접, Q4 = FY(10-K) − 9M. **FY 합계 항등식(매출·순이익) FY2023/24/25 정확 일치**, as-filed EPS 정합 전 분기 green. 13개 연속 분기(2023Q1–2026Q1). 샌드박스 data.sec.gov 403 → WebFetch companyconcept 슬라이스 + 수기 FY 교차검증. 호스트에서 `build_generic_actuals.py --cik 51143 --fye-month 12`로 정규 캐시+자동검증 재생성 권장.
- **검증**: `pytest tests/test_ibm_generic.py` 6/6 green(연속성·FY 항등식·EPS 파생 정합·백테스트 non-refuse). 메모리 경로(9Q SK Hynix) 파일 **무수정** → sha256 불변식 구성상 보존(호스트 재확인).

---

## 사후 채점 체크리스트 (발표 후)

1. actual 확보(10-Q / IR): 매출·GAAP EPS·operating EPS·세그먼트.
2. FROZEN ↔ actual: 매출·EPS MAPE, bias 부호. 세그먼트별(특히 Infrastructure).
3. 4-lever generic 귀인: 매출 / (reduced-form)마진 / OP→NI(below-OP 블록) / 주식수.
4. `skill_metrics` MASE/Theil + operating EPS 컨센 surprise 방향 적중.
5. (f) 스윙 팩터 발화 여부: z17? below-OP? FX? → YAML 앵커 수정 가능한 체계적 편향인가, 구조적(리스크밴드)인가.
6. `HANDOFF_CODEX_efe_q2_2026_ibm.md` 기록. 라벨: **"사후 귀인 — 예측 신호 아님"** (+ 7/14 정황 오염 감안).
