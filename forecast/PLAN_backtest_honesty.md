# PLAN — Backtest 정직성 (Backtest Honesty)

> **이 문서는 EFE 세션이 zero-context로 이어받는 핸드오프 plan입니다.**
> 작성 2026-06-10. 구현은 **사용자 승인 후**, workstream 당 **별도 focused 세션**에서.
> 코드/주석/식별자는 영어, 사용자용 출력(리포트·터미널)은 한국어 — 기존 컨벤션 유지.

---

## 0. 한 줄 요약

EFE backtest가 두 가지 이유로 **신뢰할 수 없는 숫자**를 내고 있다.
1. **SK하이닉스 forecast가 실측·컨센서스와 동시에 괴리** → CLAUDE.md 규칙상 "어디서나 괴리 = view가 아니라 miscalibration/bug". **driver 분해로 원인을 먼저 진단**한다(고치기 전에).
2. **방향 hit-rate 87.5%는 skill 신호가 아니다.** 구조적 상승 사이클에서 "항상 up"과 구별 불가. **naive 베이스라인 대비 skill 지표(MASE / Theil U2 / surprise-direction)로 교체**한다.

본 plan은 두 workstream을 **순서대로** 처리한다: **① 진단(read-only/additive)** → 결과로 버그/스케일 문제를 확정 → **② 지표 교체**. ①에서 backtest 숫자 자체가 오염됐다고 판명되면 ②의 베이스라인 비교가 무의미하므로 ①이 선행조건이다.

---

## 1. 현재 상태 (코드 확인 결과, 2026-06-10)

### 1.1 backtest 동작 방식
- `engine/backtest.py::run_backtest` — 각 분기 Q에 대해 직전 4Q를 seed/baseline로 forward 방법론을 그대로 적용(no look-ahead), 실측과 비교해 `revenue_mape` / `eps_mape` / `hit_ratio_direction` / `bias_*` 집계.
- `hit_ratio_direction` = `sign(model QoQ) == sign(actual QoQ)` (backtest.py:163-165). **이것이 README의 87.5% 출처.**
- `engine/signal_backtest.py` — 별개의 텍스트-신호 CAR event study. 여기엔 이미 IC(Spearman)·directional_hit_ratio가 있으나 동일하게 "방향만" 본다. 본 plan의 주 타깃은 **재무 forecast backtest**(`engine/backtest.py`)이며, 신호 backtest는 §6에서 보조적으로만 다룬다.

### 1.2 괴리의 증거 (latest report `reports/sk_hynix_20260603.md`)
**Backtest(실측 대비) — 매출은 잘 맞으나 EPS가 들쭉날쭉:**

| Quarter | Rev Err % | EPS Err % |
|---|---:|---:|
| 2024Q1 | **+0.3%** | **+44.6%** |
| 2024Q4 | −4.5% | −19.4% |
| 2025Q1 | +14.6% | −14.6% |
| 2025Q4 | −12.6% | −13.1% |

→ **결정적 단서**: 앵커 분기 2024Q1은 매출이 거의 정확(+0.3%)한데 EPS가 +44.6% 오버슈팅. 즉 **괴리는 revenue가 아니라 margin→NI→EPS 체인 또는 share count에 있다.** 또한 EPS 오차의 **부호가 분기마다 뒤집힘**(+44.6% / −19.4% / −14.6%) → 단일 방향의 상수 배율 오류(예: 잘못된 고정 share count 단독)로는 설명 안 됨 → **복합 원인**.

**Consensus(컨센서스 대비) — 스케일 자체가 의심:**

| Period | Model | Consensus | Gap % |
|---|---:|---:|---:|
| 2026Q2 EPS | 25,981 | **69,422** | −62.6% |
| FY26 revenue (조원) | 155조 | **332조** | −53.3% |

→ 컨센서스 분기 EPS 69,422원은 최근 실측 분기 EPS(2025Q4 21,909원)의 **3배**, FY26 매출 332조는 SK하이닉스 연매출 규모(수십~100조대)를 크게 초과. `pipeline/consensus_loader.py`는 revenue만 `/1e9` 정규화하고 **EPS는 raw 그대로** 사용(`_clean` 후 무변환, line 81-89). implied-margin>60% 경고만 달릴 뿐 깨진 값이 그대로 gap 표로 흐름. → **"컨센서스와의 괴리"는 상당 부분 컨센서스 정규화 아티팩트일 가능성.** 진단에서 반드시 분리해야 함.

### 1.3 고정 YAML 가정 후보 (`profiles/sk_hynix.yaml`)
- `share_count.weighted_avg_basic: 689000000` — **전 분기 고정**. backtest 전 구간 동일 share로 EPS 계산(eps_bridge.py). 실제 SK하이닉스 가중평균주식수와의 괴리 시 EPS에 배율 bias. 단 부호가 일정해야 하므로 **단독 원인은 아님**(§1.2).
- `anchor_margins` (gm_hbm 0.60, gm_ddr 0.46, gm_nand 0.15…) — "결함 12" 캘리브레이션으로 2024Q1 blended GP 38.6%에 고정했다고 주석. 그런데 2024Q1 EPS가 +44.6% 오버슈팅 → **GP는 맞췄는데 NI가 어긋남** → opex(SG&A/R&D) 또는 tax/finance 단계 의심.

---

## 2. 스코프 가드레일

- **1종목**: SK하이닉스 `000660.KS`. 다종목 확장은 진단·교체가 증명된 후.
- **① 진단은 비파괴(additive/read-only)**: 새 모듈·새 진단 출력만 추가. 기존 forecast 수치를 바꾸지 않는다. 버그 수정은 진단으로 원인이 **확정된 후 별도 변경**으로.
- **surgical**: 변경 라인은 모두 본 plan 항목으로 추적. 인접 코드 리팩토링 금지(발견 시 `NOTICED BUT NOT TOUCHING:`로만 기록).
- Pydantic v2 `extra="forbid"` 유지 → 스키마는 **필드 추가만**(기존 필드 의미 불변, 추가는 안전).

---

# Workstream ① — SK하이닉스 괴리 driver 분해 진단

> **목표: 고치기 전에 "어느 단계가 EPS 오차를 얼마나 만드는가"를 분기별로 수치 귀속(attribution)한다.**
> 산출은 진단 표 + 서면 판정(verdict). 이 세션에서 **수정은 하지 않는다.**

## ①-A. 방법론 — "swap-in actuals" 워터폴 (non-circular)

각 backtest 분기에서 forecast 체인(`segment_revenue → margin_model → tax_finance → eps_bridge`)을 단계별로 **실측값으로 한 단계씩 치환**하며 EPS 오차가 얼마나 줄어드는지 측정. 줄어든 양 = 그 단계의 귀속 오차.

```
E0 = |model_eps − actual_eps| / |actual_eps|                     # 전체 EPS 오차
E1 = 실측 revenue_total(+세그먼트 mix) 주입 후 재계산한 EPS 오차   # revenue 단계 제거
E2 = 추가로 실측 gross_profit(=실측 GP margin) 주입 후 오차        # gross margin 단계 제거
E3 = 추가로 실측 operating_profit 주입 후 오차                     # opex(SG&A/R&D) 단계 제거
E4 = 추가로 실측 net_profit 주입 후 오차                           # tax/finance 단계 제거
# E4 잔차 = share count 단계 귀속(NI는 실측인데 EPS가 어긋나면 분모=주식수 문제)
```

분기별 귀속:
- revenue 기여 = E0 − E1
- gross margin 기여 = E1 − E2
- opex 기여 = E2 − E3
- tax/finance 기여 = E3 − E4
- share count 기여 = E4

> non-circularity: 실측 주입은 **진단 전용 경로**에서만. 실제 backtest forecast는 여전히 no-look-ahead. 진단은 "사후 부검"이지 예측이 아님.

## ①-B. 컨센서스 정규화 진단 (별도 분기)

§1.2의 컨센서스 스케일 의심을 **독립적으로** 확인:
1. `pipeline/yahoo_fetcher` raw 응답에서 `earnings_estimate.avg`·`revenue_estimate.avg`의 원 단위 확인(USD? raw KRW? 연환산?).
2. `consensus_loader`의 revenue `/1e9` vs EPS 무변환의 정합성 점검. EPS가 연환산(annualized)인지, 통화가 다른지 판별.
3. implied net margin을 실측 분기 margin과 대조 — >60%면 깨진 값.
4. **판정**: 컨센서스가 신뢰 가능한가? 불가하면 (a) 정규화 수정 후보를 §3 구현 plan에 적고, (b) 그때까지 consensus gap을 리포트에서 "신뢰불가 플래그"로 표기.

## ①-C. 구현 항목 (승인 후, 진단 세션)
- **신규** `engine/attribution.py` (pure): `attribute_eps_error(target: QuarterlyActual, chain_inputs, ...) -> DriverAttribution`. backtest 루프와 동일한 stage 함수 재사용.
- **스키마** `schemas/models.py`: `DriverAttribution`(quarter_label, eps_error_total, contrib_revenue, contrib_gross_margin, contrib_opex, contrib_tax_finance, contrib_shares) — `extra="forbid"`, 모두 신규.
- **진단 진입점**: `cli.py --diagnose` 플래그(권장) 또는 `scripts/diagnose_divergence.py`. dry-run fixture에서 동작해야 함(샌드박스 네트워크 차단 회피).
- **테스트** `tests/test_attribution.py`: 합성 데이터로 (a) 단계 기여 합 ≈ 전체 오차, (b) 한 단계만 틀린 입력 → 그 단계에만 기여 몰림.

## ①-D. Acceptance (①)
- 8개 backtest 분기 각각에 대해 EPS 오차를 {revenue, gross margin, opex, tax/finance, shares} 기여로 분해한 표.
- 서면 verdict: 지배적 driver(들) + 어떤 고정 YAML 가정(share_count? anchor_margins? opex %?)이 원인인지 + 컨센서스 비교가 스케일로 오염됐는지 yes/no.
- **수정 PR은 별도** — verdict가 지목한 driver만 surgical하게.

---

# Workstream ② — naive 베이스라인 대비 skill 지표 교체

> **목표: "방향 맞췄다"를 "naive보다 잘했다"로 바꾼다.** README 87.5%를 skill-relative 숫자로 대체.

## ②-A. 베이스라인 (model이 이겨야 할 대상)
1. **Random walk (RW)**: forecast Q = seed(Q−1). 가장 단순한 persistence. backtest 루프 안에서 동일 no-look-ahead로 계산.
2. **(가능 시) 컨센서스**: 과거 분기 컨센서스 추정치. `ConsensusRecord.history`에 이미 `{actual, estimate, surprise_pct}` 보유 → 이를 역사 컨센서스로 사용(스냅샷이 아니라 과거 추정이므로 non-circular).

## ②-B. Skill 지표
- **MASE** = model MAE / naive-RW MAE. `<1` = skill. (revenue·EPS 각각)
- **Theil's U2** = model RMSE / RW RMSE. `<1` = skill.
- **Skill score vs consensus** = `1 − model MAE / consensus MAE` (컨센서스 존재 분기 한정).
- **Surprise-direction accuracy** (CLAUDE.md 명시): model이 **편차의 부호**를 맞추는가 — `sign(model_eps − consensus_est)` vs `sign(actual_eps − consensus_est)`. level이 아니라 deviation에서 컨센서스를 이기는지. 표본 N 함께 보고.
- **기존 `hit_ratio_direction`은 유지하되 "참고용 naive 방향 적중률"로 reframe** + RW의 방향 적중률을 나란히 표기 → 독자가 "model 87.5% vs RW 87.5% → edge 없음"을 즉시 봄.

## ②-C. 구현 항목 (승인 후, 별도 세션)
- **신규** `engine/skill_metrics.py` (pure): per-quarter rows + naive RW forecast로 MASE/Theil/skill/surprise 계산.
- **스키마** `schemas/models.py`: `BacktestResult`에 `BacktestSkill` 중첩 모델 추가 (`naive_rw_revenue_mape`, `naive_rw_eps_mape`, `mase_revenue`, `mase_eps`, `theil_u2_revenue`, `theil_u2_eps`, `skill_score_eps_vs_consensus`, `surprise_direction_accuracy`, `n_surprise_scored`). 모두 신규 필드 → `extra="forbid"` 안전. 기존 `hit_ratio_direction` 보존.
- **배선** `engine/backtest.py`: 루프 내 RW forecast(=seed) 동시 산출, 끝에서 `skill_metrics` 호출. consensus history는 `run_backtest`에 optional 인자로 주입(없으면 surprise/consensus 지표는 None).
- **출력** `output/md_builder.py`·`output/html_builder.py`·`output/xlsx_writer.py`: skill 지표 섹션 추가, model 오차 옆에 RW·consensus 오차 병기.
- **README.md**: Backtest Performance 표에서 단독 "Hit ratio 87.5%" 제거 → MASE/Theil U2(<1 목표)·surprise-direction·RW 대비로 교체.
- **테스트** `tests/test_skill_metrics.py`: MASE=1(model==naive), MASE<1(model 우수), Theil 정의, surprise 부호 케이스, consensus 없을 때 None graceful.

## ②-D. Acceptance (②)
- backtest 리포트에 model vs RW vs consensus 오차 + MASE/Theil U2 + surprise-direction(N 포함).
- **skill 주장 기준**: MASE<1 **그리고** Theil U2<1 일 때만 "naive 대비 우위" 표기. 아니면 "no edge"로 정직하게.
- CLAUDE.md 기준 충족: "model은 방향이 아니라 naive-baseline 오차를 이겨야 한다." gap<5% 상시 = "no view", 실측·컨센서스 동시 대괴리 = bug(①로 회귀).
- `pytest -q` green, `python cli.py --company sk_hynix --dry-run` 새 지표 포함 리포트 생성.

---

## 3. 실행 순서 & 세션 분할 (CLAUDE.md: 1 세션 = 1 workstream)

1. **세션 A — 진단(①)**: attribution + 컨센서스 스케일 진단. 비파괴. 산출 = 진단 표 + verdict + (필요 시) `HANDOFF_backtest_diag.md`.
2. **세션 B — 버그 수정(① 후속, 조건부)**: verdict가 지목한 driver/스케일만 surgical 수정. 수정 전 baseline MAPE 기록, 회귀 시 중단·격리.
3. **세션 C — skill 지표(②)**: skill_metrics + 스키마/출력/README + 테스트.

> ②는 ①(특히 세션 B)이 backtest 숫자를 신뢰 가능하게 만든 뒤 의미가 있다. 단, `skill_metrics` 모듈 자체는 ①과 독립이라 순수 함수+테스트는 병행 작성 가능.

## 4. 위험 / 가정
- 샌드박스(Cowork) 네트워크 allowlist로 Yahoo/DART live 호출 실패 가능 → 모든 진단/테스트는 **dry-run fixture** 기준. live 검증은 Windows host에서.
- consensus history(`ConsensusRecord.history`)가 sparse하면 surprise-direction 표본이 작음 → N을 항상 표기하고 작으면 "표본 부족" 주석.
- 8Q는 통계적으로 작은 표본 — MASE/Theil는 점추정일 뿐. 과대해석 금지(리포트에 명시).

## 5. 검증 (양 workstream 공통)
- `pytest -q` 전체 green.
- `python cli.py --company sk_hynix --dry-run` 오프라인 리포트 생성.
- 새 테스트: `tests/test_attribution.py`, `tests/test_skill_metrics.py`.
- 진단 표/skill 표를 수기 1건 교차검증(예: MASE = model MAE / RW MAE 손계산 일치).

## 6. 보조 — signal_backtest 정합 (옵션, 별도)
`engine/signal_backtest.py`의 `directional_hit_ratio`도 같은 "방향만" 함정. 본 plan 범위 밖이나, ② 완료 후 동일 철학(베이스라인 대비 IC·skill)으로 후속 정리 권장. **이번엔 손대지 않음** — `NOTICED BUT NOT TOUCHING: engine/signal_backtest.py:117-125 directional-only hit ratio`.

## 7. 변경 파일 요약 (구현 시, 이 세션 아님)
- ① `engine/attribution.py`(신규), `schemas/models.py`(DriverAttribution), `cli.py`(--diagnose) 또는 `scripts/diagnose_divergence.py`, `tests/test_attribution.py`. 조건부: `pipeline/consensus_loader.py`(스케일 수정).
- ② `engine/skill_metrics.py`(신규), `schemas/models.py`(BacktestSkill), `engine/backtest.py`(배선), `output/{md,html,xlsx}_*`(렌더), `README.md`(표 교체), `tests/test_skill_metrics.py`.
