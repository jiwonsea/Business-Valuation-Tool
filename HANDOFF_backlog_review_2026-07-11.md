# HANDOFF — 백로그 7건 설계 평가 요청 (CODEX)

세션: 2026-07-11 (Cowork). NVDA 심층 재밸류에이션(2026-07-10) 및 1·2차 보고서 평가에서 누적된 백로그를
구현 착수 전 설계 단계에서 평가 요청. **아직 코드 변경 없음** — 각 항목의 문제정의·설계 스케치·수용기준을
제시하니 (i) 우선순위 타당성 (ii) 설계 결함 (iii) 구현 범위(엔진 계약 영향) 관점에서 판정 바람.
배경: `HANDOFF_nvda_deep_dive_2026-07-10.md`(개정 1) · `HANDOFF_nvda_report_review_2026-07-10.md`(개정 1·2).

## P1 — LLM 피어 생성 신뢰성 (가짜 피어 재발 방지)

**문제.** NVDA 프로파일에서 실체 없는 피어 4건 확인·제거(커밋 3006899, a6b1356): '롯데칩스'(비실존),
'SK텔레콤/현대모비스'(무관 기업 융합), 'Intel Arc Graphics'(제품 라인), 'Xilinx'(소멸 법인, 4년 전 배수).
원인은 `ai/` 피어 추천 LLM 생성 — **다른 종목 프로파일 전체에 동종 오염 개연성 높음.**

**설계 스케치.**
(a) `ai/prompts.py` 피어 프롬프트에 하드 제약 추가: 실존 상장사(티커 필수)·현재 독립 상장 유지·
단일 법인만(융합 금지)·배수 기준연도 명시 필수. (b) `ai/validators.py`에 피어 검증 단계: 티커 존재성
(ticker cache 대조), 인수합병 블랙리스트, 융합 패턴('/' 포함 name) 거부. (c) 일회성 정리: 기존
`profiles/*.yaml` 전수 스캔 스크립트(scripts/)로 의심 피어 리포트 생성 → 수동 확정 후 제거.
(d) 피어 항목에 `as_of` 필드(Optional, 하위호환) 추가해 빈티지 추적.

**수용 기준.** 신규 `--auto` 생성 프로파일에서 티커 없는 피어 0건. 전수 스캔 리포트 산출.
**평가 요청.** validators의 티커 존재성 확인이 LLM 쿼터(회사당 ≤4콜)와 오프라인 실행 제약을 깨지 않는
구현 경로(로컬 ticker cache만 사용) 검토.

## P2 — CrossValidationItem `source` 필드 정식화

**문제.** trading 배수 순환성 제거(커밋 981af93)가 ±5% 시장가 밀착 휴리스틱에 의존. 경계 사례
(괴리 5~7% 시점의 재실행)에서 [T]/[P] 판정이 뒤집혀 quality 점수가 비연속적으로 변동 가능.

**설계 스케치.** `schemas/models.py` CrossValidationItem에 `source: Optional[str] = None`
("trading"|"peer") 추가 → `valuation_runner._cross_validate_*`에서 배수 출처를 아는 지점
(pipeline이 시장가 역산으로 채웠는지)에 명시 태깅 → `quality._trading_anchored_methods`는
source 우선, 미태깅 시 현 휴리스틱 폴백. `output/console_report.py` [T] 태그도 source 우선으로 통일.

**수용 기준.** 기존 프로파일(미태깅) 점수 완전 불변(폴백 가드), 신규 태깅 프로파일에서 경계 비연속성 제거.
**평가 요청.** 배수 출처를 프로파일 YAML에 어떻게 영속화할지 — `pe_multiple_source` 별도 필드 vs
peers처럼 구조화 객체 전환. 하위호환(Optional+default) 계약 준수 여부.

## P3 — 시나리오 mixture MC 분포

**문제.** 통합 MC는 Base-input MC(기본 배수 중심)로, 확률가중치의 불확실성 분포가 아님(CODEX 1차 (e)).
현재는 문서 표기로 구분하나, 사용자 오독 리스크 상존.

**설계 스케치.** `engine/monte_carlo.py`에 mixture 모드: 각 draw마다 시나리오를 확률로 샘플링 →
해당 시나리오 override(멀티플·옵셔널리티 매출) 기준으로 기존 경로 실행. 기존 Base-input MC는 유지
(이름만 명시), `MonteCarloResult`에 `mode` 필드. 콘솔·Excel 출력에 두 분포 병기.
NVDA 검증치: mixture mean ≈ 시나리오별 MC mean의 확률가중(TTM ~164 / FY27E ~196)과 일치해야 함.

**수용 기준.** mixture mean이 시나리오 MC 가중 ±1% 내 재현. 기존 MC 출력 회귀 0.
**평가 요청.** TV resampling(rules/monte-carlo.md)과 시나리오 샘플링의 상호작용 — draw별 시나리오 전환 시
DCF-TV 비율 재계산 비용(10,000회 성능) 허용 범위인지.

## P4 — `normalized_net_income` 이원 필드

**문제.** NVDA에서 GAAP NI(지분평가이익 27% 포함) 대신 비GAAP를 consolidated `net_income`에 수기 기입
(주석 문서화로 임시 대응). 자동 재생성·백테스트 누적 시 GAAP/조정치가 섞임(CODEX 1차 (b) 판정).

**설계 스케치.** consolidated 연도 dict에 `normalized_net_income: Optional[int]` 추가.
P/E 교차검증·상대가치 진단(EPS/ROE/justified P/B)·RIM ROE forecast는 normalized 우선, 없으면 GAAP.
`net_income`은 GAAP 계약으로 환원. pipeline 수집기는 GAAP만 채움(normalized는 수동/AI 조정 전용).

**수용 기준.** normalized 미지정 프로파일 전 종목 수치 불변. NVDA 프로파일을 GAAP 159,613 +
normalized 143,451로 재기입해도 현 결과 재현.
**평가 요청.** ROE 계열이 normalized를 쓸 때 auto method selection(DDM/RIM 분기)이 뒤집히는 종목이
있는지 — 금융주(kb_financial) 영향 확인 필요.

## P5 — TTM DCF stub-period 정식화

**문제.** TTM 앵커 DCF 1년차 성장 45%는 "Q1 기반영 후 잔여 전환" 수기 환산치(CODEX 1차 (g): 유지 가능하나
비정식). 엄밀하게는 FY27E를 첫 명시 예측연도로 두는 방식이 맞음.

**설계 스케치.** `DCFParams`에 `explicit_first_year_ebitda: Optional[float]` 추가 — 지정 시 1년차는
성장률 대신 명시값 사용, 이후 `ebitda_growth_rates[1:]` 적용. 기존 `revenue_growth_rates` 선례와 동일한
Optional 하위호환 패턴.

**수용 기준.** 미지정 시 전 종목 불변. NVDA TTM에 FY27E EBITDA 260,600 지정 시 DCF 교차검증값이
수기 45% 방식과 ±3% 내.
**평가 요청.** TV 정상화(normalized FCFF) 경로가 명시 1년차와 충돌하지 않는지(engine.md TV 규칙).

## P6 — NVDA SEG 매핑 재설계 (부문 보고 개편 대응)

**문제.** Q1 FY27부터 NVIDIA 보고체계가 Data Center(Hyperscale/ACIE) + Edge Computing으로 개편.
차기 10-Q부터 구 기준(DC/Gaming/ProViz/Auto) 소급 공시 소멸 가능 → 현 SEG1~3 매핑 데이터 갱신 불가.

**설계 스케치.** 차기 분기 프로파일부터 SEG1=DC-Hyperscale, SEG2=DC-ACIE, SEG3=Edge Computing으로
재정의(멀티플 재보정 필요: Hyperscale vs ACIE 성장·마진 차등). 옵셔널리티 2종 유지. 과거 비교성은
프로파일 헤더 코멘트로 단절 명시.

**평가 요청.** 세그먼트 코드 재사용(SEG1 의미 변경) vs 신규 코드(SEG_HS/SEG_ACIE) — 백테스트
prediction_snapshots의 세그먼트 참조가 코드 재사용 시 오염되는지 db/backtest 관점 판정.

## P7 — Excel Assumptions 시트 출처 라벨 정확화

**문제.** `output/sheets/assumptions.py`(추정)가 βu에 "SEG1+SEG2+SEG3 Peer 평균", D/E에 "2026년말 실적"
고정 라벨 출력 — 실제 βu는 수기 설정, D/E는 분기(2026-04) 기준. 출처 표기 부정확(코스메틱).

**설계 스케치.** 라벨을 데이터 소스에서 유도: `wacc_params`에 Optional `source_notes: dict[str,str]`
추가하거나, 최소한 하드코딩 문구를 중립화("입력 가정" / "최근 보고 기준"). 후자는 5분 수정.

**평가 요청.** 전자(구조화) vs 후자(문구 중립화) — 스키마 추가 비용 대비 효익 판정.

---

## 우선순위 근거 요약

P1은 데이터 신뢰성(전 종목 오염 개연성), P2는 이미 배포된 quality 패치의 경계 안정성, P3~P5는 방법론
정합(CODEX 1차 판정 잔여), P6은 차기 분기 데이터 단절 예방(시한 있음 — 차기 10-Q 전), P7은 코스메틱.
**시한 관점에서는 P6이 P3~P5보다 앞설 수 있음** — 이 트레이드오프 판정도 요청.

## 공통 제약 (CLAUDE.md)

engine/ 순수함수 유지 · Pydantic 불변(model_copy) · 신규 YAML 필드는 Optional+default(하위호환) ·
LLM 쿼터 회사당 ≤4콜 · 기존 프로파일 수치 완전 불변 가드(P2/P4/P5) · tests/fixtures 분리 원칙.
