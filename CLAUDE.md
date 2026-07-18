# CLAUDE.md

@~/.claude/CLAUDE.md

## Project

KR/US company valuation platform. Pure-function engine + Pydantic schemas + YAML profiles + AI-assisted analysis. Python 3.11+.

## Fast Navigation

- Start with `README.md` for the module map, then read only the path relevant to the task.
- Ignore generated outputs by default: root `*.xlsx`, `logs/`, `valuation-results/`, `test_output/`, `output/calibration/`, `.cache/`, `.claude-octopus/`.
- For valuation math, stay inside `engine/` + `schemas/models.py`.
- For data collection/API issues, stay inside `pipeline/` and avoid `app.py` unless the bug is UI-specific.
- For LLM behavior, stay inside `ai/`, `pipeline/profile_generator.py`, and the prompt/validator pair.
- For weekly automation, stay inside `scheduler/`, `discovery/`, and `db/`.

## Module Rules (read before editing a module)

Module-specific gotchas and methodology live in `.claude/rules/*.md`, each scoped to a `paths:` glob. **Read the matching file before working in that area** (they are intentionally kept out of this always-loaded file to avoid bloat):

- `engine.md` — `engine/**`, `schemas/models.py`: method/scenario selection, core numeric rules, SOTP/PBV/PE interplay, convertibles.
- `rnpv.md` — `engine/rnpv.py`, `reverse_rnpv.py`, `quality.py`, `output/sheets/rnpv.py`: rNPV revenue curve, PoS, reverse rNPV, quality restructuring.
- `distress.md` — `engine/distress.py`: distress discount cap, cyclical exemption, segment tiers.
- `monte-carlo.md` — `engine/monte_carlo.py`, `valuation_runner.py`: MC sampling, TV resampling, negative equity.
- `pipeline.md` — `pipeline/**`: DART/Yahoo/yfinance data collection, `--auto` overwrite, ticker cache.
- `ai.md` — `ai/**`: circuit breaker/fallback, prompt cache invalidation, LLM quota (≤4 calls/company).
- `output.md` — `output/**`: console report sync, Excel filename local-vs-remote convention.
- `db-backtest.md` — `db/**`, `backtest/**`, `calibration/**`: Supabase drift, persistence asymmetry, buckets, calibration.
- `scheduler.md` — `scheduler/**`: weekly discovery/scoring, news matching, Naver poster.

## Architecture

```
ValuationInput (YAML) → run_valuation() → ValuationResult → print_report() / Excel
```

- `engine/` — Pure functions (no IO). `method_selector.py` auto-selects methodology by company type. `rnpv.py` — risk-adjusted NPV for pharma/biotech. `quality.py` — composite 0-100 quality score.
- `schemas/models.py` — Pydantic models. Core contract: `ValuationInput` → `ValuationResult`.
- `pipeline/` — Data collection (DART, SEC EDGAR, Yahoo Finance). IO only here.
- `ai/` — LLM-based segment classification, peer recommendation, scenario design (Claude Sonnet 4).
- `db/` — Supabase integration. `client.py` (singleton), `repository.py` (CRUD), `migrations.sql` (DDL).
- `output/` — Excel 7-sheet (assumptions, D&A, SOTP, scenarios, DCF, sensitivity, cross-validation).
- `scheduler/` — Weekly auto news collection + valuation. `weekly_run.py` (pipeline), `scoring.py` (importance).
- `cli.py` — CLI entry point + `run_valuation()` (SOTP/DCF branching).
- `orchestrator.py` — Profile → valuation → Excel pipeline wrapper.
- `app.py` — Streamlit web UI.

## Commands

```bash
python cli.py --profile profiles/sk_ecoplant.yaml        # profile-based
python cli.py --profile profiles/sk_ecoplant.yaml --excel # Excel output
python cli.py --company "AAPL"                            # auto-fetch (US)
python cli.py --company "삼성E&A"                          # auto-fetch (KR, needs DART_API_KEY)
python cli.py --company "MSFT" --auto                     # with AI analysis
python cli.py --discover --market KR                      # news-based company discovery
python cli.py --weekly                                    # weekly auto-analysis (KR+US, 3 companies)
python cli.py --weekly --markets KR --max-companies 5     # specify market/count
python cli.py --weekly --dry-run                          # discovery only, skip valuation
python cli.py --backtest --backtest-min-age 90            # calibration backtesting report
python -m scheduler.weekly_run                            # direct module execution

streamlit run app.py                                      # web UI
pytest tests/                                             # tests
pip install -e ".[dev,pipeline,ai,ui,db]"                  # install dependencies
```

## Workflow Rules

- **Session-start backlog validation**: Before acting on NEXT_SESSION_PROMPT items, check whether they were already resolved in another session. Review `git log --oneline -15` and inspect the files/functions named in the prompt before starting work. If already resolved, refresh the backlog first.
- **Regression audit timestamp check**: Weekly artifacts under `valuation-results/YYYY-MM-DD(...)/` and `logs/weekly_YYYYMMDD.log` are frozen snapshots of pipeline state at run time. Before diagnosing a "regression bug" from an old artifact, compare its mtime against `git log -- <file>` for the suspect code — stale snapshots masquerade as regressions already fixed upstream.
- **Phase labels accumulate**: 새 "Phase N" 작업 시작 전 `git log` + memory로 실제 shipped 상태 확인. 사용자 프롬프트의 phase 번호가 실제 상태와 다를 수 있음 (예: "Phase 3" 요청 시 이미 Phase 1-3 완료 가능 → 새 축으로 재해석 필요).
- **Codex 협업**: Codex에게 코드/모델 개선을 맡길 때는 `.claude/rules/codex-cross-review.md`의 교차검증 루프를 따를 것. **Codex 주장(diff 0 / pytest 통과 / NUL clean)을 그대로 믿지 말고 독립 재현하라** — 실제로 여러 건이 사실과 달랐다. 특히 **작업 종료 직후 NUL 스캔 필수**(2회 재발, `CLAUDE.md`까지 손상됨).
- **LLM quota budgeting**: Daily quota is 50 calls; each company costs ≤4 (classify + peers_batch + wacc + scenarios). When planning weekly/batch runs, cap `targets × 4 ≤ remaining`. Details + circuit-breaker rules in `.claude/rules/ai.md`.

## Conventions

- English code/comments; Korean user-facing output.
- `engine/` functions must be pure (no IO, no state). `import httpx`, `requests` etc. forbidden.
- IO contract: `ValuationInput` → `ValuationResult` (`schemas/models.py`).
- New YAML profile fields must be Optional with defaults (backward compatibility).
- Pydantic models are immutable inputs: never assign fields directly (`obj.field = x`). Use `obj.model_copy(update={...})` to create modified copies.
- Env vars: `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `DART_API_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `SUPABASE_URL`, `SUPABASE_KEY`.
- Windows `python -c` one-liners that emit Korean fail with `UnicodeEncodeError: 'cp949'`. Prefix shell call with `PYTHONIOENCODING=utf-8` AND rewrap stdout: `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')`. Running as a saved `.py` script usually avoids this; inline `-c` invocation does not.

## Testing

```bash
pytest tests/                    # all
pytest tests/test_engine.py -k "test_sk_wacc"  # individual
```

- Engine pure function tests: fixed input → exact value assertion OK.
- Pipeline E2E tests: range-based validation. Avoid exact-value regression since methodology may vary by company type.
- **`profiles/` is AI-regenerated, not a test fixture**: the weekly pipeline rewrites `profiles/*.yaml` (scenario codes drift Bull/Base/Bear ↔ A/B/C/D), so tests that load from `profiles/` with hardcoded keys break after every run. Fix by moving test-owned YAML into `tests/fixtures/`. Current casualty: `TestScenarioDriverRoundTrip::test_sotp_segment_multiples_differentiate_ev` and `::test_yaml_segment_multiples_round_trip` — deselect with `--deselect tests/test_engine.py::TestScenarioDriverRoundTrip` until fixtures are split.
- **DB repository tests** use a Fake Supabase query builder pattern (`tests/test_backtest_repository.py` — records every chained `.select/.or_/.eq/.upsert/.execute` call, returns fake data). Reuse for new `db/*_repository.py` tests instead of mocking each call site.

## Session Safety (agent/Cowork edits)

- **NEVER run `git checkout -- <file>`, `git show HEAD:<f> > <f>`, `git restore`, `git reset --hard`, or `git stash` on this repo without first confirming the target file is clean.** As of 2026-07-18 the pre-track backlog (T1~T12) is committed through `a60f5b8`, but the remaining dirty files are INTENTIONALLY DEFERRED work awaiting user decisions (T11 profiles YAML, handoff docs, cleanup candidates). Overwriting a dirty file with its HEAD blob permanently destroys uncommitted changes — there is no stash/reflog copy. If a file is corrupted, back it up (`cp <f> /tmp/bak`) and reconstruct; do NOT reach for HEAD.
- **Sandbox git reads MUST be prefixed with `GIT_OPTIONAL_LOCKS=0`** (e.g. `GIT_OPTIONAL_LOCKS=0 git status`). A bare `git status` from the sandbox creates and strands `.git/index.lock` (happened twice). Commits and staging are host/Codex only. Sandbox `git status` also over-reports `M` (CRLF noise; sandbox lacks autocrlf) — host status is authoritative; for content diffs strip CR before `cmp`.
- **After every write/edit to a `.py` file, immediately verify integrity**: `python3 -c "import ast; ast.parse(open('<f>').read())"` + `wc -l`. On this Windows-mounted path, large in-place edits have silently TRUNCATED files mid-line (observed on `valuation_runner.py`, `schemas/models.py`, `output/console_report.py`). Catch truncation on the spot, before it compounds.
- **Prefer atomic rewrites** (read full content → transform in memory → write once) with a post-write `ast.parse` check over incremental in-place edits for large files.
- **Treat recent sandbox reads as provisional on the Windows-mounted workspace.** Before overwriting a file for apparent truncation or a missing imported field, confirm it with a fresh host/local read and recompile. Stale mount views and stale bytecode can present intact files as damaged.
- Working tree is predominantly **CRLF**; keep new/edited files CRLF to avoid whole-file line-ending diffs against the LF blobs in HEAD.
