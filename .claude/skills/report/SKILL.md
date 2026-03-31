# Report Skill

## Description
TRIGGER when: user mentions "리서치 노트 작성", "보고서 만들어", "Excel 출력", "결과 요약", "분석 리포트", "발표 자료", "research note", "generate report", "Excel output".
DO NOT TRIGGER when: running valuation (→ /valuation), result validation (→ /review), DB query (→ /db).

## Overview
Outputs valuation results as research notes (markdown), Excel, or console reports. Generates deliverables by composing existing functions.

## Available Outputs
1. **Research note** — `orchestrator.format_summary(vi, result)` → markdown text
2. **Excel 7-sheet** — `output.excel_builder.export(vi, result, output_dir)` → .xlsx file
3. **Console report** — `output.console_report.print_report(vi, result)` → terminal output

## Workflow
1. Obtain valuation result (current session or DB query)
2. Determine output format (research note / Excel / both)
3. Call function → generate deliverable
4. AI research note: `ai.analyst.AIAnalyst.research_note()` (requires ANTHROPIC_API_KEY)

## File References
- [references/output_formats.md](references/output_formats.md) — Structure and customization points for each output format

## Gotchas
- `format_summary()` internally calls `_seg_names(vi)`. Requires import from `valuation_runner`.
- If Excel `export()` `output_dir` is None, saves to current directory. Filename is auto-generated: `{company_name}_밸류에이션_{date}.xlsx`.
- AI research note requires `ANTHROPIC_API_KEY`. If not set, fall back to manual markdown (`format_summary`).
- Depending on methodology, some Excel sheets may be empty: DDM companies have empty SOTP/D&A sheets; single-segment DCF has empty SOTP sheet. Inform user in advance.
