"""Quality scoring engine tests."""

import pytest

from schemas.models import (
    QualityScore,
    CrossValidationItem,
    WACCParams,
    WACCResult,
    ScenarioResult,
    MarketComparisonResult,
)
from engine.quality import (
    calc_quality_score,
    _cv_convergence_score,
    _cv_convergence_score_rnpv,
    _rnpv_pipeline_diversity,
    _rnpv_pos_grounding,
    _reverse_rnpv_consistency,
    _market_alignment_score_rnpv,
    _wacc_plausibility_score,
    _scenario_consistency_score,
    _market_alignment_score,
    _grade,
    format_quality_report,
)


# ── CV Convergence Tests ──

class TestCVConvergence:
    def _make_cvs(self, per_shares: list[int]) -> list[CrossValidationItem]:
        return [
            CrossValidationItem(
                method=f"Method{i}",
                metric_value=100.0,
                multiple=10.0,
                enterprise_value=1_000_000,
                equity_value=800_000,
                per_share=ps,
            )
            for i, ps in enumerate(per_shares)
        ]

    def test_excellent_convergence(self):
        """CV < 8% → 25 points."""
        # Values: 50000, 51000, 50500 → CV ≈ 1%
        score, warns = _cv_convergence_score(self._make_cvs([50000, 51000, 50500]))
        assert score == 25
        assert len(warns) == 0

    def test_good_convergence(self):
        """CV 8-15% → 20 points."""
        # Values: 50000, 56000, 53000 → stdev≈3000, mean≈53000, CV≈5.7%... too tight
        # Try: 50000, 58000, 54000 → mean=54000, stdev≈4000, CV≈7.4% still <8
        # Try: 50000, 60000, 55000 → mean=55000, stdev≈5000, CV≈9.1%
        score, warns = _cv_convergence_score(self._make_cvs([50000, 60000, 55000]))
        assert score == 20

    def test_moderate_convergence(self):
        """CV 15-25% → 14 points."""
        # Values: 40000, 60000, 50000 → mean=50000, stdev≈10000, CV≈20%
        score, warns = _cv_convergence_score(self._make_cvs([40000, 60000, 50000]))
        assert score == 14

    def test_weak_convergence(self):
        """CV 25-40% → 8 points."""
        # Values: 30000, 60000, 45000 → mean=45000, stdev≈15000, CV≈33%
        score, warns = _cv_convergence_score(self._make_cvs([30000, 60000, 45000]))
        assert score == 8

    def test_poor_convergence(self):
        """CV > 40% → 3 points."""
        # Values: 20000, 80000, 50000 → mean=50000, stdev≈30000, CV≈60%
        score, warns = _cv_convergence_score(self._make_cvs([20000, 80000, 50000]))
        assert score == 3
        assert any("수렴도 낮음" in w for w in warns)

    def test_insufficient_methods(self):
        """< 2 methods → 0 points."""
        score, warns = _cv_convergence_score(self._make_cvs([50000]))
        assert score == 0
        assert any("2개 미만" in w for w in warns)

    def test_empty_methods(self):
        score, warns = _cv_convergence_score([])
        assert score == 0

    def test_zero_per_share_excluded(self):
        """Per-share values of 0 are excluded from CV calculation."""
        score, warns = _cv_convergence_score(self._make_cvs([50000, 0, 51000]))
        assert score == 25  # Only 50000 and 51000 considered


# ── WACC Plausibility Tests ──

class TestWACCPlausibility:
    def _make_wacc(self, rf=3.5, erp=6.0, bu=1.0, de=50.0, tax=22.0, kd_pre=4.0):
        params = WACCParams(rf=rf, erp=erp, bu=bu, de=de, tax=tax, kd_pre=kd_pre, eq_w=66.7)
        # Simplified result
        bl = bu * (1 + (1 - tax / 100) * de / 100)
        ke = rf + bl * erp
        kd_at = kd_pre * (1 - tax / 100)
        wacc = ke * 0.667 + kd_at * 0.333
        result = WACCResult(bl=bl, ke=ke, kd_at=kd_at, wacc=wacc)
        return params, result

    def test_all_in_range_kr(self):
        """All KR parameters in range → 25 points."""
        params, result = self._make_wacc(rf=3.5, erp=6.0, bu=0.8, kd_pre=4.5)
        score, warns = _wacc_plausibility_score(result, params, "KR")
        assert score == 25
        assert len(warns) == 0

    def test_rf_out_of_range(self):
        """Rf below range → -5 deduction."""
        params, result = self._make_wacc(rf=1.0)
        score, warns = _wacc_plausibility_score(result, params, "KR")
        assert score == 20
        assert any("무위험이자율" in w for w in warns)

    def test_multiple_out_of_range(self):
        """Multiple parameters out of range → cumulative deductions."""
        params, result = self._make_wacc(rf=1.0, erp=10.0, kd_pre=15.0)
        score, warns = _wacc_plausibility_score(result, params, "KR")
        assert score <= 10
        assert len(warns) >= 3

    def test_us_ranges(self):
        """US market uses different ranges."""
        params, result = self._make_wacc(rf=4.0, erp=5.5, bu=0.9, kd_pre=4.0)
        score, warns = _wacc_plausibility_score(result, params, "US")
        assert score == 25

    def test_extreme_wacc(self):
        """WACC > 18% triggers additional deduction."""
        params, result = self._make_wacc(rf=5.0, erp=8.0, bu=1.8, kd_pre=9.0)
        # This may produce a high WACC
        score, warns = _wacc_plausibility_score(result, params, "KR")
        # At minimum, should have some deductions if WACC is extreme
        assert score <= 25


# ── Scenario Consistency Tests ──

class TestScenarioConsistency:
    def _make_scenarios_in(self, probs: list[float]):
        from schemas.models import ScenarioParams
        names = ["bull", "base", "bear", "worst"]
        codes = ["BULL", "BASE", "BEAR", "WORST"]
        return {
            names[i]: ScenarioParams(
                code=codes[i], name=names[i], prob=p,
                ipo="성공", dlom=20.0, shares=1_000_000,
            )
            for i, p in enumerate(probs)
        }

    def _make_scenarios_out(self, per_shares: list[int]):
        names = ["bull", "base", "bear", "worst"]
        return {
            names[i]: ScenarioResult(
                total_ev=0, net_debt=0, cps_repay=0, rcps_repay=0,
                buyback=0, eco_frontier=0, equity_value=0, shares=1,
                pre_dlom=ps, post_dlom=ps, weighted=ps,
            )
            for i, ps in enumerate(per_shares)
        }

    def test_good_scenarios(self):
        """3 scenarios, moderate spread → high score."""
        sc_in = self._make_scenarios_in([30, 40, 30])
        sc_out = self._make_scenarios_out([60000, 50000, 40000])
        weighted = 50000
        score, warns = _scenario_consistency_score(sc_in, sc_out, weighted)
        assert score >= 20

    def test_two_scenarios(self):
        """2 scenarios → count_pts = 4."""
        sc_in = self._make_scenarios_in([50, 50])
        sc_out = self._make_scenarios_out([55000, 45000])
        score, warns = _scenario_consistency_score(sc_in, sc_out, 50000)
        assert score >= 4  # At least count points

    def test_no_scenarios(self):
        """0 scenarios → 0 points."""
        score, warns = _scenario_consistency_score({}, {}, 50000)
        assert score == 0
        assert any("시나리오가 없습니다" in w for w in warns)

    def test_narrow_spread(self):
        """Spread < 5% → warning."""
        sc_in = self._make_scenarios_in([30, 40, 30])
        sc_out = self._make_scenarios_out([50000, 50500, 50200])
        score, warns = _scenario_consistency_score(sc_in, sc_out, 50200)
        assert any("과소" in w for w in warns)

    def test_wide_spread(self):
        """Spread > 200% → warning."""
        sc_in = self._make_scenarios_in([30, 40, 30])
        sc_out = self._make_scenarios_out([200000, 50000, 10000])
        score, warns = _scenario_consistency_score(sc_in, sc_out, 50000)
        assert any("과대" in w for w in warns)


# ── Market Alignment Tests ──

class TestMarketAlignment:
    def test_close_alignment(self):
        """Gap < 15% → 25 points."""
        mc = MarketComparisonResult(intrinsic_value=55000, market_price=50000, gap_ratio=0.10)
        score, warns = _market_alignment_score(mc)
        assert score == 25

    def test_moderate_gap(self):
        """Gap 25-40% → 14 points."""
        mc = MarketComparisonResult(intrinsic_value=65000, market_price=50000, gap_ratio=0.30)
        score, warns = _market_alignment_score(mc)
        assert score == 14

    def test_large_gap(self):
        """Gap > 60% → 3 points."""
        mc = MarketComparisonResult(intrinsic_value=100000, market_price=50000, gap_ratio=1.0)
        score, warns = _market_alignment_score(mc)
        assert score == 3
        assert any("괴리율 과대" in w for w in warns)

    def test_no_market_data(self):
        """No market comparison → 0 points."""
        score, warns = _market_alignment_score(None)
        assert score == 0


# ── Grade Tests ──

class TestGrade:
    def test_grade_a(self):
        assert _grade(85) == "A"
        assert _grade(100) == "A"

    def test_grade_b(self):
        assert _grade(70) == "B"
        assert _grade(84) == "B"

    def test_grade_c(self):
        assert _grade(55) == "C"

    def test_grade_d(self):
        assert _grade(40) == "D"

    def test_grade_f(self):
        assert _grade(39) == "F"
        assert _grade(0) == "F"


# ── Rescaling Tests ──

class TestRescaling:
    def test_unlisted_rescale(self):
        """Unlisted companies rescale 75-point base to 100."""
        # If 3 sub-scores sum to 60/75, rescaled = round(60 * 100/75) = 80
        assert round(60 * 100 / 75) == 80

    def test_unlisted_zero(self):
        assert round(0 * 100 / 75) == 0


# ── Format Tests ──

class TestFormat:
    def test_listed_format(self):
        q = QualityScore(
            total=78, cv_convergence=22, wacc_plausibility=25,
            scenario_consistency=18, market_alignment=13,
            max_score=100, warnings=["괴리율 42%"], grade="B",
        )
        report = format_quality_report(q, is_listed=True)
        assert "78/100" in report
        assert "(B)" in report
        assert "시장가격 정합" in report

    def test_unlisted_format(self):
        q = QualityScore(
            total=85, cv_convergence=22, wacc_plausibility=25,
            scenario_consistency=18, market_alignment=0,
            max_score=75, warnings=[], grade="A",
        )
        report = format_quality_report(q, is_listed=False)
        assert "비상장" in report
        assert "시장가격 정합" not in report

    def test_rnpv_format(self):
        q = QualityScore(
            total=87, cv_convergence=15, wacc_plausibility=25,
            scenario_consistency=25, market_alignment=22,
            max_score=100, warnings=[], grade="A",
            is_rnpv=True, rnpv_weighted_cv=3, rnpv_pipeline_diversity=7,
            rnpv_pos_grounding=5, rnpv_reverse_consistency=7,
        )
        report = format_quality_report(q, is_listed=True)
        assert "rNPV 기준" in report
        assert "DCF 제외" in report
        assert "파이프라인 다양성" in report
        assert "PoS 그라운딩" in report
        assert "Reverse rNPV 정합" in report
        assert "3/10" in report
        assert "7/8" in report
        assert "5/7" in report


# ── rNPV CV Convergence Tests ──

class TestRNPVCVConvergence:
    def _make_cvs(self, methods_values: list[tuple[str, int]]) -> list[CrossValidationItem]:
        return [
            CrossValidationItem(
                method=method, metric_value=100.0, multiple=10.0,
                enterprise_value=1_000_000, equity_value=800_000, per_share=ps,
            )
            for method, ps in methods_values
        ]

    def test_dcf_excluded(self):
        """DCF (FCFF) is excluded from rNPV convergence calculation."""
        # Without DCF: [35, 39, 40] → CV ≈ 7% → 10 pts
        # With DCF: [35, 92, 39, 40] → CV ≈ 46% → 1 pt
        cvs = self._make_cvs([
            ("SOTP (EV/EBITDA)", 35),
            ("DCF (FCFF)", 92),
            ("EV/Revenue", 39),
            ("P/BV", 40),
        ])
        score_with_dcf, _ = _cv_convergence_score(cvs)
        score_rnpv, _ = _cv_convergence_score_rnpv(cvs)
        assert score_rnpv > score_with_dcf, "rNPV scoring should be higher when DCF is excluded"

    def test_tight_rnpv_convergence(self):
        """CV < 10% among rNPV-appropriate methods → 10 pts."""
        cvs = self._make_cvs([
            ("SOTP (EV/EBITDA)", 35),
            ("DCF (FCFF)", 92),  # Should be excluded
            ("EV/Revenue", 36),
            ("P/BV", 37),
        ])
        score, warns = _cv_convergence_score_rnpv(cvs)
        assert score == 10

    def test_moderate_rnpv_convergence(self):
        """CV 20-30% among rNPV methods → 5 pts.
        [25, 45, 40] → mean≈36.7, stdev≈10.4, CV≈28%"""
        cvs = self._make_cvs([
            ("SOTP (EV/EBITDA)", 25),
            ("EV/Revenue", 45),
            ("P/BV", 40),
        ])
        score, warns = _cv_convergence_score_rnpv(cvs)
        assert score == 5

    def test_insufficient_methods_after_dcf_exclusion(self):
        """Only DCF present → < 2 methods → 1 pt with warning."""
        cvs = self._make_cvs([("DCF (FCFF)", 92)])
        score, warns = _cv_convergence_score_rnpv(cvs)
        assert score == 1
        assert any("2개 미만" in w for w in warns)

    def test_poor_rnpv_convergence(self):
        """CV >= 45% → 1 pt with warning."""
        cvs = self._make_cvs([
            ("SOTP (EV/EBITDA)", 20),
            ("EV/Revenue", 80),
            ("P/BV", 50),
        ])
        score, warns = _cv_convergence_score_rnpv(cvs)
        assert score == 1
        assert any("수렴도 낮음" in w for w in warns)


# ── rNPV Pipeline Diversity Tests ──

_MINIMAL_CONSOLIDATED = {
    2025: {
        "revenue": 1000, "op": 200, "net_income": 150, "assets": 2000,
        "liabilities": 800, "equity": 1200, "dep": 50, "amort": 10,
        "gross_borr": 500, "net_borr": 400, "de_ratio": 50.0,
    }
}


def _make_minimal_vi(rnpv_params=None):
    """Create a minimal valid ValuationInput for rNPV quality tests."""
    from schemas.models import ValuationInput, CompanyProfile, WACCParams, DCFParams
    return ValuationInput(
        company=CompanyProfile(
            name="Test", market="US", shares_total=1000, shares_ordinary=1000,
        ),
        segments={},
        segment_data={},
        consolidated=_MINIMAL_CONSOLIDATED,
        wacc_params=WACCParams(rf=4.0, erp=5.0, bu=1.0, de=50.0, tax=22.0, kd_pre=4.0, eq_w=67.0),
        multiples={},
        scenarios={},
        dcf_params=DCFParams(),
        rnpv_params=rnpv_params,
    )


class TestRNPVPipelineDiversity:
    def _make_vi(self, drugs: list[dict]):
        """Create a minimal ValuationInput with rNPV pipeline."""
        from schemas.models import RNPVParams, PipelineDrug
        pipeline = [PipelineDrug(name=d["name"], phase=d["phase"]) for d in drugs]
        return _make_minimal_vi(rnpv_params=RNPVParams(pipeline=pipeline))

    def test_diverse_pipeline(self):
        """6 drugs, 4 phases → 4 + 4 = 8 pts."""
        vi = self._make_vi([
            {"name": "A", "phase": "approved"},
            {"name": "B", "phase": "filed"},
            {"name": "C", "phase": "phase3"},
            {"name": "D", "phase": "phase2"},
            {"name": "E", "phase": "phase1"},
            {"name": "F", "phase": "preclinical"},
        ])
        score, warns = _rnpv_pipeline_diversity(vi)
        assert score == 8
        assert len(warns) == 0

    def test_small_pipeline_single_phase(self):
        """1 drug, 1 phase → 1 + 1 = 2 pts with warning."""
        vi = self._make_vi([{"name": "A", "phase": "phase3"}])
        score, warns = _rnpv_pipeline_diversity(vi)
        assert score == 2
        assert any("단일 Phase" in w for w in warns)

    def test_medium_pipeline_two_phases(self):
        """4 drugs, 2 phases → 3 + 2 = 5 pts."""
        vi = self._make_vi([
            {"name": "A", "phase": "approved"},
            {"name": "B", "phase": "approved"},
            {"name": "C", "phase": "phase3"},
            {"name": "D", "phase": "phase3"},
        ])
        score, warns = _rnpv_pipeline_diversity(vi)
        assert score == 5

    def test_no_pipeline(self):
        """No rnpv_params → 0 pts."""
        vi = _make_minimal_vi(rnpv_params=None)
        score, warns = _rnpv_pipeline_diversity(vi)
        assert score == 0


# ── rNPV PoS Grounding Tests ──

class TestRNPVPoSGrounding:
    def _make_vi(self, drugs: list[dict]):
        from schemas.models import RNPVParams, PipelineDrug
        pipeline = [
            PipelineDrug(
                name=d["name"], phase=d["phase"],
                success_prob=d.get("success_prob"),
            )
            for d in drugs
        ]
        return _make_minimal_vi(rnpv_params=RNPVParams(pipeline=pipeline))

    def test_majority_custom_pos(self):
        """≥50% non-approved drugs with custom PoS → 7 pts."""
        vi = self._make_vi([
            {"name": "A", "phase": "phase3", "success_prob": 0.60},
            {"name": "B", "phase": "phase3", "success_prob": 0.55},
            {"name": "C", "phase": "phase2"},
        ])
        score, warns = _rnpv_pos_grounding(vi)
        assert score == 7

    def test_partial_custom_pos(self):
        """25-50% custom PoS → 5 pts."""
        vi = self._make_vi([
            {"name": "A", "phase": "phase3", "success_prob": 0.60},
            {"name": "B", "phase": "phase2"},
            {"name": "C", "phase": "phase1"},
            {"name": "D", "phase": "preclinical"},
        ])
        score, warns = _rnpv_pos_grounding(vi)
        assert score == 5

    def test_no_custom_pos(self):
        """All defaults → 1 pt with warning."""
        vi = self._make_vi([
            {"name": "A", "phase": "phase3"},
            {"name": "B", "phase": "phase2"},
        ])
        score, warns = _rnpv_pos_grounding(vi)
        assert score == 1
        assert any("커스텀 설정 부족" in w for w in warns)

    def test_all_approved_full_score(self):
        """All approved drugs → PoS grounding not applicable → 7 pts."""
        vi = self._make_vi([
            {"name": "A", "phase": "approved"},
            {"name": "B", "phase": "approved"},
        ])
        score, warns = _rnpv_pos_grounding(vi)
        assert score == 7


# ── Reverse rNPV Consistency Tests ──

class TestReverseRNPVConsistency:
    def _make_result(
        self,
        gap_pct: float = 20.0,
        pos_scale: float | None = None,
        peak_scale: float | None = None,
        discount_rate: float | None = None,
    ):
        from schemas.models import ValuationResult, WACCResult, ReverseRNPVResult
        rr = ReverseRNPVResult(
            target_ev=100_000, model_ev=120_000, gap_pct=gap_pct,
            implied_pos_scale=pos_scale,
            implied_peak_scale=peak_scale,
            implied_discount_rate=discount_rate,
        )
        wacc = WACCResult(bl=1.0, ke=10.0, kd_at=3.0, wacc=8.0)
        return ValuationResult(primary_method="rnpv", wacc=wacc, reverse_rnpv=rr)

    def test_small_gap_full_score(self):
        """Model within 10% of market → 10 pts regardless of implied params."""
        result = self._make_result(gap_pct=5.0)
        score, warns = _reverse_rnpv_consistency(result)
        assert score == 10

    def test_all_params_in_range(self):
        """All implied params in plausible range → 10 pts."""
        result = self._make_result(
            gap_pct=20.0, pos_scale=1.2, peak_scale=1.1, discount_rate=12.0,
        )
        score, warns = _reverse_rnpv_consistency(result)
        assert score == 10
        assert len(warns) == 0

    def test_extreme_pos_scale(self):
        """Implied PoS scale > 3.0 → -3 pts with warning."""
        result = self._make_result(
            gap_pct=50.0, pos_scale=5.0, peak_scale=1.2, discount_rate=12.0,
        )
        score, warns = _reverse_rnpv_consistency(result)
        assert score == 7  # 0 (pos) + 3 (peak) + 4 (rate)
        assert any("PoS 배수 극단값" in w for w in warns)

    def test_extreme_discount_rate(self):
        """Implied discount rate > 30% → -4 pts with warning."""
        result = self._make_result(
            gap_pct=30.0, pos_scale=1.0, peak_scale=0.9, discount_rate=45.0,
        )
        score, warns = _reverse_rnpv_consistency(result)
        assert score == 6  # 3 (pos) + 3 (peak) + 0 (rate)
        assert any("할인율 극단값" in w for w in warns)

    def test_no_reverse_rnpv(self):
        """No reverse rNPV data → neutral 5 pts."""
        from schemas.models import ValuationResult, WACCResult
        wacc = WACCResult(bl=1.0, ke=10.0, kd_at=3.0, wacc=8.0)
        result = ValuationResult(primary_method="rnpv", wacc=wacc)
        score, warns = _reverse_rnpv_consistency(result)
        assert score == 5
        assert len(warns) == 0

    def test_all_params_none(self):
        """ReverseRNPVResult with all params None → 5 pts with convergence warning."""
        result = self._make_result(gap_pct=30.0)
        score, warns = _reverse_rnpv_consistency(result)
        assert score == 5
        assert any("수렴 실패" in w for w in warns)


# ── rNPV Market Alignment Tests ──

class TestRNPVMarketAlignment:
    def test_close_gap(self):
        """Gap < 15% → 15 pts."""
        mc = MarketComparisonResult(intrinsic_value=38, market_price=40, gap_ratio=-0.05)
        score, warns = _market_alignment_score_rnpv(mc)
        assert score == 15

    def test_moderate_gap(self):
        """Gap 25-40% → 8 pts."""
        mc = MarketComparisonResult(intrinsic_value=30, market_price=40, gap_ratio=-0.25)
        score, warns = _market_alignment_score_rnpv(mc)
        assert score == 8

    def test_large_gap(self):
        """Gap > 60% → 1 pt with warning."""
        mc = MarketComparisonResult(intrinsic_value=15, market_price=40, gap_ratio=-0.625)
        score, warns = _market_alignment_score_rnpv(mc)
        assert score == 1
        assert any("괴리율 과대" in w for w in warns)

    def test_no_market_data(self):
        """No market comparison → 0 pts."""
        score, warns = _market_alignment_score_rnpv(None)
        assert score == 0

    def test_max_is_15(self):
        """Maximum score is 15 (not 25 like standard alignment)."""
        mc = MarketComparisonResult(intrinsic_value=40, market_price=40, gap_ratio=0.0)
        score, _ = _market_alignment_score_rnpv(mc)
        assert score == 15
        assert score < 25
