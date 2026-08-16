"""Markdown summary report — GitHub README embed + cover letter quotation source.

Plain text only, no JS. Static PNG charts embedded via relative path.
Designed for grep-friendly reuse.
"""

from __future__ import annotations

from pathlib import Path

from schemas.models import (
    BacktestResult,
    BacktestSkill,
    BelowOpEventScenario,
    ConsensusGap,
    EpsRiskBand,
    ScenarioTree,
    ValuationBridgeResult,
)


def _pct(value: float | None) -> str:
    """Optional value as a percent, or em-dash when undefined (small/None sample)."""
    return "—" if value is None else f"{value:.1%}"


def _num(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def _skill_verdict(skill: BacktestSkill) -> str:
    """One-line honest verdict: skill claimed only if MASE<1 AND Theil U2<1."""
    parts = []
    for label, mase, u2 in (
        ("매출", skill.mase_revenue, skill.theil_u2_revenue),
        ("EPS", skill.mase_eps, skill.theil_u2_eps),
    ):
        if mase is None or u2 is None:
            parts.append(f"{label}: 산출 불가")
        elif mase < 1 and u2 < 1:
            parts.append(f"{label}: naive(RW) 대비 우위 (MASE<1·U2<1)")
        else:
            parts.append(f"{label}: edge 없음 (naive RW 이상 못함)")
    return " · ".join(parts)


def _skill_lines(skill: BacktestSkill, model_hit_ratio: float) -> list[str]:
    """Render the naive-baseline skill block (Korean, user-facing)."""
    lines = [
        "## Skill (naive 베이스라인 대비)",
        "",
        "> 절대 MAPE·방향 적중률은 기준점이 없어 단독 판정 불가. Random Walk(persistence)·과거 컨센서스 대비로 측정. 8Q는 작은 표본 — 점추정 과대해석 금지.",
        "",
        "| 지표 | 값 | 해석 |",
        "|---|---:|---|",
        f"| RW 매출 MAPE | {_pct(skill.naive_rw_revenue_mape)} | naive 기준 오차 |",
        f"| RW EPS MAPE | {_pct(skill.naive_rw_eps_mape)} | naive 기준 오차 |",
        f"| MASE 매출 | {_num(skill.mase_revenue)} | <1 → RW 대비 우위 |",
        f"| MASE EPS | {_num(skill.mase_eps)} | <1 → RW 대비 우위 |",
        f"| Theil U2 매출 | {_num(skill.theil_u2_revenue)} | <1 → RW 대비 우위 |",
        f"| Theil U2 EPS | {_num(skill.theil_u2_eps)} | <1 → RW 대비 우위 |",
        f"| 방향 적중률 (model vs RW) | {_pct(model_hit_ratio)} vs {_pct(skill.rw_hit_ratio_direction)} | 차이 없으면 edge 없음 |",
        f"| 컨센서스 대비 skill score (EPS) | {_num(skill.skill_score_eps_vs_consensus)} | >0 → 컨센서스 대비 우위 |",
        f"| surprise-direction 적중 (N={skill.n_surprise_scored}) | {_pct(skill.surprise_direction_accuracy)} | 컨센서스 대비 *편차* 부호 |",
        "",
        f"**판정**: {_skill_verdict(skill)}",
        "",
    ]
    if skill.n_surprise_scored < 4:
        lines += [
            f"> surprise-direction 표본 부족 (N={skill.n_surprise_scored}): 과거 컨센서스(history) 희소 — 참고용.",
            "",
        ]
    return lines


def _risk_band_lines(risk_band: EpsRiskBand) -> list[str]:
    """Below-OP EPS risk band section (Korean, user-facing).

    Separate layer from the bear/bull scenario range — different uncertainty,
    never merged (PLAN_tax_finance_overlay.md §3.1).
    """
    lines = [
        "## Below-OP 리스크 밴드 (EPS)",
        "",
        f"> below-OP 블록(순금융손익·FX 평가·일회성)의 구조적 변동성을 EPS 점추정에 넣지 않고 별도 ±밴드로 표현 "
        f"(method={risk_band.method}, k={risk_band.k:g}, ±{risk_band.half_width_pct:.1%}). "
        "bear/bull 시나리오 범위와 다른 불확실성 — 합치지 않음.",
        "",
        "| 분기 | 하한 | 점추정 | 상한 |",
        "|---|---:|---:|---:|",
    ]
    for q in risk_band.quarters:
        lines.append(
            f"| {q.period_label} | {q.eps_lower:,.0f} | {q.eps_point:,.0f} | {q.eps_upper:,.0f} |"
        )
    if risk_band.overlays:
        lines += [
            "",
            "### Overlays (밸류에이션·리스크 레이어 — EPS 점추정 불반영)",
            "",
            "| As-of | Target | Driver | Direction | Magnitude | Confidence |",
            "|---|---|---|---|---:|---:|",
        ]
        for ov in risk_band.overlays:
            lines.append(
                f"| {ov.as_of_date} | {ov.target_period_label} | {ov.driver} | "
                f"{ov.direction} | {ov.magnitude:+.2f} | {ov.confidence:.0%} |"
            )
        lines += ["", f"> {risk_band.seam_note}"]
    lines.append("")
    return lines


def _valuation_lines(
    v: ValuationBridgeResult,
    *,
    below_op_events_present: bool = False,
) -> list[str]:
    """Valuation-bridge section (Korean): EPS-gap fair-value delta + overlay score."""
    def pct(x: float | None) -> str:
        return "—" if x is None else f"{x:+.1%}"

    band = ""
    if v.fair_value_delta_low is not None and v.fair_value_delta_high is not None:
        band = f" (밴드 {pct(v.fair_value_delta_low)} ~ {pct(v.fair_value_delta_high)})"
    cons = "—" if v.consensus_eps_fy is None else f"{v.consensus_eps_fy:,.0f}"
    event_note = (
        " 원래 base/weighted EPS 점추정만 사용하며 이벤트 조정 EPS는 절대 주입하지 않음."
        if below_op_events_present
        else ""
    )
    lines = [
        f"## 밸류에이션 브리지 (FY{str(v.fiscal_year)[-2:]})",
        "",
        f"> EPS gap(모델 vs 컨센) × 탄력도 {v.elasticity:g} → 공정가치 delta.{event_note} overlay 매크로 리스크는 별도 레이어 — EPS·공정가치 delta 점값에 미반영. 탄력도는 BVT sensitivity로 확정할 draft.",
        "",
        "| 지표 | 값 |",
        "|---|---:|",
        f"| 모델 FY EPS | {v.model_eps_fy:,.0f} |",
        f"| 컨센서스 FY EPS | {cons} |",
        f"| EPS gap | {pct(v.eps_delta_pct)} |",
        f"| 공정가치 delta (탄력도 {v.elasticity:g}) | {pct(v.fair_value_delta_pct)}{band} |",
        f"| overlay 리스크 점수 (매크로, 별도) | {v.overlay_risk_score:+.3f} (n={len(v.overlays)}) |",
    ]
    if v.note:
        lines += ["", f"> {v.note}"]
    lines.append("")
    return lines


def _below_op_event_lines(scenario: BelowOpEventScenario) -> list[str]:
    """Output-only event-adjusted EPS scenario and audit register."""
    lines = [
        "## Below-OP 이벤트 조정 EPS (별도 시나리오)",
        "",
        "> 기본 EPS 점추정은 불변이다. 확률은 통계 추정치가 아닌 판단값이며 기대값은 실현 불가능한 중간값이다.",
        "> 밴드와 이벤트는 근사적으로 분리된다. 기존 8Q 밴드 표본에는 이상치가 포함되어 있으나 MAD가 그 기여를 제한한다. 잔여 중복은 0이 아니며 정량화하지 않는다.",
        "",
        "| 분기 | 시나리오 | 확률 | EPS |",
        "|---|---|---:|---:|",
    ]
    for q in scenario.quarters:
        probability = sum(event.probability for event in q.events) / len(q.events)
        lines += [
            f"| {q.period_label} | 미발생 | 0 | {q.eps_no_event:,.0f} |",
            f"| {q.period_label} | 발생 | 1 | {q.eps_if_realized:,.0f} |",
            f"| {q.period_label} | 기대값 | {probability:.0%} | {q.eps_expected:,.0f} |",
        ]
    lines += [
        "",
        "| ID | 존재 As-of | 금액 As-of | Target | Kind | Basis | 금액 (KRW bn) | Probability | Confidence | Source |",
        "|---|---|---|---|---|---|---:|---:|---|---|",
    ]
    for event in scenario.events:
        lines.append(
            f"| {event.id} | {event.as_of_date} | {event.amount_as_of} | "
            f"{event.target_period_label} | {event.kind} | {event.basis} | "
            f"{event.amount_krw_bn:,.0f} | {event.probability:.0%} | "
            f"{event.confidence} | {event.source} |"
        )
        lines += [
            "",
            f"> {event.id}: 존재는 {event.as_of_date}부터, 금액은 {event.amount_as_of}부터 인지 가능. {event.note}",
            f"> Revision trigger: {event.revision_trigger}",
        ]
    lines.append("")
    return lines


def render_md_report(
    out_path: Path,
    tree: ScenarioTree,
    consensus_gaps: list[ConsensusGap],
    backtest: BacktestResult,
    png_fan_path: Path | None = None,
    png_beat_miss_path: Path | None = None,
    consensus_notes: list[str] | None = None,
    risk_band: EpsRiskBand | None = None,
    valuation: ValuationBridgeResult | None = None,
    below_op_event_scenario: BelowOpEventScenario | None = None,
) -> Path:
    """Render the MD summary.

    Args:
        out_path: Target file path (.md).
        tree, consensus_gaps, backtest: Same inputs as html_builder.
        png_fan_path, png_beat_miss_path: Static chart paths (optional).
        risk_band: Optional below-OP EPS risk band (separate layer). None leaves
            the report unchanged.
        valuation: Optional valuation-bridge result (separate section). None leaves
            the report unchanged.

    Returns:
        out_path on success.

    Raises:
        NotImplementedError: Codex implementation.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {tree.company.name_kr} ({tree.company.ticker_yahoo}) Earnings Forecast",
        "",
        f"**As of**: {tree.as_of}",
        "",
        "## Headline",
        "",
        f"- Revenue MAPE: {backtest.revenue_mape:.1%}"
        + (f" (vs RW {_pct(backtest.skill.naive_rw_revenue_mape)}, MASE {_num(backtest.skill.mase_revenue)})" if backtest.skill else ""),
        f"- EPS MAPE: {'' if backtest.eps_mape is None else f'{backtest.eps_mape:.1%}'}"
        + (f" (vs RW {_pct(backtest.skill.naive_rw_eps_mape)}, MASE {_num(backtest.skill.mase_eps)})" if backtest.skill else ""),
        f"- Direction hit ratio (model vs RW): {backtest.hit_ratio_direction:.1%}"
        + (f" vs {_pct(backtest.skill.rw_hit_ratio_direction)}" if backtest.skill else ""),
        "",
    ]
    if consensus_notes:
        lines += ["## Data Warnings", ""]
        lines += [f"- {note}" for note in consensus_notes]
        lines.append("")
    if png_fan_path is not None:
        lines += [f"![Forecast fan chart]({png_fan_path.name})", ""]
    lines += [
        "## Consensus Gap",
        "",
        "| Period | Metric | Model | Consensus | Gap % | Direction |",
        "|---|---|---:|---:|---:|---|",
    ]
    for gap in consensus_gaps:
        lines.append(
            f"| {gap.period_label} | {gap.metric} | {gap.model_value:,.1f} | "
            f"{'' if gap.consensus_value is None else f'{gap.consensus_value:,.1f}'} | "
            f"{'' if gap.gap_pct is None else f'{gap.gap_pct:.1%}'} | {gap.direction} |"
        )
    if risk_band is not None:
        lines += [""] + _risk_band_lines(risk_band)
    if below_op_event_scenario is not None:
        lines += [""] + _below_op_event_lines(below_op_event_scenario)
    if valuation is not None:
        lines += [""] + _valuation_lines(
            valuation,
            below_op_events_present=below_op_event_scenario is not None,
        )
    lines += ["", "## Backtest", ""]
    if png_beat_miss_path is not None:
        lines += [f"![Beat miss chart]({png_beat_miss_path.name})", ""]
    lines += [
        "| Quarter | Actual Rev | Model Rev | Rev Err % | Actual EPS | Model EPS | EPS Err % | Direction |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in backtest.quarters:
        lines.append(
            f"| {row.quarter_label} | {row.actual_revenue:,.1f} | {row.model_revenue:,.1f} | "
            f"{row.revenue_error_pct:.1%} | {'' if row.actual_eps is None else f'{row.actual_eps:,.1f}'} | "
            f"{'' if row.model_eps is None else f'{row.model_eps:,.1f}'} | "
            f"{'' if row.eps_error_pct is None else f'{row.eps_error_pct:.1%}'} | {row.direction_match} |"
        )
    if backtest.skill is not None:
        lines += [""] + _skill_lines(backtest.skill, backtest.hit_ratio_direction)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return out_path
