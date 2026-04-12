"""Ticker -> CJK/cross-script alias map for news title matching.

The weekly news pipeline tags companies by ticker but receives news in both
Korean and English. Without aliases, `\\bNVIDIA\\b` cannot match a Korean
title like "엔비디아가 H200 공개". This module supplies the missing link.

Edge cases (debated and confirmed):
- Aliases shorter than 3 chars (e.g. "GM", "MS", "LG") are silently dropped
  by the matcher's `len >= 3` guard in scheduler/weekly_run.py — don't waste
  time adding them here.
- Never add numeric-only aliases (e.g. Korean 6-digit tickers) — they would
  match inside unrelated digit sequences; `not t.isdigit()` guard filters
  them out anyway.
- Same alias for two tickers is allowed but causes cross-match ambiguity;
  avoid if possible.
- Keep rebrand aliases (e.g. "Facebook" for META) since older news still
  uses them.
"""

from __future__ import annotations

# Ticker (upper-case string) -> list of aliases.
CJK_ALIASES: dict[str, list[str]] = {
    # --- US tech ---
    "NVDA": ["엔비디아"],
    "AAPL": ["애플"],
    "TSLA": ["테슬라"],
    "MSFT": ["마이크로소프트", "Microsoft"],
    "AMZN": ["아마존", "Amazon"],
    "GOOGL": ["구글", "알파벳", "Alphabet", "Google"],
    "GOOG": ["구글", "알파벳", "Alphabet", "Google"],
    "META": ["메타", "페이스북", "Facebook"],
    "INTC": ["인텔", "Intel"],
    "AMD": ["에이엠디"],
    "MU": ["마이크론", "Micron"],
    # --- US autos / industrials ---
    "F": ["포드"],
    "GM": ["지엠", "General Motors"],
    # --- KR large-cap (English aliases for US-news coverage) ---
    "005930": ["삼성전자", "Samsung Electronics", "Samsung"],
    "000660": ["SK하이닉스", "SK Hynix"],
    "066570": ["LG전자", "LG Electronics"],
    "051910": ["LG화학", "LG Chem"],
    "005380": ["현대차", "현대자동차", "Hyundai Motor"],
    "000270": ["기아", "Kia"],
    "035420": ["네이버", "NAVER", "Naver"],
    "035720": ["카카오", "Kakao"],
    "003550": ["LG"],
    "012450": ["한화에어로스페이스", "Hanwha Aerospace"],
    "346010": ["에코프로비엠"],
}

assert all(
    isinstance(k, str) for k in CJK_ALIASES
), "CJK_ALIASES ticker keys must be str"


def get_aliases(ticker: str | None) -> list[str]:
    """Return alias list for *ticker*. Empty list on miss (graceful fail)."""
    if not ticker:
        return []
    return CJK_ALIASES.get(ticker.upper(), [])
