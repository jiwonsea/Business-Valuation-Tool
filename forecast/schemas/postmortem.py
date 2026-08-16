"""Schemas for generic post-earnings scoring and attribution."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from schemas.models import BacktestSkill


class Provenance(BaseModel):
    """Source metadata for a released actual."""

    model_config = ConfigDict(extra="forbid")

    source: str
    as_of: str


class GenericActualRelease(BaseModel):
    """Actual inputs available after an earnings release.

    Core financial fields remain optional so the input file can be populated
    progressively. Scoring fails closed until the required 4-lever fields exist.
    """

    model_config = ConfigDict(extra="forbid")

    quarter_label: str = Field(pattern=r"^\d{4}Q[1-4]$")
    provenance: Provenance
    revenue_total: float | None = None
    gaap_eps_diluted: float | None = None
    diluted_shares: float | None = Field(default=None, gt=0)
    operating_income: float | None = None
    net_income: float | None = None
    automotive_revenue: float | None = None
    energy_revenue: float | None = None
    services_revenue: float | None = None
    automotive_gross_margin_ex_credits: float | None = None
    regulatory_credits: float | None = None
    other_income_expense: float | None = None
    non_gaap_eps: float | None = None
    stock_based_compensation: float | None = None


class FrozenPoint(BaseModel):
    """One immutable FROZEN forecast comparand."""

    model_config = ConfigDict(extra="forbid")

    revenue_total: float
    operating_income: float
    net_income: float
    eps_diluted: float
    diluted_shares: float = Field(gt=0)


class PointError(BaseModel):
    """Signed and absolute error for one forecast point."""

    model_config = ConfigDict(extra="forbid")

    forecast: float
    actual: float
    error: float
    mape: float
    bias: float


class FourLeverAttribution(BaseModel):
    """Additive four-lever decomposition of model EPS minus actual EPS."""

    model_config = ConfigDict(extra="forbid")

    eps_error_total: float
    revenue: float
    operating_margin: float
    op_to_ni: float
    share_count: float
    residual: float


class SegmentError(BaseModel):
    """Optional segment revenue error."""

    model_config = ConfigDict(extra="forbid")

    segment: str
    forecast: float
    actual: float
    error: float
    mape: float


class TeslaSpecialAttribution(BaseModel):
    """Realized automotive gross-profit components and GAAP bridge."""

    model_config = ConfigDict(extra="forbid")

    automotive_gross_profit_ex_credits: float | None = None
    regulatory_credits: float | None = None
    automotive_gross_profit_including_credits: float | None = None
    other_income_expense: float | None = None
    gaap_to_non_gaap_eps_gap: float | None = None
    sbc_per_diluted_share: float | None = None
    non_sbc_bridge_per_share: float | None = None


class GenericPostmortemResult(BaseModel):
    """Complete one-quarter postmortem result."""

    model_config = ConfigDict(extra="forbid")

    quarter_label: str
    provenance: Provenance
    revenue_base: PointError
    revenue_weighted: PointError
    eps_base: PointError
    eps_weighted: PointError
    attribution: FourLeverAttribution
    skill: BacktestSkill
    segments: list[SegmentError]
    tesla: TeslaSpecialAttribution | None = None
