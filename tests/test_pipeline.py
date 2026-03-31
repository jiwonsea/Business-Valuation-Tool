"""Pipeline unit tests — exchange classification, CompanyIdentity, schema model validation."""

import pytest
from pipeline.yahoo_finance import classify_exchange
from pipeline.data_fetcher import CompanyIdentity, _is_korean, _is_likely_ticker
from schemas.models import (
    CompanyProfile,
    WACCParams,
    ScenarioParams,
    DCFParams,
    PeerCompany,
    ValuationInput,
    ConsolidatedFinancials,
)


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
            name="테스트", shares_total=100_000, shares_ordinary=80_000,
        )
        assert cp.legal_status == "비상장"
        assert cp.market == "KR"
        assert cp.currency == "KRW"
        assert cp.unit_multiplier == 1_000_000
        assert cp.shares_preferred == 0
        assert cp.ticker is None

    def test_company_profile_us(self):
        cp = CompanyProfile(
            name="TestCo", market="US", currency="USD", currency_unit="$M",
            shares_total=1_000_000, shares_ordinary=1_000_000,
            legal_status="상장", ticker="TEST",
        )
        assert cp.market == "US"
        assert cp.ticker == "TEST"

    def test_consolidated_properties(self):
        cf = ConsolidatedFinancials(
            year=2025, revenue=10_000, op=1_000, net_income=700,
            assets=50_000, liabilities=30_000, equity=20_000,
            dep=500, amort=200,
        )
        assert cf.da == 700
        assert cf.ebitda == 1_700

    def test_scenario_params_optional_fields(self):
        sp = ScenarioParams(
            code="A", name="테스트", prob=50, ipo="N/A", shares=10_000,
        )
        assert sp.irr is None
        assert sp.cps_repay is None
        assert sp.dlom == 0
        assert sp.rcps_repay == 0
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
        wp = WACCParams(rf=3.5, erp=7.0, bu=0.75, de=192.0, tax=22.0, kd_pre=5.5, eq_w=34.2)
        assert wp.rf == 3.5
        assert wp.eq_w == 34.2
