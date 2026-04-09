# Business Valuation Tool: 6-model Cross Review 결과 (2026-04-09)

## 배경
이번 세션에서:
1. **Codex+Qwen P2 21건 수정 완료** (커밋 de9428e) — 크래시 4, 로직 6, 리소스 리크 5, 에러핸들링 5, dict mutation 1
2. **6-model Cross Review 실행** — Claude×3 (Finance/Architecture/TDD) + Codex + Gemini(rate limit) + Qwen(minimal)
3. **P0 1건 + P1 2건 즉시 수정** (커밋 3219e6f, 1dd9773)
   - P0: `_design_scenarios_two_pass()` NameError (segment_codes 미전달)
   - P1: Anthropic client per-call 생성 → lazy singleton
   - P1: sensitivity_multiples CPS repay에 cps_dividend_rate 미반영
4. 415/415 테스트 통과, 31 커밋 ahead of origin/main

## 이번 세션 작업

### 1단계: Finance P1 구조 변경 (DDM/RIM/NAV equity bridge)
가장 영향 큰 Finance 이슈 — calc_scenario 인터페이스 변경 필요.

### 2단계: P2 수정 (아래 이슈 중 선택)
테스트 추가 + 로직 수정.

### 3단계: 테스트 커버리지 확대 (TDD 에이전트 Gap 1-5)

### 4단계: NEXT_SESSION_PROMPT.md 갱신

---

## Finance P1 이슈 (3건, 최우선)

### F-P1-1. DDM equity bridge 이중차감 (valuation_runner.py:684,690)
- DDM은 equity_per_share 직접 산출 (배당 → Ke 할인 = equity value)
- 코드가 pseudo-EV로 변환 후 `calc_scenario()`에서 net_debt/CPS/RCPS 재차감
- **수정**: DDM/RIM에 대해 `calc_scenario()`에 `net_debt=0, cps_principal=0, rcps_principal=0` 전달, 또는 equity-direct scenario path 분리

### F-P1-2. RIM equity bridge — 우연히 net_debt 상쇄되지만 구조 위험 (valuation_runner.py:789,808)
- RIM equity_value + net_debt → calc_scenario에서 net_debt 재차감 = 수학적으로 상쇄
- 그러나 CPS/RCPS/buyback은 book_value에 이미 포함됐는지 불분명 → 이중차감 가능
- **수정**: consolidated["equity"]가 total equity인지 common equity인지 문서화 + 테스트

### F-P1-3. NAV CPS/RCPS 이중차감 (valuation_runner.py:1001,1015)
- NAV = adjusted_assets - total_liabilities (부채 전체 포함)
- total_liabilities에 CPS/RCPS 이미 포함 → calc_scenario에서 재차감
- **수정**: NAV valuation에서 `cps_principal=0, rcps_principal=0` 전달

---

## Finance P2 이슈 (10건)

**F-P2-1. MC 음수 per-share 강제 0 처리** (monte_carlo.py:179)
- `np.maximum(ps, 0)` → 분포 상향 편향. calc_scenario는 음수 전파
- **수정**: 통계 계산은 음수 포함, 히스토그램만 0 바닥

**F-P2-2. MC 멀티플 정규분포 → 로그정규 전환 필요** (monte_carlo.py:107)
- 멀티플은 0 이상 + 우측 꼬리. 정규→clip은 분포 왜곡
- **수정**: `rng.lognormal()` 사용 (Damodaran 표준)

**F-P2-3. DCF revenue=EBITDA 동일 성장률 → 마진 동태 무시** (dcf.py:98)
- revenue_growth_rates 별도 파라미터 추가 옵션

**F-P2-4. SOTP total_ev에 equity-based 값 혼합** (sotp.py:135)
- cross_validate의 implied EV/EBITDA가 equity 부분 포함 → 과대
- **수정**: CV에서 equity-based segment 제외 후 EV/EBITDA 계산

**F-P2-5. DDM/RIM market_sentiment_pct가 pseudo-EV에 적용** (valuation_runner.py:687-688)
- equity-direct 방식에서 EV 기준 %는 레버리지 증폭 효과
- **수정**: equity-direct에서는 equity에 직접 적용 또는 문서화

**F-P2-6. DCF Terminal Value ROIC=WACC 단순화** (dcf.py:127-131)
- 이미 NOTE 코멘트 있음. terminal_roic 옵션 파라미터 추가 가능

**F-P2-7. sensitivity_irr_dlom 음수 equity → 0 처리** (sensitivity.py:109,111)
- calc_scenario와 불일치. 음수 전파 필요

**F-P2-8. sensitivity_multiple_range 동일 패턴** (sensitivity.py:278-280)

**F-P2-9. CPS/RCPS 동일 IRR 사용** (scenario.py:32-34,41-43)
- CPS와 RCPS는 다른 투자자/조건 → 별도 cps_irr/rcps_irr 필드 추가

**F-P2-10. distress ICR에 추정 이자비용 사용** (distress.py:119-120)
- kd_pre × gross_borr 대신 실제 이자비용 옵션 추가

---

## Architecture P1 이슈 (2건, 구조)

**A-P1-1. Untyped dict 데이터 경계** (valuation_runner.py:80-88)
- consolidated, segment_data, segments가 raw dict → KeyError 위험
- ConsolidatedFinancials Pydantic 모델 존재하나 미사용
- **수정**: load_profile()에서 Pydantic 모델로 파싱

**A-P1-2. God module valuation_runner.py (1315줄)**
- YAML 파싱 + 6개 방법론 + CV + MC 오케스트레이션 전부 한 파일
- 6개 `_run_*_valuation()` 메서드 80% 보일러플레이트 중복
- **수정**: profile_loader.py + scenario_evaluator.py + thin dispatcher 분리

---

## Architecture P2 이슈 (5건 선별)

**A-P2-1. _seg_names 등 private 함수가 외부 import됨** (valuation_runner.py:38)
- 3개 모듈에서 import → 리팩토링 시 깨짐. public으로 전환 또는 유틸 분리

**A-P2-2. calc_scenario 10+ 위치 인자** (engine/scenario.py:7-18)
- EquityBridgeConfig dataclass로 묶기

**A-P2-3. MC 전체 분포 메모리 저장** (monte_carlo.py:49,206)
- histogram만 유지, raw distribution 폐기 (DB/API 페이로드 비대)

**A-P2-4. lazy import in hot path** (valuation_runner.py:1175,1232)
- monte_carlo, MCScenarioSummary → top-level import로 이동

**A-P2-5. ApiGuard._reset_singleton() 락 미획득** (api_guard.py)
- pytest-xdist 병렬 테스트 시 경쟁 조건

---

## TDD Gap (15건, 우선순위별 선별)

### P1 Gap (테스트 완전 부재)

**T-P1-1. RIM 파이프라인 통합 테스트 없음**
- `_run_rim_valuation()` 전체 미커버. kb_financial_rim.yaml 존재하나 미사용

**T-P1-2. NAV 파이프라인 통합 테스트 없음**
- nav_test.yaml 존재하나 미사용

**T-P1-3. Multiples 파이프라인 통합 테스트 없음**
- multiples_test.yaml 존재하나 미사용

**T-P1-4. Quality scoring 통합 없음**
- result.quality 할당 검증 없음

**T-P1-5. DCF exit multiple terminal value 미테스트**
- terminal_ev_ebitda 코드 경로 전체 미커버

### P2 Gap (엣지 케이스)

**T-P2-1. DCF capex_fade_to 미테스트**
**T-P2-2. DCF 음수 NOPAT 분기 미테스트**
**T-P2-3. WACC financial sector beta bypass 미테스트**
**T-P2-4. SOTP P/BV·P/E segment 미테스트**
**T-P2-5. sensitivity dict mutation 회귀 테스트 미작성** (F1 수정 검증)
**T-P2-6. _adjust_wacc 직접 테스트 없음**
**T-P2-7. _make_scenario_dcf_params safety floor 미테스트**
**T-P2-8. MC cps_dividend_rate 회귀 테스트 미작성** (B5 수정 검증)

---

## Qwen 요약 (상세 없음, CLI 불안정)

- P0: sensitivity 중복 공식 로직
- P0: 핵심 함수 untyped dict/Any
- P1: 모듈레벨 I/O (import 시 생성)
- P1: CPS 공식 4곳 중복 + 미세 차이

---

## Codex (미완료)
파일 읽기 단계에서 세션 종료. 다음 세션에서 재실행.

## Gemini (rate limit)
gemini-3-flash-preview 용량 부족. 반복 실패.

---

## 이전 세션 보류 (별도 세션)

### Finance 구조 변경
- ~~DDM/RIM net_debt 이중차감~~ → 이번 리뷰에서 재확인 (F-P1-1~3)
- CPS effective rate 복리 계산 오류 — 금융 수학 검증 필요
- ~~MC 정규→로그정규 전환~~ → F-P2-2로 통합

### 아키텍처 리팩토링
- ~~valuation_runner God module~~ → A-P1-2로 통합
- ~~consolidated/segments 타입 강화~~ → A-P1-1로 통합
- _seg_names public 전환

### Security
- Streamlit 인증 없음 (P2)
- ai/prompts.py prompt injection (P2)
- db/repository.py ilike wildcard (P3)

### P3 보류 (Codex)
- SOTP/DCF `weighted_value=0` when no scenarios
- DCF primary에 MC 미연결
- 시나리오 MC `has_overrides`에 `segment_ebitda` 미포함
- `_build_seg_ebitdas_from_consolidated` multi-segment collapse
- RIM `terminal_ri` 필드명 오용

## 모드: normal
