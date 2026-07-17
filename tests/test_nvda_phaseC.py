from pathlib import Path

from output.console_report import print_report
from valuation_runner import load_profile, run_valuation

ROOT = Path(__file__).resolve().parents[1]


def test_forward_and_peer_metadata_do_not_change_valuation(capsys):
    vi = load_profile(str(ROOT / "profiles" / "nvda.yaml"))
    assert vi.consolidated[vi.base_year]["revenue"] == 253_491
    assert vi.forward_anchor.revenue.value > 390_000
    assert vi.peer_beta_snapshot.judgement.status == "validated"

    without = vi.model_copy(update={"forward_anchor": None, "peer_beta_snapshot": None})
    actual = run_valuation(vi)
    control = run_valuation(without)
    assert actual.wacc == control.wacc
    assert actual.scenarios == control.scenarios

    print_report(vi, actual)
    output = capsys.readouterr().out
    assert "FY27 컨센서스 (예측치" in output
    assert "Peer beta 판정: validated" in output


def test_forward_revenue_converges_with_manual_reference():
    actual = load_profile(str(ROOT / "profiles" / "nvda.yaml"))
    reference = load_profile(str(ROOT / "profiles" / "nvda_fy27e.yaml"))
    automatic = actual.forward_anchor.revenue.value
    manual = reference.consolidated[reference.base_year]["revenue"]
    assert abs(automatic / manual - 1) <= 0.10
