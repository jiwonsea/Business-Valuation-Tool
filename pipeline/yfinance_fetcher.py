"""yfinance 기반 재무제표 및 시장 데이터 수집.

KOSPI(.KS) / KOSDAQ(.KQ) 자동 감지, 3개년 재무제표, 시장 데이터를 제공한다.
engine/ 와 달리 IO를 수행하는 pipeline 모듈이므로 httpx/yfinance 사용 가능.
"""

import logging
import os
import shutil

# ── Windows 한글 사용자명 SSL 인증서 경로 문제 해결 ──
# yfinance(curl_cffi 기반)가 유니코드 경로의 CA cert를 읽지 못하는 이슈.
# os.environ 설정만으로는 이미 로드된 네이티브 curl 라이브러리에 전달되지 않으므로,
# ctypes로 Win32 API SetEnvironmentVariableW를 직접 호출한다.
_CA_BUNDLE_PATH = "C:/ProgramData/yfinance_cacert.pem"

if os.name == "nt":
    try:
        import certifi
        ca_src = certifi.where()
        if not ca_src.isascii():
            os.makedirs(os.path.dirname(_CA_BUNDLE_PATH), exist_ok=True)
            if not os.path.exists(_CA_BUNDLE_PATH):
                shutil.copy2(ca_src, _CA_BUNDLE_PATH)
            # Python os.environ + Win32 API 양쪽 설정
            os.environ["CURL_CA_BUNDLE"] = _CA_BUNDLE_PATH
            import ctypes
            ctypes.windll.kernel32.SetEnvironmentVariableW("CURL_CA_BUNDLE", _CA_BUNDLE_PATH)
    except Exception:
        pass

import yfinance as yf

logger = logging.getLogger(__name__)

# ── KR 티커 캐시 (KOSPI/KOSDAQ 감지 결과) ──
_kr_ticker_cache: dict[str, str] = {}
_kr_exchange_cache: dict[str, str] = {}  # ticker → "KOSPI" | "KOSDAQ"


def _is_valid_yf_ticker(info: dict, raw_ticker: str) -> bool:
    """yfinance info가 유효한 종목 데이터인지 검증.

    잘못된 suffix(.KS/.KQ)로 조회하면 price가 나오더라도
    longName이 깨진 문자열("247540.KS,0P0001GZPV,...")로 반환됨.
    """
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not price or price <= 0:
        return False
    name = info.get("longName") or info.get("shortName") or ""
    # 이름이 raw ticker로 시작하면 깨진 데이터
    if name.startswith(raw_ticker):
        return False
    return True


def resolve_kr_ticker(ticker: str) -> str:
    """한국 종목 코드 → yfinance 티커 변환 (KOSPI .KS / KOSDAQ .KQ 자동 감지).

    감지 전략:
      1) .KS로 조회 → price + 유효한 longName 있으면 KOSPI
      2) .KQ로 조회 → price + 유효한 longName 있으면 KOSDAQ
      3) 양쪽 실패 → .KS fallback
    """
    if ticker in _kr_ticker_cache:
        return _kr_ticker_cache[ticker]

    # KOSPI (.KS) 시도
    ks = f"{ticker}.KS"
    try:
        t = yf.Ticker(ks)
        info = t.info or {}
        if _is_valid_yf_ticker(info, ticker):
            _kr_ticker_cache[ticker] = ks
            _kr_exchange_cache[ticker] = "KOSPI"
            return ks
    except Exception:
        pass

    # KOSDAQ (.KQ) 시도
    kq = f"{ticker}.KQ"
    try:
        t = yf.Ticker(kq)
        info = t.info or {}
        if _is_valid_yf_ticker(info, ticker):
            _kr_ticker_cache[ticker] = kq
            _kr_exchange_cache[ticker] = "KOSDAQ"
            return kq
    except Exception:
        pass

    # fallback
    _kr_ticker_cache[ticker] = ks
    _kr_exchange_cache[ticker] = "KOSPI"
    return ks


def get_exchange_segment(ticker: str) -> str:
    """캐시에서 exchange segment 반환 (resolve_kr_ticker 호출 후 사용)."""
    return _kr_exchange_cache.get(ticker, "")


def _resolve_ticker(ticker: str, market: str) -> str:
    """시장에 따라 yfinance 티커 형식으로 변환."""
    if market == "KR":
        return resolve_kr_ticker(ticker)
    return ticker  # US: 그대로


def _safe_get(df, row_labels: list[str], col_idx: int = 0):
    """DataFrame에서 여러 후보 행 이름 중 첫 매칭 값을 반환."""
    if df is None or df.empty:
        return None
    for label in row_labels:
        if label in df.index:
            try:
                val = df.loc[label].iloc[col_idx]
                if val is not None and str(val) != "nan":
                    return float(val)
            except (IndexError, TypeError):
                continue
    return None


def _scale_value(raw_val, currency: str) -> int:
    """raw 통화 값 → 백만원($M) 단위로 변환.

    yfinance는 해당 통화의 기본 단위(KRW, USD 등)로 반환.
    KRW: ÷ 1,000,000 → 백만원
    USD: ÷ 1,000,000 → $M
    기타: ÷ 1,000,000 (기본)
    """
    if raw_val is None:
        return 0
    return round(float(raw_val) / 1_000_000)


def fetch_financials(ticker: str, market: str = "US") -> dict[int, dict] | None:
    """yfinance로 3개년 재무제표 수집.

    Returns:
        {year: {revenue, op, net_income, assets, liabilities, equity,
                dep, amort, gross_borr, net_borr, de_ratio, interest_expense}}
        KR=백만원, US=$M. None if fetch fails.
    """
    resolved = _resolve_ticker(ticker, market)
    try:
        t = yf.Ticker(resolved)
        info = t.info or {}
        currency = info.get("currency", "USD" if market == "US" else "KRW")

        # 연간 재무제표 (DataFrame, columns = 날짜)
        inc = t.financials  # Income Statement
        bs = t.balance_sheet  # Balance Sheet
        cf = t.cashflow  # Cashflow

        if inc is None or inc.empty:
            logger.warning("yfinance 손익계산서 없음: %s", resolved)
            return None

    except Exception as e:
        logger.warning("yfinance 데이터 수집 실패 (%s): %s", resolved, e)
        return None

    result = {}
    # 각 컬럼(날짜)별로 처리 — 최대 3개년
    for col_idx in range(min(3, inc.shape[1] if inc is not None else 0)):
        try:
            col_date = inc.columns[col_idx]
            year = col_date.year if hasattr(col_date, "year") else int(str(col_date)[:4])
        except (IndexError, ValueError):
            continue

        def _get_inc(labels):
            return _safe_get(inc, labels, col_idx)

        def _get_bs(labels):
            return _safe_get(bs, labels, col_idx) if bs is not None else None

        def _get_cf(labels):
            return _safe_get(cf, labels, col_idx) if cf is not None else None

        # Income Statement
        revenue = _get_inc(["Total Revenue", "Revenue", "Operating Revenue"])
        op = _get_inc(["Operating Income", "EBIT", "Operating Profit"])
        net_income = _get_inc(["Net Income", "Net Income Common Stockholders",
                               "Net Income From Continuing Operations"])
        interest_expense = _get_inc(["Interest Expense", "Interest Expense Non Operating",
                                     "Net Interest Income"])

        # Balance Sheet
        assets = _get_bs(["Total Assets"])
        liabilities = _get_bs(["Total Liabilities Net Minority Interest",
                               "Total Liab", "Total Liabilities"])
        equity = _get_bs(["Stockholders Equity", "Total Equity Gross Minority Interest",
                          "Common Stock Equity", "Total Stockholder Equity"])
        total_debt = _get_bs(["Total Debt", "Net Debt"])  # 이자발생부채
        long_term_debt = _get_bs(["Long Term Debt", "Long Term Debt And Capital Lease Obligation"])
        short_term_debt = _get_bs(["Current Debt", "Current Debt And Capital Lease Obligation",
                                   "Short Long Term Debt"])
        cash = _get_bs(["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments",
                        "Cash Financial", "Cash And Short Term Investments"])

        # Cashflow — D&A
        dep_amort = _get_cf(["Depreciation And Amortization",
                             "Depreciation Amortization Depletion"])
        dep_only = _get_cf(["Depreciation"])
        amort_only = _get_cf(["Amortization Of Intangibles", "Amortization"])

        # 스케일링
        s = lambda v: _scale_value(v, currency)  # noqa: E731

        revenue_s = s(revenue)
        op_s = s(op)
        net_income_s = s(net_income)
        assets_s = s(assets)
        liabilities_s = s(liabilities)
        equity_s = s(equity)
        interest_expense_s = s(interest_expense) if interest_expense else 0

        # D&A 분리
        if dep_only is not None and amort_only is not None:
            dep_s = s(dep_only)
            amort_s = s(amort_only)
        elif dep_amort is not None:
            dep_s = s(dep_amort)
            amort_s = 0
        else:
            dep_s = 0
            amort_s = 0

        # 이자발생부채 (gross_borr)
        if total_debt is not None and total_debt > 0:
            gross_borr_s = s(total_debt)
        elif long_term_debt is not None or short_term_debt is not None:
            gross_borr_s = s(long_term_debt or 0) + s(short_term_debt or 0)
        else:
            gross_borr_s = 0

        cash_s = s(cash) if cash else 0
        net_borr_s = gross_borr_s - cash_s

        # D/E ratio (이자발생부채 / 장부자본)
        de_ratio = round(gross_borr_s / equity_s * 100, 1) if equity_s > 0 else 0.0

        result[year] = {
            "revenue": revenue_s,
            "op": op_s,
            "net_income": net_income_s,
            "assets": assets_s,
            "liabilities": liabilities_s,
            "equity": equity_s,
            "dep": dep_s,
            "amort": amort_s,
            "gross_borr": gross_borr_s,
            "net_borr": net_borr_s,
            "de_ratio": de_ratio,
            "interest_expense": interest_expense_s,
        }

    return result if result else None


def fetch_market_data(ticker: str, market: str = "US") -> dict | None:
    """yfinance에서 시장 데이터 수집.

    Returns:
        {price, market_cap, beta, industry, shares_outstanding,
         currency, exchange, exchange_code}
    """
    resolved = _resolve_ticker(ticker, market)
    try:
        t = yf.Ticker(resolved)
        info = t.info or {}
        if not info.get("regularMarketPrice") and not info.get("currentPrice"):
            logger.warning("yfinance 시장 데이터 없음: %s", resolved)
            return None

        price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        market_cap_raw = info.get("marketCap", 0)
        currency = info.get("currency", "USD" if market == "US" else "KRW")

        # market_cap: 백만원 또는 $M 단위로 변환
        market_cap = round(market_cap_raw / 1_000_000) if market_cap_raw else 0

        return {
            "price": price,
            "market_cap": market_cap,  # 백만원 / $M
            "beta": info.get("beta"),
            "industry": info.get("industry", ""),
            "shares_outstanding": info.get("sharesOutstanding", 0),
            "currency": currency,
            "exchange": info.get("exchange", ""),
            "exchange_code": info.get("exchangeTimezoneName", ""),
        }
    except Exception as e:
        logger.warning("yfinance 시장 데이터 실패 (%s): %s", resolved, e)
        return None
