"""Cyclical driver library — generalize the memory cost-cycle model to any
hypercyclical sector whose earnings track an observable output/input price spread.

Item 2 (2026-07). EFE already models SK Hynix as cost-per-bit (input) vs
TrendForce ASP (output). That is one instance of a general pattern:

    margin_t = base_margin + passthrough * (spread_t - spread_0)
    spread_t = output_price_t - input_cost_t            (in indexed / per-unit terms)

This package exposes that pattern as a reusable interface (`base.py`), a set of
sector-configured drivers (`sectors.py`), and a registry keyed by sector so a
hypercyclical name gets a driver-based forward margin instead of abstaining.

Data honesty: some series are paywalled (TrendForce, IHS, S&P Global Platts).
Each sector declares its inputs with a `paywalled` flag and a public fallback
where one exists (oil & metals futures, Baltic Dry public index). The skill gate
still applies downstream: a driver forecast that does not beat naive on the
(now longer, Item 1) backtest abstains — this library only PRODUCES the forecast;
it does not certify it.
"""

from engine.cyclical_drivers.base import (
    DataSource,
    DriverInputs,
    SpreadMarginDriver,
    project_margin_path,
    spread_series,
)
from engine.cyclical_drivers.sectors import SECTOR_DRIVERS, available_sectors, get_driver

__all__ = [
    "DataSource",
    "DriverInputs",
    "SpreadMarginDriver",
    "project_margin_path",
    "spread_series",
    "SECTOR_DRIVERS",
    "available_sectors",
    "get_driver",
]
