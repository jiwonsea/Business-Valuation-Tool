"""Sector -> driver map (v1). Passthrough values are seed priors to be CALIBRATED
per name on the backtest (Item 1 skill gate decides if the calibrated driver
actually forecasts); they are not asserted truths.

Data availability is marked honestly: paywalled series (TrendForce, IHS, Platts)
carry a public fallback where one exists; where none does, the gap is explicit.
"""

from __future__ import annotations

from engine.cyclical_drivers.base import DataSource, SpreadMarginDriver

# ── reusable source definitions ─────────────────────────────────────────────
_DRAM_ASP = DataSource("DRAM/NAND contract ASP", "output_price", "TrendForce", True,
                       public_fallback="DXI memory index (proxy, lower fidelity)")
_COST_PER_BIT = DataSource("Cost per bit", "input_cost", "company IR / est.", False)

_STEEL_HRC = DataSource("Hot-rolled coil (HRC) price", "output_price", "SteelBenchmarker/CME", False,
                        public_fallback="CME HRC futures")
_IRON_ORE = DataSource("Iron ore 62% Fe", "input_cost", "public spot (SGX/Dalian)", False)

_JET_FUEL = DataSource("Jet fuel spot", "input_cost", "EIA (public)", False)
_PASSENGER_YIELD = DataSource("Passenger yield / RASK", "output_price", "carrier IR", False)

_CRUDE = DataSource("Crude oil futures (WTI/Brent)", "output_price", "CME/ICE (public)", False)
_LIFT_COST = DataSource("Production lifting cost", "input_cost", "company IR / est.", False)

_ETHYLENE = DataSource("Ethylene / PX spread", "output_price", "S&P Global Platts", True,
                       public_fallback="none (regional; approximate from naphtha crack)")
_NAPHTHA = DataSource("Naphtha", "input_cost", "public (approx from crude)", False)

_BDI = DataSource("Baltic Dry Index / SCFI", "output_price", "Baltic Exchange (BDI public)", False,
                  public_fallback="BDI public daily")
_BUNKER = DataSource("Bunker fuel (VLSFO)", "input_cost", "public port indices", False)

_BATTERY_METALS = DataSource("Li / Ni / Co basket", "input_cost", "LME / public spot", False)
_CELL_ASP = DataSource("Battery cell ASP", "output_price", "BNEF / IHS", True,
                       public_fallback="none (contract-priced)")

_AUTO_ASP = DataSource("Vehicle ASP net of incentives", "output_price", "carrier IR", False)
_STEEL_BATTERY_COST = DataSource("Steel + battery metals input cost", "input_cost", "public spot", False)


SECTOR_DRIVERS: dict[str, SpreadMarginDriver] = {
    "memory_semis": SpreadMarginDriver(
        "memory_semis", _DRAM_ASP, _COST_PER_BIT, default_passthrough=0.9,
        notes="Existing EFE memory engine is the reference instance (cost-per-bit x ASP).",
    ),
    "steel": SpreadMarginDriver(
        "steel", _STEEL_HRC, _IRON_ORE, default_passthrough=0.6,
        notes="HRC output vs iron ore input; both largely public.",
    ),
    "airlines": SpreadMarginDriver(
        "airlines", _PASSENGER_YIELD, _JET_FUEL, default_passthrough=0.7,
        notes="Jet fuel (EIA public) is the dominant swing cost.",
    ),
    "oil_gas": SpreadMarginDriver(
        "oil_gas", _CRUDE, _LIFT_COST, default_passthrough=0.85,
        notes="E&P margin tracks crude futures vs lifting cost; crude fully public.",
    ),
    "chemicals": SpreadMarginDriver(
        "chemicals", _ETHYLENE, _NAPHTHA, default_passthrough=0.7,
        notes="Ethylene/PX spread paywalled (Platts); naphtha approx from crude.",
    ),
    "shipping": SpreadMarginDriver(
        "shipping", _BDI, _BUNKER, default_passthrough=0.8,
        notes="Freight rates (BDI/SCFI) public; bunker public.",
    ),
    "batteries": SpreadMarginDriver(
        "batteries", _CELL_ASP, _BATTERY_METALS, default_passthrough=0.6,
        notes="Metals input public (LME); cell ASP contract-priced (gap).",
    ),
    "autos": SpreadMarginDriver(
        "autos", _AUTO_ASP, _STEEL_BATTERY_COST, default_passthrough=0.4,
        notes="Multi-driver (steel+battery metals, chip supply, incentives, FX); "
              "v1 collapses cost to a steel+metals basket. Chip supply/FX to add.",
        extra_sources=[
            DataSource("Semiconductor supply / lead times", "input_cost", "public/est.", False),
            DataSource("FX (USD/local)", "input_cost", "public", False),
        ],
    ),
}


def available_sectors() -> list[str]:
    return sorted(SECTOR_DRIVERS)


def get_driver(sector: str) -> SpreadMarginDriver:
    try:
        return SECTOR_DRIVERS[sector]
    except KeyError as exc:
        raise KeyError(
            f"no cyclical driver for sector {sector!r}; known: {available_sectors()}"
        ) from exc
