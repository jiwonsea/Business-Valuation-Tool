"""통합 데이터 수집기 — 기업명 입력 → KR/US 자동 판별 → 재무 데이터 수집.

사용법:
    fetcher = DataFetcher()
    result = fetcher.identify("삼성E&A")   # → KR, DART
    result = fetcher.identify("Apple")     # → US, SEC EDGAR
    financials = fetcher.fetch_financials(result)
"""

import re

from . import dart_client, dart_parser, edgar_client, edgar_parser


class CompanyIdentity:
    """기업 식별 결과."""

    def __init__(self, name: str, market: str, **kwargs):
        self.name = name
        self.market = market  # "KR" | "US"
        self.ticker = kwargs.get("ticker")
        self.cik = kwargs.get("cik")
        self.corp_code = kwargs.get("corp_code")
        self.legal_status = kwargs.get("legal_status", "상장" if market == "US" else "비상장")

    def __repr__(self):
        if self.market == "KR":
            return f"<{self.name} | KR | corp_code={self.corp_code}>"
        return f"<{self.name} | US | ticker={self.ticker} | CIK={self.cik}>"


def _is_korean(text: str) -> bool:
    """한글 포함 여부 판단."""
    return bool(re.search(r"[가-힣]", text))


def _is_likely_ticker(text: str) -> bool:
    """영문 대문자 1~5글자 = ticker일 가능성."""
    return bool(re.match(r"^[A-Z]{1,5}$", text.strip()))


class DataFetcher:
    """통합 데이터 수집기."""

    def identify(self, query: str) -> CompanyIdentity | None:
        """기업명/ticker → 시장 자동 판별 + 식별.

        판별 로직:
        1. 한글 포함 → KR 우선 (DART 검색)
        2. 영문 대문자 1~5자 → US ticker 우선 (SEC 검색)
        3. 영문 일반 → SEC 검색 우선, 실패 시 DART
        """
        query = query.strip()

        # 한글 → 한국 기업
        if _is_korean(query):
            return self._identify_kr(query)

        # 영문 ticker 패턴 → 미국 우선
        if _is_likely_ticker(query):
            result = self._identify_us(query)
            if result:
                return result

        # 영문 일반 → 미국 우선, 실패 시 한국
        result = self._identify_us(query)
        if result:
            return result

        return self._identify_kr(query)

    def _identify_kr(self, query: str) -> CompanyIdentity | None:
        """DART에서 한국 기업 검색."""
        try:
            corp_code = dart_client.get_corp_code(query)
        except Exception:
            return None

        if not corp_code:
            return None

        return CompanyIdentity(
            name=query,
            market="KR",
            corp_code=corp_code,
        )

    def _identify_us(self, query: str) -> CompanyIdentity | None:
        """SEC EDGAR에서 미국 기업 검색."""
        try:
            results = edgar_client.search_company(query)
        except Exception:
            return None

        if not results:
            return None

        best = results[0]
        return CompanyIdentity(
            name=best["name"],
            market="US",
            ticker=best["ticker"],
            cik=best["cik"],
            legal_status="상장",
        )

    def fetch_financials(
        self, identity: CompanyIdentity, years: list[int] | None = None,
    ) -> dict[int, dict]:
        """식별된 기업의 연결 재무제표 수집.

        Returns:
            {year: {"revenue": int, "op": int, "dep": int, "amort": int, ...}}
            KR: 백만원, US: $M (USD millions)
        """
        if identity.market == "US":
            return self._fetch_us(identity, years)
        return self._fetch_kr(identity, years)

    def _fetch_us(
        self, identity: CompanyIdentity, years: list[int] | None,
    ) -> dict[int, dict]:
        """SEC EDGAR → 미국 기업 재무제표."""
        if not identity.cik:
            raise ValueError(f"CIK 없음: {identity.name}")
        return edgar_parser.parse_financials(identity.cik, years)

    def _fetch_kr(
        self, identity: CompanyIdentity, years: list[int] | None,
    ) -> dict[int, dict]:
        """DART → 한국 기업 재무제표."""
        if not identity.corp_code:
            raise ValueError(f"corp_code 없음: {identity.name}")

        if years is None:
            import datetime
            current_year = datetime.date.today().year
            years = [current_year - 1, current_year - 2, current_year - 3]

        result = {}
        for year in years:
            try:
                items = dart_client.get_financial_statements(identity.corp_code, year)
                parsed = dart_parser.parse_financial_statements(items, year)
                result[year] = parsed
            except Exception as e:
                print(f"  [WARN] {year}년 데이터 수집 실패: {e}")

        return result

    def fetch_shares(self, identity: CompanyIdentity) -> dict:
        """발행주식수 + 시장 데이터.

        Returns:
            {"shares_total": int, "shares_ordinary": int, "price": float, ...}
        """
        if identity.market == "US":
            return self._fetch_us_shares(identity)
        return self._fetch_kr_shares(identity)

    def _fetch_us_shares(self, identity: CompanyIdentity) -> dict:
        """SEC EDGAR + Yahoo Finance → 주식수, 시가총액."""
        result = {"shares_total": 0, "shares_ordinary": 0}

        # EDGAR에서 주식수
        if identity.cik:
            shares = edgar_parser.get_shares_outstanding(identity.cik)
            if shares:
                result["shares_total"] = shares
                result["shares_ordinary"] = shares

        # Yahoo Finance에서 시장 데이터
        if identity.ticker:
            from . import yahoo_finance
            info = yahoo_finance.get_stock_info(identity.ticker)
            if info:
                result["price"] = info.get("price", 0)
                result["currency"] = info.get("currency", "USD")

        return result

    def _fetch_kr_shares(self, identity: CompanyIdentity) -> dict:
        """38.co.kr / KRX → 주식수."""
        from . import market_data

        result = {"shares_total": 0, "shares_ordinary": 0}
        info = market_data.get_38_company_info(identity.name)
        if info:
            result.update(info)

        return result
