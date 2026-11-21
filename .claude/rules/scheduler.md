---
paths: ["scheduler/**/*.py"]
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
- **Logo source priority**: DuckDuckGo `icons.duckduckgo.com/ip3/{domain}.ico` > Google Favicon for ambiguous brands. Google returns "Samsung Pay" icon for samsung.com; DuckDuck