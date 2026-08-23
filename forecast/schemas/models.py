"""Pydantic v2 schemas for the earnings forecast engine.

All engine/pipeline functions accept and return these models.
DataFrames are intentionally avoided to keep types explicit and serializable.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def quarter_period_end(label: str) -> date:
    """Calendar-quarter end date for a ``YYYYQN`` label (FY-December issuer).

    Q1->Mar 31, Q2->Jun 30, Q3->Sep 30, Q4->Dec 31. Used by the overlay
    lookahead guard; SK Hynix is a December fiscal-year filer, so reporting
    quarters coincide with calendar quarters.
    """
    year_text, quarter_text = label.split("Q", 1)
    year = int(year_text)
    quarter = int(quarter_text)
    if quarter not in (1, 2, 3, 4):
        raise ValueError(f"invalid quarter label: {label!r}")
    end_month = quarter * 3
    if end_month == 12:
        return date(year, 12, 31)
    return date(year, end_month + 1, 1) - timedelta(days=1)


# ---------------------------------------------------------------------------
# Company meta
# ---------------------------------------------------------------------------

class CompanyMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    name_kr: str
    ticker_yahoo: str
    corp_code_dart: str
    currency: str = "KRW"
    fiscal_year_end_month: int = Field(..., ge=1, le=12)
    reporting_unit: Literal["KRW", "KRW_million", "KRW_billion", "USD", "USD_million"]


class SharesOutstanding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weighted_avg_basic: int
    weighted_avg_diluted: int
    treasury_shares: int = 0
    source: str = ""


# ---------------------------------------------------------------------------
# Assumptions (input to engine)
# ---------------------------------------------------------------------------

class SegmentAssumptions(BaseModel):
    """Single-scenario segment-level driver assumptions for N quarters."""

    model_config = ConfigDict(extra="forbid")

    # DRAM
    dram_bit_growth_qoq: list[float]
    dram_hbm_share_qoq: list[float]
    dram_hbm_asp_yoy: float
    dram_ddr_asp_qoq: list[float]

    # NAND
    nand_bit_growth_qoq: list[float]
    nand_asp_qoq: list[float]

    # Other
    other_revenue_growth_qoq: list[float]

    @field_validator(
        "dram_bit_growth_qoq",
        "dram_hbm_share_qoq",
        "dram_ddr_asp_qoq",
        "nand_bit_growth_qoq",
        "nand_asp_qoq",
        "other_revenue_growth_qoq",
    )
    @classmethod
    def _must_be_non_empty(cls, v: list[float]) -> list[float]:
        if not v:
            raise ValueError("driver list must contain at least one quarter")
        return v


class MarginAssumptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sga_pct_of_revenue: float
    rnd_pct_of_revenue: float
    # Optional fixed + variable opex split (operating leverage, PLAN_opex_model.md).
    # When both are set, margin_model uses
    #   opex = opex_fixed_krw_bn + opex_variable_pct_of_revenue * revenue
    # instead of the constant (sga + rnd) % of revenue. Both-or-neither.
    opex_fixed_krw_bn: float | None = Field(default=None, ge=0.0)
    opex_variable_pct_of_revenue: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def _opex_split_both_or_neither(self) -> MarginAssumptions:
        if (self.opex_fixed_krw_bn is None) != (self.opex_variable_pct_of_revenue is None):
            raise ValueError(
                "opex_fixed_krw_bn and opex_variable_pct_of_revenue must be set together"
            )
        return self


class AnchorMargins(BaseModel):
    """Scenario-independent historical margin anchor for the cost-per-bit chain."""

    model_config = ConfigDict(extra="forbid")

    gm_hbm: float = Field(..., ge=-1.0, le=1.0)
    gm_ddr: float = Field(..., ge=-1.0, le=1.0)
    gm_nand: float = Field(..., ge=-1.0, le=1.0)
    gm_other: float = Field(..., ge=-1.0, le=1.0)
    cost_decline_qoq_hbm: float = Field(default=0.0, ge=0.0, lt=1.0)
    cost_decline_qoq_ddr: float = Field(default=0.0, ge=0.0, lt=1.0)
    cost_decline_qoq_nand: float = Field(default=0.0, ge=0.0, lt=1.0)


class MarginCarryover(BaseModel):
    """ASP factors carried from the historical anchor into the forward window."""

    model_config = ConfigDict(extra="forbid")

    asp_hbm: float = Field(default=1.0, gt=0.0)
    asp_ddr: float = Field(default=1.0, gt=0.0)
    asp_nand: float = Field(default=1.0, gt=0.0)
    periods_since_anchor: int = Field(default=0, ge=0)


class HistoricalDriver(BaseModel):
    """Historical quarter-specific drivers used by backtest."""

    model_config = ConfigDict(extra="forbid")

    quarter_label: str
    hbm_share: float = Field(..., ge=0.0, le=1.0)
    hbm_asp_qoq: float = 0.0
    ddr_asp_qoq: float = 0.0
    nand_asp_qoq: float = 0.0
    gm_overrides: dict[str, float] | None = None


class FinanceAssumptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effective_tax_rate: float = Field(..., ge=0.0, le=1.0)
    net_interest_pct_of_revenue: float


class MarginBaseline(BaseModel):
    """Prior 4Q averages used as baseline for cyclical margin function."""

    model_config = ConfigDict(extra="forbid")

    gp_margin: float | None = None
    op_margin: float | None = None
    np_margin: float | None = None
    dram_blended_asp: float | None = None
    nand_blended_asp: float | None = None
    capex_krw_bn: float | None = None


# ---------------------------------------------------------------------------
# Quarterly data (actual + forecast share the same shape)
# ---------------------------------------------------------------------------

class SegmentForecast(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str
    revenue: float


class QuarterlyActual(BaseModel):
    """Historical quarterly result from DART. Used for backtest and baseline."""

    model_config = ConfigDict(extra="forbid")

    quarter_label: str  # e.g., "2025Q4"
    period_end: date

    revenue_total: float
    revenue_by_segment: list[SegmentForecast]

    gross_profit: float
    operating_profit: float
    net_profit: float

    eps_basic: float | None = None
    eps_diluted: float | None = None


class QuarterlyForecast(BaseModel):
    """Forward projection. Same shape as QuarterlyActual but with scenario tag."""

    model_config = ConfigDict(extra="forbid")

    quarter_label: str
    scenario: Literal["bear", "base", "bull", "weighted"] = "base"

    revenue_total: float
    revenue_by_segment: list[SegmentForecast]
    hbm_share: float = Field(default=0.0, ge=0.0, le=1.0)
    asp_hbm: float = Field(default=1.0, gt=0.0)
    asp_ddr: float = Field(default=1.0, gt=0.0)
    asp_nand: float = Field(default=1.0, gt=0.0)
    margin_periods_since_anchor: int = Field(default=1, ge=0)

    gross_profit: float
    operating_profit: float
    net_profit: float

    gp_margin: float
    op_margin: float
    np_margin: float

    eps_basic: float | None = None
    eps_diluted: float | None = None


class AnnualForecast(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fiscal_year: int
    scenario: Literal["bear", "base", "bull", "weighted"] = "base"
    revenue_total: float
    operating_profit: float
    net_profit: float
    eps_basic: float | None = None


# ---------------------------------------------------------------------------
# Scenario tree
# ---------------------------------------------------------------------------

class ScenarioProbabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bear: float = Field(..., ge=0.0, le=1.0)
    base: float = Field(..., ge=0.0, le=1.0)
    bull: float = Field(..., ge=0.0, le=1.0)

    @field_validator("bull")
    @classmethod
    def _must_sum_to_one(cls, v: float, info) -> float:
        bear = info.data.get("bear", 0.0)
        base = info.data.get("base", 0.0)
        total = bear + base + v
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"scenario probabilities must sum to 1.0 (got {total})")
        return v


class ScenarioCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: Literal["bear", "base", "bull"]
    probability: float
    rationale: str
    quarterly: list[QuarterlyForecast]
    annual: list[AnnualForecast]


class ScenarioTree(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: CompanyMeta
    as_of: date

    bear: ScenarioCase
    base: ScenarioCase
    bull: ScenarioCase

    weighted_quarterly: list[QuarterlyForecast]
    weighted_annual: list[AnnualForecast]


# ---------------------------------------------------------------------------
# Consensus
# ---------------------------------------------------------------------------

class ConsensusRecord(BaseModel):
    """Snapshot of analyst consensus from yfinance."""

    model_config = ConfigDict(extra="forbid")

    ticker: str
    as_of: date

    # quarter_label -> consensus value
    revenue_estimate_quarterly: dict[str, float | None]
    eps_estimate_quarterly: dict[str, float | None]
    revenue_estimate_annual: dict[int, float | None]   # fiscal_year -> value
    eps_estimate_annual: dict[int, float | None]

    # Historical (prior 4Q): {quarter_label: {actual, estimate, surprise_pct}}
    history: dict[str, dict[str, float | None]] = Field(default_factory=dict)

    notes: list[str] = Field(default_factory=list)
    # Subset of notes that are genuine data-quality failures (e.g. implausible
    # implied net margin), NOT mere field absence. Downstream reliability guards
    # (valuation bridge) gate on quality_notes, not on every note.
    quality_notes: list[str] = Field(default_factory=list)


class ConsensusGap(BaseModel):
    """Model (base case) vs consensus, per period."""

    model_config = ConfigDict(extra="forbid")

    period_label: str        # "2026Q1" or "FY26"
    metric: Literal["revenue", "eps"]

    model_value: float
    consensus_value: float | None
    gap_abs: float | None
    gap_pct: float | None
    direction: Literal["above", "below", "in_line", "n_a"]

    interpretation: str = ""  # user fills in; engine leaves empty


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

class BacktestQuarter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quarter_label: str
    actual_revenue: float
    model_revenue: float
    revenue_error_pct: float

    actual_eps: float | None
    model_eps: float | None
    eps_error_pct: float | None

    direction_match: bool   # model predicted same sign of QoQ change as actual


class BacktestSkill(BaseModel):
    """Naive-baseline-relative skill metrics (engine.skill_metrics).

    Additive overlay on BacktestResult: absolute MAPE / direction hit-ratio are
    unjudgeable without a reference, so these score the model against a Random
    Walk (persistence) and, where vintage estimates exist, historical consensus.
    Every float is None when undefined (no rows, no EPS, no consensus, or a
    degenerate zero-error baseline) — honest about the small (8Q) sample.
    """

    model_config = ConfigDict(extra="forbid")

    naive_rw_revenue_mape: float | None  # RW absolute revenue MAPE (reference)
    naive_rw_eps_mape: float | None      # RW absolute EPS MAPE (reference)
    n: int = 0                            # quarters scored for revenue metrics
    n_eps: int = 0                        # quarters scored for EPS metrics
    mase_revenue: float | None           # model MAE / RW MAE; < 1 -> skill
    mase_eps: float | None
    theil_u2_revenue: float | None       # model RMSE / RW RMSE; < 1 -> skill
    theil_u2_eps: float | None
    rw_hit_ratio_direction: float | None  # RW's own direction hit-ratio (vs model's)
    skill_score_eps_vs_consensus: float | None  # 1 - model MAE / consensus MAE; > 0 -> skill
    surprise_direction_accuracy: float | None   # sign(model-est) == sign(actual-est)
    n_surprise_scored: int               # quarters with usable vintage consensus
    trailing_8q: BacktestSkill | None = None


class BacktestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lookback_quarters: int
    quarters: list[BacktestQuarter]

    revenue_mape: float
    eps_mape: float | None
    hit_ratio_direction: float
    bias_revenue: float   # avg signed error %
    bias_eps: float | None

    skill: BacktestSkill | None = None   # additive; None on legacy / un-wired paths


# ---------------------------------------------------------------------------
# Divergence diagnosis (workstream ①, PLAN_backtest_honesty.md)
# ---------------------------------------------------------------------------

class DriverAttribution(BaseModel):
    """Post-mortem attribution of one quarter's model-vs-actual EPS error.

    Realized-ratio bridge:
        EPS = revenue × (GP/revenue) × (OP/GP) × (NI/OP) × (1e9/shares)
    Substituting model→actual one lever at a time (in the field order below)
    and measuring the reduction in relative EPS error yields contributions that
    sum exactly to ``eps_error_total``. This explains a realized error only —
    actual ratios are never fed back into the no-look-ahead backtest.

    Each contribution maps to a YAML/assumption lever:
        revenue       → segment assumptions (bit growth, ASP, hbm_share)
        gross_margin  → anchor_margins (gm_*, cost_decline_qoq_*)
        opex          → scenario margins (sga_pct_of_revenue, rnd_pct_of_revenue)
        tax_finance   → finance (effective_tax_rate, net_interest_pct_of_revenue)
        shares        → share_count (weighted_avg_basic)
    """

    model_config = ConfigDict(extra="forbid")

    quarter_label: str
    eps_error_total: float          # (model_eps − actual_eps) / actual_eps

    contrib_revenue: float
    contrib_gross_margin: float
    contrib_opex: float
    contrib_tax_finance: float
    contrib_shares: float

    model_basic_shares: int
    actual_implied_basic_shares: float   # NI_actual × 1e9 / eps_actual


# ---------------------------------------------------------------------------
# Consensus signal layer (Phase B)
# ---------------------------------------------------------------------------

DisclosureSource = Literal["dart_mdna", "ir_deck", "fair_disclosure"]
SignalTone = Literal["up", "flat", "down"]


class DisclosureDocument(BaseModel):
    """Raw narrative text of one disclosure/IR document (input to extraction).

    Carries no interpretation — only the source text and provenance needed to
    align it to an earnings event (T0) without look-ahead.
    """

    model_config = ConfigDict(extra="forbid")

    source: DisclosureSource
    doc_date: date           # publication date (used for look-ahead checks)
    period_label: str        # reporting period the text describes, e.g. "2025Q4"
    raw_text: str
    char_count_kr: int = 0   # Korean-character count (sanity check, not OCR scan)
    url_or_path: str = ""    # DART rcpNo URL or local deck PDF path


class TopicEmphasis(BaseModel):
    """One topic the disclosure text emphasizes, with salience and polarity."""

    model_config = ConfigDict(extra="forbid")

    topic: str
    salience: float = Field(..., ge=0.0, le=1.0)
    polarity: Literal["positive", "neutral", "negative"]
    evidence_quote: str = ""


class ExtractedSignal(BaseModel):
    """Deterministic, validated structured signal from one DisclosureDocument.

    Produced by engine.signal_extractor from the raw LLM extraction. Holds no
    interpretation field — narrative reading is the user's, not the engine's.
    """

    model_config = ConfigDict(extra="forbid")

    period_label: str
    source: DisclosureSource
    topics: list[TopicEmphasis]
    guidance_tone: SignalTone
    surprise_candidates: list[str] = Field(default_factory=list)
    extracted_at: date
    model_id: str


class CallBrief(BaseModel):
    """Forward earnings-call pre-briefing: what to watch and ask next quarter."""

    model_config = ConfigDict(extra="forbid")

    as_of: date
    target_event_label: str           # the upcoming event, e.g. "2026Q2"
    top_topics: list[TopicEmphasis]
    expected_qna: list[str] = Field(default_factory=list)
    dispersion_flags: list[str] = Field(default_factory=list)
    predicted_revision_direction: Literal["up", "flat", "down", "n_a"] = "n_a"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    interpretation: str = ""          # user fills in; engine leaves empty


class SignalEventResult(BaseModel):
    """One backtest event: text signal at T0 vs realized market-adjusted CAR."""

    model_config = ConfigDict(extra="forbid")

    event_label: str
    t0: date

    car_t1: float | None = None       # CAR[T0 -> T+1d], market-adjusted
    car_t5: float | None = None       # CAR[T0 -> T+5d], secondary

    signal_tone: SignalTone
    signal_score: float               # salience-weighted tone, continuous (for IC)
    predicted_sign: int               # +1 / 0 / -1 from signal_tone

    realized_sign_t1: int | None = None   # sign(car_t1)
    direction_match_t1: bool | None = None


class SignalBacktestResult(BaseModel):
    """Event-study summary over SK Hynix earnings events (small-sample by design)."""

    model_config = ConfigDict(extra="forbid")

    events: list[SignalEventResult]
    sample_n: int
    directional_hit_ratio: float
    information_coefficient: float | None = None   # Spearman rank corr (signal vs CAR)
    calibration: dict[str, float] = Field(default_factory=dict)
    window_primary: str = "T+1d"


# ---------------------------------------------------------------------------
# Below-OP risk band + overlay layer (PLAN_tax_finance_overlay.md)
# ---------------------------------------------------------------------------
# The below-OP block (net financial / FX valuation / one-offs) is structurally
# volatile and macro-driven, so it is kept OUT of the EPS point estimate and
# expressed here as (a) a separate error band and (b) date-tagged overlays. None
# of these models touch QuarterlyForecast, so forecast EPS stays bit-identical.


class Overlay(BaseModel):
    """A date-tagged, lookahead-safe macro/timing/risk factor for one quarter.

    Overlays feed the valuation / risk-band layer, NEVER the EPS point estimate
    (CLAUDE.md two-layer split). ``magnitude`` is in valuation/risk units
    (fair-value fraction or risk-band weight) — explicitly NOT an EPS fraction.
    """

    model_config = ConfigDict(extra="forbid")

    as_of_date: date                 # when the factor became public knowledge
    target_period_label: str         # quarter it informs, e.g. "2026Q2"
    driver: str                      # e.g. "USD/KRW FX valuation loss"
    direction: Literal["risk_up", "neutral", "risk_down"]  # risk to value, not EPS sign
    magnitude: float                 # valuation/risk-layer units (NOT EPS fraction)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _reject_lookahead(self) -> Overlay:
        period_end = quarter_period_end(self.target_period_label)
        if self.as_of_date >= period_end:
            raise ValueError(
                f"overlay as_of_date {self.as_of_date} must be before the target "
                f"period_end {period_end} ({self.target_period_label}) — lookahead"
            )
        return self


class EpsRiskBandQuarter(BaseModel):
    """One forecast quarter's EPS point with its below-OP error band."""

    model_config = ConfigDict(extra="forbid")

    period_label: str
    eps_point: float                 # echoed from QuarterlyForecast, never recomputed
    eps_lower: float
    eps_upper: float


class EpsRiskBand(BaseModel):
    """Below-OP EPS error band — a SEPARATE layer over the point estimate.

    Produced by engine.risk_band and consumed by output only; QuarterlyForecast
    is unchanged, so forecast EPS / MASE / Theil / revenue stay bit-identical.
    ``method``/``k`` record how ``half_width_pct`` was seeded from the realized
    8Q below-OP block dispersion; the value itself is user-owned (profile YAML).
    """

    model_config = ConfigDict(extra="forbid")

    scenario: Literal["bear", "base", "bull", "weighted"] = "weighted"
    method: Literal["mad", "trimmed"]
    k: float
    half_width_pct: float = Field(..., ge=0.0)
    quarters: list[EpsRiskBandQuarter]
    overlays: list[Overlay] = Field(default_factory=list)
    seam_note: str = ""              # documents the overlay -> valuation/DCF seam


class BelowOpEvent(BaseModel):
    """Identified, lookahead-safe below-OP event for an optional EPS scenario.

    ``as_of_date`` is when the event's existence became knowable;
    ``amount_as_of`` is the separate date when its numeric amount became knowable.
    ``probability`` is a judgment input, not a statistically estimated frequency.
    Events are approximately separated from the existing 8Q MAD risk band: that
    sample already contains outliers, whose contribution MAD limits but does not
    eliminate. Residual overlap is non-zero and is not quantified.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    instrument: str | None = None
    as_of_date: date
    amount_as_of: date
    target_period_label: str
    kind: str
    amount_krw_bn: float
    basis: Literal["pre_tax", "after_tax", "net_income_level"]
    probability: float = Field(..., ge=0.0, le=1.0)
    confidence: Literal["estimated", "confirmed"]
    source: str
    note: str = ""
    revision_trigger: str = ""

    @model_validator(mode="after")
    def _reject_lookahead(self) -> BelowOpEvent:
        period_end = quarter_period_end(self.target_period_label)
        if self.as_of_date >= period_end:
            raise ValueError(
                f"below_op_event as_of_date {self.as_of_date} must be before the target "
                f"period_end {period_end} ({self.target_period_label}) — lookahead"
            )
        if self.amount_as_of < self.as_of_date:
            raise ValueError(
                f"below_op_event amount_as_of {self.amount_as_of} cannot precede "
                f"existence as_of_date {self.as_of_date}"
            )
        return self


class RecurringFairValueBlock(BaseModel):
    """Disclosure-only registry entry for a recurring fair-value exposure.

    The model deliberately has no fair-value gain/loss or EPS field. Carrying
    value documents exposure size; it is not injected into forecast outputs.
    """

    model_config = ConfigDict(extra="forbid")

    instrument: str
    accounting_basis: Literal["FVPL", "FVOCI", "equity_method"]
    carrying_value: int = Field(..., ge=0)
    carrying_value_as_of: date
    observable_proxy: str | None = None
    sensitivity: float | None = None
    confidence: Literal["confirmed", "estimated"]
    source: str


class EventAdjustedEpsQuarter(BaseModel):
    """No-event, realized-event, and judgment-weighted expected EPS views."""

    model_config = ConfigDict(extra="forbid")

    period_label: str
    eps_no_event: float
    eps_if_realized: float
    eps_expected: float
    events: list[BelowOpEvent]


class BelowOpEventScenario(BaseModel):
    """Output-only event-adjusted EPS scenario; never replaces forecast EPS."""

    model_config = ConfigDict(extra="forbid")

    quarters: list[EventAdjustedEpsQuarter]
    events: list[BelowOpEvent]


class ValuationBridgeResult(BaseModel):
    """Forecast EPS -> fair-value sensitivity, plus the macro overlay/risk layer.

    Two layers kept numerically separate (CLAUDE.md two-layer split):
      - Layer 1 (EPS-driven): ``fair_value_delta_pct`` = elasticity × EPS gap vs
        consensus, with a band projection from the below-OP EPS band half-width.
      - Layer 2 (macro): ``overlay_risk_score`` from date-tagged overlays — an
        entry-timing/risk signal that is NEVER folded into the layer-1 delta.

    Read-only over ScenarioTree; forecast EPS is unaffected. Event-adjusted EPS
    scenarios are deliberately not accepted here: layer 1 always uses the original
    base/weighted point estimate so one-off gains cannot flow into fair value.
    """

    model_config = ConfigDict(extra="forbid")

    fiscal_year: int
    model_eps_fy: float
    consensus_eps_fy: float | None
    eps_delta_pct: float | None          # (model - consensus) / consensus
    elasticity: float
    fair_value_delta_pct: float | None   # elasticity × eps_delta_pct (layer 1)
    fair_value_delta_low: float | None = None   # band lower projection
    fair_value_delta_high: float | None = None  # band upper projection
    overlay_risk_score: float = 0.0      # layer 2 — macro, NOT in fair_value_delta
    overlays: list[Overlay] = Field(default_factory=list)
    note: str = ""


class ValuationConfig(BaseModel):
    """Validated valuation-bridge config (profile ``valuation:`` section).

    Replaces the raw-dict passthrough so a typo or a negative elasticity fails at
    profile load rather than as a runtime arithmetic error / silent sign flip
    (Codex follow-up #2). Both knobs are user-owned drafts.
    """

    model_config = ConfigDict(extra="forbid")

    fair_value_elasticity: float = Field(default=1.2, ge=0.0)
    overlay_weight: float = Field(default=1.0, ge=0.0)
