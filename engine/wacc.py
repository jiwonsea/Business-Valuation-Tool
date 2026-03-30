"""WACC 계산 엔진."""

from schemas.models import WACCParams, WACCResult


def calc_wacc(p: WACCParams) -> WACCResult:
    """WACC 산출 (CAPM 기반).

    βL = βu × [1 + (1 - t) × D/E]
    Ke = Rf + βL × ERP
    Kd(세후) = Kd(세전) × (1 - t)
    WACC = Ke × E% + Kd(세후) × D%
    """
    bl = p.bu * (1 + (1 - p.tax / 100) * p.de / 100)
    ke = p.rf + bl * p.erp
    kd_at = p.kd_pre * (1 - p.tax / 100)
    dw = 100 - p.eq_w
    wacc = ke * p.eq_w / 100 + kd_at * dw / 100
    return WACCResult(
        bl=round(bl, 3),
        ke=round(ke, 2),
        kd_at=round(kd_at, 2),
        wacc=round(wacc, 2),
    )
