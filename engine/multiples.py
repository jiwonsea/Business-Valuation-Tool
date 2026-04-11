"""Multiples cross-validation engine -- multiple valuation methods beyond EV/EBITDA.

Cross-validates with EV/Revenue, P/E, P/BV in addition to SOTP (EV/EBITDA)
to expand the football field range.
"""

import logging
from dataclasses import dataclass

from .units import per_share as _per_share

logger = logging.getLogger(__name__)


@dataclass
class MultipleValuation:
    method: str  # "EV/EBITDA", "EV/Revenue", "P/E", "P/BV"
    metric_value: float  # Applied metric value (EBITDA, Revenue, etc.)
    multiple: float  # Applied multiple
    enterprise_value: int  # EV (or equity value for P/E, P/BV)
    equity_value: int  # EV - net debt (EV methods) or direct
    per_share: int  # Per-share value


def calc_ev_revenue(
    revenue: int,
    multiple: float,
    net_debt: int,
    shares: int,
    unit_multiplier: int = 1_000_000,
) -> MultipleValuation:
    """EV/Revenue method."""
    ev = round(revenue * multiple)
    equity = ev - net_debt
    ps = _per_share(equity, unit_multiplier, shares)
    return MultipleValuation(
        method="EV/Revenue",
        metric_value=revenue,
        multiple=multiple,
        enterprise_value=ev,
        equity_value=equity,
        per_share=ps,
    )


def calc_pe(
    net_income: int,
    multiple: float,
    shares: int,
    unit_multiplier: int = 1_000_000,
) -> MultipleValuation:
    """P/E method (direct equity value)."""
    equity = round(net_income * multiple) if net_income > 0 else 0
    ps = _per_share(equity, unit_multiplier, shares)
    if ps > 10_000_000 and net_income > 0:
        logger.warning(
            "P/E per-share unusually high: %s (net_income=%s, multiple=%s, shares=%s, um=%s)",
            ps,
            net_income,
            multiple,
            shares,
            unit_multiplier,
        )
    return MultipleValuation(
        method="P/E",
        metric_value=net_income,
        multiple=multiple,
        enterprise_value=0,
        equity_value=equity,
        per_share=ps,
    )


def calc_pbv(
    book_value: int,
    multiple: float,
    shares: int,
    unit_multiplier: int = 1_000_000,
) -> MultipleValuation:
    """P/BV method (direct equity value)."""
    equity = round(book_value * multiple)
    ps = _per_share(equity, unit_multiplier, shares)
    return MultipleValuation(
        method="P/BV",
        metric_value=book_value,
        multiple=multiple,
        enterprise_value=0,
        equity_value=equity,
        per_share=ps,
    )


def calc_ps(
    revenue: int,
    multiple: float,
    shares: int,
    unit_multiplier: int = 1_000_000,
) -> MultipleValuation:
    """P/S (Price-to-Sales) method -- cross-validation for loss-making growth stocks.

    Used as a DCF alternative for early-stage companies (pre-profit).
    Equity Value = Revenue x P/S multiple.
    """
    equity = round(revenue * multiple) if revenue > 0 else 0
    ps = _per_share(equity, unit_multiplier, shares)
    return MultipleValuation(
        method="P/S",
        metric_value=revenue,
        multiple=multiple,
        enterprise_value=0,
        equity_value=equity,
        per_share=ps,
    )


def calc_pffo(
    ffo: int,
    multiple: float,
    shares: int,
    unit_multiplier: int = 1_000_000,
) -> MultipleValuation:
    """P/FFO (Price to Funds From Operations) method -- REIT-specific.

    FFO = Net income + Depreciation - Gain on real estate sales.
    Reflects actual cash generation instead of net income distorted by depreciation.
    """
    equity = round(ffo * multiple) if ffo > 0 else 0
    ps = _per_share(equity, unit_multiplier, shares)
    return MultipleValuation(
        method="P/FFO",
        metric_value=ffo,
        multiple=multiple,
        enterprise_value=0,
        equity_value=equity,
        per_share=ps,
    )


def cross_validate(
    revenue: int,
    ebitda: int,
    net_income: int,
    book_value: int,
    net_debt: int,
    shares: int,
    sotp_ev: int,
    dcf_ev: int,
    ev_revenue_multiple: float = 0,
    pe_multiple: float = 0,
    pbv_multiple: float = 0,
    ps_multiple: float = 0,
    pffo_multiple: float = 0,
    ffo: int = 0,
    unit_multiplier: int = 1_000_000,
    sotp_ev_ebitda_only: int | None = None,
) -> list[MultipleValuation]:
    """Multi-method cross-validation result list.

    Args:
        revenue, ebitda, net_income, book_value: Financial metrics (in display unit)
        net_debt: Net debt
        shares: Number of shares
        sotp_ev, dcf_ev: Existing SOTP/DCF EV
        ev_revenue_multiple: EV/Revenue multiple (0 to skip)
        pe_multiple: P/E multiple (0 to skip)
        pbv_multiple: P/BV multiple (0 to skip)
        ps_multiple: P/S multiple (0 to skip, for loss-making growth stocks)
        pffo_multiple: P/FFO multiple (0 to skip, for REITs)
        ffo: Funds From Operations (for REITs, 0 to skip)

    Returns:
        [MultipleValuation, ...] (includes SOTP, DCF)
    """
    results = []

    # 1. SOTP (only when sotp_ev > 0)
    if sotp_ev > 0:
        sotp_equity = sotp_ev - net_debt
        sotp_ps = _per_share(sotp_equity, unit_multiplier, shares)
        # Use ev-only total for implied multiple when provided (excludes equity-based pbv/pe segments
        # that inflate the implied EV/EBITDA by mixing equity values into an enterprise multiple).
        ev_for_multiple = (
            sotp_ev_ebitda_only if sotp_ev_ebitda_only is not None else sotp_ev
        )
        implied_ev_ebitda = round(ev_for_multiple / ebitda, 1) if ebitda > 0 else 0
        results.append(
            MultipleValuation(
                method="SOTP (EV/EBITDA)",
                metric_value=ebitda,
                multiple=implied_ev_ebitda,
                enterprise_value=sotp_ev,
                equity_value=sotp_equity,
                per_share=sotp_ps,
            )
        )

    # 2. DCF (existing) -- skip if DCF failed (EV=0)
    if dcf_ev > 0:
        dcf_equity = dcf_ev - net_debt
        dcf_ps = _per_share(dcf_equity, unit_multiplier, shares)
        results.append(
            MultipleValuation(
                method="DCF (FCFF)",
                metric_value=ebitda,
                multiple=0,
                enterprise_value=dcf_ev,
                equity_value=dcf_equity,
                per_share=dcf_ps,
            )
        )

    # 3. EV/Revenue
    if ev_revenue_multiple > 0 and revenue > 0:
        results.append(
            calc_ev_revenue(
                revenue, ev_revenue_multiple, net_debt, shares, unit_multiplier
            )
        )

    # 4. P/E
    if pe_multiple > 0 and net_income > 0:
        results.append(calc_pe(net_income, pe_multiple, shares, unit_multiplier))

    # 5. P/BV
    if pbv_multiple > 0 and book_value > 0:
        results.append(calc_pbv(book_value, pbv_multiple, shares, unit_multiplier))

    # 6. P/S (loss-making growth stocks)
    if ps_multiple > 0 and revenue > 0:
        results.append(calc_ps(revenue, ps_multiple, shares, unit_multiplier))

    # 7. P/FFO (REITs)
    if pffo_multiple > 0 and ffo > 0:
        results.append(calc_pffo(ffo, pffo_multiple, shares, unit_multiplier))

    return results
