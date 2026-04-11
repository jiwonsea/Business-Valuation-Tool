"""AI-powered Discovery engine -- news analysis -> company recommendation -> scenario suggestion.

The user reviews/modifies the output before running valuation.
"""

from __future__ import annotations

import json
import sys

from .news_collector import NewsCollector


def _safe_print(text: str) -> None:
    """Print with encoding fallback for Windows cp949 consoles."""
    try:
        print(text)
    except Exception:
        try:
            enc = getattr(sys.stdout, "encoding", None) or "utf-8"
            safe = text.encode(enc, errors="replace").decode(enc, errors="replace")
            print(safe)
        except Exception:
            pass  # Last resort: silently drop non-critical console output


# Per-market search keywords
_KR_QUERIES = [
    "코스피 실적 발표",
    "한국 주식시장 이슈",
    "IPO 상장",
    "기업 인수합병 M&A",
]
_US_QUERIES = [
    "S&P 500 earnings report",
    "US stock market news",
    "IPO listing",
    "M&A acquisition deal",
]


def summarize_key_issues(
    news: list[dict],
    company_name: str,
    market: str = "KR",
) -> str:
    """Summarize valuation-relevant key issues from a news list.

    Args:
        news: NewsCollector output format [{"title", "description", "pub_date", ...}]
        company_name: Target company name
        market: "KR" | "US"

    Returns:
        Bullet-point key issues text. Empty string on failure.
    """
    if not news:
        return ""

    # Disk cache (reuse ai/analyst.py cache infrastructure)
    from ai.analyst import _get_cached, _set_cached

    cached = _get_cached(company_name, "key_issues")
    if cached:
        return cached.get("text", "")

    from ai.llm_client import ask
    from ai.prompts import SYSTEM_DISCOVERY

    news_text = "\n".join(f"- [{n['pub_date'][:10]}] {n['title']}" for n in news)

    market_label = "한국" if market == "KR" else "미국"
    prompt = f"""\
<company>{company_name} ({market_label} 시장)</company>
<news_data>
{news_text}
</news_data>

위 뉴스에서 이 기업의 밸류에이션에 영향을 줄 수 있는 핵심 이슈를 요약하세요.
카테고리별 bullet point 형식으로 5~10개 이내 핵심만 추출하세요.
밸류에이션과 무관한 뉴스는 제외하고, 각 이슈에 관련 뉴스 날짜를 포함하세요.

<example>
- [리스크] 수주 감소로 2025년 매출 하락 전망 (3월 뉴스)
- [기회] 신규 해외 프로젝트 수주 발표 예정 (3월 뉴스)
- [규제] ESG 관련 신규 규제안 국회 통과 가능성 (2월 뉴스)
</example>"""

    try:
        result = ask(prompt, system=SYSTEM_DISCOVERY, temperature=0.2, max_tokens=1024)
        if result:
            _set_cached(company_name, "key_issues", {"text": result})
        return result
    except Exception:
        return ""


class DiscoveryEngine:
    """News-based target company recommendation + scenario suggestion."""

    def __init__(self):
        self.collector = NewsCollector()

    def discover(self, market: str = "KR") -> dict:
        """Execute Discovery workflow.

        1. Collect news (past 1 month)
        2. AI analysis: issue summary + company recommendation + scenario/probability suggestion
        3. Output results (for user review)

        Returns:
            {"news_count": int, "analysis": str, "companies": list, "scenarios": list}
        """
        _safe_print(f"\n{'=' * 60}")
        _safe_print(f"[Discovery Mode] {market} 시장 뉴스 분석")
        _safe_print(f"{'=' * 60}")

        # Step 1: Collect news
        queries = _KR_QUERIES if market == "KR" else _US_QUERIES
        all_news = []
        for q in queries:
            _safe_print(f"  수집 중: '{q}'...")
            if market == "KR":
                items = self.collector.collect_kr(q, days=30, max_items=30)
            else:
                items = self.collector.collect_us(q, days=30, max_items=30)
            all_news.extend(items)
            _safe_print(f"    -> {len(items)}건")

        # Deduplicate (by title)
        seen = set()
        unique_news = []
        for n in all_news:
            if n["title"] not in seen:
                seen.add(n["title"])
                unique_news.append(n)

        _safe_print(f"\n  총 {len(unique_news)}건 수집 (중복 제거 후)")

        if not unique_news:
            _safe_print("[WARN] 수집된 뉴스가 없습니다.")
            return {
                "news_count": 0,
                "analysis": "",
                "companies": [],
                "scenarios": [],
                "news": [],
            }

        # Step 2: AI analysis
        _safe_print("[AI 분석 시작]")
        try:
            analysis = self._analyze_with_ai(unique_news, market)
        except Exception as e:
            _safe_print(f"[ERROR] AI 분석 실패: {e}")
            _safe_print("[FALLBACK] 수집된 뉴스 제목만 출력합니다.")
            for i, n in enumerate(unique_news[:20], 1):
                _safe_print(f"  {i}. {n['title']} ({n['pub_date'][:10]})")
            return {
                "news_count": len(unique_news),
                "analysis": "",
                "companies": [],
                "scenarios": [],
                "news": unique_news,
            }

        # Step 3: Output results
        _safe_print(f"\n{'=' * 60}")
        _safe_print("[분석 결과]")
        _safe_print(f"{'=' * 60}")
        _safe_print(analysis.get("summary", ""))

        if analysis.get("companies"):
            _safe_print("\n[추천 기업]")
            for i, co in enumerate(analysis["companies"], 1):
                _safe_print(f"  {i}. {co.get('name', '')} — {co.get('reason', '')}")

        if analysis.get("scenarios"):
            _safe_print("\n[시나리오 제안]")
            for sc in analysis["scenarios"]:
                _safe_print(
                    f"  {sc.get('name', '')}: 확률 {sc.get('prob', 0)}% — {sc.get('description', '')}"
                )

        _safe_print(f"\n{'=' * 60}")
        _safe_print("위 결과를 검토한 후, 다음 단계를 진행하세요:")
        _safe_print("  1. 추천 기업 중 분석 대상 선택")
        _safe_print("  2. 시나리오/확률 조정")
        _safe_print("  3. python cli.py --company <기업명> --auto")
        _safe_print(f"{'=' * 60}")

        return {
            "news_count": len(unique_news),
            "analysis": analysis.get("summary", ""),
            "companies": analysis.get("companies", []),
            "scenarios": analysis.get("scenarios", []),
            "news": unique_news,
        }

    def _analyze_with_ai(self, news: list[dict], market: str) -> dict:
        """Analyze news via Claude API."""
        from ai.llm_client import ask
        from ai.analyst import _parse_json
        from ai.prompts import SYSTEM_DISCOVERY

        # Compose news summary text (token-efficient: titles only)
        news_text = "\n".join(
            f"- [{n['pub_date'][:10]}] {n['title']}"
            for n in news[:30]  # 최대 30건 (토큰 절약)
        )

        market_label = "한국" if market == "KR" else "미국"
        prompt = f"""\
<news_data>
최근 1개월간 {market_label} 시장 주요 뉴스:
{news_text}
</news_data>

위 뉴스를 분석하여 시장 동향 요약, 밸류에이션 분석이 의미 있는 기업 추천(최대 5개), 시장 시나리오(3개, 확률 합계 100%)를 제시하세요.

<rules>
- companies는 반드시 개별 상장 기업만 포함하세요. '반도체 관련주', '방위산업 관련 기업군' 같은 섹터·테마 표현은 절대 사용하지 마세요.
- ticker: 정확히 알고 있는 경우에만 작성하고, 모르거나 불확실하면 반드시 null로 두세요. '미지정', 'N/A', '없음' 등의 문자열 금지.
- 한국 기업 ticker 형식: 숫자 6자리 (예: "005930"), 미국 기업: 알파벳 또는 점 포함 가능 (예: "NVDA", "BRK.B")
</rules>

<output_format>
{{
  "summary": "시장 전체 동향 요약 (3-5문장)",
  "companies": [
    {{"name": "개별 기업 정식 명칭", "ticker": "티커 또는 null", "reason": "분석 추천 이유"}}
  ],
  "scenarios": [
    {{"name": "시나리오명", "prob": 30, "description": "설명"}}
  ]
}}
</output_format>"""

        response = ask(
            prompt, system=SYSTEM_DISCOVERY, temperature=0.2, max_tokens=1536
        )

        try:
            return _parse_json(response)
        except (json.JSONDecodeError, ValueError):
            return {"summary": response, "companies": [], "scenarios": []}
