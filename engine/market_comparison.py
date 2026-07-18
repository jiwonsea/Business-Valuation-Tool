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
    value_ratio = intrinsic / market_price
    if abs(gap) >= 1.0:
        flag = "심각한 괴리. 입력 데이터를 반드시 재검토하세요."
    elif abs(gap) > threshold:
        flag = "데이터 또는 가정에 오류가 없는지 확인하세요."

    if intrinsic > 0 and (value_ratio > 10 or value_ratio < 0.1):
        unit_warning = (
            f"단위 오염 또는 극단적 밸류에이션 괴리 의심: "
            f"내재가치/시장가 비율이 {value_ratio:.2f}배입니다. "
            "단위 계약과 모델 가정을 함께 확인하세요."
        )
        flag = f"{flag} {unit_warning}".strip()

    return MarketComparison(
        intrinsic_value=intrinsic,
        market_price=market_price,
        gap_ratio=round(gap, 4),
        flag=flag,
    )
