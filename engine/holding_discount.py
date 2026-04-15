"""Holding/governance discount bridge applied after core SOTP equity value."""

from __future__ import annotations

from schemas.models import HoldingDiscountBridge, HoldingStructure

_OVERHANG_RISK_PCT = {"low": 2.5, "medium": 5.0, "high": 10.0}
_DIVIDEND_ACCESS_PCT = {"high": 0.0, "medium": 2.0, "low": 5.0}


def build_holding_discount_bridge(
    gross_sotp_value: int,
    gross_equity_value: int,
    holding_structure: HoldingStructure | None,
) -> HoldingDiscountBridge | None:
    """Build a post-SOTP bridge from gross equity to net parent equity."""
    if holding_structure is None or not holding_structure.enabled:
        return None

    lookthrough_value = 0
    access_discount = 0
    overhang_discount = 0
    warnings: list[str] = []

    for sub in holding_structure.listed_subsidiaries:
        owned_value = round(sub.market_value * sub.ownership_pct / 100)
        lookthrough_value += owned_value
        access_discount += round(owned_value * sub.parent_access_discount / 100)
        overhang_pct = (
            _OVERHANG_RISK_PCT.get(sub.overhang_risk.lower(), 0.0)
            if sub.overhang_risk
            else 0.0
        )
        dividend_pct = (
            _DIVIDEND_ACCESS_PCT.get(sub.dividend_access.lower(), 0.0)
            if sub.dividend_access
            else 0.0
        )
        overhang_discount += round(owned_value * (overhang_pct + dividend_pct) / 100)
        if sub.market_value <= 0:
            warnings.append(
                f"{sub.name}: market_value가 0이라 holding discount reference가 약합니다."
            )

    governance_discount = 0
    gov_cfg = holding_structure.governance_discount
    if gov_cfg.enabled and gov_cfg.base_discount_pct > 0:
        governance_base = max(gross_equity_value - access_discount, 0)
        governance_discount = round(governance_base * gov_cfg.base_discount_pct / 100)

    total_discount = access_discount + governance_discount + overhang_discount
    net_equity_value = gross_equity_value - total_discount
    if total_discount > max(gross_equity_value, 0):
        warnings.append("holding discount 총액이 gross equity를 초과해 net equity가 음수입니다.")
    elif net_equity_value < 0:
        warnings.append(
            "net equity가 음수입니다 — Bear 시나리오에서 gross equity부터 음수인 경우 "
            "DLOM은 추가 적용되지 않습니다(policy)."
        )

    return HoldingDiscountBridge(
        enabled=True,
        gross_sotp_value=gross_sotp_value,
        gross_equity_value=gross_equity_value,
        listed_subsidiary_lookthrough_value=lookthrough_value,
        parent_access_discount=access_discount,
        governance_discount=governance_discount,
        overhang_discount=overhang_discount,
        total_discount=total_discount,
        net_equity_value=net_equity_value,
        warnings=warnings,
    )
