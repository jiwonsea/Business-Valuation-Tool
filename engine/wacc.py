"""WACC calculation engine."""

from schemas.models import WACCParams, WACCResult

# D/E cap for Hamada levering (%)
_HAMADA_DE_CAP = 200.0
# Distress premium: max additional WACC for extreme leverage (%)
_DISTRESS_PREMIUM_MAX = 3.0
# D/E level at which maximum distress premium is reached (%)
_DISTRESS_DE_MAX = 500.0


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

    Distress premium (non-financial only):
        When D/E exceeds the Hamada cap (200%), Hamada beta is capped but the
        excess leverage risk is unpriced. A linear premium (up to 3%) is added
        to WACC so that DCF valuations reflect the true cost of capital for
        highly leveraged firms. This aligns with the SOTP distress discount
        which also penalizes high D/E (cf. Damodaran, "Valuing Distressed Firms").
    """
    distress_premium = 0.0
    if p.is_financial:
        bl = p.bu  # Use equity beta directly
    else:
        # Cap D/E at 200% for Hamada levering
        hamada_de = min(p.de, _HAMADA_DE_CAP)
        bl = p.bu * (1 + (1 - p.tax / 100) * hamada_de / 100)
        # Distress premium for D/E beyond cap
        if p.de > _HAMADA_DE_CAP:
            excess = min(p.de - _HAMADA_DE_CAP, _DISTRESS_DE_MAX - _HAMADA_DE_CAP)
            distress_premium = (
                excess / (_DISTRESS_DE_MAX - _HAMADA_DE_CAP) * _DISTRESS_PREMIUM_MAX
            )
    ke = p.rf + bl * p.erp + p.size_premium
    kd_at = p.kd_pre * (1 - p.tax / 100)
    dw = 100 - p.eq_w
    wacc = ke * p.eq_w / 100 + kd_at * dw / 100 + distress_premium
    return WACCResult(
        bl=round(bl, 3),
        ke=round(ke, 2),
        kd_at=round(kd_at, 2),
        wacc=round(wacc, 2),
        distress_premium=round(distress_premium, 2),
    )
