# REVIEW — NVDA-2 metrics parity plan (Codex)

Date: 2026-07-21  
Reviewed: `HANDOFF_nvda2_review.md`, `PLAN_nvda2.md`  
Baseline: `2ac4d58`

## Verdict

**조건부 승인.** 2a → 2b → 2c 순서는 유지하되, 구현 전에 아래 binding
corrections를 `PLAN_nvda2.md` rev-1에 반영해야 한다.

## 1. Blocking claims

### 1.1 SkillRow conversion

행 변환은 lossless다. NVDA와 TSLA 모두 `backtest_generic`의 26개 행이
`SkillRow`로 1:1 변환됐고 EPS 표본도 각각 26개였다. 현재 프로필에서는
EPS `None`/0 처리로 인한 표본 중복이나 누락이 없다.

단, legacy 필드와 `compute_skill` 필드는 **단위가 다르므로 값 자체가
동일하다는 주장은 거짓**이다.

| Profile | legacy RW revenue | `compute_skill` | legacy RW EPS | `compute_skill` |
|---|---:|---:|---:|---:|
| NVDA | 13.89797% | 0.1389797 | 30.59420% | 0.3059420 |
| TSLA | 13.19431% | 0.1319431 | 101.42220% | 1.0142220 |

정확한 identity는 다음과 같다.

```text
legacy naive_rw_*_mape == compute_skill.naive_rw_*_mape * 100
```

`BacktestSkill`은 memory-path 계약대로 0–1 ratio를 유지하고, report에서만
percent로 포맷한다. equivalence test도 `legacy == skill * 100`으로 작성한다.
`BacktestSkill.model_dump()` 값을 legacy percent와 같은 단위처럼 직접
렌더링하면 안 된다.

### 1.2 Window partition

통과했다.

```text
NVDA: full 26 = pre_break 14 + post_break 12
TSLA: full 26 = pre_break 14 + post_break 12
post_break first row = 2023Q2
duplicate quarter = none
```

현재 `YYYYQq` 형식에서는 문자열 비교가 안전하고 boundary는 post side에
포함된다. 단, MAPE 평균끼리 더해 full-window identity를 검사하면 안 된다.
행 집합, 표본 수, error numerator를 union한 결과가 full-window 값을
재현하는지 검증해야 한다.

## 2. Answers to Q1–Q7

### Q1. Split-window reporting

프로필 필드 + dual-window + post-break headline에 동의한다.
`regime_break_quarter`는 재현 가능한 analyst assumption이므로 CLI flag가
아니라 `GenericProfile`에 두는 것이 맞다.

다만 현재 `engine/generic_signal.py`는 full/trailing-8Q를 직접 재계산한다.
report와 console만 post-break를 headline으로 바꾸면 JSON signal/stance와
보고서가 서로 다른 window로 판단할 수 있다. 다음 계약을 추가한다.

- report와 console의 primary window는 post-break다.
- JSON `backtest.windows`는 full/pre/post를 모두 보존한다.
- signal primary skill도 post-break를 사용한다.
- signal trailing-8Q는 post-break 안의 마지막 8개 행을 사용한다.
- full과 post/trailing의 판정 불일치는 별도로 표시한다.
- regime field가 없는 profile은 기존 full/trailing 동작을 유지한다.

### Q2. Historical model-EPS share convention

옵션 (b), prior-quarter as-filed diluted shares를 current split basis로
조정해 사용하는 방식을 승인한다. target-quarter shares look-ahead를
피하면서 당시 이용 가능한 share base를 사용하며, TSLA의 약 25% historical
wedge 때문에 fixed-forward 방식을 유지하기 어렵다.

구현 계약은 다음과 같다.

- `prev.diluted_shares * profile.split_factor(prev.period_end)`를 사용한다.
- legacy actual에 shares가 없으면 fixed forward shares로 명시적으로 fallback한다.
- shares는 있는데 `period_end`가 없으면 기존 schema validation대로 실패한다.
- forward forecast의 fixed-share assumption은 변경하지 않는다.
- before/after handoff에 share convention 변경을 명시한다.

### Q3. N=12 skill stability

점추정치와 `n`은 계산 가능하면 표시하고, claim/gate에만 최소 표본을
적용한다. skill block 자체를 숨기면 감사 가능성이 떨어진다.

현재 signal의 `MIN_SKILL_N = 8`과 충돌하는 6을 새로 도입하지 않는다.

- MASE/Theil/RW MAPE는 계산 가능하면 항상 표시한다.
- `n < 8`은 descriptive only이며 skill claim/stance gate에 사용하지 않는다.
- `n >= 8`부터 gate를 허용한다.
- consensus N 약 4는 표시하되 “beats consensus” claim에는 사용하지 않는다.
- `n_surprise_scored`를 항상 함께 표시한다.

### Q4. Yahoo 0q anchoring

latest actual → next fiscal quarter 원칙은 맞지만 `period_end`만으로 Yahoo의
roll 상태를 완전히 판별할 수 없다. 실적 발표 당일 history와 estimate가
서로 다른 시점에 roll하거나, profile과 Yahoo 중 한쪽만 갱신될 수 있다.

다음 guard를 추가한다.

- latest actual `period_end`와 latest earnings-history end가 일치할 때만
  `0q`를 다음 fiscal quarter에 매핑한다.
- history가 없거나 두 날짜가 불일치하면 forward quarterly consensus를
  `None`으로 둔다.
- 독립적으로 정상화 가능한 historical consensus까지 삭제하지 않는다.
- anchor가 불확실하면 annual forward consensus도 `None`으로 둔다.
- cache에 fetch timestamp/as-of를 보존한다.
- revenue와 EPS의 0q/+1q period set이 다르면 quality failure로 처리한다.
- snapshot `as_of`가 latest actual period end보다 앞서면 refuse한다.

Off-cycle restatement는 보통 period-end label을 바꾸지 않으므로 주된 mapping
위험은 아니다.

또한 `ConsensusRecord` annual key는 현재 `dict[int, ...]`다. PLAN의
“`FY{fiscal_year}`로 labelled” 표현은 schema와 충돌하므로 fiscal-year 정수
key를 유지한다.

### Q5. Attribution lever count

임시 3-lever를 먼저 출시하지 않는다. 2c는 이미 후순위이고 host full-blob
refetch가 precondition이므로 임시 결과 계약을 만든 뒤 4-lever로 교체할
이유가 없다.

- 2a와 2b를 먼저 완료한다.
- full blob에서 `OperatingIncomeLoss` 재현이 확인되면 4-lever를 구현한다.
- OP facts가 불완전하면 2c를 연기한다.
- 3-lever는 필요할 경우 내부 진단 fallback으로만 고려하고 정식 산출물로
  출시하지 않는다.

### Q6. Issuer-neutral quality gates

고정 60% cap은 제거한다. quality gate는 경제적 전망의 적정성 판정이
아니라 단위·조인 오류 탐지 장치로 제한한다.

- Unit gate: `0.3 <= consensus_0q_revenue / latest_actual_revenue <= 3.0`
- Margin gate: `realized_min - 10pp <= implied_margin <= realized_max + 10pp`
- share denominator와 `unit_scale`은 profile 기준으로 명시한다.
- revenue 또는 EPS가 없으면 gate를 실행하지 않으며 그 자체를 quality
  failure로 취급하지 않는다.
- 실패한 consensus 값은 억제하되 원래 값과 실패 이유는 audit 정보로
  보존한다.

NVDA의 realized net-margin range는 약 9.8%–71.5%이므로 ±10pp buffer는
기존 60% cap의 오탐을 피한다.

### Q7. Sequencing

2a → 2b → 2c를 유지한다. consensus join은 2a skill schema의 optional
consensus fields만 채우면 되므로 순서를 뒤집을 이유가 없다.

2a에서 다음 stable schema를 먼저 확정한다.

```text
backtest
|-- legacy scalar metrics
|-- rows
|-- skill
`-- windows
    |-- full
    |-- pre_break
    `-- post_break
```

각 window는 최소 `n`, `n_eps`, MAPE, bias, `skill`을 가진다. 2b는 기존
skill 구조의 consensus 관련 필드만 계산하며 별도 consensus-skill schema를
추가하지 않는다.

## 3. Binding corrections for PLAN rev-1

1. Legacy MAPE percent와 `BacktestSkill` ratio 단위를 구분한다.
2. signal primary window를 post-break headline과 일치시킨다.
3. 최소 표본 기준은 기존 signal과 맞춰 8로 통일하고 metric 자체는
   숨기지 않는다.
4. prior-quarter shares의 split adjustment와 legacy fallback을 명시한다.
5. annual consensus key는 `FY...` 문자열이 아닌 fiscal-year 정수로 유지한다.
6. 임시 3-lever를 출시하지 않고 OP 데이터 확인 후 4-lever를 한 번만
   구현한다.

이 corrections가 반영되면 NVDA-2 구현을 2a부터 시작해도 된다. 외부에
NVDA-2 metrics를 인용하는 것은 full companyfacts refetch/reproduction gate가
통과한 뒤에만 허용한다.
