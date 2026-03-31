"""시장가격 비교 — 내재가치 vs 현재 주가 괴리율 계산. 순수 함수."""

from dataclasses import dataclass


@dataclass
class MarketComparison:
    intrinsic_value: int  # 주당 내재가치
    market_price: float  # 현재 시장가
    gap_ratio: float  # (intrinsic - market) / market
    flag: str  # 경고 메시지 (빈 문자열 = 정상)


def compare_to_market(
    intrinsic: int,
    market_price: float,
    threshold: float = 0.5,
) -> MarketComparison:
    """내재가치와 시장가격 비교.

    Args:
        intrinsic: 주당 내재가치 (원 or $)
        market_price: 현재 주가 (원 or $)
        threshold: 경고 임계값 (기본 0.5 = ±50%)

    Returns:
        MarketComparison with gap_ratio and optional warning flag
    """
    if market_price <= 0:
        return MarketComparison(
            intrinsic_value=intrinsic,
            market_price=market_price,
            gap_ratio=0.0,
            flag="시장가격 데이터 없음",
        )

    gap = (intrinsic - market_price) / market_price

    flag = ""
    if abs(gap) >= 1.0:
        flag = "심각한 괴리. 입력 데이터를 반드시 재검토하세요."
    elif abs(gap) > threshold:
        flag = "데이터 또는 가정에 오류가 없는지 확인하세요."

    return MarketComparison(
        intrinsic_value=intrinsic,
        market_price=market_price,
        gap_ratio=round(gap, 4),
        flag=flag,
    )
