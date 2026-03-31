"""Dividend Discount Model (DDM) -- Gordon Growth Model-based pure functions.

Total Payout DDM: supports valuation based on total shareholder return including buybacks.
"""

from dataclasses import dataclass


@dataclass
class DDMResult:
    """DDM valuation result."""
    dps: float  # Dividend per share
    buyback_per_share: float  # Buyback return per share
    total_payout: float  # Total payout per share (DPS + buyback)
    growth: float  # Growth rate (%)
    ke: float  # Cost of equity (%)
    equity_per_share: int  # Intrinsic value per share


def calc_ddm(
    dps: float,
    growth: float,
    ke: float,
    buyback_per_share: float = 0.0,
) -> DDMResult:
    """Gordon Growth DDM (Total Payout support).

    Per-share value = TotalPayout x (1+g) / (Ke - g)
    TotalPayout = DPS + buyback return per share

    US financials have significant buyback portions, making DPS-only DDM undervalue them.
    When buyback_per_share > 0, operates as a Total Shareholder Yield model.

    Args:
        dps: Dividend per share (KRW or $)
        growth: Dividend/payout growth rate (%, e.g., 3.0 = 3%)
        ke: Cost of equity (%, e.g., 10.0 = 10%)
        buyback_per_share: Buyback return per share (KRW or $, default 0)

    Returns:
        DDMResult with equity_per_share
    """
    g = growth / 100
    k = ke / 100

    if k <= g:
        raise ValueError(
            f"Ke({ke}%) must be greater than growth({growth}%). "
            "DDM is not applicable when growth >= cost of equity."
        )

    total_payout = dps + buyback_per_share
    value = total_payout * (1 + g) / (k - g)
    return DDMResult(
        dps=dps,
        buyback_per_share=buyback_per_share,
        total_payout=total_payout,
        growth=growth,
        ke=ke,
        equity_per_share=round(value),
    )
