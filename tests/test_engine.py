"""Engine regression & unit tests."""

import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas.models import WACCParams, ScenarioParams, DCFParams
from engine.wacc import calc_wacc
from engine.sotp import allocate_da, calc_sotp
from engine.dcf import calc_dcf
from engine.scenario import calc_scenario
from engine.sensitivity import sensitivity_multiples, sensitivity_irr_dlom, sensitivity_dcf
from engine.multiples import cross_validate, calc_ev_revenue, calc_pe, calc_pbv
from engine.peer_analysis import calc_peer_stats
from engine.monte_carlo import MCInput, run_monte_carlo
from engine.units import detect_unit, per_share
from engine.method_selector import suggest_method
from engine.ddm import calc_ddm
from engine.market_comparison import compare_to_market


# ── SK에코플랜트 기준 데이터 ──

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
        assert per_share(-100, 1_000_000, 50_000_000) == 0

    def test_per_share_억원_unit(self):
        """억원 단위: 1억원 equity, 1000만주"""
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


# ═══════════════════════════════════════════════════════════
# DDM Tests
# ═══════════════════════════════════════════════════════════

class TestDDM:
    def test_basic_ddm(self):
        r = calc_ddm(dps=1000, growth=3.0, ke=10.0)
        # DPS * (1.03) / (0.10 - 0.03) = 1030 / 0.07 = 14,714
        assert r.equity_per_share == 14_714

    def test_ddm_growth_equals_ke(self):
        """ke <= growth → ValueError"""
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

    def test_negative_ebitda_zero_ev(self):
        alloc = allocate_da({"A": {"op": -100, "assets": 100}}, 50)
        sotp, ev = calc_sotp(alloc, {"A": 10.0})
        assert sotp["A"].ev == 0
        assert ev == 0


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
        r = calc_scenario(sc, ev, SK_NET_DEBT, SK_ECO_FRONTIER, SK_CPS_PRINCIPAL, SK_CPS_YEARS)
        assert r.post_dlom > 0
        assert r.pre_dlom == r.post_dlom  # DLOM=0

    def test_sk_scenario_b(self):
        ev = self._get_sk_ev()
        sc = ScenarioParams(
            code="B", name="FI 우호", prob=45, ipo="불발", irr=5.0,
            dlom=20, rcps_repay=490_000, buyback=200_000,
            shares=SK_SHARES_ORDINARY,
        )
        r = calc_scenario(sc, ev, SK_NET_DEBT, SK_ECO_FRONTIER, SK_CPS_PRINCIPAL, SK_CPS_YEARS)
        assert r.post_dlom > 0
        assert r.post_dlom < r.pre_dlom  # DLOM 적용

    def test_scenario_with_different_unit_multiplier(self):
        """억원 단위에서 주당가치가 올바른지"""
        sc = ScenarioParams(
            code="A", name="Test", prob=100, ipo="N/A",
            dlom=0, shares=10_000_000,
        )
        r = calc_scenario(sc, 100, 0, 0, 0, 0, unit_multiplier=100_000_000)
        # 100억원 equity / 1000만주 = 1,000원/주
        assert r.pre_dlom == 1_000

    def test_negative_equity(self):
        sc = ScenarioParams(
            code="A", name="Neg", prob=100, ipo="N/A",
            dlom=0, shares=10_000,
        )
        r = calc_scenario(sc, 100, 200, 0, 0, 0)
        assert r.equity_value < 0
        assert r.pre_dlom == 0
        assert r.post_dlom == 0


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
        """row_seg/col_seg 미지정 → 자동 선택"""
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

class TestFullPipeline:
    def test_sk_ecoplant_profile(self):
        """End-to-end: YAML 로드 → SOTP 밸류에이션 → 유효한 결과"""
        from valuation_runner import load_profile, run_valuation

        profile_path = str(Path(__file__).parent.parent / "profiles" / "sk_ecoplant.yaml")
        vi = load_profile(profile_path)
        result = run_valuation(vi)

        # 구조적 검증 (고정 값 대신)
        assert result.primary_method == "sotp"
        assert result.wacc.wacc == 8.50
        assert 6_300_000 < result.total_ev < 6_400_000
        assert result.weighted_value > 0
        assert len(result.cross_validations) >= 2
        assert result.dcf is not None
        assert result.dcf.ev_dcf > 0

    def test_sk_ecoplant_mc(self):
        """SK에코플랜트 Monte Carlo 통합"""
        from valuation_runner import load_profile, run_valuation

        profile_path = str(Path(__file__).parent.parent / "profiles" / "sk_ecoplant.yaml")
        vi = load_profile(profile_path)
        result = run_valuation(vi)

        assert result.monte_carlo is not None
        mc = result.monte_carlo
        assert mc.n_sims == 10_000
        assert mc.p5 < mc.median < mc.p95
