# PLAN — 세션 C: naive 베이스라인 대비 skill 지표 (Workstream ②)

> **zero-context 핸드오프 plan.** 작성 2026-06-10. 구현은 **사용자 승인 후 별도 focused 세션**에서.
> 코드/주석/식별자 = 영어, 사용자용 출력(리포트·터미널) = 한국어. (기존 컨벤션)
> 선행: `PLAN_backtest_honesty.md` §Workstream ②(원 스펙) + `HANDOFF_backtest_diag.md`(① 진단 + 세션 B 결과). 본 문서는 그 §②를 **세션 B 학습으로 갱신·구체화**한 실행 plan이다.

---

## 0. 한 줄 요약

backtest의 절대 MAPE·`hit_ratio_direction`(README 87.5%)은 **기준점이 없어 판정 불가**다. naive Random-Walk(및 가능 시 과거 컨센서스) 대비 **MASE / Theil U2 / surprise-direction**으로 교체해, "방향 맞췄다"를 "naive보다 잘했다"로 바꾼다. 이로써 세션 B가 남긴 미해결 질문 — *"앵커 수정으로 EPS MAPE가 12.6%→14.7%로 올랐는데, 모델은 여전히 가치가 있나?"* — 에 **정직하게** 답할 측정자를 세운다.

## 1. 왜 지금 (세션 B 이후 맥락)

- 세션 B(gross-margin off-by-one 수정)로 EPS 오차가 더 정직해졌지만 **절대 EPS MAPE는 12.65%→14.66%로 상승**했다(gross-margin +bias가 tax/finance −bias를 상쇄하던 가짜 신호 제거). 이 숫자가 "좋다/나쁘다"는 **baseline 없이는 무의미**하다 — CLAUDE.md: *"Model must beat naive-baseline error, not just hit direction."*
- `README.md` Backtest Performance 표(line 42-47)는 세션 B로 **stale**: EPS MAPE 12.6%·bias −0.2%는 더 이상 사실이 아님(현재 14.7%·−10.6%). 단독 "Hit ratio 87.5% ✅"도 구조적 상승 사이클에선 "항상 up"과 구별 불가. → **이 표가 본 세션의 1차 교체 대상.**
- ①-B 판정(`HANDOFF_backtest_diag.md`): yfinance `.KS` 컨센서스 스냅샷은 **신뢰 불가**(분기 EPS가 실측의 ~3배). → surprise-direction·consensus 비교는 **반드시 `ConsensusRecord.history`(과거 추정 vs 실측)만** 사용. live 스냅샷 절대 금지(순환·오염).

## 2. 스코프 가드레일

- **1종목**: SK하이닉스 `000660.KS`. 다종목은 이후.
- **Additive only**: 새 모듈·새 스키마 필드·새 출력 섹션만. 기존 forecast/backtest 수치 **불변**. `hit_ratio_direction`은 **보존**(삭제 아님, "참고용 naive 방향 적중률"로 reframe + RW 방향 적중률 병기).
- **Pydantic v2 `extra="forbid"`** — 스키마는 **신규 필드 추가만**(기존 의미 불변 → 안전).
- **surgical**: 변경 라인 전부 본 plan 항목으로 추적. 인접 리팩토링 금지.
- **NOT TOUCHING**(다른 워크스트림): `engine/tax_finance.py`(verdict #2, EPS 변동 최대 원천 — 별도), `pipeline/consensus_loader.py`·`engine/consensus_diff.py`(컨센서스 스케일 수정 — ①-B 후속), `engine/signal_backtest.py`(텍스트 신호 CAR, line 117-125 directional-only — `NOTICED BUT NOT TOUCHING`). gross-margin 잔차 lag(+3.2%)도 본 세션 아님.

---

## 3. 설계

### 3.1 베이스라인 (model이 이겨야 할 대상)
1. **Random Walk (RW)** = persistence: 분기 Q 예측 = seed(Q−1) 실측값. `revenue_RW = seed.revenue_total`, `eps_RW = seed.eps_basic`. backtest 루프 내에서 **동일 no-look-ahead**로 산출(seed는 이미 루프에 있음 — `iter_backtest_forecasts`가 `(seed, target, forecast)` yield).
2. **과거 컨센서스 (가능 분기 한정)** = `ConsensusRecord.history[quarter_label]` = `{actual, estimate, surprise_pct}`(schemas/models.py:275-276). 스냅샷이 아니라 **그 분기 시점의 추정**이라 non-circular. sparse하면 해당 지표는 그 분기만 스킵하고 N 표기.

### 3.2 Skill 지표 (revenue·EPS 각각)
- **MASE** = model MAE / RW MAE. `<1` = skill.
- **Theil's U2** = model RMSE / RW RMSE. `<1` = skill.
- **Skill score vs consensus** = `1 − model MAE / consensus MAE` (history 존재 분기 한정).
- **Surprise-direction accuracy** (CLAUDE.md 명시) = `mean[ sign(model_eps − est) == sign(actual − est) ]`, `est = history[q]["estimate"]`. **level이 아니라 컨센서스 대비 편차의 부호**를 맞추는가. 표본 N 동반.
- reframe: `hit_ratio_direction`(model)과 **RW의 방향 적중률**을 나란히 → 독자가 "model 87.5% vs RW ≈87.5% → edge 없음"을 즉시 본다.

### 3.3 컴포넌트 (구현 항목)
- **신규 `engine/skill_metrics.py`** (pure, IO 없음): 입력 = backtest per-quarter rows(model + RW + 실측) + optional `consensus_history: dict[str, dict[str,float|None]]`. 출력 = `BacktestSkill`. 엔진은 Pydantic 모델 반환(컨벤션, DataFrame 금지).
- **스키마 `schemas/models.py`**: 신규 중첩 모델 `BacktestSkill`(`extra="forbid"`) — 필드 전부 신규:
  `naive_rw_revenue_mape, naive_rw_eps_mape, mase_revenue, mase_eps, theil_u2_revenue, theil_u2_eps, rw_hit_ratio_direction, skill_score_eps_vs_consensus: float|None, surprise_direction_accuracy: float|None, n_surprise_scored: int`.
  `BacktestResult`에 `skill: BacktestSkill | None = None` 추가(신규 optional → 기존 테스트 안전).
- **배선 `engine/backtest.py`**: `run_backtest`에 optional 인자 `consensus_history: dict | None = None` 추가. 루프에서 RW(=seed) per-quarter 동시 수집 → 끝에서 `skill_metrics.compute_skill(rows, consensus_history)` 호출해 `BacktestResult.skill` 채움. **기존 forecast 수치·기존 필드 불변**(테스트로 보증).
- **cli 배선 `cli.py`**: 이미 `ConsensusRecord` 생성됨(consensus_loader, line 139·273). 그 `record.history`를 `run_backtest(..., consensus_history=record.history)`로 주입(line 246 호출부). 없으면 None → consensus 지표 None graceful.
- **출력**: `output/md_builder.py`·`output/html_builder.py`·`output/xlsx_writer.py` — skill 섹션 추가, model 오차 옆에 RW·consensus 오차 + MASE/Theil/surprise(N) 병기. 작은 표본 경고 주석.
- **README.md** (line 42-47 표 교체): stale 수치 갱신 + 단독 "Hit ratio 87.5%" 제거 → MASE/Theil U2(<1 목표)·surprise-direction·RW 대비로. EPS MAPE는 "RW 대비"와 함께만 제시(절대값 단독 금지).

### 3.4 테스트 우선 (failing-test → pass)
- **신규 `tests/test_skill_metrics.py`** (합성, 네트워크 무관):
  - MASE=1 정확히(model==RW), MASE<1(model 우수), MASE>1(model 열등).
  - Theil U2 정의 손계산 일치.
  - surprise-direction: model·actual이 est의 같은 쪽 → 1, 반대 → 0; history 없는 분기 제외, N 정확.
  - consensus_history=None → skill_score/surprise None, RW 지표는 정상.
  - `BacktestResult.skill is None` 경로(미주입) 회귀 없음.
- 기존 `tests/test_backtest.py`: `run_backtest` 시그니처 확장 후에도 **전부 green**(skill 미주입 시 기존 동작 동일) 확인.

---

## 4. 실행 순서 (failing-test 우선, goal-driven)

1. **baseline 고정**: `pytest -q` green, `python cli.py --company sk_hynix --dry-run` 현재 리포트 1부 보관(전/후 비교용). 세션 B 후 현재값: 매출 MAPE 9.51%, EPS MAPE 14.66%, bias_eps −10.55%.
2. **`skill_metrics.py` + `test_skill_metrics.py`**: 순수 함수부터 TDD. (backtest 배선과 독립이라 먼저 완성 가능.)
3. **스키마 `BacktestSkill` + `BacktestResult.skill`** 추가.
4. **`run_backtest` 배선** + RW 수집. 기존 backtest 테스트 green 유지.
5. **cli `consensus_history` 주입** + 출력 렌더(md/html/xlsx).
6. **README 표 교체** + stale 수치 갱신.
7. **재측정**: dry-run 리포트에 model vs RW vs consensus + MASE/Theil/surprise(N) 표시. 수기 1건 교차검증(MASE = model MAE / RW MAE 손계산 일치).

## 5. Acceptance

- backtest 리포트(md/html/xlsx)에 **model vs RW vs consensus 오차 + MASE/Theil U2 + surprise-direction(N 포함)**.
- **skill 주장 기준**: `MASE<1` **그리고** `Theil U2<1`일 때만 "naive 대비 우위" 표기. 아니면 **"no edge"로 정직하게**. (세션 B 후 EPS MASE가 1 근처/초과로 나올 가능성 있음 — 그러면 그게 정답이고, tax/finance(verdict #2)가 다음 타깃임을 데이터로 확증.)
- surprise-direction은 **`ConsensusRecord.history`만** 사용(live yfinance 금지). N 항상 표기, 작으면 "표본 부족" 주석.
- `README.md`에서 단독 87.5% 제거, 측정자 기반으로 교체. stale EPS MAPE/bias 갱신.
- `pytest -q` 전부 green, `--dry-run` 새 지표 포함 오프라인 리포트 생성.

## 6. 위험 / 가정

- 8Q = 통계적으로 **작은 표본**. MASE/Theil은 점추정 — 리포트에 과대해석 금지 주석.
- `ConsensusRecord.history`가 sparse면 surprise/consensus 지표 N 작음 → graceful None + N 표기.
- **샌드박스**: cache hit로 오프라인 동작. live Yahoo/DART는 host(Windows)에서만. `pipeline/_ssl_setup.py`의 `C:\temp\...` 경로는 **host 전용** — 샌드박스 import 시 우회 필요(세션 B 메모: cwd에 해당 리터럴 파일 touch 또는 `DART_API_KEY` 더미 + cache). `pip install scipy --break-system-packages`(signal_backtest 테스트 의존성)도 세션마다 재설치.
- `run_backtest` 시그니처에 optional 인자 추가는 **호출부 전부 점검**(cli.py:246, diagnose 스크립트, 테스트) — 기본값 None이라 하위호환.

## 7. 변경 파일 요약 (구현 시, 이 세션 아님)

신규: `engine/skill_metrics.py`, `tests/test_skill_metrics.py`.
수정: `schemas/models.py`(BacktestSkill + BacktestResult.skill), `engine/backtest.py`(RW 수집·skill 배선·optional consensus_history), `cli.py`(history 주입), `output/md_builder.py`·`output/html_builder.py`·`output/xlsx_writer.py`(렌더), `README.md`(표 교체).
NOT TOUCHING: `engine/tax_finance.py`, `engine/consensus_diff.py`, `pipeline/consensus_loader.py`, `engine/signal_backtest.py`.

## 8. 후속 (본 세션 아님)

- skill 지표가 "tax/finance에서 baseline에 진다"를 보이면 → **verdict #2 tax/finance 진단** 세션(FX·below-the-line vs 고정세율; overlay/오차밴드 후보).
- gross-margin 잔차(+3.2%, 고-ASP 분기 집중) → ASP→margin **대칭 lag/EMA** 또는 2025Q3 ddr_asp_qoq 드래프트값 재검토(사용자 소유).
- `signal_backtest`의 directional-only hit ratio도 동일 철학으로 정리(별도).
