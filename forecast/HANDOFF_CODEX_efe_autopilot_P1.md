# HANDOFF_CODEX — 오토파일럿 P1 구현 사양 (완결 수식 + 빈티지 계약)

- `DOC_REV: autopilot-P1-rev3.4 / 2026-07-31 KST` ← **리뷰 시 이 줄로 최신본 여부를 확인할 것.** rev3.4 미만이면 구버전(R1~R7 완결 수식 §3·빈티지 계약 §5·이전 반려 13건 수정이 모두 반영돼 있다)

**rev3.3 반려 7건 대응**: R7 fallback 적용식 완결(§2·§3 R7) · **OP 금액 밴드 = 구간곱 4후보**(§3 R7) · **승인 커밋 결정론적 탐색 + signer allowlist + ancestry**(§7) · **동결 증명 재정의 `FREEZE_PROVEN|UNPROVEN`**(§7-b) · bridge delta **항등식 테스트로 전환**(§8) · 상위 문서 참조/`accepted_at`/윈도우 수치 동기화(상위 rev3.4)

**rev3.2 반려 6건 대응**: ① type-7 인덱스 0-index로 통일(§1) ② **R7의 OP 잔차를 `op_margin` level_delta로 교체**(적자·흑전 구간에서 log_ratio 불가) ③ R4 하드코딩 상수 정책 이관(§2) ④ `approval_commit` 자기참조 제거 → **`policy_commit` + 서명 커밋**(§7) ⑤ **Shapley↔순차 등식 테스트 폐기** → 독립 계산 + `methodology_bridge_delta` 기록(§6) ⑥ 수집 완전성 계약: raw fact에 `selection_rule_id` 금지, **선택 결과 레코드** 분리(§4)

- 작성: Claude, 2026-07-31 KST. 상위: `HANDOFF_CODEX_efe_autopilot.md`(**동일 rev**. 본문에 rev 숫자를 쓰지 않는다 — 정본은 상단 `DOC_REV` 한 줄)
- rev-2 조건부 반려(Codex) 대응. 반려 사유 5건 + 4대 권고 전부 반영
- **모든 상수는 `policy/resolver_policy_v1.yaml`에 있고, 코드에 하드코딩 금지.** 정책 활성화는 §7 승인 게이트를 통과한 SHA만

---

## 0. 반려 대응 요약

| Codex 지적 | 대응 |
|---|---|
| R3 "상하 1개 제거"는 trimming | **진짜 winsorization**으로 재정의(§3 R3). 분위수 = Hyndman–Fan **type 7** 고정. 세전≈0/음수 처리·최소표본·fallback·bear=고세율 명시 |
| R2 level/shape 결합식 부재 | 가중치·중심화·결합식 확정(§3 R2). `trailing_level_at_origin` 정의 포함 |
| R7 룩어헤드 사양 부족 | **forecast-origin 빈티지 계약**(§5)으로 분리 명세. 대상 분기 제외·metric/horizon 분리·signed 분위수·정책 변경 시 전량 재계산 |
| R1 표본 과소·슬롯 모호 | `fiscal_slot` 정의(FYE 기준), 윈도우 12Q 고정, **슬롯 표본 부족 시 축소(shrinkage) 사다리**(§3 R1) |
| R4·R5 미완결 | R4 = **매출 대비 비율**·대칭 밴드 명시. R5 = 고정 6Q·**로그차분 중앙값**(회귀 폐기 → x축 모호성 소멸)·split 정규화·희석가중평균 기준 명시 |
| P-1 누출(팩트 선택 등) | **selection_rule_id 기반 팩트 선택을 코드로 이관**(§4). 에이전트는 원천 팩트를 verbatim 적재만, 파생 필드 스키마 금지 |
| 룩어헤드 잔존 | `filed_at` → **`accepted_at`(tz-aware UTC instant)**, restated fact 침투 차단, 역산 금지, backtest origin별 `vintage_view_sha`(§5) |
| P-5 우회 | 경로가 아닌 **정책 SHA allowlist + 사람 서명 레코드**(§7). 제안 브랜치는 `ledger/proposals/**` 외 변경 거부 |
| 전 레인 공정성·귀인 순서의존 | 5필드 동일성 계약 + `human_late` 코호트 분리. 귀인은 **Shapley(정본) + 고정순서 순차(참고)** 병기(§6) |

---

## 1. 표기·공통 규약

- `fiscal_slot(q) ∈ {1,2,3,4}` — 발행사 회계연도 내 순번. `watchlist.fiscal_year_end_month`에서 결정론적으로 산출. **calendar quarter 사용 금지**(NVDA 1월 FYE 등). 기존 `backtest_methodology.revenue_growth_qoq`는 fiscal-slot 인덱스로 마이그레이션.
- `median(x)`: 정렬 후 홀수는 중앙값, 짝수는 두 중앙값의 산술평균.
- `quantile(x, p)`: **Hyndman–Fan type 7, 0-index 규약으로 고정**. 오름차순 정렬 배열 `x[0..n−1]`에 대해
  `h = (n−1)·p`, `lo = floor(h)`, `hi = min(lo+1, n−1)`, `Q = x[lo] + (h − lo)·(x[hi] − x[lo])`.
  `p=0 → x[0]`, `p=1 → x[n−1]`. numpy `np.quantile(..., method="linear")`와 일치. **1-index 표기 사용 금지**(rev3.2 모순 수정).
- 모든 시각은 **tz-aware UTC instant**. date 비교 금지.
- 직렬화: 값은 소수 10자리 반올림 후 기록. 합산은 정렬 순서 + `math.fsum`.
- 표본 부족·미정의 상황은 **예외로 죽지 않고** 플래그(`R*_SPARSE`, `LOW_SKILL`)를 남기고 fallback 사다리를 탄다. 단 `LookaheadError`·`INPUT_MUTATED`는 즉시 중단.

---

## 2. `policy/resolver_policy_v1.yaml` (전 상수 집합)

```yaml
policy_version: "v1"
r1_revenue:
  window_quarters: 12
  min_total_obs: 6                # 미만이면 seasonality 0 + LOW_SKILL
  shrinkage_k: 2                  # eff = n/(n+k) * centered
r2_op_margin:
  level_weights: [0.40, 0.30, 0.20, 0.10]   # 최근 → 과거, 합 1
  window_quarters: 12
  shrinkage_k: 2
  margin_floor: -0.20
  margin_cap: 0.60
r3_tax:
  window_quarters: 8
  min_pretax_ratio: 0.005         # pretax > 0.005 * revenue 인 분기만 표본
  winsorize: true
  winsorize_min_n: 5              # 이 미만이면 winsorize 미적용
  min_obs_after_exclusion: 4
  bear_quantile: 0.90             # 높은 세율 = bear
  bull_quantile: 0.10
  etr_clip: [0.00, 0.45]
  default_etr_by_domicile: {US: 0.21, KR: 0.22}
r4_below_op:
  basis: "revenue"                # (pretax − op) / revenue
  base_value: 0.0                 # 구조적 예측불가 — 앵커 금지
  window_quarters: 8
  band_quantile: 0.80             # q = quantile(|x|, 0.80), 밴드 [-q, +q]
  band_floor: 0.005
  min_obs: 4                      # 미만이면 sparse fallback
  sparse_band_multiplier: 4.0     # fallback q = band_floor × 이 값
r5_shares:
  window_quarters: 6
  min_obs: 3
  drift_clip: [-0.02, 0.01]       # 분기 로그드리프트 상하한
r6_scenarios:
  probabilities: {base: 0.50, bear: 0.25, bull: 0.25}
r7_band:
  metrics: ["revenue", "op_margin", "eps"]     # ⚠ "op"(금액) 아님 — §3 R7 참조
  horizons: [1]
  residual_space:
    revenue: "log_ratio"        # ln(actual/forecast)
    op_margin: "level_delta"    # actual_margin − forecast_margin (마진 포인트)
    eps: "level_usd"            # actual − forecast (USD)
  lower_quantile: 0.10
  upper_quantile: 0.90
  min_residuals: 6
  fallback_band:                  # 경험 잔차 부족 시 — **대칭**(경험 밴드는 비대칭 허용)
    revenue_log_abs: 0.08         # bounds = forecast_rev × exp(∓0.08)
    op_margin_abs: 0.030          # bounds = forecast_margin ∓ 0.030 (마진 포인트)
    eps:
      pct_of_abs_forecast: 0.60   # width = |forecast_eps| × 0.60
      absolute_floor_usd: 0.25    # 최소 절대 폭 (forecast_eps ≈ 0에서 밴드 붕괴 방지)
canonical_serialization:
  decimals: 10                  # 직렬화 반올림 자리수
selection_rules_file: "policy/selection_rules_v1.yaml"
```

---

## 3. 리졸버 룰 — 완결 수식

### R1 매출 (계절 QoQ, 로그 공간)

윈도우 = 최근 `window_quarters`개의 as-of 시점 가용 분기.

1. `g_t = ln(rev_t / rev_{t−1})`
2. `trend = median({g_t})`
3. `raw[s] = median({g_t : fiscal_slot(t)=s}) − trend`, 관측 없는 슬롯은 `raw[s]=0, n_s=0`
4. 중심화: `c[s] = raw[s] − mean(raw[1..4])`
5. 축소: `eff0[s] = n_s/(n_s + k) · c[s]`, **재중심화** `eff[s] = eff0[s] − mean(eff0[1..4])` (연간 합 보존)
6. `ln(rev_{T+1}) = ln(rev_T) + trend + eff[fiscal_slot(T+1)]`

**Fallback**: 총 관측 `< min_total_obs` → `eff[s]=0` (추세만) + `R1_SPARSE`·`LOW_SKILL`. 슬롯별 표본 부족은 예외가 아니라 4~5단계 축소가 자동 처리(하드 컷오프 없음 = 결정론).

### R2 영업이익률 (연결 GAAP OP 마진에만 앵커)

`m_t = op_t / rev_t` (**연결 GAAP OP**. 세그먼트·adjusted EBITDA 금지).

1. `level = Σ_{i=1..4} w_i · m_{T+1−i}` (`w = level_weights`, 최근이 `w_1`)
2. 각 과거 분기 q에 대해 `L(q) = Σ_{i=1..4} w_i · m_{q−i}` (q **직전** 4분기 = origin 시점 level)
3. `dev_q = m_q − L(q)`
4. `raw[s] = median({dev_q : fiscal_slot(q)=s})`, 중심화·축소·재중심화는 R1의 4~5단계와 동일
5. `forecast_margin = clip(level + eff[s], margin_floor, margin_cap)`

`L(q)` 계산에 4분기가 필요하므로 유효 슬롯 표본은 (윈도우 − 4)개에서 나온다. GEV처럼 히스토리가 짧으면 축소가 자동으로 계절성을 0 쪽으로 눌러준다.

### R3 유효세율

1. 표본 후보: 최근 `window_quarters` 중 **`pretax_t > min_pretax_ratio · rev_t`** 인 분기만. 제외된 분기는 `R3_ETR_UNDEFINED` 기록(세전 ≈ 0/음수에서 ETR은 정의 불가·발산).
2. 오버레이 `exclude_from_sample`(target=`effective_tax_rate`) 적용은 **레인에 따라 다르다**(상위 문서 §4 레인 표가 정본): `machine_base`=미적용, `machine_overlay_approved`=승인분만, `machine_overlay_proposed`=승인+미승인. 따라서 표본이 레인별로 달라진다.
3. `n < min_obs_after_exclusion` → fallback 사다리: ① 가용 FY들의 `Σtax/Σpretax` ② `default_etr_by_domicile` + `LOW_SKILL`.
4. **Winsorization (n ≥ `winsorize_min_n`)**: 정렬 후 **최솟값을 2번째 작은 값으로, 최댓값을 2번째 큰 값으로 치환**(제거 아님, n 불변). 미만이면 미적용.
5. `base = median(winsorized)`, `bear = quantile(winsorized, 0.90)`(고세율), `bull = quantile(winsorized, 0.10)`(저세율).
6. 전부 `etr_clip`으로 클리핑. `bull ≤ base ≤ bear` 위반 시 정렬 강제 후 `R3_ORDER_FIXED` 플래그.

### R4 below-OP 블록

`x_t = (pretax_t − op_t) / rev_t` (basis = revenue. OP 분모는 0 근방에서 발산하므로 금지 — GEV 2026Q1이 실례).

- `base = 0.0` (정책 상수, 앵커 금지)
- `q = max(quantile({|x_t|}, band_quantile), band_floor)` (최근 8Q)
- 밴드 = **대칭** `[−q, +q]`. bear = `−q`, bull = `+q`.
- 관측 < `min_obs` → `fallback: q = band_floor × sparse_band_multiplier` + `R4_SPARSE`. (두 상수 모두 정책 파일 — 코드 하드코딩 금지)

### R5 희석주식수

- 대상 태그: **diluted weighted-average shares outstanding**(§4 selection rule로 고정). split 정규화는 빈티지의 split factor로 코드가 수행.
- 표본: 최근 `window_quarters`=6 고정. 가용 `< min_obs` → 드리프트 0 + `R5_SPARSE`.
- `drift = clip(median({ln(s_t/s_{t−1})}), drift_clip)` — **회귀 폐기**(x축 정의 모호성 제거).
- `s_{T+1} = s_T · exp(drift)`.

### R6 시나리오 확률

정책 상수(`base .50 / bear .25 / bull .25`). 분기별 재량 금지.

### R7 예측 밴드 — §5 빈티지 계약 위에서만 성립

- 잔차 공간(정책 `residual_space`):
  - `revenue` = `ln(actual/forecast)` (항상 양수 → 로그 안전)
  - **`op_margin` = `actual_margin − forecast_margin` (마진 포인트, level_delta)** — ⚠ **OP 금액의 log_ratio 금지.** 적자·흑자전환 구간에서 정의되지 않고, R2가 마진 하한 −0.20을 허용하는 것과 모순된다(rev3.2 지적 ②)
  - `eps` = `actual − forecast` (USD 레벨) — EPS는 0을 교차하므로 비율 공간 금지
- **OP 금액 밴드는 구간곱(interval product)으로 파생**한다. 마진이 음수일 수 있으므로 경계끼리 짝지을 수 없고 4개 후보를 전수한다(매출은 항상 양수 전제):

```
rev_lo    = forecast_revenue × exp(revenue_residual_lo)
rev_hi    = forecast_revenue × exp(revenue_residual_hi)
margin_lo = forecast_margin + margin_residual_lo
margin_hi = forecast_margin + margin_residual_hi
op_candidates = {rev_lo×margin_lo, rev_lo×margin_hi, rev_hi×margin_lo, rev_hi×margin_hi}
op_lo = min(op_candidates);  op_hi = max(op_candidates)
```

  독립 OP 잔차 풀은 두지 않는다(매출 불확실성 이중 계상 방지).
- 잔차 풀은 **metric별·horizon별로 분리**. 파일럿은 h=1만.
- **현재 예측 대상 분기는 calibration에서 제외**(actual 미존재).
- 각 잔차는 그 origin 시점의 `vintage_view_sha`로 계산된 forecast에서만 나온다(§5).
- `lower = quantile(r, 0.10)`, `upper = quantile(r, 0.90)` — **signed**(비대칭 허용).
- `n < min_residuals` → `fallback_band` + `LOW_SKILL`. **적용식(대칭)**:
  - `revenue`: `[fcst × exp(−revenue_log_abs), fcst × exp(+revenue_log_abs)]`
  - `op_margin`: `[fcst_margin − op_margin_abs, fcst_margin + op_margin_abs]`
  - `eps`: `width = max(|fcst_eps| × pct_of_abs_forecast, absolute_floor_usd)` → `[fcst_eps − width, fcst_eps + width]`
    (`fcst_eps = 0`이어도 `absolute_floor_usd` 덕분에 밴드가 0으로 붕괴하지 않는다)
- **정책이 바뀌면 과거 잔차 재사용 금지 — 전량 재계산.** FROZEN 헤더에 `residual_set_sha` 기록.

---

## 4. P-1 누출 차단 — 팩트 선택을 코드로 이관

Codex 지적대로 "숫자를 입력하지 않아도" 다음 경로로 판단이 샌다: XBRL 태그/컨텍스트 선택, fiscal slot 매핑, 중복 accession 채택, tie-out 허용오차, 결측 처리, 오버레이 분류, 사전 정규화된 값 기록.

**계약:**

1. **수집 완전성 계약** — "에이전트가 무엇을 수집하지 **않았는지**"는 코드가 복구할 수 없다(rev3.2 지적 ⑥). 따라서 수집기는 **정책에 열거된 accession·document·context 전체를 적재**한다(선별 수집 금지).
   - raw fact 스키마: `{value, source_fact_id, taxonomy, tag, unit, period_start, period_end, context_ref, segment_axes[], accession, accepted_at, content_sha256}` — **`selection_rule_id`를 넣지 않는다.** 그것은 팩트의 속성이 아니라 *선택 실행*의 속성이다.
   - 선택 결과는 별도 레코드: `{metric, selection_rule_id, candidate_fact_ids[], chosen_fact_id, rule_version}` — 후보 전체가 남아야 선택이 재현·감사된다.
   - **완전성 검사**: 문서 해시 대조 + 기대 후보 수(정책에 metric별 최소 후보 수) + 필수 태그 누락 검사. 하나라도 실패 → `DATA_BLOCKED`(부분 수집으로 진행 금지).
2. **파생·정규화 필드를 스키마가 금지**한다(`op_margin`, `qoq_growth` 등 계산값 키 자체를 거부). 정규화(연결 여부 판정, 분기 분해, split 조정, 단위 환산)는 **버전 고정 코드**가 수행.
3. `policy/selection_rules_v1.yaml` — 선택도 룰이다:
   - 태그 우선순위 리스트(metric별)
   - **연결 판정**: `segment_axes`가 비어 있는 컨텍스트만 채택(세그먼트 축 존재 시 배제)
   - 중복 accession: `accepted_at <= as_of` 중 **가장 늦은 것**, 동률이면 accession 사전순
   - tie-out 허용오차: 절대/상대 임계값 명시. 초과 시 `DATA_BLOCKED`(추정 보정 금지)
   - **YTD·10-K에서 분기 역산 금지**(후속 공시 혼입 위험) — 분기 값이 as-filed로 존재하지 않으면 `DATA_BLOCKED`
4. 오버레이 분류는 에이전트가 **제안만** 한다(`proposed_by: agent, approved: false`). 미승인 레코드는 **`machine_overlay_proposed` 레인에만** 반영된다. `machine_base`는 어떤 오버레이에도 불변이고, `machine_overlay_approved`에는 `approved: true`만 들어간다(상위 문서 §4 레인 표 = 정본).

---

## 5. 빈티지 계약 (룩어헤드 차단)

1. 시점 기준은 `filed_at`이 아니라 **SEC `accepted_at`** (EDGAR acceptance datetime, tz-aware UTC). 날짜 비교 금지 — 같은 날 장 마감 후 공시가 장중 예측에 섞이는 경로를 막는다.
2. 빈티지 저장소는 **append-only**: 키 `(taxonomy, tag, period, accession)`. companyfacts의 "최신값" 질의 금지(restated fact 침투 경로).
3. `vintage_view(as_of)` = `accepted_at <= as_of`인 팩트만으로 구성한 뷰. 뷰의 해시 = **`vintage_view_sha`**.
4. **backtest는 origin마다 자기 `vintage_view_sha`를 요구**한다. 현재 저장된 actual/profile을 쓰는 backtest는 금지(`test_backtest_vintage.py`로 강제).
5. actual 스냅샷은 정의가 흔들린다(보도자료 → 8-K → 10-Q). `actual_sha`와 함께 **`actual_source_stage ∈ {press_release, 8k, 10q}`**를 기록하고, 전 레인은 동일 `actual_sha`만 사용한다. 단계가 올라가면 **재채점은 새 레코드로 append**(기존 수정 금지).

---

## 6. 전 레인 계약 + 귀인

**공정 비교 5필드 동일성**: `freeze_as_of`, `inputs_sha`, `consensus_vintage_sha`, `actual_sha`, **`comparison_policy_sha`**.

> ⚠ 마지막 필드는 rev3.2에서 `policy_sha`로 잘못 표기됐다. 사람 레인은 리졸버 정책으로 숫자를 만들지 않으므로 그것은 *생성 입력*이 아니라 **비교 조건**이다(rev3.2 지적 ⑥ 후단). 사람 레인은 자신의 방법론 식별자를 **`human_methodology_sha`**로 별도 기록한다(자유 서술 가능, 사후 대조용).

사람 레인도 **T-72 이전 커밋**이어야 `human` 코호트. 이후 커밋은 `human_late`로 **별도 코호트**(비교표에서 분리 표기, 혼합 집계 금지).

**귀인**: 순차 치환은 순서 의존이고 "잔차 0"은 오귀인을 걸러내지 못한다.
- **정본 = Shapley**. 5개 팩터(매출·op_margin·below_op·세율·주식수) → 120 순열 전수 계산(비용 무시 가능). 합은 총차이와 정확히 일치.
- **참고 = 고정순서 순차** `revenue → op_margin → below_op → tax → shares` (과거 분기 핸드오프와의 연속성 유지 목적). 두 값을 나란히 기록.
- **레거시 4-lever 접합 — 등식으로 묶지 않는다**(rev3.2 지적 ⑤). `Shapley(below_op) + Shapley(tax) == 순차 OP→NI`는 상호작용 배분 방식이 달라 **일반적으로 거짓**이다. 계약은 다음과 같다:
  1. 5팩터 Shapley를 **독립 계산**(정본)
  2. 기존 4-lever 순차 귀인을 **독립 계산**(`engine/generic_postmortem.py` 유지, 삭제 금지)
  3. 레거시 표시값은 **2번의 결과**를 쓴다(Shapley 합산값으로 대체 금지)
  4. `methodology_bridge_delta = (Shapley_below_op + Shapley_tax) − legacy_OP→NI` 를 기록만 한다. **동일성 테스트를 걸지 않는다.**

---

## 7. 정책 승인 게이트 (P-5 우회 차단)

`policy/approvals.yaml` (사람 커밋 전용):

```yaml
approvals:
  - policy_sha256: "..."          # 승인 대상 정책 파일의 내용 해시
    approved_by: "jiwon"
    approved_at: "2026-08-..T..:..:..Z"
    policy_commit: "<정책 파일이 들어간 **선행** 커밋 SHA>"
```

> ⚠ rev3.2의 `approval_commit`(자기 자신을 포함하는 커밋 SHA)은 **생성 불가능한 자기참조**였다(지적 ④). 승인 레코드는 정책 커밋 **이후의 별도 커밋**으로 남기고, 레코드는 선행 `policy_commit`을 가리킨다.
>
> `approved_by` 문자열은 서명이 아니다. 그리고 레코드에는 "자신이 담긴 커밋 SHA"가 없으므로 **런타임이 어느 커밋을 검증할지 스스로 찾아야 한다.** 4단계 게이트:
>
> 1. **승인 커밋 결정론적 탐색**: `git log --follow --diff-filter=AM --reverse -- policy/approvals.yaml`을 순회하며 **해당 `policy_sha256` 레코드를 최초로 도입한 커밋**을 찾는다(가장 이른 것 1개. 복수 후보면 `POLICY_AMBIGUOUS_APPROVAL`).
> 2. **서명 검증**: 그 커밋에 대해 `git verify-commit`(GPG/SSH) 통과.
> 3. **signer allowlist**: 서명자 fingerprint가 `config/autopilot.yaml:approver_fingerprints`에 있을 것. **임의 signer의 유효 서명은 통과시키지 않는다.**
> 4. **ancestry**: 그 커밋이 **보호된 원격 기본 브랜치(`origin/main`)의 조상**일 것.
>
> 하나라도 실패 → `POLICY_NOT_APPROVED`.

- 런타임은 **경로명이 아니라 활성 정책 파일의 SHA가 allowlist에 있는지** 검사한다. 없으면 `POLICY_NOT_APPROVED`로 동결 중단.
- `config/autopilot.yaml`이 다른 정책 파일을 가리키도록 바뀌어도, SHA 미승인이면 통과 못 한다.
- 자동 제안 브랜치는 **`ledger/proposals/**` 외 경로 변경 시 거부**(세션이 커밋 전 diff 검사).
- `required_commit` 갱신도 활성 정책 SHA 승인 레코드를 포함해야 유효.

---

## 7-b. 동결 증명 계약 (P-3 정정)

git author/committer 타임스탬프는 로컬에서 임의 설정 가능하므로 **동결 시각의 증거가 아니다.** 증명 가능한 명제는 "**원격이 프린트 전에 이 커밋을 수신했다**"뿐이다.

동결 증거 레코드(`reports/frozen/<lane>/<event_key>.md` 헤더 + 원장):

| 필드 | 검증 방법 |
|---|---|
| `frozen_commit_sha` | 커밋 생성 |
| `push_status` | push 성공 여부(실패 시 성공 표기 금지) |
| `remote_ancestry_verified` | push 후 `git fetch` → `git merge-base --is-ancestor <sha> origin/<branch>` |
| `remote_observed_at` | ancestry 확인을 수행한 시각(UTC). "원격이 이 시점엔 갖고 있었다"의 상한 |
| `signed` | 가능하면 signed commit(선택) |

**판정**: `push_status=OK` **AND** `remote_ancestry_verified=true` **AND** `remote_observed_at < announcement_at_utc` 일 때만 **`FREEZE_PROVEN`**. 그 외에는 **`FREEZE_UNPROVEN`** — 동결 산출물은 남기고 채점도 하되, **원장에 "프린트 전 동결"로 집계하지 않는다.**

## 8. 테스트 (신규/개정)

- `test_resolver_determinism.py` — 2회 실행 바이트 동일, py3.11/3.12 직렬화 동일, `datetime.now`/`random` AST 부재
- `test_r1_r2_formula.py` — 합성 데이터로 손계산 대조(중심화 후 슬롯효과 합 0, 축소 단조성)
- `test_r3_winsorize.py` — **치환이지 제거가 아님**(n 불변), type 7 분위수 값 대조, 세전≈0 제외, fallback 사다리, `bull ≤ base ≤ bear`
- `test_r4_r5.py` — 대칭 밴드·floor, 로그드리프트 클리핑, split 정규화
- `test_r7_calibration.py` — 대상 분기 제외, metric/horizon 분리, 정책 변경 시 잔차 재계산 강제, EPS는 레벨 공간, **`op_margin`은 level_delta**(적자·흑전 합성 시나리오에서 예외 없이 계산됨), OP 금액 밴드는 `revenue × margin_band` 파생
- `test_vintage_lookahead.py` — `accepted_at > as_of` 배제, restated fact 미침투, YTD 역산 거부, origin별 `vintage_view_sha`
- `test_selection_rules.py` — 세그먼트 축 포함 컨텍스트 배제, 중복 accession 채택 규칙, tie-out 초과 시 `DATA_BLOCKED`, **선택 결과 레코드에 후보 전체+선택본 기록**, raw fact에 `selection_rule_id` 부재
- `test_collection_completeness.py` — 열거된 accession/document/context 미적재 시 `DATA_BLOCKED`, 문서 해시 불일치 감지, 기대 후보 수 미달 감지
- `test_inputs_schema_no_derived.py` — 파생 키 거부
- `test_policy_approval.py` — 미승인 SHA면 동결 중단, 경로 스위칭 우회 불가, **승인 커밋 탐색이 결정론적**(레코드 최초 도입 커밋 1개), 미서명 거부, **allowlist 밖 signer의 유효 서명도 거부**, `origin/main` 조상 아님 → 거부, `policy_commit`이 선행 커밋인지 검사
- `test_lanes_and_attribution.py` — 5필드 동일성 강제(`comparison_policy_sha` 포함), `human_late` **혼합 집계 거부**, Shapley **efficiency**(합 = 총차이, 1e-9) + **permutation 불변성**, 고정순서 병기.
  **레거시 접합 테스트는 항등식으로 검증한다**: `recorded_delta == shapley_below_op + shapley_tax − legacy_op_to_ni` (1e-9). **금지되는 것은 `recorded_delta == 0` 주장뿐**이다. (rev3.3의 "값 assert 금지"는 잘못 계산된 delta도 통과시키므로 폐기)
- `test_freeze_proof.py` — `push_status=OK` + ancestry true + `remote_observed_at < announcement_at_utc`일 때만 `FREEZE_PROVEN`, push 실패 시 `FREEZE_UNPROVEN`이고 원장 집계에서 "프린트 전 동결"로 세지 않음
- `test_overlay_lanes.py` — `machine_base`는 오버레이 유무와 무관하게 동일 출력 / `machine_overlay_approved`에 미승인 레코드 미침투 / `machine_overlay_proposed`만 제안 반영 / 레인별 R3 표본 차이 재현
- `test_human_lane_cutoff.py` — 커밋 시각 ≤T-72 → `human`, >T-72 → `human_late`, 경계 동시각 포함 규칙

## 9. 수용 기준

상위 문서 §7(수용 기준 11항) + ① R1~R7이 정책 상수만으로 재현 ② `accepted_at` 기반 룩어헤드 위반 0 ③ backtest origin별 빈티지 SHA 존재 ④ 미승인 정책으로 동결 불가 ⑤ Shapley 합 = 총차이(부동소수 오차 1e-9 이내).

## 10. 사람 결정 대기

- `policy/resolver_policy_v1.yaml` **초기 상수 승인**(§2 전체) — 특히 R2 가중치 `[.4,.3,.2,.1]`, R3 분위수 .10/.90, R4 밴드 분위수 .80, R6 확률 `.50/.25/.25`
- `policy/selection_rules_v1.yaml` 태그 우선순위(metric별) 승인
- P0 SHA, PAT 발급·push 검증
- 파일럿에서 사람 레인 참여 여부
