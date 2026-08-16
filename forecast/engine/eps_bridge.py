"""Net profit → EPS bridge.

EPS_basic = NI / weighted_avg_basic_shares
EPS_diluted = NI / weighted_avg_diluted_shares
"""

from __future__ import annotations

from schemas.models import QuarterlyForecast, SharesOutstanding


def project_eps(
    forecast: list[QuarterlyForecast],
    shares: SharesOutstanding,
) -> list[QuarterlyForecast]:
    """Populate eps_basic / eps_diluted on each forecast quarter.

    Args:
        forecast: NI-populated forecast.
        shares: Weighted avg basic + diluted share counts.

    Returns:
        Same length list with EPS fields filled.

    Raises:
        NotImplementedError: Codex implementation.
    """
    if shares.weighted_avg_basic <= 0 or shares.weighted_avg_diluted <= 0:
        raise ValueError("share counts must be positive")
    results: list[QuarterlyForecast] = []
    for quarter in forecast:
        ni_krw = quarter.net_profit * 1_000_000_000.0
        results.append(
            quarter.model_copy(
                update={
                    "eps_basic": ni_krw / shares.weighted_avg_basic,
                    "eps_diluted": ni_krw / shares.weighted_avg_diluted,
                }
            )
        )
    return results
