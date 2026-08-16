"""TXN Q2 2026 채점 스캐폴드(scripts/score_txn_q2_2026.py) 검증.

프린트-전에 채점 산식을 고정: 4-lever 기여 합이 (보고EPS − 예측EPS)와 정합하고,
스코어카드 6개 섹션이 렌더되며, 실제 미입력 시 안전 종료하는지 확인.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("score_txn", REPO / "scripts" / "score_txn_q2_2026.py")
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)


def _demo_actuals() -> dict:
    a = {k: None for k in S.ACTUALS}
    a.update({
        "q2_revenue": 5300.0, "q2_operating_income": 2150.0, "q2_net_income": 1800.0,
        "q2_eps_diluted": 1.968, "q2_diluted_shares": 910_000_000.0,  # NI 1800 - RSU ~9 → IAC 1791 → EPS 1.968
        "q2_gross_margin_pct": 0.588, "q2_depreciation": 555.0, "q2_effective_tax_rate": 0.12,
        "q3_guide_rev_low": 5400.0, "q3_guide_rev_high": 5800.0,
        "q3_guide_eps_low": 2.00, "q3_guide_eps_high": 2.30,
        "q3_consensus_rev": 5450.0, "q3_consensus_eps": 2.05,
    })
    return a


def test_selftest_reconciles():
    assert S._selftest() == 0


def test_four_lever_sums_and_reconciles_to_reported_eps():
    # EPS 분자 = 보통주귀속이익(IAC) → telescoping 합=총오차 AND 재구성 e4 = 보고 EPS(정확).
    f = S.load_frozen()
    p = f["weighted"]
    a = _demo_actuals()
    iac, _ = S.income_to_common(a)
    Ra, Ma, Ca, Sa = a["q2_revenue"], a["q2_operating_income"]/a["q2_revenue"], iac/a["q2_operating_income"], a["q2_diluted_shares"]
    e0 = S._eps_from(p["rev"], p["opm"], p["conv"], p["shares"])
    e1 = S._eps_from(Ra, p["opm"], p["conv"], p["shares"])
    e2 = S._eps_from(Ra, Ma, p["conv"], p["shares"])
    e3 = S._eps_from(Ra, Ma, Ca, p["shares"])
    e4 = S._eps_from(Ra, Ma, Ca, Sa)
    total = (e1-e0) + (e2-e1) + (e3-e2) + (e4-e3)
    assert abs(total - (e4 - e0)) < 1e-9
    assert abs(e4 - a["q2_eps_diluted"]) < 1e-9   # ★ 분자=IAC라 보고 EPS로 정확 재구성


def test_eps_numerator_is_income_to_common_not_ni():
    # 회귀 가드(Codex): 분자를 NI로 쓰면 보고 EPS와 어긋나야 한다(=IAC를 써야 정합).
    a = _demo_actuals()
    iac, src = S.income_to_common(a)
    rsu = a["q2_net_income"] - iac
    assert 0.0 <= rsu <= 0.03 * a["q2_net_income"]        # RSU 배분 합리 범위
    assert src.startswith("파생") or src.startswith("10-Q")
    # IAC/shares = 보고 EPS, NI/shares ≠ 보고 EPS(RSU만큼 상회)
    assert abs(iac * S.SCALE / a["q2_diluted_shares"] - a["q2_eps_diluted"]) < 1e-9
    assert a["q2_net_income"] * S.SCALE / a["q2_diluted_shares"] > a["q2_eps_diluted"]


def test_frozen_factors_match_committed_profile():
    f = S.load_frozen()
    assert f["label"] == "2026Q2"
    assert round(f["weighted"]["rev"]) == 5207
    assert round(f["weighted"]["eps"], 2) == 1.89


def test_scorecard_renders_all_sections():
    f = S.load_frozen()
    md = S.build_scorecard(_demo_actuals(), f)
    for header in ["## 1.", "## 2.", "## 3.", "## 4.", "## 5.", "## 6."]:
        assert header in md
    assert "4-lever" in md and "감가상각" in md


def test_consensus_direction_miss_flagged_on_beat():
    # 합성 실적이 컨센을 상회하는데 우리 콜은 'below' → 미스로 표기돼야 함.
    f = S.load_frozen()
    lines: list[str] = []
    S.score_consensus(_demo_actuals(), lines)
    assert any("미스" in ln for ln in lines)


def test_main_safe_when_actuals_empty(capsys):
    saved = dict(S.ACTUALS)
    try:
        for k in S.ACTUALS:
            S.ACTUALS[k] = None
        assert S.main([]) == 0
        out = capsys.readouterr().out
        assert "SCAFFOLD READY" in out
    finally:
        S.ACTUALS.update(saved)
