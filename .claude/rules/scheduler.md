---
paths: ["scheduler/**/*.py", "references/universe.yaml"]
---

# Scheduler Gotchas

## Weekly Pipeline Output

- Weekly pipeline outputs to `valuation-results/YYYY-MM-DD(Month Xth week)/`. `_weekly_summary.json` is the regression-detection entry point — check `discoveries[].companies` (filter/buffer efficacy) and `valuations[].status` (`no_result` = regression per market). Filenames in that folder reveal whether Excel naming convention is actually applied in production runs.

## Run State (run_state.py, K-0F)

- `runs/state.db` (SQLite, gitignored, host-local) is the local source of truth for a weekly run: when the run, each market's discovery, each valuation, the summary file and each delivery started and how it ended. `runs/<run id>/events.jsonl` is exported from it and never read back — when the two differ, the database is right. `summary["local_run_id"]` names the run in this file; it is not the Supabase run id.
- Entry points call `run_weekly_recorded()` (`python -m scheduler.weekly_run`, `cli.py --weekly`). `run_weekly()` called directly records nothing and creates no file, so a new entry point (scheduled job, UI button) that calls `run_weekly()` leaves no local record.
- `python -m scheduler.weekly_run` exit codes: **3** = the run did not start (`RunStateUnavailable`: another writer is alive, or the file is damaged, foreign or of another schema version) — no discovery, no LLM call, no mail; **4** = the run finished but its record is incomplete (`RunStateRecordingFailed`). `cli.py --weekly` does not catch `RunStateError`: traceback and exit code 1. Read the logged reason code before re-running.
- One writer, refused instead of waited for (`WRITER_BUSY`): an OS lock on `runs/state.db.writer.lock` that the OS drops when the process dies. It is not `logs/.weekly_run.lock` (the re-run guard below). On `WRITER_BUSY` look for a surviving python process; do not delete the lock file or the `-wal` / `-shm` files next to the database.
- Fail closed: a damaged, foreign, hard-linked (`DB_ALIASED`) or unknown-version file is refused and left untouched. Do not add code that deletes or recreates it; moving the file aside is a human decision.
- Recovery: the next writer closes every start that has no end (`INTERRUPTED`, reason `NO_END_RECORDED`) before it records anything of its own. An unfinished delivery becomes `UNKNOWN_DELIVERY` and is not sent again — do not add an automatic re-send (the mail or post may already be out).
- A delivery starts only when its start is on record: `step = rec.start("delivery", ...)`, and `None` means do not attempt it. After the first failed state write the recorder is `broken`: later deliveries (Excel upload, email, WordPress, Naver) are not started, discovery and valuation go on, and `errors[]` gets one `RUN_STATE_WRITE_FAILED` entry. A new delivery step follows the same pattern and is added to `_FIXED_TARGETS` first.
- No free text is stored: codes from fixed lists, counts, flags and shape-checked identifiers only (no messages, URLs, paths). Add a new reason code, outcome, target or fact key to the lists in `run_state.py` first — an unlisted value is stored as `<invalid>`, an unknown fact key or target fails the write and breaks the recorder. `tests/test_run_state.py` fails when the mirrored discovery / valuation code lists drift.
- Do not `fork()` while a writer is open (`os.fork`, `multiprocessing` with the fork start method): the module does not fence it. A copy of the writer in another process records nothing and frees nothing. `subprocess` without `preexec_fn` / `pass_fds` is unaffected.
- Read with `read_runs()` / `read_run()` / `read_events()` (read-only connections). Do not open a second writer or a plain `sqlite3.connect()` to look: a writable connection rolls back a hot journal even when it only reads.
- Importing `scheduler.weekly_run` creates neither `logs/` nor `runs/`; `_setup_logging()` creates `logs/`, and only when the root logger has no handlers. Tests keep every database under `tmp_path` (point `weekly_run._RUN_STATE_DB` there), never the repository's `runs/`.
- `_setup_logging()` holds `httpx` / `httpcore` at WARNING because their INFO request lines carry the DART API key in the URL. Do not lower them to INFO for the weekly log.

## Selection Universe (universe.py, K-1B)

- `references/universe.yaml` is the list the target selection (S1) will pick from; `scheduler/universe.py` is its only reader. Nothing calls `load_universe()` yet — wiring it into a run is K-1D. The file says `coverage: pilot` (30 companies): a market-cap rank taken inside it is not an operating value, and `basis` (index membership) is empty because membership was not checked.
- Whole or nothing: `load_universe()` / `parse_universe()` return a frozen `Universe` or raise `UniverseError` with every problem found (12 codes, `PROBLEM_CODES`); no other exception leaves them. Do not add a lenient mode, a partial result or a catch-and-continue around them. A new problem code goes into `PROBLEM_CODES` first.
- Quote `ticker` and `dart_corp_code` in the YAML. Unquoted `000660` is the integer 432 to PyYAML, `00401731` is 132057 and `ON` is a boolean; those are refused (`SCHEMA`), never turned back into text. Do not relax the strict text fields: pydantic would also decode `!!binary` bytes into text and take a YAML `!!set` for a list (an empty set would be an empty universe).
- `sector` (11 fixed names), `is_financial` and `semis_equipment` are written by a person. Do not derive them from `industry_code`: that is the raw KSIC / SIC code kept as a record, and it cannot stand in for them (UNH: `SIC:6324` is financial to `engine.industry_codes.is_financial_code()` and `is_financial: false` here; Samsung Electronics and LG Electronics share `KSIC:264`).
- `Universe.content_hash()` is the sha256 of the validated content, not of the file bytes. Do not replace it with a file hash: the same commit is CRLF on Windows and LF on Linux, and a comment would change it. It names the universe only — the market caps, coverage history and earnings dates of a selection day are not in it.
- A new field is optional with a default; the hash leaves out fields at their default, so files that do not use the new field keep their hash. Aliases, merge keys and repeated keys are refused on purpose: the keys of an entry are exactly the keys written in it.
- Tests build their broken files from `tests/fixtures/universe_valid.yaml`. The test of the tracked data file checks that it is valid, not what it holds (the list changes every quarter). The pinned fixture hash was computed from the plain YAML data, not by calling `content_hash()`; when the fixture changes, recompute it independently the same way.
- What a dependency imports differs by Python version: on 3.11 `import pydantic` pulls in `asyncio` and `ssl`, on 3.14 it does not. The side-effect test imports `ssl`, `yaml` and `pydantic` before it replaces `socket.socket`; keep that order (the first CI run of PR 37 failed without it, and this PC has no Python 3.11 to show it locally).

## Discovery & News Pipeline (weekly_run.py)

- Discovery `_filter_companies()` post-filter runs deterministically after every AI JSON parse — prompt rules alone are insufficient to exclude media outlets (Bloomberg, Yahoo Finance, Electrek). Request 8 candidates from AI; `weekly_run.py` caps final output at `max_per_market`. Filtered slots are not refilled — buffer is the only compensation.
- US EDGAR company identification uses ticker symbol as query (e.g., `TSLA`, `NVDA`) when `market=='US'` and ticker is known (`_run_valuation` in `weekly_run.py`). Korean/localized names (`테슬라`) return no_result — EDGAR search is English-only.
- Google RSS US news queries must be finance-specific (earnings/valuation/IPO/M&A keywords). Generic queries like 'US stock market news' pull sports, obituaries, and unrelated articles through the same RSS feed.
- `_weekly_summary.json` persists `news_count` and `companies[].top_news` only — the raw news array is not stored. Replay-style debugging against last week's news is impossible; regression tests must use synthetic fixtures (`tests/test_top_news_for_company.py`).
- Python `\b` word boundary is ASCII-only — it does NOT fire around CJK characters. Any regex-based news/title matching must split into an ASCII branch (`\b...\b`) and a CJK branch (plain substring), otherwise Korean aliases silently fail to match. `_top_news_for_company` in `weekly_run.py` is the reference pattern.
- `python -m scheduler.weekly_run --dry-run` writes `_weekly_summary.json` with `_debug.companies_with_empty_top_news` — zero-cost validation loop for news-matching/alias changes. Counter ≥50% of total means aliases need expansion (most likely missing CJK branch, company-specific aliases, or market routing bug).
- `_top_news_for_company` length guard is `not t.isdigit() and (_CJK_RE.search(t) or len(t) >= 3)`. The CJK bypass is load-bearing — 2-syllable Korean/Chinese aliases (애플, 메타) must skip the len>=3 rule intended for noisy ASCII tickers (GM/GE). Using len>=3 alone silently drops all 2-syllable CJK aliases.
- Market tag derives from ticker format via `_market_from_ticker` (6-digit numeric → KR, else US), NOT the discovery loop variable. Discovery AI surfaces cross-market companies (US names from KR news and vice versa); loop-variable tagging breaks downstream EDGAR lookup and news matching.
- `top_news` attachment runs AFTER dedup against the combined `all_news` pool (not per-market), using company-specific aliases + ticker. Per-market matching alone misses cross-market mentions (e.g. NVDA in Korean news, Samsung in English news); alias anchoring prevents cross-company leakage.
- Lockfile at `logs/.weekly_run.lock` blocks re-runs within 1 hour to prevent naver+google_rss daily-quota burn. Pass `--force` to override. Stuck background python processes (e.g., PowerShell window closed but process survives) are the main cause of quota exhaustion — always verify `Get-Process python` after closing a shell mid-run.
- `_alert("Discovery", ...)` skips email when empty-news cause is quota exhaustion (`ApiGuard.get_usage_summary()[provider].remaining == 0`). Only fires for unexpected failures (bad API key, network outage). Do NOT revert — alerts flood Gmail at 2 emails × N-runs/day when reverted.

## Scoring (scoring.py)

- `score_companies()` uses per-market max for news-score normalization — KR names match only Korean news tokens; US names match only English tokens. A global max suppresses the lower-volume market's scores. Keep the per-market `market_max` dict in `scoring.py` — do not revert to `max(mention_scores.values())`.

## Naver Blog Poster (naver_poster.py)

- **Naver SE3 file dialog detection**: `_handle_file_dialog_win32` must match `cls == "#32770" AND title ∈ {"열기","Open","파일 열기","파일 선택"}`. OR-logic catches Chrome's "페이지를 복원하시겠습니까?" dialog (same class) and `WM_SETTEXT` sends the file path as a Chrome URL, navigating the browser away.
- **`SetForegroundWindow` Windows restriction**: wrap in try/except — Windows denies focus-stealing from background processes (`pywintypes.error` code 0). Unhandled aborts the entire posting run.
- **SE3 body focus after image insert**: file dialog close leaves focus outside the editor body. Re-focus via `driver.execute_script("var b=document.querySelector('div.se-body, div.__se-body'); if(b) b.focus();")` + ArrowDown/Return before next content write; otherwise subsequent paragraphs are dropped silently.
- **Logo source priority**: DuckDuckGo `icons.duckduckgo.com/ip3/{domain}.ico` > Google Favicon for ambiguous brands. Google returns "Samsung Pay" icon for samsung.com; DuckDuckGo returns the corporate logo. Order in `_download_logo`: Clearbit → DuckDuckGo → Google Favicon.
- **Weekly summary freshness**: `naver_poster.py` reads `_weekly_summary.json` as-is. Code fixes in `weekly_run.py` (EDGAR ticker lookup, top_news attachment, etc.) require regenerating the summary before posting — stale summaries reproduce `no_result` / missing `top_news` regardless of the fix.
