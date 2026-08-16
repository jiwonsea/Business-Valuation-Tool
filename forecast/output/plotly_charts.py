"""Plotly figure builders — return JSON for embedding in the Jinja2 template.

3 chart types:
  - fan_chart: forecast median + scenario band (bear-bull shading)
  - beat_miss_bar: backtest per-quarter error in % terms, colored by direction
  - scenario_compare: bear / base / bull bars side-by-side per period

Each function returns a Plotly figure dict (`fig.to_dict()` shape) — the template
embeds via `<div id="..."></div>` + `Plotly.newPlot(...)`.
"""

from __future__ import annotations

from schemas.models import BacktestResult, DriverAttribution, EpsRiskBand, ScenarioTree


def build_fan_chart(tree: ScenarioTree) -> dict:
    """Forecast fan — weighted base line + bear/bull shaded band.

    Returns:
        Plotly figure dict.

    Raises:
        NotImplementedError: Codex implementation.
    """
    labels = [q.quarter_label for q in tree.weighted_quarterly]
    bear_revenue = [q.revenue_total for q in tree.bear.quarterly]
    bull_revenue = [q.revenue_total for q in tree.bull.quarterly]
    weighted_revenue = [q.revenue_total for q in tree.weighted_quarterly]
    all_revenue = bear_revenue + bull_revenue + weighted_revenue
    min_revenue = min(all_revenue) if all_revenue else 0.0
    max_revenue = max(all_revenue) if all_revenue else 1.0
    padding = (max_revenue - min_revenue) * 0.10 or max_revenue * 0.05 or 1.0
    return {
        "data": [
            {
                "type": "scatter",
                "name": "Bear-Bull band lower",
                "x": labels,
                "y": bear_revenue,
                "mode": "lines",
                "line": {"color": "rgba(0, 0, 0, 0)", "width": 0},
                "hoverinfo": "skip",
                "showlegend": False,
            },
            {
                "type": "scatter",
                "name": "Bear-Bull band",
                "x": labels,
                "y": bull_revenue,
                "mode": "lines",
                "fill": "tonexty",
                "fillcolor": "rgba(65, 130, 165, 0.18)",
                "line": {"color": "rgba(0, 0, 0, 0)", "width": 0},
                "hoverinfo": "skip",
                "showlegend": False,
            },
            {
                "type": "scatter",
                "name": "Bear",
                "x": labels,
                "y": bear_revenue,
                "mode": "lines",
                "line": {"color": "#b65f3a", "width": 2},
            },
            {
                "type": "scatter",
                "name": "Weighted",
                "x": labels,
                "y": weighted_revenue,
                "mode": "lines+markers",
                "line": {"color": "#222222", "width": 3},
            },
            {
                "type": "scatter",
                "name": "Bull",
                "x": labels,
                "y": bull_revenue,
                "mode": "lines",
                "line": {"color": "#4182a5", "width": 2},
            },
        ],
        "layout": {
            "title": "Revenue forecast fan",
            "yaxis": {"title": "KRW bn", "range": [min_revenue - padding, max_revenue + padding]},
        },
    }


def build_beat_miss_bar(backtest: BacktestResult) -> dict:
    """Per-quarter backtest error bar — green when within tolerance, red otherwise.

    Returns:
        Plotly figure dict.

    Raises:
        NotImplementedError: Codex implementation.
    """
    return {
        "data": [
            {
                "type": "bar",
                "name": "Revenue error",
                "x": [q.quarter_label for q in backtest.quarters],
                "y": [q.revenue_error_pct * 100 for q in backtest.quarters],
            }
        ],
        "layout": {"title": "Backtest revenue error", "yaxis": {"title": "%"}},
    }


def build_eps_risk_band_chart(risk_band: EpsRiskBand) -> dict:
    """EPS point estimate + below-OP risk band as a SEPARATE figure.

    This is the structural below-OP (net financial / FX / one-off) volatility
    band, NOT the bear/bull earnings-scenario spread of the revenue fan
    (build_fan_chart). The two layers are deliberately never merged
    (PLAN_tax_finance_overlay.md §3.1) — they measure different uncertainties.

    Returns:
        Plotly figure dict.
    """
    labels = [q.period_label for q in risk_band.quarters]
    point = [q.eps_point for q in risk_band.quarters]
    lower = [q.eps_lower for q in risk_band.quarters]
    upper = [q.eps_upper for q in risk_band.quarters]
    half_pct = risk_band.half_width_pct * 100
    title = (
        f"EPS 점추정 + below-OP 리스크 밴드 "
        f"(±{half_pct:.1f}%, {risk_band.method} k={risk_band.k:g})"
    )
    return {
        "data": [
            {
                "type": "scatter",
                "name": "밴드 하한",
                "x": labels,
                "y": lower,
                "mode": "lines",
                "line": {"color": "rgba(0, 0, 0, 0)", "width": 0},
                "hoverinfo": "skip",
                "showlegend": False,
            },
            {
                "type": "scatter",
                "name": "below-OP 리스크 밴드",
                "x": labels,
                "y": upper,
                "mode": "lines",
                "fill": "tonexty",
                "fillcolor": "rgba(182, 95, 58, 0.16)",
                "line": {"color": "rgba(0, 0, 0, 0)", "width": 0},
                "hoverinfo": "skip",
            },
            {
                "type": "scatter",
                "name": "EPS 점추정 (weighted)",
                "x": labels,
                "y": point,
                "mode": "lines+markers",
                "line": {"color": "#222222", "width": 3},
            },
        ],
        "layout": {
            "title": title,
            "yaxis": {"title": "EPS (KRW)"},
        },
    }


ATTRIBUTION_LEVER_LABELS = ("매출", "매출총이익률", "opex 전환", "세금·금융", "주식수")
ATTRIBUTION_TOTAL_LABEL = "합계 (EPS 오차)"


def build_attribution_waterfall(attributions: list[DriverAttribution]) -> dict:
    """Per-quarter waterfall of the backtest EPS-error driver attribution.

    Renders engine.attribution output only — post-mortem / diagnostic. The chart
    is explicitly labeled as post-mortem attribution so it cannot be mistaken
    for a forecast signal (PLAN_skill_adoption.md §5 A2 risk): actual realized
    ratios explain an already-realized error; nothing here feeds the forecast.

    One waterfall group per quarter on a multicategory x-axis. The first lever
    uses measure="absolute" so each quarter's running sum restarts at zero; the
    five lever bars then telescope to eps_error_total ("total" bar).

    Returns:
        Plotly figure dict.

    Raises:
        ValueError: If attributions is empty.
    """
    if not attributions:
        raise ValueError("attributions must be non-empty")

    x_quarter: list[str] = []
    x_lever: list[str] = []
    y: list[float] = []
    measure: list[str] = []
    for attr in attributions:
        contribs = (
            attr.contrib_revenue,
            attr.contrib_gross_margin,
            attr.contrib_opex,
            attr.contrib_tax_finance,
            attr.contrib_shares,
        )
        for lever_label, contrib in zip(ATTRIBUTION_LEVER_LABELS, contribs):
            x_quarter.append(attr.quarter_label)
            x_lever.append(lever_label)
            y.append(contrib * 100)
            # "absolute" on the first lever resets the running sum per quarter.
            measure.append("absolute" if not measure or measure[-1] == "total" else "relative")
        x_quarter.append(attr.quarter_label)
        x_lever.append(ATTRIBUTION_TOTAL_LABEL)
        y.append(0.0)  # ignored for measure="total" (running sum is used)
        measure.append("total")

    return {
        "data": [
            {
                "type": "waterfall",
                "name": "사후 귀인",
                "x": [x_quarter, x_lever],
                "y": y,
                "measure": measure,
                "increasing": {"marker": {"color": "#b65f3a"}},
                "decreasing": {"marker": {"color": "#4182a5"}},
                "totals": {"marker": {"color": "#222222"}},
                "connector": {"line": {"color": "rgba(0, 0, 0, 0.25)", "width": 1}},
            }
        ],
        "layout": {
            "title": "백테스트 EPS 오차 — 드라이버별 사후 귀인 (post-mortem attribution)",
            "yaxis": {"title": "EPS 오차 기여 (%p)"},
            "showlegend": False,
            "annotations": [
                {
                    "text": "이미 실현된 백테스트 오차의 사후 분해(진단용) — 예측 신호 아님",
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0,
                    "y": 1.08,
                    "showarrow": False,
                    "font": {"size": 11, "color": "#6b7280"},
                }
            ],
        },
    }


def build_scenario_compare(tree: ScenarioTree) -> dict:
    """Bear / Base / Bull side-by-side bar per quarter.

    Returns:
        Plotly figure dict.

    Raises:
        NotImplementedError: Codex implementation.
    """
    labels = [q.quarter_label for q in tree.base.quarterly]
    return {
        "data": [
            {"type": "bar", "name": "Bear", "x": labels, "y": [q.revenue_total for q in tree.bear.quarterly]},
            {"type": "bar", "name": "Base", "x": labels, "y": [q.revenue_total for q in tree.base.quarterly]},
            {"type": "bar", "name": "Bull", "x": labels, "y": [q.revenue_total for q in tree.bull.quarterly]},
        ],
        "layout": {"title": "Scenario revenue", "barmode": "group", "yaxis": {"title": "KRW bn"}},
    }
