"""Pipeline unit tests — exchange classification, CompanyIdentity, schema model validation."""

import pytest

import tests.test_no_result_failure_contract as k0c
from pipeline.yahoo_finance import classify_exchange
from pipeline.data_fetcher import CompanyIdentity, _is_korean, _is_likely_ticker
from schemas.models import (
    CompanyProfile,
    WACCParams,
    ScenarioParams,
    DCFParams,
    PeerCompany,
    ConsolidatedFinancials,
)

# The K-0C harness (every side-effecting boundary replaced) drives auto_analyze().
from tests.test_no_result_failure_contract import env_guard, harness  # noqa: F401


# ═══════════════════════════════════════════════════════════
# classify_exchange Tests
# ═══════════════════════════════════════════════════════════


class TestClassifyExchange:
    """Yahoo Finance exchange code -> listed/OTC/unlisted classification."""

    def test_nyse(self):
        assert classify_exchange("NYQ") == "상장"
        assert classify_exchange("NYSE") == "상장"

    def test_nasdaq(self):
        assert classify_exchange("NMS") == "상장"
        assert classify_exchange("NAS") == "상장"
        assert classify_exchange("NGM") == "상장"

    def test_otc_pink(self):
        assert classify_exchange("PNK") == "OTC"
        assert classify_exchange("PK") == "OTC"

    def test_otc_bulletin_board(self):
        assert classify_exchange("OBB") == "OTC"
        assert classify_exchange("OTC Bulletin Board", "OBB") == "OTC"

    def test_otcqx_otcqb(self):
        assert classify_exchange("", "OQX") == "OTC"
        assert classify_exchange("", "OQB") == "OTC"

    def test_unknown_exchange(self):
        assert classify_exchange("", "") == "비상장"
        assert classify_exchange("UNKNOWN") == "비상장"

    def test_partial_match_otc(self):
        assert classify_exchange("OTC Markets") == "OTC"
        assert classify_exchange("Pink Sheets") == "OTC"

    def test_partial_match_major(self):
        assert classify_exchange("NYSE Arca") == "상장"
        assert classify_exchange("NASDAQ Global") == "상장"

    def test_case_insensitive(self):
        assert classify_exchange("nyq") == "상장"
        assert classify_exchange("pnk") == "OTC"

    def test_exchange_code_fallback(self):
        """Empty exchange_name falls back to exchange_code."""
        assert classify_exchange("", "PNK") == "OTC"
        assert classify_exchange("", "NYQ") == "상장"


# ═══════════════════════════════════════════════════════════
# CompanyIdentity Tests
# ═══════════════════════════════════════════════════════════


class TestCompanyIdentity:
    def test_us_listed(self):
        ci = CompanyIdentity("Apple", "US", ticker="AAPL", legal_status="상장")
        assert ci.market == "US"
        assert ci.legal_status == "상장"
        assert "OTC" not in repr(ci)

    def test_us_otc(self):
        ci = CompanyIdentity("SomeOTC", "US", ticker="SOTC", legal_status="OTC")
        assert ci.legal_status == "OTC"
        assert "OTC" in repr(ci)

    def test_kr_default_unlisted(self):
        ci = CompanyIdentity("테스트기업", "KR", corp_code="00123456")
        assert ci.legal_status == "비상장"
        assert "비상장" in repr(ci)

    def test_kr_listed(self):
        ci = CompanyIdentity("삼성전자", "KR", ticker="005930", legal_status="상장")
        assert ci.legal_status == "상장"

    def test_us_default_listed(self):
        """US companies default to listed."""
        ci = CompanyIdentity("Test", "US")
        assert ci.legal_status == "상장"


# ═══════════════════════════════════════════════════════════
# Helper Function Tests
# ═══════════════════════════════════════════════════════════


class TestHelpers:
    def test_is_korean(self):
        assert _is_korean("삼성전자") is True
        assert _is_korean("Samsung") is False
        assert _is_korean("삼성 Electronics") is True

    def test_is_likely_ticker(self):
        assert _is_likely_ticker("AAPL") is True
        assert _is_likely_ticker("MSFT") is True
        assert _is_likely_ticker("A") is True
        assert _is_likely_ticker("ABCDEF") is False  # exceeds 5 chars
        assert _is_likely_ticker("aapl") is False  # lowercase
        assert _is_likely_ticker("123") is False


# ═══════════════════════════════════════════════════════════
# Pydantic Schema Tests
# ═══════════════════════════════════════════════════════════


class TestSchemaModels:
    def test_company_profile_defaults(self):
        cp = CompanyProfile(
            name="테스트",
            shares_total=100_000,
            shares_ordinary=80_000,
        )
        assert cp.legal_status == "비상장"
        assert cp.market == "KR"
        assert cp.currency == "KRW"
        assert cp.unit_multiplier == 1_000_000
        assert cp.shares_preferred == 0
        assert cp.ticker is None

    def test_company_profile_us(self):
        cp = CompanyProfile(
            name="TestCo",
            market="US",
            currency="USD",
            currency_unit="$M",
            shares_total=1_000_000,
            shares_ordinary=1_000_000,
            legal_status="상장",
            ticker="TEST",
        )
        assert cp.market == "US"
        assert cp.ticker == "TEST"

    def test_consolidated_properties(self):
        cf = ConsolidatedFinancials(
            year=2025,
            revenue=10_000,
            op=1_000,
            net_income=700,
            assets=50_000,
            liabilities=30_000,
            equity=20_000,
            dep=500,
            amort=200,
        )
        assert cf.da == 700
        assert cf.ebitda == 1_700

    def test_scenario_params_optional_fields(self):
        sp = ScenarioParams(
            code="A",
            name="테스트",
            prob=50,
            ipo="N/A",
            shares=10_000,
        )
        assert sp.irr is None
        assert sp.cps_repay is None
        assert sp.dlom == 0
        assert sp.rcps_repay is None
        assert sp.buyback == 0

    def test_dcf_params_optional_actuals(self):
        dp = DCFParams(ebitda_growth_rates=[0.1, 0.08])
        assert dp.actual_capex is None
        assert dp.actual_nwc is None
        assert dp.prior_nwc is None
        assert dp.tax_rate == 22.0
        assert dp.terminal_growth == 2.5

    def test_peer_company_defaults(self):
        pc = PeerCompany(name="Peer", segment_code="HI", ev_ebitda=8.0)
        assert pc.source == "manual"
        assert pc.ticker is None
        assert pc.market_cap is None

    def test_wacc_params_validation(self):
        wp = WACCParams(
            rf=3.5, erp=7.0, bu=0.75, de=192.0, tax=22.0, kd_pre=5.5, eq_w=34.2
        )
        assert wp.rf == 3.5
        assert wp.eq_w == 34.2


@pytest.mark.network
@pytest.mark.parametrize(
    "provider, identifier, name, expected_code",
    [
        ("edgar", "320193", "aapl", "3571"),
        ("edgar", "19617", "jpm", "6021"),
        ("dart", "00126380", "005930", "26"),
        ("dart", "00688996", "105560", "64"),
    ],
)
def test_authoritative_industry_live(
    provider, identifier, name, expected_code, monkeypatch, caplog
):
    """One request per company; opt-in recording saves only approved public keys."""
    from dataclasses import replace
    from datetime import datetime, timedelta, timezone
    import json
    import os
    from pathlib import Path

    from dotenv import load_dotenv
    from pipeline import dart_client, edgar_client
    from pipeline.api_guard import ApiGuard

    fixture_name = (
        f"edgar_submissions_{name}.json"
        if provider == "edgar"
        else f"dart_company_{name}.json"
    )
    path = Path(__file__).parent / "fixtures" / fixture_name
    record = os.environ.get("BVT_RECORD_J3_INDUSTRY_FIXTURES") == "1"
    if record:
        assert not path.exists(), "Refuse to overwrite an existing live fixture"
    else:
        assert path.exists(), "Record the approved fixtures before live comparison"
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    guard = ApiGuard.get()
    monkeypatch.setitem(
        guard._configs, provider, replace(guard._configs[provider], max_retries=0)
    )
    # Exceptions may contain authenticated URLs: expose only the exception class.
    caplog.set_level("CRITICAL")
    try:
        if provider == "edgar":
            assert edgar_client._client.headers.get("User-Agent")
            response = edgar_client.get_submissions(identifier)
            keys = ["cik", "name", "sic", "sicDescription", "tickers"]
            assert str(response["sic"]) == expected_code
            assert str(response["cik"]).lstrip("0") == identifier.lstrip("0")
            source = f"https://data.sec.gov/submissions/CIK{identifier.zfill(10)}.json"
        else:
            response = dart_client.get_single_company_info(identifier)
            keys = ["corp_code", "corp_name", "induty_code", "stock_code"]
            assert str(response["induty_code"]).startswith(expected_code)
            assert response["corp_code"] == identifier
            assert response["stock_code"] == name
            source = (
                f"https://opendart.fss.or.kr/api/company.json?corp_code={identifier}"
            )
    except Exception as exc:
        pytest.fail(f"{provider} {identifier}: {type(exc).__name__}", pytrace=False)
    extracted = {key: response[key] for key in keys}
    if record:
        captured = {
            **extracted,
            "_note": {
                "source_url": source,
                "as_of": datetime.now(timezone(timedelta(hours=9))).isoformat(),
                "capture": "J-3a authoritative industry; one guarded request; selected public fields only",
            },
        }
        data = (
            (json.dumps(captured, ensure_ascii=False, indent=2) + "\n")
            .replace("\n", "\r\n")
            .encode("utf-8")
        )
        assert b"\0" not in data
        scratch = path.with_suffix(".json.tmp")
        scratch.write_bytes(data)
        scratch.replace(path)
    fixture = json.loads(path.read_text(encoding="utf-8"))
    assert extracted == {key: fixture[key] for key in keys}


def _stub_industry_auto_fetch(monkeypatch, identity):
    import pipeline.profile_generator as pg
    from pipeline.data_fetcher import DataFetcher

    captured = {}
    monkeypatch.setattr(DataFetcher, "identify", lambda self, *a, **kw: identity)
    monkeypatch.setattr(
        DataFetcher,
        "fetch_financials",
        lambda self, company: {2025: {"revenue": 1000, "op": 100}},
    )
    monkeypatch.setattr(
        DataFetcher, "fetch_shares", lambda self, company: {"shares_total": 1000}
    )

    def generate(company, financials, shares, industry_metadata=None):
        captured.update(industry_metadata)
        return "profiles/test.yaml"

    monkeypatch.setattr(pg, "_generate_draft_profile", generate)
    return captured


@pytest.mark.parametrize(
    "filename, market, code, expected",
    [
        ("edgar_submissions_aapl.json", "US", "SIC:3571", False),
        ("edgar_submissions_jpm.json", "US", "SIC:6021", True),
        ("dart_company_005930.json", "KR", "KSIC:264", False),
        ("dart_company_105560.json", "KR", "KSIC:64992", True),
    ],
)
@pytest.mark.parametrize("existing_industry", ["", "Manual industry: preserve this"])
def test_auto_fetch_authoritative_industry_fixture(
    filename, market, code, expected, existing_industry, monkeypatch
):
    import json
    from pathlib import Path

    from engine.industry_codes import is_financial_code
    from pipeline import dart_client, edgar_client
    import pipeline.profile_generator as pg

    payload = json.loads(
        (Path(__file__).parent / "fixtures" / filename).read_text(encoding="utf-8")
    )
    identity = CompanyIdentity(
        "SyntheticCo",
        market,
        cik=payload.get("cik"),
        corp_code=payload.get("corp_code"),
    )
    identity.industry = existing_industry
    captured = _stub_industry_auto_fetch(monkeypatch, identity)
    calls = []

    def response(identifier):
        calls.append(identifier)
        return payload

    monkeypatch.setattr(edgar_client, "get_submissions", response)
    monkeypatch.setattr(dart_client, "get_single_company_info", response)
    fetched = pg.auto_fetch("SyntheticCo", market_hint=market)
    label = payload.get("sicDescription")
    assert captured == {
        "industry": existing_industry or label or "",
        "industry_code": code,
        "industry_code_label": label,
        "industry_source": "edgar_submissions" if market == "US" else "dart_company",
    }
    assert is_financial_code(captured["industry_code"]) is expected
    assert len(calls) == 1
    assert calls[0] == (identity.cik if market == "US" else identity.corp_code)
    assert identity.industry == existing_industry
    assert fetched["yaml_path"] == "profiles/test.yaml"


@pytest.mark.parametrize("provider", ["edgar", "dart"])
def test_industry_failure_warns_once_and_auto_fetch_continues(
    provider, monkeypatch, caplog
):
    import logging
    from pipeline import dart_client, edgar_client
    import pipeline.profile_generator as pg

    identity = CompanyIdentity(
        "SyntheticCo",
        "US" if provider == "edgar" else "KR",
        cik="320193",
        corp_code="00126380",
    )
    identity.industry = "Keep manual label"
    captured = _stub_industry_auto_fetch(monkeypatch, identity)

    def unavailable(identifier):
        raise RuntimeError("exception text must not enter logs")

    monkeypatch.setattr(edgar_client, "get_submissions", unavailable)
    monkeypatch.setattr(dart_client, "get_single_company_info", unavailable)
    with caplog.at_level(logging.WARNING, logger="pipeline.profile_generator"):
        fetched = pg.auto_fetch("SyntheticCo")
    assert fetched["yaml_path"] == "profiles/test.yaml"
    assert captured == {
        "industry": "Keep manual label",
        "industry_code": None,
        "industry_code_label": None,
        "industry_source": None,
    }
    warnings = [r for r in caplog.records if r.name == "pipeline.profile_generator"]
    assert len(warnings) == 1
    assert "Authoritative industry unavailable" in warnings[0].message
    assert "exception text must not enter logs" not in caplog.text


def test_industry_missing_code_and_unsupported_market(monkeypatch, caplog):
    from pipeline import edgar_client, dart_client
    import pipeline.profile_generator as pg

    calls = []

    def missing(identifier):
        calls.append(identifier)
        return {"sicDescription": "Unknown"}

    monkeypatch.setattr(edgar_client, "get_submissions", missing)
    monkeypatch.setattr(dart_client, "get_single_company_info", missing)
    metadata = pg._fetch_industry_metadata(
        CompanyIdentity("Missing", "US", cik="320193")
    )
    assert metadata["industry_code"] is None
    assert metadata["industry_source"] is None
    assert "Authoritative industry unavailable" in caplog.text
    metadata = pg._fetch_industry_metadata(CompanyIdentity("JP", "JP"))
    assert metadata["industry_code"] is None
    assert len(calls) == 1


@pytest.mark.parametrize(
    "market, code, source, label",
    [
        ("US", "SIC:3571", "edgar_submissions", "Electronic Computers"),
        ("US", "SIC:6021", "edgar_submissions", "National Commercial Banks"),
        ("KR", "KSIC:264", "dart_company", None),
        ("KR", "KSIC:64992", "dart_company", None),
    ],
)
def test_industry_metadata_survives_draft_yaml_and_load(
    market, code, source, label, monkeypatch, tmp_path
):
    import yaml
    import pipeline.profile_generator as pg
    import pipeline.macro_data as macro_data
    from valuation_runner import load_profile

    monkeypatch.setattr(pg, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        pg,
        "_estimate_wacc_params",
        lambda *a: {
            "rf": 3,
            "erp": 5,
            "bu": 1,
            "tax": 22,
            "kd_pre": 4,
            "de": 50,
            "eq_w": 70,
        },
    )
    monkeypatch.setattr(macro_data, "get_terminal_growth", lambda *a, **kw: 2)
    monkeypatch.setattr(macro_data, "get_diluted_shares", lambda *a, **kw: None)
    identity = CompanyIdentity("SyntheticCo", market, legal_status="상장")
    financials = {
        2025: {
            "revenue": 1000,
            "op": 100,
            "dep": 20,
            "amort": 0,
            "assets": 1000,
            "liabilities": 400,
            "equity": 600,
            "net_borr": 0,
        }
    }
    shares = {
        "shares_total": 1000,
        "shares_ordinary": 1000,
        "price": 100,
        "market_cap": 0.1,
    }
    metadata = {
        "industry": label or "",
        "industry_code": code,
        "industry_code_label": label,
        "industry_source": source,
    }
    filename = pg._generate_draft_profile(
        identity, financials, shares, industry_metadata=metadata
    )
    path = tmp_path / filename
    company = yaml.safe_load(path.read_text(encoding="utf-8"))["company"]
    assert all(company[key] == value for key, value in metadata.items())
    vi = load_profile(str(path))
    assert vi.industry_code == vi.company.industry_code == code
    assert vi.company.industry_code_label == label
    assert vi.company.industry_source == source
    assert vi.industry == (label or "")


# ═══════════════════════════════════════════════════════════
# J-4: wacc_adj is not persisted where no discount rate is consumed
# ═══════════════════════════════════════════════════════════


def _ai_output_with_wacc_adj() -> tuple[list[dict], list[dict]]:
    scenarios = [
        {
            "code": "Bull",
            "drivers": {"growth_adj_pct": 20, "wacc_adj": -0.4},
            "driver_rationale": {"growth_adj_pct": "demand", "wacc_adj": "rates"},
        },
        {"code": "Base", "drivers": {"growth_adj_pct": 0, "wacc_adj": 0.0}},
        {
            "code": "Bear",
            "active_drivers": {"rate_hike": 1.0},
            "segment_multiples": {"SEG1": 8.0},
        },
    ]
    news_drivers = [
        {"id": "rate_hike", "effects": {"wacc_adj": 0.5, "growth_adj_pct": -10}},
        {"id": "tariff", "effects": {"market_sentiment_pct": -5}},
    ]
    return scenarios, news_drivers


@pytest.mark.parametrize("method", ["sotp", "nav", "multiples"])
def test_strip_unsupported_drivers_removes_wacc_adj(method):
    import copy

    from pipeline.profile_generator import _strip_unsupported_drivers

    scenarios, news_drivers = _ai_output_with_wacc_adj()
    untouched = copy.deepcopy((scenarios, news_drivers))

    out_scenarios, out_news, dropped = _strip_unsupported_drivers(
        scenarios, news_drivers, method
    )

    assert out_scenarios == [
        {
            "code": "Bull",
            "drivers": {"growth_adj_pct": 20},
            "driver_rationale": {"growth_adj_pct": "demand"},
        },
        {"code": "Base", "drivers": {"growth_adj_pct": 0}},
        {
            "code": "Bear",
            "active_drivers": {"rate_hike": 1.0},
            "segment_multiples": {"SEG1": 8.0},
        },
    ]
    assert out_news == [
        {"id": "rate_hike", "effects": {"growth_adj_pct": -10}},
        {"id": "tariff", "effects": {"market_sentiment_pct": -5}},
    ]
    assert dropped == [
        "scenarios.Bull.drivers",
        "scenarios.Bull.driver_rationale",
        "scenarios.Base.drivers",
        "news_drivers.rate_hike.effects",
    ]
    assert (scenarios, news_drivers) == untouched  # inputs are not mutated


@pytest.mark.parametrize("method", ["dcf_primary", "dcf", "ddm", "rim", "rnpv"])
def test_strip_unsupported_drivers_keeps_discount_rate_methods(method):
    from pipeline.profile_generator import _strip_unsupported_drivers

    scenarios, news_drivers = _ai_output_with_wacc_adj()

    out_scenarios, out_news, dropped = _strip_unsupported_drivers(
        scenarios, news_drivers, method
    )

    assert out_scenarios is scenarios and out_news is news_drivers
    assert (out_scenarios, out_news) == _ai_output_with_wacc_adj()
    assert dropped == []


def test_auto_analyze_does_not_persist_wacc_adj_for_sotp(harness, capsys):  # noqa: F811
    """The one call site: an LLM answer that still carries wacc_adj for SOTP."""
    import copy

    import yaml

    scenarios = copy.deepcopy(k0c.SCENARIOS)
    for sc in scenarios["scenarios"]:
        sc["drivers"]["wacc_adj"] = {"Base": 0.0, "Bull": -0.7, "Bear": 0.7}[sc["code"]]
        sc["driver_rationale"] = {"wacc_adj": "rate view"}
    scenarios["news_drivers"] = [
        {"id": "rate_hike", "name": "Rate hike", "effects": {"wacc_adj": 0.5}}
    ]
    harness.returns["ai.scenarios"] = scenarios
    harness.identity["SynCo"] = k0c.kr_identity()

    result = harness.pg.auto_analyze(
        "SynCo",
        output_dir=str(harness.out),
        scored_data={"market": "KR", "ticker": "123456"},
    )

    out = capsys.readouterr().out
    assert out.count("[WARN] wacc_adj 7건 제거 — sotp는 할인율을 소비하지 않음") == 1
    saved = (harness.root / "profiles" / "123456.yaml").read_text(encoding="utf-8")
    assert "wacc_adj" not in saved
    assert yaml.safe_load(saved)["news_drivers"][0]["effects"] == {}
    assert result.result.primary_method == "sotp"
    assert "UNSUPPORTED_DRIVER" not in {w.code for w in result.result.engine_warnings}
    assert result.validation_report.status == "ok"
    assert result.result.weighted_value == pytest.approx(
        k0c.PINNED_WEIGHTED_VALUE, rel=1e-9
    )
