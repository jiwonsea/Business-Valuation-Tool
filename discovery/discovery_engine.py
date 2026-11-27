"""AI-powered Discovery engine -- news analysis -> company recommendation -> scenario suggestion.

The user reviews/modifies the output before running valuation.
"""

from __future__ import annotations

import json
import logging
import re
import sys

from pipeline.api_guard import ApiGuardError

from .news_collector import NewsCollector
from .saveticker_collector import fetch_saveticker_news, get_top_us_tickers

logger = logging.getLogger(__name__)


# ── Failure contract (K-0B) ──────────────────────────────────────────────────
# discover() never returns an empty company list without a reason code.
# scheduler/weekly_run.py carries the code into _weekly_summary.json, so a week
# with zero selected companies no longer looks like a clean run.

NEWS_EMPTY = "NEWS_EMPTY"  # no news after dedup; the LLM was not called
LLM_CALL_FAILED = "LLM_CALL_FAILED"  # ask() raised
LLM_JSON_INVALID = "LLM_JSON_INVALID"  # response is not the agreed JSON object
NO_CANDIDATES = "NO_CANDIDATES"  # valid response / collection, zero candidates
FILTERED_TO_ZERO = "FILTERED_TO_ZERO"  # candidates existed, the post-filter removed all
DISCOVERY_EXCEPTION = "DISCOVERY_EXCEPTION"  # any other exception
SELECTION_EMPTY = "SELECTION_EMPTY"  # set by weekly_run: discovered, none selected
REASON_NOT_REPORTED = "REASON_NOT_REPORTED"  # empty result without a reason
UNKNOWN_LEGACY = "UNKNOWN_LEGACY"  # only for readers of pre-K-0B summaries

# "failure" = something broke or the contract was breached.
# "empty"   = processing finished and there was nothing to select.
REASON_SEVERITY: dict[str, str] = {
    NEWS_EMPTY: "failure",
    LLM_CALL_FAILED: "failure",
    LLM_JSON_INVALID: "failure",
    DISCOVERY_EXCEPTION: "failure",
    REASON_NOT_REPORTED: "failure",
    NO_CANDIDATES: "empty",
    FILTERED_TO_ZERO: "empty",
    SELECTION_EMPTY: "empty",
}

PATH_SAVETICKER = "saveticker"
PATH_NEWS_LLM = "news_llm"

_MESSAGE_LIMIT = 300
_REDACT_INPUT_LIMIT = 4000
_BRIEF_MESSAGE_LIMIT = 160

_SECRET_NAME = (
    r"[\w.\-]{0,40}"
    r"(?:key|secret|token|password|passwd|authorization|credential|cookie|client[_\-]?id)"
    r"[\w.\-]{0,40}"
)
# Order matters: whole URL parts first, then named values, then bare token shapes.
_REDACTIONS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"(?i)(https?://)[^\s/'\"@]+@"), r"\1***@"),
    (re.compile(r"(?i)(https?://[^\s'\"?#]+)\?[^\s'\"]*"), r"\1?***"),
    (
        re.compile(
            r"(?i)\b((?:set-)?cookie['\"]?\s*[:=]\s*)"
            r"(?:\"[^\"]*(?:\"|$)|'[^']*(?:'|$)|[^\r\n'\"}]*)"
        ),
        r"\1***",
    ),
    (
        re.compile(
            # a quoted value that never closes (cut off upstream or by the
            # input limit below) is masked to the end of the text
            r"(?i)(['\"]?" + _SECRET_NAME + r"['\"]?\s*[:=]\s*)"
            r"(?:\"[^\"]*(?:\"|$)|'[^']*(?:'|$)"
            r"|(?:bearer|basic)\s+[^\s'\",;}&)]+|[^\s'\",;}&)]+)"
        ),
        r"\1***",
    ),
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=\-]+"), r"\1 ***"),
    (re.compile(r"(?i)\bsk-[A-Za-z0-9_\-]{4,}"), "sk-***"),
    (re.compile(r"[A-Za-z0-9_\-]{32,}"), "***"),
)

# Fixed prefixes that ai/llm_client.py puts on the RuntimeErrors it raises itself.
# A provider name that merely appears somewhere in a message proves nothing: an
# OpenRouter error body can name "Anthropic" as the upstream.
_LLM_CLIENT_PREFIXES: tuple[tuple[str, str], ...] = (
    ("OpenRouter error:", "openrouter"),
    ("OpenRouter returned empty choices", "openrouter"),
    ("OPENROUTER_API_KEY", "openrouter"),
    ("ANTHROPIC_API_KEY", "anthropic"),
    ("LLM API 키가 설정되지 않았습니다", "none_configured"),
)


def redact_text(text: object, limit: int = _MESSAGE_LIMIT) -> str:
    """Mask known credential notations, fold to one line, cut to *limit* characters.

    One function for every diagnostic string K-0B adds (reason_detail, errors[],
    log lines, alert text). Redaction runs before truncation so a secret that
    straddles the cut cannot leave its head behind. It errs on the side of
    masking too much. It is not a guarantee that every secret is removed: a
    short value with no name and no known shape passes through.
    """
    try:
        value = text if isinstance(text, str) else str(text)
    except Exception:
        return ""
    if len(value) > _REDACT_INPUT_LIMIT:
        # Bound the work. The cut can land inside a secret: the token it splits
        # is dropped here, and a quoted value that lost its closing quote is
        # still masked to the end by the named-value pattern.
        value = re.sub(r"\S+$", "", value[:_REDACT_INPUT_LIMIT])
    for pattern, replacement in _REDACTIONS:
        value = pattern.sub(replacement, value)
    value = " ".join(value.split())  # one line, after the line-based cookie rule
    return value[:limit]


def _token(value: object, limit: int = 64) -> str | None:
    """Untrusted short identifier -> [A-Za-z0-9_.-] only, or None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        cleaned = re.sub(r"[^A-Za-z0-9_.\-]", "", str(value))[:limit]
    except Exception:
        return None
    return cleaned or None


def _attr(obj: object, name: str) -> object:
    """getattr that never raises (httpx raises RuntimeError for an unset .request)."""
    try:
        return getattr(obj, name, None)
    except Exception:
        return None


def _text_of(exc: BaseException) -> str:
    """str(exc) that never raises."""
    try:
        return str(exc)
    except Exception:
        return ""


def _provider_of(exc: BaseException) -> str:
    if isinstance(exc, ApiGuardError):
        provider = _token(_attr(exc, "provider"), 40)
        if provider:
            return provider
    module = type(exc).__module__ or ""
    if module == "anthropic" or module.startswith("anthropic."):
        return "anthropic"
    host = str(_attr(_attr(_attr(exc, "request"), "url"), "host") or "").lower()
    if "openrouter" in host:
        return "openrouter"
    if "anthropic" in host:
        return "anthropic"
    message = _text_of(exc)
    for prefix, provider in _LLM_CLIENT_PREFIXES:
        if message.startswith(prefix):
            return provider
    return "unknown"


def _http_status_of(exc: BaseException) -> int | None:
    for status in (
        _attr(exc, "status_code"),
        _attr(_attr(exc, "response"), "status_code"),
    ):
        if isinstance(status, int) and not isinstance(status, bool):
            return status
    return None  # never guessed from digits in the message


def _api_error_type_of(exc: BaseException) -> str | None:
    """body.error.type -> response.error.type -> body.error.code -> response.error.code."""
    errors: list[dict] = []
    body = _attr(exc, "body")  # anthropic SDK: the whole decoded JSON body
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        errors.append(body["error"])
    response = _attr(exc, "response")
    if response is not None:
        try:
            payload = response.json()
        except Exception:
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            errors.append(payload["error"])
    for key in ("type", "code"):
        for error in errors:
            token = _token(error.get(key))
            if token:
                return token
    return None


def _describe_one(exc: BaseException) -> dict:
    try:
        return {
            "provider": _provider_of(exc),
            "http_status": _http_status_of(exc),
            "error_type": type(exc).__name__,
            "api_error_type": _api_error_type_of(exc),
            "message": redact_text(exc),
        }
    except Exception:
        # Reading the diagnostics must never replace the failure being reported.
        return {"error_type": type(exc).__name__}


def describe_error(exc: BaseException) -> dict:
    """JSON-safe description of *exc* and up to three ``__cause__`` links.

    When OpenRouter fails and the Anthropic fallback fails too, ask() raises the
    Anthropic error ``from`` the OpenRouter one: the top level then describes
    Anthropic and ``caused_by[0]`` describes OpenRouter. The two are never mixed.
    """
    described = _describe_one(exc)
    chain: list[dict] = []
    try:
        seen = {id(exc)}
        cause = exc.__cause__
        while cause is not None and len(chain) < 3 and id(cause) not in seen:
            seen.add(id(cause))
            chain.append(_describe_one(cause))
            cause = cause.__cause__
    except Exception:
        pass  # an unreadable cause is left out; what was read so far stays
    described["caused_by"] = chain
    return described


def _error_brief(detail: dict) -> str:
    parts = [str(detail.get("provider") or "unknown")]
    if detail.get("http_status") is not None:
        parts.append(f"HTTP {detail['http_status']}")
    label = detail.get("api_error_type")
    if not label or label == str(detail.get("http_status")):
        # OpenRouter's error body carries a numeric code, not a type name
        label = detail.get("error_type") or "error"
    parts.append(str(label))
    return " ".join(parts)


def describe_reason(reason_code: str | None, detail: dict | None) -> str:
    """One line for logs, errors[] and alerts. Built from redacted fields only."""
    detail = detail or {}
    if reason_code == NEWS_EMPTY:
        text = str(detail.get("provider") or "unknown")
        if "quota_exhausted" in detail:
            text += f", quota_exhausted={detail['quota_exhausted']}"
    elif reason_code in (LLM_CALL_FAILED, DISCOVERY_EXCEPTION):
        text = _error_brief(detail)
        if reason_code == DISCOVERY_EXCEPTION:
            text = f"{detail.get('stage') or 'discover'}: {text}"
        message = str(detail.get("message") or "")[:_BRIEF_MESSAGE_LIMIT]
        if message:
            text += f": {message}"
        for cause in detail.get("caused_by") or []:
            if isinstance(cause, dict):
                text += f" <- {_error_brief(cause)}"
    elif reason_code == LLM_JSON_INVALID:
        text = f"{detail.get('kind')}, response_chars={detail.get('response_chars')}"
    elif reason_code == NO_CANDIDATES:
        text = f"path={detail.get('path')}"
    elif reason_code == FILTERED_TO_ZERO:
        text = f"{detail.get('candidates_raw')} candidate(s), all removed by the post-filter"
    elif reason_code == SELECTION_EMPTY:
        text = ", ".join(
            f"{key}={value}" for key, value in detail.items() if value is not None
        )
    elif reason_code == REASON_NOT_REPORTED:
        text = "discover() returned no companies and no reason"
    else:
        text = ""
    return redact_text(text, limit=600)


class _LLMCallFailed(Exception):
    """ask() raised. ``__cause__`` is the original exception.

    Carries no message of its own: building one would call str() on the
    original, which can raise and would then hide the LLM failure.
    """


# Known media outlets, financial data providers, and non-company entities that
# the AI occasionally misidentifies as investable companies.
_MEDIA_BLOCKLIST: frozenset[str] = frozenset(
    {
        "electrek",
        "yahoo finance",
        "yahoo",
        "bloomberg",
        "reuters",
        "cnbc",
        "wsj",
        "wall street journal",
        "financial times",
        "ft",
        "marketwatch",
        "benzinga",
        "seeking alpha",
        "investopedia",
        "motley fool",
        "barrons",
        "the street",
        "zerohedge",
        "techcrunch",
        "the verge",
        "ars technica",
        "engadget",
        "wired",
        "fortune",
        "business insider",
        "forbes",
        "nikkei",
        "한국경제",
        "매일경제",
        "조선비즈",
        "연합뉴스",
        # Korean transliterations — AI occasionally returns the Hangul
        # spelling of foreign outlets even after being told to use English.
        "일렉트렉",
        "야후 파이낸스",
        "야후파이낸스",
        "블룸버그",
        "로이터",
    }
)


def _is_media_name(name_lower: str) -> bool:
    """Return True if a lowercased name contains a blocklisted outlet name.

    Latin-script terms match whole words only: "ft" is a substring of
    "microsoft". Hangul terms match anywhere, because Korean joins an outlet
    name to its suffix without a space ("블룸버그통신").
    """
    for term in _MEDIA_BLOCKLIST:
        if not term.isascii():
            if term in name_lower:
                return True
        elif re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", name_lower):
            return True
    return False


def _contains_korean(text: str) -> bool:
    """Return True if text contains any Hangul syllable."""
    return any("\uac00" <= ch <= "\ud7a3" for ch in text)


def _filter_companies(companies: list[dict], market: str) -> list[dict]:
    """Remove AI hallucinations: media outlets and mis-classified companies.

    Filters:
    1. Any company whose name (lowercased) matches the media blocklist.
    2. US market: name must not contain Hangul (AI was told to use English).
    3. KR market: must be a genuine Korean listing — requires either Hangul
       in the name or a 6-digit KRX ticker. Otherwise it's a US/foreign
       company mentioned in Korean news, not a KR-listed company.
    """
    filtered: list[dict] = []
    for co in companies:
        name: str = co.get("name") or ""
        ticker: str = (co.get("ticker") or "").strip()
        name_lower = name.lower().strip()

        # Filter 1: media/data-provider blocklist
        if _is_media_name(name_lower):
            logger.info("Discovery filter: rejected media/non-company %r", name)
            continue

        # Filter 2: US market — name must be English (no Hangul)
        if market == "US" and _contains_korean(name):
            logger.info(
                "Discovery filter: rejected Korean-named US company %r "
                "(ticker=%r) — AI should have used English name",
                name,
                ticker,
            )
            continue

        # Filter 3: KR market — must be KR-listed (Hangul name or 6-digit ticker)
        if market == "KR":
            has_krx_ticker = ticker.isdigit() and len(ticker) == 6
            if not _contains_korean(name) and not has_krx_ticker:
                logger.info(
                    "Discovery filter: rejected non-KR company %r in KR market "
                    "(ticker=%r) — English name with no KRX ticker",
                    name,
                    ticker,
                )
                continue

        filtered.append(co)

    return filtered


def _safe_print(text: str) -> None:
    """Print with encoding fallback for Windows cp949 consoles."""
    try:
        print(text)
    except Exception:
        try:
            enc = getattr(sys.stdout, "encoding", None) or "utf-8"
            safe = text.encode(enc, errors="replace").decode(enc, errors="replace")
            print(safe)
        except Exception:
            pass  # Last resort: silently drop non-critical console output


# Per-market search keywords
_KR_QUERIES = [
    "코스피 실적 발표",
    "한국 주식시장 이슈",
    "IPO 상장",
    "기업 인수합병 M&A",
]
_US_QUERIES = [
    "S&P 500 company earnings beat miss revenue results",
    "nasdaq NYSE stock valuation quarterly results",
    "company IPO stock debut NYSE Nasdaq listing",
    "merger acquisition billion deal stock market",
]


def summarize_key_issues(
    news: list[dict],
    company_name: str,
    market: str = "KR",
) -> str:
    """Summarize valuation-relevant key issues from a news list.

    Args:
        news: NewsCollector output format [{"title", "description", "pub_date", ...}]
        company_name: Target company name
        market: "KR" | "US"

    Returns:
        Bullet-point key issues text. Empty string on failure.
    """
    if not news:
        return ""

    # Disk cache (reuse ai/analyst.py cache infrastructure)
    from ai.analyst import _get_cached, _set_cached
    from ai.llm_client import ask
    from ai.prompts import SYSTEM_DISCOVERY
    from ai.telemetry import call_context, emit

    cached = _get_cached(company_name, "key_issues")
    if cached:
        with call_context(company_name, "news_summary"):
            emit("step_start")
            emit("cache_hit")
            emit("step_end", outcome="cache_hit")
            return cached.get("text", "")

    news_text = "\n".join(f"- [{n['pub_date'][:10]}] {n['title']}" for n in news)

    market_label = "한국" if market == "KR" else "미국"
    prompt = f"""\
<company>{company_name} ({market_label} 시장)</company>
<news_data>
{news_text}
</news_data>

위 뉴스에서 이 기업의 밸류에이션에 영향을 줄 수 있는 핵심 이슈를 요약하세요.
카테고리별 bullet point 형식으로 5~10개 이내 핵심만 추출하세요.
밸류에이션과 무관한 뉴스는 제외하고, 각 이슈에 관련 뉴스 날짜를 포함하세요.

<example>
- [리스크] 수주 감소로 2025년 매출 하락 전망 (3월 뉴스)
- [기회] 신규 해외 프로젝트 수주 발표 예정 (3월 뉴스)
- [규제] ESG 관련 신규 규제안 국회 통과 가능성 (2월 뉴스)
</example>"""

    with call_context(company_name, "news_summary"):
        emit("step_start")
        emit("cache_miss")
        try:
            result = ask(
                prompt, system=SYSTEM_DISCOVERY, temperature=0.2, max_tokens=1024
            )
            if result:
                _set_cached(company_name, "key_issues", {"text": result})
            emit("step_end", outcome="success")
            return result
        except Exception:
            emit("step_end", outcome="error")
            return ""


class DiscoveryEngine:
    """News-based target company recommendation + scenario suggestion."""

    def __init__(self):
        self.collector = NewsCollector()

    def discover(self, market: str = "KR") -> dict:
        """Execute Discovery workflow.

        1. Collect news (past 1 month)
        2. AI analysis: issue summary + company recommendation + scenario/probability suggestion
        3. Output results (for user review)

        Returns:
            {"news_count": int, "analysis": str, "companies": list, "scenarios": list,
             "news": list} plus the K-0B failure contract (keys are only added):
            "reason_code" (None when companies is non-empty, otherwise a code --
            an empty list never comes back without one), "reason_detail" (dict),
            "path" ("saveticker" | "news_llm"), "path_fallback" (None or
            {"from", "reason_code"}), "candidates_raw", "candidates_filtered_out".

        KR and US call this on one shared instance from two threads, so every
        diagnostic lives in locals and in the returned dict, never on ``self``.
        """
        _safe_print(f"\n{'=' * 60}")
        _safe_print(f"[Discovery Mode] {market} 시장 뉴스 분석")
        _safe_print(f"{'=' * 60}")

        path_fallback: dict | None = None
        if market == "US":
            # Primary: SaveTicker ticker-tagged news (LLM-free, quota-cheap).
            # SaveTicker changed its feed shape (2026-06): tag_names no longer
            # carries "$TICKER" tags and titles are Korean-translated, so
            # fetch_saveticker_news() now yields 0 items. Fall back to the
            # proven Google News RSS + LLM path (matches the "google_rss" US
            # provider that weekly_run.py already assumes) instead of failing.
            result = self._discover_us_saveticker()
            if result.get("news_count", 0) > 0:
                return result
            logger.warning(
                "SaveTicker returned 0 items — falling back to Google News RSS "
                "+ LLM for US discovery (saveticker feed shape likely changed)"
            )
            _safe_print(
                "[WARN] SaveTicker 0건 — Google News RSS + LLM 경로로 폴백합니다."
            )
            path_fallback = {"from": PATH_SAVETICKER, "reason_code": NEWS_EMPTY}
            # fall through to the generic news + LLM flow below

        # Step 1: Collect news
        queries = _KR_QUERIES if market == "KR" else _US_QUERIES
        all_news = []
        for q in queries:
            _safe_print(f"  수집 중: '{q}'...")
            if market == "KR":
                items = self.collector.collect_kr(q, days=30, max_items=30)
            else:
                items = self.collector.collect_us(q, days=30, max_items=30)
            all_news.extend(items)
            _safe_print(f"    -> {len(items)}건")

        # Deduplicate (by title)
        seen = set()
        unique_news = []
        for n in all_news:
            if n["title"] not in seen:
                seen.add(n["title"])
                unique_news.append(n)

        _safe_print(f"\n  총 {len(unique_news)}건 수집 (중복 제거 후)")

        if not unique_news:
            _safe_print("[WARN] 수집된 뉴스가 없습니다.")
            return self._with_contract(
                {
                    "news_count": 0,
                    "analysis": "",
                    "companies": [],
                    "scenarios": [],
                    "news": [],
                },
                market=market,
                path=PATH_NEWS_LLM,
                path_fallback=path_fallback,
                reason_code=NEWS_EMPTY,
                reason_detail={
                    "provider": "naver" if market == "KR" else "google_rss",
                    "queries": len(queries),
                },
            )

        # Step 2: AI analysis
        _safe_print("[AI 분석 시작]")
        try:
            analysis = self._analyze_with_ai(unique_news, market)
        except Exception as e:
            # Only the ask() call itself is an LLM failure. Anything else raised
            # while analysing (prompt building, post-processing) is a different
            # fault and must not be reported as the provider's.
            failed: BaseException = e
            if isinstance(e, _LLMCallFailed) and e.__cause__ is not None:
                failed = e.__cause__
                reason_code = LLM_CALL_FAILED
                reason_detail = describe_error(failed)
            else:
                reason_code = DISCOVERY_EXCEPTION
                reason_detail = {"stage": "analyze", **describe_error(e)}
            _safe_print(f"[ERROR] AI 분석 실패: {redact_text(failed, limit=600)}")
            _safe_print("[FALLBACK] 수집된 뉴스 제목만 출력합니다.")
            for i, n in enumerate(unique_news[:20], 1):
                _safe_print(f"  {i}. {n['title']} ({n['pub_date'][:10]})")
            return self._with_contract(
                {
                    "news_count": len(unique_news),
                    "analysis": "",
                    "companies": [],
                    "scenarios": [],
                    "news": unique_news,
                },
                market=market,
                path=PATH_NEWS_LLM,
                path_fallback=path_fallback,
                reason_code=reason_code,
                reason_detail=reason_detail,
            )

        diag = analysis.pop("_diag", None) or {}

        # Step 3: Output results
        try:
            self._print_analysis(analysis)
        except Exception:
            # Console output only. On the normal path an error here propagates
            # exactly as it did before K-0B. Once a reason is established, a
            # printing error (say, a scenario entry that is not an object) must
            # not replace it.
            if not diag.get("reason_code"):
                raise

        return self._with_contract(
            {
                "news_count": len(unique_news),
                "analysis": analysis.get("summary", ""),
                "companies": analysis.get("companies", []),
                "scenarios": analysis.get("scenarios", []),
                "news": unique_news,
            },
            market=market,
            path=PATH_NEWS_LLM,
            path_fallback=path_fallback,
            reason_code=diag.get("reason_code"),
            reason_detail=diag.get("reason_detail"),
            candidates_raw=diag.get("candidates_raw"),
            candidates_filtered_out=diag.get("candidates_filtered_out"),
        )

    @staticmethod
    def _print_analysis(analysis: dict) -> None:
        """Console report of one analysis (the pre-K-0B print block, unchanged)."""
        _safe_print(f"\n{'=' * 60}")
        _safe_print("[분석 결과]")
        _safe_print(f"{'=' * 60}")
        _safe_print(analysis.get("summary", ""))

        if analysis.get("companies"):
            _safe_print("\n[추천 기업]")
            for i, co in enumerate(analysis["companies"], 1):
                _safe_print(f"  {i}. {co.get('name', '')} — {co.get('reason', '')}")

        if analysis.get("scenarios"):
            _safe_print("\n[시나리오 제안]")
            for sc in analysis["scenarios"]:
                _safe_print(
                    f"  {sc.get('name', '')}: 확률 {sc.get('prob', 0)}% — {sc.get('description', '')}"
                )

        _safe_print(f"\n{'=' * 60}")
        _safe_print("위 결과를 검토한 후, 다음 단계를 진행하세요:")
        _safe_print("  1. 추천 기업 중 분석 대상 선택")
        _safe_print("  2. 시나리오/확률 조정")
        _safe_print("  3. python cli.py --company <기업명> --auto")
        _safe_print(f"{'=' * 60}")

    @staticmethod
    def _with_contract(
        result: dict,
        *,
        market: str,
        path: str,
        path_fallback: dict | None = None,
        reason_code: str | None = None,
        reason_detail: dict | None = None,
        candidates_raw: int | None = None,
        candidates_filtered_out: int | None = None,
        quiet: bool = False,
    ) -> dict:
        """Add the failure-contract keys to a discover() result (existing keys untouched).

        Invariant: an empty ``companies`` list always carries a reason code, and
        a non-empty one never does.
        """
        if result.get("companies"):
            reason_code, reason_detail = None, {}
        elif not reason_code:
            reason_code = REASON_NOT_REPORTED
        result["reason_code"] = reason_code
        result["reason_detail"] = dict(reason_detail or {})
        result["path"] = path
        result["path_fallback"] = path_fallback
        result["candidates_raw"] = candidates_raw
        result["candidates_filtered_out"] = candidates_filtered_out
        if reason_code and not quiet:
            logger.warning(
                "Discovery [%s] returned 0 companies: %s (%s)",
                market,
                reason_code,
                describe_reason(reason_code, result["reason_detail"]),
            )
        return result

    def _discover_us_saveticker(self) -> dict:
        """Discover US targets from SaveTicker ticker-tagged news without LLM."""
        _safe_print("  SaveTicker news collection...")
        news = fetch_saveticker_news(max_items=100)
        companies = get_top_us_tickers(n=8, news=news)
        _safe_print(f"    -> {len(news)} items, {len(companies)} tickers")

        if not news:
            _safe_print("[WARN] SaveTicker news collection returned no items.")
            # discover() does not return this result: it falls back to the
            # news + LLM path and records the fallback there (hence quiet).
            return self._with_contract(
                {
                    "news_count": 0,
                    "analysis": "",
                    "companies": [],
                    "scenarios": [],
                    "news": [],
                },
                market="US",
                path=PATH_SAVETICKER,
                reason_code=NEWS_EMPTY,
                reason_detail={"provider": "saveticker"},
                quiet=True,
            )

        summary = (
            "US discovery used SaveTicker ticker-tagged news ranked by mention count."
        )
        _safe_print("\n[Recommended US tickers]")
        for i, co in enumerate(companies, 1):
            _safe_print(f"  {i}. {co.get('ticker', '')} - {co.get('reason', '')}")

        # Defensive: _normalize_item() drops items without tickers, so news
        # without any ticker is not expected from the real collector.
        return self._with_contract(
            {
                "news_count": len(news),
                "analysis": summary,
                "companies": companies,
                "scenarios": [],
                "news": news,
            },
            market="US",
            path=PATH_SAVETICKER,
            reason_code=None if companies else NO_CANDIDATES,
            reason_detail={} if companies else {"path": PATH_SAVETICKER},
            candidates_raw=len(companies),
            candidates_filtered_out=0,
        )

    def _analyze_with_ai(self, news: list[dict], market: str) -> dict:
        """Analyze news via Claude API.

        Returns {"summary", "companies", "scenarios", "_diag"}. ``_diag`` is the
        per-call failure diagnosis that discover() pops off and turns into the
        public contract keys. Raises ``_LLMCallFailed`` (from the original
        exception) when ask() itself fails.
        """
        from ai.llm_client import ask
        from ai.analyst import _parse_json
        from ai.prompts import SYSTEM_DISCOVERY
        from ai.telemetry import call_context, emit

        # Compose news summary text (token-efficient: titles only)
        news_text = "\n".join(
            f"- [{n['pub_date'][:10]}] {n['title']}"
            for n in news[:30]  # 최대 30건 (토큰 절약)
        )

        market_label = "한국" if market == "KR" else "미국"
        prompt = f"""\
<news_data>
최근 1개월간 {market_label} 시장 주요 뉴스:
{news_text}
</news_data>

위 뉴스를 분석하여 시장 동향 요약, 밸류에이션 분석이 의미 있는 기업 추천(최대 8개), 시장 시나리오(3개, 확률 합계 100%)를 제시하세요.
(후처리 필터로 미디어·비상장 기업이 제거되므로, 최종 분석 대상은 5개로 자동 축소됩니다. 충분한 후보를 제시하세요.)

<rules>
- companies는 반드시 개별 상장 기업만 포함하세요. '반도체 관련주', '방위산업 관련 기업군' 같은 섹터·테마 표현은 절대 사용하지 마세요.
- 뉴스 사이트·미디어·금융 데이터 제공업체(Bloomberg, Yahoo Finance, Electrek, Reuters, CNBC 등)는 제외하세요. 분석 대상은 제품/서비스를 생산하는 사업 기업에 한합니다.
- ticker: 정확히 알고 있는 경우에만 작성하고, 모르거나 불확실하면 반드시 null로 두세요. '미지정', 'N/A', '없음' 등의 문자열 금지.
- 한국 기업 ticker 형식: 숫자 6자리 (예: "005930"), 미국 기업: 알파벳 또는 점 포함 가능 (예: "NVDA", "BRK.B")
- 미국 기업 name: SEC EDGAR 검색에 사용되는 영어 공식 명칭을 반드시 사용하세요 (예: "Tesla", "NVIDIA", "Apple"). 뉴스가 한국어로 작성된 경우에도 기업명은 영어 원명으로 출력해야 합니다. 한국어 번역 이름 절대 금지.
- domain: 해당 기업의 공식 웹사이트 도메인 (예: "samsung.com", "nvidia.com"). 확실히 아는 경우에만 입력하고, 모르거나 불확실하면 null. 서브도메인 없이 루트 도메인만 입력 (corp.example.com 금지 → example.com).
</rules>

<output_format>
{{
  "summary": "시장 전체 동향 요약 (3-5문장)",
  "companies": [
    {{"name": "개별 기업 정식 명칭 (미국 기업은 반드시 영문)", "ticker": "티커 또는 null", "domain": "루트 도메인 또는 null", "reason": "분석 추천 이유"}}
  ],
  "scenarios": [
    {{"name": "시나리오명", "prob": 30, "description": "설명"}}
  ]
}}
</output_format>"""

        with call_context(market, "discovery_analyze"):
            emit("step_start")
            emit("cache_miss")
            try:
                # max_tokens=1200 truncated Korean JSON output mid-string on the
                # Anthropic haiku fallback path (2026-07-18 run: 출력=1200 exactly,
                # parse failed, discovery returned 0 companies). Korean chars are
                # token-heavy; summary + 8 companies + 3 scenarios needs headroom.
                response = ask(
                    prompt, system=SYSTEM_DISCOVERY, temperature=0.2, max_tokens=2500
                )
                emit("step_end", outcome="success")
            except Exception as exc:
                emit("step_end", outcome="error")
                raise _LLMCallFailed() from exc

        response_chars = len(response) if isinstance(response, str) else 0

        def _invalid(kind: str, keep: dict | None = None) -> dict:
            # The raw response is untrusted text: only its length and the kind
            # of breakage go into the diagnosis.
            #
            # The values under the old keys stay what they were before K-0B.
            # Breakage that used to end in the "AI 분석 실패" exception path
            # returned an empty summary and no scenarios, so that is the
            # default. `keep` is passed only where the old code returned the
            # parsed response (or the raw text) with an empty company list.
            out = keep if keep is not None else {"summary": "", "scenarios": []}
            out["companies"] = []
            out["_diag"] = {
                "reason_code": LLM_JSON_INVALID,
                "reason_detail": {"kind": kind, "response_chars": response_chars},
            }
            return out

        if not isinstance(response, str):
            return _invalid("empty_response")
        if not response.strip():
            return _invalid("empty_response", {"summary": response, "scenarios": []})

        try:
            parsed = _parse_json(response)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "AI JSON 파싱 실패 [%s]: %s — companies=[] fallback. 원본 응답 앞 200자: %.200s",
                market,
                exc,
                response,
            )
            return _invalid("parse_error", {"summary": response, "scenarios": []})

        if not isinstance(parsed, dict):
            return _invalid("not_object")
        if "companies" not in parsed:
            # old code: parsed.get("companies", []) gave [] and parsed was returned
            return _invalid("companies_missing", parsed)
        candidates = parsed["companies"]
        if candidates is None:
            return _invalid("companies_missing")
        if not isinstance(candidates, list):
            # old code: an empty "" or {} passed as "no companies" and parsed was
            # returned; any other non-list raised
            passed_before = isinstance(candidates, (str, dict)) and not candidates
            return _invalid("companies_not_list", parsed if passed_before else None)
        if any(not isinstance(co, dict) for co in candidates):
            # Outcome unchanged from before K-0B (zero companies, empty summary):
            # this used to surface as a generic "AI 분석 실패".
            return _invalid("company_entry_not_object")

        # Post-processing: remove media outlets and mis-named US companies
        raw_count = len(candidates)
        parsed["companies"] = _filter_companies(candidates, market)
        filtered_count = raw_count - len(parsed["companies"])
        if filtered_count:
            logger.info(
                "Discovery post-filter [%s]: removed %d non-company entry(s) from AI output",
                market,
                filtered_count,
            )
        if raw_count == 0:
            reason_code, reason_detail = NO_CANDIDATES, {"path": PATH_NEWS_LLM}
        elif not parsed["companies"]:
            reason_code = FILTERED_TO_ZERO
            reason_detail = {
                "candidates_raw": raw_count,
                "candidates_filtered_out": filtered_count,
            }
        else:
            reason_code, reason_detail = None, {}
        parsed["_diag"] = {
            "reason_code": reason_code,
            "reason_detail": reason_detail,
            "candidates_raw": raw_count,
            "candidates_filtered_out": filtered_count,
        }
        return parsed
