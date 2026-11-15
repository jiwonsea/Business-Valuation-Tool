"""Weekly automated news collection + valuation pipeline.

Usage:
    python -m scheduler.weekly_run                                # KR+US, 5 per market
    python -m scheduler.weekly_run --markets KR,US --max-per-market 3
    python -m scheduler.weekly_run --dry-run                      # Discovery only
"""

from __future__ import annotations
import _ssl_fix  # noqa: F401 — must run before any yfinance/curl_cffi import

import argparse
import calendar
import json
import logging
import os
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from itertools import islice
from pathlib import Path

# Load .env so Task Scheduler (which doesn't inherit shell env) gets all API keys
try:
    from dotenv import load_dotenv

    _env_file = Path(__file__).resolve().parent.parent / ".env"
    if _env_file.exists():
        load_dotenv(_env_file, override=False)
except ImportError:
    pass

from .scoring import score_companies
from discovery.cjk_aliases import get_aliases

# Sector/theme names to exclude from per-market selection
# (e.g. '반도체 관련주', 'AI Sector Companies')
_SECTOR_KEYWORDS: tuple[str, ...] = (
    "관련주",
    "관련 기업",
    "관련기업",
    "기업군",
    "관련 종목",
    "관련종목",
    # English sector/group expressions (US market AI outputs)
    # Stored lowercase; matching uses name.lower() for case-insensitive check.
    " sector",
    " companies",
    " firms",
    " industry",
)


def _is_real_company(co: dict) -> bool:
    """Return True if *co* looks like an individual listed company, not a sector/theme group."""
    name_lower = co.get("name", "").lower()
    return not any(kw in name_lower for kw in _SECTOR_KEYWORDS)


def _market_from_ticker(ticker: str | None, fallback: str) -> str:
    """Derive market from ticker format. 6-digit numeric -> KR, else US.

    The discovery loop variable is unreliable — the AI may surface US
    companies from KR news (and vice versa), and the loop previously tagged
    them with the LOOP market, breaking downstream news matching. Ticker
    format is deterministic: matches the prompt rule at
    discovery/discovery_engine.py:307.
    """
    if ticker and ticker.isdigit() and len(ticker) == 6:
        return "KR"
    if ticker and not ticker.isdigit():
        return "US"
    return fallback


_RESULTS_BASE = Path(
    os.environ.get(
        "VALUATION_RESULTS_DIR",
        Path(__file__).resolve().parent.parent / "valuation-results",
    )
)

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

WEEKLY_LLM_BUDGET = int(os.getenv("WEEKLY_LLM_BUDGET", "80"))


def _setup_logging() -> None:
    """Attach console + dated file handlers to the root logger (idempotent).

    Must be called from an entry point (main() / run_weekly()), NOT at import
    time: module-level FileHandler construction created a 0-byte
    logs/weekly_YYYYMMDD.log on every pytest collection (4 test modules import
    this module), while pytest's pre-configured root logger turned basicConfig
    into a no-op so the file was never written. If the root logger already has
    handlers (pytest, embedding app), leave it alone — no file is created.
    """
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                _LOG_DIR / f"weekly_{datetime.now().strftime('%Y%m%d')}.log",
                encoding="utf-8",
                delay=True,
            ),
        ],
    )


logger = logging.getLogger(__name__)


def _alert(phase: str, error: str) -> None:
    """Send error alert via Gmail (best-effort)."""
    try:
        from .email_sender import send_error_alert

        send_error_alert(phase, error)
    except Exception:
        pass


def _draft_publish_state(summary: dict) -> tuple[bool, str]:
    """Return whether draft gating leaves zero externally publishable results."""
    valuations = summary.get("valuations", [])
    publishable_count = sum(
        1 for value in valuations if value.get("status") == "success"
    )
    blocked_entries = [
        value for value in valuations if value.get("status") == "draft_blocked"
    ]
    if not blocked_entries or publishable_count > 0:
        return False, ""
    reasons = "; ".join(
        f"{entry['company']}: {', '.join(entry.get('draft_blockers', [])) or 'draft'}"
        for entry in blocked_entries
    )
    return True, (
        f"published 0 / blocked {len(blocked_entries)}. "
        f"Draft valuation results were retained internally. {reasons}"
    )


# ── Discovery failure contract (K-0B) ────────────────────────────────────────
# Every requested market gets one row in summary["discovery_status"]. A market
# whose final target count is zero always has a reason code there; the old
# summary showed zero companies next to errors: [].

_DISCOVERY_STATUS_CONTRACT = "k0b-1"
_ERROR_TEXT_LIMIT = 600


def _status_row(market: str, result: dict | None = None) -> dict:
    """One market's row for summary["discovery_status"]["markets"]."""
    result = result or {}
    return {
        "market": market,
        "path": result.get("path"),
        "path_fallback": result.get("path_fallback"),
        "news_count": result.get("news_count", 0),
        "candidates_raw": result.get("candidates_raw"),
        "candidates_filtered_out": result.get("candidates_filtered_out"),
        # companies discover() returned for this *requested* market
        "discovered": len(result.get("companies") or []),
        # targets per market *after* ticker re-tagging; companies found through
        # another market's news count here, so discovered - selected is not a
        # drop count
        "selected": 0,
        "selected_after_budget_trim": None,
        "reason_code": None,
        "severity": None,
        "reason_detail": {},
    }


def _set_reason(row: dict, reason_code: str | None, detail: dict | None = None) -> None:
    from discovery.discovery_engine import REASON_SEVERITY

    row["reason_code"] = reason_code
    row["severity"] = REASON_SEVERITY.get(reason_code) if reason_code else None
    row["reason_detail"] = dict(detail or {})


def _reason_error(row: dict, phase: str) -> dict:
    """errors[] entry for a market row that carries a reason code."""
    from discovery.discovery_engine import describe_reason

    return {
        "phase": phase,
        "market": row["market"],
        "reason_code": row["reason_code"],
        "severity": row["severity"],
        "error": describe_reason(row["reason_code"], row["reason_detail"]),
    }


def _zero_selection_message(status: dict) -> str:
    """Final warning for a run that selected nothing: the real reason per market.

    The prefix is kept for log searches. The old text told the reader to check
    NAVER/OpenRouter keys whatever had happened (from 2026-10-03 the actual
    cause was an Anthropic HTTP 400).
    """
    from discovery.discovery_engine import describe_reason, redact_text

    parts = []
    for row in status.get("markets", []):
        code = row.get("reason_code") or "REASON_NOT_REPORTED"
        brief = describe_reason(code, row.get("reason_detail"))
        parts.append(
            f"{row['market']}={code} ({brief})" if brief else f"{row['market']}={code}"
        )
    return redact_text(
        "Discovery returned 0 companies — valuation skipped. Reasons: "
        + "; ".join(parts)
        + ". Details: discovery_status in _weekly_summary.json.",
        limit=2000,
    )


# ── Valuation failure contract (K-0C) ────────────────────────────────────────
# Every valuations[] entry says why it has no result (reason_code) and which
# optional steps fell back (degraded). 59 of 108 past entries were a bare
# "no_result"; the cause had only ever been printed.

_VALUATION_STATUS_CONTRACT = "k0c-1"
VALUATION_EXCEPTION = "VALUATION_EXCEPTION"  # an exception escaped (status failed)
ENRICHMENT_DEGRADED = "ENRICHMENT_DEGRADED"  # a result, with optional steps missing
# What auto_analyze() may report for an empty result under contract k0c-1.
# Plain strings on purpose: this module imports only auto_analyze from
# pipeline.profile_generator, and tests replace that module with a stub that
# has nothing else. tests/test_no_result_failure_contract.py compares the sets.
_ACCEPTED_NO_RESULT_REASONS = frozenset(
    {
        "IDENTITY_NOT_FOUND",
        "IDENTITY_MISMATCH",
        "FINANCIALS_EMPTY",
        "RECONCILIATION_BLOCKED",
        "DRAFT_NO_YEARS",
        "DRAFT_NOT_WRITTEN",
        "REASON_NOT_REPORTED",
    }
)
_DIAG_ITEMS = 20
_REPORTED_LIMIT = 64
_IDENTIFIER_LIMIT = 120
_NUMBER_LIMIT = 1e15
_INVALID = "<invalid>"
# What contract k0c-1 allows in each diagnostic field. Nothing the producer
# hands over reaches the summary, the log or the DB unchecked: only the fields
# named below are read (the producer's mappings are never iterated), a value
# outside its shape becomes "<invalid>", numbers are bounded, and free text is
# masked here again whatever the producer did with it.
_DEGRADED_STEPS = frozenset(
    {
        "industry_metadata",
        "ttm_anchor",
        "beta_observation",
        "ai_module",
        "segments",
        "peers",
        "wacc",
        "news",
        "market_signals",
        "method_selection",
        "scenarios",
        "db_save_call",
    }
)
_PRODUCER_STAGES = frozenset(
    {
        "start",
        "identify",
        "financials",
        "shares",
        "draft_profile",
        "enrichment",
        "valuation",
        "export",
    }
)
_MISMATCH_KINDS = frozenset({"ticker_differs", "resolved_ticker_missing"})
_MARKET_CODES = frozenset({"KR", "US", "JP"})
_LEGAL_STATUSES = frozenset({"상장", "비상장", "listed", "unlisted", "OTC"})
_TICKER_SHAPE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]{0,11}")
_CORP_CODE_SHAPE = re.compile(r"\d{8}")
_CIK_SHAPE = re.compile(r"\d{1,10}")
_NAME_SHAPE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")  # check / exception class
_SEGMENT_SHAPE = re.compile(r"[A-Za-z0-9_.\-]{1,40}")


def _checked(value: object, allowed) -> str | None:
    """A diagnostic identifier: kept only as a plain str of its normal shape.

    None and an empty or blank string are "absent" (None), the same rule as
    pipeline.profile_generator._diag_checked. Anything longer than
    _IDENTIFIER_LIMIT characters is invalid whatever it contains, blanks
    included: telling a long blank string from other text means reading it all.
    """
    if value is None:
        return None
    if type(value) is not str or len(value) > _IDENTIFIER_LIMIT:
        return _INVALID  # len() is O(1): an oversized value is never scanned
    if not value.strip():
        return None
    if isinstance(allowed, frozenset):
        return value if value in allowed else _INVALID
    return value if allowed.fullmatch(value) else _INVALID


def _selection_identifier(value: object) -> str | None:
    """A selection-stage identifier (company name, selected ticker), copied.

    The summary already holds these verbatim under valuations[], and masking
    would mangle real names ("SK-Hynix" -> "sk-***"). One line, bounded.
    """
    if value is None:
        return None
    try:
        if type(value) is str:
            value = value[: _IDENTIFIER_LIMIT * 8]  # bound the work, then fold
        elif _number(value) is None:
            return _type_name(value)  # never render an arbitrary object
        return " ".join(str(value).split())[:_IDENTIFIER_LIMIT]
    except Exception:
        return None


def _number(value: object) -> float | int | None:
    """A finite number of modest size, else None (a huge int cannot be printed).

    Identity checks on the type and two comparisons with a float: no abs() (it
    copies a negative int) and no ==. NaN fails both comparisons.
    """
    if type(value) is not int and type(value) is not float:
        return None
    return value if -_NUMBER_LIMIT <= value <= _NUMBER_LIMIT else None


_TYPE_LABELS = (
    (list, "<list>"),
    (tuple, "<tuple>"),
    (dict, "<dict>"),
    (set, "<set>"),
    (frozenset, "<frozenset>"),
    (bytes, "<bytes>"),
    (bool, "<bool>"),
    (int, "<int>"),
    (float, "<float>"),
)


def _type_name(value: object) -> str:
    """A fixed label for what a value is; never the type's own name.

    A class can be named anything (a secret, a megabyte of text, a line
    break), so its name is not used: the built-in containers and scalars get
    a label from the table above and everything else is "<object>". The
    lookup is by identity, so nothing the class defines (a metaclass __hash__
    or __eq__) runs.
    """
    kind = type(value)
    for known, label in _TYPE_LABELS:
        if kind is known:
            return label
    return "<object>"


def _reported_text(value: object) -> str:
    """What came in place of a reason code, in bounded time and space.

    A str is masked (redact_text() looks at its first 4,000 characters only),
    a modest number is printed, and anything else gets a fixed label from
    _type_name(): str() of a large container would build the whole text
    before cutting it, and a class name is as untrusted as any other text.
    """
    if type(value) is str:
        return _free_text(value, _REPORTED_LIMIT) or ""
    if _number(value) is not None:
        return str(value)
    return _type_name(value)


def _free_text(value: object, limit: int = _ERROR_TEXT_LIMIT) -> str | None:
    """Free text from the producer: masked, one line, cut. Non-str -> None."""
    if type(value) is not str:
        return None
    from discovery.discovery_engine import redact_text

    return redact_text(value, limit=limit)


def _error_detail(exc: BaseException) -> dict:
    """describe_error() with every field held to this contract's shapes.

    The class name of an exception is as untrusted as its message and a
    status code can be any int; describe_error() reports both as they are.
    Here: error_type must look like a class name, http_status must be a modest
    number, and the remaining text fields are masked (again).
    """
    from discovery.discovery_engine import describe_error

    def one(described: object) -> dict:
        if type(described) is not dict:
            return {}
        return {
            "provider": _free_text(described.get("provider"), _REPORTED_LIMIT),
            "http_status": _number(described.get("http_status")),
            "error_type": _checked(described.get("error_type"), _NAME_SHAPE),
            "api_error_type": _free_text(
                described.get("api_error_type"), _REPORTED_LIMIT
            ),
            "message": _free_text(described.get("message")),
        }

    try:
        described = describe_error(exc)
        detail = one(described)
        causes = described.get("caused_by")
        detail["caused_by"] = (
            [one(cause) for cause in islice(causes, 3)] if type(causes) is list else []
        )
        return detail
    except Exception:
        return {}


def _reason_detail(raw: object, query: object, ticker: object) -> dict:
    """reason_detail as contract k0c-1 defines it; {} for anything malformed.

    ``query`` and ``expected_ticker`` are not taken from the producer: this
    module made the selection and passed it on, so it writes its own values.
    """
    try:
        if type(raw) is not dict:
            return {}
        detail: dict = {}
        if "kind" in raw:
            detail["kind"] = _checked(raw["kind"], _MISMATCH_KINDS)
        if "query" in raw:
            detail["query"] = _selection_identifier(query)
        if "market_hint" in raw:
            detail["market_hint"] = _checked(raw["market_hint"], _MARKET_CODES)
        if "expected_ticker" in raw:
            detail["expected_ticker"] = _selection_identifier(ticker)
        if "resolved_ticker" in raw:
            detail["resolved_ticker"] = _checked(raw["resolved_ticker"], _TICKER_SHAPE)
        if "resolved_market" in raw:
            detail["resolved_market"] = _checked(raw["resolved_market"], _MARKET_CODES)
        if "resolved_corp_code" in raw:
            detail["resolved_corp_code"] = _checked(
                raw["resolved_corp_code"], _CORP_CODE_SHAPE
            )
        if "resolved_cik" in raw:
            detail["resolved_cik"] = _checked(raw["resolved_cik"], _CIK_SHAPE)
        if "legal_status" in raw:
            detail["legal_status"] = _checked(raw["legal_status"], _LEGAL_STATUSES)
        for flag in ("has_corp_code", "has_cik"):
            if flag in raw:
                detail[flag] = raw[flag] if type(raw[flag]) is bool else None
        if type(raw.get("checks")) is list:
            detail["checks"] = [
                {
                    "check": _checked(item.get("check"), _NAME_SHAPE),
                    "rel_diff_pct": _number(item.get("rel_diff_pct")),
                    "message": _free_text(item.get("message")),
                }
                for item in islice(raw["checks"], _DIAG_ITEMS)
                if type(item) is dict
            ]
        if "reported" in raw:
            detail["reported"] = _free_text(raw["reported"], _REPORTED_LIMIT)
        return detail
    except Exception:
        return {}


def _degraded_steps(diagnostics: object) -> list[dict]:
    """The producer's degraded list as contract k0c-1 defines it; [] if malformed."""
    try:
        raw = diagnostics.get("degraded") if type(diagnostics) is dict else None
        if type(raw) is not list:
            return []
        steps = []
        for item in islice(raw, _DIAG_ITEMS):
            if type(item) is not dict:
                continue
            step: dict = {
                "step": _checked(item.get("step"), _DEGRADED_STEPS) or _INVALID
            }
            if "error_type" in item:
                step["error_type"] = _checked(item["error_type"], _NAME_SHAPE)
            if "message" in item:
                step["message"] = _free_text(item["message"])
            if type(item.get("segments")) is list:
                step["segments"] = [
                    code
                    for code in islice(item["segments"], _DIAG_ITEMS)
                    if type(code) is str and _SEGMENT_SHAPE.fullmatch(code)
                ]
            steps.append(step)
        return steps
    except Exception:
        return []


def _no_result_reason(
    diagnostics: object, query: object, ticker: object
) -> tuple[str, dict]:
    """(reason_code, reason_detail) for an empty result. Always a reason.

    A missing, malformed or unknown code becomes REASON_NOT_REPORTED and what
    was received is shown by _reported_text() (it is not an identifier).
    """
    from discovery.discovery_engine import REASON_NOT_REPORTED

    shown = None
    try:
        reported = diagnostics.get("reason_code") if type(diagnostics) is dict else None
        if (
            type(reported) is str
            and len(reported) <= _REPORTED_LIMIT
            and reported in _ACCEPTED_NO_RESULT_REASONS
        ):
            detail = _reason_detail(diagnostics.get("reason_detail"), query, ticker)
            return reported, detail
        if reported is not None:
            shown = _reported_text(reported)
    except Exception:
        shown = None
    return REASON_NOT_REPORTED, {"reported": shown}


def _valuation_diagnostics(
    reason_code: str | None, reason_detail: dict, degraded: list[dict]
) -> dict:
    """The keys K-0C adds to every valuations[] entry."""
    return {
        "reason_code": reason_code,
        "severity": "failure" if reason_code else None,
        "reason_detail": reason_detail,
        "degraded": list(dict.fromkeys(step["step"] for step in degraded)),
        "degraded_detail": degraded,
    }


def _reason_text(reason_code: str | None, detail: dict | None) -> str:
    """One line for errors[] and the log, assembled field by field.

    ``detail`` went through _reason_detail(): its free text is masked and its
    identifiers are checked, so the finished line is not masked again (that
    would turn a name such as "SK-Hynix" into "sk-***").
    """
    try:
        parts = []
        for key, value in (detail or {}).items():
            if type(value) is list:
                value = "/".join(str(item.get("check")) for item in value)
            parts.append(f"{key}={value}")
        text = f"{reason_code}: {', '.join(parts)}" if parts else f"{reason_code}"
        return " ".join(text.split())[:_ERROR_TEXT_LIMIT]
    except Exception:
        return f"{reason_code}"


def _valuation_error(entry: dict) -> dict | None:
    """errors[] entry for one valuations[] entry; at most one each.

    The terminal reason (no_result / failed) wins. A result whose optional
    steps fell back gets ENRICHMENT_DEGRADED. A clean result gets nothing.
    """
    status = entry.get("status")
    error = {
        "phase": "valuation",
        "company": entry.get("company"),
        "ticker": entry.get("ticker"),
        "market": entry.get("market"),
    }
    detail = entry.get("reason_detail") or {}
    if status == "failed":
        error.update(
            reason_code=entry.get("reason_code"),
            severity=entry.get("severity"),
            error=entry.get("error", ""),
            error_type=detail.get("error_type"),
            stage=detail.get("stage"),
        )
        return error
    if status == "no_result":
        error.update(
            reason_code=entry.get("reason_code"),
            severity=entry.get("severity"),
            error=_reason_text(entry.get("reason_code"), detail),
        )
        return error
    if entry.get("degraded"):
        error.update(
            reason_code=ENRICHMENT_DEGRADED,
            severity="degraded",
            error="steps=" + ", ".join(entry["degraded"]),
        )
        return error
    return None


def _week_number(dt: datetime) -> int:
    """Calculate which week of the month the date falls in."""
    first_day = dt.replace(day=1)
    return (dt.day + first_day.weekday()) // 7 + 1


def _ordinal(n: int) -> str:
    """Return ordinal string: 1st, 2nd, 3rd, 4th, 5th."""
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]}"


# CJK Unified Ideographs + Hangul Syllables — word boundaries (\b) don't apply
_CJK_RE = re.compile(r"[\u3000-\u9fff\uac00-\ud7af]")


def _alias_pattern(aliases: list[str]) -> re.Pattern | None:
    """Build one regex combining ASCII (\\b-anchored) and CJK (substring) aliases.

    Returns None if no usable aliases (all too short or empty).
    """
    ascii_terms = [a for a in aliases if a and not _CJK_RE.search(a)]
    cjk_terms = [a for a in aliases if a and _CJK_RE.search(a)]
    parts: list[str] = []
    if ascii_terms:
        parts.append(r"\b(?:" + "|".join(re.escape(a) for a in ascii_terms) + r")\b")
    if cjk_terms:
        parts.append("(?:" + "|".join(re.escape(a) for a in cjk_terms) + ")")
    if not parts:
        return None
    return re.compile("|".join(parts), re.IGNORECASE)


def _top_news_for_company(
    company_name: str,
    news: list[dict],
    max_items: int = 3,
    aliases: tuple[str, ...] | list[str] = (),
) -> list[dict]:
    """Return up to max_items news articles whose title contains the company
    name or one of its aliases (e.g. ticker symbol).

    ASCII aliases match on word boundaries; CJK aliases match as substrings
    (Korean/CJK names are multi-syllable and don't sub-match in practice).
    Returns an empty list when nothing matches — do NOT fall back to generic
    top-N news, which caused cross-company contamination in earlier versions.
    """
    # len>=3 drops noisy 2-char tickers (GM, GE); isdigit drops KR numeric codes
    # (005930) that collide with any article containing the digit string.
    # CJK aliases bypass the length guard — 2-syllable Korean/Chinese words
    # (애플, 메타) are already meaningful and don't have the collision risk
    # that short ASCII tickers do.
    terms = [
        t
        for t in ([company_name] + list(aliases))
        if t and not t.isdigit() and (_CJK_RE.search(t) or len(t) >= 3)
    ]
    pattern = _alias_pattern(terms)
    if pattern is None:
        return []

    matched: list[dict] = []
    for n in news:
        title = n.get("title") or ""
        url = n.get("link") or n.get("url") or ""
        if not (title and url):
            continue
        norm_title = unicodedata.normalize("NFKC", title).casefold()
        if pattern.search(norm_title):
            matched.append({"title": title, "url": url})
            if len(matched) >= max_items:
                break
    return matched


def _week_folder(dt: datetime) -> str:
    """Folder name: '2026-03-31(Mar 5th week)' (local display)."""
    wn = _week_number(dt)
    mon = calendar.month_abbr[dt.month]
    return f"{dt.year}-{dt.month:02d}-{dt.day:02d}({mon} {_ordinal(wn)} week)"


def _storage_folder(week_folder_name: str) -> str:
    """Sanitize folder name for Supabase Storage keys.

    Supabase Storage rejects keys containing parentheses or spaces.
    '2026-03-31(Mar 5th week)' -> '2026-03-31_Mar-5th-week'
    """
    return week_folder_name.replace("(", "_").replace(")", "").replace(" ", "-")


def _week_label(dt: datetime) -> str:
    """Human-readable label: 'Mar 5th week (3/31)'."""
    wn = _week_number(dt)
    mon = calendar.month_abbr[dt.month]
    return f"{mon} {_ordinal(wn)} week ({dt.month}/{dt.day})"


def run_weekly(
    markets: list[str] | None = None,
    max_per_market: int = 5,
    dry_run: bool = False,
) -> dict:
    """Execute weekly Discovery + valuation pipeline.

    1. Per-market news collection + AI analysis (DiscoveryEngine)
    2. Company importance scoring (news frequency + market cap)
    3. Auto-valuation for top N per market (auto_analyze)
    4. Upload Excel to Supabase Storage
    5. Save JSON summary for downstream delivery (Gamma + Gmail)
    6. DB save

    Returns:
        {"run_date", "markets", "discoveries", "scored_companies", "valuations", "errors",
         "discovery_status"}

    Failure contract (K-0B): summary["discovery_status"]["markets"] has one row
    per requested market, in request order. errors[] gets one entry per market
    whose discover() reported a reason or raised (whatever was selected in the
    end), plus one SELECTION_EMPTY entry per market whose discovery was fine
    but whose final target count is zero.

    Failure contract (K-0C): every valuations[] entry carries reason_code,
    severity, reason_detail, degraded and degraded_detail. A no_result or
    failed entry always has a reason code; errors[] gets at most one entry per
    valuation (its terminal reason, else ENRICHMENT_DEGRADED when optional
    steps fell back). summary["valuation_status"] is the roll-up.
    """
    from discovery.discovery_engine import (
        DISCOVERY_EXCEPTION,
        NEWS_EMPTY,
        REASON_NOT_REPORTED,
        SELECTION_EMPTY,
        DiscoveryEngine,
        describe_error,
        redact_text,
    )

    _setup_logging()
    markets = markets or ["KR", "US"]
    start = time.time()
    now = datetime.now()

    summary: dict = {
        "run_date": now.isoformat(),
        "label": _week_label(now),
        "markets": markets,
        "discoveries": [],
        "scored_companies": [],
        "valuations": [],
        "errors": [],
    }

    # Create run record in DB
    run_id = _save_run_start(markets)

    # ── Phase 1: Per-market news collection + AI analysis (parallel) ──
    engine = DiscoveryEngine()
    all_companies: list[dict] = []
    # request market of each entry in all_companies (parallel list: the company
    # dicts are shared with summary["discoveries"] and stay free of bookkeeping)
    all_company_sources: list[str] = []
    all_news: list[dict] = []
    total_news = 0
    status_rows: dict[str, dict] = {}
    raised_markets: set[str] = set()  # discover() raised; errors[] entry already made

    def _discover_market(
        market: str,
    ) -> tuple[str, dict | None, Exception | None]:
        try:
            return market, engine.discover(market=market), None
        except Exception as e:
            return market, None, e

    with ThreadPoolExecutor(max_workers=len(markets)) as pool:
        futures = {pool.submit(_discover_market, m): m for m in markets}
        for fut in as_completed(futures):
            market, result, exc = fut.result()
            # `is not None`, not truthiness of str(exc): an exception with an
            # empty message used to fall through to result.get() and crash.
            if exc is not None:
                error = redact_text(exc, limit=_ERROR_TEXT_LIMIT)
                logger.error("Discovery 실패 [%s]: %s", market, error)
                row = _status_row(market)
                _set_reason(
                    row,
                    DISCOVERY_EXCEPTION,
                    {"stage": "discover", **describe_error(exc)},
                )
                status_rows[market] = row
                raised_markets.add(market)
                summary["errors"].append(
                    {
                        "phase": "discovery",
                        "market": market,
                        "error": error,
                        "reason_code": DISCOVERY_EXCEPTION,
                        "severity": row["severity"],
                        "error_type": type(exc).__name__,
                    }
                )
                continue
            news_count = result.get("news_count", 0)
            total_news += news_count
            market_news = result.get("news", [])
            all_news.extend(market_news)
            quota_exhausted: bool | None = None
            news_provider = "naver" if market == "KR" else "google_rss"
            if not market_news:
                # Distinguish quota exhaustion (expected, don't alert) from real failures.
                # Silent quota alerts used to flood Gmail when the pipeline ran repeatedly
                # within a day; see .claude/rules/scheduler.md.
                from pipeline.api_guard import ApiGuard

                provider = news_provider
                usage = ApiGuard.get().get_usage_summary().get(provider, {})
                quota_exhausted = usage.get("remaining", -1) == 0
                # Facts only. The collector returns [] for a missing key, a
                # guard block and an HTTP error alike, so the cause is unknown
                # here and the text must not point at one.
                msg = (
                    f"[{market}] 뉴스 수집 결과 0건 — provider={provider}, "
                    f"quota_exhausted={quota_exhausted} "
                    "(수집기가 세부 원인을 보고하지 않음)"
                )
                logger.warning(msg)
                if quota_exhausted:
                    logger.info(
                        "[%s] skipping alert — %s daily quota exhausted (%d/%d)",
                        market,
                        provider,
                        usage.get("calls", 0),
                        usage.get("limit", 0),
                    )
                else:
                    _alert("Discovery", msg)
            companies_in_market = result.get("companies", [])
            for co in companies_in_market:
                ticker_str = str(co.get("ticker") or "")
                co["market"] = _market_from_ticker(ticker_str, fallback=market)
                # Attach top-3 relevant news articles (title + link) for blog output
                aliases_list: list[str] = []
                if ticker_str and not ticker_str.isdigit():
                    aliases_list.append(ticker_str)
                aliases_list.extend(get_aliases(ticker_str))
                co["_top_news_aliases"] = aliases_list  # stash for phase-2 rerun
                all_companies.append(co)
                all_company_sources.append(market)

            # Reason reported by discover(). An empty list without one is a
            # contract breach by the producer and is recorded as such.
            row = _status_row(market, result)
            if not companies_in_market:
                reason_code = result.get("reason_code") or REASON_NOT_REPORTED
                reason_detail = dict(result.get("reason_detail") or {})
                if reason_code == NEWS_EMPTY:
                    reason_detail.setdefault("provider", news_provider)
                    reason_detail["quota_exhausted"] = bool(quota_exhausted)
                _set_reason(row, reason_code, reason_detail)
                logger.warning(
                    "[%s] discovery returned 0 companies: %s", market, reason_code
                )
            status_rows[market] = row
            summary["discoveries"].append(
                {
                    "market": market,
                    "news_count": news_count,
                    "companies": companies_in_market,
                    "reason_code": row["reason_code"],
                    "path": row["path"],
                }
            )

    # ── Phase 2: Deduplication + importance scoring ──
    seen_names: set[str] = set()
    unique_companies: list[dict] = []
    # per request market: why a discovered company did not reach scoring under
    # that market (explains SELECTION_EMPTY; the selection itself is unchanged)
    dropped_empty_name: dict[str, int] = {}
    dropped_duplicate_name: dict[str, int] = {}
    retagged_to_other_market: dict[str, int] = {}
    for co, source_market in zip(all_companies, all_company_sources):
        name = co.get("name", "")
        if name and name not in seen_names:
            seen_names.add(name)
            unique_companies.append(co)
            if co.get("market") != source_market:
                retagged_to_other_market[source_market] = (
                    retagged_to_other_market.get(source_market, 0) + 1
                )
        elif not name:
            dropped_empty_name[source_market] = (
                dropped_empty_name.get(source_market, 0) + 1
            )
        else:
            dropped_duplicate_name[source_market] = (
                dropped_duplicate_name.get(source_market, 0) + 1
            )

    # Attach top_news using combined news pool + CJK aliases. Matching against
    # all_news (not per-market) covers US companies mentioned in KR news and
    # vice versa — name/alias anchoring prevents cross-company leakage.
    for co in unique_companies:
        co["top_news"] = _top_news_for_company(
            co.get("name", ""),
            all_news,
            max_items=3,
            aliases=co.pop("_top_news_aliases", []),
        )

    scored = score_companies(unique_companies, all_news)
    summary["scored_companies"] = scored
    if os.environ.get("DUMP_NEWS_TITLES"):
        summary["_debug_news_titles"] = [n.get("title", "") for n in all_news]

    # ── Per-market selection: top N per market ──
    targets: list[dict] = []

    for market in markets:
        market_companies = [
            c for c in scored if c.get("market") == market and _is_real_company(c)
        ]
        actual = market_companies[:max_per_market]
        targets.extend(actual)
        if len(actual) < max_per_market:
            logger.info(
                "%s: %d/%d companies available (below target)",
                market,
                len(actual),
                max_per_market,
            )

        # Failure contract: record what selection did for this market.
        row = status_rows.get(market)
        if row is None:  # defensive: every market has an exception or a result
            row = _status_row(market)
            _set_reason(row, REASON_NOT_REPORTED)
            status_rows[market] = row
        row["selected"] = len(actual)
        if row["reason_code"] is not None:
            # discover() reported a reason (or returned nothing without one).
            # It is kept whatever was selected: companies re-tagged from another
            # market's news can fill this market and must not erase the failure.
            if market not in raised_markets:
                summary["errors"].append(_reason_error(row, "discovery"))
        elif not actual:
            tagged = sum(1 for c in scored if c.get("market") == market)
            if market_companies:
                kind = "limit"  # eligible companies existed; the slice left none
            elif tagged:
                kind = "sector_like_excluded"
            else:
                kind = "no_company_tagged_to_market"
            _set_reason(
                row,
                SELECTION_EMPTY,
                {
                    "kind": kind,
                    "discovered": row["discovered"],
                    "dropped_empty_name": dropped_empty_name.get(market, 0),
                    "dropped_duplicate_name": dropped_duplicate_name.get(market, 0),
                    "retagged_to_other_market": retagged_to_other_market.get(market, 0),
                    "tagged_to_market": tagged,
                    "sector_like_excluded": tagged - len(market_companies),
                    "max_per_market": max_per_market,
                },
            )
            summary["errors"].append(_reason_error(row, "selection"))

    discovery_status: dict = {
        "contract": _DISCOVERY_STATUS_CONTRACT,
        "targets_selected": len(targets),
        # set after the LLM-budget trim; a dry run does not trim
        "targets_after_budget_trim": None,
        "zero_selection": not targets,
        "markets": [status_rows[m] for m in markets],
    }
    summary["discovery_status"] = discovery_status

    # ── Print results ──
    _print_summary_header(summary["label"], total_news, scored)

    # Output folder setup — runs for both dry-run and full paths so the
    # _weekly_summary.json artifact (including _debug counters) is always saved.
    week_folder_name = _week_folder(now)
    week_dir = _RESULTS_BASE / week_folder_name
    week_dir.mkdir(parents=True, exist_ok=True)
    summary["folder_name"] = week_folder_name
    summary["week_dir"] = str(week_dir)

    if dry_run:
        logger.info("Dry run — skipping valuation.")
        if not targets:
            logger.warning(_zero_selection_message(discovery_status))
        _save_json_summary(summary, week_dir)
        _finalize_run(run_id, summary, time.time() - start, total_news, scored)
        return summary

    # ── Cost estimation before valuation ──
    from pipeline.api_guard import ApiGuard, estimate_weekly_cost

    estimate = estimate_weekly_cost(markets, len(targets))
    total_est = sum(estimate["estimated_api_calls"].values())
    logger.info(
        "Estimated API calls: %d, LLM calls: %d, LLM cost: $%.2f",
        total_est,
        estimate["estimated_llm_calls"],
        estimate["estimated_llm_cost_usd"],
    )
    low_quota = {
        k: v
        for k, v in estimate["remaining_quota"].items()
        if 0 <= v < estimate["estimated_api_calls"].get(k, 0)
    }
    if low_quota:
        logger.warning("Insufficient quota for: %s", low_quota)

    # ── Quota safety net: trim targets to fit LLM quota ──
    # If OpenRouter is active, sum both budgets (Anthropic is the fallback).
    # If Anthropic only, use its budget alone.
    if os.getenv("OPENROUTER_API_KEY"):
        # Only count Anthropic budget if the fallback key is actually configured
        anthropic_bonus = (
            estimate["remaining_quota"].get("anthropic", 0)
            if os.getenv("ANTHROPIC_API_KEY")
            else 0
        )
        llm_budget = estimate["remaining_quota"].get("openrouter", 0) + anthropic_bonus
    else:
        llm_budget = estimate["remaining_quota"].get("anthropic", 50)
    calls_per_company = (
        6  # classify + peers_batch + wacc + scenarios + news_summary + profile_gen
    )
    effective_budget = max(llm_budget, WEEKLY_LLM_BUDGET)
    max_affordable = max(effective_budget // calls_per_company, 1)
    if len(targets) > max_affordable:
        logger.warning(
            "Trimming targets from %d to %d to fit LLM quota "
            "(%d remaining, weekly budget=%d)",
            len(targets),
            max_affordable,
            llm_budget,
            WEEKLY_LLM_BUDGET,
        )
        targets = targets[:max_affordable]

    # Failure contract: per-market counts after the trim. A market that had
    # targets and lost all of them to the trim gets a reason; the trim itself
    # is unchanged.
    for row in discovery_status["markets"]:
        row["selected_after_budget_trim"] = sum(
            1 for c in targets if c.get("market") == row["market"]
        )
        if (
            row["selected"] > 0
            and row["selected_after_budget_trim"] == 0
            and row["reason_code"] is None
        ):
            _set_reason(
                row,
                SELECTION_EMPTY,
                {
                    "kind": "budget_trim",
                    "selected": row["selected"],
                    "selected_after_budget_trim": 0,
                    "max_affordable": max_affordable,
                },
            )
            summary["errors"].append(_reason_error(row, "selection"))
    discovery_status["targets_after_budget_trim"] = len(targets)
    discovery_status["zero_selection"] = not targets

    # ── Phase 3: Auto-valuation for top companies ──
    from pipeline.profile_generator import auto_analyze

    logger.info("Excel output folder: %s", week_dir)

    def _run_valuation(co: dict) -> dict:
        name = co.get("name", "")
        ticker = co.get("ticker")
        reason = co.get("reason", "")
        # For US companies discovered with Korean names, EDGAR cannot resolve them.
        # Use the ticker symbol (e.g. "TSLA") as the query instead.
        market = co.get("market", "")
        ticker_str = str(ticker).strip() if ticker else ""
        if market == "US" and ticker_str:
            query = ticker_str
        else:
            query = name
        # K-0C: a fresh dict per company; auto_analyze() fills in why it has no
        # result and which optional steps fell back. Never shared across threads.
        diagnostics: dict = {}
        returned = False
        try:
            logger.info(
                "Valuation start: %s %s (query=%r)", co.get("stars", ""), name, query
            )
            analyze_result = auto_analyze(
                query,
                output_dir=str(week_dir),
                scored_data=co,
                diagnostics=diagnostics,
            )
            returned = True
            degraded = _degraded_steps(diagnostics)
            if analyze_result:
                vr = getattr(analyze_result, "validation_report", None)
                valuation_result = getattr(analyze_result, "result", None)
                is_draft = bool(valuation_result is not None and valuation_result.draft)
                return {
                    "company": name,
                    "ticker": ticker,
                    "reason": reason,
                    "market": co.get("market", ""),
                    "status": "draft_blocked" if is_draft else "success",
                    "draft": is_draft,
                    "quality_grade": (
                        valuation_result.quality.grade
                        if valuation_result is not None
                        and valuation_result.quality is not None
                        else None
                    ),
                    "draft_blockers": (
                        list(valuation_result.investability_blockers)
                        if valuation_result is not None
                        else []
                    ),
                    "excel_path": analyze_result.excel_path,
                    "summary_md": analyze_result.summary_md,
                    "market_cap_usd": co.get("market_cap_usd"),
                    "scenario_validation": getattr(vr, "status", None),
                    "scenario_validation_codes": (
                        [e.code for e in vr.errors] if vr is not None else []
                    ),
                    **_valuation_diagnostics(None, {}, degraded),
                }
            reason_code, reason_detail = _no_result_reason(diagnostics, query, ticker)
            return {
                "company": name,
                "ticker": ticker,
                "reason": reason,
                "market": co.get("market", ""),
                "status": "no_result",
                **_valuation_diagnostics(reason_code, reason_detail, degraded),
            }
        except Exception as e:
            # redact_text() never raises; str(e) did for an exception whose
            # __str__ fails and took the whole run down from this clause.
            error = redact_text(e, limit=_ERROR_TEXT_LIMIT)
            logger.error("Valuation failed [%s]: %s", name, error)
            if returned:
                stage = "result"  # raised here, while reading what came back
            else:
                stage = diagnostics.get("stage")
                if type(stage) is not str or stage not in _PRODUCER_STAGES:
                    stage = "start"
            return {
                "company": name,
                "ticker": ticker,
                "reason": reason,
                "market": co.get("market", ""),
                "status": "failed",
                "error": error,
                **_valuation_diagnostics(
                    VALUATION_EXCEPTION,
                    {"stage": stage, **_error_detail(e)},
                    _degraded_steps(diagnostics),
                ),
            }

    if not targets:
        msg = _zero_selection_message(discovery_status)
        logger.warning(msg)
        _alert("Valuation", msg)
    _summary_lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(min(len(targets), 3), 1)) as pool:
        futures = {pool.submit(_run_valuation, co): co for co in targets}
        for fut in as_completed(futures):
            entry = fut.result()
            try:
                error_entry = _valuation_error(entry)
            except Exception:
                # Describing an outcome must never end the run.
                error_entry = {
                    "phase": "valuation",
                    "company": entry.get("company"),
                    "reason_code": entry.get("reason_code"),
                    "severity": entry.get("severity"),
                    "error": "",
                }
            if entry.get("status") == "no_result":
                logger.warning(
                    "Valuation no_result [%s]: %s",
                    entry.get("company"),
                    (error_entry or {}).get("error"),
                )
            elif entry.get("degraded"):
                logger.warning(
                    "Valuation degraded [%s]: steps=%s",
                    entry["company"],
                    ", ".join(entry["degraded"]),
                )
            with _summary_lock:
                summary["valuations"].append(entry)
                if error_entry is not None:
                    summary["errors"].append(error_entry)

    # ── Phase 3.5: Upload Excel to Supabase Storage ──
    _upload_excels_to_storage(summary, _storage_folder(week_folder_name))

    # ── Phase 3.6: Save JSON summary for delivery agent ──
    _save_json_summary(summary, week_dir)

    all_draft_blocked, draft_block_message = _draft_publish_state(summary)
    if all_draft_blocked:
        logger.error("Weekly publishing blocked: %s", draft_block_message)
        _alert("Draft Gate", draft_block_message)

    # ── Phase 5: Send email notification (best-effort) ──
    if not all_draft_blocked:
        try:
            from .email_sender import send_weekly_email

            send_weekly_email(summary)
        except Exception as e:
            logger.warning("Email notification failed: %s", e)

    # ── Phase 6a: WordPress posting (US only, best-effort) ──
    if not all_draft_blocked:
        try:
            from .wp_poster import post_to_wordpress

            wp_url = post_to_wordpress(summary)
            if wp_url:
                summary["wp_url"] = wp_url
        except Exception as e:
            logger.warning("WordPress posting failed: %s", e)
            _alert("WordPress", str(e))

    # ── Phase 6b: Naver Blog posting (KR+US, best-effort) ──
    if not all_draft_blocked:
        try:
            from .naver_poster import post_to_naver

            naver_url = post_to_naver(summary)
            if naver_url:
                summary["naver_url"] = naver_url
        except Exception as e:
            logger.warning("Naver Blog posting failed: %s", e)
            _alert("Naver Blog", str(e))

    # ── Phase 7: YouTube video creation + upload (disabled) ──
    # TODO: Re-enable when YouTube pipeline is ready
    # try:
    #     from .video_creator import create_weekly_video
    #     from .youtube_uploader import upload_to_youtube
    #     video_path = create_weekly_video(summary, output_dir=week_dir)
    #     if video_path:
    #         yt_url = upload_to_youtube(video_path, summary)
    #         if yt_url:
    #             summary["youtube_url"] = yt_url
    # except Exception as e:
    #     logger.warning("YouTube pipeline failed: %s", e)
    #     _alert("YouTube", str(e))

    # ── Phase 8: Completion ──
    duration = time.time() - start
    _finalize_run(run_id, summary, duration, total_news, scored)
    _print_completion(summary, duration, week_dir)

    # Log API usage summary
    try:
        usage = ApiGuard.get().get_usage_summary()
        active = {
            k: v for k, v in usage.items() if v["calls"] > 0 or v["cache_hits"] > 0
        }
        if active:
            logger.info("API usage summary: %s", active)
    except Exception:
        pass

    return summary


def _excel_date_tag(week_folder_name: str) -> str:
    """Extract MM-DD date tag from week folder name.

    e.g. '2026-04-12(Apr 3rd week)' → '04-12'
    """
    import re as _re

    m = _re.match(r"\d{4}-(\d{2})-(\d{2})", week_folder_name)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return ""


def _to_camel(name: str) -> str:
    """Convert an English name to CamelCase suitable for filenames.

    'SAMSUNG ELECTRONICS CO., LTD.' → 'SamsungElectronics'
    'Apple Inc.' → 'Apple'
    'SK HYNIX INC' → 'SkHynix'

    Strips common legal suffixes and capitalises each word.
    """
    import re as _re

    # Remove legal suffixes
    name = _re.sub(
        r"\b(co\.?|corp\.?|inc\.?|ltd\.?|llc\.?|plc\.?|ag\.?|sa\.?|nv\.?|bv\.?)\b",
        "",
        name,
        flags=_re.IGNORECASE,
    )
    # Keep only alphanum and spaces
    name = _re.sub(r"[^A-Za-z0-9 ]", " ", name)
    words = [w.capitalize() for w in name.split() if w]
    return "".join(words[:3])  # max 3 words to keep filenames short


def _upload_excels_to_storage(summary: dict, week_folder_name: str) -> None:
    """Upload Excel files to Supabase Storage (best-effort)."""
    try:
        from db.storage import upload_and_get_url
    except ImportError:
        logger.debug("db.storage not available — skipping upload")
        return

    date_tag = _excel_date_tag(week_folder_name)  # e.g. "04-12"

    for i, entry in enumerate(summary["valuations"]):
        if entry["status"] == "success" and entry.get("excel_path"):
            try:
                ticker = entry.get("ticker")
                market = entry.get("market", "")
                from db.storage import _sanitize_key as _sk

                remote_filename = None
                date_suffix = f"({date_tag})" if date_tag else ""

                if ticker and str(ticker).strip():
                    ticker_str = str(ticker).strip()
                    if market == "KR" and ticker_str.isdigit():
                        # KR stock code → look up English name from DART corpCode.xml
                        from pipeline.dart_client import get_corp_eng_name_by_stock_code

                        eng_name = get_corp_eng_name_by_stock_code(ticker_str)
                        if eng_name:
                            camel = _to_camel(eng_name)
                            if camel:
                                remote_filename = f"{camel}{date_suffix}_valuation.xlsx"
                    if remote_filename is None:
                        # US ticker (e.g. AAPL) — use ticker + date
                        if market == "US":
                            remote_filename = (
                                f"{ticker_str}{date_suffix}_valuation.xlsx"
                            )
                        else:
                            # KR fallback: sanitize company name
                            safe = _sk(entry.get("company", ""))
                            if safe and len(safe) >= 2:
                                remote_filename = f"{safe}{date_suffix}_valuation.xlsx"
                            else:
                                remote_filename = (
                                    f"{ticker_str}{date_suffix}_valuation.xlsx"
                                )

                if remote_filename is None:
                    # No ticker: sanitize company name; fall back to positional index
                    safe = _sk(Path(entry["excel_path"]).stem)
                    remote_filename = (
                        f"{safe}{date_suffix}_valuation.xlsx"
                        if safe
                        else f"company_{i}{date_suffix}_valuation.xlsx"
                    )
                upload = upload_and_get_url(
                    entry["excel_path"], week_folder_name, remote_filename
                )
                if upload:
                    entry["download_url"] = upload["download_url"]
                    entry["remote_path"] = upload["remote_path"]
                    logger.info(
                        "Storage upload OK [%s] ticker=%s → %s",
                        entry["company"],
                        ticker,
                        upload["remote_path"],
                    )
            except Exception as e:
                logger.warning("Storage upload failed [%s]: %s", entry["company"], e)


def _save_json_summary(summary: dict, week_dir: Path) -> None:
    """Save JSON summary file for the delivery agent to read."""
    success_count = sum(1 for v in summary["valuations"] if v["status"] == "success")
    failed_count = sum(1 for v in summary["valuations"] if v["status"] == "failed")
    blocked_count = sum(
        1 for v in summary["valuations"] if v["status"] == "draft_blocked"
    )

    # Set on the live summary dict so email (sent before this function returns) gets it too
    summary["status_summary"] = {
        "total": len(summary["valuations"]),
        "success": success_count,
        "failed": failed_count,
        "draft_blocked": blocked_count,
    }

    # K-0C roll-up. status_summary above is left exactly as it was.
    by_status: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    degraded_results = 0
    for v in summary["valuations"]:
        by_status[v["status"]] = by_status.get(v["status"], 0) + 1
        if v["status"] in ("no_result", "failed"):
            code = v.get("reason_code") or "REASON_NOT_REPORTED"
            by_reason[code] = by_reason.get(code, 0) + 1
        elif v.get("degraded"):
            degraded_results += 1
    summary["valuation_status"] = {
        "contract": _VALUATION_STATUS_CONTRACT,
        "total": len(summary["valuations"]),
        "by_status": by_status,
        "by_reason": by_reason,
        "degraded_results": degraded_results,
    }

    # Scenario-differentiation validation roll-up (per-company status persisted on each
    # valuation entry by auto_analyze). Surfaces silent differentiation failures that the
    # post-generation repair loop could not fix within quota.
    sv_counts: dict[str, int] = {}
    sv_failures: list[dict] = []
    for v in summary["valuations"]:
        sv_status = v.get("scenario_validation")
        if sv_status is None:
            continue
        sv_counts[sv_status] = sv_counts.get(sv_status, 0) + 1
        if sv_status in ("fail", "skipped"):
            sv_failures.append(
                {
                    "company": v["company"],
                    "status": sv_status,
                    "codes": v.get("scenario_validation_codes", []),
                }
            )
    if sv_counts:
        summary["scenario_validation_summary"] = {
            "counts": sv_counts,
            "failures": sv_failures,
        }
        if sv_failures:
            logger.warning(
                "scenario_validation_failures: %d/%d profiles did not pass differentiation (%s)",
                len(sv_failures),
                sum(sv_counts.values()),
                ", ".join(f"{f['company']}={f['status']}" for f in sv_failures),
            )

    summary["_debug"] = {
        "companies_with_empty_top_news": sum(
            1 for co in summary.get("scored_companies", []) if not co.get("top_news")
        ),
    }
    if "_debug_news_titles" in summary:
        summary["_debug"]["news_titles"] = summary.pop("_debug_news_titles")

    summary_json = {**summary}

    summary_path = week_dir / "_weekly_summary.json"
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_json, f, ensure_ascii=False, indent=2, default=str)
        logger.info("JSON summary saved: %s", summary_path)
    except Exception as e:
        logger.warning("Failed to save JSON summary: %s", e)


def _print_summary_header(
    label: str,
    total_news: int,
    scored: list[dict],
) -> None:
    """Print weekly analysis result header."""
    print(f"\n{'=' * 50}")
    print(f"[주간 자동 분석] {label}")
    print(f"{'=' * 50}")
    print(f"  뉴스 수집: {total_news}건\n")

    if scored:
        print("  [발굴 기업 - 중요도 순]")
        for co in scored:
            stars = co.get("stars", "★☆☆☆☆")
            name = co.get("name", "")
            reason = co.get("reason", "")
            news_cnt = co.get("news_count", 0)
            print(f"  {stars} {name} - {reason} (뉴스 {news_cnt}건)")
    else:
        print("  발굴된 기업이 없습니다.")
    print()


def _print_completion(
    summary: dict, duration: float, output_dir: Path | None = None
) -> None:
    """Print completion message."""
    success = sum(1 for v in summary["valuations"] if v["status"] == "success")
    total = len(summary["valuations"])
    errors = len(summary["errors"])

    print(f"\n{'=' * 50}")
    print(f"[완료] {summary['label']}")
    print(f"  실행 시간: {duration:.0f}초")
    print(f"  밸류에이션: {success}/{total} 성공")
    if output_dir:
        print(f"  결과 폴더: {output_dir}")
    if errors:
        print(f"  오류: {errors}건")
    print(f"{'=' * 50}")


def _save_run_start(markets: list[str]) -> str | None:
    """Record run start in DB."""
    try:
        from db.repository import save_discovery_run

        return save_discovery_run(
            {
                "markets": markets,
                "status": "running",
            }
        )
    except Exception as e:
        logger.debug("DB 기록 실패 (시작): %s", e)
        return None


def _finalize_run(
    run_id: str | None,
    summary: dict,
    duration: float,
    total_news: int,
    scored: list[dict],
) -> None:
    """Record run completion in DB."""
    if not run_id:
        return
    try:
        from db.repository import update_discovery_run

        status = "completed" if not summary["errors"] else "completed_with_errors"
        update_discovery_run(
            run_id,
            {
                "status": status,
                "news_count": total_news,
                "companies_discovered": scored,
                "companies_analyzed": [v["company"] for v in summary["valuations"]],
                "errors": summary["errors"],
                "duration_seconds": round(duration, 1),
            },
        )
    except Exception as e:
        logger.debug("DB 기록 실패 (완료): %s", e)


_LOCK_PATH = Path(__file__).resolve().parent.parent / "logs" / ".weekly_run.lock"
_LOCK_MIN_INTERVAL_SECONDS = 3600  # 1 hour


def _acquire_lock(force: bool) -> bool:
    """Prevent rapid re-runs. Returns True if lock acquired, False if recent run exists."""
    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _LOCK_PATH.exists() and not force:
        age = time.time() - _LOCK_PATH.stat().st_mtime
        if age < _LOCK_MIN_INTERVAL_SECONDS:
            logger.warning(
                "Recent run detected (%.0f min ago). Skipping to prevent duplicate runs "
                "and quota exhaustion. Use --force to override.",
                age / 60,
            )
            return False
    _LOCK_PATH.write_text(
        f"pid={os.getpid()} ts={datetime.now().isoformat()}\n", encoding="utf-8"
    )
    return True


def _release_lock() -> None:
    try:
        _LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        pass


def main() -> None:
    _setup_logging()
    parser = argparse.ArgumentParser(
        description="Weekly automated news collection + valuation",
    )
    parser.add_argument(
        "--markets",
        default="KR,US",
        help="Target markets (comma-separated, default: KR,US)",
    )
    parser.add_argument(
        "--max-per-market",
        type=int,
        default=5,
        help="Max companies per market (default: 5)",
    )
    parser.add_argument(
        "--max-companies",
        type=int,
        default=None,
        help="(deprecated: use --max-per-market)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discovery only, skip valuation",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass lockfile (allow rapid re-runs)",
    )
    args = parser.parse_args()

    max_val = args.max_per_market
    if args.max_companies is not None:
        max_val = args.max_companies

    if not _acquire_lock(force=args.force):
        return
    try:
        run_weekly(
            markets=args.markets.split(","),
            max_per_market=max_val,
            dry_run=args.dry_run,
        )
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
