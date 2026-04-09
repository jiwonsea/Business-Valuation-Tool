# Business Valuation Tool: Codex P2 크래시/로직 버그 수정

## 배경
이번 세션(2026-04-09)에서 6모델 Cross Review를 실행:
- **Claude×3** (Finance/Architecture/TDD): 39건 → P2 10건 수정 완료 (커밋 56b62ae)
- **Codex GPT-5.4**: 15건 — **크래시 버그 4건 + 로직 버그 6건** 신규 발견
- Gemini: rate limit로 부분 결과만 (security 4건, 기존 known issues)
- Qwen: API 연결 실패
- 415/415 테스트 통과, 27 커밋 ahead of origin/main

## 이번 세션 작업: Codex P2 수정 (10건)

### 그룹 A: 크래시 버그 (4건, 최우선)

**A1. `_run_multiples_valuation` dcf_result 미초기화** (valuation_runner.py:922)
- `dcf_result`가 `try` 안에서만 할당 → DCF CV 실패 시 `UnboundLocalError` crash
- MC 호출(L943)과 return(L952)에서 참조
- **수정**: `dcf_result = None` 초기화 + consumer guard

**A2. `_run_nav_valuation` 동일 패턴** (valuation_runner.py:1017)
- MC(L1038), return(L1049)에서 미초기화 `dcf_result` 참조
- **수정**: A1과 동일

**A3. SOTP DCF CV에 try/except 없음** (valuation_runner.py:445)
- mixed-SOTP에서 manufacturing EBITDA<=0이면 전체 밸류에이션 crash
- **수정**: `try/except ValueError` 래핑, DCF 패널 skip

**A4. DCF 시나리오 recalc 미보호** (valuation_runner.py:567)
- `wacc_adj`/`terminal_growth_adj`가 `WACC<=TGR` 만들면 crash
- **수정**: per-scenario `calc_dcf` try/except + base EV fallback

### 그룹 B: 로직 버그 (6건)

**B1. `segment_method_override` 무시됨** (valuation_runner.py:302)
- `needs_dispatch` 1회 계산 → 시나리오에서 method override해도 적용 안 됨
- **수정**: scenario에 `segment_method_override` 있으면 dispatch 강제 활성화

**B2. `_seg_metric()` P/BV·P/E 잘못된 metric** (engine/sensitivity.py:14)
- P/BV→book_equity, P/E→net_income이어야 하는데 EBITDA 기준으로 평가
- **수정**: method별 분기 추가 또는 equity-based 세그먼트 제외

**B3. 시나리오 MC net_debt_override 미사용** (valuation_runner.py:1247)
- mixed-SOTP 시나리오 MC가 `vi.net_debt` 사용 → 이중차감 재발
- **수정**: `effective_net_debt` 전달

**B4. rcps_repay IRR 파생값 sensitivity/MC 누락** (valuation_runner.py:458)
- `sc.rcps_repay or 0`으로만 처리 → override가 None이면 0원으로 처리됨
- **수정**: None일 때 `calc_scenario()`와 동일한 IRR 파생 로직 적용

**B5. MC CPS 배당률 미반영** (engine/monte_carlo.py:122)
- MC가 full IRR로 CPS 복리 계산 — 시나리오 브릿지(`IRR - dividend_rate`)와 불일치
- **수정**: MC에 dividend_rate 파라미터 추가, effective_rate 공식 재사용

**B6. Multiples/NAV market_sentiment_pct elif 가림** (valuation_runner.py:907)
- `ev_multiple` 설정 시 `elif`로 인해 `market_sentiment_pct` 무시
- **수정**: `elif` → 별도 `if`로 변경 (SOTP/DDM/RIM 패턴과 동일하게)

### 그룹 C: P3 보류 (시간 남으면)

- P3-11: SOTP/DCF `weighted_value=0` when no scenarios
- P3-12: DCF primary에 MC 미연결
- P3-13: 시나리오 MC `has_overrides`에 `segment_ebitda` 미포함
- P3-14: `_build_seg_ebitdas_from_consolidated` multi-segment collapse
- P3-15: RIM `terminal_ri` 필드명 오용

## 이전 세션 보류 이슈 (별도 세션)

### Finance 구조 변경 필요
- DDM/RIM net_debt 이중차감 — `calc_scenario` 인터페이스 변경
- CPS effective rate 복리 계산 오류 — 금융 수학 검증 필요
- MC 정규→로그정규 전환 — 전체 캘리브레이션 필요

### 아키텍처 리팩토링
- valuation_runner God module (1260줄) 분리
- consolidated/segments 타입 강화
- _seg_names public 전환

### Security (Gemini 부분 결과)
- Streamlit 인증 없음 (P2)
- ai/prompts.py prompt injection (P2)
- db/repository.py ilike wildcard (P3)

## 모드: normal
