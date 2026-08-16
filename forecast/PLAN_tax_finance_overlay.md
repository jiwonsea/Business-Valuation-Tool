# PLAN — below-OP block → 오차밴드 / overlay (verdict #2 구조적 절반)

> **zero-context 핸드오프 plan.** 작성 2026-06-20 (tax/finance anchor 세션 후속). 구현은 **사용자 승인 후 별도 focused 세션**에서.
> 코드/주석/식별자 = 영어, 사용자용 출력(리포트·터미널) = 한국어. 선행: `PLAN_tax_finance.md`(§3.2/3.3/5/6), `scripts/diagnose_tax_finance.py`, Cowork 메모리 `efe-tax-finance-bias-split`, CLAUDE.md(2층 분리 원칙 + overlay 스키마 구상).
> **설계 3-fork는 사용자가 "follow your decision"으로 위임 → 아래 §3에 확정 반영.**

---

## 0. 한 줄 요약

직전 세션이 tax anchor를 0.20→0.164(실현 8Q 평균)로 고치며 EPS bias가 −10.55%→**−6.41%**로 줄었다. 남은 −6.41% bias와 분기 스윙(2024Q4 −23%·2025Q1 −19%·2025Q3 −3% …)은 전부 **below-OP block**(= pretax − OP = net financial / FX 평가손익 / 지분법 / 일회성)에서 온다. 이 block은 분기마다 **−1,516 ~ +3,407 ₩bn**으로 크게 튀어 점추정으로 잡으면 overfitting. 목표는 bias를 0으로 미는 게 **아니라**, 이 구조적 변동성을 EPS 점추정에 넣지 않고(lookahead 위험) **오차밴드 + date-tagged overlay 레이어**로 정직하게 표현하는 것. EPS 점추정·MASE·Theil·revenue 수치는 **bit-identical 유지**가 핵심 acceptance.

## 1. 왜 (데이터 근거, 직전 세션 확정 — additive identity 검증됨)

`scripts/diagnose_tax_finance.py`가 −8.0% tax/finance 레버를 둘로 정확 분해(additive identity 0.0, per-Q 합이 attribution 레버와 일치, mean −7.95%):

- **세율 갭: 평균 −3.9% (수정 완료).** 실현 실효세율 ~16.4% < 가정 0.20 (8Q 전부). anchor 0.164로 고정 → bias −10.55%→−6.41%, EPS path bit-identical(tax에 격리).
- **below-OP block: 평균 −4.1% (미해결, 구조적).** block 분기값(₩bn): 2024Q1 −513, Q2 −416, Q3 −151, Q4 +1,499, 2025Q1 +1,859, Q2 −490, Q3 **+3,407**, Q4 −1,516. 큰 양(+) 분기가 net_financial(FX/평가이익)·non-op·지분법 일회성에서 발생 → 현 `net_interest_pct=-0.008`(−100~−260 평평한 proxy)가 못 잡음.

**2층 분리 원칙(CLAUDE.md):** earnings drivers(메모리 가격, HBM/Nvidia) → forward EPS / 매크로·타이밍·리스크(FX 손익, CPI/PPI, UST, USD/KRW) → valuation·entry·risk-band. FX 평가손익은 EPS driver가 아니라 risk-band.

## 2. 스코프 가드레일

- **EPS 점추정 불오염 = 핵심 acceptance.** 밴드·overlay는 표현만. forecast EPS·MASE·Theil·revenue **bit-identical**. no-look-ahead backtest 경로에 FX/일회성 절대 미투입.
- **Additive 스키마 변경만.** Pydantic v2 `extra="forbid"` 유지하며 신규 모델·필드 추가(기존 직렬화 불변).
- **가정 수치(밴드 폭·overlay magnitude/confidence)는 초안·제안까지 — 확정·소유 = 사용자**(CLAUDE.md). 코드는 값을 YAML에서 읽고 하드코딩 금지.
- **NOT TOUCHING:** revenue/gross-margin 체인, `engine/eps_bridge.py`·`tax_finance.py`(점추정), tax anchor(0.164 확정), `pipeline/consensus_loader.py`(배선 완료), `engine/skill_metrics.py`·`attribution.py`.

## 3. 설계 (3-fork 확정)

### 3.0 확정된 fork (사용자 위임 → 결정)

| Fork | 결정 | 근거 |
|---|---|---|
| **모듈 위치** | **신규 `engine/risk_band.py`** (≠ `valuation_bridge.py`) | `valuation_bridge.py`는 현재 `NotImplementedError` 스텁이며 **EPS→BVT DCF 탄력도**가 본 mandate. 밴드/overlay와 별개 관심사 → CLAUDE.md "no unrequested abstractions"는 *별개 모듈*을 지지(기존 스텁에 두 mandate 혼입 회피). `valuation_bridge.py`는 **건드리지 않음**. (kickoff §7가 valuation_bridge를 지목했으나, 실제 파일 mandate 확인 후 정정.) |
| **밴드 합성** | **별도 주석 밴드** (bear/bull 스프레드와 분리 렌더) | "earnings-driver 시나리오"(bear/bull)와 "below-the-line 리스크"(block 변동성)는 CLAUDE.md 2층 분리상 *다른 불확실성*. quadrature/additive 합성은 둘을 뭉개고 cycle과 이중계상 위험. 점추정 위에 라벨된 ± 밴드를 **별도 레이어**로. |
| **overlay 범위** | **스키마 + lookahead 가드 + 렌더, consumption은 seam만** | overlay가 먹여야 할 valuation/risk consumer(=DCF 브리지)가 아직 스텁 → 지금 wiring하면 미구현 DCF를 끌어옴(스코프 확대). 최소 정직 증분: Pydantic 모델 + `as_of_date < period_end` 가드 + EPS-bridge 격리 테스트 + 출력에 risk 주석 렌더. 실제 소비는 **문서화된 seam**으로 남김(다음 워크스트림). |

### 3.1 오차밴드 (point estimate 위 표현 레이어)

- **정의.** below-OP block의 EPS 기여 변동성을 점추정 EPS에 ± 밴드로. block_contrib(= block_term/NI, diagnose가 분기별 산출)의 8Q 분산이 밴드 반폭 후보.
- **robust 추정.** 1~2 이상치 분기(2025Q3 +3,407)에 안 휘둘리게 **MAD 기반 robust scale**: `half_width ≈ 1.4826 × MAD(block_contrib_8Q)`. (대안: trimmed-std — draft 비교는 §4-3.) 밴드 반폭 = robust scale × `k`(기본 1σ ≈ 68% 구간, draft).
- **단위 변환.** EPS = NI/shares → NI의 분율 밴드 ≈ EPS의 분율 밴드. 밴드는 EPS 점추정에 `eps_point × (1 ± half_width_pct)`.
- **합성(별도 렌더).** fan chart에 (i) 점추정(base/weighted), (ii) 기존 bear/bull 시나리오 범위, (iii) **별도 "below-the-line 변동성" 밴드**를 시각·수치적으로 구분. 셋을 합치지 않음.
- **값 소유.** `half_width_pct`·`k`·method(MAD vs trimmed)는 **YAML `risk_band:` draft → 사용자 확정.** 초안 시드 = `diagnose_tax_finance.py` 출력의 block_contrib에 MAD 적용(plan이 값 제시, 사용자 sign-off).
- **출력 정합.** surprise-direction(consensus 배선 완료)과 함께 보면: "level은 약간 과소(−6.4%)지만 컨센 대비 *방향*은 맞춘다 + 그 과소분은 below-the-line 변동성 밴드로 설명" 그림이 정합.

### 3.2 overlay 스키마 (date-tagged, lookahead-safe)

- **신규 Pydantic 모델 `Overlay`** (`schemas/models.py`, `extra="forbid"`). CLAUDE.md 제안 필드 + lookahead 해석에 필요한 target 참조:
  - `as_of_date: date` — overlay가 *알려진* 시점(공개 정보 기준일).
  - `target_period_label: str` — overlay가 영향 주는 대상 분기(예: "2026Q2"). period_end 해석용.
  - `driver: str` — 예: "USD/KRW FX 평가손실", "UST 10Y 급등", "기술적 매도".
  - `direction: Literal["risk_up", "neutral", "risk_down"]` — 리스크/밸류 방향(EPS 부호 아님).
  - `magnitude: float` — **valuation/risk 레이어 단위**(fair-value 분율 또는 risk-band 가중), **EPS 분율 아님**. 주석으로 단위 명시.
  - `confidence: float = Field(ge=0.0, le=1.0)`.
- **lookahead 가드(코드+테스트):** `as_of_date`가 `target_period_label`의 period_end **이전**이어야 함. 위반 시 reject. 가드 위치 = 로더/검증(`pipeline/ir_loader.py` overlay 파싱 또는 모델 validator). period_end 해석은 분기 라벨→말일 헬퍼.
- **EPS 격리(경로+타입 강제):** overlay는 `engine/risk_band.py`(및 향후 valuation)만 소비. `eps_bridge.py`·`tax_finance.py`·backtest projection 경로에 **미주입**. 테스트로 "profile에 overlays 추가해도 EPS 점추정·MASE·Theil·revenue bit-identical" 회귀 보증.
- **consumption seam:** `risk_band.py`에 overlay를 받아 risk 주석/밸류 조정 *형태로만* 반환하는 진입점 정의. 실제 DCF 결합은 `valuation_bridge.py` 구현 워크스트림으로 명시 위임(주석 + 본 plan §5에 seam 기록).

### 3.3 데이터 한계 (명시)

- DART 요약 CIS는 `FinanceIncome`/`FinanceCosts` 안에서 **이자 vs FX 미분리** → 이자/FX 쪼개기는 주석(footnote, 호스트 필요). **block 총액은 캐시로 정확**(diagnose 입증). overlay `magnitude`는 사용자 IR 가정 입력.
- 8Q 소표본 → 밴드 폭 robust 추정 필수(MAD/trimmed), 점 분산 과신 금지.

## 4. 실행 순서 (plan 승인 → fresh 세션 구현)

1. **(본 세션)** plan 저장 → 사용자 승인 대기. **구현 금지.**
2. **baseline 보관(before):** `pytest -q` green, 현 8Q EPS bias −6.41%·점추정·기존 fan chart 캡처. diagnose 출력의 block_contrib_8Q를 `tests/fixtures/`에 커밋(밴드 calibration 입력).
3. **failing-test 우선** (승인 후):
   - `test_overlay.py`: `as_of_date ≥ target period_end` → reject. EPS 점추정 격리(overlays 추가 시 EPS bit-identical).
   - `test_risk_band.py`: 밴드 반폭 = robust scale(MAD); 밴드가 실측 8Q block_contrib 스윙을 커버(예: ≥6/8 분기가 ±k 밴드 내, draft 기준).
   - MAD vs trimmed 초안 비교 → 사용자 제시.
4. **스키마·엔진·출력 구현:** `Overlay` 모델 + 가드 → `risk_band.py`(밴드 계산 + overlay seam) → `output/*`(밴드 별도 렌더 + overlay 주석).
5. **회귀 가드:** revenue/GP/OP/**EPS 점추정 bit-identical**, MASE/Theil/revenue 불변, `pytest -q` green, `--dry-run` 새 출력 시각 확인.

## 5. Acceptance

- below-OP 변동성이 EPS 점추정이 **아니라** 오차밴드/overlay로 표현 — EPS 숫자에 lookahead 미반영(테스트 보증).
- overlay date-tagged, `as_of_date < target period_end` 강제(테스트). overlay는 `risk_band`(향후 valuation)만 소비, `eps_bridge`/`tax_finance` 격리(경로 + 회귀 테스트).
- 밴드는 별도 레이어로 bear/bull과 구분 렌더. 폭 method·값은 YAML draft → 사용자 확정.
- **forecast EPS·MASE·Theil·revenue 수치 bit-identical.** `pytest -q` green, `--dry-run` 새 출력 포함.
- **seam 기록:** overlay→DCF 실제 결합은 `valuation_bridge.py` 구현 워크스트림으로 위임(본 plan + 코드 주석에 명시).

## 6. 위험 / 가정

- below-OP(특히 FX)는 구조적으로 예측 난이 — 밴드로 "정직한 구간" 목표, **bias 0 추구 금지**(overfitting).
- 8Q 소표본 → robust 추정(MAD/trimmed). 2025Q3 +3,407 이상치에 밴드 폭이 안 끌려가게.
- 스키마 변경 = `extra="forbid"` 신규 모델/필드만, 기존 직렬화 불변.
- valuation consumer 미구현 → overlay consumption은 seam만. 지금 wiring 시 스코프 확대 → 위임 결정(§3.0).

## 7. 변경 파일 (구현 시)

**신규:** `engine/risk_band.py`(밴드 계산 + overlay seam), `tests/test_risk_band.py`, `tests/test_overlay.py`, `tests/fixtures/`(8Q block_contrib).
**수정:** `schemas/models.py`(`Overlay` 모델 + `EpsRiskBand` 결과 모델 — QuarterlyForecast는 **불변**), `pipeline/ir_loader.py`(overlays 파싱 + lookahead 가드), `output/*`(`html_builder.py`·`md_builder.py`·`plotly_charts.py` 밴드 별도 렌더 + overlay 주석), `profiles/sk_hynix.yaml`(`risk_band:` + `overlays:` **draft — 사용자 확정**).
**NOT TOUCHING:** revenue/gross-margin 체인, `engine/eps_bridge.py`·`tax_finance.py`·`segment_revenue.py`·`margin_model.py`, `engine/valuation_bridge.py`(스텁 mandate 유지), consensus 배선, `skill_metrics.py`·`attribution.py`.

> **설계 메모.** QuarterlyForecast에 밴드 필드를 추가하지 **않고**, `risk_band.py`가 별도 `EpsRiskBand` 모델을 산출 → output이 소비. 이로써 EPS 점추정 모델이 물리적으로 불변 → "EPS bit-identical"이 trivially 성립.

## 8. 런타임 메모

- **오프라인 재현:** DART 캐시(`reports/.cache/`, gitignore — 테스트는 `tests/fixtures/`), `DART_API_KEY=dummy`, `pytest -q`. 샌드박스 Yahoo/DART 라이브 403 가능 → `--dry-run`.
- **Cowork mount staleness:** 기존 파일 file-tool edit 후 bash가 truncated 캐시를 읽을 수 있음 → bash로 검증(`grep`/parse), stale면 새 파일 Write + `cp` 재동기화(메모리 `cowork-mount-stale-edits`). bash `rm` 막히면 `allow_cowork_file_delete`.
- **직전 세션 값:** tax anchor base 0.164 / bear 0.184 / bull 0.154 (DRAFT). `tests/test_tax_finance.py`가 anchor를 fixture에 고정(0.20에서 실패).
- **block 8Q (₩bn, 시드용):** 2024Q1 −513, Q2 −416, Q3 −151, Q4 +1,499, 2025Q1 +1,859, Q2 −490, Q3 +3,407, Q4 −1,516.
