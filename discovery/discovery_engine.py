"""AI 기반 Discovery 엔진 — 뉴스 분석 → 기업 추천 → 시나리오 제안.

사용자가 확인/수정한 후 밸류에이션을 실행한다.
"""

from __future__ import annotations

import json

from .news_collector import NewsCollector


# 시장별 검색 키워드
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
    """뉴스 목록에서 밸류에이션 관련 핵심 이슈를 요약.

    Args:
        news: NewsCollector 출력 형식 [{"title", "description", "pub_date", ...}]
        company_name: 대상 기업명
        market: "KR" | "US"

    Returns:
        bullet-point 형태의 핵심 이슈 텍스트. 실패 시 빈 문자열.
    """
    if not news:
        return ""

    from ai.llm_client import ask

    news_text = "\n".join(
        f"- [{n['pub_date'][:10]}] {n['title']}: {n.get('description', '')}"
        for n in news
    )

    market_label = "한국" if market == "KR" else "미국"
    prompt = f"""다음은 {company_name}({market_label} 시장) 관련 최근 1개월간 뉴스입니다:

{news_text}

위 뉴스에서 이 기업의 밸류에이션에 영향을 줄 수 있는 핵심 이슈를 요약하세요.

요구사항:
- 카테고리별 bullet point 형식: [리스크], [기회], [규제], [실적], [산업동향] 등
- 각 이슈에 관련 뉴스 날짜 포함
- 밸류에이션과 무관한 뉴스는 제외
- 5~10개 이내로 핵심만 추출
- 한국어로 작성

예시 형식:
- [리스크] 수주 감소로 2025년 매출 하락 전망 (3월 뉴스)
- [기회] 신규 해외 프로젝트 수주 발표 예정 (3월 뉴스)
- [규제] ESG 관련 신규 규제안 국회 통과 가능성 (2월 뉴스)"""

    try:
        return ask(prompt, temperature=0.2)
    except Exception:
        return ""


class DiscoveryEngine:
    """뉴스 기반 분석 대상 기업 추천 + 시나리오 제안."""

    def __init__(self):
        self.collector = NewsCollector()

    def discover(self, market: str = "KR") -> dict:
        """Discovery 워크플로 실행.

        1. 뉴스 수집 (최근 1개월)
        2. AI 분석: 이슈 요약 + 기업 추천 + 시나리오/확률 제안
        3. 결과 출력 (사용자 확인용)

        Returns:
            {"news_count": int, "analysis": str, "companies": list, "scenarios": list}
        """
        print(f"\n{'='*60}")
        print(f"[Discovery Mode] {market} 시장 뉴스 분석")
        print(f"{'='*60}")

        # Step 1: 뉴스 수집
        queries = _KR_QUERIES if market == "KR" else _US_QUERIES
        all_news = []
        for q in queries:
            print(f"  수집 중: '{q}'...")
            if market == "KR":
                items = self.collector.collect_kr(q, days=30, max_items=30)
            else:
                items = self.collector.collect_us(q, days=30, max_items=30)
            all_news.extend(items)
            print(f"    → {len(items)}건")

        # 중복 제거 (제목 기준)
        seen = set()
        unique_news = []
        for n in all_news:
            if n["title"] not in seen:
                seen.add(n["title"])
                unique_news.append(n)

        print(f"\n  총 {len(unique_news)}건 수집 (중복 제거 후)")

        if not unique_news:
            print("[WARN] 수집된 뉴스가 없습니다.")
            return {"news_count": 0, "analysis": "", "companies": [], "scenarios": []}

        # Step 2: AI 분석
        print(f"\n[AI 분석 시작]")
        try:
            analysis = self._analyze_with_ai(unique_news, market)
        except Exception as e:
            print(f"[ERROR] AI 분석 실패: {e}")
            print("[FALLBACK] 수집된 뉴스 제목만 출력합니다.")
            for i, n in enumerate(unique_news[:20], 1):
                print(f"  {i}. {n['title']} ({n['pub_date'][:10]})")
            return {
                "news_count": len(unique_news),
                "analysis": "",
                "companies": [],
                "scenarios": [],
            }

        # Step 3: 결과 출력
        print(f"\n{'='*60}")
        print("[분석 결과]")
        print(f"{'='*60}")
        print(analysis.get("summary", ""))

        if analysis.get("companies"):
            print(f"\n[추천 기업]")
            for i, co in enumerate(analysis["companies"], 1):
                print(f"  {i}. {co.get('name', '')} — {co.get('reason', '')}")

        if analysis.get("scenarios"):
            print(f"\n[시나리오 제안]")
            for sc in analysis["scenarios"]:
                print(f"  {sc.get('name', '')}: 확률 {sc.get('prob', 0)}% — {sc.get('description', '')}")

        print(f"\n{'='*60}")
        print("위 결과를 검토한 후, 다음 단계를 진행하세요:")
        print("  1. 추천 기업 중 분석 대상 선택")
        print("  2. 시나리오/확률 조정")
        print("  3. python cli.py --company <기업명> --auto")
        print(f"{'='*60}")

        return {
            "news_count": len(unique_news),
            "analysis": analysis.get("summary", ""),
            "companies": analysis.get("companies", []),
            "scenarios": analysis.get("scenarios", []),
        }

    def _analyze_with_ai(self, news: list[dict], market: str) -> dict:
        """Claude API로 뉴스 분석."""
        from ai.llm_client import ask

        # 뉴스 요약 텍스트 구성 (토큰 절약을 위해 제목+설명만)
        news_text = "\n".join(
            f"- [{n['pub_date'][:10]}] {n['title']}: {n['description'][:200]}"
            for n in news[:50]  # 최대 50건
        )

        market_label = "한국" if market == "KR" else "미국"
        prompt = f"""다음은 최근 1개월간 {market_label} 시장의 주요 뉴스입니다:

{news_text}

위 뉴스를 분석하여 다음 JSON 형식으로 응답해주세요:
{{
  "summary": "시장 전체 동향 요약 (3-5문장)",
  "companies": [
    {{"name": "기업명", "ticker": "티커 (알고 있는 경우)", "reason": "분석 추천 이유"}},
    ...최대 5개
  ],
  "scenarios": [
    {{"name": "시나리오명", "prob": 확률(%), "description": "설명"}},
    ...3개 시나리오
  ]
}}

시나리오 확률 합계는 100%여야 합니다.
기업 추천은 뉴스에서 주요 이슈가 있어 밸류에이션 분석이 의미 있는 기업을 선택하세요.
"""

        response = ask(prompt)

        # JSON 파싱 시도
        try:
            # 코드 블록 내 JSON 추출
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            else:
                json_str = response

            return json.loads(json_str.strip())
        except (json.JSONDecodeError, IndexError):
            return {"summary": response, "companies": [], "scenarios": []}
