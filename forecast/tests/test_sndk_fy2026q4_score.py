"""SNDK FY2026 Q4 사후 채점 산식 가드 (사후 귀인 — 예측 신호 아님).

동결 예측은 profiles/sndk.generic.yaml + reports/sndk_fy2026q4_forecast_FROZEN.md에
고정돼 있다. 여기서는 채점 스크립트의 **산식**만 검증한다:
  - 실적 항등식(원문 8-K EX-99.1과 대조)
  - 4-lever 재구성 잔차 ≈ 0
  - OP→NI 전환 레버의 below-OP/세율 2차 분해가 정확히 상위 레버 합과 같을 것
"""

from __future__ import annotations

import pytest

from scripts.score_sndk_fy2026q4 import ACTUAL, SCALE, _eps_from, load_frozen


def test_actual_income_statement_identities() -> None:
    a = ACTUAL
    assert a["revenue"] - a["cost_of_revenue"] == a["gross_profit"] == 7582.0
    assert a["gross_profit"] - a["opex"] == a["operating_income"] == 7037.0
    assert a["operating_income"] + a["below_op_total"] == a["pretax"] == 7849.0
    assert a["pretax"] - a["tax"] == a["net_income"] == 6903.0
    assert a["net_income"] * SCALE / a["diluted_shares"] == pytest.approx(a["eps_diluted_gaap"], abs=0.01)
    assert a["seg_datacenter"] + a["seg_edge"] + a["seg_consumer"] == a["revenue"]


def test_non_gaap_bridge_identity() -> None:
    """GAAP NI + SBC − 지분증권 평가이익 − 세금조정 = 비GAAP NI (8-K 재조정표)."""
    a = ACTUAL
    assert a["net_income"] + 67 - a["gain_on_equity_securities"] - 4 == a["non_gaap_net_income"]
    assert a["non_gaap_net_income"] * SCALE / a["diluted_shares"] == pytest.approx(
        a["eps_diluted_non_gaap"], abs=0.01
    )


def test_four_lever_reconstruction_residual_is_zero() -> None:
    a, f = ACTUAL, load_frozen()
    Ra = a["revenue"]
    Ma = a["operating_income"] / Ra
    Ca = a["net_income"] / a["operating_income"]
    e4 = _eps_from(Ra, Ma, Ca, a["diluted_shares"])
    assert e4 == pytest.approx(a["eps_diluted_gaap"], abs=0.01)


def test_below_op_and_tax_subdecomposition_sums_to_the_conversion_lever() -> None:
    a, f = ACTUAL, load_frozen()
    p = f["weighted"]
    Rp, Mp, Cp, Sp = p["rev"], p["opm"], p["conv"], f["shares"]
    Ra = a["revenue"]
    Ma = a["operating_income"] / Ra
    Ca = a["net_income"] / a["operating_income"]
    e2 = _eps_from(Ra, Ma, Cp, Sp)
    e3 = _eps_from(Ra, Ma, Ca, Sp)
    b_p = f["weighted_below_op"] / p["op"]
    t_p = 1.0 - Cp / (1.0 + b_p)
    b_a = a["below_op_total"] / a["operating_income"]
    t_a = a["tax"] / a["pretax"]
    e2b = _eps_from(Ra, Ma, (1.0 + b_a) * (1.0 - t_p), Sp)
    assert (e2b - e2) + (e3 - e2b) == pytest.approx(e3 - e2, abs=1e-9)
    # below-OP 하위 레버가 지배적이어야 한다(사후 사실: 지분증권 평가이익 +804).
    assert abs(e2b - e2) > abs(e3 - e2b) * 4


def test_band_coverage_and_consensus_direction() -> None:
    """밴드 3종 모두 커버, 컨센 방향 콜은 HIT."""
    a, f = ACTUAL, load_frozen()
    assert f["bear"]["rev"] <= a["revenue"] <= f["bull"]["rev"]
    assert f["bear"]["eps"] <= a["eps_diluted_gaap"] <= f["bull"]["eps"]
    ng_lo, ng_hi = f["bear"]["eps"] + 0.32, f["bull"]["eps"] + 0.32
    assert ng_lo <= a["eps_diluted_non_gaap"] <= ng_hi
    assert a["eps_diluted_non_gaap"] > 34.67  # 우리 콜 = above


def test_below_op_band_failed_and_that_is_recorded() -> None:
    """SF3는 발화했고 밴드는 실패했다 — 이 사실이 회귀로 남아야 한다."""
    a, f = ACTUAL, load_frozen()
    bear_below = f["bear"]["below_op"]
    bull_below = f["bull"]["below_op"]
    assert a["below_op_total"] > bull_below  # 밴드 상단 초과
    assert a["below_op_total"] / bull_below > 10  # 한 자릿수 배가 아니라 10배 이상 초과
