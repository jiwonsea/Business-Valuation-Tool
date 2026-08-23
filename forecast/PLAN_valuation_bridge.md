# PLAN — valuation_bridge: EPS→DCF 탄력도 + overlay/밴드 소비 (seam consumer)

> **zero-context 핸드오프 plan.** 작성 2026-06-20 (below-OP overlay 세션 후속). 구현은 **사용자 승인 + draft 값 확정 후 별도 focused 세션**에서.
> 코드/주석/식별자 = 영어, 사용자용 출력 = 한국어. 선행 읽기: `PLAN_tax_finance_overlay.md`, `HANDOFF_block_overlay.md`, `engine/valuation_bridge.py`(현 stub), `engine/risk_band.py`(`overlay_valuation_seam`·`EpsRiskBand`), `schemas/models.py`(`Overlay`·`EpsRiskBand`·`ScenarioTree`), `engine/consensus_diff.py`·`pipeline/consensus_loader.py`(컨센 신뢰도), `HANDOFF_backtest_diag.md` §①-B(yfinance `.KS` 컨센 비신뢰), `docs/methodology.md §8`, Cowork 메모리 `cowork-mount-stale-edits`.

---

## 0. 한 줄 요약

직전 세션이 below-OP 변동성을 오차밴드 + date-tagged overlay로 표현하고, overlay→밸류에이션 소비를 **문서화된 seam**(`risk_band.overlay_valuation_seam`, `EpsRiskBand.seam_note`)으로 위임했다. 본 세션은 그 seam의 **consumer**를 구현: `engine/valuation_bridge.sensitivity_to_dcf` stub을 채워 (a) forward EPS gap → fair-value delta(탄력도), (b) **별도로** overlay·밴드를 entry-timing/risk 조정으로 소비(2층 분리). EPS·forecast 수치는 **bit-identical 유지**(bridge는 tree에 read-only).

## 1. 왜 (현 상태)

- `valuation_bridge.py`는 `NotImplementedError` stub. 시그니처: `sensitivity_to_dcf(model_tree, consensus_eps_fy, fair_value_elasticity=1.2) -> {eps_delta_pct, fair_value_delta_pct, note}`. loose coupling — BVT repo import 안 함, elasticity는 YAML 상수(BVT sensitivity 1회 실행으로 시드, P2에 직접 wiring).
- overlay 레이어(이전 세션)는 스키마·가드·렌더까지 존재하나 **소비처가 없음**. CLAUDE.md 2층 분리: earnings driver → EPS(완료), 매크로/타이밍/리스크(overlay) → **valuation/entry/risk**(= 본 모듈).
- **컨센 신뢰도 경고(HANDOFF_backtest_diag §①-B):** yfinance `.KS` 컨센 EPS가 실측의 ~3배로 깨질 수 있음. `consensus_eps_fy`를 그대로 쓰면 fair_value_delta가 쓰레기. → bridge는 신뢰도 가드/주석 필수.

## 2. 스코프 가드레일

- **EPS·forecast 불오염.** bridge는 `ScenarioTree`·`EpsRiskBand`·`Overlay`를 **read-only** 소비. forecast EPS·MASE·Theil·revenue **bit-identical**.
- **2층 분리 강제.** EPS-gap→fair-value delta(레이어 1)와 overlay→entry/risk 조정(레이어 2)을 **수치적으로 분리**해 산출. overlay를 fair_value_delta 점값에 합치지 말 것(밴드처럼 별도 필드/주석).
- **Additive 스키마만.** `extra="forbid"` 신규 결과 모델. 기존 직렬화 불변.
- **가정 수치(elasticity·overlay 가중 합성식)는 draft·제안까지 — 확정 = 사용자.** 코드는 YAML에서 읽고 하드코딩 금지.
- **NOT TOUCHING:** EPS 경로 전체(`eps_bridge`·`tax_finance`·`segment_revenue`·`margin_model`), `risk_band.py`의 점추정 산출, consensus 배선, `skill_metrics`·`attribution`. BVT repo는 import 안 함(loose coupling 유지).

## 3. 설계

### 3.1 레이어 1 — EPS gap → fair-value delta (stub 본체)
- `eps_delta_pct = (model_fy1_eps − consensus_eps_fy) / consensus_eps_fy`. `consensus_eps_fy` None/0/비신뢰 → `None` + note.
- `fair_value_delta_pct = fair_value_elasticity × eps_delta_pct`. elasticity = YAML `valuation.fair_value_elasticity`(draft 1.2, 사용자 BVT sensitivity로 확정).
- **밴드 전파:** `EpsRiskBand`가 있으면 fair-value delta에도 밴드 → `fair_value_delta_low/high = elasticity × eps_delta(band lower/upper vs consensus)`. EPS 밴드의 valuation 투영.

### 3.2 레이어 2 — overlay → entry-timing / risk 조정 (seam consumer)
- overlay 집계: 각 overlay의 `direction`(risk_up=+1 / neutral=0 / risk_down=−1) × `magnitude` × `confidence` 가중합 → `overlay_risk_score`(valuation/risk 단위, **EPS 분율 아님**).
- **레이어 1과 분리 출력.** fair_value_delta_pct(EPS 기반)와 overlay_risk_score(매크로 기반)를 **별도 필드**로. 합성식(가중·정규화)은 **draft → 사용자 확정**(quadrature 금지, plan이 단순 가중합 제안).
- date-tag 유지: 이미 `Overlay` validator가 lookahead 가드. bridge는 추가로 "보고 시점 이후 overlay 제외" 등 as-of 필터가 필요하면 명시(기본: profile의 overlays 전량, 가드 통과분).

### 3.3 컨센 신뢰도 가드 (필수)
- `consensus_diff`/`consensus_loader`의 기존 reliability 신호 재사용. 컨센 EPS가 비현실(예: 실측 대비 임계 배수 초과)이면 `fair_value_delta_pct=None` + note "컨센서스 신뢰불가 — fair-value delta 보류". §①-B 교훈 인코딩.

### 3.4 스키마
- 신규 `ValuationBridgeResult`(`extra="forbid"`): `eps_delta_pct`, `fair_value_delta_pct`(+`_low`/`_high`), `overlay_risk_score`, `overlays`(annotation), `elasticity`, `note`. `ScenarioTree`/`QuarterlyForecast` 불변.

### 3.5 출력·배선
- `output/{html_builder,md_builder}.py`: "밸류에이션 브리지" 섹션(EPS gap·fair-value delta·밴드 투영 + overlay risk 별도). render 함수 optional 인자(하위호환).
- `cli.py`: `valuation` cfg 있으면 `sensitivity_to_dcf` 호출해 render에 전달. 없으면 불변.

## 4. 실행 순서 (failing-test 우선)
1. baseline: `pytest -q` green, forecast EPS/MASE/Theil/revenue 스냅샷.
2. failing-test: `test_valuation_bridge.py` — eps_delta/fair_value_delta 산식, None-컨센 가드, 비신뢰 컨센 보류, **overlay가 fair_value_delta 점값에 미반영**(레이어 분리 회귀), forecast bit-identical.
3. 스키마(`ValuationBridgeResult`) → `valuation_bridge.py` 본체 → output → YAML draft(`valuation.fair_value_elasticity`).
4. 회귀: EPS/MASE/Theil/revenue bit-identical, `pytest -q` green, `--dry-run` 새 섹션.

## 5. Acceptance
- `sensitivity_to_dcf` 구현(NotImplementedError 제거), EPS-gap→fair-value delta 산출 + 밴드 투영.
- overlay가 **별도** entry/risk 조정으로 소비(레이어 1 점값 불오염, 테스트 보증). seam 닫힘.
- 컨센 비신뢰 시 fair-value delta 보류 + note.
- forecast EPS·MASE·Theil·revenue **bit-identical**, `pytest -q` green, `--dry-run` 포함.
- elasticity·overlay 합성식 = YAML draft → 사용자 확정.

## 6. 위험 / 가정
- **BVT 인터페이스 미확인:** 구현 세션 첫 단계 = 호스트에서 BVT(`F:\dev\Portfolio\business-valuation-tool`) sensitivity 1회 실행해 실제 elasticity 시드(plan은 loose-coupling 상수 유지, 직접 wiring은 P2). 샌드박스는 BVT 미마운트 → elasticity는 YAML 상수로만.
- elasticity 1.2는 placeholder(터미널밸류 증폭 가정). 비선형/시나리오별 elasticity는 over-engineering — MVP는 단일 상수.
- 컨센 데이터 품질(§①-B) — fair-value delta의 최대 오염원. 가드 필수.

## 7. 변경 파일 (구현 시)
**신규:** `engine/valuation_bridge.py`(본체 — 현 stub 대체), `tests/test_valuation_bridge.py`.
**수정:** `schemas/models.py`(`ValuationBridgeResult`), `pipeline/ir_loader.py`(`valuation:` 파싱), `output/{html_builder,md_builder}.py`, `cli.py`(배선), `profiles/sk_hynix.yaml`(`valuation.fair_value_elasticity` draft).
**NOT TOUCHING:** §2 목록(EPS 경로·risk_band 점추정·consensus 배선·BVT import).

## 8. 런타임 메모
- 오프라인: `DART_API_KEY=<any> pytest -q`, `--dry-run`. elasticity는 YAML 상수라 네트워크 불요.
- **Cowork mount staleness(메모리 `cowork-mount-stale-edits`):** 기존 파일 file-tool edit 후 bash가 truncated/corrupt 읽음 → 전체 내용 신규 경로 Write + `cp` 재동기화 + `__pycache__` 삭제. bash `rm` 막히면 `allow_cowork_file_delete`.
