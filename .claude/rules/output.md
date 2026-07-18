---
paths: ["output/**/*.py"]
---

# Output (Excel / Console Report) Gotchas

Excel 7-sheet builder (assumptions, D&A, SOTP, scenarios, DCF, sensitivity, cross-validation). For rNPV-specific sheets see `rnpv.md`.

- `console_report.py` `is_mixed` must stay in sync with `_needs_method_dispatch()` in valuation_runner — both should trigger on any non-default method (ev_revenue, pbv, pe). Equity Bridge display is conditional on pbv/pe only.
- `_write_assumption_drivers` writes exactly ONE row (no `r` return). New valuation method branches must fit a single row, or the function signature must be extended to return `r`.

## Excel filename — local vs remote

Local files (`output/excel_builder.py:56`) use the Korean convention `{company}_밸류에이션_모델.xlsx` (e.g., `삼성전자_밸류에이션_모델.xlsx`) for human readability in the results folder. Supabase-uploaded filenames (`_upload_excels_to_storage` in `scheduler/weekly_run.py`) use `CamelCase(MM-DD)_valuation.xlsx` to avoid Windows/URL encoding issues: `_to_camel()` strips `co.`/`corp.`/`inc.`/`ltd.` suffixes, title-cases remaining words, joins first 3; date is pulled from the week folder via `(\d{2})-(\d{2})`. Examples: `SamsungElectronics(04-12)_valuation.xlsx`, `AAPL(04-12)_valuation.xlsx`. Do not expect local and remote names to match.
