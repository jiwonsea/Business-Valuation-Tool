# HANDOFF — Phase A 결함 수정 (Codex)

> Claude 교차검증 2026-05-30 결과. **이전 세션과 무관, 캐시 없이 읽어라.** 경로 `F:/dev/Portfolio/earnings-forecast-engine` (ASCII).
> 1차 구현(`HANDOFF_phase_a.md` 기반)은 pytest는 통과하나 **actual/seed/backtest 파이프라인이 조작 스텁**이라 산출 수치 전부 무효. 아래 결함을 고친다.
> 분업 유지: 본문 구현 = Codex. 검증·결함진단 = Claude. **가정 수치·thesis는 사용자.**

## 검증 증거 (재현 가능)

- `python cli.py --company sk_hynix --skip-pdf` → backtest 8분기 **오차율 전부 동일**(Rev 2.6%/EPS 6.1%), hit 100%. actual이 매끈한 등비수열 = 합성.
- live backtest 2025Q4 actual=97,146.7 = yfinance FY2025 **연간** 매출 97조. 분기 아님.
- `reports/.cache/`에 DART 보고서 **1개**(`dart_00164779_2025_11011.json`)만 존재 → 12분기 미수집.
- model FY26 매출 459조(비현실) — 연간 seed 97조에 분기 성장률 4회 적용 결과.

---

## 결함 1 (🔴 critical) — 백테스트 actual 합성 조작

**위치**: `cli.py:180` `historical = _synthetic_history(prior_actual, 12)` + `cli.py:203-235` `_synthetic_history`.
**근본원인**: 12개 실 DART 분기를 받지 않고 단일 seed에서 `1.035^idx` 등비수열 생성. MAPE·hit_ratio가 조작값 대비 측정이라 무의미.
**수정**:
1. `_synthetic_history` **완전 삭제**.
2. `pipeline/dart_fetcher.py`에 다분기 조립 함수 신설:
   ```python
   def fetch_quarterly_actuals_series(corp_code: str, start_year: int, end_year: int) -> list[QuarterlyActual]:
       """각 연도 {11013,11012,11014,11011} 4보고서를 fetch_quarterly_financials로 받아
       분기 단독값으로 분해한 QuarterlyActual 시계열 반환 (결함 2 규칙)."""
   ```
3. `cli.py`: backtest_window(2024Q1~2025Q4 8분기) + 시드 4분기(2023) = **2023~2025 fetch** → `run_backtest(historical, ...)`에 실 시계열 투입.
**검증**: backtest 표의 분기별 Rev Err가 서로 달라야 함. actual 분기 매출이 SK하이닉스 실제 사이클(분기 ~12-25조 범위)이어야 함(연간 66·97조가 아님).

## 결함 2 (🔴 critical) — DART 분기분해 미적용

**위치**: `pipeline/dart_fetcher.py:94-166` `extract_quarterly_actual`. reprt_code 무관하게 항상 `thstrm_amount` 사용.
**근본원인**: 보고서별 `thstrm_amount` 의미가 다른데(연간=연간전체, 분기=당기3개월), 그대로 읽어 연간치를 1분기로 취급.
**수정** — 검증된 분해 규칙(`HANDOFF_phase_a.md §5-2`, 픽스처로 확인):

| 분기 | 소스 | 단독값 산식 |
|---|---|---|
| Q1 | 11013 | `thstrm_amount` |
| Q2 | 11012(H1) | `thstrm_amount` (당기 3개월) |
| Q3 | 11014 | `thstrm_amount` (당기 3개월) |
| **Q4** | 11011(연간) − 11014 | `11011.thstrm_amount − 11014.thstrm_add_amount`(9M 누적) |

- `extract_quarterly_actual`이 reprt_code(또는 두 raw)를 받도록 시그니처 변경, 혹은 결함1의 series 함수 내부에서 분해.
- 검증 수치: 2024 매출 연간 66,192,960,000,000 − 9M 46,425,925,000,000 = Q4 **19,767,035,000,000**(19.77조).
- 손익 행: `sj_div in ("IS","CIS")`, `account_id` 우선(`ifrs-full_Revenue`, `dart_OperatingIncomeLoss`, `ifrs-full_ProfitLoss`).

## 결함 3 (🔴 critical) — forecast seed가 연간치

**위치**: `cli.py:135-142`. live가 `year-1, "11011"`(2025 연간)만 받아 `"2025Q4"`로 라벨.
**수정**: seed = **최신 실분기**. 2026-05-30 기준 2026Q1 발표 완료(yfinance earnings_history `2026-03-31`) → 2026 Q1(11013) 또는 2025Q4(연간−9M) 단독값을 seed로. 결함1 series의 마지막 원소 재사용 권장.
**검증**: model FY26 매출이 ~90-120조 범위(분기 ~25-30조 × 4)로 떨어져야 함. 459조·313조는 버그 신호.
**열린 결정(사용자)**: `forecast_window.start_quarter=2026Q1`이 이미 actual인 분기와 겹침 → 사용자가 2026Q2~로 옮길지 결정. 우선 seed만 실분기로 고치고 window는 YAML 그대로.

## 결함 4 (🟡) — gross_profit = max(op, 0)

**위치**: `pipeline/dart_fetcher.py:160`. 매출총이익을 OP로 대체 → baseline `gp_margin==op_margin`, 마진 사이클 baseline 왜곡.
**수정**: `매출총이익(손실)` 직접 추출 (`account_id` `ifrs-full_GrossProfit`, 보조 name `매출총이익`). 픽스처에 존재(2024연간 31,828,146,000,000).

## 결함 5 (🟡) — 세그먼트 70/25/5 하드코딩

**위치**: `dart_fetcher.py:156-158`, `cli.py:224`. DART CFS는 DRAM/NAND 미분해인데 코드에 비율 하드코딩 → "가정은 YAML만" 위반.
**수정**: 분해 비율을 `profiles/sk_hynix.yaml`의 명시 가정으로 이동(예 `segment_revenue_split: {dram: 0.7, nand: 0.25, other: 0.05}` + `sources` 주석). 코드는 YAML에서 읽기. (실 IR 세그먼트 데이터 도입은 P1.)

## 결함 6 (🟡 데이터) — yfinance .KS 컨센 신뢰불가 → gap 억제

**검증(Claude)**: 컨센 매출·EPS 쌍의 함의 순이익률이 FY26 **63%**, 0q **60%**로 물리적 불가능(SK 실측 최대 ~30%). yfinance .KS 절대스케일 오류.
**수정(이번 사이클, in-scope)**: `consensus_diff` 또는 리포트에서 **EPS gap을 신뢰불가로 표시**.
- `ConsensusRecord.notes`에 "yfinance .KS consensus unreliable: implied net margin >60%" 경고 추가.
- 깨진 EPS gap은 `direction` 유지하되 리포트 상단에 ⚠️ 데이터 경고 배너. (매출 gap도 동일 출처라 경고 대상.)
- **자동 thesis/interpretation 금지 규칙 유지** — gap 해석은 빈 채로.
**별도 태스크로 분리 (사용자 결정 2026-05-30)**: FnGuide/WISEreport 등 한국 broker 컨센 **교체**는 이번 Phase A 수정 사이클에서 제외. 유료·인증 필요(P1). Phase A 코어(매출 모델·backtest)를 green으로 만든 뒤 Phase B 근처에서 별도 진행. 이번 사이클은 위 in-scope(억제+경고)까지만.

---

## 결함 7 (🔴 critical) — 백테스트 EPS가 엔진을 안 거치고 proxy 사용 (2차 검증서 발견)

**위치**: `engine/backtest.py:74-77`.
**근본원인**: `model_eps = seed.eps_basic * (model_revenue / seed.revenue_total)`. forward forecast는 `project_margins → apply_taxes_and_finance → project_eps` 풀 체인을 쓰는데, 백테스트는 직전분기 EPS에 매출비율만 곱하는 proxy → (a) "동일 방법론 적용"(docstring:5) 위반, (b) 직전분기 적자를 그대로 전파.
**증거(trace)**: DART 실 EPS 2023Q4 = -1,972(2023 메모리 적자). `-1,972 × (12,000.6/11,305.5) = -2,093.4` = 리포트 2024Q1 model EPS와 정확 일치. actual은 +2,788(V회복).
**수정**: `run_backtest`에서 각 테스트 분기에 cli forward와 동일 체인 적용:
```python
fc = project_quarterly_revenue(seed, baseline, seg_assumptions, 1)
fc = project_margins(fc, baseline, margin_assumptions)
fc = apply_taxes_and_finance(fc, finance_assumptions)
fc = project_eps(fc, shares)
model_eps = fc[0].eps_basic
```
→ `run_backtest` 시그니처에 `margin_assumptions`, `finance_assumptions`, `shares` 추가. `cli.py:181`에서 `profile["scenarios"]["base"][1]`, `[2]`, `profile["shares"]` 전달.
**검증**: 동일 입력에 대해 backtest EPS == forward 엔진 EPS여야 함(일관성 테스트 1개 추가). model_eps가 더 이상 직전분기 부호를 맹목 전파하지 않아야 함.

**⚠️ CAVEAT (방법론, 사용자 판단 — 코드 버그 아님)**: 이 수정 후에도 **사이클 전환 분기(2024Q1)는 음수로 남을 가능성**이 큼. `margin_model`이 GP를 `max(0.0, baseline+cyclicality·asp_dev)`로 floor한 뒤 opex ~15%p를 빼므로, baseline이 2023 다운턴이면 op_margin이 구조적 음수가 됨(모델이 V자 회복을 못 따라감). 이는 단일 base 가정 retro 적용의 한계. 사용자 선택: thesis에 한계 명시 / 가정 튜닝 / 마진모델 보강(분기별 baseline·전환 가속). **결함 7 수정의 목적은 "정확한 EPS"가 아니라 "백테스트가 실제 EPS 방법론을 측정하도록" 일관성 회복.**

## 결함 8 (방법론 보강) — HBM mix 세그먼트 마진 브리지 (사용자 결정 2026-05-30)

**배경**: 현 단일 blended-ASP cyclicality 모델은 HBM 슈퍼사이클의 마진 확장을 못 잡아 백테스트 EPS를 8/8분기 과소추정(MAPE 70%, bias 전부 음수). 사용자가 **방법론 A(HBM mix 브리지)** + **시점별 과거 driver** 선택. **방법론·가정 수치는 사용자 영역 — Codex는 구조만 구현, 숫자는 YAML에서 읽기.**

### 8-1. 새 마진 공식 (methodology §5-1 대체)
```
GP_margin_DRAM[t] = HBM_share[t] × GM_HBM + (1 − HBM_share[t]) × GM_DDR
GP_KRW[t]   = R_DRAM[t]·GP_margin_DRAM[t] + R_NAND[t]·GM_NAND + R_other[t]·GM_other
GP_margin[t] = GP_KRW[t] / R_total[t]            # cap [0, 0.9]
OP_margin[t] = GP_margin[t] − sga_pct − rnd_pct
# 선택: 각 GM에 intra-segment ASP 민감도 추가 가능(MVP는 상수 GM)
```
- `HBM_share[t]`: **forward**는 `SegmentAssumptions.dram_hbm_share_qoq[t]`(이미 존재), **backtest**는 `historical_drivers[quarter]`에서.

### 8-2. 스키마 변경 (`schemas/models.py`)
- `MarginAssumptions`: 추가 `gm_hbm: float`, `gm_ddr: float`, `gm_nand: float`, `gm_other: float` (세그먼트 총이익률, 0~1). `gp_cyclicality`는 optional로 강등(기본 0.0, 후방호환).
- `QuarterlyForecast`: 추가 `hbm_share: float = 0.0` — margin_model이 mix 계산에 사용.
- 신규 `HistoricalDriver(BaseModel)`: `quarter_label: str`, `hbm_share: float`, (optional) `gm_overrides: dict[str,float] | None`.

### 8-3. 엔진/배선 변경
- `engine/segment_revenue.py`: 각 `QuarterlyForecast.hbm_share`를 `dram_hbm_share_qoq[t]`로 채움.
- `engine/margin_model.py`: 위 8-1 공식으로 재작성. `fc.hbm_share` + `MarginAssumptions.gm_*` 사용. (현 ASP_dev/cyclicality 경로 제거.)
- `engine/backtest.py`: 각 테스트 분기에서 projected forecast의 `hbm_share`를 `historical_drivers[target.quarter_label]`로 설정한 뒤 `project_margins` 호출. `run_backtest`에 `historical_drivers: dict[str, float]` 인자 추가. cli 배선.
- `pipeline/ir_loader.py`: 시나리오 margins에서 `gm_*` 파싱, top-level `historical_drivers` 파싱 → `profile["historical_drivers"]`.
- `profiles/sk_hynix.yaml`: 구조는 Claude가 scaffold(아래), **숫자는 사용자 확정**.

### 8-4. methodology.md §5 동기화
구현 후 §5-1을 8-1 공식으로 갱신(코드와 1:1 유지).

### 8-5. 검증
- 백테스트 EPS bias가 더 이상 8/8 음수 단방향이 아니어야 함(체계적 과소추정 해소 신호).
- 사용자가 GM·historical hbm_share 확정 후 EPS MAPE 재측정 → §11 기준(<25%) 대비 보고. 여전히 미달이면 가정 재검토(사용자).
- 일관성 테스트(결함 7) 유지: backtest EPS == forward 엔진 EPS(동일 hbm_share·GM 입력 시).

## 결함 9 (방법론 보강 2차) — cost-per-bit 마진 모델: 가격→마진 연동 (사용자 결정 2026-05-31)

**문제**: 결함 8의 mix 브리지는 HBM 구성 변화는 잡지만 세그먼트 마진(`gm_*`)이 **상수**라 가격→마진 증폭(operating leverage)을 못 잡음. 매출엔 ASP가 반영(`*_asp_qoq`)되는데 마진엔 안 됨 = 구조적 비일관(사용자: "오류, 고쳐야"). DART 직접 검증: 2025Q4 실제 OP margin 58.4%·net 46.4%(FY25 net 44.2%) — 실재. 상수 마진으론 트로프(2023 GP 음수)와 피크(blended GP ~73%)를 동시 재현 불가.

**해법(사용자 선택)**: 세그먼트 마진을 ASP에 연동하는 **bit당 원가 모델**. 매출과 마진이 동일 ASP 동인에서 나오게 → 비일관 근본 제거. **방법론·숫자는 사용자, 구조는 Codex.**

### 9-1. 공식 (methodology §5 재대체 — 결함 8의 상수 gm_* 진화)
서브세그먼트 s ∈ {hbm, ddr, nand, other}, 앵커 분기 a(=forward는 seed, backtest는 윈도 시작):
```
asp_factor_s[t]  = Π_{k=a+1..t} (1 + asp_change_s[k])     # forward: 시나리오 *_asp 가정 / backtest: historical_drivers (price-index)
cost_factor_s[t] = (1 - cost_decline_qoq_s) ** (t - a)    # 공정migration, 가격무관 완만 하락
GP_margin_s[t]   = 1 - (1 - gm_s) * cost_factor_s[t] / asp_factor_s[t]   # t=a → gm_s
R_hbm[t] = hbm_share[t]*R_dram[t];  R_ddr[t] = (1-hbm_share[t])*R_dram[t]
GP_KRW[t] = R_hbm*GP_margin_hbm + R_ddr*GP_margin_ddr + R_nand*GP_margin_nand + R_other*GP_margin_other
GP_margin[t] = GP_KRW[t] / R_total[t]
OP_margin[t] = GP_margin[t] - sga_pct - rnd_pct
```
- **`gm_s` = 앵커 분기 세그먼트 총이익률**(상수 아님, 시작점). 기존 YAML `gm_*` 재해석.
- ASP가 cost보다 빨리 오르면 마진 상승(피크), ASP < cost면 **GP 음수 허용**(트로프).
- **GP floor `max(0,...)` 제거** — 음수 마진이 사이클의 핵심. cap은 상단만(<= ~0.9) 유지 가능.

### 9-2. 스키마/엔진
- `MarginAssumptions`: 추가 `cost_decline_qoq_hbm/ddr/nand`(float, ~0.03-0.04). `gm_*`는 앵커 의미로 유지. `gp_cyclicality` 제거 가능.
- `QuarterlyForecast`: `segment_revenue`가 서브세그먼트 ASP 인덱스(`asp_hbm/asp_ddr/asp_nand`, 앵커=1.0 정규화)를 노출하도록 필드 추가(또는 margin_model이 동일 동인으로 재계산). 이미 내부 계산함(`segment_revenue.py:79-86`) — 노출만.
- `engine/margin_model.py`: 9-1로 재작성. 서브세그먼트 cost-per-bit, 음수 허용.
- `engine/backtest.py`: 각 분기 ASP 인덱스를 `historical_drivers`의 **price-index 변동**으로 누적(윈도 시작 앵커). cost_decline은 가정. `run_backtest`에 필요한 driver 전달.
- `pipeline/ir_loader.py`: `cost_decline_qoq_*` 파싱, `historical_drivers` 분기별 `{hbm_share, hbm_asp_qoq, ddr_asp_qoq, nand_asp_qoq}` 파싱.

### 9-3. ASP driver = 시장 price-index (사용자 입력 A안)
- Forward: 시나리오 `dram_hbm_asp_yoy`·`ddr_asp_qoq`·`nand_asp_qoq`를 **TrendForce/DRAMeXchange contract price**로 본인이 확정(2% placeholder 교체).
- Backtest: `historical_drivers`에 분기별 **실현 price-index 변동**(독립 관측치, 비순환). 본인 입력.

### 9-4. 검증
- 백테스트 GP/EPS가 트로프(2023 음수)·피크(2025 고마진)를 **양 끝 모두** 추종(상수 모델 대비 개선). 단방향 bias 해소.
- 2025Q4 model net margin이 실제 46% 방향으로 근접(가정 현실값 입력 시).
- methodology §5 동기화. 결함 7 일관성 테스트 유지. pytest green.
- **주의**: ASP driver에 actual 마진을 직접 넣지 말 것(순환). price-index만.

## 결함 10 (🟡 버그) — 분기 컨센서스가 매핑 실패로 누락 (HTML 리뷰 #3)

**증상**: 리포트에서 FY26 연간 컨센은 채워지는데 2026Q1~Q4 분기 컨센은 전부 n_a + "quarterly consensus unavailable" 경고. 그러나 yfinance엔 분기 컨센(`0q`/`+1q`)이 **존재**함.
**근본원인**: `pipeline/yahoo_fetcher.py:_records`가 `frame.reset_index().to_json()`로 직렬화 → `earnings_history`의 **날짜 인덱스 컬럼명이 "period"가 아님**(estimate은 인덱스명이 "period"라 통과). 라이브 캐시 검증: earnings_history 4행 전부 `period: null`. → `consensus_loader._next_quarters_from_history`가 `row.get("period")`=None → `quarter_labels=[]` → 분기 컨센 드롭(연간은 무관해 채워짐).
**수정(권장, robust)**: `consensus_loader`에서 분기 라벨을 **`as_of` 날짜로 직접 도출**(earnings_history 의존 제거). 예: as_of=2026-06-02 → 현재분기 2026Q2 → `0q`=2026Q2, `+1q`=2026Q3.
  - 대안/병행: `yahoo_fetcher._records`가 earnings_history 인덱스를 "period"로 명명 후 직렬화.
**검증**: 라이브에서 2026Q2/Q3 분기 컨센이 채워짐(여전히 unreliable 경고는 표시 — 결함 6과 독립). dry-run 픽스처(period 있음)와 라이브 동작 일치.
**주의**: 컨센 자체가 신뢰불가(결함 6)라 값의 효용은 FnGuide 교체(별도 태스크) 전까지 제한적 — 단 버그는 실재하므로 수정.

## 결함 11 (🟡 버그) — Revenue fan 차트 fill 붕괴 (HTML 리뷰 #5)

**위치**: `output/plotly_charts.py:build_fan_chart`.
**증상**: (a) Bull이 선이 아니라 채워진 영역으로 보임. (b) 범례에서 Bear를 숨기면 Bull의 `fill:"tonexty"`가 참조 대상(Bear)을 잃고 **0(축)까지 채워져** 최저점이 0이 되고 y축 autoscale로 슬로프가 평평해 보임.
**근본원인**: 밴드를 `Bear`(no fill) + `Bull`(fill="tonexty"→Bear까지) 두 토글 가능한 trace로 구성 → Bear 숨김 시 fill 기준 붕괴.
**수정**: 밴드를 토글에 견고하게.
  - Bear/Bull을 **동일 `legendgroup`**으로 묶어 함께 토글(밴드 단위), 또는 밴드를 개별 숨김 불가로.
  - Weighted(또는 Base)를 중앙 실선으로 명확히, Bear=하단·Bull=상단 경계선 + 그 사이만 음영.
  - y축이 fill 붕괴로 0까지 안 내려가게(밴드가 사라져도 데이터 기반 range 유지).
**검증**: 임의 trace 토글 시 다른 선의 최저점/슬로프가 변하지 않음. Bull이 경계선으로 보임.

## 결함 12 (🔴 아키텍처) — 통합 연속 마진 체인 (사용자 결정 2026-06-03)

**문제**: cost-per-bit 마진 앵커가 backtest(윈도 시작 2024Q1, GP~30%)와 forward(seed 2025Q4, GP~73%)에서 **정반대 국면**인데 같은 `gm_*`를 공유 → 단일 앵커로 둘 다 못 맞춤. 증거: base `gm_*`를 2024Q1 실측(0.55/0.28..)으로 맞추니 backtest는 정상(EPS MAPE 22%)이나 **forward FY26 EPS 44k·2026Q1 7,292(실제 56,670) 붕괴**. forward가 seed에서 `asp_factor=1.0`으로 **재-앵커**하는 게 원인.

**해법(사용자 선택 #1)**: 마진을 **하나의 연속 사이클**로. 단일 역사 앵커(=`historical_drivers` 최초 분기 2024Q1)에서 ASP를 **역사 + forward 끊김없이 누적**. forward 2026 마진 = 2024Q1 앵커가 2년치 누적 ASP(2025Q3 DDR +47% 포함)로 진화 → 자연히 현재 고마진 도달. backtest는 같은 체인의 부분집합.

### 12-1. 앵커는 시나리오 독립 → YAML/스키마 재구조화
마진 앵커는 **역사적 사실(한 값)**이므로 시나리오별일 수 없음. `gm_*`·`cost_decline_qoq_*`를 시나리오 margins에서 제거하고 **top-level `anchor_margins`**로 이동:
```yaml
anchor_margins:        # 단일 역사 앵커 = historical_drivers 최초 분기(2024Q1) 세그먼트 총이익률
  gm_hbm: 0.55
  gm_ddr: 0.28
  gm_nand: 0.15
  gm_other: 0.10
  cost_decline_qoq_hbm: 0.03
  cost_decline_qoq_ddr: 0.04
  cost_decline_qoq_nand: 0.04
```
- 시나리오 `margins:`엔 `sga_pct_of_revenue`·`rnd_pct_of_revenue`만 남김(opex는 시나리오별 OK).
- 스키마: 신규 `AnchorMargins` 모델. `MarginAssumptions`에서 gm_*/cost_decline 제거(또는 sga/rnd만). `ir_loader`가 `anchor_margins` 파싱 → `profile["anchor_margins"]`.
- 시나리오 마진 발산은 **forward ASP(ddr_asp_qoq·hbm_asp_yoy·nand_asp_qoq)·hbm_share**로 (이미 시나리오별). 앵커·cost_decline은 공유.

### 12-2. forward 연속 누적 (핵심 로직)
1. **carry-over 계산**(anchor→seed): `historical_drivers`(2024Q1..seed=2025Q4)로 세그먼트별
   `asp_factor_at_seed_s = Π(1 + hist_*_asp_qoq_s)`, `cost_factor_at_seed_s = (1-cost_decline_s)**periods_to_seed`, `periods_to_seed`.
   (forecast_window.start=2026Q1 → seed=2025Q4 = historical_drivers 마지막 분기. 정합.)
2. **forward 누적**: 각 forward 분기 i에 대해
   `asp_factor_s[i] = asp_factor_at_seed_s × Π_{1..i}(1 + forward_asp_qoq_s)`,
   `cost_factor_s[i] = cost_factor_at_seed_s × (1-cost_decline_s)**i`,
   `periods[i] = periods_to_seed + i`.
3. `margin_model` 공식 동일: `GP_margin_s = 1 - (1-gm_s)·cost_factor_s/asp_factor_s` (gm_s = anchor_margins, scenario 무관).
- `segment_revenue`(forward): asp 인덱스를 1.0 재시작이 아니라 **carry-over에서 연속**. `margin_periods_since_anchor = periods_to_seed + i`.
- **revenue는 그대로** seed 레벨에서 시드(불변) — margin만 연속. (revenue=레벨@seed, margin=ratio@역사앵커, 분리 정상.)
- 모든 시나리오가 동일 carry-over(anchor_margins + 실현 historical ASP) 공유 후 2026만 시나리오 forward ASP로 발산.

### 12-3. backtest
이미 윈도 시작(2024Q1) 앵커 누적이라 **로직 유지**. 단 앵커 마진을 `anchor_margins`(base 아님)에서 읽도록 정합. backtest와 forward가 **동일 2024Q1 앵커 + 동일 gm_*** 공유 확인.

### 12-4. 검증
- forward FY26 마진이 현실 수준(순익률 ~30-45%) 도달, 2026Q1 model EPS가 수만원대(7k 아님).
- backtest EPS MAPE 유지/개선, bias 단방향 아님.
- methodology §5 동기화. 결함 7 일관성 테스트 유지. pytest green.
- YAML 숫자(anchor_margins·historical_drivers)는 Claude 초안값 유지(사용자 확정 대기).

## 결함 13 (방법론 일관화) — 백테스트 매출도 실현 ASP 사용 (사용자 결정 2026-06-03)

**문제**: 백테스트에서 **마진은 `historical_drivers`의 실현 ASP**를 쓰는데(결함 9/12), **매출은 base 가정 ASP**(`ddr_asp_qoq` base ≈ 균일 +2%)를 씀 → 비일관. 2025Q3 DDR +47% 같은 실현 가격 급등이 마진엔 반영되나 매출엔 안 됨 → peak 분기 매출 -20% 과소추정 → EPS로 전파.

**해법**: 백테스트 매출을 **가정 bit × 실현 ASP**로. ASP·hbm_share는 `historical_drivers`(실현 시장가격, 독립 관측치), bit growth는 base 가정(시험 대상). **비순환**(bit=가정, 가격=관측 — 회사 매출 미투입). 마진 체인과 동일 ASP → 일관.
- **철학**: 백테스트 매출은 이제 "관측 가격 하에서 내 **물량(bit·HBM mix) 가정**이 매출을 재현하는가"를 시험. 가격은 입력(관측), 물량은 모델의 view.

### 13-1. 구현 (backtest only — forward 불변)
- `engine/backtest.py`: 각 테스트 분기 q에 대해 `project_quarterly_revenue`에 넘기는 ASP/hbm_share를 `historical_drivers[q]`로 override, bit growth는 base 유지.
  - 방법: 분기별 1-step `SegmentAssumptions`를 구성 — `dram_ddr_asp_qoq=[hd[q].ddr_asp_qoq]`, `nand_asp_qoq=[hd[q].nand_asp_qoq]`, `dram_hbm_share_qoq=[hd[q].hbm_share]`, `dram_hbm_asp_yoy = hd[q].hbm_asp_qoq*4`(모델이 /4 적용하므로) 또는 분기 HBM ASP를 직접 받게 리팩토링; bit growth(`dram_bit_growth_qoq`·`nand_bit_growth_qoq`·`other_revenue_growth_qoq`)는 base scenario 값 유지.
- **forward 매출은 변경 금지** — 미래엔 실현 가격이 없으므로 시나리오 가정 ASP 사용(올바른 비대칭, 마진 체인과 동일 원칙).
- 마진은 이미 historical ASP 사용 → 동일 분기에 매출·마진이 같은 실현 ASP를 보게 됨(일관).

### 13-2. 검증
- 백테스트 peak 분기 매출 오차 축소(2025Q4 -20.9% → 대폭 개선), revenue MAPE <10% 목표.
- EPS MAPE 추가 개선(매출 전파분 감소).
- **비순환 확인**: 실현 bit/회사매출을 매출식에 넣지 않음(오직 가정 bit × 관측 ASP).
- forward FY26 불변(시나리오 ASP). 결함 7 일관성 테스트 유지. pytest green. methodology §4/§8 동기화.

## 검증 명령 (수정 후 전부 통과해야 함)

```
pytest -q                                          # green 유지
python cli.py --company sk_hynix --dry-run --skip-pdf
python cli.py --company sk_hynix --skip-pdf        # 실데이터
```
**Acceptance 재확인**:
- backtest 분기별 오차가 **서로 다름**(동일값 = 미수정).
- actual 분기 매출이 실제 사이클 범위(~12-25조), 연간치(66·97조) 아님.
- model FY26 매출 ~90-120조 범위.
- 8Q MAPE: 매출<10%, EPS<25%, hit>60% — **실 actual 기준**. 미달 시 가정 재검토 신호로 사용자 보고(YAML 수정은 사용자).
- 리포트에 yfinance 컨센 신뢰불가 경고 표시.
```
```
