# HANDOFF — below-OP block → 오차밴드 / overlay (verdict #2 구조적 절반)

> 세션 2026-06-20. `PLAN_tax_finance_overlay.md`의 구현 결과. tax/finance anchor 세션(−3.9% 가능분, 완료) 후속 — 남은 below-OP block(−4.1%, 구조적)을 EPS 점추정이 아니라 **별도 오차밴드 + date-tagged overlay**로 표현.
> **핵심 acceptance: forecast EPS·MASE·Theil·revenue bit-identical.** 밴드/overlay는 표현 레이어, 점추정 불오염.
> 재현(오프라인): `DART_API_KEY=<any> python -m pytest -q` (68+11=79 passed) · `python cli.py --company sk_hynix --dry-run --skip-pdf` (밴드/overlay 렌더 확인).

## 추가/변경 파일

**신규**
- `engine/risk_band.py` — `robust_half_width`(1.4826×MAD, `trimmed` 대안) + `build_eps_risk_band`(점추정에 ±밴드, overlay 첨부) + `overlay_valuation_seam`/`SEAM_NOTE`(DCF 소비 위임 명시).
- `tests/test_risk_band.py` — MAD 공식·trimmed 비교·≥6/8 커버·점추정 bit-identical·음수 EPS 대칭·overlay annotation-only.
- `tests/test_overlay.py` — lookahead 가드(as_of ≥ period_end → reject)·calendar 분기말·**EPS 격리 회귀**(profile에 overlays 추가해도 forward base EPS/revenue bit-identical).
- `tests/fixtures/sk_hynix_block_contrib.json` — `diagnose_tax_finance.py` 8Q block_contrib 시드(밴드 캘리브레이션 입력, 오프라인 재현용).

**수정 (additive only)**
- `schemas/models.py` (+) — `Overlay`(model_validator lookahead 가드), `EpsRiskBandQuarter`, `EpsRiskBand`, `quarter_period_end` 헬퍼. **`QuarterlyForecast` 불변** → EPS 모델 물리적 불변 → "EPS bit-identical" trivially 성립.
- `pipeline/ir_loader.py` (+) — `overlays:` 파싱(검증 시 lookahead 발화) + `risk_band:` passthrough. 두 키 모두 EPS 경로 밖.
- `output/plotly_charts.py` (+) — `build_eps_risk_band_chart`(별도 figure, bear/bull fan과 분리).
- `output/html_builder.py`·`output/md_builder.py` (+) — 밴드 별도 섹션(점추정/하한/상한 표) + overlay annotation 표 + seam 주석. render 함수에 `risk_band` optional 인자(기존 호출 하위호환).
- `cli.py` (+) — `risk_band_cfg` 있으면 `build_eps_risk_band` 산출해 render에 전달. 없으면 리포트 불변.
- `profiles/sk_hynix.yaml` (+) — `risk_band:` + `overlays:` **draft**(아래 §사용자 소유).

## 확정 설계 (PLAN §3.0 3-fork, 재논의 금지)

| Fork | 결정 |
|---|---|
| 모듈 위치 | 신규 `engine/risk_band.py` (≠ `valuation_bridge.py`). valuation_bridge는 EPS→BVT DCF 탄력도 mandate라 별개 관심사 → **건드리지 않음**. (kickoff §7이 valuation_bridge 지목했으나 plan이 정정.) |
| 밴드 합성 | 별도 주석 밴드(bear/bull 스프레드와 분리 렌더). quadrature/additive 합성 금지 — 2층 분리상 다른 불확실성. |
| overlay 범위 | 스키마 + lookahead 가드 + 렌더까지. 실제 valuation/DCF 소비는 **문서화된 seam**(`overlay_valuation_seam`)으로 위임. |

## 캘리브레이션 (block_contrib 8Q, % of actual NI)

block 8Q(₩bn): 2024Q1 −513 · Q2 −416 · Q3 −151 · Q4 +1,499 · 2025Q1 +1,859 · Q2 −490 · Q3 **+3,407** · Q4 −1,516.

| 방법 | half-width(k=1) | 커버(±밴드 내) | k=1.5 |
|---|---:|---|---:|
| **mad** (1.4826×MAD, drafted) | 15.19% | 4/8 | **22.79% → 7/8** |
| trimmed-std (min·max 제거) | 11.28% | — | 16.92% |

- MAD를 1차로 채택: 2025Q3 +3,407 이상치에 폭이 안 끌려감. trimmed는 양 극단(2025Q1·Q3)을 떨궈 더 타이트.
- draft `k=1.5`(±22.8%, ~87% 경험 커버). **method/k/width 전부 사용자 확정 대상.**

## 검증 (acceptance, 전부 충족)

- `pytest -q` → **79 passed** (기존 68 + 신규 11).
- 오프라인 8Q backtest(DART 캐시): **EPS bias −6.4116%**(직전 세션 −6.41%와 bit-identical), revenue MAPE 9.51%, MASE EPS 0.370, Theil U2 EPS 0.404, MASE revenue 0.654 — **additive 레이어가 EPS 경로 불변** 입증.
- `--dry-run` → MD·HTML에 "Below-OP 리스크 밴드(EPS)" 섹션 + EPS band chart(`id="epsband"`) + overlay 표 렌더. 점추정 = forecast weighted EPS, 상/하한 = ±22.8%(예: 14,689 × 1.2279 = 18,036).
- lookahead 가드: `as_of_date ≥ target period_end` → ValueError(테스트 보증). overlays 추가해도 forward EPS/revenue bit-identical(격리 회귀 테스트).

## 사용자 소유 (draft → 확정 대기, 코드 하드코딩 없음)

1. **밴드:** `risk_band.method`(mad vs trimmed) · `k`(1.5) · `half_width_pct`(0.2279). 위 표가 선택지 제시.
2. **overlays(3건, draft):** magnitude/confidence가 플레이스홀더 —
   - 2026Q2 USD/KRW FX 평가손실, risk_down, mag 0.03, conf 0.40
   - 2026Q3 UST 10Y/30Y 금리 급등, risk_down, mag 0.05, conf 0.30
   - 2026Q4 Nvidia HBM 파트너 의존도, risk_down, mag 0.04, conf 0.35
   - magnitude = valuation/risk 레이어 단위(공정가치 분율 또는 risk-band 가중), **EPS 분율 아님**.

## Seam (다음 워크스트림으로 위임)

overlay→DCF/밸류에이션 실제 결합은 `engine/valuation_bridge.py`(현 stub) 구현 워크스트림. `risk_band.overlay_valuation_seam`이 overlay를 annotation payload로만 통과 — 지금 wiring 시 미구현 DCF 끌어옴(스코프 확대) → 위임. `EpsRiskBand.seam_note`에 코드상 명시.

## NOTICED BUT NOT TOUCHING

- `engine/eps_bridge.py`·`tax_finance.py`(tax anchor 0.164 확정, 점추정 격리)·`segment_revenue.py`·`margin_model.py` — EPS 경로, 불변.
- `engine/valuation_bridge.py` — stub mandate 유지(seam만).
- `engine/skill_metrics.py`·`attribution.py`·consensus 배선 — 본 세션 스코프 아님.

## 다음 워크스트림

1. **사용자 draft 값 확정** (밴드 method/k, overlay mag/conf) — 게이트.
2. **`PLAN_valuation_bridge.md`** — overlay 소비 seam의 consumer. EPS→BVT DCF 탄력도 + overlay→entry-timing/risk. 별도 plan + focused 세션(미구현 DCF 끌어오는 스코프라 plan mode부터).

## 런타임 메모 (이번 세션)

- **Cowork mount staleness 재확인(메모리 `cowork-mount-stale-edits`):** 기존 파일을 file-tool로 edit하면 bash 마운트가 truncated/corrupt 캐시를 서빙(stale .pyc 우회 import 포함). pytest는 통과하는데 직후 standalone import가 stale을 읽는 flaky도 관측. **해결:** 전체 내용을 신규 경로로 Write → `cp`로 canonical 덮어쓰기 → `__pycache__` 삭제. `schemas/models.py`·`pipeline/ir_loader.py`·`cli.py`·`output/{plotly_charts,html_builder,md_builder}.py`에 적용, 최종 79 passed로 검증. 커밋 파일은 정상.
- 워킹트리에 본 세션과 무관한 prior-session 변경/untracked(`engine/attribution.py`, `skill_metrics.py`, README/CLAUDE 등) 다수 — 커밋 시 본 세션 파일만 선별(`git add -p`).
