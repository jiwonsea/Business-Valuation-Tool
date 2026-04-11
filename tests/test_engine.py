"""Engine regression & unit tests."""

from pathlib import Path

from schemas.models import WACCParams, ScenarioParams, DCFParams, DAAllocation
from engine.wacc import calc_wacc
from engine.sotp import allocate_da, calc_sotp
from engine.dcf import calc_dcf
from engine.scenario import calc_scenario
from engine.sensitivity import (
    sensitivity_multiples,
    sensitivity_irr_dlom,
    sensitivity_dcf,
    sensitivity_ddm,
    sensitivity_rim,
    sensitivity_nav,
    sensitivity_multiple_range,
)
from engine.multiples import cross_validate, calc_ev_revenue, calc_pe, calc_pbv
from engine.peer_analysis import calc_peer_stats
from engine.monte_carlo import MCInput, run_monte_carlo
from engine.units import detect_unit, per_share
from engine.method_selector import suggest_method
from engine.ddm import calc_ddm
from engine.rim import calc_rim
from engine.multiples import calc_ps, calc_pffo
from engine.market_comparison import compare_to_market
from engine.nav import calc_nav
from engine.rnpv import calc_rnpv, PHASE_POS
from engine.growth import linear_fade, calc_ebitda_growth, generate_growth_rates
from engine.distress import calc_distress_discount, apply_distress_discount
from engine.method_selector import classify_industry
from engine.drivers import resolve_drivers
from engine.gap_diagnostics import diagnose_gap
from engine.reverse_rnpv import (
    reverse_rnpv,
    solve_implied_pos_scale,
    solve_implied_peak_scale,
    solve_implied_discount_rate,
    solve_implied_per_drug_pos,
)
from engine.sensitivity import sensitivity_rnpv, sensitivity_rnpv_tornado
from schemas.models import NewsDriver


# ── SK Ecoplant reference data ──

SK_SEG_DATA_2025 = {
    "HI": {
        "revenue": 5_158_561,
        "gross_profit": 271_510,
        "op": 74_208,
        "assets": 511_209,
    },
    "GAS": {
        "revenue": 385_640,
        "gross_profit": 121_126,
        "op": 79_644,
        "assets": 1_302_785,
    },
    "ALC": {
        "revenue": 2_596_506,
        "gross_profit": 344_714,
        "op": 169_356,
        "assets": 1_258_024,
    },
    "SOL": {
        "revenue": 4_050_862,
        "gross_profit": 416_820,
        "op": -7_264,
        "assets": 1_407_514,
    },
    "ETC": {"revenue": 0, "gross_profit": 0, "op": 0, "assets": 23_007},
}
SK_DA_2025 = 182_334 + 129_299  # dep + amort = 311,633
SK_MULTIPLES = {"HI": 8.0, "GAS": 10.0, "ALC": 13.0, "SOL": 5.0, "ETC": 0.0}
SK_NET_DEBT = 2_295_568
SK_ECO_FRONTIER = 94_644
SK_CPS_PRINCIPAL = 600_000
SK_CPS_YEARS = 4
SK_RCPS_PRINCIPAL = 400_000
SK_RCPS_YEARS = 5
SK_SHARES_TOTAL = 65_599_748
SK_SHARES_ORDINARY = 54_278_993


# ═══════════════════════════════════════════════════════════
# Units Tests
# ═══════════════════════════════════════════════════════════


class TestUnits:
    def test_detect_unit_kr_small(self):
        label, mult = detect_unit(5_000, "KR")
        assert label == "백만원"
        assert mult == 1_000_000

    def test_detect_unit_kr_medium(self):
        label, mult = detect_unit(50_000, "KR")
        assert label == "억원"
        assert mult == 100_000_000

    def test_detect_unit_kr_large(self):
        label, mult = detect_unit(5_000_000, "KR")
        assert label == "백만원"
        assert mult == 1_000_000

    def test_detect_unit_us(self):
        label, mult = detect_unit(100_000, "US")
        assert label == "$M"
        assert mult == 1_000_000

    def test_per_share_basic(self):
        assert per_share(1_000_000, 1_000_000, 50_000_000) == 20_000

    def test_per_share_zero_equity(self):
        assert per_share(0, 1_000_000, 50_000_000) == 0

    def test_per_share_negative(self):
        """Negative equity propagates (distress scenarios should not be clamped to 0)."""
        assert per_share(-100, 1_000_000, 50_000_000) == -2

    def test_per_share_억원_unit(self):
        """100M KRW unit: 1 (=100M KRW) equity, 10M shares"""
        assert per_share(1, 100_000_000, 10_000_000) == 10


# ═══════════════════════════════════════════════════════════
# Method Selector Tests
# ═══════════════════════════════════════════════════════════


class TestMethodSelector:
    def test_multi_segment_sotp(self):
        assert suggest_method(5) == "sotp"

    def test_single_segment_dcf(self):
        assert suggest_method(1) == "dcf_primary"

    def test_financial_ddm(self):
        assert suggest_method(1, industry="은행") == "ddm"
        assert suggest_method(1, industry="insurance") == "ddm"

    def test_growth_dcf(self):
        assert suggest_method(1, industry="소프트웨어") == "dcf_primary"

    def test_holding_nav(self):
        assert suggest_method(1, industry="지주회사") == "nav"
        assert suggest_method(1, industry="REIT") == "nav"

    def test_mature_with_peers_multiples(self):
        assert suggest_method(1, industry="유통", has_peers=True) == "multiples"

    def test_mature_without_peers_dcf(self):
        """No peers available: mature industry falls back to DCF"""
        assert suggest_method(1, industry="유통", has_peers=False) == "dcf_primary"


# ═══════════════════════════════════════════════════════════
# DDM Tests
# ═══════════════════════════════════════════════════════════


class TestDDM:
    def test_basic_ddm(self):
        r = calc_ddm(dps=1000, growth=3.0, ke=10.0)
        # DPS * (1.03) / (0.10 - 0.03) = 1030 / 0.07 = 14,714
        assert r.equity_per_share == 14_714

    def test_ddm_narrow_spread_warning(self):
        """W-5: ke-growth < 2%p emits warning"""
        r = calc_ddm(dps=1000, growth=9.0, ke=10.0)
        assert len(r.warnings) == 1
        assert "스프레드" in r.warnings[0]

    def test_ddm_wide_spread_no_warning(self):
        """ke-growth >= 2%p: no warning"""
        r = calc_ddm(dps=1000, growth=3.0, ke=10.0)
        assert len(r.warnings) == 0

    def test_ddm_growth_equals_ke(self):
        """ke <= growth raises ValueError"""
        import pytest

        with pytest.raises(ValueError):
            calc_ddm(dps=1000, growth=10.0, ke=10.0)


# ═══════════════════════════════════════════════════════════
# Market Comparison Tests
# ═══════════════════════════════════════════════════════════


class TestMarketComparison:
    def test_no_gap(self):
        mc = compare_to_market(10000, 10000)
        assert mc.gap_ratio == 0.0
        assert mc.flag == ""

    def test_large_gap(self):
        mc = compare_to_market(20000, 10000)
        assert mc.gap_ratio == 1.0
        assert "재검토" in mc.flag

    def test_moderate_gap(self):
        mc = compare_to_market(16000, 10000)
        assert mc.gap_ratio == 0.6
        assert "확인" in mc.flag

    def test_zero_price(self):
        mc = compare_to_market(10000, 0)
        assert "데이터 없음" in mc.flag


# ═══════════════════════════════════════════════════════════
# WACC Tests
# ═══════════════════════════════════════════════════════════


class TestWACC:
    def test_sk_wacc(self):
        p = WACCParams(
            rf=3.50, erp=7.00, bu=0.750, de=192.0, tax=22.0, kd_pre=5.50, eq_w=34.2
        )
        r = calc_wacc(p)
        assert r.bl == 1.873
        assert r.ke == 16.61
        assert r.kd_at == 4.29
        assert r.wacc == 8.50

    def test_zero_leverage(self):
        p = WACCParams(
            rf=3.0, erp=6.0, bu=1.0, de=0.0, tax=25.0, kd_pre=5.0, eq_w=100.0
        )
        r = calc_wacc(p)
        assert r.bl == 1.0
        assert r.wacc == r.ke

    def test_distress_premium_below_cap(self):
        """D/E <= 200%: no distress premium."""
        p = WACCParams(
            rf=3.0, erp=6.0, bu=1.0, de=200.0, tax=25.0, kd_pre=5.0, eq_w=50.0
        )
        r = calc_wacc(p)
        assert r.distress_premium == 0.0

    def test_distress_premium_above_cap(self):
        """D/E > 200%: linear distress premium up to 3%."""
        p = WACCParams(
            rf=3.0, erp=6.0, bu=1.0, de=350.0, tax=25.0, kd_pre=5.0, eq_w=50.0
        )
        r = calc_wacc(p)
        # (350-200)/(500-200)*3.0 = 150/300*3.0 = 1.5%
        assert r.distress_premium == 1.5
        # WACC includes the premium
        p_at_cap = WACCParams(
            rf=3.0, erp=6.0, bu=1.0, de=200.0, tax=25.0, kd_pre=5.0, eq_w=50.0
        )
        r_cap = calc_wacc(p_at_cap)
        assert r.wacc > r_cap.wacc

    def test_distress_premium_max_at_500(self):
        """D/E >= 500%: premium capped at 3%."""
        p = WACCParams(
            rf=3.0, erp=6.0, bu=1.0, de=800.0, tax=25.0, kd_pre=5.0, eq_w=50.0
        )
        r = calc_wacc(p)
        assert r.distress_premium == 3.0

    def test_distress_premium_financial_exempt(self):
        """Financial sector: no distress premium regardless of D/E."""
        p = WACCParams(
            rf=3.0,
            erp=6.0,
            bu=0.8,
            de=1500.0,
            tax=25.0,
            kd_pre=5.0,
            eq_w=100.0,
            is_financial=True,
        )
        r = calc_wacc(p)
        assert r.distress_premium == 0.0


# ═══════════════════════════════════════════════════════════
# SOTP Tests
# ═══════════════════════════════════════════════════════════


class TestSOTP:
    def test_sk_da_allocation(self):
        alloc = allocate_da(SK_SEG_DATA_2025, SK_DA_2025)
        total_allocated = sum(a.da_allocated for a in alloc.values())
        assert abs(total_allocated - SK_DA_2025) <= 5

        total_share = sum(a.asset_share for a in alloc.values())
        assert abs(total_share - 100.0) < 0.1

    def test_sk_sotp_ev(self):
        alloc = allocate_da(SK_SEG_DATA_2025, SK_DA_2025)
        sotp, total_ev = calc_sotp(alloc, SK_MULTIPLES)
        assert 6_300_000 < total_ev < 6_400_000

    def test_negative_ebitda_floored_to_zero(self):
        """W-8: negative EBITDA → EV floored to 0 (conservative approach)."""
        alloc = allocate_da({"A": {"op": -100, "assets": 100}}, 50)
        sotp, ev = calc_sotp(alloc, {"A": 10.0})
        # EBITDA = -100 + 50 = -50, EV floored to 0
        assert sotp["A"].ev == 0
        assert ev == 0

    def test_mixed_positive_negative_ebitda(self):
        """W-8: mixed segments — negative EBITDA segment floored to EV=0."""
        alloc = allocate_da(
            {
                "A": {"op": 200, "assets": 100},
                "B": {"op": -200, "assets": 100},
            },
            100,
        )
        sotp, ev = calc_sotp(alloc, {"A": 10.0, "B": 5.0})
        assert sotp["A"].ev > 0
        assert sotp["B"].ev == 0  # Negative EBITDA floored to 0
        assert ev == sotp["A"].ev  # Only positive segment contributes

    def test_ev_revenue_basic(self):
        """ev_revenue: EV = revenue × multiple."""
        alloc = allocate_da(
            {"FSD": {"op": 0, "assets": 0}}, 0, segment_methods={"FSD": "ev_revenue"}
        )
        sotp, ev = calc_sotp(
            alloc,
            {"FSD": 15.0},
            segments_info={"FSD": {"name": "FSD", "method": "ev_revenue"}},
            revenue_by_seg={"FSD": 5000},
        )
        assert sotp["FSD"].ev == 75000  # 5000 * 15.0
        assert sotp["FSD"].method == "ev_revenue"
        assert sotp["FSD"].revenue == 5000
        assert sotp["FSD"].is_equity_based is False
        assert ev == 75000

    def test_ev_revenue_with_override(self):
        """ev_revenue: revenue_override and multiple_override apply."""
        alloc = allocate_da(
            {"FSD": {"op": 0, "assets": 0}}, 0, segment_methods={"FSD": "ev_revenue"}
        )
        sotp, ev = calc_sotp(
            alloc,
            {"FSD": 15.0},
            segments_info={"FSD": {"name": "FSD", "method": "ev_revenue"}},
            revenue_by_seg={"FSD": 5000},
            revenue_override={"FSD": 20000},
            multiple_override={"FSD": 20.0},
        )
        assert sotp["FSD"].ev == 400000  # 20000 * 20.0
        assert sotp["FSD"].revenue == 20000

    def test_ev_revenue_zero(self):
        """ev_revenue: revenue=0 → EV=0 (pre-launch segment)."""
        alloc = allocate_da(
            {"ROBO": {"op": 0, "assets": 0}}, 0, segment_methods={"ROBO": "ev_revenue"}
        )
        sotp, ev = calc_sotp(
            alloc,
            {"ROBO": 25.0},
            segments_info={"ROBO": {"name": "Robotaxi", "method": "ev_revenue"}},
            revenue_by_seg={"ROBO": 0},
        )
        assert sotp["ROBO"].ev == 0
        assert ev == 0

    def test_mixed_ebitda_and_revenue(self):
        """Mixed ev_ebitda + ev_revenue: total_ev = sum of both."""
        seg_data = {"AUTO": {"op": 4000, "assets": 100}, "FSD": {"op": 0, "assets": 0}}
        seg_methods = {"AUTO": "ev_ebitda", "FSD": "ev_revenue"}
        alloc = allocate_da(seg_data, 500, segment_methods=seg_methods)
        sotp, ev = calc_sotp(
            alloc,
            {"AUTO": 8.0, "FSD": 15.0},
            segments_info={
                "AUTO": {"name": "Automotive", "method": "ev_ebitda"},
                "FSD": {"name": "FSD", "method": "ev_revenue"},
            },
            revenue_by_seg={"AUTO": 80000, "FSD": 5000},
        )
        # AUTO: EBITDA = 4000 + 500 = 4500, EV = 4500 * 8.0 = 36000
        assert sotp["AUTO"].method == "ev_ebitda"
        assert sotp["AUTO"].ev == 36000
        # FSD: Revenue = 5000, EV = 5000 * 15.0 = 75000
        assert sotp["FSD"].method == "ev_revenue"
        assert sotp["FSD"].ev == 75000
        assert ev == 36000 + 75000

    def test_allocate_da_excludes_ev_revenue(self):
        """D&A allocation excludes ev_revenue segments (like pbv/pe)."""
        seg_data = {"A": {"op": 1000, "assets": 200}, "B": {"op": 0, "assets": 50}}
        alloc = allocate_da(
            seg_data, 100, segment_methods={"A": "ev_ebitda", "B": "ev_revenue"}
        )
        # 100% of D&A goes to A (only ev_ebitda segment)
        assert alloc["A"].da_allocated == 100
        assert alloc["A"].asset_share == 100.0
        assert alloc["B"].da_allocated == 0
        assert alloc["B"].asset_share == 0


# ═══════════════════════════════════════════════════════════
# Scenario Tests
# ═══════════════════════════════════════════════════════════


class TestScenario:
    def _get_sk_ev(self):
        alloc = allocate_da(SK_SEG_DATA_2025, SK_DA_2025)
        _, ev = calc_sotp(alloc, SK_MULTIPLES)
        return ev

    def test_sk_scenario_a(self):
        ev = self._get_sk_ev()
        sc = ScenarioParams(
            code="A",
            name="IPO 성공",
            prob=20,
            ipo="성공",
            dlom=0,
            cps_repay=0,
            rcps_repay=0,
            buyback=0,
            shares=SK_SHARES_TOTAL,
        )
        r = calc_scenario(
            sc,
            ev,
            SK_NET_DEBT,
            SK_ECO_FRONTIER,
            SK_CPS_PRINCIPAL,
            SK_CPS_YEARS,
            SK_RCPS_PRINCIPAL,
            SK_RCPS_YEARS,
        )
        assert r.post_dlom > 0
        assert r.pre_dlom == r.post_dlom  # DLOM=0

    def test_sk_scenario_b(self):
        ev = self._get_sk_ev()
        sc = ScenarioParams(
            code="B",
            name="FI 우호",
            prob=45,
            ipo="불발",
            irr=5.0,
            dlom=20,
            rcps_repay=490_000,
            buyback=200_000,
            shares=SK_SHARES_ORDINARY,
        )
        r = calc_scenario(
            sc,
            ev,
            SK_NET_DEBT,
            SK_ECO_FRONTIER,
            SK_CPS_PRINCIPAL,
            SK_CPS_YEARS,
            SK_RCPS_PRINCIPAL,
            SK_RCPS_YEARS,
        )
        assert r.post_dlom > 0
        assert r.post_dlom < r.pre_dlom  # DLOM applied

    def test_scenario_with_different_unit_multiplier(self):
        """Verify per-share value is correct in 100M KRW unit"""
        sc = ScenarioParams(
            code="A",
            name="Test",
            prob=100,
            ipo="N/A",
            dlom=0,
            shares=10_000_000,
        )
        r = calc_scenario(sc, 100, 0, 0, 0, 0, unit_multiplier=100_000_000)
        # 10B KRW equity / 10M shares = 1,000 KRW/share
        assert r.pre_dlom == 1_000

    def test_negative_equity(self):
        sc = ScenarioParams(
            code="A",
            name="Neg",
            prob=100,
            ipo="N/A",
            dlom=0,
            shares=10_000,
        )
        r = calc_scenario(sc, 100, 200, 0, 0, 0)
        assert r.equity_value < 0
        assert r.pre_dlom < 0  # Negative equity propagates for distress scenarios
        assert r.post_dlom < 0  # DLOM not applied to negative equity

    def test_cps_dividend_rate_reduces_repay(self):
        """W-9: CPS dividend rate reduces effective compound rate."""
        sc = ScenarioParams(
            code="A",
            name="Test",
            prob=100,
            ipo="불발",
            irr=10.0,
            dlom=0,
            shares=100_000,
        )
        # Without dividend: repay = 1000 * (1.10)^5 = 1610
        r_zero = calc_scenario(sc, 10_000, 0, 0, 1_000, 5, cps_dividend_rate=0.0)
        # With 5% dividend: effective rate = 5%, repay = 1000 * (1.05)^5 = 1276
        r_div = calc_scenario(sc, 10_000, 0, 0, 1_000, 5, cps_dividend_rate=5.0)
        assert r_div.cps_repay < r_zero.cps_repay
        assert r_div.equity_value > r_zero.equity_value  # Less claim = more equity

    def test_rcps_dividend_rate_reduces_repay(self):
        """W-9: RCPS dividend rate reduces effective compound rate."""
        sc = ScenarioParams(
            code="A",
            name="Test",
            prob=100,
            ipo="불발",
            irr=10.0,
            dlom=0,
            shares=100_000,
        )
        r_zero = calc_scenario(sc, 10_000, 0, 0, 0, 0, 1_000, 5, rcps_dividend_rate=0.0)
        r_div = calc_scenario(sc, 10_000, 0, 0, 0, 0, 1_000, 5, rcps_dividend_rate=7.5)
        assert r_div.rcps_repay < r_zero.rcps_repay


# ═══════════════════════════════════════════════════════════
# DCF Tests
# ═══════════════════════════════════════════════════════════


class TestDCF:
    def test_sk_dcf(self):
        params = DCFParams(
            ebitda_growth_rates=[0.10, 0.08, 0.06, 0.05, 0.04],
            tax_rate=22.0,
            capex_to_da=1.10,
            nwc_to_rev_delta=0.05,
            terminal_growth=2.5,
        )
        ebitda_base = 315_944 + SK_DA_2025
        r = calc_dcf(ebitda_base, SK_DA_2025, 12_191_569, 8.50, params, 2025)
        assert len(r.projections) == 5
        assert r.projections[0].year == 2026
        assert r.ev_dcf > 0

    def test_high_wacc_low_ev(self):
        params = DCFParams(
            ebitda_growth_rates=[0.05],
            tax_rate=25.0,
            capex_to_da=1.0,
            nwc_to_rev_delta=0.0,
            terminal_growth=2.0,
        )
        low = calc_dcf(1000, 500, 5000, 15.0, params)
        high = calc_dcf(1000, 500, 5000, 7.0, params)
        assert low.ev_dcf < high.ev_dcf

    def test_actual_capex_nwc(self):
        base_params = DCFParams(
            ebitda_growth_rates=[0.10, 0.08],
            tax_rate=22.0,
            capex_to_da=1.10,
            nwc_to_rev_delta=0.05,
            terminal_growth=2.5,
        )
        actual_params = DCFParams(
            ebitda_growth_rates=[0.10, 0.08],
            tax_rate=22.0,
            capex_to_da=1.10,
            nwc_to_rev_delta=0.05,
            terminal_growth=2.5,
            actual_capex=400,
            actual_nwc=300,
            prior_nwc=280,
        )
        r_base = calc_dcf(1000, 500, 5000, 8.5, base_params)
        r_actual = calc_dcf(1000, 500, 5000, 8.5, actual_params)
        assert r_base.ev_dcf != r_actual.ev_dcf
        assert r_actual.ev_dcf > r_base.ev_dcf

    def test_revenue_growth_rates_separate_from_ebitda(self):
        """Separate revenue_growth_rates produce different NWC delta vs EBITDA rates."""
        base_params = DCFParams(
            ebitda_growth_rates=[0.10, 0.10, 0.10, 0.10, 0.10],
            tax_rate=22.0,
            capex_to_da=1.0,
            nwc_to_rev_delta=0.05,
            terminal_growth=2.5,
        )
        # Higher revenue growth → larger delta_NWC → lower FCFF
        rev_params = DCFParams(
            ebitda_growth_rates=[0.10, 0.10, 0.10, 0.10, 0.10],
            revenue_growth_rates=[0.20, 0.20, 0.20, 0.20, 0.20],
            tax_rate=22.0,
            capex_to_da=1.0,
            nwc_to_rev_delta=0.05,
            terminal_growth=2.5,
        )
        r_base = calc_dcf(1000, 300, 5000, 8.5, base_params)
        r_rev = calc_dcf(1000, 300, 5000, 8.5, rev_params)
        # Higher revenue growth → higher NWC drain → lower DCF EV
        assert r_rev.ev_dcf < r_base.ev_dcf

    def test_revenue_growth_rates_fallback_to_ebitda(self):
        """Omitting revenue_growth_rates produces same result as setting them equal to EBITDA rates."""
        growth = [0.08, 0.06, 0.05, 0.04, 0.03]
        params_implicit = DCFParams(ebitda_growth_rates=growth, terminal_growth=2.5)
        params_explicit = DCFParams(
            ebitda_growth_rates=growth, revenue_growth_rates=growth, terminal_growth=2.5
        )
        r1 = calc_dcf(1000, 300, 5000, 8.5, params_implicit)
        r2 = calc_dcf(1000, 300, 5000, 8.5, params_explicit)
        assert r1.ev_dcf == r2.ev_dcf


# ═══════════════════════════════════════════════════════════
# Sensitivity Tests
# ═══════════════════════════════════════════════════════════


class TestSensitivity:
    def test_multiples_grid_size(self):
        alloc = allocate_da(SK_SEG_DATA_2025, SK_DA_2025)
        rows, hi_r, alc_r = sensitivity_multiples(
            alloc,
            SK_MULTIPLES,
            SK_NET_DEBT,
            SK_ECO_FRONTIER,
            SK_SHARES_TOTAL,
        )
        assert len(rows) == len(hi_r) * len(alc_r)

    def test_multiples_auto_segment_selection(self):
        """row_seg/col_seg not specified: auto-selects segments"""
        alloc = allocate_da(SK_SEG_DATA_2025, SK_DA_2025)
        rows, _, _ = sensitivity_multiples(
            alloc,
            SK_MULTIPLES,
            SK_NET_DEBT,
            SK_ECO_FRONTIER,
            SK_SHARES_TOTAL,
        )
        assert len(rows) > 0

    def test_irr_dlom_grid_size(self):
        alloc = allocate_da(SK_SEG_DATA_2025, SK_DA_2025)
        _, ev = calc_sotp(alloc, SK_MULTIPLES)
        rows, irr_r, dlom_r = sensitivity_irr_dlom(
            ev,
            SK_NET_DEBT,
            SK_ECO_FRONTIER,
            SK_CPS_PRINCIPAL,
            SK_CPS_YEARS,
            490_000,
            200_000,
            SK_SHARES_ORDINARY,
        )
        assert len(rows) == len(irr_r) * len(dlom_r)

    def test_dcf_sensitivity_monotonic(self):
        params = DCFParams(
            ebitda_growth_rates=[0.10, 0.08, 0.06, 0.05, 0.04],
            tax_rate=22.0,
            capex_to_da=1.10,
            nwc_to_rev_delta=0.05,
            terminal_growth=2.5,
        )
        rows, wacc_r, tg_r = sensitivity_dcf(
            627_577,
            SK_DA_2025,
            12_191_569,
            params,
            2025,
            wacc_range=[7.0, 8.0, 9.0, 10.0],
            tg_range=[2.5],
        )
        evs = [r.value for r in rows]
        for i in range(len(evs) - 1):
            assert evs[i] > evs[i + 1]

    def test_dcf_sensitivity_dynamic_wacc_range(self):
        """W-4: wacc_base -> dynamic range centered on actual WACC ± 2%p."""
        params = DCFParams(
            ebitda_growth_rates=[0.10, 0.08, 0.06, 0.05, 0.04],
            tax_rate=22.0,
            capex_to_da=1.10,
            nwc_to_rev_delta=0.05,
            terminal_growth=2.5,
        )
        rows, wacc_r, tg_r = sensitivity_dcf(
            627_577,
            SK_DA_2025,
            12_191_569,
            params,
            2025,
            wacc_base=8.5,
        )
        # Center snaps to 8.5, range = 8.5 ± 2.0 with 0.5 steps = [6.5..10.5]
        assert len(wacc_r) == 9
        assert min(wacc_r) == 6.5
        assert max(wacc_r) == 10.5
        # Monotonic: higher WACC -> lower EV (for fixed tg)
        first_tg = tg_r[0]
        evs_first_tg = [r.value for r in rows if r.col_val == first_tg]
        for i in range(len(evs_first_tg) - 1):
            assert evs_first_tg[i] >= evs_first_tg[i + 1]


# ═══════════════════════════════════════════════════════════
# Multiples Cross-Validation Tests
# ═══════════════════════════════════════════════════════════


class TestMultiples:
    def test_ev_revenue(self):
        r = calc_ev_revenue(
            revenue=10_000_000, multiple=0.5, net_debt=2_000_000, shares=50_000_000
        )
        assert r.method == "EV/Revenue"
        assert r.enterprise_value == 5_000_000
        assert r.equity_value == 3_000_000
        assert r.per_share == per_share(3_000_000, 1_000_000, 50_000_000)

    def test_pe(self):
        r = calc_pe(net_income=500_000, multiple=15.0, shares=50_000_000)
        assert r.method == "P/E"
        assert r.equity_value == 7_500_000

    def test_pe_negative_income(self):
        r = calc_pe(net_income=-100_000, multiple=15.0, shares=50_000_000)
        assert r.equity_value == 0
        assert r.per_share == 0

    def test_pbv(self):
        r = calc_pbv(book_value=2_000_000, multiple=1.2, shares=50_000_000)
        assert r.method == "P/BV"
        assert r.equity_value == 2_400_000

    def test_cross_validate_always_has_sotp_dcf(self):
        results = cross_validate(
            revenue=10_000_000,
            ebitda=1_000_000,
            net_income=500_000,
            book_value=2_000_000,
            net_debt=2_000_000,
            shares=50_000_000,
            sotp_ev=6_000_000,
            dcf_ev=5_500_000,
        )
        methods = [r.method for r in results]
        assert "SOTP (EV/EBITDA)" in methods
        assert "DCF (FCFF)" in methods
        assert len(results) == 2

    def test_cross_validate_with_all_multiples(self):
        results = cross_validate(
            revenue=10_000_000,
            ebitda=1_000_000,
            net_income=500_000,
            book_value=2_000_000,
            net_debt=2_000_000,
            shares=50_000_000,
            sotp_ev=6_000_000,
            dcf_ev=5_500_000,
            ev_revenue_multiple=0.5,
            pe_multiple=15.0,
            pbv_multiple=1.2,
        )
        assert len(results) == 5

    def test_cross_validate_sotp_ev_ebitda_only_excludes_equity_segments(self):
        """sotp_ev_ebitda_only corrects implied EV/EBITDA when pbv/pe segments inflate total_ev."""
        ebitda = 1_000_000
        ev_only = 5_000_000  # manufacturing EV/EBITDA segments only
        equity_seg = 2_000_000  # pbv segment equity value (not enterprise value)
        total_sotp = ev_only + equity_seg  # 7_000_000 passed as sotp_ev

        results_inflated = cross_validate(
            revenue=10_000_000,
            ebitda=ebitda,
            net_income=0,
            book_value=0,
            net_debt=1_000_000,
            shares=50_000_000,
            sotp_ev=total_sotp,
            dcf_ev=0,
        )
        results_corrected = cross_validate(
            revenue=10_000_000,
            ebitda=ebitda,
            net_income=0,
            book_value=0,
            net_debt=1_000_000,
            shares=50_000_000,
            sotp_ev=total_sotp,
            dcf_ev=0,
            sotp_ev_ebitda_only=ev_only,
        )
        sotp_inflated = next(
            r for r in results_inflated if r.method == "SOTP (EV/EBITDA)"
        )
        sotp_corrected = next(
            r for r in results_corrected if r.method == "SOTP (EV/EBITDA)"
        )

        # Implied multiple: inflated uses 7M/1M=7x, corrected uses 5M/1M=5x
        assert sotp_inflated.multiple > sotp_corrected.multiple
        # Enterprise value (for equity bridge) must remain the full total in both cases
        assert (
            sotp_inflated.enterprise_value
            == sotp_corrected.enterprise_value
            == total_sotp
        )


# ═══════════════════════════════════════════════════════════
# Peer Analysis Tests
# ═══════════════════════════════════════════════════════════


class TestPeerAnalysis:
    def test_peer_stats_by_segment(self):
        from schemas.models import PeerCompany

        peers = [
            PeerCompany(name="A", segment_code="HI", ev_ebitda=8.0),
            PeerCompany(name="B", segment_code="HI", ev_ebitda=10.0),
            PeerCompany(name="C", segment_code="HI", ev_ebitda=9.0),
            PeerCompany(name="D", segment_code="SOL", ev_ebitda=5.0),
            PeerCompany(name="E", segment_code="SOL", ev_ebitda=4.5),
        ]
        stats = calc_peer_stats(
            peers, {"HI": 8.0, "SOL": 5.0}, {"HI": "Hi-Tech", "SOL": "솔루션"}
        )
        assert len(stats) == 2
        hi = next(s for s in stats if s.segment_code == "HI")
        assert hi.count == 3
        assert hi.ev_ebitda_median == 9.0

    def test_peer_stats_empty(self):
        stats = calc_peer_stats([], {})
        assert stats == []


# ═══════════════════════════════════════════════════════════
# Monte Carlo Tests
# ═══════════════════════════════════════════════════════════


class TestMonteCarlo:
    def test_basic_mc(self):
        mc_input = MCInput(
            multiple_params={"HI": (8.0, 1.2), "ALC": (13.0, 2.0)},
            wacc_mean=8.5,
            wacc_std=1.0,
            dlom_mean=20.0,
            dlom_std=5.0,
            tg_mean=2.5,
            tg_std=0.5,
            n_sims=1000,
            seed=42,
        )
        result = run_monte_carlo(
            mc_input,
            seg_ebitdas={"HI": 109_590, "ALC": 256_427},
            net_debt=2_295_568,
            eco_frontier=94_644,
            cps_principal=600_000,
            cps_years=4,
            rcps_repay=490_000,
            buyback=200_000,
            shares=54_278_993,
            irr=5.0,
        )
        assert result.n_sims == 1000
        assert result.mean > 0
        assert result.p5 < result.median < result.p95

    def test_mc_reproducibility(self):
        mc_input = MCInput(
            multiple_params={"A": (10.0, 1.5)},
            wacc_mean=8.0,
            wacc_std=1.0,
            dlom_mean=0.0,
            dlom_std=0.0,
            tg_mean=2.5,
            tg_std=0.5,
            n_sims=500,
            seed=123,
        )
        r1 = run_monte_carlo(
            mc_input, {"A": 100_000}, 50_000, 0, 0, 0, 0, 0, 10_000_000
        )
        r2 = run_monte_carlo(
            mc_input, {"A": 100_000}, 50_000, 0, 0, 0, 0, 0, 10_000_000
        )
        assert r1.mean == r2.mean


# ═══════════════════════════════════════════════════════════
# Full Pipeline Tests
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# NAV Tests
# ═══════════════════════════════════════════════════════════


class TestNAV:
    def test_basic_nav(self):
        r = calc_nav(
            total_assets=10_000,
            total_liabilities=4_000,
            shares=1_000_000,
            revaluation=0,
            unit_multiplier=1_000_000,
        )
        # NAV = 10,000 - 4,000 = 6,000 (millions KRW)
        assert r.nav == 6_000
        # per share = 6,000 * 1,000,000 / 1,000,000 = 6,000 KRW
        assert r.per_share == 6_000

    def test_nav_with_revaluation(self):
        r = calc_nav(
            total_assets=10_000,
            total_liabilities=4_000,
            shares=1_000_000,
            revaluation=2_000,
            unit_multiplier=1_000_000,
        )
        # adjusted assets = 10,000 + 2,000 = 12,000
        assert r.adjusted_assets == 12_000
        assert r.nav == 8_000
        assert r.per_share == 8_000

    def test_nav_negative(self):
        """Liabilities > assets: NAV < 0, per_share = 0"""
        r = calc_nav(
            total_assets=3_000,
            total_liabilities=5_000,
            shares=1_000_000,
            unit_multiplier=1_000_000,
        )
        assert r.nav == -2_000
        assert r.per_share == -2_000  # Negative NAV propagates


class TestFullPipeline:
    def test_sk_ecoplant_profile(self):
        """End-to-end: YAML load -> SOTP valuation -> valid result"""
        from valuation_runner import load_profile, run_valuation

        profile_path = str(
            Path(__file__).parent.parent / "profiles" / "sk_ecoplant.yaml"
        )
        vi = load_profile(profile_path)
        result = run_valuation(vi)

        # Structural verification (instead of fixed values)
        assert result.primary_method == "sotp"
        assert (
            result.wacc.wacc == 9.02
        )  # 8.50 + size_premium 1.5% → Ke 18.11% → WACC 9.02%
        assert (
            4_800_000 < result.total_ev < 6_400_000
        )  # SOTP EV (distress discount may reduce)
        assert result.weighted_value > 0
        assert len(result.cross_validations) >= 2
        assert result.dcf is not None
        assert result.dcf.ev_dcf > 0

    def test_sk_ecoplant_mc(self):
        """SK Ecoplant Monte Carlo integration"""
        from valuation_runner import load_profile, run_valuation

        profile_path = str(
            Path(__file__).parent.parent / "profiles" / "sk_ecoplant.yaml"
        )
        vi = load_profile(profile_path)
        result = run_valuation(vi)

        assert result.monte_carlo is not None
        mc = result.monte_carlo
        assert mc.n_sims == 10_000
        assert mc.p5 < mc.median < mc.p95

    def test_ddm_kb_financial(self):
        """KB Financial Group DDM integration test"""
        from valuation_runner import load_profile, run_valuation

        profile_path = str(
            Path(__file__).parent.parent / "profiles" / "kb_financial.yaml"
        )
        vi = load_profile(profile_path)
        result = run_valuation(vi)

        assert result.primary_method == "ddm"
        assert result.ddm is not None
        assert result.ddm.equity_per_share > 0
        assert result.ddm.dps == 3060.0
        assert result.ddm.growth == 4.0
        # DDM + per-scenario growth rates -> positive weighted_value
        assert result.weighted_value > 0
        # Per-scenario DDM values should differ (ddm_growth applied)
        base_ps = result.scenarios["B"].post_dlom
        bull_ps = result.scenarios["A"].post_dlom
        bear_ps = result.scenarios["C"].post_dlom
        assert bull_ps > base_ps > bear_ps
        # Financial stocks exclude DCF; only P/E and P/BV cross-validation
        assert result.dcf is None
        assert len(result.cross_validations) >= 2

    def test_ddm_no_net_debt_double_deduction(self):
        """F-P1-1: DDM equity bridge must not double-deduct net_debt.

        DDM yields equity_per_share directly; net_debt should NOT be subtracted
        again in calc_scenario. We verify by injecting non-zero net_debt and
        checking that weighted_value stays close to DDM equity_per_share.
        """
        from valuation_runner import load_profile, run_valuation

        profile_path = str(
            Path(__file__).parent.parent / "profiles" / "kb_financial.yaml"
        )
        vi = load_profile(profile_path)
        # Inject non-zero net_debt to exercise the bridge
        vi_with_debt = vi.model_copy(update={"net_debt": 5_000_000})
        result = run_valuation(vi_with_debt)

        assert result.primary_method == "ddm"
        # With correct bridge: scenario equity ≈ DDM equity - CPS/RCPS (both 0 here)
        # With double-deduction bug: equity would be ~5T lower (nonsensical)
        base_sc = result.scenarios["B"]
        ddm_eps = result.ddm.equity_per_share
        # Tolerance: within 20% of DDM equity_per_share (scenarios have DLOM, market_sentiment)
        assert base_sc.pre_dlom > ddm_eps * 0.5, (
            f"DDM net_debt double-deduction: pre_dlom={base_sc.pre_dlom} vs ddm_eps={ddm_eps}"
        )


# ═══════════════════════════════════════════════════════════
# Validation Tests (Input Validation)
# ═══════════════════════════════════════════════════════════


class TestValidation:
    """Pydantic validation and engine input error tests."""

    def test_shares_total_must_be_positive(self):
        import pytest
        from schemas.models import CompanyProfile

        with pytest.raises(Exception):
            CompanyProfile(name="Test", shares_total=0, shares_ordinary=0)

    def test_shares_ordinary_exceeds_total(self):
        import pytest
        from schemas.models import CompanyProfile

        with pytest.raises(Exception):
            CompanyProfile(name="Test", shares_total=100, shares_ordinary=200)

    def test_scenario_prob_out_of_range(self):
        import pytest

        with pytest.raises(Exception):
            ScenarioParams(code="X", name="X", prob=150, ipo="N/A", shares=100)

    def test_dlom_out_of_range(self):
        import pytest

        with pytest.raises(Exception):
            ScenarioParams(code="X", name="X", prob=50, ipo="N/A", shares=100, dlom=-10)

    def test_wacc_beta_negative(self):
        import pytest

        with pytest.raises(Exception):
            WACCParams(rf=3.5, erp=7.0, bu=-0.5, de=100, tax=22, kd_pre=5, eq_w=50)

    def test_wacc_eq_w_zero(self):
        import pytest

        with pytest.raises(Exception):
            WACCParams(rf=3.5, erp=7.0, bu=0.7, de=100, tax=22, kd_pre=5, eq_w=0)

    def test_dcf_terminal_growth_out_of_range(self):
        """terminal_growth > 5% rejected at schema level."""
        import pytest

        with pytest.raises(Exception):
            DCFParams(
                ebitda_growth_rates=[0.05, 0.04, 0.03],
                terminal_growth=10.0,  # > 5% limit
            )

    def test_dcf_wacc_lte_terminal_growth(self):
        """WACC <= terminal_growth raises DCF ValueError."""
        import pytest

        params = DCFParams(
            ebitda_growth_rates=[0.05, 0.04, 0.03],
            terminal_growth=4.5,  # Valid range but TG > WACC
        )
        with pytest.raises(ValueError, match="WACC.*영구성장률"):
            calc_dcf(
                ebitda_base=100_000,
                da_base=20_000,
                revenue_base=500_000,
                wacc_pct=3.0,  # WACC < TG
                params=params,
                base_year=2025,
            )

    def test_scenario_prob_sum_not_100(self):
        """Scenario probability sum != 100% raises ValuationInput error."""
        import pytest
        from schemas.models import ValuationInput, CompanyProfile

        with pytest.raises(Exception, match="확률 합계"):
            ValuationInput(
                company=CompanyProfile(
                    name="Test", shares_total=100, shares_ordinary=100
                ),
                segments={"A": {"name": "A", "multiple": 5.0}},
                segment_data={2025: {"A": {"revenue": 100, "op": 10, "assets": 50}}},
                consolidated={
                    2025: {
                        "revenue": 100,
                        "op": 10,
                        "net_income": 8,
                        "assets": 200,
                        "liabilities": 100,
                        "equity": 100,
                        "dep": 5,
                        "amort": 2,
                        "de_ratio": 100.0,
                    }
                },
                wacc_params=WACCParams(
                    rf=3.5, erp=7.0, bu=0.7, de=100, tax=22, kd_pre=5, eq_w=50
                ),
                multiples={"A": 5.0},
                scenarios={
                    "Base": ScenarioParams(
                        code="Base", name="Base", prob=60, ipo="N/A", shares=100
                    ),
                    "Bull": ScenarioParams(
                        code="Bull", name="Bull", prob=60, ipo="N/A", shares=100
                    ),
                },
                dcf_params=DCFParams(ebitda_growth_rates=[0.05]),
                base_year=2025,
            )

    def test_base_year_not_in_consolidated(self):
        """base_year not in consolidated raises error."""
        import pytest
        from schemas.models import ValuationInput, CompanyProfile

        with pytest.raises(Exception, match="base_year"):
            ValuationInput(
                company=CompanyProfile(
                    name="Test", shares_total=100, shares_ordinary=100
                ),
                segments={"A": {"name": "A", "multiple": 5.0}},
                segment_data={2024: {"A": {"revenue": 100, "op": 10, "assets": 50}}},
                consolidated={
                    2024: {
                        "revenue": 100,
                        "op": 10,
                        "net_income": 8,
                        "assets": 200,
                        "liabilities": 100,
                        "equity": 100,
                        "dep": 5,
                        "amort": 2,
                        "de_ratio": 100.0,
                    }
                },
                wacc_params=WACCParams(
                    rf=3.5, erp=7.0, bu=0.7, de=100, tax=22, kd_pre=5, eq_w=50
                ),
                multiples={"A": 5.0},
                scenarios={
                    "Base": ScenarioParams(
                        code="Base", name="Base", prob=100, ipo="N/A", shares=100
                    ),
                },
                dcf_params=DCFParams(ebitda_growth_rates=[0.05]),
                base_year=2025,  # 2025 not in consolidated
            )

    def test_negative_multiple_rejected(self):
        """Negative multiple raises ValuationInput error."""
        import pytest
        from schemas.models import ValuationInput, CompanyProfile

        with pytest.raises(Exception, match="멀티플.*음수"):
            ValuationInput(
                company=CompanyProfile(
                    name="Test", shares_total=100, shares_ordinary=100
                ),
                segments={"A": {"name": "A", "multiple": -3.0}},
                segment_data={2025: {"A": {"revenue": 100, "op": 10, "assets": 50}}},
                consolidated={
                    2025: {
                        "revenue": 100,
                        "op": 10,
                        "net_income": 8,
                        "assets": 200,
                        "liabilities": 100,
                        "equity": 100,
                        "dep": 5,
                        "amort": 2,
                        "de_ratio": 100.0,
                    }
                },
                wacc_params=WACCParams(
                    rf=3.5, erp=7.0, bu=0.7, de=100, tax=22, kd_pre=5, eq_w=50
                ),
                multiples={"A": -3.0},
                scenarios={
                    "Base": ScenarioParams(
                        code="Base", name="Base", prob=100, ipo="N/A", shares=100
                    ),
                },
                dcf_params=DCFParams(ebitda_growth_rates=[0.05]),
                base_year=2025,
            )


# ═══════════════════════════════════════════════════════════
# Monte Carlo Enhanced Tests
# ═══════════════════════════════════════════════════════════


class TestMonteCarloEnhanced:
    """Monte Carlo tg/wacc sampling integration tests."""

    def test_tg_variation_affects_distribution(self):
        """When tg_std > 0, providing DCF TV info should change the distribution width."""
        mc_params = MCInput(
            multiple_params={"A": (8.0, 1.2)},
            wacc_mean=9.0,
            wacc_std=1.0,
            dlom_mean=0,
            dlom_std=0,
            tg_mean=2.5,
            tg_std=0.5,
            n_sims=5_000,
            seed=42,
        )
        seg_ebitdas = {"A": 500_000}

        # Without DCF info
        r1 = run_monte_carlo(
            mc_params,
            seg_ebitdas,
            net_debt=100_000,
            eco_frontier=0,
            cps_principal=0,
            cps_years=0,
            rcps_repay=0,
            buyback=0,
            shares=50_000_000,
            unit_multiplier=1_000_000,
        )

        # With DCF info: WACC/TG variation reflected in EV
        r2 = run_monte_carlo(
            mc_params,
            seg_ebitdas,
            net_debt=100_000,
            eco_frontier=0,
            cps_principal=0,
            cps_years=0,
            rcps_repay=0,
            buyback=0,
            shares=50_000_000,
            unit_multiplier=1_000_000,
            wacc_for_dcf=9.0,
            dcf_last_fcff=300_000,
            dcf_pv_fcff_sum=1_200_000,
            dcf_n_periods=5,
        )

        # Distribution should differ when DCF TV variation is reflected
        assert r2.std != r1.std or r2.mean != r1.mean

    def test_mc_basic_stats_valid(self):
        """MC basic statistics must satisfy consistency constraints."""
        mc_params = MCInput(
            multiple_params={"A": (10.0, 2.0)},
            wacc_mean=9.0,
            wacc_std=1.0,
            dlom_mean=10.0,
            dlom_std=3.0,
            tg_mean=2.0,
            tg_std=0.3,
            n_sims=10_000,
            seed=123,
        )
        r = run_monte_carlo(
            mc_params,
            {"A": 1_000_000},
            net_debt=500_000,
            eco_frontier=0,
            cps_principal=0,
            cps_years=0,
            rcps_repay=0,
            buyback=0,
            shares=100_000_000,
            unit_multiplier=1_000_000,
        )
        assert r.min_val <= r.p5 <= r.p25 <= r.median <= r.p75 <= r.p95 <= r.max_val
        assert r.mean > 0
        assert r.std > 0


class TestMonteCarloEvRevenue:
    """Monte Carlo ev_revenue segment support tests."""

    def test_mc_ev_revenue_only(self):
        """Single ev_revenue segment: mean proportional to revenue * mean_multiple."""
        mc_params = MCInput(
            multiple_params={"FSD": (15.0, 0.01)},  # near-zero std for predictable mean
            wacc_mean=9.0,
            wacc_std=0.01,
            dlom_mean=0,
            dlom_std=0,
            tg_mean=2.5,
            tg_std=0.01,
            n_sims=5_000,
            seed=42,
            segment_methods={"FSD": "ev_revenue"},
        )
        # FSD: EBITDA=0 (pre-profit), Revenue=5000
        r = run_monte_carlo(
            mc_params,
            {"FSD": 0},
            net_debt=10_000,
            eco_frontier=0,
            cps_principal=0,
            cps_years=0,
            rcps_repay=0,
            buyback=0,
            shares=50_000_000,
            unit_multiplier=1_000_000,
            seg_revenues={"FSD": 5_000},
        )
        # EV ≈ 5000 * 15 = 75000 → per-share ≈ (75000-10000)*1M/50M = 1300
        assert r.mean > 0
        assert r.std < r.mean * 0.1  # very tight distribution (near-zero std)

    def test_mc_mixed_ebitda_revenue(self):
        """Mixed segments: ev_ebitda + ev_revenue both contribute to EV."""
        mc_params = MCInput(
            multiple_params={"AUTO": (8.0, 0.01), "FSD": (15.0, 0.01)},
            wacc_mean=9.0,
            wacc_std=0.01,
            dlom_mean=0,
            dlom_std=0,
            tg_mean=2.5,
            tg_std=0.01,
            n_sims=5_000,
            seed=42,
            segment_methods={"AUTO": "ev_ebitda", "FSD": "ev_revenue"},
        )
        r_mixed = run_monte_carlo(
            mc_params,
            {"AUTO": 10_000, "FSD": 0},
            net_debt=0,
            eco_frontier=0,
            cps_principal=0,
            cps_years=0,
            rcps_repay=0,
            buyback=0,
            shares=50_000_000,
            unit_multiplier=1_000_000,
            seg_revenues={"AUTO": 0, "FSD": 5_000},
        )
        # EV ≈ AUTO(10000*8) + FSD(5000*15) = 80000 + 75000 = 155000
        # per-share ≈ 155000*1M/50M = 3100
        expected_ps = 155_000 * 1_000_000 / 50_000_000
        assert abs(r_mixed.mean - expected_ps) / expected_ps < 0.05

    def test_mc_ev_revenue_zero_revenue(self):
        """ev_revenue segment with revenue=0 contributes 0 EV (no crash)."""
        mc_params = MCInput(
            multiple_params={"ROBO": (8.0, 1.0)},
            wacc_mean=9.0,
            wacc_std=1.0,
            dlom_mean=0,
            dlom_std=0,
            tg_mean=2.5,
            tg_std=0.5,
            n_sims=1_000,
            seed=42,
            segment_methods={"ROBO": "ev_revenue"},
        )
        r = run_monte_carlo(
            mc_params,
            {"ROBO": 0},
            net_debt=0,
            eco_frontier=0,
            cps_principal=0,
            cps_years=0,
            rcps_repay=0,
            buyback=0,
            shares=50_000_000,
            unit_multiplier=1_000_000,
            seg_revenues={"ROBO": 0},
        )
        # All EV = 0 → per-share = 0
        assert r.mean == 0

    def test_mc_backward_compat(self):
        """MCInput without segment_methods preserves existing behavior."""
        mc_old = MCInput(
            multiple_params={"A": (8.0, 1.2)},
            wacc_mean=9.0,
            wacc_std=1.0,
            dlom_mean=0,
            dlom_std=0,
            tg_mean=2.5,
            tg_std=0.5,
            n_sims=5_000,
            seed=42,
        )
        mc_new = MCInput(
            multiple_params={"A": (8.0, 1.2)},
            wacc_mean=9.0,
            wacc_std=1.0,
            dlom_mean=0,
            dlom_std=0,
            tg_mean=2.5,
            tg_std=0.5,
            n_sims=5_000,
            seed=42,
            segment_methods={},
        )
        kwargs = dict(
            net_debt=100_000,
            eco_frontier=0,
            cps_principal=0,
            cps_years=0,
            rcps_repay=0,
            buyback=0,
            shares=50_000_000,
            unit_multiplier=1_000_000,
        )
        r1 = run_monte_carlo(mc_old, {"A": 500_000}, **kwargs)
        r2 = run_monte_carlo(mc_new, {"A": 500_000}, **kwargs)
        assert r1.mean == r2.mean
        assert r1.std == r2.std


# ═══════════════════════════════════════════════════════════
# Profile Loading Tests
# ═══════════════════════════════════════════════════════════


class TestLoadProfile:
    """YAML profile loading tests."""

    def test_load_sk_ecoplant(self):
        from valuation_runner import load_profile

        profile_path = str(
            Path(__file__).parent.parent / "profiles" / "sk_ecoplant.yaml"
        )
        vi = load_profile(profile_path)

        assert vi.company.name == "SK에코플랜트"
        assert len(vi.segments) == 5
        assert vi.base_year in vi.consolidated
        assert len(vi.scenarios) > 0
        total_prob = sum(sc.prob for sc in vi.scenarios.values())
        assert abs(total_prob - 100.0) < 0.1

    def test_load_kb_financial_ddm(self):
        from valuation_runner import load_profile

        profile_path = str(
            Path(__file__).parent.parent / "profiles" / "kb_financial.yaml"
        )
        vi = load_profile(profile_path)

        assert vi.company.name == "KB금융지주"
        assert vi.valuation_method == "ddm"
        assert vi.ddm_params is not None
        assert vi.ddm_params.dps == 3060.0
        assert vi.ddm_params.dividend_growth == 4.0

    def test_load_msft(self):
        from valuation_runner import load_profile

        profile_path = str(Path(__file__).parent.parent / "profiles" / "msft.yaml")
        vi = load_profile(profile_path)

        assert vi.company.market == "US"
        assert vi.company.currency == "USD"
        assert vi.company.shares_total > 0


# ═══════════════════════════════════════════════════════════
# RIM Tests
# ═══════════════════════════════════════════════════════════


class TestRIM:
    def test_basic_rim(self):
        """BV=100, ROE=12%, Ke=10%: positive residual income, per-share > BV"""
        r = calc_rim(
            book_value=100_000,
            roe_forecasts=[12.0, 11.5, 11.0, 10.5, 10.0],
            ke=10.0,
            terminal_growth=0.0,
            shares=1_000_000,
            unit_multiplier=1_000_000,
        )
        assert r.equity_value > 100_000  # BV + positive RI
        assert r.per_share > 0
        assert len(r.projections) == 5
        # Year 1 RI = BV * (ROE - Ke) = 100,000 * 0.02 = 2,000
        assert r.projections[0].ri == 2_000

    def test_rim_roe_equals_ke(self):
        """ROE = Ke: RI = 0, per-share value equals BV"""
        r = calc_rim(
            book_value=50_000,
            roe_forecasts=[10.0, 10.0, 10.0],
            ke=10.0,
            shares=1_000_000,
            unit_multiplier=1_000_000,
        )
        assert r.equity_value == 50_000  # BV only (RI=0)

    def test_rim_roe_below_ke(self):
        """ROE < Ke: negative residual income, per-share < BV"""
        r = calc_rim(
            book_value=50_000,
            roe_forecasts=[8.0, 8.0, 8.0],
            ke=10.0,
            shares=1_000_000,
            unit_multiplier=1_000_000,
        )
        assert r.equity_value < 50_000

    def test_rim_ke_lte_growth_raises(self):
        """ke <= terminal_growth raises ValueError"""
        import pytest

        with pytest.raises(ValueError):
            calc_rim(
                book_value=100_000,
                roe_forecasts=[12.0],
                ke=5.0,
                terminal_growth=5.0,
                shares=1,
            )

    def test_rim_with_payout(self):
        """Payout ratio > 0 slows BV growth"""
        r_no_payout = calc_rim(
            book_value=100_000,
            roe_forecasts=[12.0, 12.0, 12.0],
            ke=10.0,
            shares=1_000_000,
            unit_multiplier=1_000_000,
            payout_ratio=0.0,
        )
        r_with_payout = calc_rim(
            book_value=100_000,
            roe_forecasts=[12.0, 12.0, 12.0],
            ke=10.0,
            shares=1_000_000,
            unit_multiplier=1_000_000,
            payout_ratio=50.0,
        )
        # Dividends reduce BV reinvestment -> lower future RI -> lower equity_value
        assert r_with_payout.equity_value < r_no_payout.equity_value


# ═══════════════════════════════════════════════════════════
# DDM Total Payout Tests
# ═══════════════════════════════════════════════════════════


class TestDDMTotalPayout:
    def test_ddm_with_buyback(self):
        """Including buyback increases per-share value"""
        r_div_only = calc_ddm(dps=1000, growth=3.0, ke=10.0)
        r_total = calc_ddm(dps=1000, growth=3.0, ke=10.0, buyback_per_share=500)
        assert r_total.equity_per_share > r_div_only.equity_per_share
        assert r_total.total_payout == 1500
        assert r_total.buyback_per_share == 500

    def test_ddm_buyback_zero_backward_compat(self):
        """buyback=0: identical to standard DDM"""
        r = calc_ddm(dps=1000, growth=3.0, ke=10.0, buyback_per_share=0)
        assert r.equity_per_share == 14_714
        assert r.total_payout == 1000


# ═══════════════════════════════════════════════════════════
# P/S, P/FFO Multiples Tests
# ═══════════════════════════════════════════════════════════


class TestNewMultiples:
    def test_ps_basic(self):
        r = calc_ps(
            revenue=500_000, multiple=3.0, shares=1_000_000, unit_multiplier=1_000_000
        )
        assert r.method == "P/S"
        assert r.equity_value == 1_500_000
        assert r.per_share > 0

    def test_ps_zero_revenue(self):
        r = calc_ps(revenue=0, multiple=3.0, shares=1_000_000)
        assert r.equity_value == 0

    def test_pffo_basic(self):
        r = calc_pffo(
            ffo=200_000, multiple=18.0, shares=1_000_000, unit_multiplier=1_000_000
        )
        assert r.method == "P/FFO"
        assert r.equity_value == 3_600_000
        assert r.per_share > 0

    def test_pffo_zero_ffo(self):
        r = calc_pffo(ffo=0, multiple=18.0, shares=1_000_000)
        assert r.equity_value == 0

    def test_cross_validate_includes_ps_pffo(self):
        """P/S and P/FFO included in cross-validation"""
        results = cross_validate(
            revenue=500_000,
            ebitda=100_000,
            net_income=50_000,
            book_value=300_000,
            net_debt=100_000,
            shares=1_000_000,
            sotp_ev=800_000,
            dcf_ev=750_000,
            ps_multiple=2.5,
            pffo_multiple=15.0,
            ffo=80_000,
            unit_multiplier=1_000_000,
        )
        methods = [r.method for r in results]
        assert "P/S" in methods
        assert "P/FFO" in methods


# ═══════════════════════════════════════════════════════════
# Method Selector — Financial DDM/RIM Auto-Selection Tests
# ═══════════════════════════════════════════════════════════


class TestMethodSelectorFinancial:
    def test_financial_default_ddm(self):
        """Financial stock, ROE/Ke not provided: defaults to DDM"""
        assert suggest_method(1, industry="은행") == "ddm"

    def test_financial_roe_spread_high_rim(self):
        """Financial stock, |ROE - Ke| > 2%p: recommends RIM"""
        assert suggest_method(1, industry="은행", roe=15.0, ke=10.0) == "rim"

    def test_financial_roe_spread_low_ddm(self):
        """Financial stock, |ROE - Ke| <= 2%p: stays DDM"""
        assert suggest_method(1, industry="은행", roe=11.0, ke=10.0) == "ddm"

    def test_financial_rim_params_only(self):
        """Only RIM params available: selects RIM"""
        assert suggest_method(1, industry="보험", has_rim_params=True) == "rim"

    def test_financial_ddm_params_only(self):
        """Only DDM params available: selects DDM"""
        assert suggest_method(1, industry="보험", has_ddm_params=True) == "ddm"

    def test_reit_nav(self):
        """REIT -> NAV"""
        assert suggest_method(1, industry="리츠") == "nav"
        assert suggest_method(1, industry="REIT") == "nav"
        assert suggest_method(1, industry="real estate") == "nav"

    def test_holding_nav(self):
        """Holding company -> NAV"""
        assert suggest_method(1, industry="지주") == "nav"


# ═══════════════════════════════════════════════════════════
# Pipeline Macro Data Tests
# ═══════════════════════════════════════════════════════════


class TestMacroData:
    def test_terminal_growth_defaults(self):
        from pipeline.macro_data import get_terminal_growth

        us_tg = get_terminal_growth("US")
        kr_tg = get_terminal_growth("KR")
        assert 1.5 <= us_tg <= 4.0  # reasonable range
        assert 1.0 <= kr_tg <= 3.0

    def test_effective_tax_rate(self):
        from pipeline.macro_data import calc_effective_tax_rate

        financials = {
            2024: {"op": 1000, "net_income": 780, "pre_tax_income": 1000},
            2023: {"op": 900, "net_income": 702, "pre_tax_income": 900},
        }
        rate = calc_effective_tax_rate(financials)
        assert rate is not None
        assert 20 <= rate <= 23  # around 22%

    def test_effective_tax_rate_no_data(self):
        from pipeline.macro_data import calc_effective_tax_rate

        rate = calc_effective_tax_rate({})
        assert rate is None


# ═══════════════════════════════════════════════════════════
# RIM Enhanced Tests
# ═══════════════════════════════════════════════════════════


class TestRIMEnhanced:
    def test_terminal_growth_increases_value(self):
        """Terminal growth > 0 increases equity_value"""
        r_zero_g = calc_rim(
            book_value=100_000,
            roe_forecasts=[12.0, 12.0, 12.0],
            ke=10.0,
            terminal_growth=0.0,
            shares=1_000_000,
            unit_multiplier=1_000_000,
        )
        r_pos_g = calc_rim(
            book_value=100_000,
            roe_forecasts=[12.0, 12.0, 12.0],
            ke=10.0,
            terminal_growth=2.0,
            shares=1_000_000,
            unit_multiplier=1_000_000,
        )
        assert r_pos_g.equity_value > r_zero_g.equity_value

    def test_bv_accumulation_clean_surplus(self):
        """Payout=0: BV grows by NI each period (clean surplus)"""
        r = calc_rim(
            book_value=100_000,
            roe_forecasts=[10.0, 10.0],
            ke=10.0,
            shares=1,
            unit_multiplier=1,
        )
        # BV₁ = 100,000 + NI₁(=10,000) = 110,000
        assert r.projections[1].bv == 110_000

    def test_bv_accumulation_with_payout(self):
        """Payout ratio 40%: only 60% of NI retained in BV"""
        r = calc_rim(
            book_value=100_000,
            roe_forecasts=[10.0, 10.0],
            ke=8.0,
            shares=1,
            unit_multiplier=1,
            payout_ratio=40.0,
        )
        # NI₁ = 100,000 × 10% = 10,000
        # Div₁ = 10,000 × 40% = 4,000
        # BV₁ = 100,000 + 10,000 - 4,000 = 106,000
        assert r.projections[1].bv == 106_000


# ═══════════════════════════════════════════════════════════
# NAV Enhanced Tests
# ═══════════════════════════════════════════════════════════


class TestNAVEnhanced:
    def test_large_revaluation(self):
        """Large revaluation adjustment proportionally increases per_share"""
        r1 = calc_nav(
            10_000, 4_000, 1_000_000, revaluation=0, unit_multiplier=1_000_000
        )
        r2 = calc_nav(
            10_000, 4_000, 1_000_000, revaluation=10_000, unit_multiplier=1_000_000
        )
        assert r2.per_share > r1.per_share
        assert r2.nav == 16_000  # 10,000 + 10,000 - 4,000

    def test_negative_revaluation(self):
        """Negative revaluation decreases NAV"""
        r = calc_nav(
            10_000, 4_000, 1_000_000, revaluation=-3_000, unit_multiplier=1_000_000
        )
        assert r.adjusted_assets == 7_000
        assert r.nav == 3_000


# ═══════════════════════════════════════════════════════════
# Monte Carlo Enhanced Edge Cases
# ═══════════════════════════════════════════════════════════


class TestMonteCarloEdgeCases:
    def test_negative_equity_clamped_to_zero(self):
        """claims > EV: negative per-share value propagated (not clipped to 0)"""
        mc = MCInput(
            multiple_params={"A": (2.0, 0.1)},  # low multiple
            wacc_mean=8.0,
            wacc_std=0.5,
            dlom_mean=0,
            dlom_std=0,
            tg_mean=2.0,
            tg_std=0.3,
            n_sims=1000,
            seed=42,
        )
        r = run_monte_carlo(
            mc,
            {"A": 10_000},
            net_debt=500_000,  # EV(~20,000) << claims(500,000)
            eco_frontier=0,
            cps_principal=0,
            cps_years=0,
            rcps_repay=0,
            buyback=0,
            shares=1_000_000,
            unit_multiplier=1_000_000,
        )
        # Negative equity propagates — unbiased distribution (not clipped)
        assert r.min_val < 0
        assert r.pct_negative == 100.0
        assert r.histogram_bins == []  # histogram empty when all negative

    def test_dlom_clipped_to_50(self):
        """DLOM mean 45%, std 10%: 50% upper-bound clipping"""
        mc = MCInput(
            multiple_params={"A": (10.0, 0.5)},
            wacc_mean=8.0,
            wacc_std=0.5,
            dlom_mean=45.0,
            dlom_std=10.0,  # many samples exceed 50%
            tg_mean=2.0,
            tg_std=0.3,
            n_sims=5000,
            seed=42,
        )
        r = run_monte_carlo(
            mc,
            {"A": 500_000},
            net_debt=100_000,
            eco_frontier=0,
            cps_principal=0,
            cps_years=0,
            rcps_repay=0,
            buyback=0,
            shares=50_000_000,
            unit_multiplier=1_000_000,
        )
        # DLOM capped at 50%, so per-share value > 0
        assert r.mean > 0
        assert r.p5 >= 0

    def test_histogram_generated(self):
        """Histogram bins/counts generated after simulation"""
        mc = MCInput(
            multiple_params={"A": (10.0, 1.5)},
            wacc_mean=9.0,
            wacc_std=1.0,
            dlom_mean=10.0,
            dlom_std=3.0,
            tg_mean=2.0,
            tg_std=0.5,
            n_sims=2000,
            seed=42,
        )
        r = run_monte_carlo(
            mc,
            {"A": 500_000},
            net_debt=100_000,
            eco_frontier=0,
            cps_principal=0,
            cps_years=0,
            rcps_repay=0,
            buyback=0,
            shares=50_000_000,
            unit_multiplier=1_000_000,
        )
        assert len(r.histogram_bins) > 0
        assert len(r.histogram_counts) == len(r.histogram_bins)
        assert sum(r.histogram_counts) > 0


# ═══════════════════════════════════════════════════════════
# Sensitivity — DDM/RIM/NAV/Multiple Range Tests
# ═══════════════════════════════════════════════════════════


class TestSensitivityExtended:
    def test_ddm_grid_size(self):
        rows = sensitivity_ddm(dps=1000, ke_base=10.0, g_base=3.0)
        assert len(rows) == 7 * 7  # default 7x7 grid

    def test_ddm_invalid_combinations_zero(self):
        """Ke <= g combinations yield value=0"""
        rows = sensitivity_ddm(
            dps=1000,
            ke_base=5.0,
            g_base=4.5,
            ke_range=[3.0, 4.0, 5.0],
            g_range=[3.0, 4.0, 5.0],
        )
        # ke=3%, g=5% → invalid → 0
        invalid = [r for r in rows if r.row_val <= r.col_val]
        assert all(r.value == 0 for r in invalid)

    def test_rim_grid_size(self):
        rows = sensitivity_rim(
            book_value=100_000,
            roe_forecasts=[12.0, 11.0],
            ke_base=10.0,
            shares=1_000_000,
        )
        assert len(rows) == 7 * 7

    def test_rim_higher_ke_lower_value(self):
        """Higher Ke should yield lower per-share value"""
        rows = sensitivity_rim(
            book_value=100_000,
            roe_forecasts=[12.0, 11.0, 10.5],
            ke_base=10.0,
            shares=1_000_000,
            ke_range=[8.0, 10.0, 12.0],
            tg_range=[0.0],
        )
        vals = [r.value for r in rows]
        assert vals[0] > vals[1] > vals[2]

    def test_nav_grid_size(self):
        rows = sensitivity_nav(10_000, 4_000, 1_000_000, base_revaluation=1_000)
        assert len(rows) == 7 * 5  # default 7x5

    def test_nav_discount_reduces_value(self):
        """Higher discount rate reduces per_share"""
        rows = sensitivity_nav(
            10_000,
            4_000,
            1_000_000,
            reval_range=[0],
            discount_range=[0, 20, 40],
        )
        vals = [r.value for r in rows]
        assert vals[0] > vals[1] > vals[2]

    def test_multiple_range_grid_size(self):
        rows = sensitivity_multiple_range(
            metric_value=500_000,
            net_debt=100_000,
            shares=50_000_000,
            base_multiple=10.0,
        )
        assert len(rows) == 9 * 5  # default 9x5

    def test_multiple_range_higher_mult_higher_value(self):
        """Higher multiple yields higher per-share value"""
        rows = sensitivity_multiple_range(
            metric_value=500_000,
            net_debt=100_000,
            shares=50_000_000,
            base_multiple=10.0,
            mult_range=[8.0, 10.0, 12.0],
            discount_range=[0],
        )
        vals = [r.value for r in rows]
        assert vals[0] < vals[1] < vals[2]

    def test_multiple_range_negative_equity_propagated(self):
        """Negative equity must propagate as negative per-share value, not zero."""
        rows = sensitivity_multiple_range(
            metric_value=100_000,
            net_debt=900_000,  # EV << net_debt → equity < 0
            shares=50_000_000,
            base_multiple=5.0,
            mult_range=[5.0],
            discount_range=[0],
        )
        assert rows[0].value < 0


# ═══════════════════════════════════════════════════════════
# Growth — Linear Fade & CAGR Tests
# ═══════════════════════════════════════════════════════════


class TestLinearFade:
    def test_basic_5y(self):
        result = linear_fade(0.12, 0.04, 5)
        assert result == [0.12, 0.10, 0.08, 0.06, 0.04]

    def test_no_fade(self):
        """start == end yields repeated identical values"""
        result = linear_fade(0.05, 0.05, 3)
        assert result == [0.05, 0.05, 0.05]

    def test_single_year(self):
        assert linear_fade(0.10, 0.04, 1) == [0.10]

    def test_invalid_n(self):
        import pytest

        with pytest.raises(ValueError):
            linear_fade(0.10, 0.04, 0)


class TestCalcEbitdaGrowth:
    _CONS = {
        2023: {"op": 100, "dep": 20, "amort": 5},  # EBITDA=125
        2024: {"op": 130, "dep": 22, "amort": 5},  # EBITDA=157
        2025: {"op": 160, "dep": 25, "amort": 5},  # EBITDA=190
    }

    def test_yoy_growth(self):
        """3-year CAGR (2023->2025): (190/125)^(1/2) - 1 ≈ 0.2329"""
        g = calc_ebitda_growth(self._CONS)
        assert g is not None
        # 3-yr CAGR preferred over 1-yr YoY for smoothing
        assert 0.23 < g < 0.24

    def test_insufficient_data(self):
        assert calc_ebitda_growth({2025: {"op": 100, "dep": 10, "amort": 5}}) is None

    def test_negative_ebitda(self):
        """Negative prior-year EBITDA returns None"""
        cons = {
            2024: {"op": -50, "dep": 10, "amort": 5},
            2025: {"op": 120, "dep": 10, "amort": 5},
        }
        assert calc_ebitda_growth(cons) is None


class TestGenerateGrowthRates:
    def test_kr_market(self):
        cons = {
            2023: {"op": 100, "dep": 20, "amort": 5},
            2024: {"op": 150, "dep": 22, "amort": 5},
            2025: {"op": 200, "dep": 25, "amort": 5},
        }
        rates = generate_growth_rates(cons, market="KR")
        assert len(rates) == 5
        assert rates[0] > rates[-1]  # declining trend
        assert rates[-1] == 0.03  # KR convergence rate

    def test_fallback_when_no_data(self):
        rates = generate_growth_rates({}, market="US")
        assert len(rates) == 5
        assert rates[0] == 0.08  # fallback (default base-rate)
        assert rates[-1] == 0.04  # US convergence rate

    def test_clamping_high_growth(self):
        """No industry specified: YoY fallback clamped at 30%"""
        cons = {
            2023: {"op": 50, "dep": 10, "amort": 5},
            2024: {"op": 150, "dep": 10, "amort": 5},
            2025: {"op": 300, "dep": 10, "amort": 5},
        }
        rates = generate_growth_rates(cons, market="KR")
        assert rates[0] <= 0.30

    def test_growth_industry(self):
        """Growth/tech industry: Y1=10%"""
        rates = generate_growth_rates({}, market="KR", industry="반도체")
        assert rates[0] == 0.10
        assert rates[-1] == 0.03

    def test_mature_industry(self):
        """Mature/stable industry: Y1=5%"""
        rates = generate_growth_rates({}, market="KR", industry="화학")
        assert rates[0] == 0.05
        assert rates[-1] == 0.03

    def test_default_industry(self):
        """Unclassified industry: Y1=8%"""
        rates = generate_growth_rates({}, market="US", industry="기타")
        assert rates[0] == 0.08
        assert rates[-1] == 0.04

    def test_industry_overrides_yoy(self):
        """When industry is provided, ignore YoY and use base-rate"""
        cons = {
            2024: {"op": 100, "dep": 10, "amort": 5},
            2025: {"op": 200, "dep": 10, "amort": 5},  # YoY ~83%
        }
        rates = generate_growth_rates(cons, market="KR", industry="semiconductor")
        assert rates[0] == 0.10  # industry base-rate, not YoY 83%

    def test_no_industry_uses_yoy(self):
        """No industry: falls back to YoY-based behavior (backward compat)"""
        cons = {
            2024: {"op": 100, "dep": 10, "amort": 5},
            2025: {"op": 120, "dep": 12, "amort": 5},  # EBITDA 137/115 ≈ 19.1%
        }
        rates = generate_growth_rates(cons, market="KR")
        assert rates[0] > 0.10  # YoY-based, so higher than default 8%


class TestClassifyIndustry:
    def test_growth_keywords(self):
        assert classify_industry("반도체") == "growth"
        assert classify_industry("Software") == "growth"
        assert classify_industry("바이오 제약") == "growth"

    def test_mature_keywords(self):
        assert classify_industry("화학") == "mature"
        assert classify_industry("유통") == "mature"
        assert classify_industry("Utility services") == "mature"

    def test_default(self):
        assert classify_industry("") == "default"
        assert classify_industry("기타 제조") == "default"

    def test_case_insensitive(self):
        assert classify_industry("SEMICONDUCTOR") == "growth"
        assert classify_industry("Chemical") == "mature"


# ── Multi-variable news drivers (resolve_drivers) ──


class TestResolveDrivers:
    """resolve_drivers: Y = sum(beta_i * X_i) multi-regression driver aggregation."""

    _BASE_SC = ScenarioParams(
        code="Base",
        name="Base Case",
        prob=50,
        ipo="N/A",
        shares=1_000_000,
    )

    _DRIVERS = [
        NewsDriver(
            id="rate_hike",
            name="금리인상 50bp",
            category="macro",
            effects={"wacc_adj": 0.5, "growth_adj_pct": -10},
            rationale="한은 기준금리 인상",
        ),
        NewsDriver(
            id="tariff_shock",
            name="관세충격",
            category="trade",
            effects={"growth_adj_pct": -15, "market_sentiment_pct": -5},
            rationale="미국 25% 관세 부과",
        ),
    ]

    def test_none_active_drivers_passthrough(self):
        """active_drivers=None: returns sc unchanged (backward compat)."""
        sc = self._BASE_SC
        result = resolve_drivers(sc, self._DRIVERS)
        assert result is sc  # same object

    def test_empty_active_drivers(self):
        """active_drivers={}: all drivers inactive (Base Case)."""
        sc = self._BASE_SC.model_copy(update={"active_drivers": {}})
        result = resolve_drivers(sc, self._DRIVERS)
        assert result.wacc_adj == 0.0
        assert result.growth_adj_pct == 0.0

    def test_single_driver_full_weight(self):
        """Single driver weight=1.0: full effect applied."""
        sc = self._BASE_SC.model_copy(
            update={
                "active_drivers": {"rate_hike": 1.0},
            }
        )
        result = resolve_drivers(sc, self._DRIVERS)
        assert result.wacc_adj == 0.5
        assert result.growth_adj_pct == -10

    def test_single_driver_half_weight(self):
        """weight=0.5: half the effect applied."""
        sc = self._BASE_SC.model_copy(
            update={
                "active_drivers": {"rate_hike": 0.5},
            }
        )
        result = resolve_drivers(sc, self._DRIVERS)
        assert result.wacc_adj == 0.25
        assert result.growth_adj_pct == -5.0

    def test_multi_driver_dampened(self):
        """Two drivers with correlation dampening: growth_adj_pct = (-10 + -15) * sqrt(2)/2 ≈ -17.68."""
        import math

        sc = self._BASE_SC.model_copy(
            update={
                "active_drivers": {"rate_hike": 1.0, "tariff_shock": 1.0},
            }
        )
        result = resolve_drivers(sc, self._DRIVERS)
        assert result.wacc_adj == 0.5  # rate_hike only (single driver, no dampening)
        # growth_adj_pct: raw=-25, dampened by sqrt(2)/2
        expected = round(-25 * math.sqrt(2) / 2, 4)
        assert result.growth_adj_pct == expected
        assert result.market_sentiment_pct == -5  # tariff_shock only (single driver)

    def test_multi_driver_no_dampen(self):
        """With dampen=False, pure additive: growth_adj_pct = -10 + -15 = -25."""
        sc = self._BASE_SC.model_copy(
            update={
                "active_drivers": {"rate_hike": 1.0, "tariff_shock": 1.0},
            }
        )
        result = resolve_drivers(sc, self._DRIVERS, dampen=False)
        assert result.growth_adj_pct == -25

    def test_unknown_driver_id_ignored(self):
        """Non-existent driver_id is ignored."""
        sc = self._BASE_SC.model_copy(
            update={
                "active_drivers": {"nonexistent": 1.0, "rate_hike": 1.0},
            }
        )
        result = resolve_drivers(sc, self._DRIVERS)
        assert result.wacc_adj == 0.5  # only rate_hike applied

    def test_driver_rationale_generated(self):
        """driver_rationale auto-generated when active_drivers used."""
        sc = self._BASE_SC.model_copy(
            update={
                "active_drivers": {"rate_hike": 1.0, "tariff_shock": 1.0},
            }
        )
        result = resolve_drivers(sc, self._DRIVERS)
        assert "금리인상 50bp" in result.driver_rationale["wacc_adj"]
        assert "관세충격" in result.driver_rationale["growth_adj_pct"]

    def test_no_drivers_list_with_active_drivers(self):
        """news_drivers=[] with active_drivers set: zero effect (no drivers)."""
        sc = self._BASE_SC.model_copy(
            update={
                "active_drivers": {"rate_hike": 1.0},
            }
        )
        result = resolve_drivers(sc, [])
        assert result.wacc_adj == 0.0
        assert result.growth_adj_pct == 0.0


# ═══════════════════════════════════════════════════════════
# Scenario Driver Round-Trip Tests
# ═══════════════════════════════════════════════════════════


class TestScenarioDriverRoundTrip:
    """Verify scenario drivers flow end-to-end: YAML → ScenarioParams → EV differentiation."""

    def test_sotp_segment_multiples_differentiate_ev(self):
        """SOTP: segment_multiples in YAML → different EV per scenario."""
        from valuation_runner import load_profile, run_valuation

        profile_path = str(Path(__file__).parent.parent / "profiles" / "msft.yaml")
        vi = load_profile(profile_path)
        result = run_valuation(vi)

        assert result.primary_method == "sotp"
        # Bull must have higher EV than Base, Bear must have lower
        bull = result.scenarios["Bull"]
        base = result.scenarios["Base"]
        bear = result.scenarios["Bear"]
        assert bull.pre_dlom > base.pre_dlom > bear.pre_dlom, (
            f"SOTP EV not differentiated: Bull={bull.pre_dlom}, Base={base.pre_dlom}, Bear={bear.pre_dlom}"
        )

    def test_dcf_growth_adj_differentiates_ev(self):
        """DCF: growth_adj_pct in YAML → different EV per scenario."""
        from valuation_runner import load_profile, run_valuation

        profile_path = str(Path(__file__).parent.parent / "profiles" / "tsla.yaml")
        vi = load_profile(profile_path)
        result = run_valuation(vi)

        assert result.primary_method in ("dcf_primary", "sotp")
        bull = result.scenarios["Bull"]
        base = result.scenarios["Base"]
        bear = result.scenarios["Bear"]
        assert bull.pre_dlom > base.pre_dlom > bear.pre_dlom, (
            f"DCF EV not differentiated: Bull={bull.pre_dlom}, Base={base.pre_dlom}, Bear={bear.pre_dlom}"
        )

    def test_ddm_growth_differentiates_ev(self):
        """DDM: ddm_growth in YAML → different EV per scenario."""
        from valuation_runner import load_profile, run_valuation

        profile_path = str(
            Path(__file__).parent.parent / "profiles" / "kb_financial.yaml"
        )
        vi = load_profile(profile_path)
        result = run_valuation(vi)

        assert result.primary_method == "ddm"
        bull = result.scenarios["A"]
        base = result.scenarios["B"]
        bear = result.scenarios["C"]
        assert bull.pre_dlom > base.pre_dlom > bear.pre_dlom, (
            f"DDM EV not differentiated: A={bull.pre_dlom}, B={base.pre_dlom}, C={bear.pre_dlom}"
        )

    def test_sotp_growth_adj_pct_applies_to_ebitda(self):
        """SOTP: growth_adj_pct uniformly scales all segment EBITDAs."""
        da_allocs = {
            "SEG1": DAAllocation(asset_share=60.0, da_allocated=6000, ebitda=10000),
            "SEG2": DAAllocation(asset_share=40.0, da_allocated=4000, ebitda=5000),
        }
        multiples = {"SEG1": 10.0, "SEG2": 8.0}

        _, base_ev = calc_sotp(da_allocs, multiples)

        # Apply +20% growth adjustment
        adj_allocs = {
            c: a.model_copy(update={"ebitda": round(a.ebitda * 1.2)})
            for c, a in da_allocs.items()
        }
        _, bull_ev = calc_sotp(adj_allocs, multiples)

        # Apply -25% growth adjustment
        bear_allocs = {
            c: a.model_copy(update={"ebitda": round(a.ebitda * 0.75)})
            for c, a in da_allocs.items()
        }
        _, bear_ev = calc_sotp(bear_allocs, multiples)

        assert bull_ev > base_ev > bear_ev
        # 20% EBITDA increase → ~20% EV increase
        assert abs(bull_ev / base_ev - 1.2) < 0.01

    def test_yaml_segment_multiples_round_trip(self):
        """YAML with segment_multiples loads correctly into ScenarioParams."""
        from valuation_runner import load_profile

        profile_path = str(Path(__file__).parent.parent / "profiles" / "msft.yaml")
        vi = load_profile(profile_path)

        bull_sc = vi.scenarios["Bull"]
        bear_sc = vi.scenarios["Bear"]
        base_sc = vi.scenarios["Base"]

        # Bull should have segment_multiples set
        assert bull_sc.segment_multiples is not None
        assert "IC" in bull_sc.segment_multiples
        assert (
            bull_sc.segment_multiples["IC"] > base_sc.segment_multiples.get("IC", 0)
            if base_sc.segment_multiples
            else True
        )

        # Bear should have lower multiples
        assert bear_sc.segment_multiples is not None
        assert bear_sc.segment_multiples["IC"] < bull_sc.segment_multiples["IC"]


class TestScenarioMethodTransition:
    """Scenario-level method transition via segment_method_override."""

    def test_revenue_to_ebitda_transition(self):
        """ev_revenue segment transitions to ev_ebitda when segment_method_override is set."""
        seg_data = {
            "AUTO": {"op": 4000, "assets": 80000},
            "FSD": {"op": -500, "assets": 5000},
        }
        total_da = 1000
        # Base: FSD uses ev_revenue (excluded from D&A allocation)
        base_methods = {"AUTO": "ev_ebitda", "FSD": "ev_revenue"}
        base_alloc = allocate_da(seg_data, total_da, base_methods)
        assert base_alloc["FSD"].da_allocated == 0  # ev_revenue gets no D&A

        base_sotp, base_ev = calc_sotp(
            base_alloc,
            {"AUTO": 8.0, "FSD": 15.0},
            segments_info={
                "AUTO": {"method": "ev_ebitda"},
                "FSD": {"method": "ev_revenue"},
            },
            revenue_by_seg={"AUTO": 80000, "FSD": 5000},
        )
        assert base_sotp["FSD"].method == "ev_revenue"
        assert base_sotp["FSD"].ev == 75000  # 5000 * 15

        # Bull scenario: FSD transitions to ev_ebitda (became profitable)
        bull_segments = {
            "AUTO": {"method": "ev_ebitda"},
            "FSD": {"method": "ev_ebitda"},  # TRANSITION
        }
        bull_methods = {"AUTO": "ev_ebitda", "FSD": "ev_ebitda"}
        bull_alloc = allocate_da(seg_data, total_da, bull_methods)
        # FSD now gets D&A allocation
        assert bull_alloc["FSD"].da_allocated > 0

        bull_sotp, bull_ev = calc_sotp(
            bull_alloc,
            {"AUTO": 8.0, "FSD": 15.0},
            segments_info=bull_segments,
            ebitda_override={"FSD": 4000},  # FSD now has EBITDA in Bull
        )
        assert bull_sotp["FSD"].method == "ev_ebitda"
        assert bull_sotp["FSD"].ev == 60000  # 4000 * 15

    def test_no_override_preserves_method(self):
        """Without segment_method_override, original methods are preserved."""
        seg_data = {"A": {"op": 1000, "assets": 50000}}
        alloc = allocate_da(seg_data, 500, {"A": "ev_ebitda"})
        sotp, _ = calc_sotp(
            alloc,
            {"A": 10.0},
            segments_info={"A": {"method": "ev_ebitda"}},
        )
        assert sotp["A"].method == "ev_ebitda"


class TestDistressDiscount:
    """Distress discount engine tests."""

    def test_healthy_company_no_discount(self):
        """Healthy financials should produce zero discount."""
        cons = {
            2025: {
                "de_ratio": 40.0,
                "net_income": 100000,
                "op": 80000,
                "dep": 10000,
                "amort": 2000,
                "gross_borr": 50000,
            },
            2024: {
                "de_ratio": 35.0,
                "net_income": 90000,
                "op": 70000,
                "dep": 9000,
                "amort": 1800,
                "gross_borr": 45000,
            },
        }
        d = calc_distress_discount(cons, 2025)
        assert d.discount == 0.0
        assert not d.applied

    def test_high_leverage_penalty(self):
        """D/E > 80% triggers leverage penalty."""
        cons = {
            2025: {
                "de_ratio": 120.0,
                "net_income": 50000,
                "op": 40000,
                "dep": 5000,
                "amort": 0,
                "gross_borr": 30000,
            },
        }
        d = calc_distress_discount(cons, 2025)
        assert d.de_penalty > 0
        assert d.loss_penalty == 0

    def test_consecutive_losses(self):
        """Two consecutive loss years trigger loss penalty."""
        cons = {
            2023: {
                "de_ratio": 50.0,
                "net_income": 10000,
                "op": 15000,
                "dep": 3000,
                "amort": 0,
                "gross_borr": 20000,
            },
            2024: {
                "de_ratio": 55.0,
                "net_income": -5000,
                "op": 2000,
                "dep": 3000,
                "amort": 0,
                "gross_borr": 22000,
            },
            2025: {
                "de_ratio": 60.0,
                "net_income": -8000,
                "op": -1000,
                "dep": 3000,
                "amort": 0,
                "gross_borr": 25000,
            },
        }
        d = calc_distress_discount(cons, 2025)
        assert d.loss_penalty == 0.10  # 2 consecutive losses

    def test_three_year_loss_streak(self):
        """Three consecutive losses get maximum loss penalty."""
        cons = {
            2023: {
                "de_ratio": 50.0,
                "net_income": -1000,
                "op": 0,
                "dep": 1000,
                "amort": 0,
                "gross_borr": 10000,
            },
            2024: {
                "de_ratio": 55.0,
                "net_income": -2000,
                "op": -500,
                "dep": 1000,
                "amort": 0,
                "gross_borr": 12000,
            },
            2025: {
                "de_ratio": 60.0,
                "net_income": -3000,
                "op": -1000,
                "dep": 1000,
                "amort": 0,
                "gross_borr": 15000,
            },
        }
        d = calc_distress_discount(cons, 2025)
        assert d.loss_penalty == 0.15

    def test_low_icr_penalty(self):
        """Low interest coverage triggers ICR penalty."""
        cons = {
            2025: {
                "de_ratio": 50.0,
                "net_income": 5000,
                "op": 8000,
                "dep": 2000,
                "amort": 0,
                "gross_borr": 200000,
            },
        }
        d = calc_distress_discount(cons, 2025)
        assert d.icr_penalty > 0

    def test_max_discount_cap(self):
        """Total discount is capped at max_discount."""
        cons = {
            2023: {
                "de_ratio": 250.0,
                "net_income": -50000,
                "op": -40000,
                "dep": 1000,
                "amort": 0,
                "gross_borr": 500000,
            },
            2024: {
                "de_ratio": 280.0,
                "net_income": -60000,
                "op": -45000,
                "dep": 1000,
                "amort": 0,
                "gross_borr": 550000,
            },
            2025: {
                "de_ratio": 300.0,
                "net_income": -70000,
                "op": -50000,
                "dep": 1000,
                "amort": 0,
                "gross_borr": 600000,
            },
        }
        d = calc_distress_discount(cons, 2025, max_discount=0.35)
        assert d.discount <= 0.35

    def test_apply_distress_discount(self):
        """apply_distress_discount reduces multiples by factor."""
        multiples = {"SEG1": 10.0, "SEG2": 8.0}
        result = apply_distress_discount(multiples, 0.20)
        assert result["SEG1"] == 8.0
        assert result["SEG2"] == 6.4

    def test_zero_discount_passthrough(self):
        """Zero discount returns original multiples."""
        multiples = {"SEG1": 10.0}
        result = apply_distress_discount(multiples, 0.0)
        assert result is multiples  # Same object (no copy needed)

    def test_cyclical_single_loss_exempt(self):
        """Cyclical industry with single-year loss gets no loss penalty."""
        cons = {
            2024: {
                "de_ratio": 50.0,
                "net_income": 10000,
                "op": 15000,
                "dep": 3000,
                "amort": 0,
                "gross_borr": 20000,
            },
            2025: {
                "de_ratio": 55.0,
                "net_income": -5000,
                "op": 2000,
                "dep": 3000,
                "amort": 0,
                "gross_borr": 22000,
            },
        }
        d = calc_distress_discount(cons, 2025, industry="Automotive Parts")
        assert d.loss_penalty == 0.0  # 1-year exemption for cyclicals

    def test_cyclical_two_year_loss_reduced_penalty(self):
        """Cyclical industry with 2 consecutive losses gets reduced penalty."""
        cons = {
            2024: {
                "de_ratio": 50.0,
                "net_income": -5000,
                "op": 2000,
                "dep": 3000,
                "amort": 0,
                "gross_borr": 20000,
            },
            2025: {
                "de_ratio": 55.0,
                "net_income": -8000,
                "op": -1000,
                "dep": 3000,
                "amort": 0,
                "gross_borr": 22000,
            },
        }
        d = calc_distress_discount(cons, 2025, industry="Semiconductor Equipment")
        assert d.loss_penalty == 0.05  # Cyclical 2-year: reduced from 10% to 5%

    def test_non_cyclical_single_loss_penalized(self):
        """Non-cyclical industry single-year loss still gets penalty."""
        cons = {
            2024: {
                "de_ratio": 50.0,
                "net_income": 10000,
                "op": 15000,
                "dep": 3000,
                "amort": 0,
                "gross_borr": 20000,
            },
            2025: {
                "de_ratio": 55.0,
                "net_income": -5000,
                "op": 2000,
                "dep": 3000,
                "amort": 0,
                "gross_borr": 22000,
            },
        }
        d = calc_distress_discount(cons, 2025, industry="Software & Services")
        assert d.loss_penalty == 0.05  # No cyclical exemption

    def test_exempt_segments_keep_original_multiples(self):
        """Exempt segments retain original multiples when discount applied."""
        multiples = {"AUTO": 10.0, "FSD": 15.0, "ENERGY": 8.0}
        result = apply_distress_discount(multiples, 0.20, exempt_segments={"FSD"})
        assert result["AUTO"] == 8.0  # 10.0 * 0.8
        assert result["FSD"] == 15.0  # exempt → original
        assert result["ENERGY"] == 6.4  # 8.0 * 0.8

    def test_healthy_segments_get_half_discount(self):
        """Healthy (profitable) segments get half the distress discount."""
        multiples = {"AUTO": 10.0, "FSD": 15.0, "ENERGY": 8.0}
        result = apply_distress_discount(
            multiples,
            0.20,
            exempt_segments={"FSD"},
            healthy_segments={"ENERGY"},
        )
        assert result["AUTO"] == 8.0  # full discount: 10.0 * 0.8
        assert result["FSD"] == 15.0  # exempt
        assert result["ENERGY"] == 7.2  # half discount: 8.0 * (1 - 0.10)

    def test_custom_max_discount_cap(self):
        """Custom max_discount cap limits total discount."""
        cons = {
            2023: {
                "de_ratio": 250.0,
                "net_income": -50000,
                "op": -40000,
                "dep": 1000,
                "amort": 0,
                "gross_borr": 500000,
            },
            2024: {
                "de_ratio": 280.0,
                "net_income": -60000,
                "op": -45000,
                "dep": 1000,
                "amort": 0,
                "gross_borr": 550000,
            },
            2025: {
                "de_ratio": 300.0,
                "net_income": -70000,
                "op": -50000,
                "dep": 1000,
                "amort": 0,
                "gross_borr": 600000,
            },
        }
        d = calc_distress_discount(cons, 2025, max_discount=0.25)
        assert d.discount <= 0.25


# ═══════════════════════════════════════════════════════════
# Gap Diagnostics Tests
# ═══════════════════════════════════════════════════════════

from engine.gap_diagnostics import (
    _binary_search,
    solve_implied_wacc,
    solve_implied_tgr,
    solve_implied_growth_multiplier,
    format_gap_diagnostic,
    GapDiagnostic,
)


class TestBinarySearch:
    def test_increasing_function(self):
        """Binary search on increasing f(x) = x."""
        result = _binary_search(lambda x: x, 0, 10, 5.0)
        assert result is not None
        assert abs(result - 5.0) < 0.01

    def test_decreasing_function(self):
        """Binary search on decreasing f(x) = -x."""
        result = _binary_search(lambda x: -x, 0, 10, -7.0)
        assert result is not None
        assert abs(result - 7.0) < 0.01

    def test_target_out_of_range_returns_none(self):
        """Target outside [f(lo), f(hi)] returns None."""
        result = _binary_search(lambda x: x, 0, 10, 15.0)
        assert result is None

    def test_target_at_boundary(self):
        """Target at boundary is found."""
        result = _binary_search(lambda x: x * 2, 0, 10, 0.0)
        assert result is not None
        assert abs(result) < 0.1


class TestReverseDCFSolvers:
    """Reverse-DCF solver tests using realistic financial data."""

    @staticmethod
    def _default_params():
        return DCFParams(
            ebitda_growth_rates=[0.10, 0.08, 0.06, 0.05, 0.03],
            terminal_growth=2.5,
            tax_rate=22.0,
        )

    def test_solve_implied_wacc_returns_value(self):
        """Implied WACC solver finds a reasonable value."""
        params = self._default_params()
        # First compute baseline DCF EV at 10% WACC
        from engine.dcf import calc_dcf

        baseline = calc_dcf(500_000, 100_000, 2_000_000, 10.0, params)
        # Now solve: target = baseline EV * 0.8 (needs higher WACC)
        target_ev = baseline.ev_dcf * 0.8
        result = solve_implied_wacc(target_ev, 500_000, 100_000, 2_000_000, params)
        assert result is not None
        assert result > 10.0  # Higher WACC needed for lower EV

    def test_solve_implied_tgr_returns_value(self):
        """Implied TGR solver finds a reasonable value."""
        params = self._default_params()
        from engine.dcf import calc_dcf

        baseline = calc_dcf(500_000, 100_000, 2_000_000, 10.0, params)
        # Target = baseline EV * 1.2 (needs higher TGR)
        target_ev = baseline.ev_dcf * 1.2
        result = solve_implied_tgr(target_ev, 500_000, 100_000, 2_000_000, 10.0, params)
        assert result is not None
        assert result > params.terminal_growth

    def test_solve_implied_growth_mult_returns_value(self):
        """Growth multiplier solver finds a value."""
        params = self._default_params()
        from engine.dcf import calc_dcf

        baseline = calc_dcf(500_000, 100_000, 2_000_000, 10.0, params)
        target_ev = baseline.ev_dcf * 1.3
        result = solve_implied_growth_multiplier(
            target_ev, 500_000, 100_000, 2_000_000, 10.0, params
        )
        assert result is not None
        assert result > 1.0

    def test_solve_implied_wacc_unreachable_returns_none(self):
        """Extremely high target EV cannot be reached — returns None."""
        params = self._default_params()
        result = solve_implied_wacc(999_999_999, 500_000, 100_000, 2_000_000, params)
        assert result is None

    def test_solve_growth_mult_no_rates_returns_none(self):
        """Empty growth rates → returns None."""
        params = DCFParams(ebitda_growth_rates=[], terminal_growth=2.5)
        result = solve_implied_growth_multiplier(
            100_000, 500_000, 100_000, 2_000_000, 10.0, params
        )
        assert result is None


class TestDiagnoseGap:
    """diagnose_gap() category routing tests."""

    @staticmethod
    def _default_params():
        return DCFParams(
            ebitda_growth_rates=[0.10, 0.08, 0.06, 0.05, 0.03],
            terminal_growth=2.5,
            tax_rate=22.0,
        )

    def test_below_threshold_returns_none(self):
        """Gap below 20% returns None."""
        result = diagnose_gap(
            gap_ratio=0.15,
            market_price=50_000,
            intrinsic_per_share=57_500,
            market_ev=5_000_000,
            ebitda_base=500_000,
            da_base=100_000,
            revenue_base=2_000_000,
            wacc_pct=10.0,
            params=self._default_params(),
        )
        assert result is None

    def test_negative_ebitda_returns_none(self):
        """EBITDA <= 0 returns None (DCF not applicable)."""
        result = diagnose_gap(
            gap_ratio=-0.50,
            market_price=50_000,
            intrinsic_per_share=25_000,
            market_ev=5_000_000,
            ebitda_base=-100_000,
            da_base=50_000,
            revenue_base=2_000_000,
            wacc_pct=10.0,
            params=self._default_params(),
        )
        assert result is None

    def test_market_premium_returns_diagnostic(self):
        """Large market premium (gap_ratio < -0.20) returns diagnostic."""
        result = diagnose_gap(
            gap_ratio=-0.50,
            market_price=100_000,
            intrinsic_per_share=50_000,
            market_ev=10_000_000,
            ebitda_base=500_000,
            da_base=100_000,
            revenue_base=2_000_000,
            wacc_pct=10.0,
            params=self._default_params(),
        )
        assert result is not None
        assert result.direction == "market_premium"
        assert result.gap_pct < 0

    def test_market_discount_returns_pessimism(self):
        """Large market discount (intrinsic > market) → market_pessimism."""
        params = self._default_params()
        from engine.dcf import calc_dcf

        baseline = calc_dcf(500_000, 100_000, 2_000_000, 10.0, params)
        # Set market_ev much lower than baseline → intrinsic > market
        low_market_ev = baseline.ev_dcf * 0.5
        result = diagnose_gap(
            gap_ratio=0.80,
            market_price=30_000,
            intrinsic_per_share=54_000,
            market_ev=low_market_ev,
            ebitda_base=500_000,
            da_base=100_000,
            revenue_base=2_000_000,
            wacc_pct=10.0,
            params=params,
        )
        assert result is not None
        assert result.direction == "market_discount"
        assert result.category == "market_pessimism"

    def test_gap_diagnostic_has_suggestions(self):
        """Diagnostic always includes at least one suggestion."""
        result = diagnose_gap(
            gap_ratio=-0.30,
            market_price=80_000,
            intrinsic_per_share=56_000,
            market_ev=8_000_000,
            ebitda_base=500_000,
            da_base=100_000,
            revenue_base=2_000_000,
            wacc_pct=10.0,
            params=self._default_params(),
        )
        assert result is not None
        assert len(result.suggestions) > 0


class TestFormatGapDiagnostic:
    def test_format_basic(self):
        """format_gap_diagnostic produces non-empty string."""
        diag = GapDiagnostic(
            gap_pct=-35.0,
            direction="market_premium",
            implied_wacc=7.5,
            category="wacc_overestimated",
            explanation="테스트 설명",
            suggestions=["테스트 권고"],
        )
        output = format_gap_diagnostic(diag, is_listed=True)
        assert "역방향 DCF 진단" in output
        assert "7.50%" in output

    def test_format_unlisted_returns_empty(self):
        """Unlisted company returns empty string."""
        diag = GapDiagnostic(gap_pct=-35.0, direction="market_premium")
        assert format_gap_diagnostic(diag, is_listed=False) == ""

    def test_format_irreconcilable(self):
        """Irreconcilable gap shows warning."""
        diag = GapDiagnostic(
            gap_pct=-60.0,
            direction="market_premium",
            category="optionality_premium",
            explanation="옵셔널리티",
            suggestions=["검토"],
            reconcilable=False,
        )
        output = format_gap_diagnostic(diag, is_listed=True)
        assert "옵셔널리티 구간" in output


# ═══════════════════════════════════════════════════════════
# P2 Edge Case Tests (from cross-model review 2026-04-09)
# ═══════════════════════════════════════════════════════════


class TestP2EdgeCases:
    """Tests for edge cases identified by 6-model cross review."""

    def test_mc_zero_shares_returns_zero_distribution(self):
        """T1: MC with shares=0 should produce all-zero distribution."""
        mc_input = MCInput(
            multiple_params={"A": (10.0, 1.5)},
            wacc_mean=8.0,
            wacc_std=1.0,
            dlom_mean=0.0,
            dlom_std=0.0,
            tg_mean=2.5,
            tg_std=0.5,
            n_sims=100,
            seed=42,
        )
        result = run_monte_carlo(
            mc_input,
            {"A": 100_000},
            net_debt=50_000,
            eco_frontier=0,
            cps_principal=0,
            cps_years=0,
            rcps_repay=0,
            buyback=0,
            shares=0,
        )
        assert result.mean == 0
        assert result.max_val == 0
        assert result.p5 == 0
        assert result.p95 == 0

    def test_gap_diagnostics_zero_ebitda_returns_none(self):
        """T2: diagnose_gap with ebitda_base=0 should return None (boundary)."""
        dcf_params = DCFParams(
            growth_rates=[0.05] * 5,
            terminal_growth=0.02,
            capex_ratio=0.15,
            nwc_ratio=0.05,
            tax_rate=0.25,
        )
        result = diagnose_gap(
            gap_ratio=-0.30,
            market_price=50000,
            intrinsic_per_share=35000,
            market_ev=5_000_000,
            ebitda_base=0,
            da_base=10_000,
            revenue_base=500_000,
            wacc_pct=9.0,
            params=dcf_params,
        )
        assert result is None

    def test_ddm_without_params_raises(self):
        """T3: DDM method without ddm_params should raise ValueError."""
        import pytest
        from valuation_runner import run_valuation, load_profile
        from pathlib import Path

        # Build minimal VI with ddm method but no ddm_params
        yaml_path = Path(__file__).parent.parent / "profiles"
        # Find any existing profile to use as base
        profiles = list(yaml_path.glob("*.yaml")) if yaml_path.exists() else []
        if not profiles:
            pytest.skip("No profile YAML available for DDM test")

        vi = load_profile(profiles[0])
        vi.valuation_method = "ddm"
        vi.ddm_params = None

        with pytest.raises(ValueError, match="ddm_params"):
            run_valuation(vi)


class TestRNPV:
    """rNPV engine tests."""

    def test_single_approved_drug(self):
        """Approved drug (PoS=100%) NPV should equal rNPV."""
        pipeline = [
            {
                "name": "DrugA",
                "phase": "approved",
                "peak_sales": 10_000,
                "years_to_peak": 3,
                "years_at_peak": 5,
                "patent_expiry_years": 15,
                "existing_revenue": 8_000,
                "launch_year_offset": 0,
            }
        ]
        result = calc_rnpv(pipeline, discount_rate=10.0)
        assert len(result.drug_results) == 1
        dr = result.drug_results[0]
        assert dr.success_prob == 1.0
        assert dr.npv == dr.rnpv  # 100% PoS → NPV = rNPV
        assert result.total_rnpv > 0
        assert result.enterprise_value == result.pipeline_value

    def test_phase2_probability(self):
        """Phase 2 drug should use ~25% PoS default."""
        pipeline = [
            {
                "name": "DrugB",
                "phase": "phase2",
                "peak_sales": 5_000,
                "years_to_peak": 5,
                "years_at_peak": 5,
                "patent_expiry_years": 15,
                "launch_year_offset": 3,
            }
        ]
        result = calc_rnpv(pipeline, discount_rate=10.0)
        dr = result.drug_results[0]
        assert dr.success_prob == PHASE_POS["phase2"]  # 0.25
        assert dr.rnpv == round(dr.npv * 0.25)

    def test_custom_success_prob(self):
        """Custom success_prob should override phase default."""
        pipeline = [
            {
                "name": "DrugC",
                "phase": "phase1",
                "peak_sales": 3_000,
                "success_prob": 0.40,
                "years_to_peak": 4,
                "years_at_peak": 4,
                "patent_expiry_years": 12,
                "launch_year_offset": 5,
            }
        ]
        result = calc_rnpv(pipeline, discount_rate=10.0)
        dr = result.drug_results[0]
        assert dr.success_prob == 0.40
        assert dr.rnpv == round(dr.npv * 0.40)

    def test_r_and_d_deduction(self):
        """R&D cost should be deducted from pipeline value."""
        pipeline = [
            {
                "name": "DrugD",
                "phase": "approved",
                "peak_sales": 20_000,
                "existing_revenue": 20_000,
                "years_at_peak": 5,
                "patent_expiry_years": 10,
                "launch_year_offset": 0,
            }
        ]
        result_no_rd = calc_rnpv(pipeline, discount_rate=10.0, r_and_d_cost=0)
        result_with_rd = calc_rnpv(pipeline, discount_rate=10.0, r_and_d_cost=2_000)
        assert result_with_rd.pipeline_value < result_no_rd.pipeline_value
        assert result_with_rd.r_and_d_cost_pv > 0

    def test_multi_drug_pipeline(self):
        """Multiple drugs should sum to total rNPV."""
        pipeline = [
            {
                "name": "A",
                "phase": "approved",
                "peak_sales": 10_000,
                "existing_revenue": 10_000,
                "years_at_peak": 5,
                "patent_expiry_years": 10,
                "launch_year_offset": 0,
            },
            {
                "name": "B",
                "phase": "phase3",
                "peak_sales": 8_000,
                "years_to_peak": 3,
                "years_at_peak": 5,
                "patent_expiry_years": 12,
                "launch_year_offset": 2,
            },
            {
                "name": "C",
                "phase": "phase1",
                "peak_sales": 15_000,
                "years_to_peak": 6,
                "years_at_peak": 4,
                "patent_expiry_years": 15,
                "launch_year_offset": 6,
            },
        ]
        result = calc_rnpv(pipeline, discount_rate=10.0)
        assert len(result.drug_results) == 3
        manual_sum = sum(dr.rnpv for dr in result.drug_results)
        assert result.total_rnpv == manual_sum

    def test_zero_discount_rate(self):
        """Zero discount rate should still work (no discounting)."""
        pipeline = [
            {
                "name": "E",
                "phase": "approved",
                "peak_sales": 1_000,
                "existing_revenue": 1_000,
                "years_at_peak": 3,
                "patent_expiry_years": 5,
                "launch_year_offset": 0,
            }
        ]
        result = calc_rnpv(pipeline, discount_rate=0.0)
        assert result.total_rnpv > 0

    def test_existing_revenue_below_peak_ramps(self):
        """Drug with existing_revenue < peak_sales should ramp to peak (Wegovy case)."""
        from engine.rnpv import _build_revenue_curve

        curve = _build_revenue_curve(
            peak_sales=18_000,
            years_to_peak=3,
            years_at_peak=5,
            patent_expiry_years=20,
            decline_rate=20.0,
            launch_year_offset=0,
            existing_revenue=12_500,
        )
        # Should ramp from 12,500 toward 18,000, then plateau at 18,000
        assert curve[0] > 12_500, "First year should grow beyond existing_revenue"
        assert 18_000 in curve, "Curve should reach peak_sales"
        plateau_count = sum(1 for v in curve if v == 18_000)
        assert plateau_count >= 5, (
            f"Should plateau for years_at_peak=5, got {plateau_count}"
        )

    def test_existing_revenue_at_peak_no_ramp(self):
        """Drug with existing_revenue >= peak_sales should plateau immediately."""
        from engine.rnpv import _build_revenue_curve

        curve = _build_revenue_curve(
            peak_sales=10_000,
            years_to_peak=3,
            years_at_peak=5,
            patent_expiry_years=15,
            decline_rate=20.0,
            launch_year_offset=0,
            existing_revenue=10_000,
        )
        # Should plateau at existing_revenue, no ramp
        assert curve[0] == 10_000
        plateau_count = sum(1 for v in curve if v == 10_000)
        assert plateau_count >= 5

    def test_wegovy_rnpv_higher_than_flat(self):
        """Wegovy-like drug with ramp should have higher rNPV than flat existing_revenue."""
        # With ramp: existing 12,500 → peak 18,000
        pipeline_ramp = [
            {
                "name": "Wegovy",
                "phase": "approved",
                "peak_sales": 18_000,
                "existing_revenue": 12_500,
                "years_to_peak": 3,
                "years_at_peak": 5,
                "patent_expiry_years": 15,
                "launch_year_offset": 0,
            }
        ]
        # Hypothetical flat: existing = peak = 12,500
        pipeline_flat = [
            {
                "name": "Wegovy",
                "phase": "approved",
                "peak_sales": 12_500,
                "existing_revenue": 12_500,
                "years_to_peak": 3,
                "years_at_peak": 5,
                "patent_expiry_years": 15,
                "launch_year_offset": 0,
            }
        ]
        result_ramp = calc_rnpv(pipeline_ramp, discount_rate=10.0)
        result_flat = calc_rnpv(pipeline_flat, discount_rate=10.0)
        assert result_ramp.total_rnpv > result_flat.total_rnpv, (
            "Ramping to higher peak should yield higher rNPV"
        )

    def test_method_selector_rnpv(self):
        """suggest_method should return 'rnpv' when has_rnpv_params=True."""
        method = suggest_method(
            n_segments=1,
            industry="pharma",
            has_rnpv_params=True,
        )
        assert method == "rnpv"

    def test_method_selector_pharma_without_rnpv(self):
        """Pharma without rnpv_params should fall through to DCF."""
        method = suggest_method(
            n_segments=1,
            industry="pharma",
            has_rnpv_params=False,
        )
        # pharma is in _GROWTH_KEYWORDS → dcf_primary
        assert method == "dcf_primary"


class TestReverseRNPV:
    """Reverse rNPV solver tests."""

    SIMPLE_PIPELINE = [
        {
            "name": "DrugA",
            "phase": "approved",
            "peak_sales": 10_000,
            "years_to_peak": 3,
            "years_at_peak": 5,
            "patent_expiry_years": 15,
            "existing_revenue": 8_000,
            "launch_year_offset": 0,
        },
        {
            "name": "DrugB",
            "phase": "phase3",
            "peak_sales": 5_000,
            "years_to_peak": 5,
            "years_at_peak": 5,
            "patent_expiry_years": 15,
            "launch_year_offset": 2,
        },
    ]

    def test_round_trip_pos_scale(self):
        """PoS scale of 1.0 should reproduce model EV."""
        base = calc_rnpv(self.SIMPLE_PIPELINE, discount_rate=10.0)
        target = float(base.enterprise_value)

        scale = solve_implied_pos_scale(
            target_ev=target,
            pipeline=self.SIMPLE_PIPELINE,
            discount_rate=10.0,
        )
        assert scale is not None
        assert abs(scale - 1.0) < 0.01

    def test_higher_target_needs_higher_pos(self):
        """Higher target EV requires higher PoS scale (pipeline-heavy)."""
        # Use pipeline-heavy drugs (no approved) so PoS scaling has room
        pipeline_drugs = [
            {
                "name": "DrugX",
                "phase": "phase2",
                "peak_sales": 8_000,
                "years_to_peak": 5,
                "years_at_peak": 5,
                "patent_expiry_years": 15,
                "launch_year_offset": 3,
            },
            {
                "name": "DrugY",
                "phase": "phase3",
                "peak_sales": 6_000,
                "years_to_peak": 4,
                "years_at_peak": 5,
                "patent_expiry_years": 14,
                "launch_year_offset": 2,
            },
        ]
        base = calc_rnpv(pipeline_drugs, discount_rate=10.0)
        higher_target = float(base.enterprise_value) * 1.3

        scale = solve_implied_pos_scale(
            target_ev=higher_target,
            pipeline=pipeline_drugs,
            discount_rate=10.0,
        )
        assert scale is not None
        assert scale > 1.0

    def test_round_trip_peak_scale(self):
        """Peak scale of 1.0 should reproduce model EV."""
        base = calc_rnpv(self.SIMPLE_PIPELINE, discount_rate=10.0)
        target = float(base.enterprise_value)

        scale = solve_implied_peak_scale(
            target_ev=target,
            pipeline=self.SIMPLE_PIPELINE,
            discount_rate=10.0,
        )
        assert scale is not None
        assert abs(scale - 1.0) < 0.01

    def test_lower_target_needs_lower_peak(self):
        """Lower target EV requires lower peak sales scale."""
        base = calc_rnpv(self.SIMPLE_PIPELINE, discount_rate=10.0)
        lower_target = float(base.enterprise_value) * 0.7

        scale = solve_implied_peak_scale(
            target_ev=lower_target,
            pipeline=self.SIMPLE_PIPELINE,
            discount_rate=10.0,
        )
        assert scale is not None
        assert scale < 1.0

    def test_round_trip_discount_rate(self):
        """Implied discount rate should match input discount rate."""
        base = calc_rnpv(self.SIMPLE_PIPELINE, discount_rate=10.0)
        target = float(base.enterprise_value)

        dr = solve_implied_discount_rate(
            target_ev=target,
            pipeline=self.SIMPLE_PIPELINE,
        )
        assert dr is not None
        assert abs(dr - 10.0) < 0.1

    def test_higher_target_needs_lower_discount(self):
        """Higher target EV requires lower discount rate."""
        base = calc_rnpv(self.SIMPLE_PIPELINE, discount_rate=10.0)
        higher_target = float(base.enterprise_value) * 1.2

        dr = solve_implied_discount_rate(
            target_ev=higher_target,
            pipeline=self.SIMPLE_PIPELINE,
        )
        assert dr is not None
        assert dr < 10.0

    def test_full_reverse_rnpv(self):
        """Full reverse_rnpv returns all three implied parameters."""
        base = calc_rnpv(self.SIMPLE_PIPELINE, discount_rate=10.0)
        model_ev = float(base.enterprise_value)
        target_ev = model_ev * 1.15  # Market 15% higher

        result = reverse_rnpv(
            target_ev=target_ev,
            model_ev=model_ev,
            pipeline=self.SIMPLE_PIPELINE,
            discount_rate=10.0,
        )
        assert result.gap_pct < 0  # Model < target → negative gap
        # PoS scale may be None if approved drugs dominate (capped at 1.0)
        assert result.implied_peak_scale is not None
        assert result.implied_peak_scale > 1.0
        assert result.implied_discount_rate is not None
        assert result.implied_discount_rate < 10.0
        assert len(result.implied_peak_per_drug) == 2

    def test_pos_capped_at_one(self):
        """Implied PoS should never exceed 1.0 for any drug."""
        base = calc_rnpv(self.SIMPLE_PIPELINE, discount_rate=10.0)
        very_high_target = float(base.enterprise_value) * 2.0

        result = reverse_rnpv(
            target_ev=very_high_target,
            model_ev=float(base.enterprise_value),
            pipeline=self.SIMPLE_PIPELINE,
            discount_rate=10.0,
        )
        if result.implied_pos_per_drug:
            for d in result.implied_pos_per_drug:
                assert d["implied_pos"] <= 1.0

    # ── Per-drug independent PoS (solo) tests ──

    def test_solve_implied_per_drug_pos_basic(self):
        """2-drug pipeline: approved skipped, phase3 solved."""
        base = calc_rnpv(self.SIMPLE_PIPELINE, discount_rate=10.0)
        target_ev = float(base.enterprise_value) * 1.10  # 10% higher

        results = solve_implied_per_drug_pos(
            target_ev=target_ev,
            pipeline=self.SIMPLE_PIPELINE,
            discount_rate=10.0,
        )
        assert len(results) == 2
        # DrugA (approved) → skipped
        assert results[0]["skipped"] is True
        assert results[0]["implied_pos"] is None
        # DrugB (phase3) → solved with higher PoS
        assert results[1]["skipped"] is False
        assert results[1]["solvable"] is True
        assert results[1]["implied_pos"] > results[1]["base_pos"]

    def test_solve_implied_per_drug_pos_unsolvable(self):
        """Gap too large for a single drug to resolve → solvable=False."""
        base = calc_rnpv(self.SIMPLE_PIPELINE, discount_rate=10.0)
        very_high_target = float(base.enterprise_value) * 3.0  # 200% higher

        results = solve_implied_per_drug_pos(
            target_ev=very_high_target,
            pipeline=self.SIMPLE_PIPELINE,
            discount_rate=10.0,
        )
        drug_b = results[1]  # phase3
        assert drug_b["solvable"] is False
        assert drug_b["implied_pos"] is None
        assert drug_b["max_ev_contribution"] > 0

    def test_solve_implied_per_drug_pos_all_approved(self):
        """All drugs approved → all skipped, no solves."""
        all_approved = [
            {
                "name": "DrugX",
                "phase": "approved",
                "peak_sales": 10000,
                "years_to_peak": 3,
                "years_at_peak": 5,
                "patent_expiry_years": 15,
                "existing_revenue": 8000,
            },
            {
                "name": "DrugY",
                "phase": "approved",
                "peak_sales": 5000,
                "years_to_peak": 2,
                "years_at_peak": 4,
                "patent_expiry_years": 10,
                "existing_revenue": 5000,
            },
        ]
        base = calc_rnpv(all_approved, discount_rate=10.0)
        results = solve_implied_per_drug_pos(
            target_ev=float(base.enterprise_value) * 1.2,
            pipeline=all_approved,
            discount_rate=10.0,
        )
        assert all(r["skipped"] for r in results)

    def test_solve_implied_per_drug_pos_single_pipeline(self):
        """Single pipeline drug: solo solve should give same implied PoS as uniform."""
        single_pipeline = [
            {
                "name": "DrugA",
                "phase": "phase3",
                "peak_sales": 5000,
                "years_to_peak": 5,
                "years_at_peak": 5,
                "patent_expiry_years": 15,
                "launch_year_offset": 0,
            },
        ]
        base = calc_rnpv(single_pipeline, discount_rate=10.0)
        target_ev = float(base.enterprise_value) * 1.5

        results = solve_implied_per_drug_pos(
            target_ev=target_ev,
            pipeline=single_pipeline,
            discount_rate=10.0,
        )
        solo_pos = results[0]["implied_pos"]

        # Uniform solver should give same result (only 1 drug to scale)
        uniform = solve_implied_pos_scale(
            target_ev=target_ev,
            pipeline=single_pipeline,
            discount_rate=10.0,
        )
        if solo_pos is not None and uniform is not None:
            # Uniform returns a scale factor; implied_pos = base_pos * scale
            base_pos = results[0]["base_pos"]
            uniform_pos = min(base_pos * uniform, 1.0)
            assert abs(solo_pos - uniform_pos) < 0.02

    def test_solve_implied_per_drug_pos_negative_gap(self):
        """Model overvalues → implied PoS should be lower than base."""
        base = calc_rnpv(self.SIMPLE_PIPELINE, discount_rate=10.0)
        target_ev = float(base.enterprise_value) * 0.90  # Market 10% lower

        results = solve_implied_per_drug_pos(
            target_ev=target_ev,
            pipeline=self.SIMPLE_PIPELINE,
            discount_rate=10.0,
        )
        drug_b = results[1]  # phase3
        if drug_b["solvable"]:
            assert drug_b["implied_pos"] < drug_b["base_pos"]

    def test_solve_implied_per_drug_pos_linear_exact(self):
        """Verify linear solve is algebraically exact."""
        base = calc_rnpv(self.SIMPLE_PIPELINE, discount_rate=10.0)
        base_ev = float(base.enterprise_value)
        target_ev = base_ev * 1.05  # Small 5% gap

        results = solve_implied_per_drug_pos(
            target_ev=target_ev,
            pipeline=self.SIMPLE_PIPELINE,
            discount_rate=10.0,
        )
        drug_b = results[1]
        if drug_b["solvable"] and drug_b["implied_pos"] is not None:
            # Verify: plug implied_pos back into calc_rnpv
            modified = [dict(d) for d in self.SIMPLE_PIPELINE]
            modified[1]["success_prob"] = drug_b["implied_pos"]
            check = calc_rnpv(modified, discount_rate=10.0)
            # Should match target_ev within rounding tolerance
            assert abs(float(check.enterprise_value) - target_ev) < 2.0

    def test_reverse_rnpv_includes_solo(self):
        """reverse_rnpv() should populate implied_pos_solo field."""
        base = calc_rnpv(self.SIMPLE_PIPELINE, discount_rate=10.0)
        result = reverse_rnpv(
            target_ev=float(base.enterprise_value) * 1.1,
            model_ev=float(base.enterprise_value),
            pipeline=self.SIMPLE_PIPELINE,
            discount_rate=10.0,
        )
        assert len(result.implied_pos_solo) == 2
        assert result.implied_pos_solo[0]["skipped"] is True  # DrugA approved
        assert result.implied_pos_solo[1]["skipped"] is False  # DrugB pipeline


class TestRNPVSensitivity:
    """rNPV sensitivity table + tornado tests."""

    PIPELINE = TestReverseRNPV.SIMPLE_PIPELINE

    def test_sensitivity_2d_table(self):
        """2D sensitivity table should have dr_range × pos_scale_range entries."""
        rows = sensitivity_rnpv(
            pipeline=self.PIPELINE,
            discount_rate=10.0,
            net_debt=5000,
            shares=100_000_000,
            unit_multiplier=1_000_000,
            dr_range=[8.0, 10.0, 12.0],
            pos_scale_range=[0.8, 1.0, 1.2],
        )
        assert len(rows) == 9  # 3 × 3
        # Higher PoS → higher value (same discount rate)
        at_10 = {r.col_val: r.value for r in rows if r.row_val == 10.0}
        assert at_10[1.2] >= at_10[1.0] >= at_10[0.8]
        # Lower discount rate → higher value (same PoS)
        at_1x = {r.row_val: r.value for r in rows if r.col_val == 1.0}
        assert at_1x[8.0] >= at_1x[10.0] >= at_1x[12.0]

    def test_tornado_ordering(self):
        """Tornado results should be sorted by impact magnitude (largest first)."""
        tornado = sensitivity_rnpv_tornado(
            pipeline=self.PIPELINE,
            discount_rate=10.0,
            net_debt=5000,
            shares=100_000_000,
            unit_multiplier=1_000_000,
        )
        assert len(tornado) == 2
        # Sorted by swing (largest first)
        swings = [t["high_value"] - t["low_value"] for t in tornado]
        assert swings == sorted(swings, reverse=True)
        # Each item has expected keys
        for t in tornado:
            assert t["high_value"] >= t["base_value"] >= t["low_value"]
            assert t["high_peak"] > t["low_peak"]

    def test_tornado_symmetry(self):
        """Base value should be the same for all drugs."""
        tornado = sensitivity_rnpv_tornado(
            pipeline=self.PIPELINE,
            discount_rate=10.0,
            net_debt=5000,
            shares=100_000_000,
            unit_multiplier=1_000_000,
        )
        base_values = {t["base_value"] for t in tornado}
        assert len(base_values) == 1  # All drugs share same base


class TestCrashPaths:
    """Regression tests for CR-1/CR-2/CR-3 crash paths identified in 4th audit."""

    # ── CR-1: DDM ke <= 0 ────────────────────────────────────────────────────

    def test_ddm_ke_zero_raises(self):
        """calc_ddm: ke=0% with positive growth raises ValueError (not silent crash)."""
        import pytest

        with pytest.raises(ValueError, match="Ke.*greater than growth|must be greater"):
            calc_ddm(dps=500, growth=2.0, ke=0.0)

    def test_ddm_ke_negative_growth_positive_raises(self):
        """calc_ddm: ke=-1% with growth=2% → ke <= g, raises ValueError."""
        import pytest

        with pytest.raises(ValueError):
            calc_ddm(dps=500, growth=2.0, ke=-1.0)

    # ── CR-1: RIM ke near -100% ZeroDivisionError ────────────────────────────

    def test_rim_ke_exactly_minus100_raises_not_zerodivision(self):
        """calc_rim: ke=-100% would make (1+Ke)=0 → ZeroDivisionError.
        After fix: raises ValueError before the discount computation."""
        import pytest

        with pytest.raises(ValueError, match="zero discount factor"):
            calc_rim(
                book_value=100_000,
                roe_forecasts=[5.0, 4.0],
                ke=-100.0,
                terminal_growth=-101.0,
            )

    def test_rim_ke_below_minus100_raises(self):
        """calc_rim: ke < -100% also raises ValueError via same guard."""
        import pytest

        with pytest.raises(ValueError, match="zero discount factor"):
            calc_rim(
                book_value=100_000,
                roe_forecasts=[5.0],
                ke=-150.0,
                terminal_growth=-200.0,
            )

    # ── CR-2: sensitivity_dcf negative wacc range ────────────────────────────

    def test_sensitivity_dcf_negative_wacc_no_crash(self):
        """sensitivity_dcf: wacc_range including negative values returns value=0 (no crash)."""
        params = DCFParams(
            ebitda_growth_rates=[0.05, 0.04, 0.03],
            terminal_growth=2.0,
            tax_rate=25.0,
        )
        # wacc_range includes negative values — should not raise ZeroDivisionError
        rows, wacc_r, tg_r = sensitivity_dcf(
            ebitda_base=50_000,
            da_base=10_000,
            revenue_base=200_000,
            params=params,
            base_year=2025,
            wacc_range=[-1.0, 0.0, 3.0, 5.0, 8.0],
            tg_range=[1.0, 2.0, 3.0],
        )
        # Negative / zero wacc rows should all have value=0
        negative_rows = [r for r in rows if r.row_val <= 0]
        assert all(r.value == 0 for r in negative_rows), "negative wacc rows must be 0"
        # Positive rows should be normal
        positive_rows = [r for r in rows if r.row_val > 0 and r.row_val > r.col_val]
        assert any(r.value > 0 for r in positive_rows)

    def test_sensitivity_dcf_wacc_minus100_no_zerodivision(self):
        """sensitivity_dcf: wacc=-100% (discount=0) does not raise ZeroDivisionError."""
        params = DCFParams(
            ebitda_growth_rates=[0.05],
            terminal_growth=2.0,
            tax_rate=25.0,
        )
        # Should not raise; row with w=-100 gets value=0
        rows, _, _ = sensitivity_dcf(
            ebitda_base=50_000,
            da_base=10_000,
            revenue_base=200_000,
            params=params,
            base_year=2025,
            wacc_range=[-100.0, 5.0, 8.0],
            tg_range=[1.0, 2.0],
        )
        minus100_rows = [r for r in rows if r.row_val == -100.0]
        assert all(r.value == 0 for r in minus100_rows)

    # ── CR-3: SOTP missing segment_data for base_year ────────────────────────

    def test_sotp_missing_segment_data_base_year_raises(self):
        """_run_sotp_valuation: segment_data missing base_year raises ValueError."""
        import pytest
        from schemas.models import ValuationInput, CompanyProfile
        from valuation_runner import run_valuation

        with pytest.raises((ValueError, KeyError)):
            vi = ValuationInput(
                company=CompanyProfile(
                    name="Test", shares_total=100, shares_ordinary=100
                ),
                segments={"A": {"name": "A", "multiple": 8.0}},
                # segment_data has only 2024, but base_year is 2025
                segment_data={2024: {"A": {"revenue": 100, "op": 10, "assets": 50}}},
                consolidated={
                    2025: {
                        "revenue": 100,
                        "op": 10,
                        "net_income": 8,
                        "assets": 200,
                        "liabilities": 100,
                        "equity": 100,
                        "dep": 5,
                        "amort": 2,
                        "de_ratio": 50.0,
                    }
                },
                wacc_params=WACCParams(
                    rf=3.5, erp=7.0, bu=1.0, de=50, tax=22, kd_pre=5, eq_w=70
                ),
                multiples={"A": 8.0},
                scenarios={
                    "Base": ScenarioParams(
                        code="Base", name="Base", prob=100, ipo="N/A", shares=100
                    ),
                },
                dcf_params=DCFParams(ebitda_growth_rates=[0.05]),
                base_year=2025,
                valuation_method="sotp",
            )
            run_valuation(vi)
