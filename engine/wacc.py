"""WACC calculation engine."""

from schemas.models import WACCParams, WACCResult


def calc_wacc(p: WACCParams) -> WACCResult:
    """Compute WACC (CAPM-based).

    General companies:
        beta_L = beta_u x [1 + (1 - t) x D/E]   (Hamada)
    Financial sector (is_financial=True):
        beta_L = bu (use equity beta directly)
        Financials include deposits in liabilities, pushing D/E to 1000%+,
        which distorts beta_L under Hamada. Market-observed equity beta is used instead.

    Ke = Rf + beta_L x ERP
    Kd(after-tax) = Kd(pre-tax) x (1 - t)
    WACC = Ke x E% + Kd(after-tax) x D%
    """
    if p.is_financial:
        bl = p.bu  # Use equity beta directly
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
