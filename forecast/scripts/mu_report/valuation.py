"""Scenario-implied multiples and sensitivity; never a price target."""

from __future__ import annotations

from dataclasses import dataclass

FLOW_FIELDS = {"revenue", "eps", "ebitda", "fcf"}


def normalize_52_from_53(value: float, field: str) -> float:
    if field not in FLOW_FIELDS:
        raise ValueError(f"52/53 adjustment is forbidden for point-in-time field: {field}")
    return value * 52.0 / 53.0


def safe_multiple(numerator: float, denominator: float) -> float | str:
    return "N/M" if denominator <= 0 else numerator / denominator


def trailing_pb(
    price: float | str | None,
    equity_musd: float | str | None,
    shares_million: float | str | None,
) -> float | str:
    """Return trailing P/B from price, period-end equity, and point-in-time shares."""
    values = (price, equity_musd, shares_million)
    if any(value is None or (isinstance(value, str) and value.startswith("UNAVAILABLE")) for value in values):
        return "UNAVAILABLE"
    if not all(isinstance(value, (int, float)) for value in values):
        raise ValueError("trailing P/B inputs must be numeric or UNAVAILABLE")
    if shares_million <= 0:
        return "N/M"
    book_value_per_share = equity_musd / shares_million
    return "N/M" if book_value_per_share <= 0 else price / book_value_per_share


@dataclass(frozen=True)
class ImpliedValuation:
    market_cap: float
    ev: float
    ev_adj: float | None
    pe: float | str
    ev_ebitda: float | str
    ev_fcf: float | str


def implied_valuation(price: float, shares_million: float, cash: float, investments: float, debt: float, net_income: float, ebitda: float, fcf: float, sca_deposits: float | None) -> ImpliedValuation:
    market_cap = price * shares_million
    net_cash_unadjusted = cash + investments - debt
    ev = market_cap - net_cash_unadjusted
    ev_adj = None if sca_deposits is None else ev + sca_deposits
    return ImpliedValuation(market_cap, ev, ev_adj, safe_multiple(market_cap, net_income), safe_multiple(ev, ebitda), safe_multiple(ev, fcf))


def sensitivity_heatmap(prices: list[float], earnings: list[float], shares_million: float) -> list[list[float | str]]:
    return [[safe_multiple(price * shares_million, income) for income in earnings] for price in prices]
