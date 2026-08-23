# HANDOFF — valuation_bridge 구현 (overlay seam consumer) · Codex 평가 요청

> 세션 2026-06-20. `PLAN_valuation_bridge.md` 구현 결과. 직전 below-OP overlay 세션이 위임한 seam(`risk_band.overlay_valuation_seam`, `EpsRiskBand.seam_note`)의 **consumer**를 채움.
> **이 핸드오프는 Codex 평가용입니다.** 아래 §"Codex 평가 포인트"를 호스트에서 검증해 주세요(pytest + 코드 리뷰). 가정 수치(elasticity·overlay_weight)는 draft — 사용자 소유.
> 재현(오프라인): `DART_API_KEY=<any> python -m pytest -q` → **86 passed** · `python cli.py --company sk_hynix --dry-run --skip-pdf`.

## 0. 한 줄 요약

`engine/valuation_bridge.sensitivity_to_dcf` stub(`NotImplementedError`)을 채움: (레이어 1) forward FY1 EPS gap vs 컨센 × 탄력도 → fair-value delta + below-OP 밴드 투영, (레이어 2) date-tagged overlay → 별도 매크로 entry/risk 점수. 둘은 **수치적으로 분리**(CLAUDE.md 2층). bridge는 `ScenarioTree`에 read-only → forecast EPS·MASE·Theil·revenue **bit-identical**(검증됨).

## 1. 추가/변경 파일

**신규**
- `tests/test_valuation_bridge.py` — 7 tests: delta 산식, None/비신뢰 컨센 보류, 밴드 투영, overlay 점수 부호·가중, **레이어 분리 회귀**(overlay가 fair_value_delta 점값 미변경), tree 불변.

**수정 (additive only)**
- `engine/valuation_bridge.py` — stub 대체. `sensitivity_to_dcf(model_tree, consensus_eps_fy, fair_value_elasticity=1.2, *, eps_half_width_pct, overlays, overlay_weight, consensus_reliable)` → `ValuationBridgeResult`. `_overlay_risk_score` 헬퍼. **BVT import 안 함**(loose coupling 유지).
- `schemas/models.py` (+) — `ValuationBridgeResult`(`extra="forbid"`). `ScenarioTree`/`QuarterlyForecast` 불변.
- `pipeline/ir_loader.py` (+) — `valuation:` passthrough(`raw.get("valuation")`).
- `cli.py` (+) — risk_band 블록 뒤에 `sensitivity_to_dcf` 호출, render에 `valuation=` 전달. 컨센 reliability = `len(consensus.notes) == 0`, 밴드 half-width = `risk_band.half_width_pct`, FY1 컨센 = `consensus.eps_estimate_annual.get(fy1)`.
- `output/html_builder.py`·`output/md_builder.py` (+) — "밸류에이션 브리지" 섹션(EPS gap·fair-value delta·밴드 + overlay 점수 별도). render 함수 `valuation` optional 인자.
- `profiles/sk_hynix.yaml` (+) — `valuation: {fair_value_elasticity: 1.2, overlay_weight: 1.0}` **draft**.

## 2. 설계 결정

- **2층 분리(핵심).** 레이어 1 `fair_value_delta_pct`(EPS 기반) vs 레이어 2 `overlay_risk_score`(매크로 기반)를 **별도 필드**로. overlay를 delta 점값에 합치지 않음(테스트 `test_overlays_do_not_perturb_fair_value_delta`가 보증).
- **컨센 신뢰도 가드(§①-B).** yfinance `.KS` 컨센이 비신뢰면(notes 존재) cli가 `consensus_reliable=False` → delta `None` + note "보류". 컨센 부재(None/0)도 동일. → 깨진 컨센이 fair-value delta로 흐르지 않음.
- **밴드 투영.** `eps_half_width_pct` 주면 `fair_value_delta_low/high = elasticity × (model_eps×(1∓hw) − cons)/cons`. EPS 밴드의 valuation 투영.
- **overlay 점수.** `overlay_weight × Σ sign(direction)×magnitude×confidence`, sign: risk_up +1 / neutral 0 / risk_down −1.
- **loose coupling.** elasticity = YAML 상수(BVT sensitivity로 시드). BVT repo import 없음. 직접 wiring은 P2.

## 3. 검증 (self)

- `pytest -q` → **86 passed**(직전 79 + valuation 7).
- 오프라인 8Q backtest: **EPS bias −6.4116%**(불변), rev MAPE 9.51%, MASE EPS 0.370, Theil EPS 0.404 — forecast 경로 **bit-identical**(bridge read-only).
- `--dry-run`: "밸류에이션 브리지 (FY25)" 섹션 렌더. dry-run은 2Q fixture seed fallback이라 FY=2025·컨센 부재 → delta "보류" note + overlay 점수 −0.041(n=3) 정상 표기. (호스트 실데이터에선 FY26 컨센 존재 시 delta 채워짐, reliability 가드 통과 가정.)

## 4. Codex 평가 포인트 (호스트 검증 요청)

1. **레이어 분리 무결성:** overlay가 `fair_value_delta_pct`·`eps_delta_pct`에 절대 영향 없음(레이어 2만). `test_overlays_do_not_perturb_fair_value_delta` 외 추가 엣지(overlay 0개/다수) 확인.
2. **컨센 reliability 가드 적정성:** cli의 `len(consensus.notes)==0` 판정이 §①-B 깨진 컨센을 실제로 걸러내는지(호스트 라이브 yfinance로). notes가 비어도 비현실 컨센이 통과할 여지 → 임계 가드(예: model 대비 배수) 추가 필요 여부 판단 요청.
3. **forecast bit-identical:** 호스트 `cli.py --company sk_hynix`(라이브) 전후 EPS/MASE/Theil/revenue 불변 확인(샌드박스는 −6.41% 재현).
4. **BVT elasticity 시드:** 호스트에서 BVT(`F:\dev\Portfolio\business-valuation-tool`) sensitivity 1회 실행 → 실제 elasticity로 `valuation.fair_value_elasticity` 확정 권고(현 1.2 placeholder).
5. **FY 매칭:** `consensus.eps_estimate_annual.get(fy1)` 키 타입(int fiscal_year) 정합성 — 호스트 컨센 캐시와 맞는지.

## 5. 사용자 소유 (draft → 확정)

- `valuation.fair_value_elasticity` (1.2 placeholder → BVT sensitivity).
- `valuation.overlay_weight` (1.0 draft).
- (이전 세션 미결) 밴드 method/k, overlay magnitude/confidence.

## 6. NOT TOUCHING

EPS 경로 전체(`eps_bridge`·`tax_finance`·`segment_revenue`·`margin_model`), `risk_band.py` 점추정·`build_eps_risk_band`, consensus 배선(`consensus_diff`·`consensus_loader`), `skill_metrics`·`attribution`, BVT repo.

## 7. 런타임 메모

- 오프라인: `DART_API_KEY=<any> pytest -q`. elasticity YAML 상수라 네트워크 불요.
- **Cowork mount staleness(메모리 `cowork-mount-stale-edits`) — 이번 세션 광범위 발생.** 기존 파일 file-tool edit 후 bash가 truncated 읽음(parse-OK인데 `__main__` 블록 누락으로 cli 무동작, YAML valuation 키 truncate 등). **해결:** 전체 내용 신규 경로 Write + `cp` 재동기화(+`__pycache__` 삭제), 작은 append는 신규 블록 파일 + `cat ... >>` + `cp`. 최종 86 passed·dry-run 렌더로 검증. **커밋 파일은 정상**(file-tool가 truth). 커밋 전 본 세션 파일만 선별 권장(`git add -p`); 워킹트리에 prior-session 변경 다수.

---

## 후속 조치 — Codex 평가 반영 (2026-06-20, 동일 세션)

Codex 평가의 #1·#2를 구현. #3(BVT elasticity)는 호스트/방법론 의존이라 gated 유지.

**#1 컨센 신뢰도 판정 분리 (해결).** `len(consensus.notes)==0`은 품질 오류와 단순 부재를 혼동 → 분기 컨센 부재 note만 있어도 정상 연간 bridge가 보류되던 문제.
- `ConsensusRecord`에 `quality_notes` 필드 추가(additive). `consensus_loader`가 **품질 실패(implied net margin >60%)만** quality_notes에 적재(+display용 notes에도 유지), 부재 경고는 notes에만.
- `cli`의 bridge 가드를 `len(consensus.quality_notes)==0`으로 변경(cli.py). → 부재만 있는 현실적 연간 컨센은 이제 bridge 산출, 깨진 컨센만 보류.
- 테스트: `tests/test_consensus_reliability.py`(부재→quality_notes 빈; margin>60%→적재; 현실적 연간+분기부재→reliable). 기존 `test_consensus_loader.py`(notes 검사) 불변 green.

**#2 valuation config 검증 (해결).** raw dict passthrough → 음수 탄력도·오타 키가 런타임 산술오류/사일런트 부호반전.
- `ValuationConfig`(Pydantic, `extra="forbid"`, `fair_value_elasticity>=0`, `overlay_weight>=0`) 추가. `ir_loader`가 `valuation`을 model_validate(잘못된 YAML은 load 시점 ValidationError). `cli`는 attribute 접근.
- 테스트: `tests/test_valuation_config.py`(음수·오타키 reject, 기본값, loader가 ValuationConfig 반환).

**#3 BVT elasticity (gated, 미해결 — 의도).** Codex 확인: BVT `000660.yaml`은 primary_method=sotp, DCF EV 음수(-254,819,800), sensitivity 축이 WACC×terminal-growth라 EPS 민감도 아님 → elasticity 시드 불가. **`fair_value_elasticity: 1.2`는 draft 유지.** 확정 선행조건(호스트, 사용자/방법론): (a) BVT DCF baseline을 유효한 양(+) 공정가치로 교정, (b) EPS 대응 EBITDA/FCFF 입력을 ±x% 변화시켜 (%FV)/(%EPS) 측정 → 그 값으로 YAML 확정.

**재검증:** `pytest -q` → **93 passed**(86 + 신규 7). EPS bias −6.4116%·MASE 0.370·rev MAPE 9.51% 불변(bit-identical). `--dry-run` 정상. stray 파일 없음.

**재평가 요청 (Codex):** #1 가드가 라이브 yfinance에서 깨진 컨센(margin>60%)은 보류하고 현실적 연간만 통과시키는지, #2 ValidationError가 의도대로 잘못된 YAML을 load 시점에 막는지. #3는 BVT 교정 워크스트림으로 별도.

**NOT TOUCHING (후속분):** EPS 경로, risk_band 점추정, `consensus_diff`(gap 계산 로직), BVT repo. consensus_loader 변경은 quality_notes 적재 1곳 + 반환 1필드로 한정(기존 notes/직렬화 불변).
