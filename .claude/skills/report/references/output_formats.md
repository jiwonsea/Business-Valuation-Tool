# Output Format Details

## 1. Research Note (Markdown)

`orchestrator.format_summary(vi, result)` → `str`

### Included Sections (auto-branches by methodology)
- Company name, analysis date, methodology
- WACC (βL, Ke, Kd)
- DDM result (financials)
- Relative valuation (Multiples Primary)
- NAV (holding/REIT)
- SOTP EV (multi-segment)
- DCF EV + deviation from SOTP
- Per-scenario per-share value + probability-weighted conclusion
- Market price comparison + gap ratio
- Cross-validation results

### AI Research Note
```python
from ai.analyst import AIAnalyst
analyst = AIAnalyst()
note = analyst.research_note(vi, result)  # Claude API call
```
- Includes qualitative analysis: investment opinion, risk factors, catalysts, etc.
- AI analysis result is auto-saved to DB (step="research_note")

## 2. Excel 7-Sheet

`output.excel_builder.export(vi, result, output_dir)` → `str` (file path)

| Sheet | Content | Applicable Methodology |
|-------|---------|----------------------|
| Assumptions | Company info, WACC, Peers | Common |
| D&A Allocation | Asset weight → D&A allocation → per-segment EBITDA | SOTP |
| SOTP | Per-segment EV/EBITDA → summed EV | SOTP |
| Scenarios | Per-scenario per-share value + probability-weighted | Common |
| DCF | FCFF projection + terminal value | DCF |
| Sensitivity | Multiple/WACC/growth rate grid | Common |
| Cross-Validation | EV/Revenue, P/E, P/BV, etc. | Common |

## 3. Console Report

`output.console_report.print_report(vi, result)` → stdout

- Terminal 60-char width format
- For debugging / quick review
