"""Automatic valuation method selection — pure functions."""

# Financial sector keywords
_FINANCIAL_KEYWORDS = frozenset({
    "은행", "bank", "보험", "insurance", "증권", "securities",
    "캐피탈", "capital", "금융", "financial", "카드", "card",
    "저축", "savings", "투자", "investment",
})

# Growth/tech keywords
_GROWTH_KEYWORDS = frozenset({
    "소프트웨어", "software", "플랫폼", "platform", "클라우드", "cloud",
    "ai", "saas", "바이오", "bio", "제약", "pharma", "게임", "game",
    "인터넷", "internet", "핀테크", "fintech", "반도체", "semiconductor",
    # EV / clean energy / space (high-growth disruptors regardless of legacy sector)
    "ev ", "(ev",               # "EV & ICE", "(EV & ICE)" segment name patterns
    "electric vehicle", "전기차", "battery storage",
    "autonomous vehicle", "자율주행", "로보택시", "robotaxi",
    "space exploration", "로켓",
})

# Asset-centric / holding company keywords (REITs excluded — handled separately)
_HOLDING_KEYWORDS = frozenset({
    "지주", "holding", "holdings",
    "자산운용", "asset management",
})

# REIT/real estate keywords (NAV + P/FFO cross-validation)
_REIT_KEYWORDS = frozenset({
    "리츠", "reit", "reits",
    "부동산", "real estate", "인프라", "infrastructure",
})

# Mature/stable sector keywords (Multiples primary candidates)
_MATURE_KEYWORDS = frozenset({
    "유통", "retail", "식품", "food", "음료", "beverage",
    "통신", "telecom", "전력", "utility", "utilities",
    "건설", "construction", "화학", "chemical", "철강", "steel",
    "섬유", "textile", "운송", "transport", "logistics",
})


def classify_industry(industry: str) -> str:
    """Classify an industry string into a growth category.

    Returns:
        "growth" | "mature" | "default"
        (Financial/REIT/Holding companies do not use DCF, so return "default")
    """
    industry_lower = industry.lower()
    if not industry_lower:
        return "default"
    if any(kw in industry_lower for kw in _GROWTH_KEYWORDS):
        return "growth"
    if any(kw in industry_lower for kw in _MATURE_KEYWORDS):
        return "mature"
    return "default"


def is_financial(industry: str) -> bool:
    """Check if an industry string indicates a financial company."""
    return any(kw in industry.lower() for kw in _FINANCIAL_KEYWORDS)


def suggest_method(
    n_segments: int,
    legal_status: str = "",
    industry: str = "",
    has_peers: bool = False,
    roe: float = 0.0,
    ke: float = 0.0,
    has_ddm_params: bool = False,
    has_rim_params: bool = False,
    segment_names: list[str] | None = None,
) -> str:
    """Suggest the primary valuation method based on company characteristics.

    Args:
        n_segments: Number of business segments
        legal_status: "비상장" | "상장" | "listed" | "unlisted"
        industry: Industry hint (Korean/English)
        has_peers: Whether sufficient peer data is available
        roe: ROE (%). Used for DDM/RIM decision for financials
        ke: Cost of equity (%). Used for DDM/RIM decision for financials
        has_ddm_params: Whether DDM parameters are provided
        has_rim_params: Whether RIM parameters are provided
        segment_names: Segment name list (for mixed financial/non-financial detection)

    Returns:
        "sotp" | "dcf_primary" | "ddm" | "rim" | "multiples" | "nav"
    """
    industry_lower = industry.lower()

    # Multi-segment with mixed financial/non-financial subsidiaries -> SOTP
    # (must precede single-keyword checks to avoid mis-routing platform+bank combos)
    if n_segments > 1 and segment_names:
        has_fin_seg = any(
            any(kw in name.lower() for kw in _FINANCIAL_KEYWORDS)
            for name in segment_names
        )
        has_non_fin_seg = any(
            not any(kw in name.lower() for kw in _FINANCIAL_KEYWORDS)
            for name in segment_names
        )
        if has_fin_seg and has_non_fin_seg:
            return "sotp"

    # Financial companies -> auto-select DDM vs RIM
    if is_financial(industry):
        return _suggest_financial_method(
            roe=roe, ke=ke,
            has_ddm_params=has_ddm_params,
            has_rim_params=has_rim_params,
        )

    # REITs/Real estate -> NAV (P/FFO auto-included as cross-validation)
    if any(kw in industry_lower for kw in _REIT_KEYWORDS):
        return "nav"

    # Holding/asset-centric companies -> NAV
    if any(kw in industry_lower for kw in _HOLDING_KEYWORDS):
        return "nav"

    # Multi-segment -> SOTP (before growth check: conglomerates with growth segments
    # are better served by per-segment multiples than consolidated DCF)
    if n_segments > 1:
        return "sotp"

    # Growth/tech -> DCF (P/S cross-validation auto-included)
    if any(kw in industry_lower for kw in _GROWTH_KEYWORDS):
        return "dcf_primary"

    # Mature/stable + sufficient peers -> relative valuation (Multiples primary)
    if has_peers and any(kw in industry_lower for kw in _MATURE_KEYWORDS):
        return "multiples"

    # Single-segment -> DCF primary
    return "dcf_primary"


def _suggest_financial_method(
    roe: float = 0.0,
    ke: float = 0.0,
    has_ddm_params: bool = False,
    has_rim_params: bool = False,
) -> str:
    """Select DDM vs RIM within the financial sector.

    Decision criteria:
    - Only RIM params provided -> RIM
    - Only DDM params provided -> DDM
    - Both or neither provided:
      - Significant ROE-Ke spread (|ROE - Ke| > 2%p) -> RIM
        (Large residual income makes BV-based RIM more precise)
      - ROE ~ Ke or insufficient data -> DDM
        (Suitable for stable dividend-paying companies)

    In equity-intensive sectors like banks, ROE > Ke indicates excess returns,
    making RIM advantageous as it explicitly separates book value from
    the present value of excess earnings.
    """
    # Explicit parameter availability takes priority
    if has_rim_params and not has_ddm_params:
        return "rim"
    if has_ddm_params and not has_rim_params:
        return "ddm"

    # ROE/Ke spread-based auto decision
    if roe > 0 and ke > 0:
        spread = abs(roe - ke)
        if spread > 2.0:
            return "rim"

    return "ddm"
