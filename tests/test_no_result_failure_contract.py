"""K-0C no_result failure contract: every failed valuation leaves a reason.

Backstory: across 25 weekly summaries 59 of 108 valuations ended as
``no_result`` with nothing recorded. ``auto_fetch()`` printed the cause and
returned ``{}``, ``auto_analyze()`` turned that into ``None`` and
``_run_valuation()`` kept only ``status: "no_result"``. Replaying the lookup
against a cached registry showed that KR companies were searched by their
English name: ``Samsung Electronics`` matched nothing, and ``SK Hynix`` and
``LG Electronics`` resolved to *other* listed companies (``SK``, ``LG``).

These tests run the real ``run_weekly()`` with the real
``pipeline.profile_generator`` and read the summary file that was written.
Nothing here may touch the network, the LLM, the database, mail, blog
posting, ``logs/``, ``.cache/``, ``profiles/`` or ``valuation-results/`` --
see the ``harness`` fixture. Every replaced boundary records unexpected calls
and the fixture fails at teardown if there were any.
"""

from __future__ import annotations

import copy
import importlib
import json
import logging
import os
import sys
import tempfile
import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

import pytest
import yaml

# ── synthetic inputs ─────────────────────────────────────────────────────────

FIXED_TODAY = date(2026, 11, 13)

PRICE = 100_000.0
SHARES = 70_000_000

FIN = {
    2023: dict(
        revenue=8_000_000,
        op=700_000,
        net_income=560_000,
        assets=18_000_000,
        liabilities=11_000_000,
        equity=7_000_000,
        dep=450_000,
        amort=90_000,
        gross_borr=4_800_000,
        net_borr=3_900_000,
        de_ratio=68.6,
        capex=650_000,
    ),
    2024: dict(
        revenue=9_000_000,
        op=850_000,
        net_income=680_000,
        assets=19_000_000,
        liabilities=11_500_000,
        equity=7_500_000,
        dep=480_000,
        amort=95_000,
        gross_borr=4_900_000,
        net_borr=3_950_000,
        de_ratio=65.3,
        capex=680_000,
    ),
    2025: dict(
        revenue=10_000_000,
        op=1_000_000,
        net_income=800_000,
        assets=20_000_000,
        liabilities=12_000_000,
        equity=8_000_000,
        dep=500_000,
        amort=100_000,
        gross_borr=5_000_000,
        net_borr=4_000_000,
        de_ratio=62.5,
        capex=700_000,
    ),
}

SHARES_INFO = dict(
    shares_total=SHARES,
    shares_ordinary=SHARES,
    shares_preferred=0,
    treasury_shares=0,
    price=PRICE,
    market_cap=PRICE * SHARES / 1_000_000,  # fetch_shares() reports 백만원 / $M
    currency="KRW",
    beta=1.1,
)

SEGMENTS = [
    {"code": "CORE", "name": "Core Devices", "revenue_share_pct": 70},
    {"code": "SVC", "name": "Services", "revenue_share_pct": 30},
]

PEERS_BATCH = {
    "CORE": {
        "peers": [
            {"name": "PeerA", "ev_ebitda": 8.0, "notes": ""},
            {"name": "PeerB", "ev_ebitda": 9.0, "notes": ""},
        ],
        "recommended_multiple": 8.5,
    },
    "SVC": {
        "peers": [{"name": "PeerC", "ev_ebitda": 12.0, "notes": ""}],
        "recommended_multiple": 12.0,
    },
}

SCENARIOS = {
    "scenarios": [
        {
            "code": "Base",
            "name": "Base",
            "prob": 50,
            "description": "base",
            "drivers": {
                "growth_adj_pct": 0,
                "terminal_growth_adj": 0.0,
                "market_sentiment_pct": 0,
            },
        },
        {
            "code": "Bull",
            "name": "Bull",
            "prob": 25,
            "description": "bull",
            "drivers": {
                "growth_adj_pct": 30,
                "terminal_growth_adj": 0.5,
                "market_sentiment_pct": 10,
            },
        },
        {
            "code": "Bear",
            "name": "Bear",
            "prob": 25,
            "description": "bear",
            "drivers": {
                "growth_adj_pct": -30,
                "terminal_growth_adj": -0.5,
                "market_sentiment_pct": -10,
            },
        },
    ],
    "news_drivers": [],
    "optionality_segments": [],
}

SECRETS = [
    "ABCDEF0123456789ABCDEF0123456789ABCDEF01",  # DART-style key in a URL query
    "s3cr3t-json-value",
    "tok.en-VALUE_3",
    "sk-ant-SECRETSECRET4",
    "hunter2secret",
]

LEAKY_MESSAGE = (
    "GET https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    "?crtfc_key=ABCDEF0123456789ABCDEF0123456789ABCDEF01&corp_code=1 failed;\n"
    'headers={"api_key": "s3cr3t-json-value", '
    '"Authorization": "Bearer tok.en-VALUE_3"}\tkey sk-ant-SECRETSECRET4 '
    "PASSWORD: hunter2secret"
)

# Characterization values for the synthetic company above (the same on HEAD).
PINNED_WEIGHTED_VALUE = 164417.142857143
PINNED_QUALITY_GRADE = "C"
PINNED_DRAFT_VALUE = 151657.142857143
PINNED_DRAFT_GRADE = "F"

_MISSING = object()


def co(name: str, ticker: str | None, reason: str = "실적") -> dict:
    return {"name": name, "ticker": ticker, "domain": None, "reason": reason}


def kr_identity(name: str = "SynCo", ticker: str | None = "123456", **kwargs):
    from pipeline.data_fetcher import CompanyIdentity

    kwargs.setdefault("corp_code", "00999999")
    kwargs.setdefault("legal_status", "상장")
    return CompanyIdentity(name, "KR", ticker=ticker, **kwargs)


def us_identity(
    name: str = "SynUS Inc.", ticker: str = "SYNU", analysis_date=None, **kwargs
):
    from pipeline.data_fetcher import CompanyIdentity

    kwargs.setdefault("cik", "1234567")
    identity = CompanyIdentity(name, "US", ticker=ticker, **kwargs)
    if analysis_date is not None:
        # CompanyIdentity has no such attribute and nothing in pipeline/ sets
        # it, so the TTM branch only gets past its first line when a test does.
        identity.analysis_date = analysis_date
    return identity


def beta_observation(as_of: date):
    from schemas.provenance import BetaObservation, Source

    return BetaObservation(
        equity_beta=Source(
            value=1.10,
            source="yfinance",
            url="https://finance.yahoo.com/quote/X",
            as_of=as_of,
            method="derived",
            derived_from=["yfinance:X:adj_close"],
        ),
        window_start=as_of - timedelta(days=728),
        window_end=as_of,
        frequency="weekly",
        benchmark="^KS11",
        observation_count=104,
        calculation_method="ols_weekly_log_returns_adjusted_close",
    )


class _FixedDate(date):
    """date.today() pinned so generated profiles do not depend on the clock."""

    @classmethod
    def today(cls):
        return cls(FIXED_TODAY.year, FIXED_TODAY.month, FIXED_TODAY.day)


class UnprintableError(Exception):
    def __str__(self) -> str:
        raise ValueError("__str__ failed")


class UnreadableCauseError(Exception):
    @property
    def __cause__(self):
        raise RuntimeError("__cause__ failed")


# ── harness ──────────────────────────────────────────────────────────────────


class Harness:
    """Replaces every side-effecting boundary below run_weekly(); fails closed."""

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "repo"  # stands in for the repository root
        self.results = tmp_path / "results"
        self.sys_tmp = tmp_path / "sys_tmp"
        self.out = tmp_path / "out"  # output_dir for direct auto_analyze() calls
        for folder in (self.root / "profiles", self.results, self.sys_tmp, self.out):
            folder.mkdir(parents=True)
        self.discovered: dict[str, list[dict]] = {"KR": [], "US": []}
        # query -> CompanyIdentity | None | Exception
        self.identity: dict[str, object] = {}
        # identity.name -> dict | Exception (defaults: FIN / SHARES_INFO)
        self.financials: dict[str, object] = {}
        self.shares: dict[str, object] = {}
        # boundary -> Exception, or {key: Exception}
        self.raises: dict[str, object] = {}
        # boundary -> value or callable (also un-blocks a fail-closed boundary)
        self.returns: dict[str, object] = {}
        self.delay: dict[str, float] = {}  # query -> seconds spent in identify
        self.calls: list[tuple[str, object]] = []
        self.unexpected: list[str] = []
        self.alerts: list[tuple[str, str]] = []
        self.mail: list[dict] = []
        self.posts: list[str] = []
        self.db_updates: list[tuple[str, dict]] = []
        # remaining 0 -> the scenario repair call is skipped, never attempted
        self.usage: dict = {
            "anthropic": {"calls": 0, "cache_hits": 0, "limit": 50, "remaining": 0}
        }
        self.remaining_quota: dict = {"anthropic": 1000}
        self._lock = threading.Lock()
        self.wr = None
        self.pg = None
        self.real_identify = None

    # -- boundary plumbing --

    def reach(self, boundary: str, key: object = None) -> None:
        with self._lock:
            self.calls.append((boundary, key))
        exc = self.raises.get(boundary)
        if isinstance(exc, dict):
            exc = exc.get(key)
        if exc is not None:
            raise exc

    def called(self, boundary: str) -> list:
        return [key for name, key in self.calls if name == boundary]

    def _unexpected(self, what: str):
        with self._lock:
            self.unexpected.append(what)
        raise AssertionError(f"unexpected call: {what}")

    def closed(self, name: str):
        """A boundary nobody may reach unless the test sets returns[name]."""

        def boundary(*args, **kwargs):
            value = self.returns.get(name, _MISSING)
            if value is _MISSING:
                self._unexpected(name)
            self.reach(name, args[0] if args else None)
            return value(*args, **kwargs) if callable(value) else value

        return boundary

    def value(self, name: str, default):
        value = self.returns.get(name, default)
        return copy.deepcopy(value)

    # -- running --

    def discover(self, market: str) -> dict:
        companies = [dict(c) for c in self.discovered.get(market, [])]
        news = [
            {
                "title": f"{c['name']} quarterly results",
                "description": "",
                "link": f"https://news.example/{market}/{i}",
                "pub_date": "2020-01-06T09:00:00",
                "source": "naver" if market == "KR" else "google_rss",
            }
            for i, c in enumerate(companies)
        ]
        return {
            "news_count": len(news),
            "analysis": "",
            "companies": companies,
            "scenarios": [],
            "news": news,
            "reason_code": None,
            "reason_detail": {},
            "path": "news_llm",
            "path_fallback": None,
            "candidates_raw": len(companies),
            "candidates_filtered_out": 0,
        }

    def run(self, markets=("KR",), dry_run: bool = False, **kwargs) -> dict:
        """Run the real run_weekly() and return the summary *as written to disk*."""
        summary = self.wr.run_weekly(markets=list(markets), dry_run=dry_run, **kwargs)
        path = Path(summary["week_dir"]) / "_weekly_summary.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def one(self, company: dict, identity=_MISSING, market: str = "KR") -> None:
        """Select one company; ``identity`` is what identify() answers for it."""
        self.discovered[market] = [company]
        if identity is not _MISSING:
            ticker = str(company.get("ticker") or "")
            query = ticker if market == "US" and ticker else company["name"]
            self.identity[query] = identity

    def profiles(self) -> list[str]:
        base = self.root / "profiles"
        return sorted(p.relative_to(base).as_posix() for p in base.rglob("*.yaml"))

    def workbooks(self) -> list[str]:
        return sorted(p.name for p in self.results.rglob("*.xlsx"))


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
    h = Harness(tmp_path)

    monkeypatch.setenv("BVT_TELEMETRY", "0")
    # _ssl_fix returns early when this is set. pipeline/yfinance_fetcher.py sets
    # it at import time whenever the certifi path is not ASCII, whatever the
    # current value, so pre-seed the very value it would write: monkeypatch
    # then restores the original state when the fixture ends.
    ca_bundle = os.path.join(
        os.environ.get("ALLUSERSPROFILE", "C:\\ProgramData"), "python-ssl", "cacert.pem"
    )
    monkeypatch.setenv("CURL_CA_BUNDLE", os.environ.get("CURL_CA_BUNDLE") or ca_bundle)
    # cli.py and scheduler.weekly_run load the repository's .env on first import.
    try:
        import dotenv
    except ImportError:
        dotenv = None
    if dotenv is not None:
        monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)

    wr = importlib.import_module("scheduler.weekly_run")
    pg = importlib.import_module("pipeline.profile_generator")
    cli = importlib.import_module("cli")
    orchestrator = importlib.import_module("orchestrator")
    h.wr, h.pg = wr, pg

    # After the imports: another test module may already have loaded keys.
    for name in list(os.environ):
        upper = name.upper()
        if any(
            marker in upper
            for marker in (
                "OPENROUTER",
                "ANTHROPIC_API",
                "NAVER",
                "DART_API",
                "SUPABASE",
                "GMAIL",
                "RESEND",
                "FRED_API",
                "DUMP_NEWS_TITLES",
                "BVT_TELEMETRY_PATH",
            )
        ):
            monkeypatch.delenv(name, raising=False)

    # where files go, and what "today" is
    monkeypatch.setattr(pg, "_PROJECT_ROOT", h.root)
    monkeypatch.setattr(pg, "date", _FixedDate)
    monkeypatch.setattr(tempfile, "tempdir", str(h.sys_tmp))
    monkeypatch.setattr(wr, "_RESULTS_BASE", h.results)
    monkeypatch.setattr(wr, "_setup_logging", lambda: None)

    # discovery: fixed result (K-0B covers discover() itself)
    monkeypatch.setattr(
        "discovery.discovery_engine.DiscoveryEngine.discover",
        lambda self, market="KR": h.discover(market),
    )

    # identification, financials, shares
    from pipeline import data_fetcher
    from pipeline.data_fetcher import DataFetcher

    h.real_identify = DataFetcher.identify

    def identify(self, query, market_hint=None, ticker=None):
        h.reach("identify", query)
        time.sleep(h.delay.get(query, 0))
        value = h.identity.get(query, _MISSING)
        if value is _MISSING:
            h._unexpected(f"identify({query!r})")
        if isinstance(value, BaseException):
            raise value
        return value

    def fetch_financials(self, identity, years=None):
        h.reach("financials", identity.name)
        value = h.financials.get(identity.name, FIN)
        if isinstance(value, BaseException):
            raise value
        return value if not isinstance(value, dict) else copy.deepcopy(value)

    def fetch_shares(self, identity):
        h.reach("shares", identity.name)
        value = h.shares.get(identity.name, SHARES_INFO)
        if isinstance(value, BaseException):
            raise value
        return copy.deepcopy(value)

    monkeypatch.setattr(DataFetcher, "identify", identify)
    monkeypatch.setattr(DataFetcher, "fetch_financials", fetch_financials)
    monkeypatch.setattr(DataFetcher, "fetch_shares", fetch_shares)

    # registry, EDGAR, Yahoo: closed unless a test opens them
    from pipeline import (
        beta_observation as beta_module,
        dart_client,
        edgar_client,
        edgar_parser,
        macro_data,
        market_signals,
        yahoo_finance,
    )

    monkeypatch.setattr(
        dart_client, "_load_corp_code_xml", h.closed("dart._load_corp_code_xml")
    )
    monkeypatch.setattr(
        edgar_client, "search_company", h.closed("edgar.search_company")
    )
    for name in ("get_stock_info", "get_quote_summary"):
        monkeypatch.setattr(yahoo_finance, name, h.closed(f"yahoo.{name}"))
    if data_fetcher.yfinance_fetcher is not None:
        for name in (
            "fetch_market_data",
            "fetch_financials",
            "resolve_kr_ticker",
            "get_exchange_segment",
        ):
            monkeypatch.setattr(
                data_fetcher.yfinance_fetcher, name, h.closed(f"yf.{name}")
            )

    def industry(identifier):
        h.reach("industry", identifier)
        return h.value(
            "industry",
            {
                "induty_code": "264",
                "induty_name": "전자부품 제조업",
                "sic": "3571",
                "sicDescription": "Electronic Computers",
            },
        )

    monkeypatch.setattr(dart_client, "get_single_company_info", industry)
    monkeypatch.setattr(edgar_client, "get_submissions", industry)

    def parse_ttm(cik, latest, computed_as_of=None):
        h.reach("ttm", cik)
        return h.value("ttm", None)

    monkeypatch.setattr(edgar_parser, "parse_ttm_financials", parse_ttm)

    def collect_beta(ticker, market, analysis_date, *, benchmark=None):
        h.reach("beta", ticker)
        observed = analysis_date - timedelta(days=3)
        return beta_observation(observed), "digest-k0c", "snapshot.json"

    monkeypatch.setattr(beta_module, "collect_beta_observation", collect_beta)

    def terminal_growth(market="KR"):
        h.reach("terminal_growth", market)
        return 2.0

    def diluted_shares(ticker, market="US"):
        h.reach("diluted_shares", ticker)
        return None

    monkeypatch.setattr(macro_data, "get_terminal_growth", terminal_growth)
    monkeypatch.setattr(macro_data, "get_diluted_shares", diluted_shares)

    # LLM: the analyst is a fake, the transport is closed
    import ai.analyst
    import ai.llm_client

    for module in (ai.llm_client, ai.analyst):
        for name in ("ask", "ask_structured"):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, h.closed(f"llm.{name}"))

    class FakeAnalyst:
        def __init__(self, model: str = ""):
            h.reach("ai.init")

        def classify_segments(self, company_name, revenue_breakdown):
            h.reach("ai.segments", company_name)
            return {"segments": h.value("ai.segments", SEGMENTS)}

        def recommend_peers_batch(self, company_name, segments, market="KR"):
            h.reach("ai.peers_batch", company_name)
            return h.value("ai.peers_batch", PEERS_BATCH)

        def recommend_peers(self, company_name, code, name, description=""):
            h.reach("ai.peers", code)
            return h.value("ai.peers", PEERS_BATCH)[code]

        def suggest_wacc(self, company_name, de_ratio, industry="", market="KR"):
            h.reach("ai.wacc", company_name)
            return h.value("ai.wacc", {"wacc_estimate": 9.1})

        def design_scenarios(self, company_name, legal_status, key_issues, **kwargs):
            h.reach("ai.scenarios", company_name)
            return h.value("ai.scenarios", SCENARIOS)

        def _ask_json(self, *args, **kwargs):
            h._unexpected("ai._ask_json (scenario repair)")

    monkeypatch.setattr(ai.analyst, "AIAnalyst", FakeAnalyst)

    # news, key issues, market signals, method selection
    def collect_for_company(self, name, market):
        h.reach("news", name)
        return h.value("news", [])

    def key_issues(news, company_name, market="KR"):
        h.reach("key_issues", company_name)
        return "- synthetic key issue"

    def market_signal(**kwargs):
        h.reach("market_signals", kwargs.get("company_name"))
        return None

    monkeypatch.setattr(
        "discovery.news_collector.NewsCollector.collect_for_company",
        collect_for_company,
    )
    monkeypatch.setattr("discovery.discovery_engine.summarize_key_issues", key_issues)
    monkeypatch.setattr(market_signals, "fetch_market_signals", market_signal)

    import engine.method_selector as method_selector

    real_suggest = method_selector.suggest_method

    def suggest_method(*args, **kwargs):
        h.reach("method_selection")
        return real_suggest(*args, **kwargs)

    monkeypatch.setattr(method_selector, "suggest_method", suggest_method)

    # valuation and output stay real; only their IO edges are replaced
    import output.excel_builder as excel_builder
    import valuation_runner

    real_run = valuation_runner.run_valuation
    real_export = excel_builder.export

    def run_valuation(vi, *args, **kwargs):
        h.reach("run_valuation", vi.company.name)
        return real_run(vi, *args, **kwargs)

    def export(vi, result, output_dir=None, *args, **kwargs):
        h.reach("export", vi.company.name)
        return real_export(vi, result, output_dir, *args, **kwargs)

    def market_compare(vi, result, use_live_price=False):
        h.reach("market_compare", vi.company.name)
        return result

    def save_to_db(vi, result, profile_path=None):
        h.reach("db_save", vi.company.name)
        return None

    monkeypatch.setattr(valuation_runner, "run_valuation", run_valuation)
    monkeypatch.setattr(excel_builder, "export", export)
    monkeypatch.setattr(cli, "_fetch_and_compare_market_price", market_compare)
    monkeypatch.setattr(orchestrator, "_save_to_db", save_to_db)

    # alerts, DB, storage, quota, scoring
    monkeypatch.setattr(
        wr, "_alert", lambda phase, error: h.alerts.append((phase, error))
    )
    monkeypatch.setattr(wr, "_save_run_start", lambda markets: "run-k0c")
    monkeypatch.setattr(wr, "_upload_excels_to_storage", lambda *a, **k: None)
    monkeypatch.setitem(
        sys.modules,
        "db.repository",
        _module(
            "db.repository",
            update_discovery_run=lambda run_id, updates: h.db_updates.append(
                (run_id, updates)
            ),
            # the workbook's history sheet reads this; an empty history is a
            # normal answer, an ImportError would only hide the boundary
            list_valuation_history=lambda **kwargs: [],
        ),
    )
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
    monkeypatch.setattr(
        "scheduler.scoring._fetch_market_cap_usd", lambda ticker, market: None
    )

    # mail and posting: the real modules are never imported
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
    leftovers = sorted(p.name for p in h.sys_tmp.iterdir())
    assert leftovers == [], f"temporary files were left behind: {leftovers}"


# ── helpers ──────────────────────────────────────────────────────────────────

LEGACY_BASE_KEYS = {"company", "ticker", "reason", "market", "status"}
LEGACY_RESULT_KEYS = LEGACY_BASE_KEYS | {
    "draft",
    "quality_grade",
    "draft_blockers",
    "excel_path",
    "summary_md",
    "market_cap_usd",
    "scenario_validation",
    "scenario_validation_codes",
}
NEW_KEYS = {"reason_code", "severity", "reason_detail", "degraded", "degraded_detail"}
FETCH_AND_LATER = (
    "financials",
    "shares",
    "industry",
    "terminal_growth",
    "ai.init",
    "run_valuation",
    "export",
    "db_save",
)


def entry(saved: dict, company: str) -> dict:
    found = [v for v in saved["valuations"] if v["company"] == company]
    assert len(found) == 1, f"expected one valuation for {company}: {found}"
    return found[0]


def verrors(saved: dict, company: str | None = None) -> list[dict]:
    return [
        e
        for e in saved["errors"]
        if e.get("phase") == "valuation"
        and (company is None or e.get("company") == company)
    ]


def verror(saved: dict, company: str) -> dict:
    found = verrors(saved, company)
    assert len(found) == 1, f"expected one valuation error for {company}: {found}"
    return found[0]


def final_status(h: Harness) -> str:
    assert len(h.db_updates) == 1
    run_id, payload = h.db_updates[0]
    assert run_id == "run-k0c"
    return payload["status"]


def assert_stopped_before(h: Harness, boundaries=FETCH_AND_LATER) -> None:
    reached = {name for name, _ in h.calls}
    assert reached.isdisjoint(boundaries), sorted(reached & set(boundaries))
    assert h.profiles() == []
    assert h.workbooks() == []


def assert_no_result(saved: dict, h: Harness, company: str, code: str) -> dict:
    item = entry(saved, company)
    assert item["status"] == "no_result"
    assert (item["reason_code"], item["severity"]) == (code, "failure")
    assert set(item) >= LEGACY_BASE_KEYS | NEW_KEYS
    err = verror(saved, company)
    assert (err["reason_code"], err["severity"]) == (code, "failure")
    assert (err["company"], err["ticker"], err["market"]) == (
        item["company"],
        item["ticker"],
        item["market"],
    )
    assert err["error"] and not any(ch in err["error"] for ch in "\r\n\t")
    return item


# ── 0. characterization: must pass before and after K-0C ─────────────────────


def test_normal_success_keeps_legacy_values(harness):
    harness.one(co("SynCo", "123456"), kr_identity())

    saved = harness.run()

    item = entry(saved, "SynCo")
    assert set(item) >= LEGACY_RESULT_KEYS
    assert (item["status"], item["draft"], item["draft_blockers"]) == (
        "success",
        False,
        [],
    )
    assert (item["ticker"], item["market"], item["reason"]) == ("123456", "KR", "실적")
    assert item["scenario_validation"] == "ok"
    assert item["scenario_validation_codes"] == []
    assert item["quality_grade"] in {"A", "B", "C", "D"}
    assert Path(item["excel_path"]).exists()
    assert saved["errors"] == []
    assert saved["status_summary"] == {
        "total": 1,
        "success": 1,
        "failed": 0,
        "draft_blocked": 0,
    }
    assert final_status(harness) == "completed"
    assert harness.profiles() == ["123456.yaml"]
    profile = yaml.safe_load(
        (harness.root / "profiles" / "123456.yaml").read_text(encoding="utf-8")
    )
    assert (profile["draft"], profile["generated"], profile["curated"]) == (
        False,
        "auto",
        False,
    )
    assert profile["company"]["analysis_date"] == FIXED_TODAY.isoformat()
    assert sorted(profile["segments"]) == ["CORE", "SVC"]
    assert profile["beta_provenance"]["source_hash"] == "digest-k0c"
    assert len(harness.mail) == 1 and harness.posts == ["wp", "naver"]
    assert harness.alerts == []


def test_normal_draft_keeps_legacy_values(harness):
    """No exception anywhere, but no peers: an ordinary blocked draft."""
    harness.one(co("SynCo", "123456"), kr_identity())
    harness.returns["ai.peers_batch"] = {
        code: {"peers": [], "recommended_multiple": 9.0} for code in ("CORE", "SVC")
    }

    saved = harness.run()

    item = entry(saved, "SynCo")
    assert (item["status"], item["draft"]) == ("draft_blocked", True)
    assert item["draft_blockers"]
    assert saved["errors"] == []
    assert final_status(harness) == "completed"
    assert harness.mail == [] and harness.posts == []
    assert [phase for phase, _ in harness.alerts] == ["Draft Gate"]


def test_normal_draft_values_are_pinned(harness):
    """The ordinary draft (no peers): its numbers too, before and after."""
    harness.identity["SynCo"] = kr_identity()
    harness.returns["ai.peers_batch"] = {
        code: {"peers": [], "recommended_multiple": 9.0} for code in ("CORE", "SVC")
    }

    result = harness.pg.auto_analyze(
        "SynCo",
        output_dir=str(harness.out),
        scored_data={"market": "KR", "ticker": "123456"},
    )

    assert type(result).__name__ == "AnalyzeResult"
    assert result.result.draft is True
    assert result.result.weighted_value == pytest.approx(PINNED_DRAFT_VALUE, rel=1e-9)
    assert result.result.quality.grade == PINNED_DRAFT_GRADE
    assert list(result.result.investability_blockers) != []
    assert result.validation_report.status == "ok"
    assert Path(result.excel_path).exists()


def test_unreadable_cause_was_and_stays_failed(harness):
    """HEAD never read __cause__, so this exception was recorded already."""
    harness.one(co("SynCo", "123456"), UnreadableCauseError("plain failure"))

    saved = harness.run()

    item = entry(saved, "SynCo")
    assert (item["status"], item["error"]) == ("failed", "plain failure")
    assert verror(saved, "SynCo")["error"] == "plain failure"


def test_cli_path_never_checks_the_ticker(harness, tmp_path):
    """auto_analyze() without scored_data: any resolved ticker is accepted."""
    harness.identity["SynCo"] = kr_identity(ticker="654321")

    result = harness.pg.auto_analyze("SynCo", output_dir=str(harness.out))

    assert result is not None and result.vi.company.ticker == "654321"
    assert harness.profiles() == ["654321.yaml"]


def test_normal_result_values_are_pinned(harness):
    """The numbers themselves and every AnalyzeResult field, before and after."""
    harness.identity["SynCo"] = kr_identity()

    result = harness.pg.auto_analyze(
        "SynCo",
        output_dir=str(harness.out),
        scored_data={"market": "KR", "ticker": "123456"},
    )

    assert type(result).__name__ == "AnalyzeResult"
    assert set(vars(result)) == {
        "vi",
        "result",
        "excel_path",
        "summary_md",
        "validation_report",
    }
    assert (result.vi.company.name, result.vi.company.ticker) == ("SynCo", "123456")
    assert result.result.draft is False
    assert result.result.weighted_value == pytest.approx(
        PINNED_WEIGHTED_VALUE, rel=1e-9
    )
    assert result.result.quality.grade == PINNED_QUALITY_GRADE
    assert list(result.result.investability_blockers) == []
    assert result.validation_report.status == "ok"
    assert Path(result.excel_path).exists()
    assert isinstance(result.summary_md, str) and "SynCo" in result.summary_md


def test_selection_without_a_ticker_is_not_checked(harness):
    harness.one(co("SynCo", None), kr_identity(ticker="654321"))

    saved = harness.run()

    assert entry(saved, "SynCo")["status"] == "success"


def test_direct_calls_behave_as_before(harness, caplog):
    """No diagnostics bound: same return values, no extra log records."""
    pg = harness.pg
    harness.identity["Nobody"] = None
    doubled = dict(SHARES_INFO, shares_total=SHARES * 2, shares_ordinary=SHARES * 2)

    with caplog.at_level(logging.WARNING, logger="pipeline.profile_generator"):
        assert pg.auto_fetch("Nobody") == {}
        assert pg._generate_draft_profile(kr_identity(), FIN, doubled) is None
        assert pg._generate_draft_profile(kr_identity(), {}, SHARES_INFO) is None

    assert [r for r in caplog.records if r.name == "pipeline.profile_generator"] == []
    assert harness.profiles() == []

    harness.raises["industry"] = RuntimeError("exception text must not enter logs")
    with caplog.at_level(logging.WARNING, logger="pipeline.profile_generator"):
        metadata = pg._fetch_industry_metadata(kr_identity())
    assert (metadata["industry_code"], metadata["industry_source"]) == (None, None)
    records = [r for r in caplog.records if r.name == "pipeline.profile_generator"]
    assert len(records) == 1  # the one warning HEAD logged, nothing added
    assert "must not enter" not in caplog.text


def test_unprotected_draft_profile_is_overwritten(harness):
    target = harness.root / "profiles" / "123456.yaml"
    target.write_text(
        "draft: true\ngenerated: auto\ncurated: false\n", encoding="utf-8"
    )
    harness.one(co("SynCo", "123456"), kr_identity())

    saved = harness.run()

    assert entry(saved, "SynCo")["status"] == "success"
    assert harness.profiles() == ["123456.yaml"]
    assert "segments" in yaml.safe_load(target.read_text(encoding="utf-8"))


# ── 1. identification ────────────────────────────────────────────────────────


def test_identity_not_found(harness):
    harness.one(co("Samsung Electronics", "005930"), None)

    saved = harness.run()

    item = assert_no_result(saved, harness, "Samsung Electronics", "IDENTITY_NOT_FOUND")
    assert item["reason_detail"] == {
        "query": "Samsung Electronics",
        "market_hint": "KR",
        "expected_ticker": "005930",
    }
    assert (item["degraded"], item["degraded_detail"]) == ([], [])
    assert_stopped_before(harness)
    assert final_status(harness) == "completed_with_errors"
    assert saved["valuation_status"]["by_reason"] == {"IDENTITY_NOT_FOUND": 1}


@pytest.mark.parametrize(
    "resolved, kind",
    [("003600", "ticker_differs"), (None, "resolved_ticker_missing")],
)
def test_identity_mismatch_blocks_before_financials(harness, resolved, kind, capsys):
    harness.one(co("SK Hynix", "000660"), kr_identity("SK Hynix", resolved))

    saved = harness.run()

    item = assert_no_result(saved, harness, "SK Hynix", "IDENTITY_MISMATCH")
    detail = item["reason_detail"]
    assert detail["kind"] == kind
    assert (detail["expected_ticker"], detail["resolved_ticker"]) == (
        "000660",
        resolved,
    )
    assert (detail["query"], detail["resolved_market"]) == ("SK Hynix", "KR")
    assert detail["resolved_corp_code"] == "00999999"
    assert_stopped_before(harness)
    assert "000660" in capsys.readouterr().out  # the one new console line


def test_abnormal_resolved_identifiers_are_not_persisted(harness):
    """What identify() newly reports is shape-checked; odd values are dropped."""
    odd = kr_identity("SK Hynix", "sk-ant-SECRETSECRET4", corp_code="hunter2secret")
    harness.one(co("SK Hynix", "000660"), odd)

    saved = harness.run()

    detail = assert_no_result(saved, harness, "SK Hynix", "IDENTITY_MISMATCH")[
        "reason_detail"
    ]
    assert detail["kind"] == "ticker_differs"
    assert detail["expected_ticker"] == "000660"
    assert detail["resolved_ticker"] == "<invalid>"
    assert detail["resolved_corp_code"] == "<invalid>"
    assert detail["resolved_cik"] is None
    _assert_no_secret(json.dumps(saved, ensure_ascii=False))


def test_normal_resolved_identifiers_are_kept(harness):
    """The shape check is a full match: normal values pass, a tail does not."""
    harness.discovered["US"] = [co("SynUS", "SYNU"), co("Other", "BRK.B")]
    harness.identity["SYNU"] = us_identity(ticker="OTHR")
    harness.identity["BRK.B"] = us_identity(
        "Tail Inc.", "OTHR; PASSWORD: hunter2secret", cik="12345678901"
    )

    saved = harness.run(markets=("US",))

    kept = entry(saved, "SynUS")["reason_detail"]
    assert (kept["resolved_ticker"], kept["resolved_cik"]) == ("OTHR", "1234567")
    assert (kept["resolved_market"], kept["market_hint"]) == ("US", "US")
    assert kept["resolved_corp_code"] is None
    tail = entry(saved, "Other")["reason_detail"]
    assert (tail["resolved_ticker"], tail["resolved_cik"]) == ("<invalid>", "<invalid>")
    assert tail["expected_ticker"] == "BRK.B"
    _assert_no_secret(json.dumps(saved, ensure_ascii=False))


@pytest.mark.parametrize(
    "expected, resolved, accepted",
    [
        ("005930", "005930", True),
        ("005930.KS", "005930", True),
        ("035720.kq", "035720", True),
        (" 005930 ", "005930", True),
        ("7203.T", "7203", True),
        ("BRK.B", "BRK-B", True),
        ("brk-b", "BRK.B", True),
        ("SYNU", "synu", True),
        ("005935", "005930", False),  # preferred share vs ordinary share
        ("AB.C", "ABC", False),
        ("SYNTH.T", "SYNTH", False),
        ("GOOGL", "GOOG", False),
        ("005930", None, False),
        ("N/A", "005930", False),  # a string is a symbol, never "absent"
        ("none", None, False),
        (None, "005930", True),  # nothing to check against
        ("", "005930", True),
        ("   ", "005930", True),
        (float("nan"), "005930", True),
        (Decimal("NaN"), "005930", True),
    ],
)
def test_ticker_comparison_rules(harness, expected, resolved, accepted):
    harness.identity["SynCo"] = kr_identity(ticker=resolved)

    fetched = harness.pg.auto_fetch("SynCo", market_hint="KR", expected_ticker=expected)

    assert bool(fetched) is accepted
    assert (harness.called("financials") != []) is accepted


# ── 2. financials, reconciliation, draft ─────────────────────────────────────


def test_financials_empty(harness):
    harness.one(co("SynCo", "123456"), kr_identity())
    harness.financials["SynCo"] = {}

    saved = harness.run()

    item = assert_no_result(saved, harness, "SynCo", "FINANCIALS_EMPTY")
    assert item["reason_detail"] == {
        "resolved_market": "KR",
        "resolved_ticker": "123456",
        "legal_status": "상장",
        "has_corp_code": True,
        "has_cik": False,
    }
    assert_stopped_before(harness, FETCH_AND_LATER[1:])


def test_reconciliation_blocked(harness):
    harness.one(co("SynCo", "123456"), kr_identity())
    harness.shares["SynCo"] = dict(
        SHARES_INFO, shares_total=SHARES * 2, shares_ordinary=SHARES * 2
    )

    saved = harness.run()

    item = assert_no_result(saved, harness, "SynCo", "RECONCILIATION_BLOCKED")
    checks = item["reason_detail"]["checks"]
    assert {c["check"] for c in checks} >= {"share_count"}
    assert all(c["rel_diff_pct"] is not None and c["message"] for c in checks)
    assert_stopped_before(
        harness, ("terminal_growth", "ai.init", "run_valuation", "export")
    )


class _TruthyEmpty(dict):
    """A financials mapping that is truthy and still has no years."""

    def __bool__(self) -> bool:
        return True


def test_draft_without_years(harness):
    harness.one(co("SynCo", "123456"), kr_identity())
    harness.financials["SynCo"] = _TruthyEmpty()

    saved = harness.run()

    assert_no_result(saved, harness, "SynCo", "DRAFT_NO_YEARS")
    assert_stopped_before(harness, ("ai.init", "run_valuation", "export"))


def test_draft_not_written_without_a_reason(harness, monkeypatch):
    harness.one(co("SynCo", "123456"), kr_identity())
    monkeypatch.setattr(
        harness.pg, "_generate_draft_profile", lambda *args, **kwargs: None
    )

    saved = harness.run()

    assert_no_result(saved, harness, "SynCo", "DRAFT_NOT_WRITTEN")


@pytest.mark.parametrize("fetched", [{}, {"identity": object(), "yaml_path": None}])
def test_auto_fetch_without_a_reason(harness, monkeypatch, fetched):
    harness.one(co("SynCo", "123456"))
    monkeypatch.setattr(harness.pg, "auto_fetch", lambda *args, **kwargs: fetched)

    saved = harness.run()

    item = assert_no_result(saved, harness, "SynCo", "REASON_NOT_REPORTED")
    assert item["reason_detail"] == {"reported": None}


@pytest.mark.parametrize(
    "reported, shown",
    [
        (_MISSING, None),
        (None, None),
        ("identity_not_found", "identity_not_found"),
        (404, "404"),
        ({"code": "X"}, "<dict>"),
        pytest.param(10**5000, "<int>", id="huge-int"),
        (True, "<bool>"),
        ("sk-ant-SECRETSECRET4", "sk-***"),  # free text: masked, not just trimmed
        ("ABCDEF0123456789ABCDEF0123456789ABCDEF01", "***"),
        ("BOGUS_CODE", "BOGUS_CODE"),
        ("UNKNOWN_LEGACY", "UNKNOWN_LEGACY"),
        ("VALUATION_EXCEPTION", "VALUATION_EXCEPTION"),
        ("ENRICHMENT_DEGRADED", "ENRICHMENT_DEGRADED"),
    ],
)
def test_producer_without_an_acceptable_reason(harness, monkeypatch, reported, shown):
    harness.one(co("SynCo", "123456"))

    def auto_analyze(query, output_dir=None, scored_data=None, *, diagnostics=None):
        if reported is not _MISSING:
            diagnostics["reason_code"] = reported
            diagnostics["reason_detail"] = {"query": "kept out"}
        return None

    monkeypatch.setattr(harness.pg, "auto_analyze", auto_analyze)

    saved = harness.run()

    item = assert_no_result(saved, harness, "SynCo", "REASON_NOT_REPORTED")
    assert item["reason_detail"] == {"reported": shown}


def test_a_bad_reason_code_is_never_rendered(harness, monkeypatch):
    """str() of a large container would build the whole text before any cut."""
    rendered = []

    class Loud(list):
        def __repr__(self) -> str:
            rendered.append("repr")
            return "x" * 10

        __str__ = __repr__

    def auto_analyze(query, output_dir=None, scored_data=None, *, diagnostics=None):
        diagnostics["reason_code"] = Loud(["x"] * 100_000)
        return None

    harness.one(co("SynCo", "123456"))
    monkeypatch.setattr(harness.pg, "auto_analyze", auto_analyze)

    saved = harness.run()

    item = assert_no_result(saved, harness, "SynCo", "REASON_NOT_REPORTED")
    assert item["reason_detail"] == {"reported": "<object>"}  # not even its name
    assert rendered == []


@pytest.mark.parametrize(
    "class_name",
    ["sk-ant-SECRETSECRET4", "first\nsecond", "N" * 1_000_000],
    ids=["secret-like", "line-break", "huge"],
)
def test_a_class_name_is_as_untrusted_as_any_text(harness, monkeypatch, class_name):
    """What stands in for an odd value is a fixed label, never the type's name."""
    odd = type(class_name, (), {})()

    def auto_analyze(query, output_dir=None, scored_data=None, *, diagnostics=None):
        diagnostics["reason_code"] = odd
        return None

    harness.one(co(odd, "123456"))  # the selection hands on an odd "name" too
    harness.discovered["KR"][0]["name"] = "SynCo"
    monkeypatch.setattr(harness.pg, "auto_analyze", auto_analyze)

    saved = harness.run()

    item = assert_no_result(saved, harness, "SynCo", "REASON_NOT_REPORTED")
    assert item["reason_detail"] == {"reported": "<object>"}
    assert harness.wr._selection_identifier(odd) == "<object>"
    wr = harness.wr
    assert (wr._type_name([]), wr._type_name({})) == ("<list>", "<dict>")
    assert (wr._type_name(True), wr._type_name(1.5)) == ("<bool>", "<float>")
    assert wr._number(-(10**5000)) is None and wr._number(float("nan")) is None
    assert wr._number(-3) == -3 and wr._number(True) is None
    text = json.dumps(saved, ensure_ascii=False)
    assert class_name[:20] not in text
    _assert_no_secret(text)


def test_oversized_identifiers_are_invalid_without_being_read(harness, monkeypatch):
    """Longer than the limit = invalid, blanks included; len() decides, not a scan."""

    def auto_analyze(query, output_dir=None, scored_data=None, *, diagnostics=None):
        diagnostics["reason_code"] = "IDENTITY_MISMATCH"
        diagnostics["reason_detail"] = {
            "kind": " " * 10_000_000,
            "resolved_ticker": " " * 121,
            "resolved_market": " " * 120,  # within the limit and blank: absent
            "resolved_corp_code": "0" * 10_000_000,
        }
        diagnostics["degraded"] = [{"step": "x" * 10_000_000}]
        return None

    harness.one(co("SynCo", "123456"))
    monkeypatch.setattr(harness.pg, "auto_analyze", auto_analyze)

    saved = harness.run()

    item = assert_no_result(saved, harness, "SynCo", "IDENTITY_MISMATCH")
    assert item["reason_detail"] == {
        "kind": "<invalid>",
        "resolved_ticker": "<invalid>",
        "resolved_market": None,
        "resolved_corp_code": "<invalid>",
    }
    assert item["degraded"] == ["<invalid>"]


def test_an_oversized_reason_code_is_not_accepted(harness, monkeypatch):
    def auto_analyze(query, output_dir=None, scored_data=None, *, diagnostics=None):
        diagnostics["reason_code"] = "IDENTITY_NOT_FOUND" + "A" * 10_000_000
        return None

    harness.one(co("SynCo", "123456"))
    monkeypatch.setattr(harness.pg, "auto_analyze", auto_analyze)

    saved = harness.run()

    item = assert_no_result(saved, harness, "SynCo", "REASON_NOT_REPORTED")
    assert item["reason_detail"] == {"reported": ""}  # one long token: masked away


def test_required_failures_have_distinct_codes(harness):
    harness.discovered["KR"] = [
        co("Alpha", "111111"),
        co("Bravo", "222222"),
        co("Charlie", "333333"),
        co("Delta", "444444"),
    ]
    harness.identity.update(
        {
            "Alpha": None,
            "Bravo": kr_identity("Bravo", "999999"),
            "Charlie": kr_identity("Charlie", "333333"),
            "Delta": kr_identity("Delta", "444444"),
        }
    )
    harness.financials["Charlie"] = {}
    harness.shares["Delta"] = dict(
        SHARES_INFO, shares_total=SHARES * 2, shares_ordinary=SHARES * 2
    )

    saved = harness.run()

    codes = {v["company"]: v["reason_code"] for v in saved["valuations"]}
    assert codes == {
        "Alpha": "IDENTITY_NOT_FOUND",
        "Bravo": "IDENTITY_MISMATCH",
        "Charlie": "FINANCIALS_EMPTY",
        "Delta": "RECONCILIATION_BLOCKED",
    }
    assert sorted(e["reason_code"] for e in verrors(saved)) == sorted(codes.values())
    assert harness.called("run_valuation") == []
    assert final_status(harness) == "completed_with_errors"
    status = saved["valuation_status"]
    assert status["contract"] == "k0c-1"
    assert (status["total"], status["by_status"]) == (4, {"no_result": 4})
    assert status["by_reason"] == {code: 1 for code in codes.values()}
    assert status["degraded_results"] == 0


# ── 3. the registry lookup that produced the 13 weeks of no_result ───────────


def _registry(*rows: tuple[str, ...]) -> ElementTree.Element:
    """Rows are (corp_name, stock_code) or (corp_name, stock_code, corp_eng_name)."""
    root = ElementTree.Element("result")
    for index, (name, stock_code, *english) in enumerate(rows):
        item = ElementTree.SubElement(root, "list")
        ElementTree.SubElement(item, "corp_code").text = f"{index:08d}"
        ElementTree.SubElement(item, "corp_name").text = name
        ElementTree.SubElement(item, "stock_code").text = stock_code
        if english:
            ElementTree.SubElement(item, "corp_eng_name").text = english[0]
    return root


# Korean and English names as the real registry carries them. The lookup used
# to read the Korean ones only.
REGISTRY_ROWS = (
    ("삼성전자", "005930", "SAMSUNG ELECTRONICS CO,.LTD"),
    ("SK", "003600", "SK Inc."),
    ("SK하이닉스", "000660", "SK hynix Inc."),
    ("LG", "003550", "LG Corp."),
    ("LG전자", "066570", "LG ELECTRONICS INC."),
    ("현대차", "005380", "HYUNDAI MOTOR CO"),
)


def _use_registry(harness, monkeypatch, rows=REGISTRY_ROWS) -> None:
    """Real DataFetcher.identify() over a synthetic registry."""
    from pipeline.data_fetcher import DataFetcher

    monkeypatch.setattr(DataFetcher, "identify", harness.real_identify)
    harness.returns["dart._load_corp_code_xml"] = lambda: _registry(*rows)
    harness.returns["yf.resolve_kr_ticker"] = lambda code: f"{code}.KS"
    harness.returns["yf.get_exchange_segment"] = lambda code: "KOSPI"


def test_registry_lookup_by_english_name(harness, monkeypatch):
    _use_registry(harness, monkeypatch)
    harness.discovered["KR"] = [
        co("Samsung Electronics", "005930"),
        co("SK Hynix", "000660"),
        co("LG Electronics", "066570"),
        co("현대차", "005380"),
        # neither this name nor this stock code is in the registry (and not a
        # second 005930: two valuations of one code would write one profile)
        co("Kakao", "035720"),
    ]

    saved = harness.run()

    # The English name is the registered one and its row carries the selected
    # stock code. By the Korean names alone "Samsung Electronics" matched
    # nothing and the other two landed on SK and LG.
    assert {
        v["company"]: (v["status"], v["reason_code"]) for v in saved["valuations"]
    } == {
        "Samsung Electronics": ("success", None),
        "SK Hynix": ("success", None),
        "LG Electronics": ("success", None),
        "현대차": ("success", None),
        "Kakao": ("no_result", "IDENTITY_NOT_FOUND"),
    }
    kakao = entry(saved, "Kakao")["reason_detail"]
    assert (kakao["query"], kakao["expected_ticker"]) == ("Kakao", "035720")
    assert harness.profiles() == [
        "000660.yaml",
        "005380.yaml",
        "005930.yaml",
        "066570.yaml",
    ]
    # each valued as its own registry row: 삼성전자, SK하이닉스, LG전자, 현대차
    assert sorted(harness.called("industry")) == [
        "00000000",
        "00000002",
        "00000004",
        "00000005",
    ]


def test_registry_lookup_still_blocks_a_wrong_code(harness, monkeypatch):
    """Passes before and after: what was blocked for a wrong code still is."""
    _use_registry(harness, monkeypatch)
    harness.discovered["KR"] = [
        # the registered name of one listing with the stock code of another
        co("삼성전자", "000660"),
        # a preferred share: its code is not in the registry
        co("삼성전자우", "005935"),
        # the code is in the registry, the name is nobody's registered name:
        # the code alone identifies nothing, the name lookup lands on SK
        co("SK Hynix Semiconductor", "000660"),
        co("Nowhere Corp", "999999"),
    ]

    saved = harness.run()

    assert {
        v["company"]: (v["status"], v["reason_code"]) for v in saved["valuations"]
    } == {
        "삼성전자": ("no_result", "IDENTITY_MISMATCH"),
        "삼성전자우": ("no_result", "IDENTITY_MISMATCH"),
        "SK Hynix Semiconductor": ("no_result", "IDENTITY_MISMATCH"),
        "Nowhere Corp": ("no_result", "IDENTITY_NOT_FOUND"),
    }
    resolved = {
        v["company"]: (
            v["reason_detail"].get("kind"),
            v["reason_detail"].get("expected_ticker"),
            v["reason_detail"].get("resolved_ticker"),
        )
        for v in saved["valuations"]
    }
    assert resolved == {
        "삼성전자": ("ticker_differs", "000660", "005930"),
        "삼성전자우": ("ticker_differs", "005935", "005930"),
        "SK Hynix Semiconductor": ("ticker_differs", "000660", "003600"),
        "Nowhere Corp": (None, "999999", None),
    }
    for boundary in FETCH_AND_LATER:
        assert harness.called(boundary) == []
    assert harness.profiles() == [] and harness.workbooks() == []


def test_registry_without_the_selected_company_leaves_a_reason(harness, monkeypatch):
    """Passes before and after: the three selections when their rows are missing."""
    rows = tuple(
        row
        for row in REGISTRY_ROWS
        if row[0] not in ("삼성전자", "SK하이닉스", "LG전자")
    )
    _use_registry(harness, monkeypatch, rows)
    harness.discovered["KR"] = [
        co("Samsung Electronics", "005930"),
        co("SK Hynix", "000660"),
        co("LG Electronics", "066570"),
    ]

    saved = harness.run()

    assert {
        v["company"]: (v["status"], v["reason_code"]) for v in saved["valuations"]
    } == {
        "Samsung Electronics": ("no_result", "IDENTITY_NOT_FOUND"),
        "SK Hynix": ("no_result", "IDENTITY_MISMATCH"),
        "LG Electronics": ("no_result", "IDENTITY_MISMATCH"),
    }
    sk = entry(saved, "SK Hynix")["reason_detail"]
    assert (sk["expected_ticker"], sk["resolved_ticker"]) == ("000660", "003600")
    lg = entry(saved, "LG Electronics")["reason_detail"]
    assert (lg["expected_ticker"], lg["resolved_ticker"]) == ("066570", "003550")
    for boundary in FETCH_AND_LATER:
        assert harness.called(boundary) == []
    assert harness.profiles() == []


def test_cli_company_name_is_looked_up_as_before(harness, monkeypatch):
    """Passes before and after: ``cli.py --company`` selects no ticker."""
    import cli

    _use_registry(harness, monkeypatch)
    # an English name carries no market hint: EDGAR is asked first, then DART
    harness.returns["edgar.search_company"] = lambda query: []

    monkeypatch.setattr(sys, "argv", ["cli.py", "--company", "현대차"])
    fetched = cli.main()

    identity = fetched["identity"]
    assert (identity.name, identity.ticker, identity.corp_code) == (
        "현대차",
        "005380",
        "00000005",
    )
    assert harness.called("edgar.search_company") == []

    # Without a selected ticker the English name is still compared with the
    # Korean names only: "SK" is inside "SK Hynix".
    monkeypatch.setattr(sys, "argv", ["cli.py", "--company", "SK Hynix"])
    fetched = cli.main()

    identity = fetched["identity"]
    assert (identity.name, identity.ticker, identity.corp_code) == (
        "SK Hynix",
        "003600",
        "00000001",
    )
    assert harness.called("edgar.search_company") == ["SK Hynix"]
    assert harness.called("identify") == []  # the real identify() ran both times
    assert harness.profiles() == ["003600.yaml", "005380.yaml"]


# ── 4. exceptions ────────────────────────────────────────────────────────────


def _fail_start(h, monkeypatch):
    monkeypatch.setitem(sys.modules, "valuation_runner", _module("valuation_runner"))


def _fail_identify(h, monkeypatch):
    h.identity["SynCo"] = RuntimeError("identify exploded")


def _fail_financials(h, monkeypatch):
    h.financials["SynCo"] = ValueError("corp_code 없음: SynCo")


def _fail_shares(h, monkeypatch):
    h.shares["SynCo"] = RuntimeError("shares exploded")


def _fail_draft(h, monkeypatch):
    h.raises["terminal_growth"] = RuntimeError("macro exploded")


def _fail_enrichment(h, monkeypatch):
    def checkpoint(path, raw):
        raise OSError("checkpoint exploded")

    monkeypatch.setattr(h.pg, "_write_enrichment_checkpoint", checkpoint)


def _fail_fetch_result(h, monkeypatch):
    monkeypatch.setattr(
        h.pg, "auto_fetch", lambda *args, **kwargs: {"yaml_path": "profiles/x.yaml"}
    )


def _fail_valuation(h, monkeypatch):
    h.raises["market_compare"] = RuntimeError("market compare exploded")


def _fail_export(h, monkeypatch):
    h.raises["export"] = RuntimeError("export exploded")


@pytest.mark.parametrize(
    "stage, inject, error_type",
    [
        ("start", _fail_start, "ImportError"),
        ("identify", _fail_identify, "RuntimeError"),
        ("financials", _fail_financials, "ValueError"),
        ("shares", _fail_shares, "RuntimeError"),
        ("draft_profile", _fail_draft, "RuntimeError"),
        ("enrichment", _fail_enrichment, "OSError"),
        ("enrichment", _fail_fetch_result, "KeyError"),
        ("valuation", _fail_valuation, "RuntimeError"),
        ("export", _fail_export, "RuntimeError"),
    ],
)
def test_exception_is_recorded_with_its_stage(
    harness, monkeypatch, stage, inject, error_type
):
    harness.one(co("SynCo", "123456"), kr_identity())
    inject(harness, monkeypatch)

    saved = harness.run()

    item = entry(saved, "SynCo")
    assert (item["status"], item["reason_code"], item["severity"]) == (
        "failed",
        "VALUATION_EXCEPTION",
        "failure",
    )
    assert item["reason_detail"]["stage"] == stage
    assert item["reason_detail"]["error_type"] == error_type
    assert isinstance(item["error"], str) and item["error"]  # the pre-K-0C key
    err = verror(saved, "SynCo")
    assert (err["reason_code"], err["company"]) == ("VALUATION_EXCEPTION", "SynCo")
    assert (err["stage"], err["error_type"]) == (stage, error_type)
    assert err["error"] == item["error"]  # the exception text, as before K-0C
    assert saved["valuation_status"]["by_reason"] == {"VALUATION_EXCEPTION": 1}


def test_exception_while_reading_the_result(harness, monkeypatch):
    class Broken:
        validation_report = None
        excel_path = "x.xlsx"
        summary_md = ""

        @property
        def result(self):
            raise RuntimeError("result exploded")

    harness.one(co("SynCo", "123456"))
    monkeypatch.setattr(harness.pg, "auto_analyze", lambda *args, **kwargs: Broken())

    saved = harness.run()

    item = entry(saved, "SynCo")
    assert (item["status"], item["reason_code"]) == ("failed", "VALUATION_EXCEPTION")
    assert item["reason_detail"]["stage"] == "result"


def test_an_exception_class_name_is_checked_like_any_identifier(harness):
    """describe_error() reports type(exc).__name__ and status_code as they are:
    a class can be named anything and a status code can be any int."""
    odd = type("sk-ant-SECRETSECRET4", (RuntimeError,), {})("plain message")
    odd.status_code = 10**5000  # would also make the summary impossible to save
    harness.discovered["KR"] = [co("Alpha", "111111"), co("Bravo", "222222")]
    harness.identity.update({"Alpha": odd, "Bravo": RuntimeError("plain message")})

    saved = harness.run()

    item = entry(saved, "Alpha")
    assert (item["status"], item["reason_code"]) == ("failed", "VALUATION_EXCEPTION")
    assert item["error"] == "plain message"
    detail = item["reason_detail"]
    assert (detail["stage"], detail["error_type"]) == ("identify", "<invalid>")
    assert detail["http_status"] is None
    assert verror(saved, "Alpha")["error_type"] == "<invalid>"
    plain = entry(saved, "Bravo")["reason_detail"]
    assert (plain["error_type"], plain["provider"]) == ("RuntimeError", "unknown")
    assert plain["caused_by"] == []
    _assert_no_secret(json.dumps(saved, ensure_ascii=False))
    _assert_no_secret(json.dumps(harness.db_updates, ensure_ascii=False, default=str))


def test_unprintable_exception_does_not_end_the_run(harness):
    """HEAD: str(e) raised inside the except clause and run_weekly() died."""
    harness.discovered["KR"] = [co("Alpha", "111111"), co("SynCo", "123456")]
    harness.identity.update({"Alpha": UnprintableError(), "SynCo": kr_identity()})

    saved = harness.run()

    item = entry(saved, "Alpha")
    assert (item["status"], item["reason_code"]) == ("failed", "VALUATION_EXCEPTION")
    assert item["reason_detail"]["error_type"] == "UnprintableError"
    assert item["error"] == ""
    assert entry(saved, "SynCo")["status"] == "success"


@pytest.mark.parametrize(
    "stage",
    [
        "identify",
        "financials",
        "shares",
        "draft_profile",
        "enrichment",
        "valuation",
        "export",
    ],
)
def test_exception_text_is_masked_at_every_stage(harness, monkeypatch, caplog, stage):
    harness.one(co("SynCo", "123456"), kr_identity())
    leak = RuntimeError(LEAKY_MESSAGE)
    if stage == "identify":
        harness.identity["SynCo"] = leak
    elif stage == "financials":
        harness.financials["SynCo"] = leak
    elif stage == "shares":
        harness.shares["SynCo"] = leak
    elif stage == "draft_profile":
        harness.raises["terminal_growth"] = leak
    elif stage == "enrichment":

        def checkpoint(path, raw):
            raise leak

        monkeypatch.setattr(harness.pg, "_write_enrichment_checkpoint", checkpoint)
    elif stage == "valuation":
        harness.raises["market_compare"] = leak
    else:
        harness.raises["export"] = leak

    with caplog.at_level(logging.DEBUG, logger="scheduler.weekly_run"):
        saved = harness.run()

    item = entry(saved, "SynCo")
    assert (item["status"], item["reason_detail"]["stage"]) == ("failed", stage)
    masked = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json?***"
    assert masked in item["error"] and masked in item["reason_detail"]["message"]
    _assert_no_secret(json.dumps(saved, ensure_ascii=False))
    _assert_no_secret(json.dumps(harness.db_updates, ensure_ascii=False, default=str))
    _assert_no_secret(" ".join(msg for _, msg in harness.alerts))
    _assert_no_secret(
        " ".join(
            r.getMessage() for r in caplog.records if r.name == "scheduler.weekly_run"
        )
    )


# ── 5. secrets ───────────────────────────────────────────────────────────────


def _assert_no_secret(text: str) -> None:
    for secret in SECRETS:
        assert secret not in text, f"secret leaked: {secret[:6]}…"


def test_exception_text_is_redacted_and_names_are_not(harness, monkeypatch, caplog):
    from pipeline.reconciliation import Finding, ReconciliationReport

    blocked = ReconciliationReport()
    blocked.add(Finding(check="share_count", severity="block", message=LEAKY_MESSAGE))
    real_reconcile = importlib.import_module(
        "pipeline.reconciliation"
    ).reconcile_market_data

    def reconcile(financials, shares_info, market="KR", **kwargs):
        if shares_info.get("leaky"):
            return blocked
        return real_reconcile(financials, shares_info, market=market, **kwargs)

    monkeypatch.setattr("pipeline.reconciliation.reconcile_market_data", reconcile)
    harness.discovered["KR"] = [
        co("SK-Hynix", "000660"),
        co("Bravo", "222222"),
        co("Charlie", "333333"),
        co("Delta", "444444"),
    ]
    harness.identity.update(
        {
            "SK-Hynix": RuntimeError(LEAKY_MESSAGE),
            "Bravo": kr_identity("Bravo", "222222"),
            "Charlie": kr_identity("Charlie", "333333"),
            "Delta": kr_identity("Delta", "444444"),
        }
    )
    harness.financials["Bravo"] = RuntimeError(LEAKY_MESSAGE)
    harness.shares["Charlie"] = dict(SHARES_INFO, leaky=True)
    harness.raises["ai.wacc"] = {"Delta": RuntimeError(LEAKY_MESSAGE)}

    with caplog.at_level(logging.DEBUG, logger="scheduler.weekly_run"):
        saved = harness.run()

    assert entry(saved, "SK-Hynix")["reason_detail"]["stage"] == "identify"
    assert entry(saved, "Charlie")["reason_code"] == "RECONCILIATION_BLOCKED"
    assert entry(saved, "Delta")["degraded"] == ["wacc"]
    opendart = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    assert opendart in entry(saved, "Bravo")["error"]  # masked, not dropped
    _assert_no_secret(json.dumps(saved, ensure_ascii=False))
    _assert_no_secret(json.dumps(harness.db_updates, ensure_ascii=False, default=str))
    _assert_no_secret(" ".join(msg for _, msg in harness.alerts))
    _assert_no_secret(
        " ".join(
            r.getMessage() for r in caplog.records if r.name == "scheduler.weekly_run"
        )
    )
    texts = [e["error"] for e in saved["errors"]]
    texts += [v["error"] for v in saved["valuations"] if "error" in v]
    texts += [d["message"] for v in saved["valuations"] for d in v["degraded_detail"]]
    texts += [c["message"] for c in entry(saved, "Charlie")["reason_detail"]["checks"]]
    assert texts
    for text in texts:
        assert not any(ch in text for ch in "\r\n\t")
    # identifiers are copied as they are: masking would turn this into "sk-***"
    assert verror(saved, "SK-Hynix")["company"] == "SK-Hynix"
    assert entry(saved, "SK-Hynix")["company"] == "SK-Hynix"


# ── 6. optional steps ────────────────────────────────────────────────────────


def _us(h):
    h.discovered["KR"] = []
    h.one(co("SynUS", "SYNU"), us_identity(analysis_date=FIXED_TODAY), market="US")
    h.shares["SynUS Inc."] = dict(SHARES_INFO, currency="USD")
    return ("US",)


def _d_industry(h):
    h.raises["industry"] = RuntimeError("exception text must not enter logs")


def _d_ttm(h):
    h.raises["ttm"] = RuntimeError("ttm exploded")
    return _us(h)


def _d_ttm_no_analysis_date(h):
    """What production does today: CompanyIdentity has no analysis_date."""
    h.discovered["KR"] = []
    h.one(co("SynUS", "SYNU"), us_identity(), market="US")
    h.shares["SynUS Inc."] = dict(SHARES_INFO, currency="USD")
    return ("US",)


def _d_beta(h):
    h.raises["beta"] = RuntimeError("beta exploded")


def _d_ai_module(h):
    h.raises["ai.init"] = RuntimeError("no analyst")


def _d_segments(h):
    h.raises["ai.segments"] = RuntimeError("segments exploded")


def _d_peers(h):
    h.raises["ai.peers_batch"] = RuntimeError("batch exploded")
    h.raises["ai.peers"] = {"SVC": RuntimeError("peer exploded")}


def _d_wacc(h):
    h.raises["ai.wacc"] = RuntimeError("wacc exploded")


def _d_news(h):
    h.raises["news"] = RuntimeError("news exploded")


def _d_signals(h):
    h.raises["market_signals"] = RuntimeError("signals exploded")


def _d_method(h):
    h.raises["method_selection"] = RuntimeError("method exploded")


def _d_scenarios(h):
    h.raises["ai.scenarios"] = RuntimeError("scenarios exploded")


def _d_db(h):
    h.raises["db_save"] = RuntimeError("db exploded")


@pytest.mark.parametrize(
    "step, inject, error_type",
    [
        ("industry_metadata", _d_industry, "RuntimeError"),
        ("ttm_anchor", _d_ttm, "RuntimeError"),
        ("ttm_anchor", _d_ttm_no_analysis_date, "AttributeError"),
        ("beta_observation", _d_beta, "RuntimeError"),
        ("ai_module", _d_ai_module, "RuntimeError"),
        ("segments", _d_segments, "RuntimeError"),
        ("peers", _d_peers, "RuntimeError"),
        ("wacc", _d_wacc, "RuntimeError"),
        ("news", _d_news, "RuntimeError"),
        ("market_signals", _d_signals, "RuntimeError"),
        ("method_selection", _d_method, "RuntimeError"),
        ("scenarios", _d_scenarios, "RuntimeError"),
        ("db_save_call", _d_db, "RuntimeError"),
    ],
)
def test_optional_step_failure_is_reported_as_degraded(
    harness, step, inject, error_type
):
    harness.one(co("SynCo", "123456"), kr_identity())
    markets = inject(harness) or ("KR",)

    saved = harness.run(markets=markets)

    (item,) = saved["valuations"]
    assert item["status"] in ("success", "draft_blocked")  # a result was produced
    assert (item["reason_code"], item["severity"], item["reason_detail"]) == (
        None,
        None,
        {},
    )
    assert item["degraded"] == [step]
    (detail,) = item["degraded_detail"]
    assert (detail["step"], detail["error_type"]) == (step, error_type)
    (err,) = verrors(saved)
    assert (err["reason_code"], err["severity"]) == ("ENRICHMENT_DEGRADED", "degraded")
    assert step in err["error"]
    assert final_status(harness) == "completed_with_errors"
    assert saved["valuation_status"]["degraded_results"] == 1
    assert saved["valuation_status"]["by_reason"] == {}
    if step == "industry_metadata":
        # this site keeps exception text out on purpose (it can hold a keyed URL)
        assert "message" not in detail
        assert "must not enter" not in json.dumps(saved, ensure_ascii=False)
    if step == "peers":
        assert detail["segments"] == ["SVC"]


def test_recovered_or_empty_steps_are_not_degraded(harness):
    """Batch failure repaired per segment, no news, no signals, no TTM data."""
    markets = _us(harness)
    harness.raises["ai.peers_batch"] = RuntimeError("batch exploded")
    harness.returns["news"] = []

    saved = harness.run(markets=markets)

    (item,) = saved["valuations"]
    assert item["status"] == "success"
    assert (item["degraded"], item["degraded_detail"]) == ([], [])
    assert saved["errors"] == []
    assert harness.called("ai.peers") == ["CORE", "SVC"]
    assert harness.called("ttm") == ["1234567"]


def test_no_registry_target_is_not_degraded(harness):
    harness.one(co("SynCo", "123456"), kr_identity(corp_code=None))

    saved = harness.run()

    assert entry(saved, "SynCo")["degraded"] == []
    assert harness.called("industry") == []


def test_earlier_degraded_steps_survive_a_later_failure(harness):
    harness.one(co("SynCo", "123456"), kr_identity())
    harness.raises["industry"] = RuntimeError("industry exploded")
    harness.raises["ai.init"] = RuntimeError("no analyst")
    harness.raises["export"] = RuntimeError("export exploded")

    saved = harness.run()

    item = entry(saved, "SynCo")
    assert (item["status"], item["reason_code"]) == ("failed", "VALUATION_EXCEPTION")
    assert item["degraded"] == ["industry_metadata", "ai_module"]
    (err,) = verrors(saved)  # one entry per valuation: the terminal reason wins
    assert err["reason_code"] == "VALUATION_EXCEPTION"
    assert saved["valuation_status"]["degraded_results"] == 0


def test_steps_degraded_before_the_ai_fallback_are_kept(harness):
    """Beta and TTM fall back while the draft is written, then the AI module fails."""
    markets = _us(harness)
    harness.raises["beta"] = RuntimeError("beta exploded")
    harness.raises["ttm"] = RuntimeError("ttm exploded")
    harness.raises["ai.init"] = RuntimeError("no analyst")

    saved = harness.run(markets=markets)

    (item,) = saved["valuations"]
    assert item["status"] in ("success", "draft_blocked")
    assert item["degraded"] == ["beta_observation", "ttm_anchor", "ai_module"]
    (err,) = verrors(saved)
    assert err["reason_code"] == "ENRICHMENT_DEGRADED"


def test_no_result_keeps_the_steps_degraded_before_it(harness):
    harness.one(co("SynCo", "123456"), kr_identity())
    harness.raises["industry"] = RuntimeError("industry exploded")
    harness.shares["SynCo"] = dict(
        SHARES_INFO, shares_total=SHARES * 2, shares_ordinary=SHARES * 2
    )

    saved = harness.run()

    item = assert_no_result(saved, harness, "SynCo", "RECONCILIATION_BLOCKED")
    assert item["degraded"] == ["industry_metadata"]
    (err,) = verrors(saved)  # still one entry: the terminal reason
    assert err["reason_code"] == "RECONCILIATION_BLOCKED"
    assert saved["valuation_status"]["degraded_results"] == 0


# ── 7. protected profiles ────────────────────────────────────────────────────


def test_protected_profile_is_staged_and_valued(harness):
    protected = harness.root / "profiles" / "123456.yaml"
    original = b"curated: true\ndraft: false\ncompany: {name: Curated}\n"
    protected.write_bytes(original)
    harness.one(co("SynCo", "123456"), kr_identity())

    saved = harness.run()

    item = entry(saved, "SynCo")
    assert (item["status"], item["reason_code"]) == ("success", None)
    assert protected.read_bytes() == original
    assert harness.profiles() == ["123456.yaml", "staging/123456.yaml"]
    staged = yaml.safe_load(
        (harness.root / "profiles" / "staging" / "123456.yaml").read_text("utf-8")
    )
    assert staged["generated"] == "auto" and "segments" in staged
    assert harness.workbooks() != []


# ── 8. isolation between valuations ──────────────────────────────────────────


@pytest.mark.parametrize("slow", ["Alpha", "Charlie", "Echo"])
def test_parallel_valuations_do_not_share_diagnostics(harness, slow):
    harness.discovered["KR"] = [
        co("Alpha", "111111"),
        co("Charlie", "333333"),
        co("Delta", "444444"),
        co("Echo", "555555"),
    ]
    harness.identity.update(
        {
            "Alpha": None,
            "Charlie": kr_identity("Charlie", "333333"),
            "Delta": kr_identity("Delta", "444444"),
            "Echo": RuntimeError("identify exploded"),
        }
    )
    harness.financials["Charlie"] = {}
    harness.raises["ai.wacc"] = {"Delta": RuntimeError("wacc exploded")}
    harness.delay[slow] = 0.3

    saved = harness.run()

    outcome = {
        v["company"]: (v["status"], v["reason_code"], v["degraded"])
        for v in saved["valuations"]
    }
    assert outcome == {
        "Alpha": ("no_result", "IDENTITY_NOT_FOUND", []),
        "Charlie": ("no_result", "FINANCIALS_EMPTY", []),
        "Delta": ("success", None, ["wacc"]),
        "Echo": ("failed", "VALUATION_EXCEPTION", []),
    }
    assert entry(saved, "Alpha")["reason_detail"]["query"] == "Alpha"
    assert entry(saved, "Charlie")["reason_detail"]["resolved_ticker"] == "333333"
    assert sorted(e["company"] for e in verrors(saved)) == [
        "Alpha",
        "Charlie",
        "Delta",
        "Echo",
    ]


def test_a_reused_worker_thread_starts_clean(harness, monkeypatch):
    monkeypatch.setattr(
        harness.wr, "ThreadPoolExecutor", lambda max_workers: ThreadPoolExecutor(1)
    )
    harness.discovered["KR"] = [
        co("Alpha", "111111"),
        co("Delta", "444444"),
        co("SynCo", "123456"),
    ]
    harness.identity.update(
        {
            "Alpha": None,
            "Delta": kr_identity("Delta", "444444"),
            "SynCo": kr_identity(),
        }
    )
    harness.raises["ai.wacc"] = {"Delta": RuntimeError("wacc exploded")}

    saved = harness.run()

    clean = entry(saved, "SynCo")
    assert (clean["status"], clean["reason_code"], clean["degraded"]) == (
        "success",
        None,
        [],
    )
    assert entry(saved, "Delta")["degraded"] == ["wacc"]
    assert entry(saved, "Alpha")["reason_code"] == "IDENTITY_NOT_FOUND"


def test_an_inherited_context_is_never_written_to(harness, tmp_path):
    """Python 3.14 can start a thread with a copy of the caller's context.

    Simulated here: every task runs inside a copy of a context that already
    has someone else's dict bound, on one reused worker thread, and one of
    the tasks ends with an exception.
    """
    import contextvars

    pg = harness.pg
    harness.identity.update(
        {
            "Nobody": None,
            "Echo": RuntimeError("identify exploded"),
            "SynCo": kr_identity(),
        }
    )
    own: dict[str, dict] = {"Nobody": {}, "Echo": {}, "SynCo": {}}
    outer: dict = {}

    def task(query: str):
        try:
            return pg.auto_analyze(
                query, output_dir=str(harness.out), diagnostics=own[query]
            )
        except RuntimeError:
            return "raised"

    token = pg._DIAGNOSTICS.set(outer)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            futures = {
                query: pool.submit(contextvars.copy_context().run, task, query)
                for query in own
            }
            results = {query: future.result() for query, future in futures.items()}
        assert pg._DIAGNOSTICS.get() is outer
    finally:
        pg._DIAGNOSTICS.reset(token)

    assert outer == {}
    assert results["Nobody"] is None and results["Echo"] == "raised"
    assert results["SynCo"] is not None
    assert own["Nobody"]["reason_code"] == "IDENTITY_NOT_FOUND"
    assert (own["Echo"]["stage"], own["Echo"]["reason_code"]) == ("identify", None)
    assert (own["SynCo"]["reason_code"], own["SynCo"]["degraded"]) == (None, [])


# ── 9. diagnostics must never change an outcome ──────────────────────────────


def test_unwritable_diagnostics_do_not_change_the_result(harness, tmp_path):
    harness.identity["SynCo"] = kr_identity()
    harness.identity["Nobody"] = None
    harness.raises["ai.wacc"] = RuntimeError("wacc exploded")
    read_only = types.MappingProxyType({})

    result = harness.pg.auto_analyze(
        "SynCo", output_dir=str(harness.out), diagnostics=read_only
    )
    missing = harness.pg.auto_analyze(
        "Nobody", output_dir=str(harness.out), diagnostics=read_only
    )

    assert result is not None and Path(result.excel_path).exists()
    assert missing is None
    assert dict(read_only) == {}


def test_diagnostics_are_bound_per_call(harness, tmp_path):
    first: dict = {}
    harness.identity["Nobody"] = None
    harness.identity["SynCo"] = kr_identity()

    assert harness.pg.auto_analyze("Nobody", diagnostics=first) is None
    second: dict = {}
    result = harness.pg.auto_analyze(
        "SynCo", output_dir=str(harness.out), diagnostics=second
    )

    assert first["contract"] == "k0c-1"
    assert first["reason_code"] == "IDENTITY_NOT_FOUND"
    assert result is not None
    assert (second["reason_code"], second["degraded"]) == (None, [])
    assert second["stage"] == "export"


def test_malformed_diagnostics_are_normalised(harness, monkeypatch, caplog):
    """A producer that breaks the contract can neither end the run nor leak text.

    Only the fields contract k0c-1 names are read; each is shape-checked,
    numbers are bounded, free text is masked again by the consumer, and the
    selection identifiers are the consumer's own values.
    """

    class Unprintable:
        def __str__(self) -> str:
            raise ValueError("no text")

    cyclic: dict = {}
    cyclic["self"] = cyclic

    def auto_analyze(query, output_dir=None, scored_data=None, *, diagnostics=None):
        diagnostics["reason_code"] = "IDENTITY_MISMATCH"
        diagnostics["reason_detail"] = {
            "kind": "PASSWORD: hunter2secret",
            "query": "sk-ant-SECRETSECRET4",
            "expected_ticker": "sk-ant-SECRETSECRET4",
            "market_hint": "KR",
            "resolved_ticker": "sk-ant-SECRETSECRET4",
            "resolved_market": Unprintable(),
            "resolved_corp_code": 10**5000,
            "resolved_cik": "1234567",
            "has_cik": "yes",
            "legal_status": "   ",
            "checks": [
                {
                    "check": "share_count",
                    "rel_diff_pct": 10**5000,
                    "message": LEAKY_MESSAGE,
                },
                "not a dict",
            ],
            "PASSWORD: hunter2secret": "a free-text key",
            7: "a non-string key",
            "cyclic": cyclic,
            "count": 10**5000,
        }
        diagnostics["degraded"] = [
            {"step": "PASSWORD: hunter2secret"},
            {
                "step": "wacc",
                "error_type": "Not A Class!",
                "message": LEAKY_MESSAGE,
                "segments": ["SVC", "sk-ant-SECRETSECRET4 x", 7],
                "count": 10**5000,
            },
            "not a dict",
        ] + [{"step": "news"}] * 500
        return None

    harness.one(co("SynCo", "123456"))
    monkeypatch.setattr(harness.pg, "auto_analyze", auto_analyze)

    with caplog.at_level(logging.DEBUG, logger="scheduler.weekly_run"):
        saved = harness.run()  # the summary was written and parses as JSON

    item = assert_no_result(saved, harness, "SynCo", "IDENTITY_MISMATCH")
    detail = item["reason_detail"]
    (check,) = detail.pop("checks")
    assert detail == {
        "kind": "<invalid>",
        "query": "SynCo",  # written by the consumer, not taken from the producer
        "market_hint": "KR",
        "expected_ticker": "123456",
        "resolved_ticker": "<invalid>",
        "resolved_market": "<invalid>",
        "resolved_corp_code": "<invalid>",
        "resolved_cik": "1234567",
        "has_cik": None,
        "legal_status": None,  # blank = absent, as on the producer side
    }
    assert (check["check"], check["rel_diff_pct"]) == ("share_count", None)
    assert (
        "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json?***" in check["message"]
    )
    steps = item["degraded_detail"]
    assert len(steps) == 19  # the first 20 items, minus the one that is no dict
    assert steps[0] == {"step": "<invalid>"}
    assert set(steps[1]) == {"step", "error_type", "message", "segments"}
    assert (steps[1]["step"], steps[1]["error_type"]) == ("wacc", "<invalid>")
    assert steps[1]["segments"] == ["SVC"]
    assert item["degraded"] == ["<invalid>", "wacc", "news"]
    assert len(verrors(saved)) == 1
    _assert_no_secret(json.dumps(saved, ensure_ascii=False))
    _assert_no_secret(json.dumps(harness.db_updates, ensure_ascii=False, default=str))
    _assert_no_secret(" ".join(msg for _, msg in harness.alerts))
    _assert_no_secret(" ".join(r.getMessage() for r in caplog.records))


def test_diagnostic_fields_are_computed_inside_the_guard(harness):
    """Nothing is evaluated for the diagnostics unless a caller is listening,
    and a failure while building them stays inside the helper."""
    pg = harness.pg
    calls = []

    def fields():
        calls.append("evaluated")
        raise ValueError("building the diagnostics failed")

    pg._diag_degraded("peers", RuntimeError("peer exploded"), fields=fields)
    pg._diag_reason("FINANCIALS_EMPTY", fields)
    assert calls == []  # nothing bound: not evaluated at all

    listening: dict = {}
    token = pg._DIAGNOSTICS.set(pg._diag_bind(listening))
    try:
        pg._diag_degraded("peers", RuntimeError("peer exploded"), fields=fields)
        pg._diag_reason("FINANCIALS_EMPTY", fields)
    finally:
        pg._DIAGNOSTICS.reset(token)
    assert calls == ["evaluated", "evaluated"]
    assert listening["degraded"] == []


# ── 10. roll-up and the code sets ────────────────────────────────────────────


def test_valuation_status_rollup(harness):
    harness.discovered["KR"] = [
        co("Alpha", "111111"),
        co("Delta", "444444"),
        co("Echo", "555555"),
        co("SynCo", "123456"),
    ]
    harness.identity.update(
        {
            "Alpha": None,
            "Delta": kr_identity("Delta", "444444"),
            "Echo": RuntimeError("identify exploded"),
            "SynCo": kr_identity(),
        }
    )
    harness.raises["ai.wacc"] = {"Delta": RuntimeError("wacc exploded")}

    saved = harness.run()

    status = saved["valuation_status"]
    assert status == {
        "contract": "k0c-1",
        "total": 4,
        "by_status": {"no_result": 1, "success": 2, "failed": 1},
        "by_reason": {"IDENTITY_NOT_FOUND": 1, "VALUATION_EXCEPTION": 1},
        "degraded_results": 1,
    }
    assert sum(status["by_status"].values()) == len(saved["valuations"])
    assert len(verrors(saved)) == 3  # one per valuation that has something to say
    # the pre-K-0C roll-up is untouched
    assert saved["status_summary"] == {
        "total": 4,
        "success": 2,
        "failed": 1,
        "draft_blocked": 0,
    }


def test_dry_run_reports_an_empty_rollup(harness):
    harness.one(co("SynCo", "123456"))

    saved = harness.run(dry_run=True)

    assert saved["valuations"] == []
    assert saved["valuation_status"] == {
        "contract": "k0c-1",
        "total": 0,
        "by_status": {},
        "by_reason": {},
        "degraded_results": 0,
    }


def test_consumer_accepts_exactly_the_producer_codes(harness):
    assert harness.wr._ACCEPTED_NO_RESULT_REASONS == harness.pg.NO_RESULT_REASONS
    assert harness.pg.NO_RESULT_REASONS == {
        "IDENTITY_NOT_FOUND",
        "IDENTITY_MISMATCH",
        "FINANCIALS_EMPTY",
        "RECONCILIATION_BLOCKED",
        "DRAFT_NO_YEARS",
        "DRAFT_NOT_WRITTEN",
        "REASON_NOT_REPORTED",
    }
