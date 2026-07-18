# 새 세션 프롬프트 — SK하이닉스(000660) 밸류에이션 커레이션 + 보고서

> business-valuation-tool 폴더에서 새 세션으로 열 것. 목적 = draft 스텁인 하이닉스 프로필을 투자가능(investable) 수준으로 커레이션하고, NVDA 2026-07-10 deep dive 수준의 기업분석보고서 PDF를 만든다. 용도 = 증권사 리서치/RA 지원 첨부 + 면접 대비. **마감 압박 없음 — 정합성 최우선.**

## 현재 상태 (⚠️ 프로필이 draft 스텁 — F등급)
`profiles/000660.yaml`(analysis_date 2026-07-06)을 `python3 cli.py --profile profiles/000660.yaml --json`로 돌리면:
- `quality.grade = "F"`, `draft: true`, warning "TODO/stub assumptions remain; not investable"
- `investability_blockers: ["no DCF value to cross-check against peer median"]`

### 반드시 고칠 스텁 값 (실제 재무로 커레이션)
1. **DCF capex 스텁**: 2026 capex가 **132.3조원**으로 잡혀 FCFF가 음수(−65.8조). SK하이닉스 실제 연 capex는 ~20~40조 수준 → DART/IR로 실제값 확인해 정상화
2. **DCF 영업이익 단절**: DCF의 2026 op ≈ 2.7조인데, `segment_data.2025`의 세그먼트 OP 합은 SEG1 21.2조+SEG2 22.6조+SEG3 3.3조 ≈ **47조**. DCF projection이 세그먼트 실적과 연결되지 않음 → 매출·마진·D&A·capex 가정을 실제 기준으로 재설정
3. **segment `gross_profit: 0`**: 전 세그먼트 0 → 실제 GP 또는 EBITDA 기준 확인
4. **세그먼트 EV/EBITDA 멀티플**(DRAM 9.1 / NAND 8.6 / 파운드리·기타 10.3): 피어(마이크론·삼성 반도체)·사이클 위치 근거로 검증. HBM 프리미엄 반영 여부 결정
5. **주가 스냅샷**: market_comparison의 market_price 2,425,000원(profile_snapshot) — as-of 날짜·현재가 재확인(사용자 제공 또는 리포트 인용, 기준일 명시)
6. shares_total 690,455,268 · corp_code 00164779 — 확정값(DART 대조)

## 절차
1. DART 분기/사업보고서로 실제 매출·세그먼트 OP·capex·D&A·차입금·현금 확보 (샌드박스 외부망 차단 → Chrome javascript_tool same-origin fetch 경로, reference_dart_via_chrome_javascript 참조)
2. `profiles/000660.yaml` 커레이션 → `cli.py --profile ... --json`이 **draft:false + grade C 이상**, blocker 없음이 될 때까지 반복
3. NVDA 템플릿 참고: `valuation-results/2026-07-10-nvda-deep-dive/`(report md·_report.html·charts·_run_*.txt). 동일 섹션 구조로 `valuation-results/2026-07-16-hynix-deep-dive/`에 산출
4. 보고서 md → PDF: weasyprint(`pip install weasyprint --break-system-packages`, font-family를 Noto Sans CJK KR로 치환, `base_url='.'`로 charts png 임베드) 또는 Chrome headless. fitz로 1페이지 렌더 육안 검증
5. **전수 검산**: 모든 수치를 분자·분모 명시해 재계산(WACC는 Ke·Kd세후·자본구조 블렌드까지 표기해 재현 가능하게 — NVDA에서 WACC 표기 누락이 Codex [치명] 됐던 사례). Codex `--skip-git-repo-check`로 1라운드 이상
6. 완성본 PDF를 career 폴더로 복사(향후 지원 첨부용)

## 앵글 (증권사 리서치 대비)
메모리 반도체 사이클(DRAM/NAND) + HBM AI 수요. NH 하반기 반도체 뷰 '모든 AI는 메모리를 거친다'와 정합 — 단, 첨부 보고서엔 수신처 메타("왜 NH" 등) 넣지 말고 중립 분석 유지.

## 원칙 (CLAUDE.md)
없는 수치 날조 금지 · 스텁 값을 실제인 양 쓰지 말 것 · 큰 파일은 bash heredoc · 개념 오용(성장조정배수·CV 정의·WACC 블렌드) 자가점검.
