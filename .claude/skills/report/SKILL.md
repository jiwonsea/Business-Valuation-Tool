# Report Skill

## Description
TRIGGER when: 사용자가 "리서치 노트 작성", "보고서 만들어", "Excel 출력", "결과 요약", "분석 리포트", "발표 자료" 등 밸류에이션 결과를 정리된 산출물로 만들려 할 때.
DO NOT TRIGGER when: 밸류에이션 실행 (→ /valuation), 결과 검증 (→ /review), DB 조회 (→ /db).

## Overview
밸류에이션 결과를 리서치 노트(마크다운), Excel, 콘솔 리포트 형태로 출력한다. 기존 함수를 조합해서 산출물을 생성.

## Available Outputs
1. **리서치 노트** — `orchestrator.format_summary(vi, result)` → 마크다운 텍스트
2. **Excel 7시트** — `output.excel_builder.export(vi, result, output_dir)` → .xlsx 파일
3. **콘솔 리포트** — `output.console_report.print_report(vi, result)` → 터미널 출력

## Workflow
1. 밸류에이션 결과 확보 (현재 세션 or DB 조회)
2. 출력 형식 결정 (리서치 노트 / Excel / 둘 다)
3. 함수 호출 → 결과물 생성
4. AI 리서치 노트: `ai.analyst.AIAnalyst.research_note()` (ANTHROPIC_API_KEY 필요)

## File References
- [references/output_formats.md](references/output_formats.md) — 각 출력 형식의 구조와 커스터마이즈 포인트

## Gotchas
- `format_summary()`는 `_seg_names(vi)`를 내부 호출. `valuation_runner`에서 import 필요.
- Excel `export()`의 `output_dir`이 None이면 현재 디렉토리에 저장. 파일명은 `{기업명}_밸류에이션_{날짜}.xlsx` 자동 생성.
- AI 리서치 노트는 `ANTHROPIC_API_KEY` 필요. 미설정 시 수동 마크다운(`format_summary`)으로 대체.
- 방법론에 따라 Excel 빈 시트 발생: DDM 기업은 SOTP/D&A 시트 비어있고, 단일부문 DCF는 SOTP 시트 비어있음. 사용자에게 미리 안내.
