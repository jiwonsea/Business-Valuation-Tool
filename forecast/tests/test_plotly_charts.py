from __future__ import annotations

from datetime import date

import pytest

from engine.scenario import aggregate_quarterly_to_annual, build_scenario_tree
from output.plotly_charts import build_attribution_waterfall, build_fan_chart
from schemas.models import (
    CompanyMeta,
    DriverAttribution,
    QuarterlyForecast,
    ScenarioCase,
    ScenarioProbabilities,
    SegmentForecast,
)


def _q(label: str, scenario: str, revenue: float) -> QuarterlyForecast:
    return QuarterlyForecast(
        quarter_label=label,
        scenario=scenario,
        revenue_total=revenue,
        revenue_by_segment=[SegmentForecast(segment_id="dram", revenue=revenue)],
        gross_profit=revenue * 0.4,
        operating_profit=revenue * 0.3,
        net_profit=revenue * 0.2,
        gp_margin=0.4,
        op_margin=0.3,
        np_margin=0.2,
        eps_basic=revenue,
    )


def _case(name: str, revenue: float) -> ScenarioCase:
    quarterly = [_q("2026Q2", name, revenue), _q("2026Q3", name, revenue * 1.1)]
    return ScenarioCase(
        scenario=name,
        probability={"bear": 0.25, "base": 0.50, "bull": 0.25}[name],
        rationale="test",
        quarterly=quarterly,
        annual=aggregate_quarterly_to_annual(quarterly, name),
    )


def _tree():
    company = CompanyMeta(
        name="SK Hynix",
        name_kr="SK",
        ticker_yahoo="000660.KS",
        corp_code_dart="00164779",
        fiscal_year_end_month=12,
        reporting_unit="KRW_billion",
    )
    return build_scenario_tree(
        company,
        date(2026, 6, 2),
        _case("bear", 80),
        _case("base", 100),
        _case("bull", 130),
        ScenarioProbabilities(bear=0.25, base=0.50, bull=0.25),
    )


def test_fan_chart_keeps_scenario_legends_separate_and_fixes_yaxis_range() -> None:
    chart = build_fan_chart(_tree())
    band_lower, band_upper, bear, weighted, bull = chart["data"]

    assert band_lower["showlegend"] is False
    assert band_upper["showlegend"] is False
    assert band_upper["fill"] == "tonexty"
    assert [trace["name"] for trace in chart["data"] if trace.get("showlegend", True)] == [
        "Bear",
        "Weighted",
        "Bull",
    ]
    assert "legendgroup" not in bear
    assert "legendgroup" not in bull
    assert weighted["name"] == "Weighted"
    assert chart["layout"]["yaxis"]["range"][0] > 0


def _attr(quarter_label: str, contribs: tuple[float, float, float, float, float]) -> DriverAttribution:
    return DriverAttribution(
        quarter_label=quarter_label,
        eps_error_total=sum(contribs),
        contrib_revenue=contribs[0],
        contrib_gross_margin=contribs[1],
        contrib_opex=contribs[2],
        contrib_tax_finance=contribs[3],
        contrib_shares=contribs[4],
        model_basic_shares=700_000_000,
        actual_implied_basic_shares=705_000_000.0,
    )


def test_attribution_waterfall_telescopes_per_quarter() -> None:
    attributions = [
        _attr("2025Q4", (0.04, -0.02, 0.01, -0.05, 0.003)),
        _attr("2026Q1", (-0.10, 0.03, -0.01, -0.08, 0.002)),
    ]
    chart = build_attribution_waterfall(attributions)

    (trace,) = chart["data"]
    assert trace["type"] == "waterfall"
    # 2 quarters × (5 levers + 1 total)
    assert len(trace["y"]) == 12
    # First lever of EACH quarter is "absolute" so the running sum resets per quarter.
    assert trace["measure"] == ["absolute"] + ["relative"] * 4 + ["total"] + ["absolute"] + ["relative"] * 4 + ["total"]
    # Lever bars telescope to the quarter's total EPS error (in %p).
    for i, attr in enumerate(attributions):
        levers = trace["y"][i * 6 : i * 6 + 5]
        assert sum(levers) == pytest.approx(attr.eps_error_total * 100)
    # Multicategory x: quarter group + lever label.
    x_quarter, x_lever = trace["x"]
    assert x_quarter[:6] == ["2025Q4"] * 6
    assert x_lever[0] != x_lever[1]


def test_attribution_waterfall_is_labeled_post_mortem_not_forecast() -> None:
    chart = build_attribution_waterfall([_attr("2025Q4", (0.04, -0.02, 0.01, -0.05, 0.003))])

    assert "사후 귀인" in chart["layout"]["title"]
    assert "post-mortem attribution" in chart["layout"]["title"]
    annotation_text = " ".join(a["text"] for a in chart["layout"]["annotations"])
    assert "예측 신호 아님" in annotation_text


def test_attribution_waterfall_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        build_attribution_waterfall([])
