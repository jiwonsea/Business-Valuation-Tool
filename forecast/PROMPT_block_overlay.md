# PROMPT — below-OP block → 오차밴드/overlay (verdict #2 구조적 절반, 다음 세션)

> **zero-context 세션 킥오프 프롬프트.** 작성 2026-06-20 (tax/finance 세션 후속).
> **plan mode로 시작** — 스키마 + 출력 변경이라 3개+ 파일·되돌리기 어려운 변경. 설계 확정 후 `PLAN_tax_finance_overlay.md` 저장 → fresh 세션에서 구현.
> 코드/주석/식별자 = 영어, 사용자용 출력 = 한국어. 선행 읽기: `PLAN_tax_finance.md`(§3.2/3.3/5/6), `scripts/diagnose_tax_finance.py`, `CLAUDE.md`(2층 분리 원칙 + overlay 스키마 구상), Cowork 메모리 `efe-tax-finance-bias-split`.

## 0. 한 줄 요약
tax anchor 수정(0.20→0.164, 이전 세션)으로 EPS bias가 −10.55%→**−6.41%**로 줄었다. 남은 −6.41% bias와 분기 스윙(2024Q4 −23%, 2025Q1 −19%, 2025Q3 −3%, …)은 **전부 below-OP block**(= pretax − OP = net financial / FX 평가손익 / 지분법 / 일회성)에서 온다. 이 block은 −1,516 ~ +3,407 ₩bn으로 분기마다 크게 튀어 **점추정으로 잡으면 overfitting**. 목표: 이 변동성을 **EPS 점추정에 넣지 말고**(lookahead 위험) 오차밴드 / date-tagged overlay 레이어로 정직하게 표현한다.

## 1. 왜 (데이터 근거, 이전 세션 확정)
- `scripts/diagnose_tax_finance.py`가 −8.0% tax/finance 레버를 둘로 분해(additive identity 정확): 세율 갭 −3.9%(이미 수정) + **below-OP block −4.1%(미해결)**.
- block 분기값(₩bn): 2024Q1 −513, Q2 −416, Q3 −151, Q4 +1,499, 2025Q1 +1,859, Q2 −490, Q3 +3,407, Q4 −1,516. 큰 양(+) 분기가 net_financial(FX/valuation 이익)·non-op·지분법 일회성에서 발생 → 현 `net_interest_pct=-0.008`(−100~−260) 평평한 proxy가 못 잡음.
- **CLAUDE.md 2층 분리 원칙**: earnings drivers(메모리 가격, HBM/Nvidia) → forward EPS / 매크로·타이밍·리스크(FX 손익, CPI/PPI, UST, USD/KRW) → valuation·entry·risk-band. FX 평가손익은 EPS driver가 **아니라** risk-band.

## 2. 스코프 가드레일
- **EPS 점추정 불오염이 핵심 acceptance.** overlay/밴드는 *표현*만 — forecast EPS 숫자는 bit-identical 유지. no-look-ahead backtest 경로에 FX/일회성 절대 미투입.
- **Additive 스키마 변경만.** Pydantic v2 `extra="forbid"` 유지하며 신규 `overlays:` 필드 추가(기존 의미 불변).
- **NOT TOUCHING:** revenue/gross-margin 체인, tax anchor(직전 세션 확정 0.164), `pipeline/consensus_loader.py`(consensus_wiring 완료), `engine/skill_metrics.py`, `engine/attribution.py`.
- 가정 수치(밴드 폭·overlay magnitude/confidence)는 **초안·제안까지만 — 확정·소유 = 사용자**(CLAUDE.md).

## 3. 설계 후보 (plan mode에서 확정)
### 3.1 오차밴드 (point estimate 위 표현 레이어)
- below-OP block 변동성(분기 std)을 EPS 시나리오 밴드 폭에 반영. 후보: block/NI 비율의 8Q std(robust: trimmed/MAD)를 EPS 밴드 ± 폭으로. bear/bull 시나리오 밴드와 어떻게 합성할지 설계.
- 출력(`output/` html/md/xlsx, fan chart): "below-the-line 변동성" 주석 + EPS 밴드. surprise-direction(consensus 배선 완료)과 함께 보면 "level은 약간 과소(−6.4%)지만 컨센 대비 방향은 맞춘다" 그림 정합.
### 3.2 overlay 스키마 (date-tagged, lookahead-safe)
- CLAUDE.md 제안: per-profile `overlays: {as_of_date, driver, direction, magnitude, confidence}`. Pydantic v2 모델 신규(`schemas/models.py`). **as_of_date < 대상 분기 period_end 보장**(lookahead 가드를 코드+테스트로).
- overlay는 valuation/entry/risk 레이어에만 주입 — EPS bridge 미투입을 타입/경로로 강제(예: overlay는 `valuation_bridge.py`만 소비, `eps_bridge.py`·`tax_finance.py` 미접근).
### 3.3 데이터 한계 (명시)
- DART 요약 CIS는 FinanceIncome/FinanceCosts 안에서 이자 vs FX를 안 쪼갬 → 이자/FX 분리는 주석(footnote, 호스트 필요). block 총액은 캐시로 정확. overlay magnitude는 사용자 IR 가정 입력.

## 4. 실행 순서 (plan mode → 구현)
1. **plan mode**: 3.1/3.2 설계 확정 → `PLAN_tax_finance_overlay.md` 저장 → 사용자 승인.
2. baseline: `pytest -q` green, 현 EPS 점추정·밴드 보관(before).
3. (승인 후 fresh 세션) failing-test 먼저: overlay lookahead 가드(as_of_date ≥ period_end → reject), EPS 점추정 불변 회귀, 밴드가 실측 block 스윙을 커버하는지.
4. 스키마·출력 구현 → 8Q 재측정. **EPS 점추정 bit-identical** + 밴드만 추가 확인.
5. 회귀: revenue/GP/OP/EPS 점추정 경로 bit-identical, `pytest -q` green, `--dry-run` 새 출력.

## 5. Acceptance
- below-OP 변동성이 EPS **점추정이 아니라** 오차밴드/overlay로 표현 — EPS 숫자에 lookahead 미반영(테스트 보증).
- overlay date-tagged, as_of < period_end 강제. overlay는 valuation/risk만 소비(EPS bridge 격리).
- forecast EPS·MASE·Theil·revenue 수치 **불변**. 가정값(밴드 폭·overlay) 전부 사용자 확정 후. `pytest -q` green.

## 6. 위험 / 가정
- below-OP(특히 FX)는 구조적으로 예측 난이 — 밴드로 "정직한 구간" 목표, bias 0 추구 금지(overfitting).
- 8Q 소표본 → 밴드 폭 robust 추정(MAD/trimmed), 1~2 이상치 분기(2025Q3 +3,407)에 안 휘둘리게.
- 스키마 변경 = Pydantic `extra="forbid"` 신규 필드만, 기존 직렬화 불변.

## 7. 변경 파일 (구현 시, plan 후 확정)
신규: `PLAN_tax_finance_overlay.md`, overlay 테스트. 수정: `schemas/models.py`(overlay 모델), `engine/valuation_bridge.py`(밴드/overlay 소비), `output/*`(밴드 렌더), `profiles/sk_hynix.yaml`(`overlays:` 초안 — **사용자 확정**).
NOT TOUCHING: revenue/gross-margin 체인, `engine/eps_bridge.py`·`tax_finance.py`(점추정), consensus 배선, `skill_metrics.py`.

## 8. 런타임 메모
- 오프라인 재현: DART 캐시(`reports/.cache/`, gitignore — 테스트는 `tests/fixtures/` 사용), `DART_API_KEY=dummy`, `pytest -q`.
- **Cowork mount staleness 주의**: 기존 파일을 file-tool로 edit 후 bash가 truncated 캐시를 읽을 수 있음 → bash로 검증(`grep`/parse), stale면 새 파일 Write + `cp` 재동기화(메모리 `cowork-mount-stale-edits`). bash `rm`이 막히면 `allow_cowork_file_delete`.
- 직전 세션 tax anchor: base 0.164 / bear 0.184 / bull 0.154 (DRAFT). `tests/test_tax_finance.py`가 anchor를 fixture에 고정.
