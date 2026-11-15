"""K-0B discovery failure contract: every zero-selection path leaves a reason.

Backstory: from 2026-10-03 the weekly pipeline selected 0 companies for five
weeks while ``_weekly_summary.json`` said ``errors: []``. ``discover()`` printed
the LLM failure and returned an empty list, and the final warning told the
reader to check NAVER/OpenRouter keys while the real cause was an Anthropic
HTTP 400.

These tests inject each fault through the real ``DiscoveryEngine`` and the real
``run_weekly()`` and read the summary file that was written. Nothing here may
touch the network, the LLM, the database, mail, blog posting, ``logs/``,
``.cache/`` or ``valuation-results/`` -- see the ``harness`` fixture.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import sys
import threading
import types
from pathlib import Path

import httpx
import pytest

# ── synthetic inputs ─────────────────────────────────────────────────────────

# Far in the past so every item gets the same time-decay weight (0.1) and the
# score order depends only on how often a company is mentioned.
KR_NEWS = [
    {
        "title": "삼성전자 3분기 실적 발표",
        "description": "",
        "link": "https://news.example/kr/1",
        "pub_date": "2020-01-06T09:00:00",
        "source": "naver",
    },
    {
        "title": "삼성전자 반도체 투자 확대",
        "description": "",
        "link": "https://news.example/kr/2",
        "pub_date": "2020-01-07T09:00:00",
        "source": "naver",
    },
    {
        "title": "SK하이닉스 HBM 증설",
        "description": "",
        "link": "https://news.example/kr/3",
        "pub_date": "2020-01-08T09:00:00",
        "source": "naver",
    },
]

US_NEWS = [
    {
        "title": "Apple beats quarterly revenue estimates",
        "description": "",
        "link": "https://news.example/us/1",
        "pub_date": "2020-01-06T09:00:00",
        "source": "google_rss",
    },
    {
        "title": "Tesla deliveries rise in the quarter",
        "description": "",
        "link": "https://news.example/us/2",
        "pub_date": "2020-01-07T09:00:00",
        "source": "google_rss",
    },
]

# One media outlet and one foreign company are in the list on purpose: the
# post-filter must drop them and keep the rest in the order the LLM gave.
KR_ANALYSIS = {
    "summary": "반도체 중심의 실적 시즌.",
    "companies": [
        {
            "name": "삼성전자",
            "ticker": "005930",
            "domain": "samsung.com",
            "reason": "실적",
        },
        {"name": "블룸버그", "ticker": None, "domain": None, "reason": "매체"},
        {
            "name": "SK하이닉스",
            "ticker": "000660",
            "domain": "skhynix.com",
            "reason": "HBM",
        },
        {
            "name": "Tesla",
            "ticker": "TSLA",
            "domain": "tesla.com",
            "reason": "미국 기업",
        },
    ],
    "scenarios": [{"name": "기준", "prob": 100, "description": "유지"}],
}

US_ANALYSIS = {
    "summary": "Large-cap earnings.",
    "companies": [
        {
            "name": "Apple",
            "ticker": "AAPL",
            "domain": "apple.com",
            "reason": "earnings",
        },
        {
            "name": "Tesla",
            "ticker": "TSLA",
            "domain": "tesla.com",
            "reason": "deliveries",
        },
    ],
    "scenarios": [],
}

CREDIT_MESSAGE = "Your credit balance is too low to access the Anthropic API."


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def anthropic_status_error(status: int = 400, api_type: str = "invalid_request_error"):
    """An exception shaped like anthropic.APIStatusError (the SDK is not imported)."""
    body = {"type": "error", "error": {"type": api_type, "message": CREDIT_MESSAGE}}
    cls = type("BadRequestError", (Exception,), {"__module__": "anthropic"})
    exc = cls(f"Error code: {status} - {body}")
    exc.status_code = status
    exc.body = body
    return exc


def openrouter_http_error(status: int = 403) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(
        status,
        request=request,
        json={"error": {"message": "Key limit exceeded", "code": status}},
    )
    return httpx.HTTPStatusError(
        f"Client error '{status} Forbidden' for url '{request.url}'",
        request=request,
        response=response,
    )


def anthropic_after_openrouter() -> Exception:
    """What ask() raises when OpenRouter fails and the Anthropic fallback fails too."""
    exc = anthropic_status_error()
    exc.__cause__ = openrouter_http_error()
    return exc


# ── isolation ────────────────────────────────────────────────────────────────


class Harness:
    """Replaces every side-effecting boundary of run_weekly(); fails closed."""

    def __init__(self) -> None:
        self.news_kr: list[dict] | None = None
        self.news_us: list[dict] | None = None
        self.saveticker_news: list[dict] | None = None
        self.saveticker_tickers: list[dict] = []
        self.ask = None  # callable(prompt) -> str, or an Exception to raise
        self.usage: dict = {
            "naver": {"calls": 4, "cache_hits": 0, "limit": 50, "remaining": 46},
            "google_rss": {"calls": 4, "cache_hits": 0, "limit": 50, "remaining": 46},
        }
        self.remaining_quota: dict = {"anthropic": 50}
        self.ask_prompts: list[str] = []
        self.alerts: list[tuple[str, str]] = []
        self.db_updates: list[tuple[str, dict]] = []
        self.analyzed: list[str] = []
        self.mail: list[dict] = []
        self.posts: list[str] = []
        self.unexpected: list[str] = []
        self.wr = None

    def _unexpected(self, what: str):
        self.unexpected.append(what)
        raise AssertionError(f"unexpected call: {what}")

    def collect_kr(self, query: str) -> list[dict]:
        if self.news_kr is None:
            self._unexpected("NewsCollector.collect_kr")
        return list(self.news_kr)

    def collect_us(self, query: str) -> list[dict]:
        if self.news_us is None:
            self._unexpected("NewsCollector.collect_us")
        return list(self.news_us)

    def fetch_saveticker(self) -> list[dict]:
        if self.saveticker_news is None:
            self._unexpected("fetch_saveticker_news")
        return list(self.saveticker_news)

    def call_ask(self, prompt: str):
        self.ask_prompts.append(prompt)
        if self.ask is None:
            self._unexpected("ai.llm_client.ask")
        if isinstance(self.ask, BaseException):
            raise self.ask
        return self.ask(prompt)

    def run(self, markets=("KR",), dry_run: bool = True, **kwargs) -> dict:
        """Run the real run_weekly() and return the summary *as written to disk*."""
        summary = self.wr.run_weekly(markets=list(markets), dry_run=dry_run, **kwargs)
        path = Path(summary["week_dir"]) / "_weekly_summary.json"
        return json.loads(path.read_text(encoding="utf-8"))


def _module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


@pytest.fixture
def env_guard():
    """The process environment after a test is what it was before it.

    Requested ahead of ``monkeypatch`` so that it is torn down after it. Only
    names are compared and reported, never values.
    """
    before = {key: hash(value) for key, value in os.environ.items()}
    yield
    after = {key: hash(value) for key, value in os.environ.items()}
    changed = sorted(
        key
        for key in set(before) | set(after)
        if key != "PYTEST_CURRENT_TEST" and before.get(key) != after.get(key)
    )
    assert changed == [], f"environment not restored for: {changed}"


@pytest.fixture
def harness(env_guard, monkeypatch, tmp_path):
    h = Harness()

    monkeypatch.setenv("BVT_TELEMETRY", "0")
    # _ssl_fix.apply() returns early when this is set, so a first import of
    # scheduler.weekly_run from this file never copies certificates around.
    monkeypatch.setenv("CURL_CA_BUNDLE", os.environ.get("CURL_CA_BUNDLE") or "k0b-test")
    # The first import of scheduler.weekly_run loads the repository's .env.
    # Keep that out of the tests: no key is needed here, and keys loaded during
    # the fixture would outlive it.
    try:
        import dotenv
    except ImportError:
        dotenv = None
    if dotenv is not None:
        monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)

    wr = importlib.import_module("scheduler.weekly_run")
    h.wr = wr

    # After the import: an earlier import by another test module may already
    # have loaded keys, and they must be gone for the duration of the test.
    for var in (
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "NAVER_CLIENT_ID",
        "NAVER_CLIENT_SECRET",
        "DUMP_NEWS_TITLES",
        "BVT_TELEMETRY_PATH",
    ):
        monkeypatch.delenv(var, raising=False)

    # news + LLM
    monkeypatch.setattr(
        "discovery.news_collector.NewsCollector.collect_kr",
        lambda self, query="", days=30, max_items=100: h.collect_kr(query),
    )
    monkeypatch.setattr(
        "discovery.news_collector.NewsCollector.collect_us",
        lambda self, query="", days=30, max_items=100: h.collect_us(query),
    )
    monkeypatch.setattr(
        "discovery.discovery_engine.fetch_saveticker_news",
        lambda max_items=100: h.fetch_saveticker(),
    )
    monkeypatch.setattr(
        "discovery.discovery_engine.get_top_us_tickers",
        lambda n=15, max_items=100, news=None: list(h.saveticker_tickers),
    )
    importlib.import_module("ai.llm_client")
    monkeypatch.setattr(
        "ai.llm_client.ask", lambda prompt, **kwargs: h.call_ask(prompt)
    )

    # files, logging, alerts, DB, storage
    monkeypatch.setattr(wr, "_RESULTS_BASE", tmp_path)
    monkeypatch.setattr(wr, "_setup_logging", lambda: None)
    monkeypatch.setattr(
        wr, "_alert", lambda phase, error: h.alerts.append((phase, error))
    )
    monkeypatch.setattr(wr, "_save_run_start", lambda markets: "run-k0b")
    monkeypatch.setattr(wr, "_upload_excels_to_storage", lambda *a, **k: None)
    monkeypatch.setitem(
        sys.modules,
        "db.repository",
        _module(
            "db.repository",
            update_discovery_run=lambda run_id, updates: h.db_updates.append(
                (run_id, updates)
            ),
        ),
    )

    # quota guard: a real ApiGuard() creates .cache/api_usage.lock
    guard = types.SimpleNamespace(get_usage_summary=lambda: h.usage)
    monkeypatch.setattr(
        "pipeline.api_guard.ApiGuard.get", classmethod(lambda cls: guard)
    )
    monkeypatch.setattr(
        "pipeline.api_guard.estimate_weekly_cost",
        lambda markets, n: {
            "estimated_api_calls": {},
            "estimated_llm_calls": 0,
            "estimated_llm_cost_usd": 0.0,
            "remaining_quota": dict(h.remaining_quota),
        },
    )

    # scoring stays real except for the market-cap lookup (yfinance)
    monkeypatch.setattr(
        "scheduler.scoring._fetch_market_cap_usd", lambda ticker, market: None
    )

    # valuation, mail and posting: the real modules are never imported
    def _auto_analyze(query, **kwargs):
        h.analyzed.append(query)
        return None

    monkeypatch.setitem(
        sys.modules,
        "pipeline.profile_generator",
        _module("pipeline.profile_generator", auto_analyze=_auto_analyze),
    )
    monkeypatch.setitem(
        sys.modules,
        "scheduler.email_sender",
        _module(
            "scheduler.email_sender",
            send_weekly_email=lambda summary: h.mail.append(summary),
            send_error_alert=lambda phase, error: h.alerts.append((phase, error)),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "scheduler.wp_poster",
        _module(
            "scheduler.wp_poster", post_to_wordpress=lambda s: h.posts.append("wp")
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "scheduler.naver_poster",
        _module(
            "scheduler.naver_poster", post_to_naver=lambda s: h.posts.append("naver")
        ),
    )

    yield h

    assert h.unexpected == [], f"un-mocked boundary was reached: {h.unexpected}"


# ── helpers ──────────────────────────────────────────────────────────────────


def row(saved: dict, market: str) -> dict:
    rows = [r for r in saved["discovery_status"]["markets"] if r["market"] == market]
    assert len(rows) == 1, f"expected exactly one discovery_status row for {market}"
    return rows[0]


def error_for(saved: dict, market: str) -> dict:
    found = [e for e in saved["errors"] if e.get("market") == market]
    assert len(found) == 1, (
        f"expected exactly one error for {market}: {saved['errors']}"
    )
    return found[0]


def discovery_entry(saved: dict, market: str) -> dict:
    found = [d for d in saved["discoveries"] if d["market"] == market]
    assert len(found) == 1
    return found[0]


def final_status(h: Harness) -> str:
    assert len(h.db_updates) == 1
    run_id, payload = h.db_updates[0]
    assert run_id == "run-k0b"
    return payload["status"]


# ── 0. normal path: selection must not change (passes before and after K-0B) ──


def test_normal_discover_legacy_keys_unchanged(harness):
    """Characterization: values under the pre-K-0B keys of discover()."""
    from discovery.discovery_engine import DiscoveryEngine

    harness.news_kr = KR_NEWS
    harness.ask = lambda prompt: _json(KR_ANALYSIS)

    result = DiscoveryEngine().discover(market="KR")

    assert result["news_count"] == 3
    assert result["analysis"] == "반도체 중심의 실적 시즌."
    assert result["companies"] == [
        KR_ANALYSIS["companies"][0],
        KR_ANALYSIS["companies"][2],
    ]
    assert result["scenarios"] == KR_ANALYSIS["scenarios"]
    assert result["news"] == KR_NEWS
    assert len(harness.ask_prompts) == 1


def test_normal_weekly_selection_unchanged(harness):
    """Characterization: what run_weekly() selects and writes under the old keys."""
    harness.news_kr = KR_NEWS
    harness.ask = lambda prompt: _json(KR_ANALYSIS)

    saved = harness.run(markets=["KR"], dry_run=True)

    entry = discovery_entry(saved, "KR")
    assert entry["news_count"] == 3
    assert [c["name"] for c in entry["companies"]] == ["삼성전자", "SK하이닉스"]
    assert [(c["name"], c["market"]) for c in saved["scored_companies"]] == [
        ("삼성전자", "KR"),
        ("SK하이닉스", "KR"),
    ]
    assert saved["scored_companies"][0]["top_news"] == [
        {"title": KR_NEWS[0]["title"], "url": KR_NEWS[0]["link"]},
        {"title": KR_NEWS[1]["title"], "url": KR_NEWS[1]["link"]},
    ]
    assert saved["valuations"] == []
    assert saved["errors"] == []
    assert harness.alerts == []


def test_normal_reports_no_reason(harness):
    harness.news_kr = KR_NEWS
    harness.ask = lambda prompt: _json(KR_ANALYSIS)

    saved = harness.run(markets=["KR"], dry_run=True)

    kr = row(saved, "KR")
    assert "reason_code" in kr and kr["reason_code"] is None
    assert kr["reason_detail"] == {}
    assert kr["path"] == "news_llm"
    assert kr["path_fallback"] is None
    assert (kr["candidates_raw"], kr["candidates_filtered_out"]) == (4, 2)
    assert (kr["discovered"], kr["selected"]) == (2, 2)
    entry = discovery_entry(saved, "KR")
    assert "reason_code" in entry and entry["reason_code"] is None
    assert entry["path"] == "news_llm"
    status = saved["discovery_status"]
    assert status["contract"] == "k0b-1"
    assert status["targets_selected"] == 2
    assert status["zero_selection"] is False
    assert status["targets_after_budget_trim"] is None  # dry run does not trim
    assert saved["errors"] == []
    assert final_status(harness) == "completed"


def test_discover_return_contract_on_success(harness):
    from discovery.discovery_engine import DiscoveryEngine

    harness.news_kr = KR_NEWS
    harness.ask = lambda prompt: _json(KR_ANALYSIS)

    result = DiscoveryEngine().discover(market="KR")

    assert "reason_code" in result and result["reason_code"] is None
    assert result["reason_detail"] == {}
    assert result["path"] == "news_llm"
    assert result["path_fallback"] is None
    assert result["candidates_raw"] == 4
    assert result["candidates_filtered_out"] == 2
    assert all(not key.startswith("_") for key in result)


# ── 1. news empty ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("remaining, exhausted", [(46, False), (0, True)])
def test_news_empty(harness, remaining, exhausted):
    harness.news_kr = []
    harness.usage["naver"]["remaining"] = remaining

    saved = harness.run(markets=["KR"], dry_run=True)

    kr = row(saved, "KR")
    assert kr["reason_code"] == "NEWS_EMPTY"
    assert kr["severity"] == "failure"
    assert kr["reason_detail"]["provider"] == "naver"
    assert kr["reason_detail"]["quota_exhausted"] is exhausted
    assert kr["candidates_raw"] is None
    assert harness.ask_prompts == []  # the LLM is not called without news
    err = error_for(saved, "KR")
    assert (err["phase"], err["reason_code"]) == ("discovery", "NEWS_EMPTY")
    assert discovery_entry(saved, "KR")["reason_code"] == "NEWS_EMPTY"
    assert final_status(harness) == "completed_with_errors"
    # existing rule: no "Discovery" mail when the daily quota is simply used up
    discovery_alerts = [msg for phase, msg in harness.alerts if phase == "Discovery"]
    assert len(discovery_alerts) == (0 if exhausted else 1)
    for msg in discovery_alerts:
        assert "API 키/네트워크 확인 필요" not in msg
        assert msg.startswith("[KR] 뉴스 수집 결과 0건")


# ── 2. LLM call failed ───────────────────────────────────────────────────────


def test_llm_call_failed_keeps_provider_status_and_cause_chain(harness):
    harness.news_kr = KR_NEWS
    harness.ask = anthropic_after_openrouter()

    saved = harness.run(markets=["KR"], dry_run=True)

    kr = row(saved, "KR")
    assert kr["reason_code"] == "LLM_CALL_FAILED"
    assert kr["severity"] == "failure"
    detail = kr["reason_detail"]
    assert detail["provider"] == "anthropic"
    assert detail["http_status"] == 400
    assert detail["error_type"] == "BadRequestError"
    assert detail["api_error_type"] == "invalid_request_error"
    assert "credit balance is too low" in detail["message"]
    assert len(detail["caused_by"]) == 1
    cause = detail["caused_by"][0]
    assert cause["provider"] == "openrouter"
    assert cause["http_status"] == 403
    assert cause["error_type"] == "HTTPStatusError"
    assert cause["api_error_type"] == "403"
    assert kr["news_count"] == 3  # the news were there; the LLM was not
    err = error_for(saved, "KR")
    assert (err["phase"], err["reason_code"]) == ("discovery", "LLM_CALL_FAILED")
    assert "anthropic" in err["error"] and "400" in err["error"]
    assert final_status(harness) == "completed_with_errors"


@pytest.mark.parametrize(
    "exc_factory, provider, error_type",
    [
        (
            lambda: RuntimeError(
                "OpenRouter error: {'message': 'Provider returned error', "
                "'metadata': {'provider_name': 'Anthropic'}}"
            ),
            "openrouter",
            "RuntimeError",
        ),
        (
            lambda: RuntimeError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다."),
            "anthropic",
            "RuntimeError",
        ),
        (
            lambda: RuntimeError(
                "LLM API 키가 설정되지 않았습니다. "
                "OPENROUTER_API_KEY 또는 ANTHROPIC_API_KEY를 .env에 추가하세요."
            ),
            "none_configured",
            "RuntimeError",
        ),
        (lambda: TimeoutError("read timed out after 500 s"), "unknown", "TimeoutError"),
    ],
)
def test_llm_call_failed_without_http_status(
    harness, exc_factory, provider, error_type
):
    harness.news_kr = KR_NEWS
    harness.ask = exc_factory()

    saved = harness.run(markets=["KR"], dry_run=True)

    detail = row(saved, "KR")["reason_detail"]
    assert row(saved, "KR")["reason_code"] == "LLM_CALL_FAILED"
    assert detail["provider"] == provider
    assert detail["error_type"] == error_type
    assert detail["http_status"] is None  # never guessed from digits in the message
    assert detail["caused_by"] == []


def test_llm_call_failed_quota_guard(harness):
    from pipeline.api_guard import QuotaExceededError

    harness.news_kr = KR_NEWS
    harness.ask = QuotaExceededError("anthropic", 50, 50)

    saved = harness.run(markets=["KR"], dry_run=True)

    detail = row(saved, "KR")["reason_detail"]
    assert detail["provider"] == "anthropic"
    assert detail["error_type"] == "QuotaExceededError"
    assert detail["http_status"] is None


# ── 3. LLM answered, JSON unusable ───────────────────────────────────────────


@pytest.mark.parametrize(
    "response, kind",
    [
        ("", "empty_response"),
        (None, "empty_response"),
        ("죄송합니다. 분석할 수 없습니다 {", "parse_error"),
        ('{"summary": "잘린 응답", "companies": [{"name": "삼성', "parse_error"),
        ("[1, 2, 3]", "not_object"),
        ('{"summary": "x", "scenarios": []}', "companies_missing"),
        ('{"summary": "x", "companies": null}', "companies_missing"),
        ('{"summary": "x", "companies": {"name": "삼성전자"}}', "companies_not_list"),
        (
            '{"summary": "x", "companies": [{"name": "삼성전자", "ticker": "005930"}, "SK하이닉스"]}',
            "company_entry_not_object",
        ),
    ],
)
def test_llm_json_invalid(harness, response, kind):
    harness.news_kr = KR_NEWS
    harness.ask = lambda prompt: response

    saved = harness.run(markets=["KR"], dry_run=True)

    kr = row(saved, "KR")
    assert kr["reason_code"] == "LLM_JSON_INVALID"
    assert kr["severity"] == "failure"
    assert kr["reason_detail"]["kind"] == kind
    assert kr["reason_detail"]["response_chars"] == len(response or "")
    assert kr["discovered"] == 0
    assert error_for(saved, "KR")["reason_code"] == "LLM_JSON_INVALID"
    # the raw LLM text is untrusted and stays out of the summary diagnostics
    if response:
        assert response not in json.dumps(kr, ensure_ascii=False)
    assert final_status(harness) == "completed_with_errors"


# ── 4. candidates, then none ─────────────────────────────────────────────────


def test_filtered_to_zero(harness):
    harness.news_kr = KR_NEWS
    harness.ask = lambda prompt: _json(
        {
            "summary": "매체만 나왔다.",
            "companies": [
                {"name": "블룸버그", "ticker": None},
                {"name": "연합뉴스", "ticker": None},
                {"name": "Tesla", "ticker": "TSLA"},
            ],
            "scenarios": [],
        }
    )

    saved = harness.run(markets=["KR"], dry_run=True)

    kr = row(saved, "KR")
    assert kr["reason_code"] == "FILTERED_TO_ZERO"
    assert kr["severity"] == "empty"
    assert (kr["candidates_raw"], kr["candidates_filtered_out"]) == (3, 3)
    assert kr["reason_detail"]["candidates_raw"] == 3
    assert error_for(saved, "KR")["reason_code"] == "FILTERED_TO_ZERO"
    assert final_status(harness) == "completed_with_errors"


def test_no_candidates(harness):
    harness.news_kr = KR_NEWS
    harness.ask = lambda prompt: _json(
        {"summary": "조용한 주.", "companies": [], "scenarios": []}
    )

    saved = harness.run(markets=["KR"], dry_run=True)

    kr = row(saved, "KR")
    assert kr["reason_code"] == "NO_CANDIDATES"
    assert kr["severity"] == "empty"
    assert (kr["candidates_raw"], kr["candidates_filtered_out"]) == (0, 0)
    assert error_for(saved, "KR")["reason_code"] == "NO_CANDIDATES"


# ── 5. the four injected faults are told apart ───────────────────────────────


def test_four_faults_have_four_reason_codes(harness, tmp_path):
    faults = {
        "news_empty": ([], None),
        "llm_call_failed": (KR_NEWS, anthropic_after_openrouter()),
        "llm_json_invalid": (KR_NEWS, lambda prompt: "{ not json"),
        "filtered_to_zero": (
            KR_NEWS,
            lambda prompt: _json({"summary": "", "companies": [{"name": "Bloomberg"}]}),
        ),
    }
    codes = {}
    for name, (news, ask) in faults.items():
        harness.news_kr, harness.ask = news, ask
        saved = harness.run(markets=["KR"], dry_run=True)
        assert saved["scored_companies"] == []
        assert saved["errors"] != [], f"{name} is buried under errors: []"
        codes[name] = error_for(saved, "KR")["reason_code"]
        assert row(saved, "KR")["reason_code"] == codes[name]
        assert saved["discovery_status"]["zero_selection"] is True

    assert codes == {
        "news_empty": "NEWS_EMPTY",
        "llm_call_failed": "LLM_CALL_FAILED",
        "llm_json_invalid": "LLM_JSON_INVALID",
        "filtered_to_zero": "FILTERED_TO_ZERO",
    }
    assert [
        status for _, payload in harness.db_updates for status in [payload["status"]]
    ] == ["completed_with_errors"] * 4


# ── 6. the final warning names the real reason (full run, zero targets) ──────


def test_zero_selection_alert_states_real_reasons(harness):
    harness.news_kr = KR_NEWS
    harness.ask = anthropic_after_openrouter()
    harness.saveticker_news = []
    harness.news_us = []

    saved = harness.run(markets=["KR", "US"], dry_run=False)

    valuation_alerts = [msg for phase, msg in harness.alerts if phase == "Valuation"]
    assert len(valuation_alerts) == 1
    msg = valuation_alerts[0]
    assert msg.startswith("Discovery returned 0 companies — valuation skipped.")
    assert "NAVER/OpenRouter" not in msg
    assert "Check " not in msg
    assert "KR=LLM_CALL_FAILED" in msg
    assert "anthropic HTTP 400 invalid_request_error" in msg
    assert "credit balance is too low" in msg
    assert "<- openrouter HTTP 403 HTTPStatusError" in msg
    assert "US=NEWS_EMPTY" in msg and "google_rss" in msg
    assert msg.index("KR=") < msg.index("US=")  # requested order, not thread order

    status = saved["discovery_status"]
    assert status["zero_selection"] is True
    assert status["targets_selected"] == 0
    assert status["targets_after_budget_trim"] == 0
    assert [r["market"] for r in status["markets"]] == ["KR", "US"]
    us = row(saved, "US")
    assert us["path"] == "news_llm"
    assert us["path_fallback"] == {"from": "saveticker", "reason_code": "NEWS_EMPTY"}
    assert {e["reason_code"] for e in saved["errors"]} == {
        "LLM_CALL_FAILED",
        "NEWS_EMPTY",
    }
    assert saved["valuations"] == []
    assert harness.analyzed == []
    assert final_status(harness) == "completed_with_errors"


def test_zero_selection_is_logged_in_dry_run_without_mail(harness, caplog):
    harness.news_kr = KR_NEWS
    harness.ask = anthropic_after_openrouter()

    with caplog.at_level(logging.WARNING):
        harness.run(markets=["KR"], dry_run=True)

    lines = [r.getMessage() for r in caplog.records if r.name == "scheduler.weekly_run"]
    assert any(
        line.startswith("Discovery returned 0 companies")
        and "KR=LLM_CALL_FAILED" in line
        for line in lines
    )
    assert [phase for phase, _ in harness.alerts] == []
    assert harness.mail == []
    assert harness.posts == []


# ── 7. exceptions that are not the LLM call ──────────────────────────────────


@pytest.mark.parametrize("exc", [RuntimeError("KR API 실패"), Exception()])
def test_exception_out_of_discover(harness, monkeypatch, exc):
    """An exception with an empty message used to crash run_weekly()."""
    engine = types.SimpleNamespace(discover=lambda market: (_ for _ in ()).throw(exc))
    monkeypatch.setattr("discovery.discovery_engine.DiscoveryEngine", lambda: engine)

    saved = harness.run(markets=["KR"], dry_run=True)

    kr = row(saved, "KR")
    assert kr["reason_code"] == "DISCOVERY_EXCEPTION"
    assert kr["severity"] == "failure"
    assert kr["reason_detail"]["stage"] == "discover"
    assert kr["reason_detail"]["error_type"] == type(exc).__name__
    err = error_for(saved, "KR")
    assert err["phase"] == "discovery"
    assert err["reason_code"] == "DISCOVERY_EXCEPTION"
    assert err["error_type"] == type(exc).__name__
    assert err["error"] == str(exc)
    assert saved["discoveries"] == []  # unchanged: no entry for a market that raised
    assert final_status(harness) == "completed_with_errors"


def test_exception_inside_analysis_is_not_called_an_llm_failure(harness, monkeypatch):
    harness.news_kr = KR_NEWS
    harness.ask = lambda prompt: _json(KR_ANALYSIS)

    def broken_filter(companies, market):
        raise ZeroDivisionError("filter bug")

    monkeypatch.setattr("discovery.discovery_engine._filter_companies", broken_filter)

    saved = harness.run(markets=["KR"], dry_run=True)

    kr = row(saved, "KR")
    assert kr["reason_code"] == "DISCOVERY_EXCEPTION"
    assert kr["reason_detail"]["stage"] == "analyze"
    assert kr["reason_detail"]["error_type"] == "ZeroDivisionError"
    assert discovery_entry(saved, "KR")["reason_code"] == "DISCOVERY_EXCEPTION"


def test_producer_without_reason_is_an_error(harness, monkeypatch):
    engine = types.SimpleNamespace(
        discover=lambda market: {"news_count": 5, "companies": []}
    )
    monkeypatch.setattr("discovery.discovery_engine.DiscoveryEngine", lambda: engine)

    saved = harness.run(markets=["US"], dry_run=True)

    us = row(saved, "US")
    assert us["reason_code"] == "REASON_NOT_REPORTED"
    assert us["severity"] == "failure"
    assert error_for(saved, "US")["reason_code"] == "REASON_NOT_REPORTED"
    assert discovery_entry(saved, "US")["reason_code"] == "REASON_NOT_REPORTED"
    assert final_status(harness) == "completed_with_errors"


# ── 8. which path produced the result ────────────────────────────────────────


def test_saveticker_path_needs_no_llm(harness):
    harness.saveticker_news = [
        {
            "title": "NVDA rallies",
            "link": "https://st.example/1",
            "url": "https://st.example/1",
            "pub_date": "2020-01-06T09:00:00",
            "source": "saveticker",
            "tickers": ["NVDA"],
        },
    ]
    harness.saveticker_tickers = [
        {
            "name": "NVDA",
            "ticker": "NVDA",
            "market": "US",
            "reason": "SaveTicker mention count 1",
        },
    ]

    saved = harness.run(markets=["US"], dry_run=True)

    us = row(saved, "US")
    assert us["path"] == "saveticker"
    assert us["path_fallback"] is None
    assert us["reason_code"] is None
    assert (us["discovered"], us["selected"]) == (1, 1)
    assert harness.ask_prompts == []
    assert saved["errors"] == []


def test_saveticker_news_without_tickers(harness):
    harness.saveticker_news = [
        {
            "title": "macro note",
            "link": "https://st.example/2",
            "url": "https://st.example/2",
            "pub_date": "2020-01-06T09:00:00",
            "source": "saveticker",
            "tickers": [],
        },
    ]
    harness.saveticker_tickers = []

    saved = harness.run(markets=["US"], dry_run=True)

    us = row(saved, "US")
    assert us["path"] == "saveticker"
    assert us["reason_code"] == "NO_CANDIDATES"
    assert us["reason_detail"]["path"] == "saveticker"
    assert harness.ask_prompts == []


def test_saveticker_empty_falls_back_to_news_llm(harness):
    harness.saveticker_news = []
    harness.news_us = US_NEWS
    harness.ask = lambda prompt: _json(US_ANALYSIS)

    saved = harness.run(markets=["US"], dry_run=True)

    us = row(saved, "US")
    assert us["path"] == "news_llm"
    assert us["path_fallback"] == {"from": "saveticker", "reason_code": "NEWS_EMPTY"}
    assert us["reason_code"] is None
    assert [c["name"] for c in discovery_entry(saved, "US")["companies"]] == [
        "Apple",
        "Tesla",
    ]
    assert saved["errors"] == []


# ── 9. KR and US share one engine instance and run in parallel ───────────────


def test_parallel_markets_do_not_share_diagnostics(harness):
    harness.news_kr = KR_NEWS
    harness.saveticker_news = []
    harness.news_us = US_NEWS
    both_in_flight = threading.Barrier(2, timeout=10)

    def ask(prompt: str) -> str:
        try:
            both_in_flight.wait()
        except threading.BrokenBarrierError:
            pass
        if "한국 시장" in prompt:
            raise anthropic_status_error()
        return _json(US_ANALYSIS)

    harness.ask = ask

    saved = harness.run(markets=["KR", "US"], dry_run=True)

    assert (
        both_in_flight.broken is False
    )  # both markets really were in the LLM step together
    kr, us = row(saved, "KR"), row(saved, "US")
    assert kr["reason_code"] == "LLM_CALL_FAILED"
    assert kr["path_fallback"] is None
    assert kr["reason_detail"]["provider"] == "anthropic"
    assert us["reason_code"] is None
    assert us["reason_detail"] == {}
    assert us["path_fallback"] == {"from": "saveticker", "reason_code": "NEWS_EMPTY"}
    assert (us["discovered"], us["selected"]) == (2, 2)
    assert [e["market"] for e in saved["errors"]] == ["KR"]
    assert saved["discovery_status"]["zero_selection"] is False


def test_discovery_failure_survives_companies_arriving_from_another_market(harness):
    """KR's LLM call fails; US news yields a KR-listed company and a US one.

    Both markets end up with a target, and KR's failure must still be on record.
    """
    harness.news_kr = KR_NEWS
    harness.saveticker_news = []
    harness.news_us = US_NEWS

    def ask(prompt: str) -> str:
        if "한국 시장" in prompt:
            raise anthropic_status_error()
        return _json(
            {
                "summary": "",
                "companies": [
                    {"name": "Samsung Electronics", "ticker": "005930"},
                    {"name": "Apple", "ticker": "AAPL"},
                ],
                "scenarios": [],
            }
        )

    harness.ask = ask

    saved = harness.run(markets=["KR", "US"], dry_run=True)

    kr, us = row(saved, "KR"), row(saved, "US")
    assert (kr["discovered"], kr["selected"]) == (0, 1)
    assert (us["discovered"], us["selected"]) == (2, 1)
    assert kr["reason_code"] == "LLM_CALL_FAILED"
    assert us["reason_code"] is None
    assert saved["discovery_status"]["zero_selection"] is False
    assert [(e["market"], e["phase"], e["reason_code"]) for e in saved["errors"]] == [
        ("KR", "discovery", "LLM_CALL_FAILED")
    ]
    assert final_status(harness) == "completed_with_errors"


# ── 10. discovered something, selected nothing ───────────────────────────────


def test_selection_empty_when_all_retagged_to_other_market(harness):
    harness.news_kr = KR_NEWS
    harness.ask = lambda prompt: _json(
        {
            "summary": "",
            "companies": [{"name": "엔비디아", "ticker": "NVDA"}],
            "scenarios": [],
        }
    )

    saved = harness.run(markets=["KR"], dry_run=True)

    kr = row(saved, "KR")
    assert (kr["discovered"], kr["selected"]) == (1, 0)
    assert kr["reason_code"] == "SELECTION_EMPTY"
    assert kr["severity"] == "empty"
    detail = kr["reason_detail"]
    assert detail["kind"] == "no_company_tagged_to_market"
    assert detail["retagged_to_other_market"] == 1
    assert detail["tagged_to_market"] == 0
    err = error_for(saved, "KR")
    assert (err["phase"], err["reason_code"]) == ("selection", "SELECTION_EMPTY")
    assert (
        discovery_entry(saved, "KR")["reason_code"] is None
    )  # discover() itself was fine
    assert saved["discovery_status"]["zero_selection"] is True


def test_selection_empty_when_only_sector_names(harness):
    harness.news_kr = KR_NEWS
    harness.ask = lambda prompt: _json(
        {
            "summary": "",
            "companies": [{"name": "반도체 관련주", "ticker": None}],
            "scenarios": [],
        }
    )

    saved = harness.run(markets=["KR"], dry_run=True)

    detail = row(saved, "KR")["reason_detail"]
    assert row(saved, "KR")["reason_code"] == "SELECTION_EMPTY"
    assert detail["kind"] == "sector_like_excluded"
    assert (detail["tagged_to_market"], detail["sector_like_excluded"]) == (1, 1)


def test_selection_empty_when_limit_is_zero(harness):
    harness.news_kr = KR_NEWS
    harness.ask = lambda prompt: _json(KR_ANALYSIS)

    saved = harness.run(markets=["KR"], dry_run=True, max_per_market=0)

    detail = row(saved, "KR")["reason_detail"]
    assert row(saved, "KR")["reason_code"] == "SELECTION_EMPTY"
    assert detail["kind"] == "limit"
    assert detail["max_per_market"] == 0
    assert detail["tagged_to_market"] == 2


def test_selection_empty_when_budget_trim_drops_a_market(harness, monkeypatch):
    harness.news_kr = KR_NEWS
    harness.saveticker_news = []
    harness.news_us = US_NEWS
    harness.ask = lambda prompt: _json(
        KR_ANALYSIS if "한국 시장" in prompt else US_ANALYSIS
    )
    harness.remaining_quota = {"anthropic": 0}
    monkeypatch.setattr(
        harness.wr, "WEEKLY_LLM_BUDGET", 6
    )  # 6 calls per company -> 1 target

    saved = harness.run(markets=["KR", "US"], dry_run=False)

    status = saved["discovery_status"]
    kr, us = row(saved, "KR"), row(saved, "US")
    assert (kr["selected"], kr["selected_after_budget_trim"]) == (2, 1)
    assert (us["selected"], us["selected_after_budget_trim"]) == (2, 0)
    assert status["targets_selected"] == 4
    assert status["targets_after_budget_trim"] == 1
    assert kr["selected_after_budget_trim"] + us["selected_after_budget_trim"] == 1
    assert status["zero_selection"] is False
    assert kr["reason_code"] is None
    assert us["reason_code"] == "SELECTION_EMPTY"
    assert us["reason_detail"]["kind"] == "budget_trim"
    assert us["reason_detail"]["max_affordable"] == 1
    err = error_for(saved, "US")
    assert (err["phase"], err["reason_code"]) == ("selection", "SELECTION_EMPTY")
    assert harness.analyzed == ["삼성전자"]  # selection itself is unchanged
    assert [v["status"] for v in saved["valuations"]] == ["no_result"]


def test_discovery_reason_is_kept_when_cross_market_target_is_trimmed(
    harness, monkeypatch
):
    """US discovery fails, gets a target from KR news, then loses it to the trim."""
    harness.news_kr = KR_NEWS
    harness.saveticker_news = []
    harness.news_us = US_NEWS

    def ask(prompt: str) -> str:
        if "미국 시장" in prompt:
            raise anthropic_status_error()
        return _json(
            {
                "summary": "",
                "companies": [
                    {"name": "삼성전자", "ticker": "005930"},
                    {"name": "엔비디아", "ticker": "NVDA"},  # KR news, US ticker
                ],
                "scenarios": [],
            }
        )

    harness.ask = ask
    harness.remaining_quota = {"anthropic": 0}
    monkeypatch.setattr(harness.wr, "WEEKLY_LLM_BUDGET", 6)

    saved = harness.run(markets=["KR", "US"], dry_run=False)

    us = row(saved, "US")
    assert (us["discovered"], us["selected"], us["selected_after_budget_trim"]) == (
        0,
        1,
        0,
    )
    assert us["reason_code"] == "LLM_CALL_FAILED"  # not replaced by SELECTION_EMPTY
    assert row(saved, "KR")["reason_code"] is None
    # K-0C: the stub auto_analyze() returns None without a reason, which is now
    # recorded as well (phase "valuation"); this test is about the others.
    assert [
        (e["market"], e["phase"], e["reason_code"])
        for e in saved["errors"]
        if e["phase"] != "valuation"
    ] == [("US", "discovery", "LLM_CALL_FAILED")]
    assert saved["discovery_status"]["targets_after_budget_trim"] == 1
    assert harness.analyzed == ["삼성전자"]


# ── 11. secrets never reach the summary, the log or the alert ────────────────

SECRETS = [
    "ABCDEF0123456789ABCDEF0123456789ABCDEF01",  # DART-style key in a URL query
    "s3cr3t-json-value",
    "s3cr3t-header-value",
    "tok.en-VALUE_3",
    "sk-ant-SECRETSECRET4",
    "s3cr3t-env-5",
    "hunter2secret",
    "dXNlcjpwYXNzd29yZA==",
    "demo:pw7",  # URL userinfo
    "sid=ab12",  # cookie
    "theme=dark9",  # second cookie pair on the same line
]

LEAKY_MESSAGE = (
    "OpenRouter error: GET https://opendart.fss.or.kr/api/list.json"
    "?crtfc_key=ABCDEF0123456789ABCDEF0123456789ABCDEF01&page=1 failed; "
    "headers={\"api_key\": \"s3cr3t-json-value\", 'X-Api-Key': 's3cr3t-header-value', "
    '"Authorization": "Bearer tok.en-VALUE_3"} key sk-ant-SECRETSECRET4 '
    "NAVER_CLIENT_SECRET=s3cr3t-env-5 PASSWORD: hunter2secret Basic dXNlcjpwYXNzd29yZA== "
    "via https://demo:pw7@example.invalid/path Cookie: sid=ab12; theme=dark9"
)


def _assert_no_secret(text: str) -> None:
    for secret in SECRETS:
        assert secret not in text, f"secret leaked: {secret[:6]}…"


def test_secrets_are_redacted_everywhere(harness, caplog, capsys):
    harness.news_kr = KR_NEWS
    cause = RuntimeError(LEAKY_MESSAGE)
    top = RuntimeError("Anthropic fallback failed: api-key=s3cr3t-header-value")
    top.__cause__ = cause
    harness.ask = top
    harness.saveticker_news = []
    harness.news_us = []

    with caplog.at_level(logging.DEBUG):
        saved = harness.run(markets=["KR", "US"], dry_run=False)

    detail = row(saved, "KR")["reason_detail"]
    assert detail["caused_by"][0]["provider"] == "openrouter"
    assert (
        "https://opendart.fss.or.kr/api/list.json" in detail["caused_by"][0]["message"]
    )
    _assert_no_secret(json.dumps(saved, ensure_ascii=False))
    _assert_no_secret(" ".join(msg for _, msg in harness.alerts))
    _assert_no_secret(
        " ".join(
            r.getMessage()
            for r in caplog.records
            if r.name in ("scheduler.weekly_run", "discovery.discovery_engine")
        )
    )
    _assert_no_secret(json.dumps(harness.db_updates, ensure_ascii=False, default=str))
    _assert_no_secret(
        capsys.readouterr().out
    )  # the "[ERROR] AI 분석 실패" console line


def test_exception_out_of_discover_is_redacted(harness, monkeypatch, caplog):
    exc = RuntimeError(LEAKY_MESSAGE)
    engine = types.SimpleNamespace(discover=lambda market: (_ for _ in ()).throw(exc))
    monkeypatch.setattr("discovery.discovery_engine.DiscoveryEngine", lambda: engine)

    with caplog.at_level(logging.DEBUG):
        saved = harness.run(markets=["KR"], dry_run=True)

    assert error_for(saved, "KR")["reason_code"] == "DISCOVERY_EXCEPTION"
    _assert_no_secret(json.dumps(saved, ensure_ascii=False))
    _assert_no_secret(
        " ".join(
            r.getMessage() for r in caplog.records if r.name == "scheduler.weekly_run"
        )
    )


def test_redaction_runs_before_truncation(harness):
    harness.news_kr = KR_NEWS
    # the secret straddles the 300-character cut: truncating first would leave
    # its head in the summary with nothing left for the redaction to match
    filler = ("lorem ipsum " * 30)[:285]
    harness.ask = RuntimeError(filler + " api_key=STRADDLINGSECRETVALUE")

    saved = harness.run(markets=["KR"], dry_run=True)

    message = row(saved, "KR")["reason_detail"]["message"]
    assert len(message) <= 300
    assert "STRADDLING" not in json.dumps(saved, ensure_ascii=False)


def test_untrusted_api_error_type_is_sanitised(harness):
    harness.news_kr = KR_NEWS
    exc = anthropic_status_error(api_type="<b>evil</b> " + "t" * 200)
    harness.ask = exc

    saved = harness.run(markets=["KR"], dry_run=True)

    api_type = row(saved, "KR")["reason_detail"]["api_error_type"]
    assert len(api_type) <= 64
    assert "<" not in api_type and " " not in api_type


# ── 12. redaction edge cases (Codex implementation review r1) ────────────────


@pytest.mark.parametrize(
    "message, secret",
    [
        # the closing quote lies beyond the 4,000-character input limit
        ('api_key="' + "synthetic phrase " * 300 + '"', "synthetic phrase"),
        ("token: 'a value that never closes its quote", "never closes"),
        ("OpenRouter error: upstream key SK-ant-UPPERCASE123", "UPPERCASE123"),
        # no name, no prefix: only the bare long-token rule can catch this
        (
            "request 0123456789abcdef0123456789abcdef0123 failed",
            "0123456789abcdef0123456789abcdef0123",
        ),
    ],
)
def test_redaction_edge_cases(harness, message, secret):
    harness.news_kr = KR_NEWS
    harness.ask = RuntimeError(message)
    harness.saveticker_news = []
    harness.news_us = []

    saved = harness.run(markets=["KR", "US"], dry_run=False)

    assert row(saved, "KR")["reason_code"] == "LLM_CALL_FAILED"
    assert secret not in json.dumps(saved, ensure_ascii=False)
    assert secret not in " ".join(msg for _, msg in harness.alerts)


def test_diagnostic_strings_are_one_line(harness):
    harness.news_kr = KR_NEWS
    harness.ask = RuntimeError("first line\nsecond line\r\n\tthird")
    harness.saveticker_news = []
    harness.news_us = []

    saved = harness.run(markets=["KR", "US"], dry_run=False)

    assert (
        row(saved, "KR")["reason_detail"]["message"] == "first line second line third"
    )
    texts = [e["error"] for e in saved["errors"]] + [msg for _, msg in harness.alerts]
    assert texts
    for text in texts:
        assert not any(ch in text for ch in "\r\n\t")


# ── 13. describing an error must not fail ────────────────────────────────────


class UnprintableError(Exception):
    def __str__(self) -> str:
        raise ValueError("__str__ failed")


class UnreadableCauseError(Exception):
    @property
    def __cause__(self):
        raise RuntimeError("__cause__ failed")


@pytest.mark.parametrize(
    "exc, message",
    [(UnprintableError(), ""), (UnreadableCauseError("boom"), "boom")],
)
def test_llm_failure_that_resists_description(harness, exc, message):
    harness.news_kr = KR_NEWS
    harness.ask = exc

    saved = harness.run(markets=["KR"], dry_run=True)

    kr = row(saved, "KR")
    assert kr["reason_code"] == "LLM_CALL_FAILED"  # still the LLM's failure
    assert kr["reason_detail"]["error_type"] == type(exc).__name__
    assert kr["reason_detail"]["message"] == message
    assert kr["reason_detail"]["caused_by"] == []
    assert error_for(saved, "KR")["reason_code"] == "LLM_CALL_FAILED"


@pytest.mark.parametrize(
    "exc, message",
    [(UnprintableError(), ""), (UnreadableCauseError("boom"), "boom")],
)
def test_exception_out_of_discover_that_resists_description(
    harness, monkeypatch, exc, message
):
    engine = types.SimpleNamespace(discover=lambda market: (_ for _ in ()).throw(exc))
    monkeypatch.setattr("discovery.discovery_engine.DiscoveryEngine", lambda: engine)

    saved = harness.run(markets=["KR"], dry_run=True)

    kr = row(saved, "KR")
    assert kr["reason_code"] == "DISCOVERY_EXCEPTION"
    assert kr["reason_detail"]["error_type"] == type(exc).__name__
    assert error_for(saved, "KR")["error"] == message
    assert final_status(harness) == "completed_with_errors"


class FakeResponse:
    def __init__(self, status_code: int, payload) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


@pytest.mark.parametrize(
    "body, payload, expected",
    [
        ({"error": {}}, {"error": {"type": "response_type"}}, "response_type"),
        (
            {"error": {"code": "body_code"}},
            {"error": {"type": "response_type"}},
            "response_type",
        ),
        (
            {"error": {"type": "body_type"}},
            {"error": {"type": "response_type"}},
            "body_type",
        ),
        ({"error": {"code": 429}}, {"error": {}}, "429"),
        (None, {"error": {"code": "response_code"}}, "response_code"),
        ({"type": "error"}, None, None),  # top-level body["type"] is not the error type
        ("not a dict", "not a dict", None),
    ],
)
def test_api_error_type_reading_order(harness, body, payload, expected):
    """body.error.type, response.error.type, body.error.code, response.error.code."""
    exc = RuntimeError("OpenRouter error: synthetic")
    exc.body = body
    exc.response = FakeResponse(502, payload)
    harness.news_kr = KR_NEWS
    harness.ask = exc

    saved = harness.run(markets=["KR"], dry_run=True)

    detail = row(saved, "KR")["reason_detail"]
    assert detail["api_error_type"] == expected
    assert detail["http_status"] == 502
    assert detail["provider"] == "openrouter"


# ── 14. invalid responses keep the values the old keys had before K-0B ───────

SCENARIO = {"name": "기준", "prob": 100, "description": "유지"}

# (response text, kind, analysis, scenarios). The last two columns are what
# HEAD ae76b1c returned for the same response: breakage that used to end in the
# "AI 분석 실패" exception path gave "" and [], the rest kept the parsed values.
INVALID_RESPONSES = [
    (
        _json(
            {
                "summary": "s",
                "companies": [KR_ANALYSIS["companies"][0], "bad"],
                "scenarios": [SCENARIO],
            }
        ),
        "company_entry_not_object",
        "",
        [],
    ),
    (
        _json({"summary": "s", "companies": [1], "scenarios": [1]}),
        "company_entry_not_object",
        "",
        [],
    ),
    (
        _json({"summary": "s", "companies": None, "scenarios": [SCENARIO]}),
        "companies_missing",
        "",
        [],
    ),
    (
        _json({"summary": "s", "scenarios": [SCENARIO]}),
        "companies_missing",
        "s",
        [SCENARIO],
    ),
    (
        _json(
            {"summary": "s", "companies": {"name": "삼성전자"}, "scenarios": [SCENARIO]}
        ),
        "companies_not_list",
        "",
        [],
    ),
    (
        _json({"summary": "s", "companies": {}, "scenarios": [SCENARIO]}),
        "companies_not_list",
        "s",
        [SCENARIO],
    ),
    (
        _json({"summary": "s", "companies": "", "scenarios": [SCENARIO]}),
        "companies_not_list",
        "s",
        [SCENARIO],
    ),
    (
        _json({"summary": "s", "companies": 5, "scenarios": [SCENARIO]}),
        "companies_not_list",
        "",
        [],
    ),
    ("[1, 2, 3]", "not_object", "", []),
    ("   ", "empty_response", "   ", []),
    ("", "empty_response", "", []),
    ("not json {", "parse_error", "not json {", []),
]


@pytest.mark.parametrize("response, kind, analysis, scenarios", INVALID_RESPONSES)
def test_invalid_response_keeps_old_key_values(
    harness, response, kind, analysis, scenarios
):
    from discovery.discovery_engine import DiscoveryEngine

    harness.news_kr = KR_NEWS
    harness.ask = lambda prompt: response

    result = DiscoveryEngine().discover(market="KR")

    assert result["reason_code"] == "LLM_JSON_INVALID"
    assert result["reason_detail"]["kind"] == kind
    # old keys
    assert result["news_count"] == 3
    assert result["analysis"] == analysis
    assert result["companies"] == []
    assert result["scenarios"] == scenarios
    assert result["news"] == KR_NEWS


@pytest.mark.parametrize(
    "companies, reason_code",
    [
        (None, "LLM_JSON_INVALID"),  # the key is absent
        ([], "NO_CANDIDATES"),
        ([{"name": "블룸버그", "ticker": None}], "FILTERED_TO_ZERO"),
    ],
)
def test_print_error_does_not_replace_an_established_reason(
    harness, companies, reason_code
):
    """A zero-company reason is settled, then a scenario entry cannot be printed.

    Before K-0B all three raised AttributeError out of discover().
    """
    from discovery.discovery_engine import DiscoveryEngine

    payload: dict = {"summary": "s", "scenarios": [1]}
    if companies is not None:
        payload["companies"] = companies
    harness.news_kr = KR_NEWS
    harness.ask = lambda prompt: _json(payload)

    result = DiscoveryEngine().discover(market="KR")

    assert result["reason_code"] == reason_code
    assert result["companies"] == []
    assert result["analysis"] == "s"
    assert result["news"] == KR_NEWS


def test_print_error_on_the_normal_path_still_propagates(harness):
    """Unchanged from before K-0B: valid companies, unprintable scenario entry."""
    from discovery.discovery_engine import DiscoveryEngine

    harness.news_kr = KR_NEWS
    harness.ask = lambda prompt: _json(
        {"summary": "s", "companies": [KR_ANALYSIS["companies"][0]], "scenarios": [1]}
    )

    with pytest.raises(AttributeError):
        DiscoveryEngine().discover(market="KR")
