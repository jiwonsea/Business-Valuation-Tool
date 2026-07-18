# Codex 핸드오프 — PART B Round 2: BVT 엔진·Excel 결함 수정

> **실행 위치**: `F:\dev\Portfolio\business-valuation-tool`
> **재현 프로필**: `profiles/nexus.yaml` (SOTP, `ev_revenue` + `pbv` **혼합** 세그먼트 — 이 조합이 결함을 전부 드러낸다)
> **재현 명령**: `python cli.py --profile profiles/nexus.yaml --excel`
> **PART A(밸류에이션 검증)는 PART B 완료 후 진행한다.**

## 작업 규칙 (CLAUDE.md Session Safety)
- working tree에 **미커밋 작업 다수**. `git checkout -- <f>` / `git restore` / `git reset --hard` **절대 금지**.
- 모든 `.py` 수정 직후 `python -c "import ast; ast.parse(open('<f>').read())"` + 줄 수 확인 (Windows 마운트에서 **무언의 truncation** 이력 있음).
- `engine/`은 **순수 함수** 유지 (IO 금지). Pydantic 입력 직접 mutate 금지 → `model_copy(update=...)`.
- CRLF 유지. 완료 후 `pytest tests/ --deselect tests/test_engine.py::TestScenarioDriverRoundTrip` 전량 통과.
- **구현 전 정책 제안 먼저.** 하위호환 영향(기존 48개 프로필 산출값 diff 0)을 증명할 것.

---

# P0 — Excel 산출물이 **거짓 정보를 출력**한다

`ev_revenue` + `pbv` 혼합 SOTP에서 Excel 3개 시트가 **틀린 수치를 자신 있게 출력**한다. 이 파일을 실제 리서치 증빙으로 첨부하면 사고가 난다.

## P0-1. Sensitivity 시트가 통째로 무의미 — 축이 죽었고 음수 배수가 찍힌다

**증상** (`넥써쓰_밸류에이션_모델_2026-07-13.xlsx` → `Sensitivity`):

```
게임\원스토어 | -2.3x | -1.3x | -0.3x |  0.7x |  1.7x |  2.7x |  3.7x
        -1.6x |  -681 |  -681 |  -681 |  -681 |  -681 |  -681 |  -681
        -0.6x |  -171 |  -171 |  -171 |  -171 |  -171 |  -171 |  -171
         0.5x |   389 |   389 |   389 |   389 |   389 |   389 |   389
         1.4x |   848 |   848 |   848 |   848 |   848 |   848 |   848
         2.5x |  1409 |  1409 |  1409 |  1409 |  1409 |  1409 |  1409
```

**근본 원인 2건** (`engine/sensitivity.py`):

**(a) PBV/PE 세그먼트가 열 축으로 선택되면 축이 죽는다.**
`_seg_metric()` (L14-32)이 `method in ("pbv","pe")`일 때 **0을 반환**한다. 그런데 `sensitivity_multiples()` (L57-58)는 축 세그먼트를 `seg_codes[0]`, `seg_codes[1]`로 **무조건 자동 선택**한다. 그 결과 `col_metric = 0` → `col_ev = 0 × col_m = 0` → **열 축을 아무리 흔들어도 결과 불변**. 세그먼트 값은 `pbv_pe_ev` 상수로 따로 더해진다.

**(b) 축 범위 생성이 배수의 스케일을 무시한 가산법이다.**
```python
row_range = [round(base_m + i, 1) for i in range(-2, 3)]   # L62
col_range = [round(base_m + i, 1) for i in range(-3, 4)]   # L65
```
EV/EBITDA(8~13x)에는 ±1이 합리적이지만, **EV/Sales 0.45 / PBR 0.70563에 ±1~±3을 더하면 음수가 나온다.** 실제로 `[-1.6, -0.6, 0.5, 1.4, 2.5]`, `[-2.3, -1.3, -0.3, 0.7, 1.7, 2.7, 3.7]`가 생성됐다. **PBR −2.3배**는 존재할 수 없는 값이다.
또한 `0.5x` 행은 실제 Base 배수 `0.45`와 다르다 — 격자가 모델을 지나가지 않는다.

**요구사항**
1. 축 세그먼트 자동 선택에서 **equity-based(pbv/pe) 세그먼트를 제외**하거나, PBV 축을 지원하려면 `_seg_metric`이 `book_equity`(pbv) / `net_income_segment`(pe)를 반환하고 `pbv_pe_ev` 상수 가산과 **이중계상되지 않도록** 정합시켜라. **둘 중 어느 설계가 옳은지 먼저 의견을 내라.**
2. 축 범위를 **승법(multiplicative)** 또는 스케일 인지 방식으로 바꿔라 (예: `base × [0.6, 0.8, 1.0, 1.2, 1.4]`). **어떤 경우에도 음수 배수가 생성되면 안 된다** — 하한 클리핑 필수.
3. 격자에 **Base 배수 자체가 반드시 포함**되도록 하라(현재 0.45가 격자에 없다).
4. EV-based 세그먼트가 1개뿐이면(=축 2개를 못 만들면) 시트를 **생성하지 말고 사유를 명시**하라. 조용히 빈 표를 내지 마라.
5. 회귀 테스트: `ev_revenue + pbv` 혼합 프로필에서 (i) 음수 축이 없고 (ii) **열 축을 바꾸면 값이 실제로 변한다**를 검증.

## P0-2. Peer Comparison이 EV/EBITDA와 EV/Sales를 **직접 비교**한다

**증상** (`Peer Comparison` 시트):
```
부문별 EV/EBITDA 멀티플 통계
  게임·크로쓰 | Peer 4 | Min 1.3 | Median 8.5 | Max 19.0 | 적용 멀티플 0.45
  중앙값 대비: -94.7%  |  밴드 위치: 레인지 밖
  선정 근거: "peer 중앙값 8.5x 대비 -94.7% 할인"
```
**적용 멀티플 0.45는 EV/Sales**다. peer 통계 8.5x는 **EV/EBITDA**다. **단위가 다른 두 수를 나눠서 "-94.7% 할인"이라고 출력**한다. 완전한 허위 정보다.

**근본 원인**: `schemas/models.py::PeerCompany`에 **`ev_ebitda` 필드밖에 없다.** `ev_revenue` 방식 세그먼트의 peer 배수를 담을 자리가 없어서, 사용자가 EV/Sales 값을 `notes`에 문자열로 적는 수밖에 없었다 (현행 `profiles/nexus.yaml`이 그렇게 하고 있다).

**요구사항**
1. `PeerCompany`에 **세그먼트 method에 대응하는 배수 필드**를 추가하라 (`ev_sales` / `pbv` / `pe` 등). Optional + 기본값으로 **하위호환** 유지.
2. `output/sheets/peers.py`가 **세그먼트의 `method`에 맞는 배수로 통계를 내고 비교**하도록 고쳐라. method가 불일치하면 **비교를 생략하고 경고**를 출력할 것 — 지금처럼 계산해버리면 안 된다.
3. 같은 시트의 **역산 교차검증**도 무효다:
   > `현재 주가 역산 | 1505 | 내재 EV 174,169 | 내재 EV/EBITDA 56.18x`
   분자(시총·순차입금)는 **거래 후**(증자 후 주식수 + 신규 CB 231억), 분모(2025 EBITDA 3,100백만원)는 **거래 전**(원스토어 미연결)이다. **기준일이 다른 분자·분모를 나눴다.** 인수/합병으로 자본구조가 바뀐 프로필에서는 이 패널을 **끄거나 경고**해야 한다.

## P0-3. Relative Valuation이 **거래 전 실적 ÷ 거래 후 자본구조**

**증상** (`Relative Valuation` 시트):
```
P/B 4.07  |  EV/EBITDA 56.18  |  EV/Sales 4.75  |  판정 "OK"
피어 median 대비: EV/EBITDA 56.18 vs 8.5 → "피어 대비 프리미엄"
정당배수 대비: P/B 실제 4.07 vs 정당 -0.71 → "판단불가"
```
- `P/B 4.07` = 시총 1,224.8억 ÷ **2025년 자본 301억**(원스토어 미연결, 유증 전)
- `EV/EBITDA 56.18`·`EV/Sales 4.75` = **거래 후 EV** ÷ **거래 전 EBITDA/매출**
- "정당 P/B **−0.71**" — 음수 정당배수를 출력하고 "판단불가"로 넘어간다

**게다가**: 프로필에서 `pe_multiple: 0`, `pbv_multiple: 0`, `ev_revenue_multiple: 0`, `ps_multiple: 0`으로 **전부 꺼놨는데도 이 시트는 그대로 출력된다.** 끄는 스위치가 `cross_validate` 경로에만 걸려 있고 진단 패널은 별개 경로다.

**요구사항**
1. 진단 배수의 **분모(실적·자본)와 분자(시총·EV)의 기준일 정합성**을 검사하라. `consolidated`의 base_year 실적이 현재 자본구조를 반영하지 않으면(예: 기중 대규모 인수·증자) **경고 + 값 미출력**.
   - 판정 신호 후보: `net_debt`이 `consolidated[base_year]`의 `net_borr`와 크게 어긋남 / `shares_total`이 base_year 대비 급증 / segment에 base_year 미연결 자산이 존재.
   - **어떤 신호가 가장 견고한지 먼저 제안하라.**
2. 프로필에서 배수를 0으로 끄면 **이 시트도 함께 꺼지도록** 스위치를 일원화하라.
3. **정당배수가 음수면 출력하지 말 것** (현재 −0.71 출력).

---

# P1 — 엔진 결함

## P1-1. Monte Carlo가 PBV/PE 세그먼트를 조용히 건너뛴다 → 음수 붕괴

`engine/monte_carlo.py`는 `seg_ebitdas.items()`를 순회하며 `method in ("pbv","pe")`를 `continue`로 스킵한다. 결과적으로 **pbv 세그먼트 기여분을 0으로 두고 전체 net_debt을 차감**한다.

`profiles/nexus.yaml` 실측 (`mc_enabled: true`로 되돌리면 재현):
```
시나리오 SOTP:  Bear 46원 / Base 364원 / Bull 798원   (정상)
엔진 MC:        중앙값 −375원, P5 −498원              (전 구간 음수 — 쓰레기)
```
경고도 예외도 없다. **같은 프로필에서 SOTP와 MC가 서로 다른 모델을 계산한다.**

**요구사항**: MC에서 pbv/pe 세그먼트를 `book_equity × 배수`(또는 `net_income × 배수`)로 **EV에 가산**하거나(배수 샘플링 포함), 최소한 **혼합 프로필에서 MC를 비활성화하고 경고**하라. 조용히 쓰레기값을 내는 현 상태가 최악이다.

## P1-2. `console_report`의 Distress Haircut이 `distress_max_discount`를 무시한다 → **거짓 출력**

`valuation_runner.py:895`는 `calc_distress_discount(..., max_discount=vi.distress_max_discount)`를 넘긴다. 그런데 `output/console_report.py`는 **인자 없이 독립 재계산**해서 기본값(0.25)으로 출력한다.

`profiles/nexus.yaml` (`distress_max_discount: 0.0`) 실측:
```
[Distress Haircut] Distress haircut −10%: ICR 1.6x (−10%)
  원스토어 지분 89.03%: 0.7x → 0.6x        ← 거짓
[SOTP] 원스토어 P/BV 0.7x → 62,633백만원    ← 88,762 × 0.70563 = 할인 미적용(실제)
```
**모델은 할인을 안 했는데 리포트는 했다고 말한다.** 읽는 사람이 속는다.

**요구사항**: 콘솔이 `vi.distress_max_discount`를 넘겨 재계산하거나, `result`에 저장된 `effective_multiples`를 그대로 출력하라 (**후자가 옳다** — 리포트가 모델을 재계산하는 것 자체가 위험).

## P1-3. 시트마다 **주식수가 다르다**

| 시트 | 사용 주식수 | 출처 |
|---|---|---|
| Scenario Analysis / Dashboard | **81,385,045** | `ScenarioParams.shares` (YAML) |
| Sensitivity / Peer Comparison | **81,383,610** | `CompanyProfile.shares_outstanding` (= total − treasury 1,435) |

둘 다 나름의 근거가 있으나 **한 산출물 안에서 두 값이 섞이면 안 된다.** 실제로 Sensitivity의 `0.5x` 행이 389원인데, 같은 계산을 81,385,045주로 하면 다른 값이 나온다.

**요구사항**: 주식수 정책을 **하나로 통일**하고 문서화하라. (자기주식 차감 여부는 밸류에이션 관행상 선택 가능하나, **선택했으면 전 시트가 따라야 한다.**) 어느 쪽이 옳은지 의견을 내고, 하위호환 영향(48개 프로필 diff)을 확인하라.

---

# P2 — 기존 백로그 (`BACKLOG_P2_units_sotp_guardrails.md`)

우선순위 순. **P0/P1 완료 후** 착수.

1. **`currency_unit` ↔ `unit_multiplier` 정합성 정책** — `unit_multiplier: 1e8`이 여전히 합법이라 `currency_unit: 억원` + `1e6` 조합이 **산술은 맞고 표시만 100배 틀린** 리포트를 만든다. 2026-07-13 100배 사고와 같은 계열.
2. **부분 시나리오 코드 fallback 안전화** — `engine/quality.py:669` `if bull is None or base is None:`이 **한쪽만 없어도 양쪽을 재선정**한다. `Base/Bear/Stress`처럼 Bull이 없는 프로필에서 `bull is base`가 되어 ratio 1.00 고정 감점 + 오해를 부르는 메시지. 현행 48개엔 없어 잠복.
3. **밴드 예산 규칙 문서화** → `.claude/rules/engine.md`
   ```
   (Base/Bear) × (Bull/Base) = Bull/Bear ≤ _SOTP_MAX_RATIO (=2.0)
   → Base를 Bear의 1.667배 이상 올리면 Bull 여유가 품질 임계 1.20x 미만이 되어 구조적 감점 확정
   ```
4. **wide-spread 우회 감사 플래그 영속화** — 현재는 안전(주간 파이프라인이 비-curated만 생성). **curated 프로필을 주간 런에 편입하는 순간 P1로 승격.**

### 부수 표시 결함 (P2)
- `Dashboard` / `Assumptions`가 배수를 소수 1자리로 반올림해 **실제값을 은폐**한다: `EV/Revenue 0.5x`(실제 0.45), `P/BV 0.7x`(실제 0.70563).
- `Dashboard`의 `순차입금 (연결) 51,687` — **연결이 아니다**(본체 + 인수금융). 라벨 오류.
- `Sensitivity` 시트 라벨 `주당가치(백만원)` — 실제 단위는 **원/주**.
- `Financial Summary`의 부문 표가 PBV 세그먼트에 매출/영업이익/EBITDA를 표시한다(모델은 쓰지 않는 값). 오해 유발 → `N/A` 처리 검토.
- `Dashboard`의 MC 분포 라벨이 `Normal(mean=...)`인데 **엔진은 로그정규**를 쓴다.

---

## 출력 형식 (한국어)
1. **구현 전 정책 제안** — P0-1 축 설계 / P0-2 PeerCompany 스키마 / P0-3 기준일 정합성 신호 / P1-3 주식수 정책. 각각 **하위호환 영향**과 함께.
2. 승인 후 구현 → 파일:라인 diff
3. **기존 48개 프로필 산출값 diff 0 증명** (unit_multiplier / weighted_value / 시나리오 post_dlom)
4. 신규 회귀 테스트 목록
5. `pytest` 결과
6. 미해결로 남긴 항목과 사유

---

# ✅ 정책 승인 (2026-07-13) — **조건부 승인. 아래 6건 반영 후 구현 착수**

제안한 4개 정책의 방향은 전부 옳다. 사실관계도 독립 확인했다:

| Codex 주장 | 검증 |
|---|---|
| `PeerCompany`에 `ev_revenue`·`pbv`·`trailing_pe`·`forward_pe` 이미 존재 | ✅ 확인 (중복 필드 신설 불필요) |
| 48개 프로필 peer 전부 `ev_ebitda`만 사용 | ✅ **450건 전수 확인** (448이 아니라 450) |
| 시나리오 간 주식수 상이 프로필 0개 | ✅ 확인 |
| reference shares ≠ shares_outstanding 프로필 = nexus 1개 | ✅ 확인 (차 1,435주 = 자기주식) |

## 조건

### C-1. **P1-2가 정책에서 빠졌다** — `console_report`의 거짓 Distress 출력

"나머지 P1 처리 정책"에 **MC만** 적었다. `output/console_report.py`가 `vi.distress_max_discount`를 무시하고 독립 재계산해 **모델이 적용하지 않은 할인을 적용했다고 출력**하는 문제(P1-2)가 누락됐다.

**요구**: 리포트가 모델을 **재계산하지 않도록** 고쳐라. `result`에 저장된 `effective_multiples`(또는 distress 결과)를 그대로 출력하는 방향이 옳다. 리포트 레이어가 엔진 계산을 복제하는 구조 자체가 이 버그의 원인이다 — 같은 패턴이 다른 시트에도 있는지 함께 훑어라.

### C-2. Sensitivity 격자 변경은 **diff-0이 아니다** — 회귀 증명을 분리하라

가산식 → 승법식 전환은 **48개 프로필 전부의 Sensitivity 격자를 바꾼다.** "diff 0"으로 뭉뚱그리면 안 된다.

**요구**: 회귀 증명을 **두 갈래로 분리**해서 제출하라.
- **불변이어야 하는 것 (diff 0 필수)**: `unit_multiplier`, `weighted_value`, 시나리오별 `post_dlom`, SOTP 세그먼트 EV
- **의도적으로 바뀌는 것**: Sensitivity 격자 축·값 → **변경 전후 격자를 몇 개 프로필에 대해 나란히 제시**하고, 새 격자가 Base를 포함하며 음수가 없음을 보여라

### C-3. Peer 역산 패널은 **혼합 SOTP에서는 기준일과 무관하게 무의미**하다

P0-2의 3번을 "기준일 불일치 시 끔"으로만 처리했는데 부족하다. **SOTP가 mixed-method면(예: `ev_revenue` + `pbv`) 회사 수준의 단일 내재 배수 자체가 정의되지 않는다.** 기준일이 완벽히 정합해도 "내재 EV/EBITDA 56.18x"는 여전히 의미가 없다 — 분모 EBITDA가 PBV 세그먼트의 가치를 설명하지 못하기 때문이다.

**요구**: `is_mixed_method(vi)`가 참이면 **기준일 정합 여부와 무관하게** 역산 교차검증 패널을 끄고 사유를 출력하라.

### C-4. 주식수 정책 — 승인하되 **경고를 강제**하라

"단일 분모 패널 = Base/reference scenario shares" 방침에 동의한다. 내부 일관성이 확보되고 diff-0이 유지된다.

그러나 이 방침은 **nexus에서 자기주식 1,435주를 포함한 81,385,045주를 주당가치 분모로 쓰게 된다.** 자기주식은 경제적 청구권이 없으므로 이론적으로는 `shares_outstanding`(81,383,610)이 맞다. 차이가 0.0018%라 실무 영향은 없지만, **정책이 조용히 이론적으로 틀린 분모를 고정하는 것**은 곤란하다.

**요구**: `scenario.shares != company.shares_outstanding`이면 **경고를 출력**하라 (`"적용 주식수 81,385,045 ≠ 유통주식수 81,383,610 (자기주식 1,435 포함) — 시나리오 shares가 의도적 설정인지 확인"`). 작성자가 **의식적으로 선택하도록 강제**하는 것이 목적이다. Raw Data에 두 값을 병기하는 제안은 그대로 좋다.

### C-5. `pbv_pe_ev` 이중계상 방지는 **검증이 아니라 단정(assert)**으로

"신규 세그먼트 metric과 동시에 사용되지 않도록 검증"이라고 했는데, 이건 런타임에 **터져야** 한다. 조용히 이중계상되면 그 순간 밸류에이션이 2배가 된다.

**요구**: `pbv_pe_ev > 0`이면서 축 세그먼트에 pbv/pe가 포함되면 **`ValueError`를 던져라**. 회귀 테스트로 그 예외를 검증하라.

### C-6. MC 수용 기준을 **수치로 못박아라**

"PBV는 장부자본×샘플 PBR로 정식 가산" 만으로는 검증이 안 된다. 로그정규 샘플링의 중앙값은 평균 배수에 수렴하므로, **MC 중앙값은 Base 시나리오 주당가치에 근접해야 한다.**

**요구 (회귀 테스트)**: `profiles/nexus.yaml`(`mc_enabled: true`)에서
```
| MC median − Base scenario per_share | / Base < 15%
MC P5 > 0 을 요구하지는 않되, 음수 비율이 100%가 아닐 것
```
현재 Base = **364원**, 엔진 밖 수동 MC 중앙값 = **344원**(−5.5%) → 정상 구현 시 이 범위에 들어와야 한다. **지금 엔진은 −375원을 낸다.**
또한 MC가 `effective_net_debt`(= `net_debt − segment_net_debt[pbv/pe]`)를 쓰는지 **명시적으로 단정**하라 — 순차입금 이중차감이 이 버그의 재발 경로다.

## 승인 후 순서
1. **C-1~C-6 반영한 정책 확정본**을 짧게 회신 (코드 아직 X)
2. P0-1 → P0-2 → P0-3 → P1-1 → P1-2 → P1-3 구현
3. 회귀 증명 (C-2의 2갈래 분리) + `pytest` 전량
4. green 확인 후 **P2 백로그** 착수
5. P2까지 완료되면 **PART A(밸류에이션 검증)** 로 넘어간다 — 프롬프트는 `valuation-results/2026-07-13-nexus-onestore/_codex_eval_prompt_PART_A_v5.md`에 준비돼 있다

## 부수 확인
- `ev_ebitda`를 Optional로 낮출 때 `output/sheets/peers.py`·`calc_peer_stats()`가 **None을 0으로 취급하지 않도록** 가드하라. method 매칭 배수가 없는 peer는 **통계에서 제외하고 경고**할 것 (0으로 넣으면 중앙값이 오염된다).
- P2 표시 결함 중 **"배수 소수 1자리 반올림"**(`EV/Revenue 0.5x` ← 실제 0.45, `P/BV 0.7x` ← 실제 0.70563)은 P0-1의 "최소 소수 2자리" 방침으로 함께 해소되는지 확인하라. `Assumptions`·`Dashboard` 시트도 포함이다.
