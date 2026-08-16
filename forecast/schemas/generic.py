"""Sector-agnostic (generic) forecast schemas.

The core engine (schemas/models.py, engine/segment_revenue.py, margin_model.py)
is purpose-built for memory semiconductors: revenue is modelled as DRAM/NAND
bit-volume x ASP and gross margin flows from a HBM/DDR/NAND cost-per-bit chain.
That model does not describe a software, GPU, e-commerce, EV or social company,
so forcing (e.g.) Microsoft through `dram_ddr_asp_qoq` would be meaningless.

This module adds a **top-down** generic path used for non-memory issuers:

    revenue_q      = revenue_{q-1} x (1 + revenue_growth_qoq)
    operating_prof = revenue_q x op_margin
    pretax         = operating_prof + net_interest_pct_of_revenue x revenue_q
    net_profit     = pretax x (1 - effective_tax_rate)
    eps            = net_profit x unit_scale / weighted_avg_diluted_shares

It is intentionally simpler than the memory engine: no bit/ASP decomposition,
no cost-per-bit gross-margin chain. Every driver is a directly-observable,
top-down assumption (segment growth, operating margin, tax) that can be anchored
to reported financials without fabricating unobservable unit economics.

Design rules (mirror the memory path):
- Pydantic v2, ``extra="forbid"`` — a typo in a profile fails at load, not runtime.
- Engine functions are pure; these models are their IO contract.
- Reuses ``QuarterlyForecast`` / ``AnnualForecast`` / ``ScenarioTree`` from
  schemas.models so downstream (scenario weighting, skill metrics) is shared.

Historical-EPS normalization (NVDA-1c, REVIEW_nvidia_codex.md #1/#6):
- EDGAR companyfacts EPS facts are NEVER selected as canonical data — the same
  period carries both the as-filed value and later filings' retroactively
  split-adjusted comparatives, and old quarters may have no current-basis
  comparative at all (naive selection created the 0.62B → 2.5B → 24.5B
  mixed-basis seams in the original NVDA profile).
- Instead each actual stores the AS-FILED per-quarter diluted weighted-average
  share count (+ period_end); ``split_history`` brings it to the CURRENT basis
  at load and ``eps_diluted`` is DERIVED as net_profit x unit_scale / adjusted
  shares. Real dilution/buyback variation is preserved (never recompute history
  with the fixed forward share count). As-filed EPS + accession live on in the
  row's ``source`` string as provenance.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Reporting-unit -> multiplier that converts a P&L line (stated in the unit)
# into absolute currency, so EPS = line * scale / shares is dimensionally right.
UNIT_SCALE: dict[str, float] = {
    "USD": 1.0,
    "USD_million": 1_000_000.0,
    "USD_billion": 1_000_000_000.0,
    "KRW": 1.0,
    "KRW_million": 1_000_000.0,
    "KRW_billion": 1_000_000_000.0,
}


class GenericScenarioAssumptions(BaseModel):
    """One scenario (bear/base/bull) of top-down drivers for N forward quarters.

    ``revenue_growth_qoq`` is a per-quarter QoQ growth vector (length >= N).
    ``op_margin``, ``effective_tax_rate`` and ``net_interest_pct_of_revenue`` may
    each be given as a scalar (held flat across the window) or as a per-quarter
    vector; :meth:`vec` normalises both to a length-N list.
    """

    model_config = ConfigDict(extra="forbid")

    probability: float = Field(..., ge=0.0, le=1.0)
    rationale: str = ""

    revenue_growth_qoq: list[float]
    op_margin: float | list[float]
    effective_tax_rate: float | list[float]
    net_interest_pct_of_revenue: float | list[float] = 0.0

    @model_validator(mode="after")
    def _non_empty_growth(self) -> "GenericScenarioAssumptions":
        if not self.revenue_growth_qoq:
            raise ValueError("revenue_growth_qoq must contain at least one quarter")
        return self

    @staticmethod
    def _as_vector(value: float | list[float], n: int) -> list[float]:
        if isinstance(value, list):
            if len(value) < n:
                raise ValueError(f"driver vector length {len(value)} < n_quarters {n}")
            return list(value[:n])
        return [float(value)] * n

    def growth(self, n: int) -> list[float]:
        return self._as_vector(self.revenue_growth_qoq, n)

    def margin(self, n: int) -> list[float]:
        return self._as_vector(self.op_margin, n)

    def tax(self, n: int) -> list[float]:
        return self._as_vector(self.effective_tax_rate, n)

    def net_interest(self, n: int) -> list[float]:
        return self._as_vector(self.net_interest_pct_of_revenue, n)


class GenericBacktestMethodology(GenericScenarioAssumptions):
    """Calendar-slot drivers used only by the generic historical backtest.

    Vector positions map to the target quarter (Q1->0 ... Q4->3). The fixed
    probability is inherited only to reuse the scenario driver contract;
    backtesting never probability-weights this block.
    """

    probability: Literal[1.0] = 1.0


class SplitEvent(BaseModel):
    """One stock split: shares are multiplied by ``ratio`` on ``date``.

    Explicit-assumptions convention (Codex #1): the split history lives in the
    profile YAML, auditable, instead of pre-adjusted magic numbers. A quarter
    whose ``period_end`` predates ``date`` gets its as-filed share count
    multiplied by ``ratio`` to reach today's basis. (Facts as-filed AFTER a
    split are already on the post-split basis — SEC comparatives are restated
    retroactively in the filing itself — so period_end, not filing date, is the
    right key as long as no split falls between a period end and its original
    filing; true for every NVDA/TSLA split covered here.)
    """

    model_config = ConfigDict(extra="forbid")

    date: date
    ratio: float = Field(..., gt=0.0)


class GenericSeedQuarter(BaseModel):
    """The last reported quarter — seeds revenue compounding and EPS scale."""

    model_config = ConfigDict(extra="forbid")

    quarter_label: str
    revenue_total: float
    net_profit: float | None = None
    eps_diluted: float | None = None


class GenericActualQuarter(BaseModel):
    """A reported quarter used for the offline backtest (revenue/EPS MAPE).

    Preferred form (NVDA-1c): supply ``net_profit`` + ``diluted_shares``
    (AS-FILED weighted-average diluted, from the quarter's own accession) +
    ``period_end``; ``eps_diluted`` is then DERIVED at load on the current
    share basis via the profile's ``split_history``. A directly-stored
    ``eps_diluted`` is only honoured when ``diluted_shares`` is absent
    (legacy profiles).
    """

    model_config = ConfigDict(extra="forbid")

    quarter_label: str
    revenue_total: float
    net_profit: float | None = None
    eps_diluted: float | None = None
    period_end: date | None = None
    diluted_shares: float | None = Field(None, gt=0.0)
    source: str = ""


class GenericForecastWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_quarter: str
    n_quarters: int = Field(..., ge=1, le=12)


class GenericProfile(BaseModel):
    """Full generic-company profile (parsed from profiles/<name>.generic.yaml)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    name_kr: str
    ticker: str
    currency: str
    reporting_unit: Literal[
        "USD", "USD_million", "USD_billion", "KRW", "KRW_million", "KRW_billion"
    ]
    fiscal_year_end_month: int = Field(..., ge=1, le=12)
    weighted_avg_diluted: float = Field(..., gt=0.0)

    seed: GenericSeedQuarter
    window: GenericForecastWindow
    actuals: list[GenericActualQuarter] = Field(default_factory=list)
    split_history: list[SplitEvent] = Field(default_factory=list)
    regime_break_quarter: str | None = Field(None, pattern=r"^\d{4}Q[1-4]$")
    backtest_methodology: GenericBacktestMethodology | None = None

    bear: GenericScenarioAssumptions
    base: GenericScenarioAssumptions
    bull: GenericScenarioAssumptions

    notes: list[str] = Field(default_factory=list)

    @property
    def unit_scale(self) -> float:
        return UNIT_SCALE[self.reporting_unit]

    def split_factor(self, period_end: date) -> float:
        """Multiplier taking an as-filed share count at ``period_end`` to today's basis."""
        factor = 1.0
        for event in self.split_history:
            if event.date > period_end:
                factor *= event.ratio
        return factor

    @model_validator(mode="after")
    def _probabilities_sum_to_one(self) -> "GenericProfile":
        total = self.bear.probability + self.base.probability + self.bull.probability
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"scenario probabilities must sum to 1.0 (got {total})")
        return self

    @model_validator(mode="after")
    def _derive_actual_eps(self) -> "GenericProfile":
        """NVDA-1c: derive historical EPS from NI + split-adjusted diluted shares.

        Whenever an actual carries ``diluted_shares`` the stored ``eps_diluted``
        (if any) is IGNORED and replaced by the derived, current-basis value —
        selecting EPS facts directly is exactly how the mixed-basis history was
        assembled. The fixed forward ``weighted_avg_diluted`` is deliberately
        NOT used here: per-quarter shares preserve real dilution/buyback.
        """
        for actual in self.actuals:
            if actual.diluted_shares is None:
                continue
            if actual.period_end is None:
                raise ValueError(
                    f"{actual.quarter_label}: diluted_shares requires period_end for split adjustment"
                )
            if actual.net_profit is None:
                raise ValueError(
                    f"{actual.quarter_label}: diluted_shares requires net_profit to derive EPS"
                )
            adjusted_shares = actual.diluted_shares * self.split_factor(actual.period_end)
            actual.eps_diluted = actual.net_profit * self.unit_scale / adjusted_shares
        return self
