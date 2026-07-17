from datetime import date

import pytest

from engine.peer_beta import judge_company_beta
from schemas.models import PeerBetaEntry


def _peer(ticker: str, beta: float, **over) -> PeerBetaEntry:
    data = dict(
        name=ticker,
        ticker=ticker,
        segment_code="SEG1",
        qualified=True,
        qualification_reason="data-center semiconductor peer",
        raw_levered_beta=beta,
        blume_adjusted=round(0.67 * beta + 0.33, 4),
        window_start=date(2024, 7, 5),
        window_end=date(2026, 7, 10),
        frequency="weekly",
        benchmark="^GSPC",
        observation_count=105,
        calculation_method="ols_weekly_log_returns_adjusted_close",
        source_hash="a" * 64,
    )
    data.update(over)
    return PeerBetaEntry(**data)


def _judge(beta: float, peers: list[PeerBetaEntry]):
    return judge_company_beta(
        beta,
        peers,
        benchmark="^GSPC",
        frequency="weekly",
        calculation_method="ols_weekly_log_returns_adjusted_close",
    )


def test_tukey_judgement_is_pure_and_deterministic():
    peers = [_peer(str(i), beta) for i, beta in enumerate([1.0, 1.1, 1.2, 1.3, 1.4])]
    assert _judge(1.25, peers).status == "validated"
    assert _judge(2.0, peers).status == "outlier_high"
    assert _judge(0.1, peers).status == "outlier_low"


def test_exact_fence_is_validated_and_value_above_is_outlier():
    peers = [_peer(str(i), beta) for i, beta in enumerate([1.0, 1.1, 1.2, 1.3, 1.4])]
    result = _judge(1.7, peers)
    assert result.upper_fence == pytest.approx(1.6)
    assert result.status == "outlier_high"
    assert _judge(result.lower_fence, peers).status == "validated"
    assert _judge(result.upper_fence, peers).status == "validated"


def test_degenerate_distribution_fails_closed():
    peers = [_peer(str(i), 1.2) for i in range(5)]
    assert _judge(1.2, peers).status == "degenerate_distribution"


def test_ties_are_not_deduplicated():
    peers = [_peer(str(i), beta) for i, beta in enumerate([1.0, 1.0, 1.2, 1.4, 1.4])]
    result = _judge(1.2, peers)
    assert result.n_qualified == 5
    assert result.status == "validated"


def test_fewer_than_five_peers_fails_closed():
    peers = [_peer(str(i), beta) for i, beta in enumerate([1.0, 1.1, 1.2, 1.3])]
    result = _judge(1.2, peers)
    assert result.status == "insufficient_peers"
    assert result.n_qualified == 4


def test_method_mismatch_fails_closed():
    peers = [_peer(str(i), beta) for i, beta in enumerate([1.0, 1.1, 1.2, 1.3, 1.4])]
    peers[-1] = _peer("bad", 1.4, benchmark="^KS11")
    assert _judge(1.2, peers).status == "method_mismatch"


def test_unqualified_peer_requires_reason():
    entry = PeerBetaEntry(
        name="SK hynix", ticker="000660.KS", segment_code="SEG1",
        qualified=False, exclusion_reason="benchmark_mismatch:^KS11",
    )
    assert entry.raw_levered_beta is None
