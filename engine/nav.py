"""자산가치평가법 (NAV: Net Asset Value) 엔진 — 순수 함수.

지주사, 리츠, 자산중심 기업에 적용.
조정 순자산가치 = 총자산 공정가치 − 총부채 (+ 투자자산 재평가 반영).
"""

from dataclasses import dataclass

from .units import per_share as _per_share


@dataclass
class NAVRawResult:
    """calc_nav 반환값."""
    total_assets: int       # 총자산 (장부)
    revaluation: int        # 투자자산 재평가 조정액
    adjusted_assets: int    # 조정 후 총자산
    total_liabilities: int  # 총부채
    nav: int                # 순자산가치 (조정 자산 − 부채)
    shares: int
    per_share: int          # 주당 NAV


def calc_nav(
    total_assets: int,
    total_liabilities: int,
    shares: int,
    revaluation: int = 0,
    unit_multiplier: int = 1_000_000,
) -> NAVRawResult:
    """조정 순자산가치(NAV) 계산.

    Args:
        total_assets: 총자산 (표시 단위)
        total_liabilities: 총부채 (표시 단위)
        shares: 발행주식수
        revaluation: 투자자산 재평가 조정액 (공정가치 − 장부가, 표시 단위)
        unit_multiplier: 1표시단위 = 몇 원/$

    Returns:
        NAVRawResult
    """
    adjusted = total_assets + revaluation
    nav = adjusted - total_liabilities
    ps = _per_share(nav, unit_multiplier, shares)
    return NAVRawResult(
        total_assets=total_assets,
        revaluation=revaluation,
        adjusted_assets=adjusted,
        total_liabilities=total_liabilities,
        nav=nav,
        shares=shares,
        per_share=ps,
    )
