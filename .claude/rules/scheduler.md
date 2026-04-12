---
paths: ["scheduler/**/*.py"]
---

# Scheduler Gotchas

## Discovery & News Pipeline (weekly_run.py)

- Discovery `_filter_companies()` post-filter runs deterministically after every AI JSON parse — prompt rules alone are insufficient to exclude media outlets (Bloomberg, Yahoo Finance, Electrek). Request 8 candidates from AI; `weekly_run.py` caps final output at `max_per_market`. Filtered slots are not refilled — buffer is the only compensation.
- US EDGAR company identification uses ticker symbol as query (e.g., `TSLA`, `NVDA`) when `market=='US'` and ticker is known (`_run_valuation` in `weekly_run.py`). Korean/localized names (`테슬라`) return no_result — EDGAR search is English-only.
- Google RSS US news queries must be finance-specific (earnings/valuation/IPO/M&A keywords). Generic queries like 'US stock market news' pull sports, obituaries, and unrelated articles through the same RSS feed.
- `_weekly_summary.json` persists `news_count` and `companies[].top_news` only — the raw news array is not stored. Replay-style debugging against last week's news is impossible; regression tests must use synthetic fixtures (`tests/test_top_news_for_company.py`).
- Python `\b` word boundary is ASCII-only — it does NOT fire around CJK characters. Any regex-based news/title matching must split into an ASCII branch (`\b...\b`) and a CJK branch (plain substring), otherwise Korean aliases silently fail to match. `_top_news_for_company` in `weekly_run.py` is the reference pattern.
- `python -m scheduler.weekly_run --dry-run` writes `_weekly_summary.json` with `_debug.companies_with_empty_top_news` — zero-cost validation loop for news-matching/alias changes. Counter ≥50% of total means aliases need expansion (most likely missing CJK branch, company-specific aliases, or market routing bug).

## Scoring (scoring.py)

- `score_companies()` uses per-market max for news-score normalization — KR names match only Korean news tokens; US names match only English tokens. A global max suppresses the lower-volume market's scores. Keep the per-market `market_max` dict in `scoring.py` — do not revert to `max(mention_scores.values())`.

## Naver Blog Poster (naver_poster.py)

- **Naver SE3 file dialog detection**: `_handle_file_dialog_win32` must match `cls == "#32770" AND title ∈ {"열기","Open","파일 열기","파일 선택"}`. OR-logic catches Chrome's "페이지를 복원하시겠습니까?" dialog (same class) and `WM_SETTEXT` sends the file path as a Chrome URL, navigating the browser away.
- **`SetForegroundWindow` Windows restriction**: wrap in try/except — Windows denies focus-stealing from background processes (`pywintypes.error` code 0). Unhandled aborts the entire posting run.
- **SE3 body focus after image insert**: file dialog close leaves focus outside the editor body. Re-focus via `driver.execute_script("var b=document.querySelector('div.se-body, div.__se-body'); if(b) b.focus();")` + ArrowDown/Return before next content write; otherwise subsequent paragraphs are dropped silently.
- **Logo source priority**: DuckDuckGo `icons.duckduckgo.com/ip3/{domain}.ico` > Google Favicon for ambiguous brands. Google returns "Samsung Pay" icon for samsung.com; DuckDuckGo returns the corporate logo. Order in `_download_logo`: Clearbit → DuckDuckGo → Google Favicon.
- **Weekly summary freshness**: `naver_poster.py` reads `_weekly_summary.json` as-is. Code fixes in `weekly_run.py` (EDGAR ticker lookup, top_news attachment, etc.) require regenerating the summary before posting — stale summaries reproduce `no_result` / missing `top_news` regardless of the fix.
