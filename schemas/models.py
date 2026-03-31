"""Pydantic schemas: company profile, segment data, and valuation I/O models."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Company Basic Info ──

class CompanyProfile(BaseModel):
    name: str
    former_name: Optional[str] = None
    legal_status: str = "비상장"  # "비상장" | "상장" | "listed" | "unlisted"
    market: str = "KR"  # "KR" | "US"
    currency: str = "KRW"  # "KRW" | "USD"
    currency_unit: str = "백만원"  # "백만원" | "억원" | "$K" | "$M" | "$B"
    unit_multiplier: int = 1_000_000  # 1 display unit = how many KRW/$? (백만원=1e6, 억원=1e8)
    ticker: Optional[str] = None  # Listed company ticker (e.g., "AAPL", "005930")
    cik: Optional[str] = None  # SEC CIK (US only)
    corp_code: Optional[str] = None  # DART corp_code (KR only)
    parent_name: Optional[str] = None
    parent_stake_pct: Optional[float] = None
    shares_total: int  # Total shares issued (common + preferred)
    shares_ordinary: int  # Common shares issued
    shares_preferred: int = 0  # Preferred shares issued
    treasury_shares: int = 0  # Treasury shares (common basis)
    cps_conversion_shares: int = 0
    analysis_date: date = Field(default_factory=date.today)
    industry: Optional[str] = None

    @property
    def shares_outstanding(self) -> int:
        """Outstanding common shares (issued common - treasury). Basis for per-share value."""
        return max(self.shares_ordinary - self.treasury_shares, 1)

    @field_validator("shares_total")
    @classmethod
    def shares_total_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"총발행주식수는 양수여야 합니다: {v}")
        return v

    @model_validator(mode="after")
    def shares_consistency(self):
        if self.shares_ordinary > self.shares_total:
            raise ValueError(
                f"보통주({self.shares_ordinary:,})가 총주식수({self.shares_total:,})를 초과합니다"
            )
        return self


# ── Segment Data ──

class SegmentFinancials(BaseModel):
    revenue: int  # In display units
    gross_profit: int = 0
    op: int  # Operating profit (in display units)
    assets: int  # Tangible/intangible assets (in display units)


class SegmentInfo(BaseModel):
    code: str
    name: str
    multiple: float = 0.0  # EV/EBITDA


# ── Consolidated Financial Statements ──

class ConsolidatedFinancials(BaseModel):
    year: int
    revenue: int
    op: int
    net_income: int
    assets: int
    liabilities: int
    equity: int
    dep: int  # Depreciation
    amort: int  # Amortization
    gross_borr: int = 0  # Gross borrowings
    net_borr: int = 0  # Net borrowings
    de_ratio: float = 0.0  # Debt-to-equity ratio (%)

    @property
    def da(self) -> int:
        return self.dep + self.amort

    @property
    def ebitda(self) -> int:
        return self.op + self.da


# ── WACC ──

class WACCParams(BaseModel):
    rf: float  # Risk-free rate (%)
    erp: float  # Equity risk premium (%)
    bu: float  # Unlevered Beta (financials: used directly as Equity Beta)
    de: float  # D/E Ratio (%)
    tax: float  # Corporate tax rate (%)
    kd_pre: float  # Pre-tax cost of debt (%)
    eq_w: float  # Equity weight (%)
    is_financial: bool = False  # Financial sector (True: skip Hamada, use bu as βL directly)

    @field_validator("bu")
    @classmethod
    def bu_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"Unlevered Beta는 음수일 수 없습니다: {v}")
        return v

    @field_validator("eq_w")
    @classmethod
    def eq_w_range(cls, v: float) -> float:
        if not 0 < v <= 100:
            raise ValueError(f"자기자본 비중은 0~100% 범위여야 합니다: {v}%")
        return v


class WACCResult(BaseModel):
    bl: float  # Levered Beta
    ke: float  # Cost of equity (%)
    kd_at: float  # After-tax cost of debt (%)
    wacc: float  # WACC (%)


# ── Equity Bridge Adjustment Items ──

class AdjustmentItem(BaseModel):
    """Equity Bridge adjustment item.

    value > 0: deducted from EV (debt, repayment, etc.)
    value < 0: added to EV (excess cash, non-operating assets, etc.)
    """
    name: str
    value: int  # In display units (positive=deduct, negative=add)


# ── News Drivers (multiple regression independent variables) ──

_DRIVER_FIELDS = frozenset({
    "growth_adj_pct", "terminal_growth_adj", "wacc_adj",
    "market_sentiment_pct", "ddm_growth", "rim_roe_adj",
    "ev_multiple", "nav_discount",
})


class NewsDriver(BaseModel):
    """News-based independent driver (independent variable in multiple regression).

    Each key in effects corresponds to a driver field name in ScenarioParams;
    the value is the partial effect (beta). Multiplied by per-scenario weight(X) and summed.
    """
    id: str                          # "rate_hike", "tariff_shock"
    name: str                        # "금리인상 50bp"
    category: str = ""               # "macro" | "industry" | "company"
    effects: dict[str, float] = {}   # {"wacc_adj": 0.5, "growth_adj_pct": -10}
    rationale: str = ""              # Rationale / justification
    source: str = ""                 # News URL / source

    @field_validator("effects")
    @classmethod
    def validate_effect_keys(cls, v: dict[str, float]) -> dict[str, float]:
        invalid = set(v.keys()) - _DRIVER_FIELDS
        if invalid:
            raise ValueError(f"허용되지 않는 effect 키: {invalid}")
        return v


# ── Scenarios ──

class ScenarioParams(BaseModel):
    code: str
    name: str
    prob: float  # Probability (%)
    ipo: str  # "성공" | "불발"
    irr: Optional[float] = None  # FI IRR (%)
    dlom: float = 0  # DLOM (%)
    cps_repay: Optional[int] = None  # In display units (None=calculated from IRR)
    rcps_repay: int = 0
    buyback: int = 0
    shares: int  # Applicable share count
    desc: str = ""
    probability_rationale: str = ""  # Probability allocation rationale (AI-generated)
    ddm_growth: Optional[float] = None  # Per-scenario DDM dividend growth rate (%, None=use default)
    ev_multiple: Optional[float] = None  # Per-scenario applied multiple (Multiples methodology)
    rim_roe_adj: float = 0.0  # ROE %p adjustment (RIM, e.g., -1.0 -> all ROE -1%p)
    nav_discount: float = 0.0  # Holding company discount (NAV, e.g., 30 -> NAV * 0.7)

    # DCF driver overrides (per-scenario)
    growth_adj_pct: float = 0.0  # EBITDA growth rate % adjustment (e.g., +20 -> each rate * 1.2)
    terminal_growth_adj: float = 0.0  # TGR absolute adjustment (e.g., +0.3 -> TGR + 0.3%)
    market_sentiment_pct: float = 0.0  # Market sentiment premium/discount (EV % adjustment)

    # Cross-cutting driver (all discount-rate methods)
    wacc_adj: float = 0.0  # WACC %p adjustment (e.g., +0.5 -> WACC + 0.5%p; DDM/RIM applied to Ke)

    # AI analysis rationale (news -> driver mapping)
    driver_rationale: dict[str, str] = {}  # {"wacc_adj": "Reflects 50bp rate hike", ...}

    # Multi-variable news drivers (when active_drivers is set, effects are summed via resolve_drivers())
    active_drivers: Optional[dict[str, float]] = None  # {driver_id: weight(0~1)}, None=direct assignment mode

    @field_validator("wacc_adj")
    @classmethod
    def wacc_adj_range(cls, v: float) -> float:
        if not -3.0 <= v <= 3.0:
            raise ValueError(f"WACC 조정은 ±3.0%p 범위여야 합니다: {v}%p")
        return v

    @field_validator("prob")
    @classmethod
    def prob_range(cls, v: float) -> float:
        if not 0 <= v <= 100:
            raise ValueError(f"시나리오 확률은 0~100% 범위여야 합니다: {v}%")
        return v

    @field_validator("dlom")
    @classmethod
    def dlom_range(cls, v: float) -> float:
        if not 0 <= v <= 100:
            raise ValueError(f"DLOM은 0~100% 범위여야 합니다: {v}%")
        return v


class ScenarioResult(BaseModel):
    total_ev: int
    net_debt: int
    cps_repay: int
    rcps_repay: int
    buyback: int
    eco_frontier: int
    equity_value: int
    shares: int
    pre_dlom: int
    post_dlom: int
    weighted: int
    adjustments: list[AdjustmentItem] = []  # Dynamic Equity Bridge (for Excel Waterfall)


# ── DDM ──

class DDMParams(BaseModel):
    """Dividend Discount Model (DDM) input parameters."""
    dps: float  # Dividend per share (KRW or $)
    dividend_growth: float = 3.0  # Dividend growth rate (%)
    buyback_per_share: float = 0.0  # Buyback return per share (for US financial Total Payout)


class DDMValuationResult(BaseModel):
    """DDM valuation result (for Pydantic serialization)."""
    dps: float
    buyback_per_share: float = 0.0
    total_payout: float = 0.0
    growth: float  # (%)
    ke: float  # (%)
    equity_per_share: int


# ── RIM (Residual Income Model) ──

class RIMParams(BaseModel):
    """Residual Income Model (RIM) input parameters -- specialized for financials."""
    roe_forecasts: list[float]  # Forecast-period ROE (%, e.g. [12.0, 11.5, 11.0])
    terminal_growth: float = 0.0  # RI terminal growth rate (%, conservative 0%)
    payout_ratio: float = 30.0  # Dividend payout ratio (%)


class RIMProjectionResult(BaseModel):
    """RIM annual projection (for serialization)."""
    year: int
    bv: int
    net_income: int
    roe: float
    ri: int
    pv_ri: int


class RIMValuationResult(BaseModel):
    """RIM valuation result (for Pydantic serialization)."""
    bv_current: int
    ke: float
    terminal_growth: float
    projections: list[RIMProjectionResult] = []
    pv_ri_sum: int = 0
    terminal_ri: int = 0
    pv_terminal: int = 0
    equity_value: int = 0
    per_share: int = 0


# ── NAV (Net Asset Value) ──

class NAVParams(BaseModel):
    """Net Asset Value (NAV) input parameters."""
    revaluation: int = 0  # Investment asset revaluation adjustment (fair value - book value, in display units)


class NAVResult(BaseModel):
    """NAV valuation result."""
    total_assets: int = 0
    revaluation: int = 0
    adjusted_assets: int = 0
    total_liabilities: int = 0
    nav: int = 0  # Net asset value
    per_share: int = 0


# ── Multiples Primary (Relative Valuation as primary method) ──

class MultiplesResult(BaseModel):
    """Result when relative valuation (Multiples) is the primary method."""
    primary_multiple_method: str = ""  # "EV/EBITDA" | "P/E" | "P/BV"
    metric_value: float = 0.0
    multiple: float = 0.0
    enterprise_value: int = 0
    equity_value: int = 0
    per_share: int = 0


# ── DCF ──

class DCFParams(BaseModel):
    ebitda_growth_rates: Optional[list[float]] = None  # Forecast-period EBITDA growth rates (None=auto-generate)
    tax_rate: float = 22.0
    capex_to_da: float = 1.10
    nwc_to_rev_delta: float = 0.05
    terminal_growth: float = 2.5  # Terminal growth rate (%)
    # Actual Capex/NWC (used instead of ratios when available)
    actual_capex: Optional[int] = None  # Actual Capex (in display units)
    actual_nwc: Optional[int] = None  # Actual NWC (in display units)
    prior_nwc: Optional[int] = None  # Prior-period NWC (for delta NWC calculation)


class DCFProjection(BaseModel):
    year: int
    ebitda: int
    op: int
    da: int
    nopat: int
    capex: int
    delta_nwc: int
    fcff: int
    growth: float
    pv_fcff: int = 0


class DCFResult(BaseModel):
    projections: list[DCFProjection]
    pv_fcff_sum: int
    terminal_value: int
    pv_terminal: int
    ev_dcf: int
    wacc: float
    terminal_growth: float


# ── Peer ──

class PeerCompany(BaseModel):
    name: str
    segment_code: str
    ev_ebitda: float
    notes: str = ""
    ticker: Optional[str] = None  # Yahoo Finance ticker (for auto-fetch)
    market_cap: Optional[float] = None  # Market cap (in display units or $M)
    enterprise_value: Optional[float] = None
    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    pbv: Optional[float] = None
    ev_revenue: Optional[float] = None
    beta: Optional[float] = None
    source: str = "manual"  # "manual" | "yahoo" | "dart"


class PeerSegmentStats(BaseModel):
    """Per-segment peer multiple statistics."""
    segment_code: str
    segment_name: str = ""
    count: int = 0
    ev_ebitda_median: float = 0.0
    ev_ebitda_mean: float = 0.0
    ev_ebitda_q1: float = 0.0
    ev_ebitda_q3: float = 0.0
    ev_ebitda_min: float = 0.0
    ev_ebitda_max: float = 0.0
    applied_multiple: float = 0.0  # Actually applied multiple


# ── Comprehensive Valuation I/O ──

class ValuationInput(BaseModel):
    company: CompanyProfile
    valuation_method: str = "auto"  # "sotp" | "dcf_primary" | "multiples" | "ddm" | "rim" | "nav" | "auto"
    industry: str = ""  # Industry hint (for method_selector auto-routing, e.g. "은행", "software")
    segments: dict[str, dict]  # code -> {"name": str, "multiple": float}
    segment_data: dict[int, dict[str, dict]]  # year -> code -> {"revenue", "op", "assets", ...}
    consolidated: dict[int, dict]  # year -> {"revenue", "op", "dep", "amort", ...}
    wacc_params: WACCParams
    multiples: dict[str, float]  # segment code -> EV/EBITDA
    scenarios: dict[str, ScenarioParams]  # scenario code -> params
    news_drivers: list[NewsDriver] = []  # News-based independent driver catalog
    dcf_params: DCFParams
    ddm_params: Optional[DDMParams] = None  # For DDM (financial sector)
    rim_params: Optional[RIMParams] = None  # For RIM (financial sector -- BV-based)
    nav_params: Optional[NAVParams] = None  # For NAV (holding co./REITs/asset-heavy)
    cps_principal: int = 0  # In display units
    cps_years: int = 0
    net_debt: int = 0  # In display units
    segment_net_debt: dict[str, int] = {}  # {segment_code: net_debt} -- for financial subsidiary split SOTP
    eco_frontier: int = 0  # In display units
    peers: list[PeerCompany] = []
    base_year: int = 2025
    # Cross-validation multiples (0 means skip that method)
    ev_revenue_multiple: float = 0.0
    pe_multiple: float = 0.0
    pbv_multiple: float = 0.0
    ps_multiple: float = 0.0  # P/S (cross-validation for loss-making growth stocks)
    pffo_multiple: float = 0.0  # P/FFO (cross-validation for REITs)
    ffo: int = 0  # Funds From Operations (for REITs: net income + depreciation - gain on sale)
    # Monte Carlo settings
    mc_enabled: bool = False
    mc_sims: int = 10_000
    mc_multiple_std_pct: float = 15.0  # Multiple std dev (% of applied value)
    mc_dlom_mean: float = 0.0  # DLOM mean (%)
    mc_dlom_std: float = 5.0  # DLOM std dev (%)
    news_key_issues: Optional[str] = None  # News-based key issues summary

    @model_validator(mode="after")
    def validate_inputs(self):
        # Verify base_year exists in consolidated
        if self.base_year not in self.consolidated:
            available = sorted(self.consolidated.keys())
            raise ValueError(
                f"base_year({self.base_year})에 해당하는 연결재무제표가 없습니다. "
                f"사용 가능한 연도: {available}"
            )

        # Validate scenario probability sum
        if self.scenarios:
            total_prob = sum(sc.prob for sc in self.scenarios.values())
            if abs(total_prob - 100.0) > 0.1:
                raise ValueError(
                    f"시나리오 확률 합계가 100%가 아닙니다: {total_prob:.1f}%"
                )

        # Validate non-negative multiples
        for code, mult in self.multiples.items():
            if mult < 0:
                raise ValueError(f"멀티플은 음수일 수 없습니다: {code}={mult}")

        return self


class SOTPSegmentResult(BaseModel):
    ebitda: int
    multiple: float
    ev: int
    method: str = "ev_ebitda"  # "ev_ebitda" | "pbv" | "pe"
    is_equity_based: bool = False  # P/BV, P/E → True (equity bridge에서 net_debt 차감 불필요)


class DAAllocation(BaseModel):
    asset_share: float  # Asset share (%)
    da_allocated: int
    ebitda: int


class SensitivityRow(BaseModel):
    row_val: float
    col_val: float
    value: float


class MonteCarloResult(BaseModel):
    """Monte Carlo simulation result (for serialization)."""
    n_sims: int = 0
    mean: int = 0
    median: int = 0
    std: int = 0
    p5: int = 0
    p25: int = 0
    p75: int = 0
    p95: int = 0
    min_val: int = 0
    max_val: int = 0
    histogram_bins: list[int] = []
    histogram_counts: list[int] = []


class MarketComparisonResult(BaseModel):
    """Market price comparison result."""
    intrinsic_value: int = 0  # Intrinsic value (per share)
    market_price: float = 0.0  # Current market price
    gap_ratio: float = 0.0  # (intrinsic - market) / market
    flag: str = ""  # Warning message (when gap exceeds +/-50%)


class CrossValidationItem(BaseModel):
    method: str  # "SOTP (EV/EBITDA)", "DCF (FCFF)", "EV/Revenue", "P/E", "P/BV"
    metric_value: float  # Applied metric value
    multiple: float  # Applied multiple
    enterprise_value: int  # EV
    equity_value: int  # Equity Value
    per_share: int  # Per-share value


class ValuationResult(BaseModel):
    primary_method: str = "sotp"  # Primary method used ("sotp"|"dcf_primary"|"multiples"|"ddm"|"rim"|"nav")
    wacc: WACCResult
    da_allocations: dict[int, dict[str, DAAllocation]] = {}  # For SOTP (empty dict = not used)
    sotp: dict[str, SOTPSegmentResult] = {}  # For SOTP (empty dict = not used)
    total_ev: int = 0
    scenarios: dict[str, ScenarioResult] = {}  # Empty dict when scenarios not used
    weighted_value: int = 0  # Probability-weighted per-share value
    dcf: Optional[DCFResult] = None
    ddm: Optional[DDMValuationResult] = None
    rim: Optional[RIMValuationResult] = None
    nav: Optional[NAVResult] = None
    multiples_primary: Optional[MultiplesResult] = None
    cross_validations: list[CrossValidationItem] = []
    peer_stats: list[PeerSegmentStats] = []
    monte_carlo: Optional[MonteCarloResult] = None
    market_comparison: Optional[MarketComparisonResult] = None
    sensitivity_multiples: list[SensitivityRow] = []
    sensitivity_irr_dlom: list[SensitivityRow] = []
    sensitivity_dcf: list[SensitivityRow] = []
    sensitivity_primary: list[SensitivityRow] = []  # Primary method-specific sensitivity
    sensitivity_primary_label: str = ""  # Sensitivity table title
