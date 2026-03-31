"""통합 데이터 수집기 — 기업명 입력 → KR/US 자동 판별 → 재무 데이터 수집.

사용법:
    fetcher = DataFetcher()
    result = fetcher.identify("삼성E&A")   # → KR, DART
    result = fetcher.identify("Apple")     # → US, SEC EDGAR
    financials = fetcher.fetch_financials(result)
"""

import datetime
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import dart_client, dart_parser, edgar_client, edgar_parser, yahoo_finance

try:
    from . import yfinance_fetcher
except ImportError:
    yfinance_fetcher = None  # yfinance 미설치 시 기존 경로 유지

logger = logging.getLogger(__name__)


class CompanyIdentity:
    """기업 식별 결과."""

    def __init__(self, name: str, market: str, **kwargs):
        self.name = name
        self.market = market  # "KR" | "US"
        self.ticker = kwargs.get("ticker")
        self.cik = kwargs.get("cik")
        self.corp_code = kwargs.get("corp_code")
        self.legal_status = kwargs.get("legal_status", "상장" if market == "US" else "비상장")
        self.exchange_segment = kwargs.get("exchange_segment", "")  # "KOSPI" | "KOSDAQ" | ""

    def __repr__(self):
        if self.market == "KR":
            return f"<{self.name} | KR | {self.legal_status} | corp_code={self.corp_code}>"
        status = f" | OTC" if self.legal_status == "OTC" else ""
        return f"<{self.name} | US{status} | ticker={self.ticker} | CIK={self.cik}>"


def _is_korean(text: str) -> bool:
    """한글 포함 여부 판단."""
    return bool(re.search(r"[가-힣]", text))


def _is_likely_ticker(text: str) -> bool:
    """영문 대문자 1~5글자 = ticker일 가능성."""
    return bool(re.match(r"^[A-Z]{1,5}$", text.strip()))


class DataFetcher:
    """통합 데이터 수집기."""

    def __init__(self):
        self._cache: dict[str, object] = {}

    def fetch_market_price(self, identity: CompanyIdentity) -> float | None:
        """상장/OTC 기업 현재 주가 조회. 비상장이면 None 반환.

        KR 상장: KRX / Yahoo Finance (.KS)
        US 상장: Yahoo Finance
        US OTC: Yahoo Finance (OTC 종목도 커버)
        비상장: None (시장가 없음)
        """
        if identity.legal_status in ("비상장", "unlisted"):
            return None

        cache_key = f"price:{identity.market}:{identity.ticker or identity.name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        price = None
        try:
            if identity.ticker and yfinance_fetcher:
                ticker = identity.ticker
                if identity.market == "KR":
                    ticker = yfinance_fetcher.resolve_kr_ticker(ticker)
                mkt = yfinance_fetcher.fetch_market_data(ticker, identity.market)
                price = mkt.get("price", 0) if mkt else None
            elif identity.ticker:
                info = yahoo_finance.get_stock_info(identity.ticker)
                price = info.get("price", 0) if info else None
        except Exception as e:
            logger.debug("시장가 조회 실패 (%s): %s", identity.ticker, e)

        if price:
            self._cache[cache_key] = price
        return price

    def identify(self, query: str) -> CompanyIdentity | None:
        """기업명/ticker → 시장 자동 판별 + 식별.

        판별 로직:
        1. 한글 포함 → KR 우선 (DART 검색)
        2. 영문 대문자 1~5자 → US ticker 우선 (SEC 검색)
        3. 영문 일반 → SEC 검색 우선, 실패 시 DART
        """
        query = query.strip()

        cache_key = f"id:{query}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 한글 → 한국 기업
        if _is_korean(query):
            result = self._identify_kr(query)
        elif _is_likely_ticker(query):
            # 영문 ticker 패턴 → 미국 우선
            result = self._identify_us(query) or self._identify_kr(query)
        else:
            # 영문 일반 → 미국 우선, 실패 시 한국
            result = self._identify_us(query) or self._identify_kr(query)

        if result is not None:
            self._cache[cache_key] = result
        return result

    def _identify_kr(self, query: str) -> CompanyIdentity | None:
        """DART에서 한국 기업 검색 + 상장 여부 판별."""
        try:
            info = dart_client.get_corp_info(query)
        except Exception as e:
            logger.debug("DART 검색 실패 (%s): %s", query, e)
            return None

        if not info:
            return None

        legal_status = "상장" if info["is_listed"] else "비상장"
        stock_code = info.get("stock_code")

        # 상장사: KOSPI/KOSDAQ 감지
        exchange_segment = ""
        if legal_status == "상장" and stock_code and yfinance_fetcher:
            try:
                yfinance_fetcher.resolve_kr_ticker(stock_code)
                exchange_segment = yfinance_fetcher.get_exchange_segment(stock_code)
            except Exception:
                pass

        return CompanyIdentity(
            name=query,
            market="KR",
            corp_code=info["corp_code"],
            ticker=stock_code,
            legal_status=legal_status,
            exchange_segment=exchange_segment,
        )

    def _identify_us(self, query: str) -> CompanyIdentity | None:
        """SEC EDGAR에서 미국 기업 검색 + Yahoo Finance로 상장/OTC 구분."""
        try:
            results = edgar_client.search_company(query)
        except Exception as e:
            logger.debug("SEC EDGAR 검색 실패 (%s): %s", query, e)
            return None

        if not results:
            return None

        best = results[0]
        ticker = best["ticker"]

        # Yahoo Finance로 거래소 확인 → 상장/OTC 자동 분류
        legal_status = "상장"
        if ticker:
            try:
                info = yahoo_finance.get_stock_info(ticker)
                if info:
                    legal_status = yahoo_finance.classify_exchange(
                        info.get("exchange", ""),
                        info.get("exchange_code", ""),
                    )
            except Exception as e:
                logger.debug("Yahoo 거래소 조회 실패 (%s): %s", ticker, e)

        return CompanyIdentity(
            name=best["name"],
            market="US",
            ticker=ticker,
            cik=best["cik"],
            legal_status=legal_status,
        )

    def fetch_financials(
        self, identity: CompanyIdentity, years: list[int] | None = None,
    ) -> dict[int, dict]:
        """식별된 기업의 연결 재무제표 수집.

        Returns:
            {year: {"revenue": int, "op": int, "dep": int, "amort": int, ...}}
            KR: 백만원, US: $M (USD millions)
        """
        years_key = tuple(sorted(years)) if years else ()
        cache_key = f"fin:{identity.market}:{identity.corp_code or identity.cik or identity.ticker}:{years_key}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if identity.market == "US":
            result = self._fetch_us(identity, years)
        else:
            result = self._fetch_kr(identity, years)

        if result:
            self._cache[cache_key] = result
        return result

    def _fetch_us(
        self, identity: CompanyIdentity, years: list[int] | None,
    ) -> dict[int, dict]:
        """미국 기업 재무제표: yfinance 우선, SEC EDGAR fallback."""
        if identity.ticker and yfinance_fetcher:
            try:
                yf_data = yfinance_fetcher.fetch_financials(identity.ticker, "US")
                if yf_data:
                    logger.info("yfinance 재무제표 수집 성공: %s (%d년)", identity.name, len(yf_data))
                    return yf_data
            except Exception as e:
                logger.debug("yfinance 재무제표 실패, EDGAR fallback: %s", e)

        if not identity.cik:
            raise ValueError(f"CIK 없음: {identity.name}")
        return edgar_parser.parse_financials(identity.cik, years)

    def _fetch_kr(
        self, identity: CompanyIdentity, years: list[int] | None,
    ) -> dict[int, dict]:
        """한국 기업 재무제표: yfinance 우선, DART fallback."""
        # 상장사 + yfinance 사용 가능 → yfinance 우선
        if identity.legal_status == "상장" and identity.ticker and yfinance_fetcher:
            try:
                yf_data = yfinance_fetcher.fetch_financials(identity.ticker, "KR")
                if yf_data:
                    logger.info("yfinance 재무제표 수집 성공: %s (%d년)", identity.name, len(yf_data))
                    return yf_data
            except Exception as e:
                logger.debug("yfinance 재무제표 실패, DART fallback: %s", e)

        # DART fallback (비상장 또는 yfinance 실패)
        if not identity.corp_code:
            raise ValueError(f"corp_code 없음: {identity.name}")

        if years is None:
            current_year = datetime.date.today().year
            years = [current_year - 1, current_year - 2, current_year - 3]

        def _fetch_year(year: int) -> tuple[int, dict | None]:
            try:
                items = dart_client.get_financial_statements(identity.corp_code, year)
                return year, dart_parser.parse_financial_statements(items, year)
            except Exception as e:
                logger.warning("%d년 데이터 수집 실패: %s", year, e)
                return year, None

        result = {}
        with ThreadPoolExecutor(max_workers=len(years)) as pool:
            futures = {pool.submit(_fetch_year, y): y for y in years}
            for fut in as_completed(futures):
                yr, parsed = fut.result()
                if parsed is not None:
                    result[yr] = parsed

        return result

    def fetch_shares(self, identity: CompanyIdentity) -> dict:
        """발행주식수 + 시장 데이터.

        Returns:
            {"shares_total": int, "shares_ordinary": int, "price": float, ...}
        """
        cache_key = f"shares:{identity.market}:{identity.ticker or identity.corp_code or identity.name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if identity.market == "US":
            result = self._fetch_us_shares(identity)
        else:
            result = self._fetch_kr_shares(identity)

        if result and result.get("shares_total", 0) > 0:
            self._cache[cache_key] = result
        return result

    def _fetch_us_shares(self, identity: CompanyIdentity) -> dict:
        """SEC EDGAR + Yahoo Finance → 주식수, 시가총액."""
        result = {"shares_total": 0, "shares_ordinary": 0}

        # EDGAR에서 주식수
        if identity.cik:
            shares = edgar_parser.get_shares_outstanding(identity.cik)
            if shares:
                result["shares_total"] = shares
                result["shares_ordinary"] = shares

        # 시장 데이터: yfinance 우선, Yahoo Finance fallback
        if identity.ticker:
            if yfinance_fetcher:
                try:
                    mkt = yfinance_fetcher.fetch_market_data(identity.ticker, "US")
                    if mkt:
                        result["price"] = mkt.get("price", 0)
                        result["currency"] = mkt.get("currency", "USD")
                        if mkt.get("beta") is not None:
                            result["beta"] = mkt["beta"]
                        if mkt.get("market_cap"):
                            result["market_cap"] = mkt["market_cap"]
                        if mkt.get("shares_outstanding") and not result["shares_total"]:
                            result["shares_total"] = mkt["shares_outstanding"]
                            result["shares_ordinary"] = mkt["shares_outstanding"]
                except Exception:
                    pass
            if not result.get("price"):
                summary = yahoo_finance.get_quote_summary(identity.ticker)
                if summary:
                    result["price"] = summary.get("price", 0)
                    result["currency"] = "USD"
                    if not result["shares_total"] and summary.get("shares_outstanding"):
                        result["shares_total"] = summary["shares_outstanding"]
                        result["shares_ordinary"] = summary["shares_outstanding"]

        return result

    def _fetch_kr_shares(self, identity: CompanyIdentity) -> dict:
        """상장사: yfinance(시세) + DART(주식총수현황) → 비상장: 38.co.kr."""
        result = {"shares_total": 0, "shares_ordinary": 0,
                  "shares_preferred": 0, "treasury_shares": 0}

        # 상장사: yfinance(시세/beta) + DART(주식수 정밀 분류)
        if identity.legal_status in ("상장", "listed") and identity.ticker:
            # yfinance: 시세, beta, 시가총액
            if yfinance_fetcher:
                try:
                    mkt = yfinance_fetcher.fetch_market_data(identity.ticker, "KR")
                    if mkt and mkt.get("shares_outstanding"):
                        result["price"] = mkt.get("price", 0)
                        result["currency"] = "KRW"
                        # yfinance shares_outstanding → 보통주 발행 (fallback)
                        result["shares_ordinary"] = mkt["shares_outstanding"]
                        result["shares_total"] = mkt["shares_outstanding"]
                        if mkt.get("beta") is not None:
                            result["beta"] = mkt["beta"]
                        if mkt.get("market_cap"):
                            result["market_cap"] = mkt["market_cap"]
                except Exception as e:
                    logger.debug("yfinance KR 조회 실패 (%s): %s", identity.ticker, e)

            # DART 주식총수현황: 보통주/우선주/자사주 정밀 분류
            if identity.corp_code:
                try:
                    current_year = datetime.datetime.now().year
                    stock_info = dart_client.get_stock_total_info(
                        identity.corp_code, current_year - 1,
                    )
                    if stock_info and stock_info["shares_ordinary"] > 0:
                        ord_shares = stock_info["shares_ordinary"]
                        pref_shares = stock_info["shares_preferred"]
                        treasury = stock_info["treasury_ordinary"]
                        result["shares_ordinary"] = ord_shares
                        result["shares_preferred"] = pref_shares
                        result["shares_total"] = ord_shares + pref_shares
                        result["treasury_shares"] = treasury
                        logger.info(
                            "DART 주식총수: 보통주=%s, 우선주=%s, 자사주=%s",
                            f"{ord_shares:,}", f"{pref_shares:,}", f"{treasury:,}",
                        )
                except Exception as e:
                    logger.debug("DART 주식총수 조회 실패 (%s): %s", identity.corp_code, e)

            # yfinance도 DART도 실패 시 Yahoo Finance REST fallback (1회 호출)
            if result["shares_total"] == 0:
                try:
                    if yfinance_fetcher:
                        kr_ticker = yfinance_fetcher.resolve_kr_ticker(identity.ticker)
                    else:
                        kr_ticker = f"{identity.ticker}.KS"
                    summary = yahoo_finance.get_quote_summary(kr_ticker)
                    if summary:
                        if summary.get("shares_outstanding"):
                            result["shares_total"] = summary["shares_outstanding"]
                            result["shares_ordinary"] = summary["shares_outstanding"]
                        if not result.get("price") and summary.get("price"):
                            result["price"] = summary["price"]
                            result["currency"] = "KRW"
                except Exception as e:
                    logger.debug("Yahoo KR 주식수 조회 실패 (%s): %s", identity.ticker, e)

            if result["shares_total"] > 0:
                return result

        # 비상장 또는 상장 Yahoo 실패 시: 38.co.kr
        from . import market_data  # lazy: 비상장 경로에서만 사용
        info = market_data.get_38_company_info(identity.name)
        if info:
            result.update(info)

        return result
