---
paths: ["cli.py", "valuation_runner.py", "output/**/*.py"]
---

# Reporting / Engine Boundary

- CLI and `output/` must consume `ValuationResult`; they must not independently recompute valuation-engine results.
- Market-dependent enrichment that can only run after a quote is available belongs in one `valuation_runner.py` result-enrichment function. CLI may fetch/select the quote and call that function.
- Excel formulas used for user-editable models are presentation artifacts, not authoritative engine calculations. Label them as formulas and keep the engine reference value separate.
- Before adding an `engine.*` calculation call under CLI or `output/`, first check whether the value already exists on `ValuationResult`. If it does, reuse it.
