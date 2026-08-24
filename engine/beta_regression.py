"""Pure regression helpers for observed equity beta."""

from __future__ import annotations

import math
from collections.abc import Sequence


def regress_beta(
    stock_returns: Sequence[float], benchmark_returns: Sequence[float]
) -> tuple[float, int]:
    """Return OLS slope with an intercept for aligned return observations."""
    if len(stock_returns) != len(benchmark_returns):
        raise ValueError("stock and benchmark returns must be aligned")
    n = len(stock_returns)
    if n < 2:
        raise ValueError("at least two aligned observations are required")
    pairs = [(float(s), float(b)) for s, b in zip(stock_returns, benchmark_returns)]
    if any(not math.isfinite(v) for pair in pairs for v in pair):
        raise ValueError("returns must be finite")
    stock_mean = sum(s for s, _ in pairs) / n
    benchmark_mean = sum(b for _, b in pairs) / n
    variance = sum((b - benchmark_mean) ** 2 for _, b in pairs)
    if variance <= 0:
        raise ValueError("benchmark return variance must be positive")
    covariance = sum((s - stock_mean) * (b - benchmark_mean) for s, b in pairs)
    beta = covariance / variance
    if not math.isfinite(beta):
        raise ValueError("regressed beta is not finite")
    return beta, n
