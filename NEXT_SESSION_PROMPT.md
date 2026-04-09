# Business Valuation Tool: Post-4th Cross Review (2026-04-09)

## 배경
4차 크로스 리뷰 50건 중 **43건 수정 완료** (1세션).
- 415/415 tests pass, 21 files changed, 미커밋 상태
- 수정 범위: CR 5건 + VL 22건 + AR 10건 + SEC 6건

## 현재 상태
- 415/415 tests pass
- **커밋 필요**: 4차 리뷰 43건 일괄 수정 (21파일)
- P0 전부 해소, P1 3건(equity bridge) 미수정

---

## 즉시 할 일

### 0. 커밋
- `git add` + 커밋 (4차 리뷰 43건 수정)

### 1. F-P1-1~3: Equity Bridge 구조 변경 (P1, 3건)
- **calc_scenario 인터페이스 변경 필요** — 가장 큰 잔존 리스크

**F-P1-1. DDM equity bridge 이중차감** (valuation_runner.py:684,690)
- DDM은 equity-per-share 직접 산출 → calc_scenario에 EV로 전달하면서 net_debt 이중차감
- **수정**: DDM path에서 calc_scenario의 net_debt=0 또는 equity-direct 분기 추가

**F-P1-2. RIM equity bridge 구조 위험** (valuation_runner.py:789,808)
- RIM도 equity value 직접 산출 → 동일 이중차감 패턴
- **수정**: F-P1-1과 동일 패턴 적용

**F-P1-3. NAV CPS/RCPS 이중차감** (valuation_runner.py:1001,1015)
- NAV는 자산-부채 기반 → CPS/RCPS가 부채에 이미 포함될 수 있음
- **수정**: NAV path에서 CPS/RCPS 이미 반영 여부 검증 후 분기

**설계 방향**: calc_scenario에 `is_equity_direct: bool` 파라미터 추가
- True: net_debt 차감 스킵 (DDM, RIM, P/E, P/BV)
- False: 기존 EV→equity bridge 유지 (SOTP, DCF, NAV, EV/EBITDA)

---

## 2단계: 잔존 VL (3건)

**VL-12. WACC D/E cap 200% + distress discount 이중벌칙** (wacc.py:25)
- D/E>200% → WACC 과소(DCF 과대) + distress discount(SOTP 과소)
- **설계 논의 필요**: WACC premium 보정 vs distress discount 조건부 비활성

**VL-15. DCF sensitivity가 EV 출력 (per-share 아님)** (sensitivity.py:153-171)
- 다른 sensitivity는 per-share, DCF만 EV → UI에서 비교 불가
- **수정**: per-share 변환 또는 console_report/app.py에 단위 레이블

**VL-12는 설계 결정, VL-15는 UI 연동이 필요해 별도 세션 권장**

---

## 3단계: SEC P3~P4 잔존 (2건)

**SEC-4. Cross-process API usage race** (pipeline/api_guard.py:157) [P3]
- threading lock만 → 멀티프로세스(CLI+Streamlit) 동시 실행 시 usage 파일 손상
- **수정**: `portalocker` 파일 락 (pip install 필요)

**SEC-5. DB upsert insecure fallback** (db/repository.py:53) [P3]
- upsert 실패 → blind insert fallback → 중복 가능
- **수정**: 특정 예외 catch + conflict handling

---

## 4단계: 기존 미수정 P2 (이전 리뷰, 10건)

F-P2-1~10, A-P2-1~5 — 이전 NEXT_SESSION 참조
(MC 로그정규, DCF revenue growth, SOTP equity mixing 등)

---

## 5단계: TDD Gap (이전 리뷰 기준, 13건)

T-P1-1~5: RIM/NAV/Multiples 통합, quality scoring, DCF exit multiple
T-P2-1~8: capex_fade, 음수 NOPAT, financial beta, SOTP P/BV·P/E 등

---

## 이번 세션 수정 완료 목록 (43건)

### 크래시 경로 (5건)
- CR-1: DDM 시나리오 calc_ddm_engine try/except + base fallback
- CR-2: DCF sensitivity → dcf_result None이면 스킵
- CR-3: auto_analyze() news = None 초기화
- CR-4: dcf_params conditional 파싱 (equity-only 프로필 지원)
- CR-5: scenarios → .get({})

### 밸류에이션 로직 (22건)
- VL-1: MC RCPS → _derive_rcps_repay(sc, vi) 통일
- VL-2: RIM TV → end-of-period BV 사용
- VL-3: DCF TV → normalized FCFF (capex-fade artifact 제거)
- VL-4: MC DCF ratio → np.clip(0, 3.0) cap
- VL-5: P/E·P/BV 시나리오 ev_multiple → net_debt add-back
- VL-6: PBV/PE + segment_net_debt 미설정 경고 로그
- VL-7: MC에서 pbv/pe 세그먼트 skip (continue)
- VL-8: sensitivity_multiples에 pbv_pe_ev 고정값 전달
- VL-9: row_seg == col_seg → col_ev = 0 (2x 방지)
- VL-10: SOTP PBV/PE → multiple_override 적용
- VL-11: Sensitivity IRR/DLOM 음수 equity 전파, DLOM만 스킵
- VL-13+20: Quality score → sr.post_dlom 직접 + 확률가중 평균
- VL-14: DCF EV=0 → cross-validation 제외
- VL-16: MC histogram/stats 동일 set + pct_negative 필드
- VL-17: 단일 세그먼트 MC → 균등 배분
- VL-18: DCF primary에 MC 호출 추가
- VL-19: "ev " → \bev\b regex word boundary
- VL-21: binary_search 미수렴 → None 반환
- VL-22: hashlib.md5 결정적 seed
- VL-23: mc_revenue_std_pct, distress_max_discount, market_signals 파싱
- VL-24: treasury_shares 검증 (0 ≤ treasury ≤ ordinary)
- VL-25: _make_scenario_dcf_params → model_copy(update=...)

### 코드 품질 (10건)
- AR-1: ET_Element import (mypy 호환)
- AR-2: ZipFile context manager
- AR-3: vi.wacc_params mutation → model_copy
- AR-4: os.replace 원자적 파일 교체
- AR-5: _save_usage() disk I/O → lock 밖으로
- AR-6: 캐시 키 → md5 content hash
- AR-7: _seg_metric alloc None guard
- AR-8: Anthropic client → threading.Lock double-check
- AR-9: LLM fallback → raise from e 예외 체인
- AR-10: 억원 → // 정수 나눗셈

### 보안 (6건)
- SEC-1: Excel export filename sanitization
- SEC-2: Profile ticker path traversal sanitization
- SEC-3: SSL cert → user-specific ~/.cache/ 디렉토리
- SEC-6: API guard 로그 → class name만 출력
- SEC-7: DART base URL → env var
- SEC-8: 이미 errors="replace" 적용 확인

## 작업 우선순위

1. **커밋** (즉시)
2. **F-P1-1~3**: equity bridge 구조 변경 (calc_scenario 인터페이스)
3. **VL-12**: WACC D/E 이중벌칙 설계 논의
4. **SEC-4~5**: portalocker + DB upsert
5. **기존 P2 + TDD gap**: 점진적 수정

## 모드: normal
