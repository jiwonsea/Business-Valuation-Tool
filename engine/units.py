"""금액 단위 감지 및 주당가치 변환 — 순수 함수."""


def detect_unit(revenue: int, market: str) -> tuple[str, int]:
    """재무제표 규모 기반 표시 단위 자동 결정.

    Args:
        revenue: 매출액 (내부 저장 단위: 백만원 or $M)
        market: "KR" | "US"

    Returns:
        (display_label, unit_multiplier)
        - KR: 매출 < 10,000 (100억 미만) → ("백만원", 1_000_000)
              매출 10,000~1,000,000 (100억~1조) → ("억원", 100_000_000)
              매출 > 1,000,000 (1조 초과) → ("백만원", 1_000_000)
        - US: 항상 ("$M", 1_000_000)
    """
    if market == "US":
        return "$M", 1_000_000

    # KR 시장
    if revenue < 10_000:
        return "백만원", 1_000_000
    elif revenue <= 1_000_000:
        return "억원", 100_000_000
    else:
        return "백만원", 1_000_000


def per_share(equity: int, unit_multiplier: int, shares: int) -> int:
    """Equity Value를 주당 가치로 변환.

    Args:
        equity: Equity Value (표시 단위 기준)
        unit_multiplier: 1단위가 몇 원/$인지 (e.g., 1_000_000 for 백만원)
        shares: 주식수

    Returns:
        주당 가치 (원 or $)
    """
    if equity <= 0 or shares <= 0:
        return 0
    return round(equity * unit_multiplier / shares)
