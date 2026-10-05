# MU FY2026 Q4 RLE 값 산출 검토 r2

> 수행 기준: `forecast/HANDOFF_CODEX_mu_report_exec.md` 부록 R13  
> 단위: USD million, 별도 표기 없으면 GAAP  
> 투자 자문이 아니다. 렌더 및 git 쓰기는 수행하지 않았다.

## 1. A11 해석 정정과 FY27E D&A

### 1.1 판정

**A11 AVAILABLE.** FY2025 10-K p.87은 자본적 지출 관련 정부 인센티브가 PP&E를 감액한다고 명시한다. 따라서 재무상태표 PP&E와 정합하는 roll-forward 입력은 회사 가이드의 **net capex**다. R6의 `gross capex` 표기는 해석 오류이며, R13에 따라 다음 식으로 정정했다.

`PPE_end = PPE_begin + net capex − D&A`

`D&A = (d/4) × average(PPE_begin, PPE_end)`

여기서 `d = 9,503 / average(46,590, 63,310) = 17.2939035487%`, 분기율은 4.3234758872%다. 암시식을 정리하면 `D&A = (d/4)×(PPE_begin + net capex/2) / (1 + d/8)`이다.

이 조치는 R12의 `post_print_change` 3건을 늘리지 않는다. YAML의 별도 `interpretation_note.A11_net_capex_roll_forward`에 원해석·정정·근거·한계를 기록했다.

### 1.2 분기 roll-forward

| 기간 | 기초 PP&E | net capex | D&A | 기말 PP&E |
|---|---:|---:|---:|---:|
| FQ1 FY27E | 63,310.00 | 11,500.00 | 2,922.61 | 71,887.39 |
| FQ2 FY27E | 71,887.39 | 13,500.00 | 3,327.93 | 82,059.46 |
| FQ3 FY27E | 82,059.46 | 12,500.00 | 3,737.25 | 90,822.21 |
| FQ4 FY27E | 90,822.21 | 12,500.00 | 4,108.09 | 99,214.12 |
| **FY27E** | **63,310.00** | **50,000.00** | **14,095.88** | **99,214.12** |

한계는 정부 인센티브 수령과 PP&E 감액의 시차다. FY26A 비유동 미실현 정부 인센티브 $786M을 별도 시차 모델로 풀지 않았으며 이 해석은 J다.

## 2. FY27E FCF와 순현금

### 2.1 기초 순현금

표 라벨은 **순현금(SCA 예치금 미조정)**으로 고정한다. FY26A 재무상태표에서 다음과 같이 계산했다.

`38,364 cash and equivalents + 5,070 short-term investments + 30,019 long-term marketable investments − 491 current debt − 4,688 long-term debt = 68,274`

FY26A SCA 고객계약부채 $12,895M은 위 값에서 차감하지 않았고, A16에 따라 FY27 유입·반환도 예측하지 않았다. 제한현금도 순현금 정의에 넣지 않았다.

### 2.2 시나리오별 계산

식은 `운전자본 투자 = k×(FY27 매출−FY26 매출)`, `CFO = NI + D&A + SBC − 운전자본 투자`, `FCF = CFO − net capex`, `기말 순현금 = 68,274 + FCF − 배당`이다. `k=3.4479155783%`, FY26 매출 $133,188M, D&A $14,095.88M, SBC $1,972M, net capex $50,000M, 배당 $690M은 세 시나리오 공통이다.

| 시나리오 | FY27 매출 | NI | D&A | SBC | 운전자본 투자 | CFO | net capex | FCF | 배당 | 기말 순현금(SCA 예치금 미조정) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Bear | 210,876.00 | 136,791.92 | 14,095.88 | 1,972.00 | 2,678.62 | 150,181.18 | 50,000.00 | **100,181.18** | 690.00 | **167,765.18** |
| Base | 274,784.14 | 194,403.52 | 14,095.88 | 1,972.00 | 4,882.12 | 205,589.28 | 50,000.00 | **155,589.28** | 690.00 | **223,173.28** |
| Bull | 313,826.03 | 229,443.11 | 14,095.88 | 1,972.00 | 6,228.25 | 239,282.74 | 50,000.00 | **189,282.74** | 690.00 | **256,866.74** |

bear/base/bull 세 경로만 계산했다. R9의 확률 삭제를 유지했으며 확률가중 FCF·순현금은 만들지 않았다. 자사주·인수·차입 변동·SCA 예치금 신규 유입 또는 반환도 모델하지 않았다.

## 3. 로더 계약 정렬

### 3.1 `rle.py` 변경

- 구형 `RLEDrivers` 축약 계약을 제거하고 계획 D2 머리 계약을 모델링했다: `units` 3단위, FY2027/FY2028 `week_basis`, 경로별 `input_sha256`, `source_catalog`, 일자 정밀도와 KST 시간대.
- 모든 `value` 노드는 `source_id`가 필수다. 빈 목록과 source catalog에 없는 ID는 거부한다.
- `post_print_change`는 R12의 **A3_base·A4_opex·A14_net_capex 정확히 3건**이어야 한다.
- `interpretation_note.A11_net_capex_roll_forward`를 필수로 한다.
- 알 수 없는 최상위 키와 구형 YAML은 명시적 검증 오류로 거부한다. 조용한 하위 호환은 두지 않았다.
- 순수 함수 `quarterly_da_roll_forward()`를 추가해 분기 평균 PP&E와 net capex로 D&A·기말 PP&E를 재현한다.

### 3.2 fixture와 실제 YAML 재현

E2-A 리허설 fixture `fake_postprint.yaml`을 같은 D2/source 계약으로 갱신했다. 기존 DRYRUN 테스트가 사용하는 fixture 경로와 식별자는 유지했다.

실제 `mu_fy2026q4_report_assumptions.yaml`을 로더로 읽어 다음을 한 테스트에서 재현한다.

| 항목 | 기대값 | 결과 |
|---|---:|---|
| FY27 base 매출 | 274,784.139585 | PASS |
| FY27 base GAAP EPS | 169.05 ±0.01 | PASS |
| FY27 D&A | 14,095.876795 | PASS |
| FY27 base FCF | 155,589.277541 | PASS |
| FY27 base 기말 순현금(SCA 예치금 미조정) | 223,173.277541 | PASS |

테스트의 `GenericProfile` 확률 필드는 기존 엔진 스키마를 만족시키기 위한 계산 경로용 값일 뿐이며, 결과를 가중하거나 YAML 가정으로 저장하지 않는다. YAML의 `scenario_probabilities`는 계속 `null`이다.

## 4. 검증과 테스트

| 검사 | 결과 |
|---|---|
| 신규 fixture 및 실제 YAML 로더 단위 테스트 | **2 passed** |
| MU 보고서 테스트(리허설·DRYRUN 포함) | **57 passed** |
| forecast 전체 | **479 passed, 3 skipped, 1 deselected, 1 xfailed** |
| 실제 YAML 입력 SHA 핀 재계산 | PASS |
| LF / NUL / `git diff --check` | PASS |
| 렌더 | **미실행** |

skip 3건은 Windows symlink·process-group 제약과 gitignore된 파생 EDGAR cache 부재다. xfail 1건은 기존 FYE-August Q1 라벨 이슈다.

## 5. 변경 파일

- `forecast/inputs/mu_fy2026q4_report_assumptions.yaml`
- `forecast/scripts/mu_report/rle.py`
- `forecast/tests/fixtures/mu_report/fake_postprint.yaml`
- `forecast/tests/test_mu_report.py`
- `forecast/REVIEW_CODEX_mu_report_rle_values_r2.md`

git add·commit·push는 하지 않았다.
