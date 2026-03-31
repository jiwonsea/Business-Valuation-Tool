"""Net Asset Value (NAV) engine -- pure functions.

Applied to holding companies, REITs, and asset-centric firms.
Adjusted NAV = total assets at fair value - total liabilities (+ investment asset revaluation).
"""

from dataclasses import dataclass

from .units import per_share as _per_share


@dataclass
class NAVRawResult:
    """Return value of calc_nav."""
    total_assets: int       # Total assets (book value)
    revaluation: int        # Investment asset revaluation adjustment
    adjusted_assets: int    # Adjusted total assets
    total_liabilities: int  # Total liabilities
    nav: int                # Net asset value (adjusted assets - liabilities)
    shares: int
    per_share: int          # NAV per share


def calc_nav(
    total_assets: int,
    total_liabilities: int,
    shares: int,
    revaluation: int = 0,
    unit_multiplier: int = 1_000_000,
) -> NAVRawResult:
    """Compute adjusted Net Asset Value (NAV).

    Args:
        total_assets: Total assets (display unit)
        total_liabilities: Total liabilities (display unit)
        shares: Shares outstanding
        revaluation: Investment asset revaluation adjustment (fair value - book value, display unit)
        unit_multiplier: KRW/$ per display unit

    Returns:
        NAVRawResult
    """
    adjusted = total_assets + revaluation
    nav = adjusted - total_liabilities
    ps = _per_share(nav, unit_multiplier, shares)
    return NAVRawResult(
        total_assets=total_assets,
        revaluation=revaluation,
        adjusted_assets=adjusted,
        total_liabilities=total_liabilities,
        nav=nav,
        shares=shares,
        per_share=ps,
    )
