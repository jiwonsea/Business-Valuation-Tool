# 뉴스 수집 소스

## KR: 네이버 뉴스 검색 API
- Endpoint: `https://openapi.naver.com/v1/search/news.json`
- Headers: `X-Naver-Client-Id`, `X-Naver-Client-Secret`
- Params: query, display(건수), start, sort(date/sim)
- 환경변수: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`
- 발급: https://developers.naver.com → 애플리케이션 등록 → 검색 API

## US: Google News RSS
- URL: `https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en`
- API Key 불필요
- XML 파싱: `xml.etree.ElementTree` (stdlib)

## 검색 키워드 전략
- KR: "주식시장", "코스피", "실적", "IPO", 섹터별 키워드
- US: "stock market", "earnings", "S&P 500", "IPO", sector keywords
