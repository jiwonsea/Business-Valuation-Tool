# Plan v11: 3-Statement + Forward — **설계 확정. PLAN 리뷰 종료.**

**Status:** ✅ **설계 확정** — 구현 착수 가능 (선행 태스크부터)

**Codex 10차 판정:** C1 **닫힘** / C2 **수학 계약 닫힘** / C3 **분리 완료** / C4 **닫힘** → *"이 네 항목 반영 후 PLAN 리뷰를 종료하고 선행 태스크 E1부터 실행해도 됩니다."*

| 계약 | 상태 | 절 |
|---|---|---|
| **C1** scenario-aware Ref + Excel-compatible AST (Solve 없음) | ✅ **닫힘** | §2 |
| **C2** debt/cash regime + 세금·배당 순환 | ✅ **닫힘** | §3 |
| **C3** quota reservation | 🔀 **분리 완료** → `PLAN_E1_llm_instrumentation.md` + E2 | §4 |
| **C4** candidate·fallback 권한 행렬 | ✅ **닫힘** | §5 |

### v11이 추가하는 것: **구현 안전 계약 4건** (§3-11)

아키텍처 변경이 아니라, **구현자가 조용히 틀릴 수 있는 구멍을 막는 계약**이다.

| # | 계약 | 막는 사고 |
|---|---|---|
| **a** | **`LinearForm` 선형성 검증기** + `NonLinearConstraintError` | regime 내부에 `MAX`/`IF`가 남았는데 **선형이라 가정하고 푸는 것** |
| **b** | **Singular determinant 처리** (`SingularRegime` → 다음 regime → 전부 singular이면 `IncompleteForecast`) | 특이해를 **조용히 통과시키는 것** |
| **c** | **이자 전액 세무공제 가정 명시** + **`tax_rate` 단위 고정**(소수, `0 ≤ t ≤ 1`) | `22`와 `0.22`의 **단위 혼동** |
| **d** | **Unsupported feature 결정표** (`value_only`는 **외부 확정값이 있을 때만**, 없으면 `IncompleteForecast`) | NOL·PIK를 **경고만 하고 틀린 숫자를 계속 내는 것** |

> 🔴 **"경고 또는 value-only"는 정책이 아니었다.** 구현자에게 선택지를 열어두면 NOL을 무시하고 경고만 띄운 채 계산을 계속한다. **feature별로 결과를 확정했다** (§3-2).

**개정:** v1 → … → v9 → v10 → **v11 (최종)**

---

## 0. 🔴 v6의 과잉 주장 정정

**v6는 "주간 파이프라인이 이미 quota를 위반 중"이라고 단정했다. 이건 증명되지 않았다.**

`scheduler/weekly_run.py:410`의 `calls_per_company = 6`은 **예산 추정용 상수와 주석**이다. 실제 소비량은 캐시 히트 / two-pass 여부 / repair / fallback provider / optionality / news summary 캐시 / 실패·재시도에 따라 달라진다.

| | 판단 |
|---|---|
| ✅ **확정** | 현재 scheduler가 **6콜/기업을 예산 추정에 사용한다** |
| ✅ **확정** | `10 × 6` 이라는 **scheduler의 가정**은 내부 50콜 정책과 **충돌한다** |
| ✅ **확정** | `effective_budget = max(llm_budget, WEEKLY_LLM_BUDGET)`은 **실제 잔여를 무시하는 가상 예산이다** |
| ❌ **미확정** | 실제 주간 실행이 **항상** 6콜/기업을 소비한다 |
| ❌ **미확정** | 최근 실제 run이 **정말 60콜을 소비했다** |

**→ 태스크 E를 둘로 쪼갠다. 계측(E1)이 먼저다. 실측 없이 "위반 중"이라고 말하지 않는다.**

---

## 1. 아키텍처 (v6 유지)

```
L0 INGEST   결정론  pipeline/            FactObservation[]  (v3 계약)
L1 MAP      하이브리드 YAML head + 🤖A1 tail + 승격 + 권한행렬       §5,§8
L2 CONSTRAIN 순수  engine/fs_model.py    ConstraintModel + SweepPolicy   §3
L3 LOWER    순수   engine/fs_solve.py    ★ 기간별 로컬 regime lowering → Piecewise   §3
L4 GRAPH    순수   engine/fs_graph.py    ★ Excel-compatible final DAG (Solve 없음)   §2
            ├─ engine/fs_eval.py     → Decimal
            └─ output/fs_compile.py  → Excel 수식 (Layout 바인딩)
L5 DRIVERS  🤖A2   결정론 baseline + LLM 조정치                      §8
L6 VERIFY   결정론 engine/fs_checks.py → 게이트 → 🤖A3(미분류만)      §7
L7 RENDER   결정론 output/sheets/
```

---

## 2. C1 — 마감 조건 2건

### 2-1. `Coords.ext` 검증 (중요4)

v6의 `ext: frozenset[tuple[str,str]]`는 escape hatch로는 괜찮지만 **core dimension으로 쓰면 위험하다:** 오타가 조용히 새 차원을 만들고, 같은 key의 복수 값이 들어가고, 값 타입이 문자열로 축소되고, 미지원 차원을 컴파일러가 놓친다.

```python
@dataclass(frozen=True)
class Coords:
    # ── 핵심 차원: 명시 필드 ──────────────────────────
    period:      Period
    scenario:    str  = "Base"
    entity:      str  = "consolidated"
    scope:       Scope = Scope.FORECAST
    currency:    str  = "KRW"                # ★ 명시 필드로 승격
    restatement: str  = "current"            # ★ 명시 필드로 승격 (as_of 뷰)
    # ── 실험적 차원만 ext ─────────────────────────────
    ext: frozenset[tuple[str, str]] = frozenset()   # namespaced only: "x.foo"
```

**규칙:**
- `ext` key는 **namespaced 접두사 필수** (`x.`) — 핵심 차원 오타가 ext로 새지 않는다
- **key registry** + **duplicate-key validator**
- **Layout이 모르는 ext key가 있으면 에러** (조용히 무시 금지)
- **factory(`Ref.of()`)에서만 생성.** constructor 직접 호출 제한

> 완전한 generic Dimension 시스템은 **필요 없다.**

### 2-2. 반올림: `ROUND_HALF_UP` 고정 (개선1)

- **Excel `ROUND`** = midpoint를 **0에서 멀어지는 방향**으로
- **Python `Decimal`의 `ROUND_HALF_UP`** = 이에 대응
- **Python 내장 `round()` = banker's rounding → 사용 금지** (정적 검사로 막는다)

**추가 계약:**
- Decimal 상수를 **짧고 정규화된 decimal literal**로 출력 (Excel의 binary float 표현 차이 완화)
- **의미론적 경계에서만 명시적 `ROUND`.** 모든 중간 셀을 과도하게 반올림하지 않는다
- CI parity는 **최종 통화 tolerance** 적용

### 2-3. Piecewise 폭발 방지 (중요5)

**폭발하지 않는다 — 단, 규칙을 명시해야 한다:**
- **각 기간의 regime은 그 기간의 로컬 Piecewise** (year × scenario당 5분기)
- **전년도 결과는 `Ref`로 참조**
- 🔴 **5년 전체 regime sequence를 하나의 거대 Piecewise로 전개 금지** (Cartesian product = 5^5)
- 공통 조건식은 **DAG node로 공유**
- 컴파일러가 같은 subtree를 반복 인라인하지 않도록 **보조 셀 또는 named expression** 사용

### 2-4. 날짜·lookup 연산 (개선2)

**annual v1 + `interest_timing=average_balance` + covenant step 제외** 조건에서는 **불필요하다.**

**필요해지는 시점 (IR 확장 = 범위 밖):** stub period / 비12월 결산의 달력연도 변환 / mid-year discounting / 실제 draw·repayment 날짜 / 일수 기반 DSO·이자.

---

## 3. C2 — Sweep Policy + Eligible Regime (치명4, 중요7)

### 3-1. v6의 우선순위는 정책과 반대로 작동한다

v6는 `no_transaction`을 `full_sweep`보다 **먼저** 뒀다. **opening revolver가 있고 잉여현금도 있는 상태에서 `no_transaction`이 허용되면, 첫 regime에서 정합 판정을 받아 sweep이 영원히 실행되지 않는다.** mandatory sweep이면 `no_transaction`은 **애초에 후보가 아니어야 한다.**

### 3-2. Sweep을 정책으로 모델링한다

```python
class SweepPolicy(BaseModel):
    mode:       Literal["none", "optional", "mandatory"] = "none"    # 기본값 none
    sweep_pct:  Decimal = Decimal("1")               # 잉여의 몇 %를 상환에 쓰는가
    annual_cap: Money | None = None
    source:     Literal["manual", "profile"] | None = None   # ★ Optional + default
    evidence:   Source | None = None                 # mandatory 시 대출계약 근거
```

🔴 **`source`는 반드시 Optional + default여야 한다** (Codex 8차 치명1). v8은 `source`를 필수로 뒀는데, **`mode="none"`인 기본 `SweepPolicy`조차 생성되지 않고**, `source` 필드가 없는 **기존 YAML 프로필이 전부 깨진다.**
> CLAUDE.md: *"새 YAML 프로필 필드는 Optional + defaults여야 한다 (backward compatibility)."* — 이걸 위반했다.
> **새로 추가되는 상위 필드(`sweep_policy` 자체)도 Optional + default를 제공한다.**

**조건부 validation:**
| `mode` | `source` | `evidence` | 기타 |
|---|---|---|---|
| `none` | 불필요 | 불필요 | sweep = 0 |
| `optional` | **필수** | 불필요 | 선택한 것 자체가 활성 |
| `mandatory` | **필수** | **필수** | **`sweep_pct > 0` 강제** |

- **`optional` → 선택한 것 자체가 활성이다.** (v8의 "optional 활성/비활성" 2상태는 폐기 — 비활성 optional은 사실상 `none`이다.)
- **LLM은 직접 설정할 수 없다.** 제안만 가능 (`source ∈ {manual, profile}`).

#### 🔴 `sweep_base` — v7의 `excess_fcff`는 폐기 (Codex 7차 치명4)

v7은 `sweep_base: excess_cash | excess_fcff`를 뒀다. **`excess_fcff`는 의미가 불명확하다:**
- 엄밀한 **FCFF는 unlevered**이므로 이자와 무관하다 → "이자 때문에 순환한다"는 v8 이전의 우려는 **틀렸다**
- 그러나 **실제 대출계약의 excess cash flow sweep은 FCFF와 다르다** — 세후이자·의무상환·허용 공제가 들어간다
- 그대로 두면 **구현자마다 다른 금액을 sweep한다**

**v1 계약: `excess_cash`만 지원.** 계약형 ECF(CFADS 계열, 세후이자·의무상환·허용 공제 반영)는 **Phase 2에서 별도 정의**한다. `excess_fcff`라는 이름은 **쓰지 않는다.**

#### `pre_revolver_cash_change` 정확한 정의 (Codex 8차 중요1·2)

v8은 `CFO`라는 명칭을 썼고 `non-revolver CFF`의 범위를 명시하지 않아 **이중 차감 위험**이 있었다.

🔴 **`CFO`라는 명칭을 쓰지 않는다.** IFRS와 US-GAAP은 **이자 지급·수취의 CF 분류가 다르다** (IFRS는 CFO/CFF 선택 가능). 총현금에는 영향이 없지만 **CF 시트 표시와 tie-out에는 영향을 준다.** 해석적 solve에서는 **분류 중립적인 항**을 쓴다.

🔴 v9의 `operating_cash_flow_pre_interest`는 **세금 포함 여부가 불명확**했다 (Codex 9차 치명2). `pre_interest`만 뜻한다면 세금이 이미 들어 있어 **`− cash_tax`에서 이중 차감**된다.

#### v1 현금 계약 — 이 블록이 유일한 정의다 (Codex 9차 개선1)

```python
# ★ 각 line을 별도로 유지하고 합계는 마지막에. 이름이 곧 계약이다.
  OCF_pre_interest_and_tax              # ★ 이자 AND 세금 제외 (아래 EXCLUDES)
− cash_interest_expense                 # ← D_close 의존 (symbolic)
+ cash_interest_income                  # ← C_close 의존 (symbolic)
− cash_tax                              # ← §3-5 Piecewise (tax regime)
+ investing_cash_flow
+ other_cff_excluding_debt_and_dividends
− scheduled_term_debt_repayment         # 외생, 리볼버 판정 이전
− dividends_paid                        # ← §3-5 외생화 (전기 NI 기준)
─────────────────────────────────────
= pre_revolver_cash_change

cash_before_revolver = opening_cash + pre_revolver_cash_change
excess_cash          = max(0, cash_before_revolver − min_cash)
```

**`OCF_pre_interest_and_tax` — 반드시 EXCLUDES:**
```
- cash interest paid
- cash interest received
- cash taxes
- dividends
- debt transactions
```

**`other_cff_excluding_debt_and_dividends` — 반드시 EXCLUDES:**
```
- scheduled_term_debt_repayment    ← 위에서 이미 차감
- dividends_paid                   ← 위에서 이미 차감
- revolver_activity (draw / sweep) ← 미지수
```

**포함되면 이중 차감된다.** 이름에 제외 항목을 박아넣는 이유가 이것이다 — parser·builder 구현자가 **서로 다른 정의를 쓰는 것을 막는다.** 각 line의 IS/BS/CF 대응 관계를 **fixture로 검증**한다.

#### 🔴 v1 단순화 — 명시적으로 선언한다 (Codex 9차 중요1·2)

**숨기면 "IS의 세금과 CF의 세금이 왜 우연히 같은지" 설명할 수 없다.**

```yaml
# 세금
cash_tax = current_tax                    # ★ v1 가정
deferred_tax:            0                # 미지원
change_in_tax_payable:   0                # 미지원
prepaid_tax / 과거연도 정산 / 분할납부:    미지원

# 이자
cash_interest_expense = interest_expense_pnl    # ★ v1 가정 (발생 = 현금)
cash_interest_income  = interest_income_pnl
accrued_interest_payable/receivable:  unsupported
PIK_interest:                         unsupported
capitalized_interest:                 unsupported
debt_issuance_fee_amortization:       unsupported
```

#### 🔴 Unsupported feature 결정표 — "경고 또는 value-only"는 정책이 아니다 (Codex 10차 치명1)

v10은 구현자에게 **두 선택지를 열어뒀다.** 그런데 NOL·PIK·자본화이자처럼 **숫자에 직접 영향을 주는** 기능을 미지원한 채 **경고만 띄우고 계산을 계속하면 모델이 틀린 숫자를 낸다.** feature별로 **결과를 확정한다:**

| 입력에 존재 | live formula | 외부 확정 forecast 값 있음 | 없음 |
|---|---|---|---|
| **NOL carryforward** | ❌ 미지원 | `value_only` | **`IncompleteForecast`** ※ |
| **PIK interest** | ❌ 미지원 | `value_only` | **`IncompleteForecast`** |
| **capitalized interest** | ❌ 미지원 | `value_only` | **`IncompleteForecast`** |
| **covenant step** | ❌ 미지원 | `value_only` | **`IncompleteForecast`** |
| **minimum tax / tax credit** | ❌ 미지원 | `value_only` | **`IncompleteForecast`** |
| **interest deduction limitation** | ❌ 미지원 | `value_only` | **`IncompleteForecast`** |

※ NOL은 예외적으로 **명시적 `nol_ignored: true` manual override**가 있으면 진행 가능 (사용자가 무시를 의도했음을 선언).

🔴 **`value_only`의 의미를 좁힌다:** "BVT가 모르는 계산을 몰래 한다"가 **아니라**, **외부에서 제공된 확정 값을 그대로 쓴다**는 뜻이다. 확정 값이 없으면 **`value_only`가 아니라 `IncompleteForecast`다.**

**침묵 금지:** 미지원 입력을 조용히 무시하지 않는다. "구현하지 않았다"와 "입력을 삼켰다"는 다르다.

#### `Money` 정합 검증 (Codex 8차 중요4)

`annual_cap`, `min_cash`, `D_open`이 서로 다른 currency/scale이면 **`min()`이 의미가 없다.**

```
필수 검증:
  - 동일 currency
  - 동일 internal scale로 정규화
  - annual_cap >= 0
  - 0 <= sweep_pct <= 1
  - D_open >= 0
  - commitment >= D_open   (아니면 명시적 covenant breach)
```

#### `annual_cap` — `None`과 `0`은 다르다 (Codex 8차 중요3)

```python
# ❌ 금지
cap = annual_cap if annual_cap else INF        # 0이 "cap 없음"으로 둔갑

# ✅
cap = annual_cap.amount if annual_cap is not None else INF
```
**명시적 `0` cap은 "cap 없음"이 아니라 "sweep 0"이다.** 이 구분이 무너지면 sweep이 조용히 무제한 실행된다.

### 3-3. 🔴 Sweep 수학 — v8의 오류 3건 수정 (Codex 8차 치명1·2·3)

#### 오류① "`sweep_pct < 1`이면 `full_sweep` 불가" — **틀렸다**

잉여현금 **규모**를 고려하지 않은 주장이었다.
```
D_open = 100,  excess_cash = 1,000,  sweep_pct = 50%
→ 허용 sweep = 500  →  부채 100을 전액 상환  →  FULL SWEEP이다
```
"잉여를 다 쓰는 것"과 "부채를 다 갚는 것"을 혼동했다.

#### 오류② `partial_sweep`에서 `C_close = min_cash` — **틀렸다**

`pct < 1`이거나 cap이 binding이면 **상환 후에도 현금이 최소현금보다 높게 남는다.**
```
pre_sweep_cash = 1,000,  min_cash = 100,  excess = 900,  sweep_pct = 50%
→ S = 450  →  C_close = 550       ← min_cash(100)가 아니다
```

#### ✅ 올바른 계약

```python
S = allowed_sweep = min(
        sweep_pct × excess_cash,              # percentage 제한
        annual_cap if annual_cap else ∞,      # cap 제한
        D_open,                               # 부채 잔액 제한
    )

D_close = D_open − S
C_close = cash_before_revolver_activity − S     # ★ min_cash로 고정하지 않는다

full_sweep     iff  S >= D_open − ε
partial_sweep  iff  0 < S < D_open − ε
```

#### 오류③ `mandatory`에서 `no_transaction` **무조건** 제외 — **틀렸다**

`mandatory`여도 **required sweep이 0**인 경우가 있다: `excess_cash = 0` / `sweep_pct = 0` / `annual_cap = 0` / `D_open = 0`.
이때 sweep regime은 성립하지 않는데 `no_transaction`도 제외되면 **아무 regime도 남지 않는다.**

**eligibility는 정책 *이름*이 아니라 계산된 *의무액*을 기준으로 한다:**
```python
required_sweep = min(sweep_pct × excess_cash, annual_cap, D_open)   # mandatory 시

if required_sweep > ε:   eligible = sweep regimes만
else:                    eligible = no_transaction 허용
```
**schema validation에서 `mandatory` → `sweep_pct > 0`을 강제한다.**

### 3-4. Regime 표 — **binding constraint 기준** (Codex 8차 개선2)

정책 이름이 아니라 **어느 제약이 binding인가**로 나눈다.

| 순위 | Regime | binding (활성 제약) | 해 |
|---|---|---|---|
| 1 | `no_transaction` | 없음 (`S = 0`, `D_close = D_open`) | **joint linear system → lowered closed form** |
| 2 | `sweep_debt_binding` (= full sweep) | `S = D_open` → `D_close = 0` | ↑ |
| 3 | `sweep_pct_binding` | `S = pct × excess` | ↑ |
| 4 | `sweep_cap_binding` | `S = annual_cap` | ↑ |
| 5 | `draw` | `C = min_cash`, `D < commitment` | ↑ |
| 6 | `draw_at_commitment` | `D = commitment` | ↑ → **`LiquidityShortfall`** |

#### 🔴 `D = K/(1−r)`는 폐기한다 (Codex 9차 치명1)

v9까지 `draw` regime의 해를 **`D = K/(1−r)` 고정 공식**으로 남겨뒀다. **세금을 도입한 순간 틀렸다** — **이자가 세금을 줄이기 때문이다:**

> ⚠️ **아래는 직관을 위한 *설명 예시*이지 계약이 아니다** (Codex 10차 개선1). opening debt와 현금 이자수익이 들어간 완전한 2×2 시스템에서는 **최종 분모가 정확히 이 모양이 아닐 수 있다.**

```
[설명 예시 — 단순화 조건: opening_debt = 0, 이자수익 = 0, 미지수 1개, 전액 공제]
interest  = r × draw
cash_tax  = (EBT_pre_interest − interest) × tax_rate      ← tax_positive regime
→ 리볼버 증가의 순현금 비용 ≈ interest × (1 − tax_rate)

tax_zero      :   draw = K / (1 − r)
tax_positive  :   draw = K / (1 − r × (1 − tax_rate))     ★ 계수가 다르다
```

여기에 **현금 이자수익과 opening debt까지 넣으면 `(·, C)` 2×2 연립**이다. **어떤 고정 공식도 계약으로 남길 수 없다.**

#### 🔴 미지수의 의미를 고정한다 (Codex 10차 중요5)

위 예시는 `draw`를 쓰고 regime 표는 `D_close`를 쓴다. **섞으면 opening-debt 이자 항이 constant 쪽에서 누락된다.**

```
D_open                                    # 기초 (기지)
draw_amount   >= 0
sweep_amount  >= 0
D_close = D_open + draw_amount − sweep_amount
```
**계수행렬의 미지수는 `(D_close, C_close)`로 고정한다.** `draw_amount`/`sweep_amount`는 **파생값**이다 (regime이 둘 중 하나를 0으로 고정하므로 유일하게 복원된다).

**v10 계약:**
```
각 joint regime (tax × liquidity) 에서:
    coefficient matrix 를 세우고  →  lowering 단계에서 **상징적으로(symbolically)** 푼다
    →  regime별 lowered closed-form expression 을 얻는다
```
- **일반 `Solve` 노드는 최종 AST에 남기지 않는다** (C1 유지).
- 그러나 **lowering 단계에서는 계수행렬을 상징적으로 풀어야 한다.** 손으로 유도한 공식을 박아넣지 않는다.
- **`§3-4`의 표는 "어느 제약이 binding인가"만 정의하고, 해는 lowering이 생성한다.**

**감사 정보 보존 (Codex 9차 개선2):** 각 joint regime에 `matrix_coefficients` / `determinant` / `closed_form_expr` / `eligibility_conditions`를 남긴다 → 특이해 진단과 Python·Excel parity 실패 분석에 필수.

- `pct`와 `cap`이 **동시에 같은 값**이 되는 경계에서는 **고정 우선순위로 label만** 결정한다 (경제적 결과는 동일).
- **`cash_floor`(min_cash)는 `excess_cash` 정의에 이미 흡수**되어 있다 (§3-2).
- **각 joint regime 내부는 선형** → 닫힌 식. `excess_cash`가 `D_close`에 의존하는 순환도, **세금이 이자에 의존하는 순환도** 이 선형계 안에서 풀린다.

**추가 불변식:**
- **`draw`와 `sweep`은 상호배타**다 (같은 기간에 둘 다 활성 금지)
- **정기차입(term debt) 의무상환은 외생**이며 **리볼버 판정 이전에** 현금흐름에 반영된다 (리볼버와 분리)
- **term-debt 의무상환 후 리볼버 draw는 허용한다** (이건 상호배타 위반이 아니다 — 다른 부채다)

#### Annual netting convention (Codex 7차 중요6)

연간 모델에서 `draw`·`sweep` 상호배타는 **허용 가능한 근사**다. 실제로는 분기별로 인출 후 상환할 수 있지만, 연간 ending balance 모델은 **net movement로 단순화**한다.

**대가로 잃는 것 — Assumptions 시트에 명시한다:**
- **gross draw / repayment CFF를 재현하지 못한다** (net만 나온다)
- **commitment fee · transaction fee가 왜곡될 수 있다**

→ Assumptions에 **"annual netting convention"**을 표기한다. 숨겨진 가정으로 두지 않는다.

### 3-5. 🔴 세금·배당 순환 — v9 마감 (Codex 8차 치명2)

v8의 **"각 sweep regime 내부는 선형"**은 **틀렸다.** 실제 3-statement에는 두 개의 `max(0, ·)`가 더 있다:

```
interest → EBT → tax = max(0, EBT × rate) → NI → dividend = max(0, NI) × payout
         → cash → revolver → interest        ← 원점
```

**v1 계약 — 세금은 Piecewise, 배당은 외생화:**

```yaml
tax:
  current_tax = max(0, EBT × tax_rate)     # ★ Piecewise lowering (2분기)
  NOL_carryforward: 제외                   # v1 범위 밖 (경로의존 state)
  minimum_tax / tax_credit: 제외

dividend:
  policy: exogenous                        # ★ 외생화 — 순환을 끊는다
  # 우선순위 (Codex 9차 중요5) — 둘 다 존재할 수 있으므로 명시:
  #   1) 명시적 dividend schedule (DriverSet)     ← 있으면 이것이 우선
  #   2) max(0, prior_year_NI) × payout_rate      ← KR 결산배당 관행과 일치
  #   3) 0
  # ※ max(0, ·)는 **전년도 확정 Ref**에 적용된다 → 동일 연도 순환을 만들지 않는다
  #   (음수 전기 NI에서 배당이 음수가 되는 것을 막는다)
  dividend_floor / dividend_cap: 제외
  prior_dividend_maintenance: 제외
```

**왜 이 조합인가:**
- **세금**은 `EBT` 부호에 대한 **2분기 Piecewise**로 충분히 표현된다. `EBT`가 `D_close`에 선형 의존하므로, **각 분기 안에서는 여전히 선형**이다. → lowering 가능.
- **배당**을 당기 `NI`에 연동하면 `max(0, NI)`가 또 하나의 분기를 만들고, `NI`가 `interest`에 의존하므로 **순환이 닫히지 않는다.** 외생화하면 **루프가 끊어진다.** 게다가 **(a)는 한국 기업의 결산배당 관행(전기 실적 기준)과 실제로 일치**한다 — 근사가 아니라 오히려 더 정확하다.
- **NOL**은 경로의존 state(전년 이월결손)라 연도 간 결합을 만든다. v1 제외. (§2-3에서 unroll로 표현 가능하다고 했으나, 이번 범위에서는 **넣지 않는다**.)

### 3-6. Joint Regime — 세금 × 유동성

lowering은 **(세금 분기 × 유동성 regime)** 결합 공간을 전개한다:

```
tax_regime       ∈ { tax_positive (ROUND(EBT) > ε),  tax_zero (ROUND(EBT) <= ε) }   2
liquidity_regime ∈ { no_transaction, sweep_debt_binding, sweep_pct_binding,
                     sweep_cap_binding, draw, draw_at_commitment }                   6
                                                          ──────────────────────────
joint regime — **최대 후보 수** (year × scenario 당)                                12
```

> 🔴 **12는 "최대 후보 수"이지 항상 평가하는 유효 regime 수가 아니다** (Codex 9차 중요3).
> **policy/state eligibility를 먼저 적용하고(§3-3), 남은 joint regime만 평가한다.** (`D_open == 0`이면 sweep 3종이 사라지고, `mode="none"`이면 또 줄어든다.)

- **세금과 유동성은 결합해서 풀어야 한다** — 세금이 현금을 바꾸고, 현금이 리볼버를 바꾸고, 리볼버가 이자를 바꾸고, **이자가 `EBT`를 바꿔 세금 분기를 뒤집을 수 있다.**
- **각 joint regime 안에서는 모든 식이 선형** → lowering이 **상징적으로** 푼다 (§3-4). **이제 이 주장이 참이다.**
- 절차: eligible joint regime을 **고정 우선순위**로 순회 → lowered closed form 평가 → **세금·유동성 양쪽 분기 조건을 모두 검사** → 첫 정합 채택.
- **§2-3의 기간별 로컬 규칙 준수:** 12분기는 **해당 year×scenario의 로컬 Piecewise**다. 5년 전체로 Cartesian product(12^5)를 전개하지 **않는다.**

#### 🔴 세금 분기에도 §2-4의 tolerance·rounding 계약을 적용한다 (Codex 9차 중요4)

```
tax_positive  iff  ROUND(EBT, n) >  ε
tax_zero      iff  ROUND(EBT, n) <= ε
```
`EBT == 0` 근처에서 **Python Decimal과 Excel float가 다른 분기를 타면** 세금이 통째로 달라진다. §2-4의 **동일 `ROUND` + `Const(ε)` 규칙을 세금 분기 조건에 명시적으로 연결**한다 (sweep 경계와 같은 계약).

> **covenant step을 v1에서 뺀 이유가 여기서 더 분명해진다** — 이율이 debt에 의존하면 joint regime이 `12 × N`으로 곱해진다.

### 3-7. covenant step — **v1 범위 밖** (중요6)

covenant step은 이율이 debt/EBITDA·ICR에 의존 → **적용이율 → 이자비용 → 순이익·현금 → debt balance → covenant ratio**가 다시 순환한다. 유한 Piecewise라도 검증 범위가 폭증한다.

**v1 계약:** `debt_rate`를 **외생 driver로 고정**. covenant step은 `unsupported_feature` 플래그 → **Excel value-only 또는 Phase 2**.

### 3-8. `interest_timing` (관찰2)

v1은 `average_balance` 고정. 다만 **적자가 심해 실제 draw가 연초에 발생하면 이자를 과소추정**한다.

**필요 장치:** 고금리·대규모 draw 시 **경고** / `beginning_balance`·`end_balance` **민감도 표시** / **Assumptions 시트에 명시** (숨겨진 가정 금지).

### 3-9. 결과 객체 + 상태 (Codex 8차 개선1)

**Sweep 계산을 독립 결과 객체로 분리한다** — Python 결과와 AST 결과를 **같은 fixture로 비교**할 수 있다:

```python
class SweepResult(BaseModel):
    allowed_sweep: Decimal
    debt_close:    Decimal
    cash_close:    Decimal
    binding: Literal["none", "debt", "percentage", "annual_cap"]
    # ★ Codex 9차 중요6 — binding만으론 감사 불가
    liquidity_regime: LiquidityRegime          # no_transaction | sweep_* | draw*
    tax_regime:       Literal["positive", "zero"]
    joint_regime:     str                      # 예: "tax_positive/sweep_pct_binding"
```
**`binding`만 있으면 같은 sweep 결과가 tax-positive였는지 tax-zero였는지 감사할 수 없다.** `joint_regime`은 **Checks 시트와 실패 진단(A3)**에도 그대로 쓰인다.

**최종 상태 (v6 유지):** `Solvent(regime)` / `LiquidityShortfall(unfunded_cash_need, year)` / `IncompleteForecast(missing, reason)` — **엄격히 분리.** shortfall 이후 연도 = `not_projected_due_to_shortfall`.

### 3-10. 🔴 경계 fixture — 동시 binding (Codex 8차 중요5)

경제적 값이 같아도 **컴파일러(Excel)와 evaluator(Python)가 같은 label을 선택해야 한다.** 필수 fixture:

| # | 조건 |
|---|---|
| 1 | `pct × excess == D_open` (percentage와 debt가 동시 binding) |
| 2 | `annual_cap == D_open` |
| 3 | `pct × excess == annual_cap < D_open` |
| 4 | **세 제한이 모두 같음** |
| 5 | 각 값이 **tolerance 안팎** (ε 경계) |
| 6 | `D_open == 0` |
| 7 | `excess_cash == 0` |
| 8 | **`EBT == 0`** (세금 분기 경계 — §3-6) |
| 9 | **세금 분기 × 유동성 regime 동시 경계** |

---

### 3-11. 🔴 구현 안전 계약 (Codex 10차 — 아키텍처 변경 아님)

#### (a) `LinearForm` — 선형성을 **강제**한다 (중요1)

v10은 "계수행렬을 상징적으로 푼다"고만 했다. **AST의 어떤 식이 선형인지 검사하는 계약이 없었다.**

```python
# engine/fs_solve.py 내부
class LinearForm:
    coefficients: Mapping[UnknownRef, Expr]   # UnknownRef ∈ {D_close, C_close}
    constant:     Expr
```

| 허용 | 금지 |
|---|---|
| `unknown + unknown` | ❌ `unknown × unknown` |
| `scalar × unknown` | ❌ `unknown ÷ unknown` |
| `unknown ÷ nonzero scalar` | ❌ **regime 내부에 `MAX`/`MIN`/`IF` 잔존** |
| | ❌ unknown을 포함한 비선형 함수 |

**`Piecewise` 선택은 lowering *이전에* 특정 regime으로 제거되어야 한다.** regime을 고른 뒤에도 `MAX`/`IF`가 남아 있으면 그건 **regime 분해가 불완전하다는 증거**다.

🔴 **선형성 검증 실패 → `NonLinearConstraintError`로 명시적 중단.** 조용히 근사하지 않는다.

#### (b) Singular determinant 처리 (중요2)

`determinant`를 **감사 정보로 저장하는 것만으로는 부족하다.** 동작을 정의한다:

```python
if abs(det) <= determinant_tolerance:
    → SingularRegime
    → 해당 regime 부적격 처리
    → 다음 eligible regime 검사

if 모든 eligible regime이 singular:
    → IncompleteForecast(reason="singular constraint system")
```

**단, 원인이 비현실적 금리(계수가 1에 근접)라면** `IncompleteForecast`보다 **driver validation 오류가 더 정확하다** → §8의 드라이버 경계 검증(`0 ≤ debt_rate ≤ 1` 등)이 **먼저** 잡아야 한다. singular까지 내려왔다는 건 검증이 샜다는 뜻이다.

#### (c) 세금 가정을 완전히 명시한다 (중요3·4)

§3-4의 세금방패 계수는 **이자가 전액 세무상 공제될 때만** 맞다.

```yaml
interest_tax_deductibility: 100%          # ★ v1 가정
interest_deduction_limitation: unsupported   # EBITDA 대비 한도 등 → regime 추가됨
nondeductible_interest:        unsupported
```
**이자공제 한도가 존재하면 세금 regime이 하나 더 생긴다** (공제 한도 binding). v1 범위 밖 → §3-2의 결정표에 따라 `value_only` 또는 `IncompleteForecast`.

**`tax_rate` 단위 — 하나로 고정한다:**
```
DriverSet의 모든 rate는 소수(fraction)다.    22% → Decimal("0.22")
검증: 0 <= tax_rate <= 1
```
🔴 기존 프로젝트는 **일부 세율을 `%` 단위(22)로 쓴다** → Decimal forward layer에서 **단위 혼동 위험**. `DriverSet` 경계에서 **명시적으로 변환**하고, 범위 검증으로 사고를 막는다 (`22`가 들어오면 `tax_rate <= 1` 위반으로 즉시 잡힌다).

#### (d) 해 검증 = **residual 검사** (개선2)

symbolic expression의 **문자열이 예상 모양인지만 검사하면 algebra 오류를 놓친다.** 각 regime에서:

```
1. A × x − b  residual  <= tolerance      ← 닫힌 해가 원 제약식을 실제로 만족하는가
2. eligibility conditions  == true         ← 고른 regime의 조건이 실제로 성립하는가
3. accounting identities   == true         ← BS balance / CF tie-out
```

**세금방패 회귀 테스트(`1 − r(1−t)`)는 §3-4의 단순화 fixture에서만 적용한다** (opening debt = 0, 이자수익 = 0, 미지수 1개, 전액 공제). **일반 joint regime은 residual로 검증한다.**

#### (e) 배당 source를 결과에 보존 (개선3)

```python
dividend_source: Literal["explicit_schedule", "prior_year_ni_payout", "zero_fallback"]
```
**US 기업(분기배당, 당기 실적 연동)에서 `prior_year_ni_payout` 근사가 쓰였는지** 리포트와 Assumptions에서 확인 가능해야 한다.

---

## 4. C3 — Quota: **이 PLAN에서 분리** 🔀

> **Codex 7차 최종 권고:** *"다음 작업은 PLAN_three_statement.md를 다시 크게 고치는 것보다 E1을 별도 계획으로 떼어내는 것입니다."*

**C3는 3-statement 기능이 아니다.** `api_guard`의 lost update(`:281`)와 이중 계상은 **지금도 발생 가능한 기존 인프라 버그**이고, 3-statement가 없어도 존재한다. API guard / LLM client / scheduler / cache를 건드리는 **독립 기능**이다.

| PLAN | 범위 | 세션 |
|---|---|---|
| **`PLAN_E1_llm_instrumentation.md`** 🆕 | **계측만.** 동작 변경 0. 2계층(workflow/transport) + `contextvars` + JSONL. cold/warm 실측 + 비용 승인 게이트 | **즉시 착수 가능** |
| **E2** (미작성) | 예산·예약. `used`/`reserved`/**`in_flight`** / **heartbeat + lease renewal** / **fallback provider permit** / SQLite / `PolicyBudget` 중심 | E1 실측 후 |
| **이 PLAN** | 3-statement. **E1 실측치로 예산표를 확정한 뒤** 진행 | E1/E2 후 |

### 4-1. External prerequisite (이 PLAN의 DoD 아님)

```
External prerequisite:
    E1 complete   →  PLAN_E1_llm_instrumentation.md
    E2 complete   →  (미작성 — reservation/budget 상세 계약은 E2 PLAN 소유)
```

**C3의 상세 설계·DoD는 E2 PLAN이 소유한다.** 이 PLAN은 링크만 제공한다. (v8은 분리를 선언해놓고 DoD와 임계경로에 C3를 그대로 남겨 모순이었다 — Codex 8차 중요4.)

### 4-2. 이 PLAN이 E1/E2에 **요구하는** 입력 계약

3-statement가 진행되려면 E1/E2로부터 다음이 필요하다. **이것만이 이 PLAN의 관심사다:**

| # | 요구 | 출처 |
|---|---|---|
| 1 | **기업당 실제 HTTP attempt 수** (cold / warm / 부분만료) — step별 | **E1 실측** |
| 2 | **A1·A2·A3 추가분을 얹었을 때의 상한** | E1 실측 + D(A2 spike) |
| 3 | **예산 부족 시 각 step의 행동** (`skip` / `deterministic_fallback` / `abort`) 선언 | E2 |
| 4 | **열화가 발생했음을 산출물·로그·이메일에 기록하는 훅** | E2 |

**각 LLM step의 캐시 miss 시 행동 — 이 PLAN이 E2에 제시하는 요구사항:**

| step | 캐시 miss 시 |
|---|---|
| `classify` | **abort** (밸류에이션 입력 없음) |
| `peers_batch` | deterministic fallback (섹터 평균 멀티플) |
| `wacc` | deterministic fallback (CAPM 기본식) |
| `scenarios` (+A2) | deterministic fallback (§8 결정론 baseline) |
| `news_summary` | skip (뉴스 섹션 생략) |
| `profile_gen` | 신규 회사면 abort / 기존 프로필 있으면 skip |
| **`A1 mapper`** | **skip** (미매핑 유지 → coverage 지표에 노출) |
| **`A3 auditor`** | **skip** (결정론 classifier 리포트만) |

> 🔴 **E1 실측이 끝나기 전에는 이 PLAN의 예산 관련 숫자를 확정하지 않는다.**

---

## 5. C4 — 권한 행렬 (마감 조건)

### 5-1. Materiality — 단일 계정 임계로는 부족 (중요8)

**각 candidate가 0.8%이고 10개면 총 8%다.** 동시에 봐야 한다:

```yaml
# 출발점 — eval fixture로 보정할 것. 영구 상수 아님.
individual_candidate:  < 0.5%
aggregate_candidate:   < 1%
aggregate_unmapped:    < 1%
critical_concepts:     0% tolerance     # ★ 금액 비중과 무관하게 candidate 사용 금지
```

**critical concepts:** `revenue`, `cash`, `total_debt`, `total_equity`, `operating_income`, `capex`
→ **금액이 아무리 작아도 candidate 매핑을 산술에 쓰지 않는다.**

또한 봐야 할 것: **핵심 line 여부 / BS·CF equation residual 영향.**

### 5-2. Coverage — statement별 + critical line별 (중요9)

```yaml
# publish 기준 출발점 — fixture precision/coverage 결과로 조정
IS weighted coverage:  >= 98%
BS weighted coverage:  >= 98%
CF weighted coverage:  >= 95%
critical concepts:     100%
candidate aggregate exposure: <= threshold (§5-1)
BS/CF tie-out:         통과
```
**근거 없는 영구 상수로 확정하지 않는다.**

### 5-3. Mapping tier × 권한 (v6 유지)

| tier | valuation 산술 | Excel 표시 | coverage | 공개 |
|---|---|---|---|---|
| `trusted` / `validated` | ✅ | ✅ | ✅ | ✅ |
| `candidate` | **❌** (§5-1 예외만) | ✅ 회색 + caveat | ✅ 별도 집계 | caveat |
| `unmapped` | ❌ | ✅ raw 섹션 | ✅ | ❌ |

### 5-4. Summary — **3개 스키마가 아니라 같은 스키마의 view** (개선3)

기존 delivery 함수는 전부 `summary["valuations"]`를 순회하고 `status == "success"`만 필터링한다 → **스키마를 바꿀 필요가 없다.**

```python
public_summary   = filter_summary(summary, publication_status={"approved"})
internal_summary = summary                     # 이메일 = 내부 채널
blocked_summary  = filter_summary(summary, publication_status={"internal_review","blocked_incomplete"})
```

🔴 **각 view에서 `status_summary`를 반드시 재계산한다.** 안 하면 **본문엔 approved 6개인데 헤더엔 성공 10개**로 표시된다. (`delivery.py:105`, `:274`가 전달받은 집계를 **그대로 표시**한다 — **중앙 helper에서 재계산**하면 builder 수정 범위가 최소화된다.)

#### 🔴 `status_summary`만으로는 부족하다 — 파생 데이터 전부 (Codex 7차 개선4)

builder들은 `valuations` 외에도 **discoveries / scored companies / Gamma links / news lookup**을 쓴다. **public view에서 최소한 다음을 함께 필터·재계산해야 한다:**

- `status_summary`
- `valuations`
- **company-specific links** (Excel URL, Gamma URL)
- **top picks / 주간 시사점 요약 텍스트**
- 🔴 **공개 제외 기업을 언급하는 discovery·reason 텍스트**

**안 하면:** valuation 카드에서는 빠졌는데 **"주간 시사점"이나 discovery 목록에 `internal_review` 기업이 그대로 남는다.**

### 5-5. Entry-point 방어 (개선4)

**중앙 filtering만 믿으면 안 된다.** standalone CLI로 `post_to_naver(summary)`를 직접 호출하면 gate가 우회된다.

**공개 entry point는 자체적으로 검증한다.**

🔴 **`assert`를 보안 게이트로 쓰면 안 된다** (Codex 8차 중요3) — **Python `-O`에서 제거된다.**

```python
# ❌ 금지
assert all(v["publication_status"] == "approved" for v in valuations)

# ✅ 명시적 검증
if any(v["publication_status"] != "approved" for v in valuations):
    raise PublicationBlockedError(...)
```
**WordPress / Naver / YouTube 모두 동일.**

**빈 public summary 정책 (Codex 8차 중요6):** approved 기업이 **0개**이면 poster는 **오류가 아니라 "게시할 내용 없음"으로 정상 skip**한다. (`PublicationBlockedError`는 *approved가 아닌 항목이 섞여 들어왔을 때*만 던진다 — 비어 있는 것과 오염된 것은 다르다.) skip 사실은 **내부 검토 이메일에 기록**한다.

### 5-6. Storage upload도 권한 행렬에 포함 (개선5)

`weekly_run.py:502` — **Storage upload가 공개 gate보다 먼저다.** Supabase object가 public bucket이거나 이메일/summary URL로 노출되면 **`internal_review` 결과도 사실상 공개**된다.

| status | Storage |
|---|---|
| `approved` | public bucket |
| `internal_review` | **private bucket + signed URL** |
| `blocked_incomplete` | **로컬 보관만** |

### 5-7. 이메일 (관찰3)

`send_weekly_email()`은 전체 summary를 받아 HTML builder에 넘긴다(`email_sender.py:83`) → **builder만 확장**해서 `internal_review` / `blocked_incomplete` 상태와 사유를 표시하면 된다. **차단이 아니라 표시.**
반면 **공개 poster들은 `status == "success"`만 보므로 반드시 publication filter가 필요하다.**

---

## 6. Layout (v6 유지)

`PresentationSpec → LayoutBuilder → Layout`. 검증: 전사성 / 단사성 / orphan 없음 / `scenario × period × entity` 전사 / 같은 Layout으로 수식·표시·Checks 생성 / 행 삽입 후 재생성 가능. **Layout이 모르는 `ext` key는 에러**(§2-1).

---

## 7. 검증 (v6 유지)

> ★ **BS balance만 맞는다고 모델이 맞는 게 아니다. Plug를 잘못 넣어도 BS는 항상 맞출 수 있다.**

워크북 체크: 회계 등식 / **롤포워드**(NI↔이익잉여금, D&A↔PP&E, Capex↔CF·PP&E, 차입↔CFF·BS, 배당↔이익잉여금) / 정합성(이자↔평균잔액, AR·재고·AP↔DSO·DIO·DPO) / 시나리오(확률합, Bull≥Base≥Bear) / 입력 범위 / `ISERROR`·`ISNA` / **candidate·unmapped materiality** / **regime 라벨·`commitment_binding`·`unfunded_cash_need`**.

극단 드라이버 **3중 방어**: Data Validation + Checks 수식 + **output invalidation**.

CI parity: Python `fs_eval` (기준) / LibreOffice (호환성, **Excel의 oracle 아님**) / Windows Excel (릴리즈 전 baseline) / **불연속 경계 fixture**.

---

## 8. LLM 계층 (v6 유지 + 보강)

**A1 MAPPER** — 승격 evidence = **독립 회계 근거** (LLM 판단 횟수 아님). `MappingKey`의 `normal_balance`는 **XBRL `balance` 속성 / 없으면 `unknown` / 관측 부호로 추론 금지**.

**`industry_class` 우선순위 (관찰1):**
```
공시 산업 코드 → 기존 profile의 검증된 industry → keyword classifier(method_selector.py:164) → unknown
```
`method_selector.is_financial()`은 문자열 keyword 검사라 **함수 자체는 결정론적**이다. 그러나 **industry 문자열이 앞선 LLM company identification에서 왔다면 출처는 LLM이다** → **출처를 보존**한다.

**A2 DRIVER** — **결정론 baseline + 작은 LLM 조정치** (주 설계). LLM은 5년 표를 재작성하지 않고 `revenue_fade_adjustment` / `target_margin_delta` / `working_capital_normalization_flag` / `capex_cycle_classification` / `terminal_normalization_caveat`만 출력.

**Spike(태스크 D):** strata 6~12개 (KR제조 / KR금융 / US대형 / **적자 성장** / 다중세그먼트 / **고레버리지·distress** / optionality-heavy / **비12월·20-F**) × 지표 9종.

**A3 AUDITOR** — 결정론 root-cause classifier 1차, 미분류만 LLM. 구조화 출력. **숫자 수정 금지.**

---

## 9. 데이터 계약 (v3 유지)

`FactObservation`(Decimal, filed_at, doc_id, form, period, duration_class, unit, statement_hint, fs_scope) / `cash_effect` / `fact_identity` vs `observation_id` / CFS→OFS / `account_id`(IFRS) 우선 / **as_of = snapshot immutable cutoff** / comparability policy.

---

## 10. 태스크 — **세션 순서** (Codex 7차 권장)

**각각 별도 feature / 별도 세션.** 한 세션에서 병행할 이유가 없다 (리포 규칙: 기존 파이프라인 end-to-end 안정화 전에는 단일 agent 우선).

| 순서 | 세션 | PLAN | 상태 |
|---|---|---|---|
| **1** | **E1 — LLM 호출 계측 (관측만)** | 🆕 **`PLAN_E1_llm_instrumentation.md`** | ✅ **즉시 착수 가능** |
| **2** | **controlled cold/warm 측정** | (E1에 포함) | E1 후 |
| **3** | **E2 — budget / reservation** | 미작성. **E2 PLAN이 계약·DoD를 소유** | 측정치 기반 |
| **4** | **A — EDGAR 파서 감사** | 이 PLAN (아래) | E와 독립, 별도 세션 |
| **5** | **B — 음수자본 버그** | 이 PLAN (아래) | 별도 세션 |
| **6** | **C — Excel/LibreOffice spike** | 이 PLAN (아래) | 별도 세션 |
| **7** | **D — A2 strata spike** | 이 PLAN (아래) | E1 후 |
| **8** | **3-statement 본 구현** | 이 PLAN | **보류** — 위 전부 완료 후 |

### 선행 태스크 상세

- **A — EDGAR 파서 감사.** duration/accn dedupe 없음(`edgar_parser.py:86`), 동일 `end` 동률이 입력 순서 의존. `_guess_recent_years`(`:155`)가 10-K만 → **20-F 발행사 누락**. 기존 US 결과 재검산. fixture 동반, 별도 커밋.
- **B — 음수자본 버그.** `edgar_parser.py:145`가 equity≤0일 때 D/E=0 → `distress.py:100`이 그 값을 신뢰 → **음수자본 기업이 leverage stress 0**. `monte_carlo.py:201`은 올바르게 보존. **`fs_forward`는 음수자본·음수현금흐름을 clamp하지 않고 별도 distress state를 낸다.**
- **C — openpyxl/Excel spike.** `calcPr`/`Table`/수식 저장 ✅ 확인(3.1.5). **openpyxl은 계산하지 않는다** → 재계산 엔진 필수. LibreOffice 미설치 → CI 컨테이너 구성.
- **D — A2 spike.** strata 6~12개 × 지표 9종 (§8).

> **~~F — CFI 워크북 파싱~~ → backlog로 이동** (Codex 8차 중요6). 목적·선행관계·완료조건이 정의되지 않았고, **3-statement 필수 선행이 아니다.** CFI 파일은 사용자가 참고용으로 올린 예시일 뿐이며, v5부터 모델 구조는 `ConstraintModel`/regime 표로 자체 정의된다. 필요해지면 별도 backlog 항목으로 다시 꺼낸다.

### 본 구현 (8번 세션)

`fs_graph` / `fs_model` / `fs_solve` / `fs_eval` / `fs_checks` (engine, 순수) → `fs_compile` / `fs_layout` (output) → taxonomy / parser / `fs_statements` → A1·A2·A3 → sheets → delivery gate → DCF 어댑터 → evals → CI.

---

## 11. DCF 어댑터 — 반올림 경계 (중요10)

`schemas/models.py:743` — `DCFProjection`은 **금액 int, 성장률 float**.

```
ForwardStatements           : Decimal 유지
calc_dcf_from_forward 내부  : 할인·TV까지 Decimal 유지
DCFResult 생성 직전         : display unit으로 ROUND_HALF_UP → int    ← ★ 반올림은 여기 한 번만
```
🔴 **중간 projection별로 int 반올림하면 PV와 TV에 누적 오차가 생긴다.**
장기적으로 `DCFProjection`도 Decimal을 허용하는 **v2 모델을 별도로** 두는 게 맞다.

`TerminalAssumptions`(terminal_growth / normalized_roic 또는 reinvestment_rate / normalized_tax_rate / exit_multiple / terminal_fcff_policy)는 v6 유지 — `dcf.py:150-158`이 **이미 terminal FCFF를 정규화**하기 때문에 필수.

---

## 12. Definition of Done

> **External prerequisite (이 PLAN의 DoD 아님):** E1 complete → E2 complete. **C3의 DoD는 E2 PLAN이 소유한다.** (§4-1)

**C1** — 최종 `Model`에 `Solve` 0개 / Bull·Base·Bear가 서로 다른 `Ref` / Layout 전사·단사 / **`ROUND_HALF_UP` 고정** + **내장 `round()` 사용 0건 — 단, 정적 검사 범위는 `engine/fs_*.py` / `output/fs_*.py` / 신규 DCF 어댑터로 한정** (기존 코드에는 의도적 `round()`가 많다. Codex 8차 개선3) / Piecewise가 **기간별 로컬**(Cartesian product 0건) / IR에 `fmt` 없음 / **미지원 `ext` key → 에러**

**C2 — sweep 수학 (v8 오류 3건, 회귀 테스트로 방어)**
- `allowed_sweep = min(pct × excess, cap, D_open)` 정확히 구현
- 🔴 **`sweep_pct < 1`이어도 `S ≥ D_open`이면 `full_sweep`** (오류① 회귀)
- 🔴 **`partial_sweep`에서 `C_close ≠ min_cash`** — `C_close = cash_pre − S` (오류② 회귀)
- 🔴 **`required_sweep = 0`이면 `mandatory`에서도 `no_transaction` 허용** (오류③ 회귀)
- `annual_cap`: **`None`(무제한) ≠ `0`(sweep 0)** — `is not None` 검사
- `Money` currency·scale 정합 / `0 ≤ sweep_pct ≤ 1` / `commitment ≥ D_open`

**C2 — 세금·배당 순환 (v9/v10)**
- 🔴 **`D = K/(1−r)` 고정 공식이 코드에 없다** (정적 검사). 해는 **lowering이 상징적으로 생성한 closed form**이다
- 🔴 **`tax_positive`에서 계수가 `1 − r(1−t)`임을 테스트** — `tax_zero`(`1 − r`)와 **다른 값이 나오는지** 회귀
- 🔴 **joint regime = 세금(2) × 유동성(6), 최대 12 후보 → eligibility 후 평가.** 각 regime 내부가 **실제로 선형**임을 테스트
- 🔴 **배당이 당기 `NI`에 의존하지 않는다** (외생화 — 순환 차단). 우선순위: 명시 스케줄 → `max(0, prior_NI) × payout` → 0
- 🔴 **세금 분기 조건이 §2-4의 `ROUND` + `Const(ε)`를 사용** (Python·Excel 동일 분기)
- **`SweepResult`에 `joint_regime` 기록** (감사 가능)
- **lowering이 `matrix_coefficients` / `determinant` / `closed_form_expr` 보존**
- **NOL / minimum tax / tax credit / PIK / capitalized interest / covenant step / dividend floor·cap = `unsupported_feature`** — 입력에 있으면 **경고 또는 value-only** (조용히 무시 금지)
- **§3-10 경계 fixture 9종 전부** — 동시 binding에서 Python·Excel이 **같은 label**

**C2 — 현금 계약 (v10)**
- 🔴 **`OCF_pre_interest_and_tax`가 이자·세금·배당·부채거래를 EXCLUDES** — fixture로 IS/BS/CF 대응 검증
- 🔴 **term-debt 상환·배당이 `other_cff`에 포함되지 않음** (이중 차감 0)
- **v1 단순화가 명시 선언됨**: `cash_tax = current_tax`, `deferred_tax = 0`, `Δtax_payable = 0`, `cash_interest = accrual_interest`

**C2 — 구현 안전 계약 (v11, §3-11)**
- 🔴 **`LinearForm` 검증기** — regime 내부에 `MAX`/`MIN`/`IF`가 남으면 **`NonLinearConstraintError`로 중단** (조용한 근사 0건)
- 🔴 **미지수 = `(D_close, C_close)`로 고정.** `draw_amount`/`sweep_amount`는 파생값 (opening-debt 이자 항 누락 방지)
- 🔴 **`abs(det) <= tol` → `SingularRegime` → 다음 regime → 전부 singular이면 `IncompleteForecast`**
- 🔴 **`tax_rate`는 소수.** `0 ≤ tax_rate ≤ 1` 검증 (기존 코드의 `%` 단위와 혼동 차단)
- **`interest_tax_deductibility = 100%`** 명시. 공제 한도 = `unsupported`
- 🔴 **해 검증 = residual**: `|A·x − b| ≤ tol` + eligibility 조건 + 회계 등식. **symbolic 문자열 모양 검사만으로는 algebra 오류를 놓친다**
- **세금방패 회귀 테스트(`1 − r(1−t)`)는 단순화 fixture에서만** (opening debt = 0, 이자수익 = 0, 미지수 1개)
- **`dividend_source` 보존** (`explicit_schedule` / `prior_year_ni_payout` / `zero_fallback`)

**C2 — Unsupported feature (v11, §3-2)**
- 🔴 **NOL / PIK / capitalized interest / covenant step / minimum tax / 이자공제한도**: 외부 확정값 **있으면** `value_only`, **없으면 `IncompleteForecast`**
- 🔴 **"경고 후 계산 계속" 경로가 코드에 없다** (정적 검사) — NOL은 명시적 `nol_ignored: true` override만 예외
- **미지원 입력을 조용히 무시하지 않는다**

**C2 — 구조**
- `SweepPolicy.source`가 **Optional + default** (기본 `SweepPolicy()` 생성 가능 + **기존 YAML 프로필 무손상**)
- `pre_revolver_cash_change`에서 **term-debt 상환·배당이 이중 차감되지 않음**
- **`CFO` 명칭 미사용** (IFRS/US-GAAP 이자 분류 차이)
- `no_transaction`에서 `D_close = D_open` / draw·sweep 상호배타 (term-debt 상환 후 revolver draw는 허용)
- regime 선택이 초기값·순서 독립 / `LiquidityShortfall` ≠ `IncompleteForecast` / 음수자본 clamp 안 함

**C4** — critical concept에 candidate **0건** / aggregate exposure 임계 준수 / `fallback` 기업이 **공개 채널에 0건** / 기업 단위 게이트(1개 fallback이 9개를 막지 않음) / **각 view의 `status_summary` + 파생 링크·텍스트 재계산** / **entry-point 자체 gate — `assert` 아닌 명시적 `raise`** / **Storage 권한 분리** / `IncompleteForecast` → Excel `NA()`

**결정론/v3** — 밸런스·CF tie-out·**롤포워드 전종** / Decimal 정밀도 / EPS ÷1e6 안 함 / SEC·DART Capex → `value_cash` 둘 다 음수 / CFS→OFS / 20-F / 재현성 = **semantic 동일**

---

## 13. 잔여 위험

1. 🔴 **순환 구조에 대한 내 직관이 다섯 번 틀렸다.**
   | 버전 | 오류 |
   |---|---|
   | v5 | 순환을 **반복계산**으로 풀려 함 → distress를 "수렴 실패 예외"로 처리 |
   | v8 | sweep 수학 **3건** (full/partial 조건, `C_close`, mandatory eligibility) |
   | v8 | **세금·배당 순환을 통째로 누락** (`max(0,·)` 두 개) |
   | v9 | 세금 계약을 §3-5에 써놓고 **§3-4 표의 `D = K/(1−r)`에 반영 안 함** (세금방패로 계수가 바뀐다) |
   | v9 | `OCF_pre_interest`가 **세금 포함 여부 불명확** → 이중 차감 위험 |

   **패턴이 분명하다: 순환의 깊이를 매번 과소평가했다.** 그래서 최종 설계는 **해를 손으로 유도하지 않는다** — lowering이 계수행렬을 **상징적으로** 풀고, **`LinearForm` 검증기가 선형성을 강제**하며(§3-11a), **residual 검사가 algebra를 검증**한다(§3-11d). §3-10의 경계 fixture 9종 + DoD 회귀 테스트가 안전망이다.

   🔴 **구현 시 이 문서의 손으로 쓴 공식(`1 − r(1−t)` 등)을 코드에 박지 말 것.** 그건 설명 예시다. 계약은 symbolic solve다.
2. **joint regime이 12개다.** 기간별 로컬이므로 폭발하지 않지만(§2-3), **covenant step이나 NOL을 넣는 순간 `12 × N`으로 곱해진다.** v1에서 뺀 이유가 이것이다. **넣고 싶어지면 이 곱셈을 먼저 계산하라.**
3. **배당 외생화는 근사다** — 다만 KR 결산배당(전기 실적 기준) 관행과 일치하므로 **오히려 더 정확할 수 있다.** US 기업(분기배당, 당기 실적 연동)에서는 근사도가 떨어진다. **Assumptions에 명시한다.**
4. **E1/E2는 외부 선행조건이다.** reservation은 3-statement와 무관한 기존 파이프라인 정확성 문제다 (`api_guard.py:281` lost update는 지금도 발생 가능). 별도 PLAN·별도 세션이 소유한다.
5. **A2 spike(D)가 예산 상한을 확정한다.** E1 실측 전에는 예산 숫자를 확정하지 않는다.
6. **LibreOffice는 Excel의 oracle이 아니다.**
