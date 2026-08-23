# HANDOFF — Backtest 괴리 진단 결과 (Workstream ①)

> 세션 2026-06-10. `PLAN_backtest_honesty.md` workstream ① "SK하이닉스 괴리 driver 분해 진단"의 **실행 결과 + verdict**.
> 진단은 **비파괴**(forecast 수치 불변). 수정은 본 verdict가 지목한 driver만 별도 세션에서.
> 재현: `DART_API_KEY=<any> python scripts/diagnose_divergence.py --company sk_hynix` (cache hit → 오프라인 동작).

## 추가/변경 파일
- `engine/attribution.py` (신규) — realized-ratio bridge로 분기 EPS 오차를 5개 lever에 가산 분해.
- `schemas/models.py` (+) — `DriverAttribution` 모델.
- `engine/backtest.py` (refactor) — projection loop를 `iter_backtest_forecasts`로 추출, `run_backtest`가 이를 소비. **forecast 수치 불변**(기존 `tests/test_backtest.py` 전부 green로 보증).
- `scripts/diagnose_divergence.py` (신규) — cli 로딩 미러 + attribution 표 출력.
- `tests/test_attribution.py` (신규) — 기여 합 = 전체 오차, 단일-lever 국소화, share-only, 가드.
- 검증: `pytest -q` → **49 passed**.

## 진단 표 (8Q, base 가정, DART 캐시 실측 기준)

| Quarter | EPS err | revenue | gross-m | opex | tax/fin | shares |
|---|---:|---:|---:|---:|---:|---:|
| 2024Q1 | +44.6% | +0.5% | **+17.3%** | +10.8% | +16.2% | −0.2% |
| 2024Q2 | −1.7% | −14.4% | +12.6% | −3.0% | +3.3% | −0.1% |
| 2024Q3 | +1.2% | +3.7% | +6.5% | −4.3% | −4.6% | +0.1% |
| 2024Q4 | −19.4% | −3.8% | +9.0% | −3.6% | **−21.1%** | +0.1% |
| 2025Q1 | −14.6% | +10.9% | +1.9% | +0.8% | **−28.3%** | +0.1% |
| 2025Q2 | +3.8% | −14.5% | +16.2% | −1.2% | +3.1% | +0.2% |
| 2025Q3 | −2.8% | +12.9% | +15.4% | −2.2% | **−29.1%** | +0.2% |
| 2025Q4 | −13.1% | −12.6% | +6.0% | −6.4% | −1.2% | +1.0% |
| **MEAN** | | −2.2% | **+10.6%** | −1.1% | **−7.7%** | +0.2% |

(각 행: 해당 lever를 실측으로 치환했을 때 줄어드는 상대 EPS 오차. 5개 합 = EPS err.)

## Verdict

**1. 지배적·계통적 miscalibration = gross margin (anchor_margins / cost-per-bit 체인).**
- 평균 **+10.6%**, **8개 분기 전부 양(+)** → 모델 GP마진이 일관되게 실측보다 높음(단방향 bias).
- **결정적 모순**: profile 주석은 anchor를 "DART 실측 2024Q1 blended GP 38.6%에 고정"한다고 명시("결함 12" 캘리브레이션). 그러나 2024Q1조차 gross margin 기여 **+17.3%** → 모델 GP마진 ≈ 38.6%×1.17 ≈ **45%**. **앵커가 실제로 38.6%를 재현하지 못한다.** 원인 후보: `project_quarterly_revenue`의 ASP carryover(`asp_hbm/ddr/nand`) + `cost_decline_qoq_*` + `margin_periods_since_anchor`가 앵커 분기에서부터 마진을 들어올림(`margin_model._cost_per_bit_margin`: `cost_factor/asp_factor`가 1Q차부터 1을 초과).
- **→ 최우선 수정 대상.** 앵커 분기에서 blended GP가 정확히 실측과 일치하도록 cost-per-bit 체인/초기 periods·ASP factor를 재캘리브레이션(failing-test부터: "2024Q1 모델 GP마진 == 실측 38.6%").

**2. 분기별 EPS 변동성의 최대 원천 = tax/finance (OP→NI 전환).**
- 평균 −7.7%지만 분기 스윙이 **−29.1% ~ +16.2%**로 큼. 고정 `effective_tax_rate=0.20` + `net_interest_pct`가 실측 below-the-line(FX 평가손익·지분법·일회성 등)을 못 잡음.
- 이건 "캘리브레이션 버그"라기보다 **본질적으로 예측 어려운 항목** → CLAUDE.md의 overlay 레이어(매크로/FX 리스크) 또는 EPS 오차밴드 확대로 다룰 후보. 점추정 가정 미세조정으로는 해결 안 됨.

**3. share count = 문제 아님 (가설 기각).**
- 평균 +0.2%, 최대 +1.0%. 모델 고정 689,000,000 vs 실측 implied(최신) 695,876,261 → ~1% 차이. **EPS 괴리의 원인이 아니다.**

**4. revenue = 평균적으로 unbiased (양호).**
- 평균 −2.2%, 분기 스윙 ±14%는 노이즈. 세그먼트/ASP 매출 레이어는 평균적으로 편향 없음(낮은 매출 MAPE와 정합).

## ①-B 컨센서스 스케일 진단 (별도 분기)

`reports/.cache/yahoo_000660_KS_20260603.json` raw 확인:
- revenue_estimate avg: 0q=**81.8조**, +1q=96.8조, 0y(연)=**332.8조**, +1y=446조 KRW.
- earnings_estimate avg(EPS/주): 0q=**69,422**, +1q=82,073, 0y=295,507원.

판정: **컨센서스 원본 데이터 자체가 비현실적.** SK하이닉스 실측 분기 매출(2025Q4 32.8조)·연매출(수십~100조대) 대비 revenue가 **2.5~5배**, 분기 EPS가 최근 실측(~22,000원)의 **~3배**. `consensus_loader`의 revenue `/1e9` 정규화는 **단위 버그 아님**(81.8e12→81,815.9bn 정상) — yfinance `.KS` 추정치가 신뢰 불가한 것. 기존 implied-margin>60% 가드는 **연간에만 발화**(분기 58.5%로 미발화)하고, 깨진 값이 그대로 consensus-gap 표로 흘러 "model −54~−63% below consensus"를 만든다.

**→ "컨센서스와의 괴리"는 대부분 컨센서스 데이터 품질 문제이지 모델 오차가 아니다.** 실측 대비 진짜 miscalibration은 위 #1(gross margin)이다.
- 후속(②/별도): consensus-gap을 reliability 가드에 종속(분기에도 발화하도록 임계·구현 강화, 깨진 값은 gap 표에서 "신뢰불가"로 표기/억제). 중기엔 KR 컨센서스 소스(네이버 금융/FnGuide, README 로드맵)로 교체.

## 다음 세션 (gated)
- **세션 B (① 수정)**: gross-margin 앵커 재캘리브레이션 — failing-test("2024Q1 GP마진==실측") → cost-per-bit 체인 수정 → 8Q 재측정. baseline MAPE 먼저 기록, 회귀 시 중단·격리. (tax/finance·consensus는 별개로 분리.)
- **세션 C (②)**: naive 베이스라인 대비 skill 지표(MASE/Theil U2/surprise-direction) — `engine/skill_metrics.py`. **단, ①-B 때문에 surprise-direction은 yfinance 컨센서스가 아니라 `ConsensusRecord.history`(과거 추정 vs 실측) 기반으로만.**

## 세션 B 결과 — gross-margin 앵커 off-by-one 수정 (2026-06-10)

**한 줄 before/after:** gross-margin 기여 평균 **+10.6% → +3.2%**, 8분기 전부 양(+) → 부호 혼재(−2.8%~+12.1%); 앵커 2024Q1 모델 GP **43.84% → 38.42%**(실측 38.57%, ±0.16%p). 매출 MAPE 9.51%→9.51%(불변), **EPS MAPE 12.65%→14.66%(회귀)**.

**근본 원인 (격리 완료, 추정 아님):** `engine/backtest.py::iter_backtest_forecasts`의 ASP/period 누적이 **앵커(첫 스코어) 분기에서부터** 실행됨. 앵커 분기 margin 계산 직전에 이미 `periods_since_anchor=1`, `asp_*≈1.05~1.08`가 주입돼(`diagnose` 계측으로 확인) `_cost_per_bit_margin`의 `cost_factor/asp_factor>1` → 앵커가 실측 38.6%를 재현 못 함. 진단 후보 (a)periods off-by-one + (b)앵커 자기 qoq 포함이 **동일 한 곳**에서 동시 발생. (c)가정 수치는 1차 원인 아님(앵커는 periods=0/asp=1.0 가정으로 캘리브레이션돼 있었음).

**수정 (surgical, 1곳):** 누적 블록을 `if idx > start_idx:`로 가드 → 앵커는 reference(periods=0, asp=1.0)로 고정, 누적은 앵커 다음 분기부터. 앵커 qoq는 "앵커로 들어오는 변화"라 post-anchor 레버리지에서 제외(매출 측 driver 해석과 일관). **가정 수치(gm_*/cost_decline) 미변경.**

**테스트:** `tests/test_backtest.py` +`test_anchor_quarter_reproduces_actual_gross_margin`(실데이터, DART 캐시; 환경 없으면 skip) — 앵커 GP==실측 ±1.5%p. 기존 `test_backtest_accumulates_..._window_anchor`는 버그 동작을 인코딩하고 있어 corrected semantics로 수정(2024Q2 asp_ddr 1.21→1.10, periods 2→1). `pytest -q` → **50 passed**.

**회귀 보고 (가드레일):** EPS MAPE +2.0%p 악화는 **이번 수정이 틀려서가 아니라**, 그동안 gross-margin의 +bias가 tax/finance의 −bias를 상쇄해 EPS 오차를 인위적으로 0 근처로 만들고 있었기 때문(bias_eps −0.24%→−10.55%). diagnose 표의 tax/fin 열은 사실상 불변(예: 2025Q1 −28.3→−28.5, 2025Q3 −29.1→−29.2)으로 내가 건드리지 않았음을 확인. 매출 MAPE는 bit-identical → 변경이 margin 경로에만 격리됨. **두 버그가 상쇄하던 가짜 신호가 사라진, 더 정직한 상태.** tax/finance는 별도 세션(verdict #2, overlay/오차밴드) — 본 세션 스코프 아님.

**잔차 (사용자 소유):** 평균 +3.2%는 목표 ±2~3%p를 소폭 초과. 잔차는 DDR ASP 급등 분기(2025Q2 +9.4%, 2025Q3 +12.1%; 2025Q3 ddr_asp_qoq +0.47)에 집중 → `_cost_per_bit_margin`의 ASP 탄력성이 실측 blended 마진보다 과도하게 확장(cause c 영역). 이는 구조/가정 수치 결정이라 **직접 확정하지 않음**. 후보 레버(출처·방향만): `cost_decline_qoq_ddr`↓ 또는 ASP→마진 전이 댐핑 도입(고-ASP 분기 마진 상단 억제). 사용자가 레버 선택 시 before/after attribution 재실행 제공 가능.

**NOTICED BUT NOT TOUCHING:** `engine/tax_finance.py`(분기 EPS 변동성 최대 원천, verdict #2), `engine/consensus_diff.py`·`pipeline/consensus_loader.py`(컨센서스 데이터 품질, ①-B), `engine/signal_backtest.py`.

## 주의 (이번 세션 메모)
- 워킹트리에 내 변경과 무관한 line-ending(CRLF/LF) 재인코딩 변경이 다수 존재(CLAUDE.md, docs/, graphify-out/, reports/, tests/fixtures/*.json). 내용 동일·줄끝만 다름. **내 실질 변경은 `engine/backtest.py`, `schemas/models.py`, 신규 4파일뿐.** 커밋 전 `git add -p` 또는 `.gitattributes`로 line-ending 정리 권장.

## 세션 C 결과 — skill 지표 실측 해석 (2026-06-19)

**실측 경로(중요):** 샌드박스에서 **오프라인 재현 성공.** DART 캐시(2023–2025 전 분기 존재)로 backtest를 돌리면 `BacktestResult.skill`이 실측으로 채워진다(`--dry-run` fixture와 달리 분기 충분). cli 전체 실행은 2026 forward 분기 캐시 미스로 네트워크를 타지만, backtest는 2023–2025만 필요 → cli 배선(line 242-256)을 그대로 미러한 read-only 스크립트로 산출. headline이 PLAN 베이스라인과 **bit-identical**(매출 MAPE 9.51%, EPS MAPE 14.66%, bias_eps −10.55%) → 실측 확인. (yahoo 캐시는 today-날짜 키라 기존 스냅샷을 today로 alias; `_ssl_setup`의 `C:\temp\...`는 리눅스에서 literal-name 파일 touch로 우회.)

**한 줄 before/after:** "절대 MAPE·87.5% 방향적중 → 판정 불가"였던 backtest가 → **naive RW 대비 매출·EPS 둘 다 skill 확인**(EPS MASE 0.49 / Theil 0.51, 매출 0.65 / 0.64). 방향적중은 model 87.5% **= RW 87.5%** → edge 아님(구조적 up-cycle). EPS의 −10.55% bias는 계통적(8분기 중 7분기 과소예측)으로 잔존.

**실측 skill 표 (8Q, base):**

| | naive RW MAPE | MASE | Theil U2 | 판정 |
|---|---:|---:|---:|---|
| 매출 | 14.79% | **0.654** | **0.640** | <1 & <1 → **우위** |
| EPS | 44.87% | **0.488** | **0.505** | <1 & <1 → **우위** |

- 방향: model 87.5% = RW 87.5% → 방향은 edge 위치 아님. edge는 **magnitude/궤적**에 있음(절대 14.7% EPS MAPE는 RW 44.9%의 1/3 미만이라 진짜 skill).
- **분기점 판정:** PLAN §2.1(EPS MASE≥1 → tax/finance)이 **데이터로 기각**됨. EPS는 RW를 크게 이김 → §2.2(edge) 분기. 단 §2.2가 tax/finance를 배제하는 건 아님 — MASE/Theil는 dispersion-상대 지표라 단방향 level bias를 거의 벌하지 않음(RW가 워낙 나빠 biased 모델도 이김). −10.55% bias는 ① attribution상 below-the-line(tax/finance, 평균 −7.7%)에 집중 → verdict #2는 여전히 유효한 **실체적** 다음 타깃.

**NOTICED — consensus 배선 버그 (신규 발견, 본 세션 미수정):** surprise-direction·consensus-skill이 **N=0/None**으로 나온 원인은 컨센 부재가 아니라 `pipeline/consensus_loader.py:93`이 `row.get("period")`를 읽는데 캐시의 `earnings_history` 행은 그 필드를 **`"quarter"`**로 키한다(yahoo_fetcher `_records`의 reset_index 산물). → vintage 추정치 전량 silently drop. **호스트에서도 동일 실패** → 사용자의 호스트 실행도 surprise=N/A였을 것. vintage 추정치 자체는 존재·현실적(2025Q2 est 9338 vs 실측 9572, 2025Q3 est 12586 vs 17850 — ①-B가 지적한 *forward* 스냅샷의 3배 깨짐과 다름). **in-memory로 `quarter→period` 패치 시**(저장 안 함) 8Q 중 3분기 겹침: `skill_score_eps_vs_consensus = +0.483`(모델 EPS MAE ≈ 컨센의 52%), `surprise_direction_accuracy = 1.0 (3/3)`. **단 N=3 < 4 → 참고용**(PLAN §1). 모델이 컨센을 이기는 건 부분적으로 컨센이 up-cycle을 더 강하게 lowball(모든 vintage 추정이 실측 아래)한 결과.

**다음 워크스트림 (확정, 데이터 근거):**
1. **`PLAN_consensus_wiring.md` — 즉시 1순위.** §2.2 경로(컨센서스, ①-B 계열)에 정확히 안착하는 1-line 버그 수정. thesis-정의 지표(컨센 대비 gap)를 모든 환경에서 살리고 N을 키운다. 최저비용·최고레버리지.
2. **`PLAN_tax_finance.md` — verdict #2, 실체적 2순위.** −10.55% 계통 EPS bias(FX·below-the-line vs 고정세율) 분리. 모델 EPS 숫자 자체를 개선.
- (1)은 *측정*을 살리고 (2)는 *예측*을 고친다. 순서: 측정 먼저(싸고 thesis-critical) → 예측.

**수치 변경 대기:** 가정값 변경 없음. README "리포트 참조" 자리는 실측 MASE/Theil/RW-MAPE로 채움(surprise는 "보류¹"+버그 각주). 컨센 버그 수정·N 확대는 사용자 확정 후 별도 세션.
