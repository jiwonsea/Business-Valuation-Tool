"""Pure spread-to-margin driver interface. No IO, no fetch."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DataSource:
    """One observable price series a driver depends on.

    ``paywalled`` marks series behind a subscription (TrendForce, IHS, Platts) so
    a coverage gap is explicit, never silently assumed. ``public_fallback`` names
    a free proxy where one exists (e.g. crude futures for a refiner input).
    """

    name: str
    role: str  # "output_price" | "input_cost"
    provider: str
    paywalled: bool
    public_fallback: str | None = None


@dataclass(frozen=True)
class DriverInputs:
    """Observable series + margin anchor. All series are period-aligned and in
    consistent units; index-normalize before use so passthrough is unit-free.

    output_prices[i] - input_costs[i] is the spread at period i; index 0 is the
    anchor (matches the calibrated base_margin, mirroring the memory model's
    ``margin_periods_since_anchor == 0`` anchor).
    """

    output_prices: list[float]
    input_costs: list[float]
    base_margin: float
    passthrough: float  # d(margin) per unit change in (indexed) spread; >= 0


def spread_series(inputs: DriverInputs) -> list[float]:
    """output_price - input_cost per period. Raises on length mismatch."""
    if len(inputs.output_prices) != len(inputs.input_costs):
        raise ValueError("output_prices and input_costs must be the same length")
    return [o - c for o, c in zip(inputs.output_prices, inputs.input_costs)]


def project_margin_path(inputs: DriverInputs) -> list[float]:
    """Project a margin path from the spread relative to the anchor (period 0).

    margin_t = base_margin + passthrough * (spread_t - spread_0). Pure, so the
    same result is reproducible offline and directly unit-testable. Widening
    spread raises margin; narrowing lowers it; passthrough scales sensitivity.
    """
    spreads = spread_series(inputs)
    if not spreads:
        return []
    anchor = spreads[0]
    return [inputs.base_margin + inputs.passthrough * (s - anchor) for s in spreads]


@dataclass(frozen=True)
class SpreadMarginDriver:
    """Sector-configured driver: which series feed the spread + how sensitive
    the margin is to it. Reusable across names in the same sector."""

    sector: str
    output_source: DataSource
    input_source: DataSource
    default_passthrough: float
    notes: str = ""
    extra_sources: list[DataSource] = field(default_factory=list)

    def data_sources(self) -> list[DataSource]:
        return [self.output_source, self.input_source, *self.extra_sources]

    def paywalled_gaps(self) -> list[str]:
        return [s.name for s in self.data_sources() if s.paywalled]

    def project(self, inputs: DriverInputs) -> list[float]:
        return project_margin_path(inputs)
