# PLAN — tax/finance 진단·분리 (verdict #2, 실체적 2순위)

> **zero-context 핸드오프 plan.** 작성 2026-06-19 (세션 C 해석 결과). 구현은 **사용자 승인 후 별도 focused 세션**에서.
> 코드/주석/식별자 = 영어, 사용자용 출력 = 한국어. 선행: `HANDOFF_backtest_diag.md` Verdict #2 + 세션 C(−10.55% bias 실측), `engine/tax_finance.py`(현 OP→NI 전환), CLAUDE.md(overlay 레이어 구상).

---

## 0. 한 줄 요약

세션 C가 확인한 모델의 **유일한 계통적 약점 = −10.55% EPS bias**(8분기 중 7분기 과소예측). ① attribution상 이 bias는 **below-the-line(tax/finance)**에 집중(평균 −7.7%, 분기 스윙 −29.1%~+16.2%). 고정 `effective_tax_rate=0.20` + 단순 `net_interest_pct`가 실측 FX 평가손익·지분법·일회성을 못 잡는다. 본 PLAN은 **진단 우선**(어느 below-the-line 항목이 bias를 만드는지 분해) → **고정세율과 변동항목 분리** → **overlay/오차밴드** 후보 평가. 점추정 미세조정으로 풀리는 문제가 아닐 수 있음을 전제.

## 1. 왜 (데이터 근거, 세션 C 확정)

- gross-margin off-by-one 수정(세션 B) 후 EPS bias가 −0.24%→−10.55%로 **드러났다**(두 버그의 상쇄 가짜신호 제거). 이건 회귀가 아니라 정직해진 상태.
- 세션 C: MASE/Theil로 모델은 RW를 이김(EPS 0.49/0.51) — **그러나 MASE는 dispersion-상대 지표라 단방향 level bias를 거의 벌하지 않는다.** RW가 워낙 나빠(EPS MAPE 44.9%) biased 모델도 이긴다. 즉 "RW 이김"은 bias 면죄부가 **아니다**. 컨센도 이기지만(skill_score +0.48) 부분적으로 컨센이 더 lowball한 결과 — 모델 자체의 −10.55%는 별개 개선 여지.
- ① attribution 분기별 tax/finance 기여(EPS err 분해, HANDOFF 표):

  | Q | tax/fin 기여 |
  |---|---:|
  | 2024Q1 | +16.2% |
  | 2024Q2 | +3.3% |
  | 2024Q3 | −4.6% |
  | 2024Q4 | **−21.1%** |
  | 2025Q1 | **−28.3%** |
  | 2025Q2 | +3.1% |
  | 2025Q3 | **−29.1%** |
  | 2025Q4 | −1.2% |
  | 평균 | **−7.7%** |

  → 평균은 −7.7%지만 **분기 스윙이 최대 원천**. 큰 음(−) 분기(2024Q4·2025Q1·2025Q3)가 −10.55% 평균 bias를 끌어내림.

## 2. 스코프 가드레일

- **진단 우선, 수정은 진단이 지목한 항목만.** 세션 C와 동일 철학: read-only 분해 → driver 격리 → 그 다음 수정.
- **가정 수치(effective_tax_rate·net_interest_pct 등) 변경은 초안·제안까지만. 확정·소유 = 사용자**(CLAUDE.md).
- **NOT TOUCHING:** gross-margin 체인(세션 B 완료, 잔차 +3.2%는 별개), `engine/skill_metrics.py`, 컨센 배선(`PLAN_consensus_wiring.md`), revenue 경로.
- **이 항목은 "예측 어려운 본질"일 수 있음**(verdict #2 명시). 목표는 "bias 0"이 아니라 **bias를 설명 가능한 구조로 분리**(고정 가능분 vs 본질적 변동분) + 후자를 오차밴드/overlay로 정직하게 표현.

## 3. 설계 (진단 → 분리 → 표현)

### 3.1 진단 (read-only, failing-test 무관)
- **신규 `scripts/diagnose_tax_finance.py`**(또는 기존 `diagnose_divergence.py` 확장): 8분기 각각에 대해 below-the-line을 실측 분해 — 실효세율(실측 tax/pretax), net financial(이자수지), FX 평가손익, 지분법, 기타 일회성. DART 캐시에서 추출 가능한 라인 우선.
- 산출: 분기별 (모델 가정 vs 실측) 표 → **−10.55% bias가 (a)실효세율 편차 (b)FX (c)일회성 중 어디서 오는지** 격리. 큰 음(−) 분기(2024Q4·2025Q1·2025Q3)에 무엇이 있었는지 점검(FX 평가손익 추정).

### 3.2 분리 (구조 — 진단 후 설계 확정)
- **고정 가능분**: 실효세율을 단일 0.20 대신 (i)완만한 시간가변 또는 (ii)pretax 구간별로. 실측 평균 실효세율로 anchor(가정값 = 사용자 확정).
- **본질적 변동분**(FX·일회성): 점추정으로 넣지 말 것 — 매크로/타이밍 레이어로. CLAUDE.md overlay 스키마 후보:
  `overlays: {as_of_date, driver, direction, magnitude, confidence}` — **단, EPS 숫자엔 넣지 않고**(lookahead 위험) valuation/entry/risk 레이어로(CLAUDE.md 2층 분리 원칙). FX 손익은 EPS driver가 아니라 risk-band.
- **오차밴드**: tax/finance 기여 변동성(분기 ±20%대)을 EPS 시나리오 밴드 폭에 반영 → 점추정 과신 대신 정직한 구간.

### 3.3 표현 / 출력
- backtest 리포트에 EPS 오차밴드 또는 "below-the-line 변동성" 주석. surprise-direction(컨센 배선 수정 후)과 함께 보면, 모델이 *level*은 약간 과소(−10.5%)지만 *컨센 대비 방향*은 잘 맞춘다는 그림이 정합적으로 보임.

## 4. 실행 순서 (진단 우선)

1. baseline: `pytest -q` green, 현재 8Q EPS bias −10.55%·tax/fin 기여표 보관(before).
2. `diagnose_tax_finance.py`로 below-the-line 실측 분해 → bias driver 격리(read-only, 비파괴).
3. 진단 결과를 사용자에 보고 → **분리 구조(3.2)·가정값(실효세율 anchor 등) 사용자 확정 대기.**
4. (확정 후) 고정 가능분 수정 → failing-test("실효세율 항이 실측 평균 ±Xp 재현") → 8Q 재측정, bias·MAPE before/after.
5. 본질적 변동분 → overlay/오차밴드 설계(EPS 숫자 불오염 보증).
6. 회귀 가드: 매출·gross-margin 경로 bit-identical(변경이 tax/finance에 격리됨) 확인.

## 5. Acceptance

- 진단표: −10.55% EPS bias가 below-the-line의 어느 항목(세율/FX/일회성)에서 오는지 분기별 격리.
- 고정 가능분 수정 후 EPS bias 축소(목표 방향: |bias| 감소) + **MASE/Theil 비악화**(RW 우위 유지). 단방향 bias가 줄면 MASE도 개선되어야 정합.
- 본질적 변동분은 EPS 점추정이 아니라 오차밴드/overlay로 — **EPS 숫자에 lookahead 미반영** 보증.
- 가정값 변경은 전부 사용자 확정 후. `pytest -q` green, `--dry-run` 새 출력 포함.

## 6. 위험 / 가정

- below-the-line(특히 FX·일회성)은 **구조적으로 예측 어려움** — 미세조정으로 bias 0 추구는 overfitting. "설명 가능한 분리 + 정직한 밴드"가 목표.
- 8Q 작은 표본: 세율 anchor가 1~2개 이상치 분기에 휘둘리지 않게 robust 추정(중앙값/trimmed) 고려.
- overlay 도입은 스키마 변경 → Pydantic v2 `extra="forbid"` 신규 필드 추가만(기존 의미 불변).
- 샌드박스: DART 캐시로 진단 오프라인 가능(세션 C 입증). FX/일회성 라인이 캐시 DART에 없으면 호스트 보강 필요.

## 7. 변경 파일 요약 (구현 시, 진단 후 확정)

신규: `scripts/diagnose_tax_finance.py`, 관련 테스트. 수정(진단 후): `engine/tax_finance.py`(세율 구조), `profiles/sk_hynix.yaml`(세율/finance 가정 — **사용자 확정**), 조건부 `schemas/models.py`(overlay 필드)·출력(오차밴드).
NOT TOUCHING: gross-margin 체인, 컨센 배선, revenue 경로, `engine/skill_metrics.py`.

## 8. 순서 메모

`PLAN_consensus_wiring.md`(측정 복구, 1-line)가 **선행 권장** — 측정을 켠 뒤 tax/finance 수정의 before/after를 surprise-direction까지 포함해 평가하기 위함. 단 두 PLAN은 독립이라 병렬 가능.
