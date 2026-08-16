"""Primary HTML report — Jinja2 template + inline Plotly figures.

Self-contained single file. Plotly JS via CDN by default (smaller file);
pass inline_plotly=True for offline distribution at the cost of ~3MB.

Output layout (per docs/methodology.md §13-B):
  - Top: 6 KPI cards (Model FY26 EPS, Consensus FY26 EPS, Gap %, Backtest MAPE,
    Scenario range, As-of-date).
  - Middle: 3 tabs — Forecast / Backtest / Consensus Gap.
  - Bottom: Assumptions YAML dump + AI collaboration disclosure.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from output.plotly_charts import (
    build_attribution_waterfall,
    build_beat_miss_bar,
    build_eps_risk_band_chart,
    build_fan_chart,
    build_scenario_compare,
)
from schemas.models import (
    BacktestResult,
    BacktestSkill,
    BelowOpEventScenario,
    ConsensusGap,
    DriverAttribution,
    EpsRiskBand,
    ScenarioTree,
    ValuationBridgeResult,
)


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1%}"


def _num(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def _skill_verdict(skill: BacktestSkill) -> str:
    parts = []
    for label, mase, u2 in (
        ("매출", skill.mase_revenue, skill.theil_u2_revenue),
        ("EPS", skill.mase_eps, skill.theil_u2_eps),
    ):
        if mase is None or u2 is None:
            parts.append(f"{label}: 산출 불가")
        elif mase < 1 and u2 < 1:
            parts.append(f"{label}: naive(RW) 대비 우위")
        else:
            parts.append(f"{label}: edge 없음")
    return " · ".join(parts)


def _skill_html(skill: BacktestSkill, model_hit_ratio: float) -> str:
    """Skill block: naive-baseline-relative metrics table + honest verdict."""
    small = (
        f"<p><small>surprise-direction 표본 부족 (N={skill.n_surprise_scored}) — 참고용.</small></p>"
        if skill.n_surprise_scored < 4
        else ""
    )
    return f"""<h2>Skill (naive 베이스라인 대비)</h2>
<p><small>절대 MAPE·방향 적중률은 기준점이 없어 단독 판정 불가. Random Walk(persistence)·과거 컨센서스 대비로 측정. 8Q 작은 표본 — 점추정 과대해석 금지.</small></p>
<table><thead><tr><th>지표</th><th>값</th><th>해석</th></tr></thead><tbody>
<tr><td>RW 매출 MAPE</td><td>{_pct(skill.naive_rw_revenue_mape)}</td><td>naive 기준 오차</td></tr>
<tr><td>RW EPS MAPE</td><td>{_pct(skill.naive_rw_eps_mape)}</td><td>naive 기준 오차</td></tr>
<tr><td>MASE 매출</td><td>{_num(skill.mase_revenue)}</td><td>&lt;1 → RW 대비 우위</td></tr>
<tr><td>MASE EPS</td><td>{_num(skill.mase_eps)}</td><td>&lt;1 → RW 대비 우위</td></tr>
<tr><td>Theil U2 매출</td><td>{_num(skill.theil_u2_revenue)}</td><td>&lt;1 → RW 대비 우위</td></tr>
<tr><td>Theil U2 EPS</td><td>{_num(skill.theil_u2_eps)}</td><td>&lt;1 → RW 대비 우위</td></tr>
<tr><td>방향 적중률 (model vs RW)</td><td>{_pct(model_hit_ratio)} vs {_pct(skill.rw_hit_ratio_direction)}</td><td>차이 없으면 edge 없음</td></tr>
<tr><td>컨센서스 대비 skill score (EPS)</td><td>{_num(skill.skill_score_eps_vs_consensus)}</td><td>&gt;0 → 컨센서스 대비 우위</td></tr>
<tr><td>surprise-direction 적중 (N={skill.n_surprise_scored})</td><td>{_pct(skill.surprise_direction_accuracy)}</td><td>컨센서스 대비 <i>편차</i> 부호</td></tr>
</tbody></table>
<p><b>판정</b>: {html.escape(_skill_verdict(skill))}</p>
{small}"""


def _risk_band_html(risk_band: EpsRiskBand) -> str:
    """Below-OP EPS risk band: separate-layer chart + per-quarter table + overlays.

    Rendered as its own section so the below-the-line volatility band is visually
    and numerically distinct from the bear/bull revenue fan (PLAN §3.1).
    """
    band_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(q.period_label)}</td>"
        f"<td>{q.eps_lower:,.0f}</td><td>{q.eps_point:,.0f}</td><td>{q.eps_upper:,.0f}</td>"
        "</tr>"
        for q in risk_band.quarters
    )
    if risk_band.overlays:
        overlay_rows = "\n".join(
            "<tr>"
            f"<td>{ov.as_of_date}</td><td>{html.escape(ov.target_period_label)}</td>"
            f"<td>{html.escape(ov.driver)}</td><td>{html.escape(ov.direction)}</td>"
            f"<td>{ov.magnitude:+.2f}</td><td>{ov.confidence:.0%}</td></tr>"
            for ov in risk_band.overlays
        )
        overlay_html = (
            "<h3>Overlays (밸류에이션·리스크 레이어 — EPS 점추정 불반영)</h3>"
            "<table><thead><tr><th>As-of</th><th>Target</th><th>Driver</th>"
            "<th>Direction</th><th>Magnitude</th><th>Confidence</th></tr></thead>"
            f"<tbody>{overlay_rows}</tbody></table>"
            f"<p><small>{html.escape(risk_band.seam_note)}</small></p>"
        )
    else:
        overlay_html = ""
    return f"""<h2>Below-OP 리스크 밴드 (EPS)</h2>
<p><small>below-OP 블록(순금융손익·FX 평가·일회성)의 구조적 변동성을 EPS 점추정에 넣지 않고 별도 ±밴드로 표현
(method={html.escape(risk_band.method)}, k={risk_band.k:g}, ±{risk_band.half_width_pct:.1%}).
bear/bull 시나리오 범위와 다른 불확실성 — 합치지 않음.</small></p>
<div id="epsband"></div>
<table><thead><tr><th>분기</th><th>하한</th><th>점추정</th><th>상한</th></tr></thead><tbody>{band_rows}</tbody></table>
{overlay_html}"""


def _attribution_html(attributions: list[DriverAttribution]) -> str:
    """Post-mortem EPS-error attribution: waterfall chart + per-quarter table.

    Diagnostic layer over the backtest — labeled as post-mortem so it is not
    read as a forecast signal (PLAN_skill_adoption.md §5 A2 risk).
    """
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(a.quarter_label)}</td>"
        f"<td>{a.eps_error_total:+.1%}</td>"
        f"<td>{a.contrib_revenue:+.1%}</td><td>{a.contrib_gross_margin:+.1%}</td>"
        f"<td>{a.contrib_opex:+.1%}</td><td>{a.contrib_tax_finance:+.1%}</td>"
        f"<td>{a.contrib_shares:+.1%}</td></tr>"
        for a in attributions
    )
    return f"""<h2>EPS 오차 사후 귀인 (post-mortem attribution)</h2>
<p><small>백테스트에서 이미 실현된 모델-실적 EPS 오차를 5개 레버(매출·매출총이익률·opex 전환·세금·금융·주식수)로
사후 분해한 진단 차트. 실적 비율로 실현 오차를 설명할 뿐 예측 신호가 아니며, 전망(fan·리스크 밴드)에 어떤 값도
피드백되지 않음. 레버별 기여의 합 = 분기 EPS 오차 (telescoping).</small></p>
<div id="attribution"></div>
<table><thead><tr><th>분기</th><th>EPS 오차</th><th>매출</th><th>매출총이익률</th><th>opex 전환</th><th>세금·금융</th><th>주식수</th></tr></thead><tbody>{rows}</tbody></table>"""


def _valuation_html(
    v: ValuationBridgeResult,
    *,
    below_op_events_present: bool = False,
) -> str:
    """Valuation-bridge section: EPS-gap fair-value delta + separate overlay score."""
    def pct(x: float | None) -> str:
        return "—" if x is None else f"{x:+.1%}"

    band = ""
    if v.fair_value_delta_low is not None and v.fair_value_delta_high is not None:
        band = f" (밴드 {pct(v.fair_value_delta_low)} ~ {pct(v.fair_value_delta_high)})"
    note = f"<p><small>{html.escape(v.note)}</small></p>" if v.note else ""
    cons = "—" if v.consensus_eps_fy is None else f"{v.consensus_eps_fy:,.0f}"
    event_note = (
        " 원래 base/weighted EPS 점추정만 사용하며 이벤트 조정 EPS는 절대 주입하지 않음."
        if below_op_events_present
        else ""
    )
    return f"""<h2>밸류에이션 브리지 (FY{str(v.fiscal_year)[-2:]})</h2>
<p><small>EPS gap(모델 vs 컨센) × 탄력도 {v.elasticity:g} → 공정가치 delta.{event_note} overlay 매크로 리스크는 별도 레이어 — EPS·공정가치 delta 점값에 미반영. 탄력도는 BVT sensitivity로 확정할 draft.</small></p>
<table><thead><tr><th>지표</th><th>값</th></tr></thead><tbody>
<tr><td>모델 FY EPS</td><td>{v.model_eps_fy:,.0f}</td></tr>
<tr><td>컨센서스 FY EPS</td><td>{cons}</td></tr>
<tr><td>EPS gap</td><td>{pct(v.eps_delta_pct)}</td></tr>
<tr><td>공정가치 delta (탄력도 {v.elasticity:g})</td><td>{pct(v.fair_value_delta_pct)}{band}</td></tr>
<tr><td>overlay 리스크 점수 (매크로, 별도)</td><td>{v.overlay_risk_score:+.3f} (n={len(v.overlays)})</td></tr>
</tbody></table>
{note}"""


def _below_op_event_html(scenario: BelowOpEventScenario) -> str:
    """Output-only below-OP event EPS scenario and audit register."""
    quarter_rows = "\n".join(
        "\n".join(
            (
                f"<tr><td>{html.escape(q.period_label)}</td><td>미발생</td><td>0</td><td>{q.eps_no_event:,.0f}</td></tr>",
                f"<tr><td>{html.escape(q.period_label)}</td><td>발생</td><td>1</td><td>{q.eps_if_realized:,.0f}</td></tr>",
                f"<tr><td>{html.escape(q.period_label)}</td><td>기대값</td><td>{sum(e.probability for e in q.events) / len(q.events):.0%}</td><td>{q.eps_expected:,.0f}</td></tr>",
            )
        )
        for q in scenario.quarters
    )
    event_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(e.id)}</td><td>{e.as_of_date}</td><td>{e.amount_as_of}</td>"
        f"<td>{html.escape(e.target_period_label)}</td><td>{html.escape(e.kind)}</td><td>{html.escape(e.basis)}</td>"
        f"<td>{e.amount_krw_bn:,.0f}</td><td>{e.probability:.0%}</td>"
        f"<td>{html.escape(e.confidence)}</td><td>{html.escape(e.source)}</td></tr>"
        for e in scenario.events
    )
    event_notes = "".join(
        f"<p><small>{html.escape(e.id)}: 존재는 {e.as_of_date}부터, 금액은 {e.amount_as_of}부터 인지 가능. "
        f"{html.escape(e.note)}<br>Revision trigger: {html.escape(e.revision_trigger)}</small></p>"
        for e in scenario.events
    )
    return f"""<h2>Below-OP 이벤트 조정 EPS (별도 시나리오)</h2>
<p><small>기본 EPS 점추정은 불변이다. 확률은 통계 추정치가 아닌 판단값이며 기대값은 실현 불가능한 중간값이다.<br>
밴드와 이벤트는 근사적으로 분리된다. 기존 8Q 밴드 표본에는 이상치가 포함되어 있으나 MAD가 그 기여를 제한한다. 잔여 중복은 0이 아니며 정량화하지 않는다.</small></p>
<table><thead><tr><th>분기</th><th>시나리오</th><th>확률</th><th>EPS</th></tr></thead><tbody>{quarter_rows}</tbody></table>
<table><thead><tr><th>ID</th><th>존재 As-of</th><th>금액 As-of</th><th>Target</th><th>Kind</th><th>Basis</th><th>금액 (KRW bn)</th><th>Probability</th><th>Confidence</th><th>Source</th></tr></thead><tbody>{event_rows}</tbody></table>
{event_notes}"""


def render_html_report(
    out_path: Path,
    tree: ScenarioTree,
    consensus_gaps: list[ConsensusGap],
    backtest: BacktestResult,
    profile_raw: dict,
    inline_plotly: bool = False,
    risk_band: EpsRiskBand | None = None,
    valuation: ValuationBridgeResult | None = None,
    below_op_event_scenario: BelowOpEventScenario | None = None,
    attributions: list[DriverAttribution] | None = None,
) -> Path:
    """Render the full HTML report to out_path.

    Args:
        out_path: Target file path (must end with .html).
        tree: Full scenario tree.
        consensus_gaps: From engine.consensus_diff.
        backtest: From engine.backtest.
        profile_raw: Original profile YAML dict (rendered as assumptions block).
        inline_plotly: If True, bundle plotly.js into the HTML (offline-friendly).
        risk_band: Optional below-OP EPS risk band (separate layer; overlays are
            surfaced as annotations only). None leaves the report unchanged.
        valuation: Optional valuation-bridge result (separate section). None leaves
            the report unchanged.
        attributions: Optional per-quarter post-mortem EPS-error attribution
            (engine.attribution). Rendering-only diagnostic layer; None or empty
            leaves the report unchanged.

    Returns:
        out_path on success.

    Raises:
        NotImplementedError: Codex implementation.
    """
    import yaml

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plotly_script = (
        '<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>'
        if not inline_plotly
        else '<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>'
    )
    fan = json.dumps(build_fan_chart(tree))
    beat = json.dumps(build_beat_miss_bar(backtest))
    compare = json.dumps(build_scenario_compare(tree))
    risk_band_section = _risk_band_html(risk_band) if risk_band is not None else ""
    valuation_section = (
        _valuation_html(
            valuation,
            below_op_events_present=below_op_event_scenario is not None,
        )
        if valuation is not None
        else ""
    )
    below_op_event_section = (
        _below_op_event_html(below_op_event_scenario)
        if below_op_event_scenario is not None
        else ""
    )
    eps_band_json = json.dumps(build_eps_risk_band_chart(risk_band)) if risk_band is not None else "null"
    eps_band_script = (
        f"const epsband={eps_band_json};Plotly.newPlot('epsband',epsband.data,epsband.layout);"
        if risk_band is not None
        else ""
    )
    has_attribution = bool(attributions)
    attribution_section = _attribution_html(attributions) if has_attribution else ""
    attribution_script = (
        f"const attr={json.dumps(build_attribution_waterfall(attributions))};"
        "Plotly.newPlot('attribution',attr.data,attr.layout);"
        if has_attribution
        else ""
    )

    gap_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(g.period_label)}</td><td>{g.metric}</td>"
        f"<td>{g.model_value:,.1f}</td><td>{'' if g.consensus_value is None else f'{g.consensus_value:,.1f}'}</td>"
        f"<td>{'' if g.gap_pct is None else f'{g.gap_pct:.1%}'}</td><td>{g.direction}</td>"
        f"<td>{html.escape(g.interpretation)}</td></tr>"
        for g in consensus_gaps
    )
    backtest_rows = "\n".join(
        "<tr>"
        f"<td>{q.quarter_label}</td><td>{q.actual_revenue:,.1f}</td><td>{q.model_revenue:,.1f}</td>"
        f"<td>{q.revenue_error_pct:.1%}</td><td>{'' if q.actual_eps is None else f'{q.actual_eps:,.1f}'}</td>"
        f"<td>{'' if q.model_eps is None else f'{q.model_eps:,.1f}'}</td>"
        f"<td>{'' if q.eps_error_pct is None else f'{q.eps_error_pct:.1%}'}</td>"
        f"<td>{q.direction_match}</td></tr>"
        for q in backtest.quarters
    )
    notes = profile_raw.get("consensus_notes") or []
    warning_html = ""
    if notes:
        warning_items = "".join(f"<li>{html.escape(str(note))}</li>" for note in notes)
        warning_html = f"<div class=\"card\"><b>Data warning</b><ul>{warning_items}</ul></div>"
    fy1_eps = tree.weighted_annual[0].eps_basic if tree.weighted_annual else None
    skill_html = (
        _skill_html(backtest.skill, backtest.hit_ratio_direction)
        if backtest.skill is not None
        else ""
    )
    mase_eps_card = (
        _num(backtest.skill.mase_eps) if backtest.skill is not None else "—"
    )
    content = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>{html.escape(tree.company.name)} report</title>
{plotly_script}
<style>body{{font-family:Arial,sans-serif;margin:24px;color:#111827}}table{{border-collapse:collapse;width:100%;margin:16px 0}}td,th{{border:1px solid #d1d5db;padding:6px;text-align:right}}td:first-child,th:first-child{{text-align:left}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.card{{border:1px solid #d1d5db;padding:12px;border-radius:6px}}pre{{white-space:pre-wrap;background:#f3f4f6;padding:12px}}</style>
</head><body>
<h1>{html.escape(tree.company.name_kr)} ({tree.company.ticker_yahoo})</h1>
<div class="grid">
<div class="card"><b>Weighted FY EPS</b><br>{'' if fy1_eps is None else f'{fy1_eps:,.0f}'}</div>
<div class="card"><b>Revenue MAPE</b><br>{backtest.revenue_mape:.1%}</div>
<div class="card"><b>EPS MAPE</b><br>{'' if backtest.eps_mape is None else f'{backtest.eps_mape:.1%}'}</div>
<div class="card"><b>Hit Ratio</b><br>{backtest.hit_ratio_direction:.1%}</div>
<div class="card"><b>EPS MASE (vs RW)</b><br>{mase_eps_card}</div>
</div>
{warning_html}
<h2>Forecast</h2><div id="fan"></div><div id="compare"></div>
{risk_band_section}
{below_op_event_section}
{valuation_section}
<h2>Consensus Gap</h2><table><thead><tr><th>Period</th><th>Metric</th><th>Model</th><th>Consensus</th><th>Gap</th><th>Direction</th><th>Interpretation</th></tr></thead><tbody>{gap_rows}</tbody></table>
<h2>Backtest</h2><div id="beat"></div><table><thead><tr><th>Quarter</th><th>Actual Rev</th><th>Model Rev</th><th>Rev Err</th><th>Actual EPS</th><th>Model EPS</th><th>EPS Err</th><th>Direction</th></tr></thead><tbody>{backtest_rows}</tbody></table>
{attribution_section}
{skill_html}
<h2>Assumptions</h2><pre>{html.escape(yaml.safe_dump(profile_raw, allow_unicode=True, sort_keys=False))}</pre>
<script>const fan={fan};const beat={beat};const compare={compare};Plotly.newPlot('fan',fan.data,fan.layout);Plotly.newPlot('beat',beat.data,beat.layout);Plotly.newPlot('compare',compare.data,compare.layout);{eps_band_script}{attribution_script}</script>
</body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return out_path
