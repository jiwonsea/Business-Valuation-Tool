"""Pydantic 스키마: 기업 프로필, 부문 데이터, 밸류에이션 입출력 모델."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


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
    industry: Optional[str] = None

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
    bu: float  # Unlevered Beta (금융주: Equity Beta로 직접 사용)
    de: float  # D/E Ratio (%)
    tax: float  # 법인세율 (%)
    kd_pre: float  # 세전 타인자본비용 (%)
    eq_w: float  # 자기자본 비중 (%)
    is_financial: bool = False  # 금융업종 (True: Hamada 스킵, bu를 βL로 직접 사용)

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
    ke: float  # 자기자본비용 (%)
    kd_at: float  # 세후 타인자본비용 (%)
    wacc: float  # WACC (%)


# ── Equity Bridge 조정 항목 ──

class AdjustmentItem(BaseModel):
    """Equity Bridge 조정 항목.

    value > 0: EV에서 차감 (부채, 상환 등)
    value < 0: EV에 가산 (초과현금, 비영업자산 등)
    """
    name: str
    value: int  # 표시 단위 (양수=차감, 음수=가산)


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
    probability_rationale: str = ""  # 확률 할당 근거 (AI 생성)
    ddm_growth: Optional[float] = None  # 시나리오별 DDM 배당성장률 (%, None=기본값 사용)
    ev_multiple: Optional[float] = None  # 시나리오별 적용 멀티플 (Multiples 방법론)
    rim_roe_adj: float = 0.0  # ROE %p 조정 (RIM, e.g., -1.0 → 전체 ROE -1%p)
    nav_discount: float = 0.0  # 지주할인율 (NAV, e.g., 30 → NAV × 0.7)

    # DCF driver overrides (per-scenario)
    growth_adj_pct: float = 0.0  # EBITDA 성장률 % 조정 (e.g., +20 → 각 rate × 1.2)
    terminal_growth_adj: float = 0.0  # TGR 절대 조정 (e.g., +0.3 → TGR + 0.3%)
    market_sentiment_pct: float = 0.0  # 시장 심리 프리미엄/디스카운트 (EV % 조정)

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
    adjustments: list[AdjustmentItem] = []  # 동적 Equity Bridge (Excel Waterfall용)


# ── DDM ──

class DDMParams(BaseModel):
    """배당할인모델(DDM) 입력 파라미터."""
    dps: float  # 주당 배당금 (원 or $)
    dividend_growth: float = 3.0  # 배당 성장률 (%)
    buyback_per_share: float = 0.0  # 주당 자사주매입 환원액 (미국 금융주 Total Payout용)


class DDMValuationResult(BaseModel):
    """DDM 밸류에이션 결과 (Pydantic 직렬화용)."""
    dps: float
    buyback_per_share: float = 0.0
    total_payout: float = 0.0
    growth: float  # (%)
    ke: float  # (%)
    equity_per_share: int


# ── RIM (잔여이익모델) ──

class RIMParams(BaseModel):
    """잔여이익모델(RIM) 입력 파라미터 — 금융업종 특화."""
    roe_forecasts: list[float]  # 예측기간 ROE (%, e.g. [12.0, 11.5, 11.0])
    terminal_growth: float = 0.0  # RI 영구성장률 (%, 보수적 0%)
    payout_ratio: float = 30.0  # 배당성향 (%)


class RIMProjectionResult(BaseModel):
    """RIM 연도별 예측 (직렬화용)."""
    year: int
    bv: int
    net_income: int
    roe: float
    ri: int
    pv_ri: int


class RIMValuationResult(BaseModel):
    """RIM 밸류에이션 결과 (Pydantic 직렬화용)."""
    bv_current: int
    ke: float
    terminal_growth: float
    projections: list[RIMProjectionResult] = []
    pv_ri_sum: int = 0
    terminal_ri: int = 0
    pv_terminal: int = 0
    equity_value: int = 0
    per_share: int = 0


# ── NAV (자산가치평가법) ──

class NAVParams(BaseModel):
    """순자산가치(NAV) 입력 파라미터."""
    revaluation: int = 0  # 투자자산 재평가 조정액 (공정가치 − 장부가, 표시 단위)


class NAVResult(BaseModel):
    """NAV 밸류에이션 결과."""
    total_assets: int = 0
    revaluation: int = 0
    adjusted_assets: int = 0
    total_liabilities: int = 0
    nav: int = 0  # 순자산가치
    per_share: int = 0


# ── Multiples Primary (상대가치평가법 주방법론) ──

class MultiplesResult(BaseModel):
    """상대가치평가법이 주방법론일 때의 결과."""
    primary_multiple_method: str = ""  # "EV/EBITDA" | "P/E" | "P/BV"
    metric_value: float = 0.0
    multiple: float = 0.0
    enterprise_value: int = 0
    equity_value: int = 0
    per_share: int = 0


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
    valuation_method: str = "auto"  # "sotp" | "dcf_primary" | "multiples" | "ddm" | "rim" | "nav" | "auto"
    industry: str = ""  # 업종 힌트 (method_selector 자동 분기용, e.g. "은행", "software")
    segments: dict[str, dict]  # code → {"name": str, "multiple": float}
    segment_data: dict[int, dict[str, dict]]  # year → code → {"revenue", "op", "assets", ...}
    consolidated: dict[int, dict]  # year → {"revenue", "op", "dep", "amort", ...}
    wacc_params: WACCParams
    multiples: dict[str, float]  # segment code → EV/EBITDA
    scenarios: dict[str, ScenarioParams]  # scenario code → params
    dcf_params: DCFParams
    ddm_params: Optional[DDMParams] = None  # DDM용 (금융업종)
    rim_params: Optional[RIMParams] = None  # RIM용 (금융업종 — BV 기반)
    nav_params: Optional[NAVParams] = None  # NAV용 (지주사/리츠/자산중심)
    cps_principal: int = 0  # 백만원
    cps_years: int = 0
    net_debt: int = 0  # 백만원
    segment_net_debt: dict[str, int] = {}  # {segment_code: net_debt} — 금융자회사 분리 SOTP용
    eco_frontier: int = 0  # 백만원
    peers: list[PeerCompany] = []
    base_year: int = 2025
    # 교차검증용 멀티플 (0이면 해당 방법론 스킵)
    ev_revenue_multiple: float = 0.0
    pe_multiple: float = 0.0
    pbv_multiple: float = 0.0
    ps_multiple: float = 0.0  # P/S (적자 성장주 교차검증)
    pffo_multiple: float = 0.0  # P/FFO (리츠 교차검증)
    ffo: int = 0  # Funds From Operations (리츠용, 순이익+감가상각-매각이익)
    # Monte Carlo 설정
    mc_enabled: bool = False
    mc_sims: int = 10_000
    mc_multiple_std_pct: float = 15.0  # 멀티플 표준편차 (적용값 대비 %)
    mc_dlom_mean: float = 0.0  # DLOM 평균 (%)
    mc_dlom_std: float = 5.0  # DLOM 표준편차 (%)
    news_key_issues: Optional[str] = None  # 뉴스 기반 핵심 이슈 요약

    @model_validator(mode="after")
    def validate_inputs(self):
        # base_year가 consolidated에 존재하는지 확인
        if self.base_year not in self.consolidated:
            available = sorted(self.consolidated.keys())
            raise ValueError(
                f"base_year({self.base_year})에 해당하는 연결재무제표가 없습니다. "
                f"사용 가능한 연도: {available}"
            )

        # 시나리오 확률 합계 검증
        if self.scenarios:
            total_prob = sum(sc.prob for sc in self.scenarios.values())
            if abs(total_prob - 100.0) > 0.1:
                raise ValueError(
                    f"시나리오 확률 합계가 100%가 아닙니다: {total_prob:.1f}%"
                )

        # 멀티플 음수 검증
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
    primary_method: str = "sotp"  # 사용된 주 방법론 ("sotp"|"dcf_primary"|"multiples"|"ddm"|"rim"|"nav")
    wacc: WACCResult
    da_allocations: dict[int, dict[str, DAAllocation]] = {}  # SOTP용 (빈 dict = 미사용)
    sotp: dict[str, SOTPSegmentResult] = {}  # SOTP용 (빈 dict = 미사용)
    total_ev: int = 0
    scenarios: dict[str, ScenarioResult] = {}  # 시나리오 미사용 시 빈 dict
    weighted_value: int = 0  # 확률가중 주당 가치
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
    sensitivity_primary: list[SensitivityRow] = []  # 주방법론 전용 민감도
    sensitivity_primary_label: str = ""  # 민감도 테이블 제목
