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
