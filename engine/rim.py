"""Residual Income Model (RIM) engine — pure functions.

Specialized valuation for financial sector (banks, insurance, securities, etc.).
Value = BV_0 + sum( RI_t / (1+ke)^t )
where RI_t = (ROE - ke) x BV_{t-1}
"""

from dataclasses import dataclass


@dataclass
class RIMProjection:
    """Per-year RIM projection."""

    year: int
    bv: int  # Beginning book value (display unit)
    net_income: int  # Net income (display unit)
    roe: float  # ROE (%)
    ri: int  # Residual income (display unit)
    pv_ri: int  # Present value of residual income


@dataclass
class RIMResult:
    """RIM valuation result."""

    bv_current: int  # Current book value
    ke: float  # Cost of equity (%)
    terminal_growth: float  # Terminal growth rate (%)
    projections: list[RIMProjection]
    pv_ri_sum: int  # Sum of PV of RI over projection period
    terminal_ri: int  # RI terminal value
    pv_terminal: int  # PV of terminal value
    equity_value: int  # Total equity value (BV + PV(RI) + PV(TV))
    per_share: int  # Per-share value


def calc_rim(
    book_value: int,
    roe_forecasts: list[float],
    ke: float,
    terminal_growth: float = 0.0,
    shares: int = 1,
    unit_multiplier: int = 1_000_000,
    payout_ratio: float = 0.0,
) -> RIMResult:
    """Compute RIM valuation.

    Args:
        book_value: Current equity book value (display unit, e.g. millions)
        roe_forecasts: Forecast-period ROE list (%, e.g. [12.0, 11.5, 11.0, 10.5, 10.0])
        ke: Cost of equity (%, e.g. 10.0)
        terminal_growth: RI terminal growth rate (%, e.g. 0.0 -- conservative)
        shares: Shares outstanding
        unit_multiplier: 1 display unit = how many KRW/$
        payout_ratio: Dividend payout ratio (%, e.g. 30.0). 0 assumes clean surplus (all earnings retained in BV).

    Returns:
        RIMResult
    """
    k = ke / 100
    g = terminal_growth / 100
    payout = payout_ratio / 100

    if k <= -1.0:
        raise ValueError(
            f"Ke({ke}%) produces a zero discount factor (1+Ke≤0). Ke must be > -100%."
        )

    if k <= g:
        raise ValueError(
            f"Ke({ke}%) must be greater than terminal_growth({terminal_growth}%). "
            "RIM terminal value is not finite when growth >= cost of equity."
        )

    projections = []
    bv = book_value
    pv_sum = 0

    for i, roe_pct in enumerate(roe_forecasts):
        roe = roe_pct / 100
        ni = round(bv * roe)
        ri = round(bv * (roe - k))
        discount = (1 + k) ** (i + 1)
        pv_ri = round(ri / discount)
        pv_sum += pv_ri

        projections.append(
            RIMProjection(
                year=i + 1,
                bv=bv,
                net_income=ni,
                roe=roe_pct,
                ri=ri,
                pv_ri=pv_ri,
            )
        )

        # Update book value: BV_{t} = BV_{t-1} + NI - Dividends
        dividends = round(ni * payout)
        bv = bv + ni - dividends

    # Terminal Value: RI_{n+1} / (ke - g), using end-of-period BV
    # After loop, `bv` is BV_n (beginning of period n+1).
    # terminal_ri_base = BV_n * (ROE_n - ke) = RI_{n+1} already — no extra (1+g).
    last_roe = roe_forecasts[-1] / 100 if roe_forecasts else 0
    terminal_ri_base = round(bv * (last_roe - k)) if projections else 0
    if k > g and terminal_ri_base != 0:
        terminal_value = round(terminal_ri_base / (k - g))
    else:
        terminal_value = 0

    n = len(projections)
    pv_terminal = round(terminal_value / (1 + k) ** n) if n > 0 else 0

    equity_value = book_value + pv_sum + pv_terminal
    ps = round(equity_value * unit_multiplier / shares) if shares > 0 else 0

    return RIMResult(
        bv_current=book_value,
        ke=ke,
        terminal_growth=terminal_growth,
        projections=projections,
        pv_ri_sum=pv_sum,
        terminal_ri=terminal_value,
        pv_terminal=pv_terminal,
        equity_value=equity_value,
        per_share=ps,
    )
