# CLAUDE Review Handoff — BVT Units + SOTP Guardrails

Date: 2026-07-13

## Review Mode

- Review only. Do not modify files unless the user explicitly requests it.
- The working tree contains many unrelated uncommitted changes.
- Never use `git checkout`, `git restore`, or `git reset --hard`.
- Evaluate only the scoped files and hunks listed below.

## Objective

Re-review the BVT pipeline fixes for:

1. KR unit detection that previously inflated per-share values by 100x.
2. Silent SOTP scenario multiple clamping.
3. Follow-up P1 findings from the first CLAUDE review.

## Scoped Files

- `engine/units.py`
- `engine/market_comparison.py`
- `engine/quality.py`
- `output/console_report.py`
- `valuation_runner.py`
- `schemas/models.py`
- `tests/test_engine.py`
- `tests/test_quality.py`
- `tests/test_scenario_spread_guardrail.py`

## Implemented Contract

### KR units

- Engine storage defaults to KRW millions for KR profiles.
- `detect_unit()` no longer infers an arithmetic unit from revenue scale.
- Explicit `company.unit_multiplier` remains authoritative.
- Revenue in the old 10,000–1,000,000 hazard band now uses `1_000_000`.
- Intrinsic/market ratios above 10x or below 0.1x warn about possible unit contamination.
- Negative intrinsic values retain the severe-gap warning but do not receive the unit-contamination label.

### SOTP clamp visibility

- `_SOTP_MAX_RATIO` remains `2.0`.
- Every clamped segment emits `logger.warning` with company, scenario, segment,
  original/applied multiple, and original/applied ratio.
- The same warning is printed at the top of the console report.
- A wide spread bypass requires both:

```yaml
curated: true
allow_wide_scenario_spread: true
```

- The bypass warns but does not clamp.
- `allow_wide_scenario_spread: true` without `curated: true` still clamps.

### Quality score

- A multiple clamp caps scenario spread points at 5/9.
- Bull/Base EV below 1.20x caps scenario spread points at 6/9.
- Both conditions intentionally use `min()` rather than additive deductions because
  clamp is usually the cause and narrow spread is the downstream result.
- Explicit `Bull`/`Base` codes are preferred, case-insensitively.
- For A/B/C-style codes only, fallback semantics are:
  - Base = highest-probability scenario.
  - Bull = highest-total-EV scenario.
- `scenario_validator` retains its separate Bull/Bear >=1.3x generation contract.
  Quality's Bull/Base 1.20x check detects upside-case collapse after runtime transforms.

## First Review P1 Resolution

### P1-1: Negative intrinsic unit-warning false positive

Resolved with an `intrinsic > 0` guard. Positive values below 0.1x still warn because
the original user requirement explicitly requested both the upper and lower gates.

### P1-2: A/B/C codes skipped Bull/Base scoring

Resolved with explicit-code-first selection plus the probability/EV fallback above.
A dedicated A/B/C regression test verifies the deduction.

### P1-3: 1.3x Bull/Base threshold conflicts with the 2.0x Bull/Bear clamp

Resolved by recalibrating Bull/Base to 1.20x. `_SOTP_MAX_RATIO` was not changed.

## Tests Added or Strengthened

- KR mid-band `detect_unit()` + `per_share()` regression.
- `load_profile()` → `run_valuation()` mid-band profile equivalence against an
  explicit `unit_multiplier: 1_000_000` control.
- Extreme positive high/low intrinsic-to-market unit warnings.
- Negative intrinsic value does not receive a unit-contamination warning.
- Clamp logger/report/quality behavior.
- `curated=true` without opt-in still clamps.
- `allow_wide=true` without curated still clamps.
- Dual opt-in warns and bypasses the clamp.
- Bull/Base narrow-spread quality deduction.
- A/B/C scenario-code fallback deduction.

## Verification Evidence

### Profile regression

- Profiles inspected: 48.
- Patch-before vs final snapshot diff: 0.
- 46 runnable profiles: identical `unit_multiplier`, `weighted_value`, and every
  scenario `post_dlom` value.
- `346010.yaml` and `_template.yaml`: same pre-existing `shares_total=0` validation
  error before and after.
- `profiles/nexus.yaml`: `unit_multiplier=1_000_000`, weighted value `1,065` KRW.

### Tests

```powershell
python -m pytest tests/ --deselect tests/test_engine.py::TestScenarioDriverRoundTrip
```

Result:

```text
933 passed, 5 deselected, 4 warnings in 27.24s
```

The four warnings are pre-existing Supabase/deprecated-`utcnow()` warnings.

### File integrity

- Every modified Python file passed `ast.parse()` immediately after editing.
- PowerShell `(Get-Content <file>).Count` was used for line-count truncation checks
  because `wc` is unavailable in the Windows shell.
- `git diff --check` should be rerun by the reviewer on the Windows workspace.

## Deferred P2 Items

These were intentionally not included in this defect-fix scope:

- Persisting a wide-spread bypass audit flag into DB/backtest results.
- Renaming `detect_unit()` and removing its compatibility `revenue` argument.
- Enforcing currency label/unit-multiplier pairs in `CompanyProfile`.
- Adding external empirical justification for `_SOTP_MAX_RATIO = 2.0`.

## Requested Review Output

1. Verdict: approve / conditional approve / reject.
2. Findings ordered P0/P1/P2 with `file:line`, reproduction, impact, and fix.
3. Requirement-by-requirement compliance table.
4. Regression-test blind spots.
5. Whether the deferred P2 items can safely remain separate.

If there are no merge-blocking findings, explicitly state `No P0/P1 findings`.
