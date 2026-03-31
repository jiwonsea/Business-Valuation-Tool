"""WACC 계산 엔진."""

from schemas.models import WACCParams, WACCResult


def calc_wacc(p: WACCParams) -> WACCResult:
    """WACC 산출 (CAPM 기반).

    일반 기업:
        βL = βu × [1 + (1 - t) × D/E]   (Hamada)
    금융업종 (is_financial=True):
        βL = bu (Equity Beta 직접 사용)
        금융사는 예금 등이 부채에 포함되어 D/E가 1000%+ → Hamada 적용 시 βL 왜곡.
        실무에서는 시장에서 관찰된 Equity Beta를 그대로 사용.

    Ke = Rf + βL × ERP
    Kd(세후) = Kd(세전) × (1 - t)
    WACC = Ke × E% + Kd(세후) × D%
    """
    if p.is_financial:
        bl = p.bu  # Equity Beta 직접 사용
    else:
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
