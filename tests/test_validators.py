"""AI output validator tests."""

import pytest

from ai.validators import (
    validate_peers,
    validate_wacc,
    validate_scenarios,
    validate_scenario_draft,
    validate_news_drivers,
)


# ── Peer Validation Tests ──

class TestValidatePeers:
    def test_valid_peers_pass_through(self):
        """All-valid peers pass through unchanged."""
        data = {
            "segments": {
                "HI": {
                    "peers": [
                        {"name": "Peer A", "ev_ebitda": 8.0},
                        {"name": "Peer B", "ev_ebitda": 12.0},
                        {"name": "Peer C", "ev_ebitda": 6.5},
                    ],
                    "recommended_multiple": 8.5,
                }
            }
        }
        result, warns = validate_peers(data, "KR")
        assert len(result["segments"]["HI"]["peers"]) == 3
        assert len(warns) == 0

    def test_negative_ev_ebitda_excluded(self):
        """Negative EV/EBITDA peers are EXCLUDED, not clamped."""
        data = {
            "segments": {
                "MAIN": {
                    "peers": [
                        {"name": "Good Co", "ev_ebitda": 10.0},
                        {"name": "Loss Co", "ev_ebitda": -5.0},
                        {"name": "OK Co", "ev_ebitda": 8.0},
                    ]
                }
            }
        }
        result, warns = validate_peers(data, "KR")
        peers = result["segments"]["MAIN"]["peers"]
        assert len(peers) == 2
        assert all(p["name"] != "Loss Co" for p in peers)
        assert any("음수" in w and "Loss Co" in w for w in warns)

    def test_extreme_multiple_excluded(self):
        """EV/EBITDA outside [0.5, 50] excluded."""
        data = {
            "peers": [
                {"name": "Normal", "ev_ebitda": 10.0},
                {"name": "Extreme", "ev_ebitda": 80.0},
                {"name": "Tiny", "ev_ebitda": 0.1},
            ]
        }
        result, warns = validate_peers(data)
        assert len(result["peers"]) == 1
        assert result["peers"][0]["name"] == "Normal"

    def test_insufficient_peers_warning(self):
        """< 2 valid peers triggers warning."""
        data = {"peers": [{"name": "Solo", "ev_ebitda": 10.0}]}
        result, warns = validate_peers(data)
        assert any("부족" in w for w in warns)

    def test_null_ev_ebitda_excluded_with_warning(self):
        """W-10: Null EV/EBITDA peers excluded with explicit warning (not silent)."""
        data = {
            "segments": {
                "A": {
                    "peers": [
                        {"name": "Null Co", "ev_ebitda": None},
                        {"name": "Good Co", "ev_ebitda": 10.0},
                        {"name": "OK Co", "ev_ebitda": 8.0},
                    ]
                }
            }
        }
        result, warns = validate_peers(data, "KR")
        assert len(result["segments"]["A"]["peers"]) == 2
        assert any("Null Co" in w and "파싱 에러" in w for w in warns)

    def test_flat_null_ev_warning(self):
        """W-10: Flat format null EV/EBITDA also warns."""
        data = {
            "peers": [
                {"name": "A", "ev_ebitda": None},
                {"name": "B", "ev_ebitda": 10.0},
                {"name": "C", "ev_ebitda": 8.0},
            ]
        }
        result, warns = validate_peers(data)
        assert len(result["peers"]) == 2
        assert any("파싱 에러" in w for w in warns)


# ── WACC Validation Tests ──

class TestValidateWACC:
    def test_all_in_range(self):
        """All parameters in range → no clamping, no warnings."""
        data = {"rf": 3.5, "erp": 6.0, "bu": 1.0, "kd_pre": 4.5}
        result, warns = validate_wacc(data, "KR")
        assert result == data  # Unchanged
        assert len(warns) == 0

    def test_beta_clamped_high(self):
        """Beta > 2.0 clamped to 2.0."""
        data = {"rf": 3.5, "erp": 6.0, "bu": 5.0, "kd_pre": 4.5}
        result, warns = validate_wacc(data, "KR")
        assert result["bu"] == 2.0
        assert any("Unlevered Beta" in w and "상한" in w for w in warns)

    def test_rf_clamped_low(self):
        """Rf below KR range (2.5%) clamped."""
        data = {"rf": 0.5, "erp": 6.0, "bu": 1.0, "kd_pre": 4.5}
        result, warns = validate_wacc(data, "KR")
        assert result["rf"] == 2.5
        assert any("무위험이자율" in w for w in warns)

    def test_us_ranges_different(self):
        """US ranges are different from KR."""
        data = {"rf": 2.5, "erp": 5.0, "bu": 1.0, "kd_pre": 4.0}
        result, warns = validate_wacc(data, "US")
        assert result["rf"] == 3.0  # Clamped to US lower bound
        assert any("무위험이자율" in w for w in warns)

    def test_missing_key_ignored(self):
        """Missing keys don't cause errors."""
        data = {"rf": 3.5}
        result, warns = validate_wacc(data, "KR")
        assert result["rf"] == 3.5
        assert len(warns) == 0

    def test_original_not_mutated(self):
        """Original data is not mutated (deepcopy)."""
        data = {"rf": 0.5, "erp": 6.0, "bu": 1.0, "kd_pre": 4.5}
        result, warns = validate_wacc(data, "KR")
        assert data["rf"] == 0.5
        assert result["rf"] == 2.5


# ── Scenario Validation Tests ──

class TestValidateScenarios:
    def test_valid_scenarios_dict(self):
        """Valid 3-scenario dict passes through."""
        data = {
            "bull": {"prob": 30, "dlom": 20},
            "base": {"prob": 40, "dlom": 20, "name": "Base Case"},
            "bear": {"prob": 30, "dlom": 20},
        }
        result, warns = validate_scenarios(data)
        total = sum(v["prob"] for v in result.values() if isinstance(v, dict))
        assert abs(total - 100) < 0.01

    def test_valid_scenarios_list(self):
        """List format (prompt output) works correctly."""
        data = [
            {"code": "Bull", "name": "Bull Case", "prob": 30, "dlom": 0},
            {"code": "Base", "name": "Base Case", "prob": 40, "dlom": 0},
            {"code": "Bear", "name": "Bear Case", "prob": 30, "dlom": 0},
        ]
        result, warns = validate_scenarios(data)
        assert isinstance(result, list)
        total = sum(s["prob"] for s in result)
        assert abs(total - 100) < 0.01

    def test_rounding_tolerance_silent(self):
        """Probability sum 99.5% → normalized silently (within 98-102%)."""
        data = {
            "bull": {"prob": 29.5, "dlom": 20},
            "base": {"prob": 40.0, "dlom": 20, "name": "Base Case"},
            "bear": {"prob": 30.0, "dlom": 20},
        }
        result, warns = validate_scenarios(data)
        total = sum(v["prob"] for v in result.values() if isinstance(v, dict))
        assert abs(total - 100) < 0.01
        assert not any("비정상" in w for w in warns)

    def test_large_deviation_warns(self):
        """Probability sum 85% → normalized with warning."""
        data = {
            "bull": {"prob": 25, "dlom": 20},
            "base": {"prob": 35, "dlom": 20, "name": "Base Case"},
            "bear": {"prob": 25, "dlom": 20},
        }
        result, warns = validate_scenarios(data)
        total = sum(v["prob"] for v in result.values() if isinstance(v, dict))
        assert abs(total - 100) < 0.01
        assert any("비정상" in w for w in warns)

    def test_dominant_scenario_warned(self):
        """Single scenario > 60% → warning (threshold lowered from 70%)."""
        data = {
            "bull": {"code": "bull", "prob": 10, "dlom": 20},
            "base": {"code": "base", "prob": 80, "dlom": 20, "name": "Base Case"},
            "bear": {"code": "bear", "prob": 10, "dlom": 20},
        }
        result, warns = validate_scenarios(data)
        assert any("과대" in w for w in warns)

    def test_base_case_prob_out_of_range_warned(self):
        """Base Case probability outside 30-50% → warning."""
        data = [
            {"code": "Bull", "name": "Bull Case", "prob": 40, "dlom": 0},
            {"code": "Base", "name": "Base Case", "prob": 20, "dlom": 0},
            {"code": "Bear", "name": "Bear Case", "prob": 40, "dlom": 0},
        ]
        result, warns = validate_scenarios(data)
        assert any("Base Case 확률" in w for w in warns)

    def test_negative_dlom_clamped(self):
        """Negative DLOM → clamped to 0%."""
        data = {
            "bull": {"code": "bull", "prob": 50, "dlom": -5},
            "bear": {"code": "bear", "prob": 50, "dlom": 20},
        }
        result, warns = validate_scenarios(data)
        assert result["bull"]["dlom"] == 0
        assert any("음수" in w for w in warns)

    def test_excessive_dlom_warned(self):
        """DLOM > 40% → warning (not clamped)."""
        data = {
            "bull": {"code": "bull", "prob": 50, "dlom": 50},
            "bear": {"code": "bear", "prob": 50, "dlom": 20},
        }
        result, warns = validate_scenarios(data)
        assert result["bull"]["dlom"] == 50
        assert any("DLOM 과대" in w for w in warns)

    def test_single_scenario_warned(self):
        """< 2 scenarios → warning."""
        data = {"base": {"prob": 100, "dlom": 20}}
        result, warns = validate_scenarios(data)
        assert any("부족" in w for w in warns)

    def test_empty_scenarios(self):
        """Empty → warning, no crash."""
        result, warns = validate_scenarios({})
        assert any("부족" in w for w in warns)

    def test_empty_list_scenarios(self):
        """Empty list → warning, no crash."""
        result, warns = validate_scenarios([])
        assert any("부족" in w for w in warns)

    def test_driver_range_clamped(self):
        """Driver values outside allowed ranges are clamped."""
        data = [
            {"code": "Bull", "prob": 50, "dlom": 0, "drivers": {"growth_adj_pct": 200}},
            {"code": "Bear", "prob": 50, "dlom": 0, "drivers": {"growth_adj_pct": -10}},
        ]
        result, warns = validate_scenarios(data)
        assert result[0]["drivers"]["growth_adj_pct"] == 100  # clamped to max
        assert any("범위 이탈" in w for w in warns)

    def test_identical_drivers_warned(self):
        """All scenarios with same drivers → differentiation warning."""
        data = [
            {"code": "Bull", "prob": 50, "dlom": 0, "drivers": {"growth_adj_pct": 0}},
            {"code": "Bear", "prob": 50, "dlom": 0, "drivers": {"growth_adj_pct": 0}},
        ]
        result, warns = validate_scenarios(data)
        assert any("분화 부족" in w for w in warns)

    def test_combined_extreme_warned(self):
        """Extreme combined wacc+growth effect → sanity warning."""
        data = [
            {"code": "Bear", "prob": 50, "dlom": 0,
             "drivers": {"wacc_adj": 2.5, "growth_adj_pct": -40}},
            {"code": "Base", "prob": 50, "dlom": 0, "drivers": {}},
        ]
        result, warns = validate_scenarios(data)
        assert any("극단적 복합" in w for w in warns)


# ── Scenario Draft Validation Tests (Two-Pass Pass 1) ──

class TestValidateScenarioDraft:
    def test_valid_draft(self):
        """Well-formed draft passes with no warnings."""
        draft = {
            "scenario_draft": [
                {"code": "Bull", "name": "Bull Case", "prob_range": [25, 35],
                 "driver_directions": {"growth_adj_pct": "up"}},
                {"code": "Base", "name": "Base Case", "prob_range": [35, 45],
                 "driver_directions": {"growth_adj_pct": "flat"}},
                {"code": "Bear", "name": "Bear Case", "prob_range": [20, 30],
                 "driver_directions": {"growth_adj_pct": "down"}},
            ]
        }
        result, warns = validate_scenario_draft(draft)
        assert len(warns) == 0
        assert len(result["scenario_draft"]) == 3

    def test_insufficient_scenarios(self):
        """< 2 scenarios → warning."""
        draft = {
            "scenario_draft": [
                {"code": "Base", "name": "Base Case", "prob_range": [40, 50],
                 "driver_directions": {}},
            ]
        }
        result, warns = validate_scenario_draft(draft)
        assert any("부족" in w for w in warns)

    def test_prob_range_reversed(self):
        """Reversed prob_range → swapped with warning."""
        draft = {
            "scenario_draft": [
                {"code": "Bull", "prob_range": [35, 25],
                 "driver_directions": {"growth_adj_pct": "up"}},
                {"code": "Base", "name": "Base Case", "prob_range": [35, 45],
                 "driver_directions": {}},
            ]
        }
        result, warns = validate_scenario_draft(draft)
        assert result["scenario_draft"][0]["prob_range"] == [25, 35]
        assert any("역전" in w for w in warns)

    def test_prob_range_exceeds_60(self):
        """prob_range upper bound > 60% → warning."""
        draft = {
            "scenario_draft": [
                {"code": "Base", "name": "Base Case", "prob_range": [50, 70],
                 "driver_directions": {}},
                {"code": "Bear", "prob_range": [20, 30],
                 "driver_directions": {"wacc_adj": "up"}},
            ]
        }
        result, warns = validate_scenario_draft(draft)
        assert any("60%" in w for w in warns)

    def test_missing_driver_directions(self):
        """Missing driver_directions → warning."""
        draft = {
            "scenario_draft": [
                {"code": "Bull", "prob_range": [25, 35]},
                {"code": "Base", "name": "Base Case", "prob_range": [35, 45],
                 "driver_directions": {}},
            ]
        }
        result, warns = validate_scenario_draft(draft)
        assert any("driver_directions 누락" in w for w in warns)

    def test_no_base_case_warned(self):
        """No Base Case scenario → warning."""
        draft = {
            "scenario_draft": [
                {"code": "Upside", "name": "Upside", "prob_range": [40, 50],
                 "driver_directions": {"growth_adj_pct": "up"}},
                {"code": "Downside", "name": "Downside", "prob_range": [40, 50],
                 "driver_directions": {"growth_adj_pct": "down"}},
            ]
        }
        result, warns = validate_scenario_draft(draft)
        assert any("Base Case" in w for w in warns)

    def test_not_a_list(self):
        """scenario_draft not a list → warning."""
        draft = {"scenario_draft": "invalid"}
        result, warns = validate_scenario_draft(draft)
        assert any("리스트" in w for w in warns)

    def test_original_not_mutated(self):
        """Original data is not mutated."""
        draft = {
            "scenario_draft": [
                {"code": "Bull", "prob_range": [35, 25],
                 "driver_directions": {"growth_adj_pct": "up"}},
                {"code": "Base", "name": "Base Case", "prob_range": [35, 45],
                 "driver_directions": {}},
            ]
        }
        result, warns = validate_scenario_draft(draft)
        assert draft["scenario_draft"][0]["prob_range"] == [35, 25]  # unchanged
        assert result["scenario_draft"][0]["prob_range"] == [25, 35]  # fixed


# ── News Driver Validation Tests ──

class TestValidateNewsDrivers:
    def test_valid_driver(self):
        drivers = [{"id": "d1", "effects": {"wacc_adj": 0.5, "growth_adj_pct": -10}}]
        result, warns = validate_news_drivers(drivers)
        assert len(warns) == 0
        assert result[0]["effects"]["wacc_adj"] == 0.5

    def test_out_of_range_clamped(self):
        drivers = [{"id": "d1", "effects": {"wacc_adj": 5.0}}]
        result, warns = validate_news_drivers(drivers)
        assert result[0]["effects"]["wacc_adj"] == 3.0
        assert any("범위 이탈" in w for w in warns)
