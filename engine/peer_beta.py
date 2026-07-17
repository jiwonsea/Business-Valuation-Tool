"""Pure peer-beta distribution judgement; never changes valuation inputs."""

from __future__ import annotations

from schemas.models import PeerBetaEntry, PeerBetaJudgement

MIN_QUALIFIED_PEERS = 5


def _quantile(values: list[float], probability: float) -> float:
    """Linear interpolation on (n-1)*p; deterministic for small peer sets."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def judge_company_beta(
    company_raw_bl: float,
    peers: list[PeerBetaEntry],
    *,
    benchmark: str,
    frequency: str,
    calculation_method: str,
) -> PeerBetaJudgement:
    qualified = [peer for peer in peers if peer.qualified]
    if len(qualified) < MIN_QUALIFIED_PEERS:
        return PeerBetaJudgement(
            status="insufficient_peers",
            company_raw_bl=company_raw_bl,
            n_qualified=len(qualified),
        )
    if any(
        peer.benchmark != benchmark
        or peer.frequency != frequency
        or peer.calculation_method != calculation_method
        for peer in qualified
    ):
        return PeerBetaJudgement(
            status="method_mismatch",
            company_raw_bl=company_raw_bl,
            n_qualified=len(qualified),
        )

    values = [float(peer.raw_levered_beta) for peer in qualified]
    q1 = _quantile(values, 0.25)
    median = _quantile(values, 0.50)
    q3 = _quantile(values, 0.75)
    iqr = q3 - q1
    if iqr == 0:
        return PeerBetaJudgement(
            status="degenerate_distribution",
            company_raw_bl=company_raw_bl,
            n_qualified=len(qualified),
            median_raw=median,
            q1_raw=q1,
            q3_raw=q3,
        )
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    status = "validated"
    if company_raw_bl < lower:
        status = "outlier_low"
    elif company_raw_bl > upper:
        status = "outlier_high"
    return PeerBetaJudgement(
        status=status,
        company_raw_bl=company_raw_bl,
        n_qualified=len(qualified),
        median_raw=median,
        q1_raw=q1,
        q3_raw=q3,
        lower_fence=lower,
        upper_fence=upper,
    )
