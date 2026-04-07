"""Engine regression & unit tests."""

from pathlib import Path

from schemas.models import WACCParams, ScenarioParams, DCFParams, DAAllocation
from engine.wacc import calc_wacc
from engine.sotp import allocate_da, calc_sotp
from engine.dcf import calc_dcf
from engine.scenario import calc_scenario
from engine.sensitivity import (
    sensitivity_multiples, sensitivity_irr_dlom, sensitivity_dcf,
    sensitivity_ddm, sensitivity_rim, sensitivity_nav, sensitivity_multiple_range,
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
from engine.growth import linear_fade, calc_ebitda_growth, generate_growth_rates
from engine.distress import calc_distress_discount, apply_distress_discount
from engine.method_selector import classify_industry
from engine.drivers import resolve_drivers
from schemas.models import NewsDriver


# ── SK Ecoplant reference data ──

SK_SEG_DATA_2025 = {
    "HI":  {"revenue": 5_158_561, "gross_profit": 271_510, "op":  74_208, "assets":  511_209},
    "GAS": {"revenue":   385_640, "gross_profit": 121_126, "op":  79_644, "assets": 1_302_785},
    "ALC": {"revenue": 2_596_506, "gross_profit": 344_714, "op": 169_356, "assets": 1_258_024},
    "SOL": {"revenue": 4_050_862, "gross_profit": 416_820, "op":  -7_264, "assets": 1_407_514},
    "ETC": {"revenue":         0, "gross_profit":       0, "op":       0, "assets":    23_007},
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
        p = WACCParams(rf=3.50, erp=7.00, bu=0.750, de=192.0, tax=22.0, kd_pre=5.50, eq_w=34.2)
        r = calc_wacc(p)
        assert r.bl == 1.873
        assert r.ke == 16.61
        assert r.kd_at == 4.29
        assert r.wacc == 8.50

    def test_zero_leverage(self):
        p = WACCParams(rf=3.0, erp=6.0, bu=1.0, de=0.0, tax=25.0, kd_pre=5.0, eq_w=100.0)
        r = calc_wacc(p)
        assert r.bl == 1.0
        assert r.wacc == r.ke


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

    def test_negative_ebitda_negative_ev(self):
        """W-8: negative EBITDA produces negative EV (restructuring/divestiture)."""
        alloc = allocate_da({"A": {"op": -100, "assets": 100}}, 50)
        sotp, ev = calc_sotp(alloc, {"A": 10.0})
        # EBITDA = -100 + 50 = -50, EV = -50 * 10 = -500
        assert sotp["A"].ev < 0
        assert ev < 0

    def test_mixed_positive_negative_ebitda(self):
        """W-8: mixed segments — negative EV segment reduces total."""
        alloc = allocate_da({
            "A": {"op": 200, "assets": 100},
            "B": {"op": -200, "assets": 100},
        }, 100)
        sotp, ev = calc_sotp(alloc, {"A": 10.0, "B": 5.0})
        assert sotp["A"].ev > 0
        assert sotp["B"].ev < 0
        assert ev < sotp["A"].ev  # Negative segment reduces total

    def test_ev_revenue_basic(self):
        """ev_revenue: EV = revenue × multiple."""
        alloc = allocate_da({"FSD": {"op": 0, "assets": 0}}, 0,
                            segment_methods={"FSD": "ev_revenue"})
        sotp, ev = calc_sotp(
            alloc, {"FSD": 15.0},
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
        alloc = allocate_da({"FSD": {"op": 0, "assets": 0}}, 0,
                            segment_methods={"FSD": "ev_revenue"})
        sotp, ev = calc_sotp(
            alloc, {"FSD": 15.0},
            segments_info={"FSD": {"name": "FSD", "method": "ev_revenue"}},
            revenue_by_seg={"FSD": 5000},
            revenue_override={"FSD": 20000},
            multiple_override={"FSD": 20.0},
        )
        assert sotp["FSD"].ev == 400000  # 20000 * 20.0
        assert sotp["FSD"].revenue == 20000

    def test_ev_revenue_zero(self):
        """ev_revenue: revenue=0 → EV=0 (pre-launch segment)."""
        alloc = allocate_da({"ROBO": {"op": 0, "assets": 0}}, 0,
                            segment_methods={"ROBO": "ev_revenue"})
        sotp, ev = calc_sotp(
            alloc, {"ROBO": 25.0},
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
            alloc, {"AUTO": 8.0, "FSD": 15.0},
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
        alloc = allocate_da(seg_data, 100,
                            segment_methods={"A": "ev_ebitda", "B": "ev_revenue"})
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
            code="A", name="IPO 성공", prob=20, ipo="성공",
            dlom=0, cps_repay=0, rcps_repay=0, buyback=0,
            shares=SK_SHARES_TOTAL,
        )
        r = calc_scenario(sc, ev, SK_NET_DEBT, SK_ECO_FRONTIER, SK_CPS_PRINCIPAL, SK_CPS_YEARS,
                          SK_RCPS_PRINCIPAL, SK_RCPS_YEARS)
        assert r.post_dlom > 0
        assert r.pre_dlom == r.post_dlom  # DLOM=0

    def test_sk_scenario_b(self):
        ev = self._get_sk_ev()
        sc = ScenarioParams(
            code="B", name="FI 우호", prob=45, ipo="불발", irr=5.0,
            dlom=20, rcps_repay=490_000, buyback=200_000,
            shares=SK_SHARES_ORDINARY,
        )
        r = calc_scenario(sc, ev, SK_NET_DEBT, SK_ECO_FRONTIER, SK_CPS_PRINCIPAL, SK_CPS_YEARS,
                          SK_RCPS_PRINCIPAL, SK_RCPS_YEARS)
        assert r.post_dlom > 0
        assert r.post_dlom < r.pre_dlom  # DLOM applied

    def test_scenario_with_different_unit_multiplier(self):
        """Verify per-share value is correct in 100M KRW unit"""
        sc = ScenarioParams(
            code="A", name="Test", prob=100, ipo="N/A",
            dlom=0, shares=10_000_000,
        )
        r = calc_scenario(sc, 100, 0, 0, 0, 0, unit_multiplier=100_000_000)
        # 10B KRW equity / 10M shares = 1,000 KRW/share
        assert r.pre_dlom == 1_000

    def test_negative_equity(self):
        sc = ScenarioParams(
            code="A", name="Neg", prob=100, ipo="N/A",
            dlom=0, shares=10_000,
        )
        r = calc_scenario(sc, 100, 200, 0, 0, 0)
        assert r.equity_value < 0
        assert r.pre_dlom < 0  # Negative equity propagates for distress scenarios
        assert r.post_dlom < 0  # DLOM not applied to negative equity

    def test_cps_dividend_rate_reduces_repay(self):
        """W-9: CPS dividend rate reduces effective compound rate."""
        sc = ScenarioParams(
            code="A", name="Test", prob=100, ipo="불발",
            irr=10.0, dlom=0, shares=100_000,
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
            code="A", name="Test", prob=100, ipo="불발",
            irr=10.0, dlom=0, shares=100_000,
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
            tax_rate=22.0, capex_to_da=1.10,
            nwc_to_rev_delta=0.05, terminal_growth=2.5,
        )
        ebitda_base = 315_944 + SK_DA_2025
        r = calc_dcf(ebitda_base, SK_DA_2025, 12_191_569, 8.50, params, 2025)
        assert len(r.projections) == 5
        assert r.projections[0].year == 2026
        assert r.ev_dcf > 0

    def test_high_wacc_low_ev(self):
        params = DCFParams(
            ebitda_growth_rates=[0.05], tax_rate=25.0,
            capex_to_da=1.0, nwc_to_rev_delta=0.0, terminal_growth=2.0,
        )
        low = calc_dcf(1000, 500, 5000, 15.0, params)
        high = calc_dcf(1000, 500, 5000, 7.0, params)
        assert low.ev_dcf < high.ev_dcf

    def test_actual_capex_nwc(self):
        base_params = DCFParams(
            ebitda_growth_rates=[0.10, 0.08], tax_rate=22.0,
            capex_to_da=1.10, nwc_to_rev_delta=0.05, terminal_growth=2.5,
        )
        actual_params = DCFParams(
            ebitda_growth_rates=[0.10, 0.08], tax_rate=22.0,
            capex_to_da=1.10, nwc_to_rev_delta=0.05, terminal_growth=2.5,
            actual_capex=400, actual_nwc=300, prior_nwc=280,
        )
        r_base = calc_dcf(1000, 500, 5000, 8.5, base_params)
        r_actual = calc_dcf(1000, 500, 5000, 8.5, actual_params)
        assert r_base.ev_dcf != r_actual.ev_dcf
        assert r_actual.ev_dcf > r_base.ev_dcf


# ═══════════════════════════════════════════════════════════
# Sensitivity Tests
# ═══════════════════════════════════════════════════════════

class TestSensitivity:
    def test_multiples_grid_size(self):
        alloc = allocate_da(SK_SEG_DATA_2025, SK_DA_2025)
        rows, hi_r, alc_r = sensitivity_multiples(
            alloc, SK_MULTIPLES, SK_NET_DEBT, SK_ECO_FRONTIER, SK_SHARES_TOTAL,
        )
        assert len(rows) == len(hi_r) * len(alc_r)

    def test_multiples_auto_segment_selection(self):
        """row_seg/col_seg not specified: auto-selects segments"""
        alloc = allocate_da(SK_SEG_DATA_2025, SK_DA_2025)
        rows, _, _ = sensitivity_multiples(
            alloc, SK_MULTIPLES, SK_NET_DEBT, SK_ECO_FRONTIER, SK_SHARES_TOTAL,
        )
        assert len(rows) > 0

    def test_irr_dlom_grid_size(self):
        alloc = allocate_da(SK_SEG_DATA_2025, SK_DA_2025)
        _, ev = calc_sotp(alloc, SK_MULTIPLES)
        rows, irr_r, dlom_r = sensitivity_irr_dlom(
            ev, SK_NET_DEBT, SK_ECO_FRONTIER, SK_CPS_PRINCIPAL, SK_CPS_YEARS,
            490_000, 200_000, SK_SHARES_ORDINARY,
        )
        assert len(rows) == len(irr_r) * len(dlom_r)

    def test_dcf_sensitivity_monotonic(self):
        params = DCFParams(
            ebitda_growth_rates=[0.10, 0.08, 0.06, 0.05, 0.04],
            tax_rate=22.0, capex_to_da=1.10,
            nwc_to_rev_delta=0.05, terminal_growth=2.5,
        )
        rows, wacc_r, tg_r = sensitivity_dcf(
            627_577, SK_DA_2025, 12_191_569, params, 2025,
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
            tax_rate=22.0, capex_to_da=1.10,
            nwc_to_rev_delta=0.05, terminal_growth=2.5,
        )
        rows, wacc_r, tg_r = sensitivity_dcf(
            627_577, SK_DA_2025, 12_191_569, params, 2025,
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
        r = calc_ev_revenue(revenue=10_000_000, multiple=0.5, net_debt=2_000_000, shares=50_000_000)
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
            revenue=10_000_000, ebitda=1_000_000, net_income=500_000,
            book_value=2_000_000, net_debt=2_000_000, shares=50_000_000,
            sotp_ev=6_000_000, dcf_ev=5_500_000,
        )
        methods = [r.method for r in results]
        assert "SOTP (EV/EBITDA)" in methods
        assert "DCF (FCFF)" in methods
        assert len(results) == 2

    def test_cross_validate_with_all_multiples(self):
        results = cross_validate(
            revenue=10_000_000, ebitda=1_000_000, net_income=500_000,
            book_value=2_000_000, net_debt=2_000_000, shares=50_000_000,
            sotp_ev=6_000_000, dcf_ev=5_500_000,
            ev_revenue_multiple=0.5, pe_multiple=15.0, pbv_multiple=1.2,
        )
        assert len(results) == 5


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
        stats = calc_peer_stats(peers, {"HI": 8.0, "SOL": 5.0}, {"HI": "Hi-Tech", "SOL": "솔루션"})
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
            wacc_mean=8.5, wacc_std=1.0,
            dlom_mean=20.0, dlom_std=5.0,
            tg_mean=2.5, tg_std=0.5,
            n_sims=1000, seed=42,
        )
        result = run_monte_carlo(
            mc_input,
            seg_ebitdas={"HI": 109_590, "ALC": 256_427},
            net_debt=2_295_568, eco_frontier=94_644,
            cps_principal=600_000, cps_years=4,
            rcps_repay=490_000, buyback=200_000,
            shares=54_278_993, irr=5.0,
        )
        assert result.n_sims == 1000
        assert result.mean > 0
        assert result.p5 < result.median < result.p95

    def test_mc_reproducibility(self):
        mc_input = MCInput(
            multiple_params={"A": (10.0, 1.5)},
            wacc_mean=8.0, wacc_std=1.0,
            dlom_mean=0.0, dlom_std=0.0,
            tg_mean=2.5, tg_std=0.5,
            n_sims=500, seed=123,
        )
        r1 = run_monte_carlo(mc_input, {"A": 100_000}, 50_000, 0, 0, 0, 0, 0, 10_000_000)
        r2 = run_monte_carlo(mc_input, {"A": 100_000}, 50_000, 0, 0, 0, 0, 0, 10_000_000)
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

        profile_path = str(Path(__file__).parent.parent / "profiles" / "sk_ecoplant.yaml")
        vi = load_profile(profile_path)
        result = run_valuation(vi)

        # Structural verification (instead of fixed values)
        assert result.primary_method == "sotp"
        assert result.wacc.wacc == 9.02  # 8.50 + size_premium 1.5% → Ke 18.11% → WACC 9.02%
        assert 4_800_000 < result.total_ev < 6_400_000  # SOTP EV (distress discount may reduce)
        assert result.weighted_value > 0
        assert len(result.cross_validations) >= 2
        assert result.dcf is not None
        assert result.dcf.ev_dcf > 0

    def test_sk_ecoplant_mc(self):
        """SK Ecoplant Monte Carlo integration"""
        from valuation_runner import load_profile, run_valuation

        profile_path = str(Path(__file__).parent.parent / "profiles" / "sk_ecoplant.yaml")
        vi = load_profile(profile_path)
        result = run_valuation(vi)

        assert result.monte_carlo is not None
        mc = result.monte_carlo
        assert mc.n_sims == 10_000
        assert mc.p5 < mc.median < mc.p95

    def test_ddm_kb_financial(self):
        """KB Financial Group DDM integration test"""
        from valuation_runner import load_profile, run_valuation

        profile_path = str(Path(__file__).parent.parent / "profiles" / "kb_financial.yaml")
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
                ebitda_base=100_000, da_base=20_000, revenue_base=500_000,
                wacc_pct=3.0,  # WACC < TG
                params=params, base_year=2025,
            )

    def test_scenario_prob_sum_not_100(self):
        """Scenario probability sum != 100% raises ValuationInput error."""
        import pytest
        from schemas.models import ValuationInput, CompanyProfile
        with pytest.raises(Exception, match="확률 합계"):
            ValuationInput(
                company=CompanyProfile(name="Test", shares_total=100, shares_ordinary=100),
                segments={"A": {"name": "A", "multiple": 5.0}},
                segment_data={2025: {"A": {"revenue": 100, "op": 10, "assets": 50}}},
                consolidated={2025: {"revenue": 100, "op": 10, "net_income": 8,
                                     "assets": 200, "liabilities": 100, "equity": 100,
                                     "dep": 5, "amort": 2, "de_ratio": 100.0}},
                wacc_params=WACCParams(rf=3.5, erp=7.0, bu=0.7, de=100, tax=22, kd_pre=5, eq_w=50),
                multiples={"A": 5.0},
                scenarios={
                    "Base": ScenarioParams(code="Base", name="Base", prob=60, ipo="N/A", shares=100),
                    "Bull": ScenarioParams(code="Bull", name="Bull", prob=60, ipo="N/A", shares=100),
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
                company=CompanyProfile(name="Test", shares_total=100, shares_ordinary=100),
                segments={"A": {"name": "A", "multiple": 5.0}},
                segment_data={2024: {"A": {"revenue": 100, "op": 10, "assets": 50}}},
                consolidated={2024: {"revenue": 100, "op": 10, "net_income": 8,
                                     "assets": 200, "liabilities": 100, "equity": 100,
                                     "dep": 5, "amort": 2, "de_ratio": 100.0}},
                wacc_params=WACCParams(rf=3.5, erp=7.0, bu=0.7, de=100, tax=22, kd_pre=5, eq_w=50),
                multiples={"A": 5.0},
                scenarios={
                    "Base": ScenarioParams(code="Base", name="Base", prob=100, ipo="N/A", shares=100),
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
                company=CompanyProfile(name="Test", shares_total=100, shares_ordinary=100),
                segments={"A": {"name": "A", "multiple": -3.0}},
                segment_data={2025: {"A": {"revenue": 100, "op": 10, "assets": 50}}},
                consolidated={2025: {"revenue": 100, "op": 10, "net_income": 8,
                                     "assets": 200, "liabilities": 100, "equity": 100,
                                     "dep": 5, "amort": 2, "de_ratio": 100.0}},
                wacc_params=WACCParams(rf=3.5, erp=7.0, bu=0.7, de=100, tax=22, kd_pre=5, eq_w=50),
                multiples={"A": -3.0},
                scenarios={
                    "Base": ScenarioParams(code="Base", name="Base", prob=100, ipo="N/A", shares=100),
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
            wacc_mean=9.0, wacc_std=1.0,
            dlom_mean=0, dlom_std=0,
            tg_mean=2.5, tg_std=0.5,
            n_sims=5_000, seed=42,
        )
        seg_ebitdas = {"A": 500_000}

        # Without DCF info
        r1 = run_monte_carlo(
            mc_params, seg_ebitdas,
            net_debt=100_000, eco_frontier=0,
            cps_principal=0, cps_years=0,
            rcps_repay=0, buyback=0, shares=50_000_000,
            unit_multiplier=1_000_000,
        )

        # With DCF info: WACC/TG variation reflected in EV
        r2 = run_monte_carlo(
            mc_params, seg_ebitdas,
            net_debt=100_000, eco_frontier=0,
            cps_principal=0, cps_years=0,
            rcps_repay=0, buyback=0, shares=50_000_000,
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
            wacc_mean=9.0, wacc_std=1.0,
            dlom_mean=10.0, dlom_std=3.0,
            tg_mean=2.0, tg_std=0.3,
            n_sims=10_000, seed=123,
        )
        r = run_monte_carlo(
            mc_params, {"A": 1_000_000},
            net_debt=500_000, eco_frontier=0,
            cps_principal=0, cps_years=0,
            rcps_repay=0, buyback=0, shares=100_000_000,
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
            wacc_mean=9.0, wacc_std=0.01,
            dlom_mean=0, dlom_std=0,
            tg_mean=2.5, tg_std=0.01,
            n_sims=5_000, seed=42,
            segment_methods={"FSD": "ev_revenue"},
        )
        # FSD: EBITDA=0 (pre-profit), Revenue=5000
        r = run_monte_carlo(
            mc_params, {"FSD": 0},
            net_debt=10_000, eco_frontier=0,
            cps_principal=0, cps_years=0,
            rcps_repay=0, buyback=0, shares=50_000_000,
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
            wacc_mean=9.0, wacc_std=0.01,
            dlom_mean=0, dlom_std=0,
            tg_mean=2.5, tg_std=0.01,
            n_sims=5_000, seed=42,
            segment_methods={"AUTO": "ev_ebitda", "FSD": "ev_revenue"},
        )
        r_mixed = run_monte_carlo(
            mc_params, {"AUTO": 10_000, "FSD": 0},
            net_debt=0, eco_frontier=0,
            cps_principal=0, cps_years=0,
            rcps_repay=0, buyback=0, shares=50_000_000,
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
            wacc_mean=9.0, wacc_std=1.0,
            dlom_mean=0, dlom_std=0,
            tg_mean=2.5, tg_std=0.5,
            n_sims=1_000, seed=42,
            segment_methods={"ROBO": "ev_revenue"},
        )
        r = run_monte_carlo(
            mc_params, {"ROBO": 0},
            net_debt=0, eco_frontier=0,
            cps_principal=0, cps_years=0,
            rcps_repay=0, buyback=0, shares=50_000_000,
            unit_multiplier=1_000_000,
            seg_revenues={"ROBO": 0},
        )
        # All EV = 0 → per-share = 0
        assert r.mean == 0

    def test_mc_backward_compat(self):
        """MCInput without segment_methods preserves existing behavior."""
        mc_old = MCInput(
            multiple_params={"A": (8.0, 1.2)},
            wacc_mean=9.0, wacc_std=1.0,
            dlom_mean=0, dlom_std=0,
            tg_mean=2.5, tg_std=0.5,
            n_sims=5_000, seed=42,
        )
        mc_new = MCInput(
            multiple_params={"A": (8.0, 1.2)},
            wacc_mean=9.0, wacc_std=1.0,
            dlom_mean=0, dlom_std=0,
            tg_mean=2.5, tg_std=0.5,
            n_sims=5_000, seed=42,
            segment_methods={},
        )
        kwargs = dict(
            net_debt=100_000, eco_frontier=0,
            cps_principal=0, cps_years=0,
            rcps_repay=0, buyback=0, shares=50_000_000,
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
        profile_path = str(Path(__file__).parent.parent / "profiles" / "sk_ecoplant.yaml")
        vi = load_profile(profile_path)

        assert vi.company.name == "SK에코플랜트"
        assert len(vi.segments) == 5
        assert vi.base_year in vi.consolidated
        assert len(vi.scenarios) > 0
        total_prob = sum(sc.prob for sc in vi.scenarios.values())
        assert abs(total_prob - 100.0) < 0.1

    def test_load_kb_financial_ddm(self):
        from valuation_runner import load_profile
        profile_path = str(Path(__file__).parent.parent / "profiles" / "kb_financial.yaml")
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
        r = calc_ps(revenue=500_000, multiple=3.0, shares=1_000_000, unit_multiplier=1_000_000)
        assert r.method == "P/S"
        assert r.equity_value == 1_500_000
        assert r.per_share > 0

    def test_ps_zero_revenue(self):
        r = calc_ps(revenue=0, multiple=3.0, shares=1_000_000)
        assert r.equity_value == 0

    def test_pffo_basic(self):
        r = calc_pffo(ffo=200_000, multiple=18.0, shares=1_000_000, unit_multiplier=1_000_000)
        assert r.method == "P/FFO"
        assert r.equity_value == 3_600_000
        assert r.per_share > 0

    def test_pffo_zero_ffo(self):
        r = calc_pffo(ffo=0, multiple=18.0, shares=1_000_000)
        assert r.equity_value == 0

    def test_cross_validate_includes_ps_pffo(self):
        """P/S and P/FFO included in cross-validation"""
        results = cross_validate(
            revenue=500_000, ebitda=100_000, net_income=50_000,
            book_value=300_000, net_debt=100_000, shares=1_000_000,
            sotp_ev=800_000, dcf_ev=750_000,
            ps_multiple=2.5, pffo_multiple=15.0, ffo=80_000,
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
            book_value=100_000, roe_forecasts=[12.0, 12.0, 12.0],
            ke=10.0, terminal_growth=0.0, shares=1_000_000,
            unit_multiplier=1_000_000,
        )
        r_pos_g = calc_rim(
            book_value=100_000, roe_forecasts=[12.0, 12.0, 12.0],
            ke=10.0, terminal_growth=2.0, shares=1_000_000,
            unit_multiplier=1_000_000,
        )
        assert r_pos_g.equity_value > r_zero_g.equity_value

    def test_bv_accumulation_clean_surplus(self):
        """Payout=0: BV grows by NI each period (clean surplus)"""
        r = calc_rim(
            book_value=100_000, roe_forecasts=[10.0, 10.0],
            ke=10.0, shares=1, unit_multiplier=1,
        )
        # BV₁ = 100,000 + NI₁(=10,000) = 110,000
        assert r.projections[1].bv == 110_000

    def test_bv_accumulation_with_payout(self):
        """Payout ratio 40%: only 60% of NI retained in BV"""
        r = calc_rim(
            book_value=100_000, roe_forecasts=[10.0, 10.0],
            ke=8.0, shares=1, unit_multiplier=1, payout_ratio=40.0,
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
        r1 = calc_nav(10_000, 4_000, 1_000_000, revaluation=0, unit_multiplier=1_000_000)
        r2 = calc_nav(10_000, 4_000, 1_000_000, revaluation=10_000, unit_multiplier=1_000_000)
        assert r2.per_share > r1.per_share
        assert r2.nav == 16_000  # 10,000 + 10,000 - 4,000

    def test_negative_revaluation(self):
        """Negative revaluation decreases NAV"""
        r = calc_nav(10_000, 4_000, 1_000_000, revaluation=-3_000, unit_multiplier=1_000_000)
        assert r.adjusted_assets == 7_000
        assert r.nav == 3_000


# ═══════════════════════════════════════════════════════════
# Monte Carlo Enhanced Edge Cases
# ═══════════════════════════════════════════════════════════

class TestMonteCarloEdgeCases:
    def test_negative_equity_clamped_to_zero(self):
        """claims > EV: negative per-share value clipped to 0"""
        mc = MCInput(
            multiple_params={"A": (2.0, 0.1)},  # low multiple
            wacc_mean=8.0, wacc_std=0.5,
            dlom_mean=0, dlom_std=0,
            tg_mean=2.0, tg_std=0.3,
            n_sims=1000, seed=42,
        )
        r = run_monte_carlo(
            mc, {"A": 10_000},
            net_debt=500_000,  # EV(~20,000) << claims(500,000)
            eco_frontier=0, cps_principal=0, cps_years=0,
            rcps_repay=0, buyback=0, shares=1_000_000,
            unit_multiplier=1_000_000,
        )
        assert r.min_val >= 0

    def test_dlom_clipped_to_50(self):
        """DLOM mean 45%, std 10%: 50% upper-bound clipping"""
        mc = MCInput(
            multiple_params={"A": (10.0, 0.5)},
            wacc_mean=8.0, wacc_std=0.5,
            dlom_mean=45.0, dlom_std=10.0,  # many samples exceed 50%
            tg_mean=2.0, tg_std=0.3,
            n_sims=5000, seed=42,
        )
        r = run_monte_carlo(
            mc, {"A": 500_000},
            net_debt=100_000, eco_frontier=0,
            cps_principal=0, cps_years=0,
            rcps_repay=0, buyback=0, shares=50_000_000,
            unit_multiplier=1_000_000,
        )
        # DLOM capped at 50%, so per-share value > 0
        assert r.mean > 0
        assert r.p5 >= 0

    def test_histogram_generated(self):
        """Histogram bins/counts generated after simulation"""
        mc = MCInput(
            multiple_params={"A": (10.0, 1.5)},
            wacc_mean=9.0, wacc_std=1.0,
            dlom_mean=10.0, dlom_std=3.0,
            tg_mean=2.0, tg_std=0.5,
            n_sims=2000, seed=42,
        )
        r = run_monte_carlo(
            mc, {"A": 500_000},
            net_debt=100_000, eco_frontier=0,
            cps_principal=0, cps_years=0,
            rcps_repay=0, buyback=0, shares=50_000_000,
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
            dps=1000, ke_base=5.0, g_base=4.5,
            ke_range=[3.0, 4.0, 5.0], g_range=[3.0, 4.0, 5.0],
        )
        # ke=3%, g=5% → invalid → 0
        invalid = [r for r in rows if r.row_val <= r.col_val]
        assert all(r.value == 0 for r in invalid)

    def test_rim_grid_size(self):
        rows = sensitivity_rim(
            book_value=100_000, roe_forecasts=[12.0, 11.0],
            ke_base=10.0, shares=1_000_000,
        )
        assert len(rows) == 7 * 7

    def test_rim_higher_ke_lower_value(self):
        """Higher Ke should yield lower per-share value"""
        rows = sensitivity_rim(
            book_value=100_000, roe_forecasts=[12.0, 11.0, 10.5],
            ke_base=10.0, shares=1_000_000,
            ke_range=[8.0, 10.0, 12.0], tg_range=[0.0],
        )
        vals = [r.value for r in rows]
        assert vals[0] > vals[1] > vals[2]

    def test_nav_grid_size(self):
        rows = sensitivity_nav(10_000, 4_000, 1_000_000, base_revaluation=1_000)
        assert len(rows) == 7 * 5  # default 7x5

    def test_nav_discount_reduces_value(self):
        """Higher discount rate reduces per_share"""
        rows = sensitivity_nav(
            10_000, 4_000, 1_000_000,
            reval_range=[0], discount_range=[0, 20, 40],
        )
        vals = [r.value for r in rows]
        assert vals[0] > vals[1] > vals[2]

    def test_multiple_range_grid_size(self):
        rows = sensitivity_multiple_range(
            metric_value=500_000, net_debt=100_000,
            shares=50_000_000, base_multiple=10.0,
        )
        assert len(rows) == 9 * 5  # default 9x5

    def test_multiple_range_higher_mult_higher_value(self):
        """Higher multiple yields higher per-share value"""
        rows = sensitivity_multiple_range(
            metric_value=500_000, net_debt=100_000,
            shares=50_000_000, base_multiple=10.0,
            mult_range=[8.0, 10.0, 12.0], discount_range=[0],
        )
        vals = [r.value for r in rows]
        assert vals[0] < vals[1] < vals[2]


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
        2023: {"op": 100, "dep": 20, "amort": 5},   # EBITDA=125
        2024: {"op": 130, "dep": 22, "amort": 5},   # EBITDA=157
        2025: {"op": 160, "dep": 25, "amort": 5},   # EBITDA=190
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
        assert rates[-1] == 0.03     # KR convergence rate

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
        code="Base", name="Base Case", prob=50, ipo="N/A", shares=1_000_000,
    )

    _DRIVERS = [
        NewsDriver(
            id="rate_hike", name="금리인상 50bp", category="macro",
            effects={"wacc_adj": 0.5, "growth_adj_pct": -10},
            rationale="한은 기준금리 인상",
        ),
        NewsDriver(
            id="tariff_shock", name="관세충격", category="trade",
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
        sc = self._BASE_SC.model_copy(update={
            "active_drivers": {"rate_hike": 1.0},
        })
        result = resolve_drivers(sc, self._DRIVERS)
        assert result.wacc_adj == 0.5
        assert result.growth_adj_pct == -10

    def test_single_driver_half_weight(self):
        """weight=0.5: half the effect applied."""
        sc = self._BASE_SC.model_copy(update={
            "active_drivers": {"rate_hike": 0.5},
        })
        result = resolve_drivers(sc, self._DRIVERS)
        assert result.wacc_adj == 0.25
        assert result.growth_adj_pct == -5.0

    def test_multi_driver_dampened(self):
        """Two drivers with correlation dampening: growth_adj_pct = (-10 + -15) * sqrt(2)/2 ≈ -17.68."""
        import math
        sc = self._BASE_SC.model_copy(update={
            "active_drivers": {"rate_hike": 1.0, "tariff_shock": 1.0},
        })
        result = resolve_drivers(sc, self._DRIVERS)
        assert result.wacc_adj == 0.5  # rate_hike only (single driver, no dampening)
        # growth_adj_pct: raw=-25, dampened by sqrt(2)/2
        expected = round(-25 * math.sqrt(2) / 2, 4)
        assert result.growth_adj_pct == expected
        assert result.market_sentiment_pct == -5  # tariff_shock only (single driver)

    def test_multi_driver_no_dampen(self):
        """With dampen=False, pure additive: growth_adj_pct = -10 + -15 = -25."""
        sc = self._BASE_SC.model_copy(update={
            "active_drivers": {"rate_hike": 1.0, "tariff_shock": 1.0},
        })
        result = resolve_drivers(sc, self._DRIVERS, dampen=False)
        assert result.growth_adj_pct == -25

    def test_unknown_driver_id_ignored(self):
        """Non-existent driver_id is ignored."""
        sc = self._BASE_SC.model_copy(update={
            "active_drivers": {"nonexistent": 1.0, "rate_hike": 1.0},
        })
        result = resolve_drivers(sc, self._DRIVERS)
        assert result.wacc_adj == 0.5  # only rate_hike applied

    def test_driver_rationale_generated(self):
        """driver_rationale auto-generated when active_drivers used."""
        sc = self._BASE_SC.model_copy(update={
            "active_drivers": {"rate_hike": 1.0, "tariff_shock": 1.0},
        })
        result = resolve_drivers(sc, self._DRIVERS)
        assert "금리인상 50bp" in result.driver_rationale["wacc_adj"]
        assert "관세충격" in result.driver_rationale["growth_adj_pct"]

    def test_no_drivers_list_with_active_drivers(self):
        """news_drivers=[] with active_drivers set: zero effect (no drivers)."""
        sc = self._BASE_SC.model_copy(update={
            "active_drivers": {"rate_hike": 1.0},
        })
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

        profile_path = str(Path(__file__).parent.parent / "profiles" / "kb_financial.yaml")
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
        assert bull_sc.segment_multiples["IC"] > base_sc.segment_multiples.get("IC", 0) if base_sc.segment_multiples else True

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
            base_alloc, {"AUTO": 8.0, "FSD": 15.0},
            segments_info={"AUTO": {"method": "ev_ebitda"}, "FSD": {"method": "ev_revenue"}},
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
            bull_alloc, {"AUTO": 8.0, "FSD": 15.0},
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
            alloc, {"A": 10.0},
            segments_info={"A": {"method": "ev_ebitda"}},
        )
        assert sotp["A"].method == "ev_ebitda"


class TestDistressDiscount:
    """Distress discount engine tests."""

    def test_healthy_company_no_discount(self):
        """Healthy financials should produce zero discount."""
        cons = {
            2025: {"de_ratio": 40.0, "net_income": 100000, "op": 80000,
                   "dep": 10000, "amort": 2000, "gross_borr": 50000},
            2024: {"de_ratio": 35.0, "net_income": 90000, "op": 70000,
                   "dep": 9000, "amort": 1800, "gross_borr": 45000},
        }
        d = calc_distress_discount(cons, 2025)
        assert d.discount == 0.0
        assert not d.applied

    def test_high_leverage_penalty(self):
        """D/E > 80% triggers leverage penalty."""
        cons = {
            2025: {"de_ratio": 120.0, "net_income": 50000, "op": 40000,
                   "dep": 5000, "amort": 0, "gross_borr": 30000},
        }
        d = calc_distress_discount(cons, 2025)
        assert d.de_penalty > 0
        assert d.loss_penalty == 0

    def test_consecutive_losses(self):
        """Two consecutive loss years trigger loss penalty."""
        cons = {
            2023: {"de_ratio": 50.0, "net_income": 10000, "op": 15000,
                   "dep": 3000, "amort": 0, "gross_borr": 20000},
            2024: {"de_ratio": 55.0, "net_income": -5000, "op": 2000,
                   "dep": 3000, "amort": 0, "gross_borr": 22000},
            2025: {"de_ratio": 60.0, "net_income": -8000, "op": -1000,
                   "dep": 3000, "amort": 0, "gross_borr": 25000},
        }
        d = calc_distress_discount(cons, 2025)
        assert d.loss_penalty == 0.10  # 2 consecutive losses

    def test_three_year_loss_streak(self):
        """Three consecutive losses get maximum loss penalty."""
        cons = {
            2023: {"de_ratio": 50.0, "net_income": -1000, "op": 0,
                   "dep": 1000, "amort": 0, "gross_borr": 10000},
            2024: {"de_ratio": 55.0, "net_income": -2000, "op": -500,
                   "dep": 1000, "amort": 0, "gross_borr": 12000},
            2025: {"de_ratio": 60.0, "net_income": -3000, "op": -1000,
                   "dep": 1000, "amort": 0, "gross_borr": 15000},
        }
        d = calc_distress_discount(cons, 2025)
        assert d.loss_penalty == 0.15

    def test_low_icr_penalty(self):
        """Low interest coverage triggers ICR penalty."""
        cons = {
            2025: {"de_ratio": 50.0, "net_income": 5000, "op": 8000,
                   "dep": 2000, "amort": 0, "gross_borr": 200000},
        }
        d = calc_distress_discount(cons, 2025)
        assert d.icr_penalty > 0

    def test_max_discount_cap(self):
        """Total discount is capped at max_discount."""
        cons = {
            2023: {"de_ratio": 250.0, "net_income": -50000, "op": -40000,
                   "dep": 1000, "amort": 0, "gross_borr": 500000},
            2024: {"de_ratio": 280.0, "net_income": -60000, "op": -45000,
                   "dep": 1000, "amort": 0, "gross_borr": 550000},
            2025: {"de_ratio": 300.0, "net_income": -70000, "op": -50000,
                   "dep": 1000, "amort": 0, "gross_borr": 600000},
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
            2024: {"de_ratio": 50.0, "net_income": 10000, "op": 15000,
                   "dep": 3000, "amort": 0, "gross_borr": 20000},
            2025: {"de_ratio": 55.0, "net_income": -5000, "op": 2000,
                   "dep": 3000, "amort": 0, "gross_borr": 22000},
        }
        d = calc_distress_discount(cons, 2025, industry="Automotive Parts")
        assert d.loss_penalty == 0.0  # 1-year exemption for cyclicals

    def test_cyclical_two_year_loss_still_penalized(self):
        """Cyclical industry with 2+ consecutive losses still gets penalty."""
        cons = {
            2024: {"de_ratio": 50.0, "net_income": -5000, "op": 2000,
                   "dep": 3000, "amort": 0, "gross_borr": 20000},
            2025: {"de_ratio": 55.0, "net_income": -8000, "op": -1000,
                   "dep": 3000, "amort": 0, "gross_borr": 22000},
        }
        d = calc_distress_discount(cons, 2025, industry="Semiconductor Equipment")
        assert d.loss_penalty == 0.10  # 2 consecutive → penalty applies

    def test_non_cyclical_single_loss_penalized(self):
        """Non-cyclical industry single-year loss still gets penalty."""
        cons = {
            2024: {"de_ratio": 50.0, "net_income": 10000, "op": 15000,
                   "dep": 3000, "amort": 0, "gross_borr": 20000},
            2025: {"de_ratio": 55.0, "net_income": -5000, "op": 2000,
                   "dep": 3000, "amort": 0, "gross_borr": 22000},
        }
        d = calc_distress_discount(cons, 2025, industry="Software & Services")
        assert d.loss_penalty == 0.05  # No cyclical exemption

    def test_exempt_segments_keep_original_multiples(self):
        """Exempt segments retain original multiples when discount applied."""
        multiples = {"AUTO": 10.0, "FSD": 15.0, "ENERGY": 8.0}
        result = apply_distress_discount(multiples, 0.20, exempt_segments={"FSD"})
        assert result["AUTO"] == 8.0   # 10.0 * 0.8
        assert result["FSD"] == 15.0   # exempt → original
        assert result["ENERGY"] == 6.4 # 8.0 * 0.8

    def test_custom_max_discount_cap(self):
        """Custom max_discount cap limits total discount."""
        cons = {
            2023: {"de_ratio": 250.0, "net_income": -50000, "op": -40000,
                   "dep": 1000, "amort": 0, "gross_borr": 500000},
            2024: {"de_ratio": 280.0, "net_income": -60000, "op": -45000,
                   "dep": 1000, "amort": 0, "gross_borr": 550000},
            2025: {"de_ratio": 300.0, "net_income": -70000, "op": -50000,
                   "dep": 1000, "amort": 0, "gross_borr": 600000},
        }
        d = calc_distress_discount(cons, 2025, max_discount=0.25)
        assert d.discount <= 0.25
