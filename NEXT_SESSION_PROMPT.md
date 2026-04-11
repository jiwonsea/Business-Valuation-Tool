# Business Valuation Tool: 다음 세션

## 현재 상태
- 534/534 tests pass
- origin/main 동기화 필요

## 완료된 작업 (2026-04-12 VL fixes + scenario.py 정합성 수정 세션)

### 이전 세션 (CR-1/CR-2/CR-3)
- CR-1: DDM/RIM ke≤0 크래시 방지
- CR-2: sensitivity_dcf ZeroDivisionError 방지
- CR-3: SOTP base_year UnboundLocalError 방지

### 지난 세션 (VL-1/VL-2/VL-3/VL-4)
- **VL-1** `valuation_runner.py`: `_derive_rcps_repay` — `irr is None`일 때도 `rcps_principal` 반영
- **VL-2** `engine/rim.py`: TV 공식 수정 — extra `*(1+g)` 제거
- **VL-3** `valuation_runner.py`: MC TV base를 normalized FCFF 사용
- **VL-4** `engine/monte_carlo.py`: MC TV spread 최솟값 0.5% 적용

### 이번 세션 (VL-1b: scenario.py 정합성)
- **VL-1b** `engine/scenario.py`: `calc_scenario` CPS/RCPS 조건 수정
  - `elif sc.irr is not None and cps_principal > 0` → `elif cps_principal > 0` + `(sc.irr or 0)`
  - `elif sc.irr is not None and rcps_principal > 0` → `elif rcps_principal > 0` + `(sc.irr or 0)`
  - `_derive_rcps_repay`(MC)와 `calc_scenario`(결정론적) 경로 완전 정합
  - 신규 회귀 테스트 2개 추가: `test_calc_scenario_rcps_included_when_irr_none`, `test_calc_scenario_cps_included_when_irr_none`

---

## 백로그

현재 미해결 항목 없음.

---

## 모드: normal
