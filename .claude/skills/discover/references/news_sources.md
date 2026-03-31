# News Collection Sources

## KR: Naver News Search API
- Endpoint: `https://openapi.naver.com/v1/search/news.json`
- Headers: `X-Naver-Client-Id`, `X-Naver-Client-Secret`
- Params: query, display (count), start, sort (date/sim)
- Env vars: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`
- Registration: https://developers.naver.com → Register app → Search API

## US: Google News RSS
- URL: `https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en`
- No API key required
- XML parsing: `xml.etree.ElementTree` (stdlib)

## Search Keyword Strategy
- KR: "주식시장", "코스피", "실적", "IPO", sector-specific keywords
- US: "stock market", "earnings", "S&P 500", "IPO", sector keywords
