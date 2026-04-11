# Business Valuation Tool: 다음 세션

## 현재 상태
- 550/550 tests pass
- origin/main 동기화 필요 (4개 미push 커밋)

## 완료된 작업 요약

### 이전 세션까지 (CR-1~3, VL-1~4)
- CR-1/2/3: DDM ke≤0 크래시, sensitivity ZeroDivisionError, SOTP UnboundLocalError 방지
- VL-1~4: RCPS irr=None 누락, RIM TV 공식, MC normalized FCFF, MC TV spread min 0.5%

### 2026-04-11 세션 (output/ + wp_poster 크로스 리뷰)
- wp_poster: dead statement, markdown injection, script injection, URL scheme validation
- dashboard: DCF per_share 불일치, football field 음수 clamping
- scoring: case-insensitive sector filter (_is_real_company)

### 2026-04-12 세션 A (Excel 5-sheet 리뷰 + push)
- scenarios.py: dead statement `any(...)` → `has_dlom = any(...)`, DLOM 행 조건화
- sensitivity.py: `_get_ref_label_value` SOTP fallthrough → "DCF EV" 오표시 수정
- assumptions.py: `_write_assumption_drivers` SOTP/DCF 분기 추가
- origin/main push 완료 (커밋 28e9d40 기준)

### 2026-04-12 세션 B (rnpv.py 4-fix 크로스 리뷰)
4-model cross-review (Gemini + Qwen + Codex + Claude 합성):
- **FX-1** (P3): Tornado 섹션 내 중복 `style_header_row` import 제거
- **FX-2** (P2): `rnpv_pct` 가드 `> 0` → `!= 0` (음수 total_rnpv 시 실제 비중 표시)
- **FX-3** (P2): Equity Bridge `enterprise_value` → `pipeline_value` (명시성)
- **FX-4** (P2): Peak Revenue 요약 `drugs_with_curves` → `rnpv.drug_results` (모든 약물 포함)

FALSE ALARM 확인 목록:
- gap_pct /100 표시: PCT_FMT 0-1 float 기대 → 정상
- total_col 인덱스: drugs col 2..N+1, total N+2 → 정상
- "시장 낙관/비관" 레이블: gap_pct=(model-target)/target*100 공식 확인 → 정상
- revenue_curve launch year: engine에서 pre-launch zeros 패딩 확인 → 정상
- ctx.vi.net_debt null 크래시: int=0 기본값 확인 → 정상

---

## 다음 작업: scheduler/naver_poster.py 구현 + origin/main push

**세션 시작 시 아래 프롬프트를 그대로 복사해서 사용:**

---

Business Valuation Tool — push + naver_poster.py 구현 (선택)

경로: `F:\dev\Portfolio\business-valuation-tool`
현재 상태: 550/550 tests pass, 4개 미push 커밋

## 즉시 실행할 작업

1. `git push origin main` (4개 커밋 push)

## 선택적 작업: scheduler/naver_poster.py 구현

현재 stub 상태. 크로스 리뷰에서 확정한 보안 패턴:
- `os.getenv("NAVER_ID")` / `os.getenv("NAVER_PW")` — 절대 로그 금지
- `try/finally: driver.quit()` — 리소스 누수 방지
- Chrome Profile 재사용 — CAPTCHA 방지
- wp_poster.py 보안 패턴 동일 적용 (markdown escaping, URL scheme 검증, script tag 제거)

## 모드: normal

---
