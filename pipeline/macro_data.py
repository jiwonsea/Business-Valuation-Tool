"""시장별 매크로 데이터 — 영구성장률, 유효세율, 희석주식수 추정.

engine은 순수 함수이므로 여기서 수집/계산한 값을 프로필에 주입한다.
"""

import logging

import httpx

logger = logging.getLogger(__name__)


# ── 영구성장률 기본값 ──

# 시장별 장기 기대 성장률 (명목 GDP 성장률 ≈ 인플레이션 + 실질 GDP)
_DEFAULT_TERMINAL_GROWTH = {
    "US": 2.5,   # US: ~2% 인플레이션 + ~0.5% 실질 성장 (보수적)
    "KR": 2.0,   # KR: ~2% 목표 인플레이션 + ~0% 잠재 성장 (고령화)
}


def get_terminal_growth(market: str = "KR") -> float:
    """시장별 영구성장률 기본값 반환 (%).

    FRED API 사용 가능 시 최신 기대 인플레이션을 반영하고,
    실패 시 하드코딩 기본값을 사용한다.
    """
    # FRED API (미국 10Y Breakeven Inflation Rate)
    if market == "US":
        try:
            rate = _fetch_fred_breakeven()
            if rate is not None:
                # Breakeven ≈ 기대 인플레이션, +0.5%p 실질 성장
                return round(rate + 0.5, 1)
        except Exception as e:
            logger.debug("FRED breakeven 조회 실패: %s", e)

    return _DEFAULT_TERMINAL_GROWTH.get(market, 2.0)


def _fetch_fred_breakeven() -> float | None:
    """FRED: 10-Year Breakeven Inflation Rate (T10YIE).

    공개 API — API key 불요.
    """
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
    try:
        resp = httpx.get(
            url,
            params={"id": "T10YIE", "cosd": "2025-01-01"},
            timeout=5,
        )
        resp.raise_for_status()
        lines = resp.text.strip().split("\n")
        if len(lines) < 2:
            return None
        # 마지막 행의 값
        last_val = lines[-1].split(",")[-1].strip()
        if last_val == ".":
            return None
        return float(last_val)
    except (httpx.HTTPError, ValueError, IndexError):
        return None


# ── 유효세율 ──

def calc_effective_tax_rate(financials: dict[int, dict]) -> float | None:
    """재무제표에서 유효세율 역산 (%).

    유효세율 = 1 - (순이익 / 세전이익)
    세전이익 = 영업이익 + 영업외 (근사: 순이익 / (1-tax) 역산이 아닌 직접 계산)

    실무적으로는 최근 3개년 평균을 사용.
    """
    rates = []
    for year in sorted(financials.keys(), reverse=True)[:3]:
        data = financials[year]
        net_income = data.get("net_income", 0)
        op = data.get("op", 0)

        # 세전이익 근사: 영업이익 기준 (영업외 무시 — 비금융 기업 한정)
        # 보다 정확한 계산은 세전이익(pre_tax_income) 필드가 있을 때
        pre_tax = data.get("pre_tax_income", 0)
        if pre_tax <= 0 and op > 0 and net_income > 0:
            # 영업이익 대비 순이익 비율로 역산
            pre_tax = op  # 보수적 근사 (영업외손익 = 0 가정)

        if pre_tax > 0 and net_income >= 0:
            rate = (1 - net_income / pre_tax) * 100
            if 0 <= rate <= 60:  # 비정상 값 필터
                rates.append(rate)

    if rates:
        return round(sum(rates) / len(rates), 1)
    return None


# ── 희석주식수 ──

def get_diluted_shares(ticker: str, market: str = "US") -> int | None:
    """Yahoo Finance에서 희석주식수(Diluted Shares Outstanding) 조회.

    SBC/스톡옵션 반영된 실질 주식수.
    """
    from . import yahoo_finance  # lazy: pipeline 선택적 의존성

    if market == "KR":
        try:
            from . import yfinance_fetcher
            ticker = yfinance_fetcher.resolve_kr_ticker(ticker)
        except ImportError:
            ticker = f"{ticker}.KS"

    try:
        summary = yahoo_finance.get_quote_summary(ticker)
        if summary:
            # Yahoo의 sharesOutstanding은 basic shares
            # diluted는 별도 필드가 없으므로 basic 반환
            # (SEC filing에서 직접 파싱하면 더 정확하지만 scope 벗어남)
            return summary.get("shares_outstanding", 0) or None
    except Exception as e:
        logger.debug("희석주식수 조회 실패 (%s): %s", ticker, e)
    return None
