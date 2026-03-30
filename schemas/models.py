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
    currency_unit: str = "백만원"  # display label: "백만원" | "$M"
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


# ── DCF ──

class DCFParams(BaseModel):
    ebitda_growth_rates: list[float]  # 예측기간 EBITDA 성장률 리스트
    tax_rate: float = 22.0
    capex_to_da: float = 1.10
    nwc_to_rev_delta: float = 0.05
    terminal_growth: float = 2.5  # 영구성장률 (%)


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


# ── 종합 밸류에이션 입출력 ──

class ValuationInput(BaseModel):
    company: CompanyProfile
    segments: dict[str, dict]  # code → {"name": str, "multiple": float}
    segment_data: dict[int, dict[str, dict]]  # year → code → {"revenue", "op", "assets", ...}
    consolidated: dict[int, dict]  # year → {"revenue", "op", "dep", "amort", ...}
    wacc_params: WACCParams
    multiples: dict[str, float]  # segment code → EV/EBITDA
    scenarios: dict[str, ScenarioParams]  # scenario code → params
    dcf_params: DCFParams
    cps_principal: int = 0  # 백만원
    cps_years: int = 0
    net_debt: int = 0  # 백만원
    eco_frontier: int = 0  # 백만원
    peers: list[PeerCompany] = []
    base_year: int = 2025


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


class ValuationResult(BaseModel):
    wacc: WACCResult
    da_allocations: dict[int, dict[str, DAAllocation]]  # year → code → allocation
    sotp: dict[str, SOTPSegmentResult]  # code → result
    total_ev: int
    scenarios: dict[str, ScenarioResult]  # scenario code → result
    weighted_value: int  # 확률가중 주당 가치
    dcf: DCFResult
    sensitivity_multiples: list[SensitivityRow] = []
    sensitivity_irr_dlom: list[SensitivityRow] = []
    sensitivity_dcf: list[SensitivityRow] = []
