---
paths:
  - "forecast/**"
---

# Forward Earnings Layer

## Scope

- `forecast/` is the forward-earnings layer embedded in this repository, not a sibling repository.
- It provides quarterly/annual EPS forecasts, consensus-gap analysis, trailing-quarter backtests, and a sensitivity bridge into the root valuation layer.
- Start with `forecast/README.md`; historical `forecast/HANDOFF_*`, `PLAN_*`, `START_*`, and generated graph reports are records, not current path instructions.

## Architecture

- `forecast/engine/` contains pure functions: no IO, global state, or logging.
- `forecast/pipeline/` owns Yahoo Finance and DART IO.
- Inputs and outputs are Pydantic v2 models; engine functions never return DataFrames.
- Assumptions belong in `forecast/profiles/*.yaml`; do not hardcode company assumptions in Python.
- Use `encoding="utf-8"` for file IO to avoid Windows cp949 failures.

## Commands

```powershell
pip install -e ".[forecast]"
python -m forecast.cli --company sk_hynix --dry-run
pytest forecast/tests/ -q
python forecast/scripts/verify_anchor.py
pytest forecast/tests/test_frozen_integrity.py -q -s
```

## Data and runtime

- `.KS` Yahoo fields can be sparse; preserve null handling and explicit consensus-unavailable warnings.
- DART corp-code cache and API retry/backoff remain pipeline concerns. Never print or commit API keys.
- Networked Yahoo/DART runs can fail in restricted environments; use `--dry-run` for offline verification and run live pulls on an authorized host.
- Keep generated single-file Plotly HTML below 5 MB.

## Verification and integrity

- `*_FROZEN.md` reports are immutable. Corrections go in sibling `*_errata.md` files.
- The FROZEN gate must run from a Git checkout and must satisfy `checked == passed == 4`, `supported_skipped == 0`, and `failures == []`.
- `python forecast/scripts/verify_anchor.py` is the offline anchor gate.
- Backtests must beat a naive baseline, not merely match direction. Revisit assumptions when revenue MAPE exceeds 10% or EPS MAPE exceeds 25%.
- Preserve the separation between forward EPS assumptions and the root valuation engine; do not silently wire forecast outputs into valuation inputs.

## Conventions

- Code, comments, docstrings, and configuration are English; user-facing reports and terminal output may be Korean.
- Use Pydantic v2 `model_validate` and `model_dump`, not deprecated v1 APIs.
- External API failures are raised by pipeline code and handled by callers; engine code validates inputs with explicit errors.
- Tests use `forecast/tests/fixtures/`; do not depend on mutable generated outputs.
