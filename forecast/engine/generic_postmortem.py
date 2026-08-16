"""Generic post-earnings scoring with a four-lever EPS attribution."""

from __future__ import annotations

from engine.skill_metrics import SkillRow, compute_skill
from schemas.postmortem import (
    FourLeverAttribution,
    FrozenPoint,
    GenericActualRelease,
    GenericPostmortemResult,
    PointError,
    SegmentError,
    TeslaSpecialAttribution,
)


def _require_actual(actual: GenericActualRelease) -> tuple[float, float, float, float, float]:
    fields = {
        "revenue_total": actual.revenue_total,
        "gaap_eps_diluted": actual.gaap_eps_diluted,
        "diluted_shares": actual.diluted_shares,
        "operating_income": actual.operating_income,
        "net_income": actual.net_income,
    }
    missing = [name for name, value in fields.items() if value is None]
    if missing:
        raise ValueError(f"actual release missing required fields: {', '.join(missing)}")
    revenue, eps, shares, operating_income, net_income = fields.values()
    assert revenue is not None
    assert eps is not None
    assert shares is not None
    assert operating_income is not None
    assert net_income is not None
    if revenue == 0 or operating_income == 0:
        raise ValueError("actual revenue_total and operating_income must be non-zero")
    return revenue, eps, shares, operating_income, net_income


def point_error(forecast: float, actual: float) -> PointError:
    """Calculate one-point MAPE and signed bias."""
    if actual == 0:
        raise ValueError("actual must be non-zero")
    error = forecast - actual
    return PointError(
        forecast=forecast,
        actual=actual,
        error=error,
        mape=abs(error) / abs(actual),
        bias=error / actual,
    )


def attribute_eps_error_four_levers(
    forecast: FrozenPoint,
    actual: GenericActualRelease,
    unit_scale: float,
) -> FourLeverAttribution:
    """Attribute EPS error to revenue, OP margin, OP-to-NI, and shares.

    Args:
        forecast: Immutable FROZEN point used as the model comparand.
        actual: Released quarter carrying all core financial fields.
        unit_scale: Currency-unit multiplier, for example 1e6 for USD millions.

    Returns:
        Four additive contributions that telescope to model EPS minus actual EPS.

    Raises:
        ValueError: If a required field or bridge denominator is missing/zero.
    """
    revenue_a, eps_a, shares_a, op_a, net_a = _require_actual(actual)
    if forecast.revenue_total == 0 or forecast.operating_income == 0:
        raise ValueError("forecast revenue_total and operating_income must be non-zero")
    derived_eps = net_a * unit_scale / shares_a
    eps_tolerance = max(0.01, abs(eps_a) * 0.02)
    if abs(eps_a - derived_eps) > eps_tolerance:
        raise ValueError(
            "actual gaap_eps_diluted is inconsistent with net_income / diluted_shares"
        )

    revenue_m = forecast.revenue_total
    margin_m = forecast.operating_income / revenue_m
    conversion_m = forecast.net_income / forecast.operating_income
    margin_a = op_a / revenue_a
    conversion_a = net_a / op_a

    def eps(revenue: float, margin: float, conversion: float, shares: float) -> float:
        return revenue * margin * conversion * unit_scale / shares

    # Use the published FROZEN/actual EPS endpoints. Financial-statement inputs
    # are rounded, so recomputing either endpoint could create a false residual.
    e0 = forecast.eps_diluted
    e1 = eps(revenue_a, margin_m, conversion_m, forecast.diluted_shares)
    e2 = eps(revenue_a, margin_a, conversion_m, forecast.diluted_shares)
    e3 = eps(revenue_a, margin_a, conversion_a, forecast.diluted_shares)
    e4 = eps_a
    contributions = (e0 - e1, e1 - e2, e2 - e3, e3 - e4)
    total = forecast.eps_diluted - eps_a
    residual = total - sum(contributions)
    return FourLeverAttribution(
        eps_error_total=total,
        revenue=contributions[0],
        operating_margin=contributions[1],
        op_to_ni=contributions[2],
        share_count=contributions[3],
        residual=residual,
    )


def tesla_special_attribution(
    actual: GenericActualRelease,
    unit_scale: float,
) -> TeslaSpecialAttribution:
    """Build Tesla's realized auto-GM/credit split and GAAP bridge."""
    auto_gp_ex_credits = None
    auto_gp_including_credits = None
    if (
        actual.automotive_revenue is not None
        and actual.automotive_gross_margin_ex_credits is not None
        and actual.regulatory_credits is not None
    ):
        revenue_ex_credits = actual.automotive_revenue - actual.regulatory_credits
        auto_gp_ex_credits = (
            revenue_ex_credits * actual.automotive_gross_margin_ex_credits
        )
        auto_gp_including_credits = auto_gp_ex_credits + actual.regulatory_credits

    eps_gap = None
    sbc_per_share = None
    non_sbc_bridge = None
    if actual.non_gaap_eps is not None and actual.gaap_eps_diluted is not None:
        eps_gap = actual.non_gaap_eps - actual.gaap_eps_diluted
    if actual.stock_based_compensation is not None and actual.diluted_shares is not None:
        sbc_per_share = actual.stock_based_compensation * unit_scale / actual.diluted_shares
    if eps_gap is not None and sbc_per_share is not None:
        non_sbc_bridge = eps_gap - sbc_per_share

    return TeslaSpecialAttribution(
        automotive_gross_profit_ex_credits=auto_gp_ex_credits,
        regulatory_credits=actual.regulatory_credits,
        automotive_gross_profit_including_credits=auto_gp_including_credits,
        other_income_expense=actual.other_income_expense,
        gaap_to_non_gaap_eps_gap=eps_gap,
        sbc_per_diluted_share=sbc_per_share,
        non_sbc_bridge_per_share=non_sbc_bridge,
    )


def score_generic_release(
    *,
    actual: GenericActualRelease,
    base: FrozenPoint,
    weighted: FrozenPoint,
    prior_revenue: float,
    prior_eps: float,
    consensus_eps: float,
    unit_scale: float,
    segment_forecasts: dict[str, float] | None = None,
    include_tesla: bool = False,
) -> GenericPostmortemResult:
    """Score a released quarter against immutable base and weighted anchors."""
    revenue, eps, _, _, _ = _require_actual(actual)
    skill = compute_skill(
        [
            SkillRow(
                quarter_label=actual.quarter_label,
                actual_revenue=revenue,
                model_revenue=weighted.revenue_total,
                rw_revenue=prior_revenue,
                actual_eps=eps,
                model_eps=weighted.eps_diluted,
                rw_eps=prior_eps,
            )
        ],
        consensus_history={actual.quarter_label: {"estimate": consensus_eps}},
    )

    actual_segments = {
        "automotive": actual.automotive_revenue,
        "energy": actual.energy_revenue,
        "services": actual.services_revenue,
    }
    segments: list[SegmentError] = []
    for name, forecast_value in (segment_forecasts or {}).items():
        actual_value = actual_segments.get(name)
        if actual_value is None or actual_value == 0:
            continue
        error = point_error(forecast_value, actual_value)
        segments.append(
            SegmentError(
                segment=name,
                forecast=forecast_value,
                actual=actual_value,
                error=error.error,
                mape=error.mape,
            )
        )

    return GenericPostmortemResult(
        quarter_label=actual.quarter_label,
        provenance=actual.provenance,
        revenue_base=point_error(base.revenue_total, revenue),
        revenue_weighted=point_error(weighted.revenue_total, revenue),
        eps_base=point_error(base.eps_diluted, eps),
        eps_weighted=point_error(weighted.eps_diluted, eps),
        attribution=attribute_eps_error_four_levers(base, actual, unit_scale),
        skill=skill,
        segments=segments,
        tesla=tesla_special_attribution(actual, unit_scale) if include_tesla else None,
    )
