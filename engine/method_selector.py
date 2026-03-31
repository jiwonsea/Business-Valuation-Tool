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

# 자산중심 / 지주사 키워드 (리츠 제외 — 리츠는 별도 처리)
_HOLDING_KEYWORDS = frozenset({
    "지주", "holding", "holdings",
    "자산운용", "asset management",
})

# 리츠/부동산 키워드 (NAV + P/FFO 교차검증)
_REIT_KEYWORDS = frozenset({
    "리츠", "reit", "reits",
    "부동산", "real estate", "인프라", "infrastructure",
})

# 성숙/안정 업종 키워드 (Multiples primary 후보)
_MATURE_KEYWORDS = frozenset({
    "유통", "retail", "식품", "food", "음료", "beverage",
    "통신", "telecom", "전력", "utility", "utilities",
    "건설", "construction", "화학", "chemical", "철강", "steel",
    "섬유", "textile", "운송", "transport", "logistics",
})


def suggest_method(
    n_segments: int,
    legal_status: str = "",
    industry: str = "",
    has_peers: bool = False,
    roe: float = 0.0,
    ke: float = 0.0,
    has_ddm_params: bool = False,
    has_rim_params: bool = False,
) -> str:
    """기업 특성에 따른 주 밸류에이션 방법론 제안.

    Args:
        n_segments: 사업부문 수
        legal_status: "비상장" | "상장" | "listed" | "unlisted"
        industry: 업종 힌트 (한글/영문)
        has_peers: Peer 데이터 충분 여부
        roe: ROE (%). 금융주 DDM/RIM 판단에 사용
        ke: 자기자본비용 (%). 금융주 DDM/RIM 판단에 사용
        has_ddm_params: DDM 파라미터 존재 여부
        has_rim_params: RIM 파라미터 존재 여부

    Returns:
        "sotp" | "dcf_primary" | "ddm" | "rim" | "multiples" | "nav"
    """
    industry_lower = industry.lower()

    # 금융회사 → DDM vs RIM 자동 판단
    if any(kw in industry_lower for kw in _FINANCIAL_KEYWORDS):
        return _suggest_financial_method(
            roe=roe, ke=ke,
            has_ddm_params=has_ddm_params,
            has_rim_params=has_rim_params,
        )

    # 리츠/부동산 → NAV (P/FFO는 교차검증으로 자동 포함)
    if any(kw in industry_lower for kw in _REIT_KEYWORDS):
        return "nav"

    # 지주사/자산중심 → NAV
    if any(kw in industry_lower for kw in _HOLDING_KEYWORDS):
        return "nav"

    # 성장/테크 → DCF (P/S 교차검증 자동 포함)
    if any(kw in industry_lower for kw in _GROWTH_KEYWORDS):
        return "dcf_primary"

    # 다부문 → SOTP
    if n_segments > 1:
        return "sotp"

    # 성숙/안정 + Peer 충분 → 상대가치 (Multiples primary)
    if has_peers and any(kw in industry_lower for kw in _MATURE_KEYWORDS):
        return "multiples"

    # 단일부문 → DCF primary
    return "dcf_primary"


def _suggest_financial_method(
    roe: float = 0.0,
    ke: float = 0.0,
    has_ddm_params: bool = False,
    has_rim_params: bool = False,
) -> str:
    """금융업종 내 DDM vs RIM 판단.

    판단 기준:
    - RIM 파라미터만 있으면 → RIM
    - DDM 파라미터만 있으면 → DDM
    - 둘 다 있거나 둘 다 없으면:
      - ROE와 Ke 차이가 유의미하면(|ROE - Ke| > 2%p) → RIM
        (잔여이익이 크면 BV 기반 RIM이 더 정교)
      - ROE ≈ Ke 이거나 데이터 부족 → DDM
        (안정적 배당 기업에 적합)

    은행처럼 자기자본이 핵심인 업종에서 ROE > Ke는 초과이익 존재를 의미하므로
    장부가치 + 초과이익의 현재가치를 명시적으로 분리하는 RIM이 유리하다.
    """
    # 명시적 파라미터 제공 시 우선
    if has_rim_params and not has_ddm_params:
        return "rim"
    if has_ddm_params and not has_rim_params:
        return "ddm"

    # ROE/Ke 기반 자동 판단
    if roe > 0 and ke > 0:
        spread = abs(roe - ke)
        if spread > 2.0:
            return "rim"

    return "ddm"
