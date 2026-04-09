# Business Valuation Tool: P2 보류 이슈 + Phase 3

## 배경
직전 세션(2026-04-09)에서 완료한 것:
- **P0 5건 수정** (커밋 640d8a6): MC net_debt 이중차감, segment_revenue 미저장, 음수 EBITDA 제외, cross-validation DCF crash, rcps_repay=0 override
- **P1 4건 수정** (커밋 6d8a3e4): gap_diagnostics 테스트 20개, silent except→로깅, engine/ 순수성(peer_fetcher 제거), f-string YAML→yaml.dump()
- **P2 10건 수정** (이번 세션, 미커밋):
  - F1: RIM ROE 수렴 `range(5)` → `range(1, 6)` — year5에서 80%만 수렴하던 버그
  - F2: SOTP P/BV·P/E 세그먼트 book_equity=0/net_income=0 시 `logger.warning` 추가
  - F3: `sensitivity_multiples` deductions에 CPS/RCPS/buyback 추가 — 시나리오 대비 과대평가 수정
  - F4: DCF terminal value ROIC=WACC 가정 독스트링 문서화 + NOL 미반영 limitation 명시
  - F5: WACC에서 CPS/RCPS 존재 시 preferred equity 미분리 경고 로그
  - A1: `load_profile` peers/news_drivers except 범위 `(ValueError, Exception)` → `(ValueError, TypeError, KeyError)` + warning 로그
  - A2: `engine.quality` inline import → top-level import
  - T1: MC zero shares 경계값 테스트
  - T2: gap_diagnostics zero EBITDA 경계값 테스트
  - T3: DDM params=None 에러 경로 테스트
- 415/415 테스트 통과
- 27+ 커밋 ahead of origin/main

## 이번 세션 작업

### 1단계: P2 보류 이슈 (구조 변경 필요)
리뷰에서 도출되었으나 영향 범위가 커서 보류한 항목:

1. **DDM/RIM net_debt 이중차감** (Finance P2)
   - DDM은 equity value를 직접 반환하는데 `calc_scenario`에서 net_debt를 재차감
   - RIM도 동일 패턴 (`equity_value + net_debt` → `calc_scenario`에서 다시 차감)
   - `calc_scenario` 공통 인터페이스 변경 또는 DDM/RIM 전용 경로 필요
   - CPS/RCPS/eco_frontier가 0이 아닌 경우 equity 과소평가

2. **CPS effective rate 계산 오류** (Finance P2)
   - `effective_rate = max(sc.irr - cps_dividend_rate, 0.0)` 후 복리 적용은 수학적 부정확
   - 배당이 매년 지급되면 compound에서 차감이 아닌 연금 합산 방식이어야 함
   - 시뮬레이션 테스트 설계 후 수정 필요

3. **MC 정규분포 → 로그정규 전환** (Finance P2)
   - `np.maximum(samples, 0)` floor 절단이 left-truncated bias 유발
   - 로그정규 파라미터 변환: `mu_ln = log(mu²/sqrt(mu²+sigma²))`
   - 기존 모든 MC 테스트 결과값이 변경됨 — 캘리브레이션 필요

### 2단계: Phase 3 아이템 (calibration 인프라)
- Monte Carlo 캘리브레이션 인프라
- GOOGL/TSLA 프로필 검증
- 감사 보고서에서 도출된 추가 백로그

### 3단계: NEXT_SESSION_PROMPT.md 갱신

## 이전 리뷰 참고 (문서화 완료 / 수정 불필요)
- Terminal FCFF 재투자율: ROIC=WACC 가정 독스트링 추가됨 (F4)
- NOL 미반영: limitation 독스트링 추가됨 (F4)
- Hamada D/E cap 200%: 의도적 설계, 경고 로그 검토만

## 아키텍처 보류 (별도 리팩토링 세션)
- valuation_runner God module (1260줄) 분리
- consolidated/segments 타입 강화 (ConsolidatedFinancials/SegmentInfo)
- _seg_names private 함수 public 전환

## 모드: normal
