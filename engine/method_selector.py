"""밸류에이션 방법론 자동 선택 — 순수 함수."""

# 금융 업종 키워드
_FINANCIAL_KEYWORDS = frozenset({
    "은행", "bank", "보험", "insurance", "증권", "securities",
    "캐피탈", "capital", "금융", "financial", "카드", "card",
    "저축", "savings", "투자", "investment",
})

# 성장/테크 키워드
_GROWTH_KEYWORDS = frozenset({
    "소프트웨어", "software", "플랫폼", "platform", "클라우드", "cloud",
    "ai", "saas", "바이오", "bio", "제약", "pharma", "게임", "game",
    "인터넷", "internet", "핀테크", "fintech", "반도체", "semiconductor",
})


def suggest_method(
    n_segments: int,
    legal_status: str = "",
    industry: str = "",
) -> str:
    """기업 특성에 따른 주 밸류에이션 방법론 제안.

    Args:
        n_segments: 사업부문 수
        legal_status: "비상장" | "상장" | "listed" | "unlisted"
        industry: 업종 힌트 (한글/영문)

    Returns:
        "sotp" | "dcf_primary" | "ddm" | "multiples"
    """
    industry_lower = industry.lower()

    # 금융회사 → DDM 또는 P/BV
    if any(kw in industry_lower for kw in _FINANCIAL_KEYWORDS):
        return "ddm"

    # 성장/테크 → DCF (Revenue 기반 교차검증)
    if any(kw in industry_lower for kw in _GROWTH_KEYWORDS):
        return "dcf_primary"

    # 다부문 → SOTP
    if n_segments > 1:
        return "sotp"

    # 단일부문 → DCF primary
    return "dcf_primary"
