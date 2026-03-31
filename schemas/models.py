"""Pydantic 스키마: 기업 프로필, 부문 데이터, 밸류에이션 입출력 모델."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# ── 기업 기본 정보 ──

class CompanyProfile(BaseModel):
    name: str
    former_name: Optional[str] = None
    legal_status: str = "비상장"  # "비상장" | "상장" | "listed" | "unlisted"
    market: str = "KR"  # "KR" | "US"
    currency: str = "KRW"  # "KRW" | "USD"
    currency_unit: str = "백만원"  # "백만원" | "억원" | "$K" | "$M" | "$B"
    unit_multiplier: int = 1_000_000  # 1표시단위 = 몇 원/$? (백만원=1e6, 억원=1e8)
    ticker: Optional[str] = None  # 상장사 ticker (e.g., "AAPL", "005930")
    cik: Optional[str] = None  # SEC CIK (US only)
    corp_code: Optional[str] = None  # DART corp_code (KR only)
    parent_name: Optional[str] = None
    parent_stake_pct: Optional[float] = None
    shares_total: int
    shares_ordinary: int
    shares_preferred: int = 0  # CPS/우선주
    cps_conversion_shares: int = 0
    analysis_date: date = Field(default_factory=date.today)


# ── 부문(Segment) 데이터 ──

class SegmentFinancials(BaseModel):
    revenue: int  # 백만원
    gross_profit: int = 0
    op: int  # 영업이익 (백만원)
    assets: int  # 유무형자산 (백만원)


class SegmentInfo(BaseModel):
    code: str
    name: str
    multiple: float = 0.0  # EV/EBITDA


# ── 연결 재무제표 ──

class ConsolidatedFinancials(BaseModel):
    year: int
    revenue: int
    op: int
    net_income: int
    assets: int
    liabilities: int
    equity: int
    dep: int  # 감가상각비
    amort: int  # 무형자산상각비
    gross_borr: int = 0  # 총차입금
    net_borr: int = 0  # 순차입금
    de_ratio: float = 0.0  # 부채비율 (%)

    @property
    def da(self) -> int:
        return self.dep + self.amort

    @property
    def ebitda(self) -> int:
        return self.op + self.da


# ── WACC ──

class WACCParams(BaseModel):
    rf: float  # 무위험이자율 (%)
    erp: float  # 주식위험프리미엄 (%)
    bu: float  # Unlevered Beta
    de: float  # D/E Ratio (%)
    tax: float  # 법인세율 (%)
    kd_pre: float  # 세전 타인자본비용 (%)
    eq_w: float  # 자기자본 비중 (%)


class WACCResult(BaseModel):
    bl: float  # Levered Beta
    ke: float  # 자기자본비용 (%)
    kd_at: float  # 세후 타인자본비용 (%)
    wacc: float  # WACC (%)


# ── 시나리오 ──

class ScenarioParams(BaseModel):
    code: str
    name: str
    prob: float  # 확률 (%)
    ipo: str  # "성공" | "불발"
    irr: Optional[float] = None  # FI IRR (%)
    dlom: float = 0  # DLOM (%)
    cps_repay: Optional[int] = None  # 백만원 (None=IRR 기반 계산)
    rcps_repay: int = 0
    buyback: int = 0
    shares: int  # 적용 주식수
    desc: str = ""


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


# ── DDM ──

class DDMParams(BaseModel):
    """배당할인모델(DDM) 입력 파라미터."""
    dps: float  # 주당 배당금 (원 or $)
    dividend_growth: float = 3.0  # 배당 성장률 (%)


class DDMValuationResult(BaseModel):
    """DDM 밸류에이션 결과 (Pydantic 직렬화용)."""
    dps: float
    growth: float  # (%)
    ke: float  # (%)
    equity_per_share: int


# ── DCF ──

class DCFParams(BaseModel):
    ebitda_growth_rates: list[float]  # 예측기간 EBITDA 성장률 리스트
    tax_rate: float = 22.0
    capex_to_da: float = 1.10
    nwc_to_rev_delta: float = 0.05
    terminal_growth: float = 2.5  # 영구성장률 (%)
    # 실제 Capex/NWC (있으면 ratio 대신 사용)
    actual_capex: Optional[int] = None  # 실제 Capex (백만원/$M)
    actual_nwc: Optional[int] = None  # 실제 NWC (백만원/$M)
    prior_nwc: Optional[int] = None  # 전기 NWC (ΔNWC 계산용)


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
    ticker: Optional[str] = None  # Yahoo Finance ticker (자동 fetch용)
    market_cap: Optional[float] = None  # 시가총액 (백만원 or $M)
    enterprise_value: Optional[float] = None
    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    pbv: Optional[float] = None
    ev_revenue: Optional[float] = None
    beta: Optional[float] = None
    source: str = "manual"  # "manual" | "yahoo" | "dart"


class PeerSegmentStats(BaseModel):
    """부문별 Peer 멀티플 통계."""
    segment_code: str
    segment_name: str = ""
    count: int = 0
    ev_ebitda_median: float = 0.0
    ev_ebitda_mean: float = 0.0
    ev_ebitda_q1: float = 0.0
    ev_ebitda_q3: float = 0.0
    ev_ebitda_min: float = 0.0
    ev_ebitda_max: float = 0.0
    applied_multiple: float = 0.0  # 실제 적용된 멀티플


# ── 종합 밸류에이션 입출력 ──

class ValuationInput(BaseModel):
    company: CompanyProfile
    valuation_method: str = "auto"  # "sotp" | "dcf_primary" | "multiples" | "ddm" | "auto"
    industry: str = ""  # 업종 힌트 (method_selector 자동 분기용, e.g. "은행", "software")
    segments: dict[str, dict]  # code → {"name": str, "multiple": float}
    segment_data: dict[int, dict[str, dict]]  # year → code → {"revenue", "op", "assets", ...}
    consolidated: dict[int, dict]  # year → {"revenue", "op", "dep", "amort", ...}
    wacc_params: WACCParams
    multiples: dict[str, float]  # segment code → EV/EBITDA
    scenarios: dict[str, ScenarioParams]  # scenario code → params
    dcf_params: DCFParams
    ddm_params: Optional[DDMParams] = None  # DDM용 (금융업종)
    cps_principal: int = 0  # 백만원
    cps_years: int = 0
    net_debt: int = 0  # 백만원
    eco_frontier: int = 0  # 백만원
    peers: list[PeerCompany] = []
    base_year: int = 2025
    # 교차검증용 멀티플 (0이면 해당 방법론 스킵)
    ev_revenue_multiple: float = 0.0
    pe_multiple: float = 0.0
    pbv_multiple: float = 0.0
    # Monte Carlo 설정
    mc_enabled: bool = False
    mc_sims: int = 10_000
    mc_multiple_std_pct: float = 15.0  # 멀티플 표준편차 (적용값 대비 %)
    mc_dlom_mean: float = 0.0  # DLOM 평균 (%)
    mc_dlom_std: float = 5.0  # DLOM 표준편차 (%)


class SOTPSegmentResult(BaseModel):
    ebitda: int
    multiple: float
    ev: int


class DAAllocation(BaseModel):
    asset_share: float  # (%)
    da_allocated: int
    ebitda: int


class SensitivityRow(BaseModel):
    row_val: float
    col_val: float
    value: float


class MonteCarloResult(BaseModel):
    """Monte Carlo 시뮬레이션 결과 (직렬화용)."""
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
    """시장가격 비교 결과."""
    intrinsic_value: int = 0  # 내재가치 (주당)
    market_price: float = 0.0  # 현재 시장가
    gap_ratio: float = 0.0  # (내재 - 시장) / 시장
    flag: str = ""  # 경고 메시지 (괴리율 ±50% 초과 시)


class CrossValidationItem(BaseModel):
    method: str  # "SOTP (EV/EBITDA)", "DCF (FCFF)", "EV/Revenue", "P/E", "P/BV"
    metric_value: float  # 적용 지표값
    multiple: float  # 적용 배수
    enterprise_value: int  # EV
    equity_value: int  # Equity Value
    per_share: int  # 주당 가치


class ValuationResult(BaseModel):
    primary_method: str = "sotp"  # 사용된 주 방법론
    wacc: WACCResult
    da_allocations: dict[int, dict[str, DAAllocation]] = {}  # SOTP용 (빈 dict = 미사용)
    sotp: dict[str, SOTPSegmentResult] = {}  # SOTP용 (빈 dict = 미사용)
    total_ev: int = 0
    scenarios: dict[str, ScenarioResult] = {}  # 시나리오 미사용 시 빈 dict
    weighted_value: int = 0  # 확률가중 주당 가치
    dcf: Optional[DCFResult] = None
    ddm: Optional[DDMValuationResult] = None
    cross_validations: list[CrossValidationItem] = []
    peer_stats: list[PeerSegmentStats] = []
    monte_carlo: Optional[MonteCarloResult] = None
    market_comparison: Optional[MarketComparisonResult] = None
    sensitivity_multiples: list[SensitivityRow] = []
    sensitivity_irr_dlom: list[SensitivityRow] = []
    sensitivity_dcf: list[SensitivityRow] = []
