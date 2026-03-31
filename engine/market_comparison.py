"""Market price comparison -- intrinsic value vs current price gap calculation. Pure functions."""

from dataclasses import dataclass


@dataclass
class MarketComparison:
    intrinsic_value: int  # Intrinsic value per share
    market_price: float  # Current market price
    gap_ratio: float  # (intrinsic - market) / market
    flag: str  # Warning message (empty string = normal)


def compare_to_market(
    intrinsic: int,
    market_price: float,
    threshold: float = 0.5,
) -> MarketComparison:
    """Compare intrinsic value to market price.

    Args:
        intrinsic: Intrinsic value per share (KRW or $)
        market_price: Current market price (KRW or $)
        threshold: Warning threshold (default 0.5 = +/-50%)

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
