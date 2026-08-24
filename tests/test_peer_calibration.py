"""Regression tests for Phase 3 external-market peer calibration.

Offline — uses frozen yfinance-info JSON fixtures injected via the fetcher
parameter, so these tests never hit the network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from calibration.peer_deviation import (
    N_PRELIMINARY,
    N_STABLE,
    calc_stats,
    compute_profile_deviations,
)
from calibration.peer_fetcher import PeerMultiples, fetch_peer_multiples
from calibration.peer_report import emit_peer_report, render_peer_report

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str):
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def fetcher(ticker: str) -> dict:
        return data.get(ticker, {})

    return data, fetcher


def test_calc_stats_tier_boundaries():
    assert calc_stats([]).tier == "insufficient"
    assert calc_stats([1.0, 2.0, 3.0, 4.0]).tier == "insufficient"  # N=4
    preliminary = calc_stats([1.0, 2.0, 3.0, 4.0, 5.0])  # N=5
    assert preliminary.tier == "preliminary"
    assert preliminary.median == 3.0
    stable = calc_stats([float(i) for i in range(1, 11)])  # N=10
    assert stable.tier == "stable"
    assert stable.n == N_STABLE >= 10 and N_PRELIMINARY == 5


def test_calc_stats_drops_nonpositive_and_none():
    stats = calc_stats([None, 0, -5, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
    assert stats.n == 6
    assert stats.median == 35.0


def test_fetch_peer_multiples_with_injected_fetcher():
    data, fetcher = _load_fixture("msft_peer_info.json")
    peers = fetch_peer_multiples(list(data.keys()), fetcher=fetcher)
    assert len(peers) == len(data)
    crm = next(p for p in peers if p.ticker == "CRM")
    assert crm.ev_ebitda == pytest.approx(22.4)
    assert crm.trailing_pe == pytest.approx(42.1)


def test_msft_deviation_regression():
    """MSFT profile values (pe=27, ev_rev=9.9) vs frozen 10-peer universe."""
    data, fetcher = _load_fixture("msft_peer_info.json")
    peers = fetch_peer_multiples(list(data.keys()), fetcher=fetcher)

    deviations = compute_profile_deviations(
        peers,
        pe_multiple=27.0,
        ev_revenue_multiple=9.9,
        scenario_ev_ebitda={"A": 22.67, "B": 26.0, "C": 18.33, "D": 20.33},
    )

    by = {(d.multiple_type, d.scope): d for d in deviations}

    ev_rev = by[("ev_revenue", "profile")]
    assert ev_rev.stats.n == 10
    assert ev_rev.stats.tier == "stable"
    # Median of 10 ev_revenue values = mean(6.8, 7.2) = 7.0
    assert ev_rev.stats.median == pytest.approx(7.0)
    # 9.9 vs 7.0 → ~+41% → flagged
    assert ev_rev.flag == "⚠️"

    trailing = by[("trailing_pe", "profile")]
    # WDAY had null trailing_pe → dropped by gate
    assert trailing.stats.n == 9

    # Scenario B (EV/EBITDA 26) vs peer median
    scen_b = by[("ev_ebitda", "scenario B")]
    assert scen_b.engine_value == pytest.approx(26.0)
    assert scen_b.stats.tier == "stable"
    assert scen_b.stats.n == 10


def test_tsla_small_peer_group_tier():
    """TSLA fixture has only 7 peers; NIO drops EV/EBITDA → N=6 preliminary."""
    data, fetcher = _load_fixture("tsla_peer_info.json")
    peers = fetch_peer_multiples(list(data.keys()), fetcher=fetcher)

    deviations = compute_profile_deviations(
        peers,
        pe_multiple=60.0,
        ev_revenue_multiple=5.0,
        scenario_ev_ebitda={"A": 40.0},
    )
    by = {(d.multiple_type, d.scope): d for d in deviations}

    ev_ebitda = by[("ev_ebitda", "scenario A")]
    assert ev_ebitda.stats.n == 6  # NIO null excluded
    assert ev_ebitda.stats.tier == "preliminary"
    assert any("preliminary" in n for n in ev_ebitda.notes)

    # Trailing P/E: NIO null excluded → 6 peers, all positive
    trailing = by[("trailing_pe", "profile")]
    assert trailing.stats.n == 6
    # 60 vs peer median ~7.75 → huge positive deviation → flagged
    assert trailing.flag == "⚠️"


def test_insufficient_peers_suppressed():
    peers = [
        PeerMultiples(
            ticker="A", ev_ebitda=10, ev_revenue=2, trailing_pe=15, forward_pe=12
        ),
        PeerMultiples(
            ticker="B", ev_ebitda=12, ev_revenue=3, trailing_pe=18, forward_pe=14
        ),
    ]
    rows = compute_profile_deviations(peers, pe_multiple=25.0, ev_revenue_multiple=5.0)
    for r in rows:
        assert r.stats.tier == "insufficient"
        assert r.deviation_pct is None
        assert r.flag == "—"


def test_render_report_smoke(tmp_path):
    data, fetcher = _load_fixture("msft_peer_info.json")
    peers = fetch_peer_multiples(list(data.keys()), fetcher=fetcher)
    deviations = compute_profile_deviations(
        peers, pe_multiple=27.0, ev_revenue_multiple=9.9
    )
    text = render_peer_report(deviations, ticker="MSFT", peers=peers)
    assert "Peer Deviation Report" in text
    assert "MSFT" in text
    assert "ev_revenue" in text


def test_emit_peer_report_end_to_end(tmp_path):
    """Write a minimal profile yaml and run the full emit pipeline."""
    import yaml

    data, fetcher = _load_fixture("msft_peer_info.json")
    profile_path = tmp_path / "msft_test.yaml"
    profile_path.write_text(
        yaml.safe_dump(
            {
                "company": {"ticker": "MSFT"},
                "pe_multiple": 27.0,
                "ev_revenue_multiple": 9.9,
                "peer_tickers": list(data.keys()),
                "scenarios": {
                    "A": {
                        "segment_multiples": {"SEG1": 28.0, "SEG2": 22.0, "SEG3": 18.0}
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    out = emit_peer_report(profile_path, output_dir=tmp_path, fetcher=fetcher)
    assert out.exists()
    body = out.read_text(encoding="utf-8")
    assert "MSFT" in body
    assert "scenario A" in body
