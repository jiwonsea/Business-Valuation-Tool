"""Bridge from forecast EPS to BVT DCF fair value sensitivity (+ overlay layer).

Loose coupling: this module imports nothing from the BVT repo. It expects a
caller-supplied elasticity constant:
    fair_value_delta_pct = elasticity × eps_delta_pct
For MVP the elasticity is a YAML-provided constant (set by the user after running
BVT once with sensitivity analysis). P2 work will wire BVT directly.

Two layers are produced and kept numerically separate (CLAUDE.md two-layer split,
PLAN_valuation_bridge.md §3):
  - Layer 1 (EPS-driven): EPS gap vs consensus × elasticity -> fair-value delta,
    with a band projection from the below-OP EPS band half-width.
  - Layer 2 (macro): date-tagged overlays -> a separate entry-timing/risk score,
    NEVER folded into the layer-1 delta. This is the consumer of the overlay seam
    opened by engine.risk_band.overlay_valuation_seam.

Consensus guard: yfinance .KS consensus can be ~3x broken (HANDOFF_backtest_diag
§①-B). A missing or caller-flagged-unreliable consensus holds the fair-value delta
(None + note) rather than emitting garbage.

Below-OP event scenarios are intentionally absent from this API. Layer 1 always
reads the original ScenarioTree base/weighted EPS point; an event-adjusted EPS
must never be injected because a one-off gain would be amplified by elasticity
and incorrectly flow into recurring fair value (HANDOFF §17.2 P2).
"""

from __future__ import annotations

from collections.abc import Sequence

from schemas.models import Overlay, ScenarioTree, ValuationBridgeResult

# Risk direction -> sign on the macro overlay score (risk to value, not EPS sign).
_DIRECTION_SIGN: dict[str, float] = {"risk_up": 1.0, "neutral": 0.0, "risk_down": -1.0}


def _overlay_risk_score(overlays: Sequence[Overlay], overlay_weight: float) -> float:
    """Signed, confidence-weighted sum of overlays (layer 2, macro)."""
    return overlay_weight * sum(
        _DIRECTION_SIGN[o.direction] * o.magnitude * o.confidence for o in overlays
    )


def sensitivity_to_dcf(
    model_tree: ScenarioTree,
    consensus_eps_fy: float | None,
    fair_value_elasticity: float = 1.2,
    *,
    eps_half_width_pct: float | None = None,
    overlays: Sequence[Overlay] | None = None,
    overlay_weight: float = 1.0,
    consensus_reliable: bool = True,
) -> ValuationBridgeResult:
    """Compute implied fair-value delta vs consensus + the macro overlay score.

    The bridge deliberately reads the existing weighted point-estimate EPS only.
    Identified below-OP event scenarios are excluded: a one-time disposal gain
    must not be amplified by ``fair_value_elasticity`` into recurring fair value.

    Args:
        model_tree: Full tree — weighted_annual FY1 EPS is used (read-only).
        consensus_eps_fy: Consensus EPS for the same fiscal year (None if absent).
        fair_value_elasticity: EPS-delta -> fair-value-delta multiplier (YAML draft;
            1.2 is a placeholder assuming roughly linear DCF response with small
            terminal-value amplification).
        eps_half_width_pct: Below-OP EPS band half-width (EpsRiskBand.half_width_pct);
            when given, projects a fair-value band around the point delta.
        overlays: Date-tagged macro/timing/risk overlays (layer 2 only).
        overlay_weight: YAML draft weight on the aggregated overlay score.
        consensus_reliable: Caller (cli) sets False when the consensus snapshot is
            flagged unreliable (ConsensusRecord.notes present, §①-B).

    Returns:
        ValuationBridgeResult — fair_value_delta_pct is None (with a note) when the
        consensus is missing or unreliable; overlay_risk_score is always computed.

    Raises:
        ValueError: model_tree has no weighted FY1 EPS to bridge from.
    """
    annual = model_tree.weighted_annual
    if not annual or annual[0].eps_basic is None:
        raise ValueError("model_tree.weighted_annual[0].eps_basic is required")
    fy = annual[0]
    model_eps = fy.eps_basic

    overlay_list = list(overlays or [])
    overlay_risk_score = _overlay_risk_score(overlay_list, overlay_weight)

    eps_delta_pct: float | None = None
    fair_value_delta_pct: float | None = None
    fair_value_delta_low: float | None = None
    fair_value_delta_high: float | None = None
    note = ""

    if consensus_eps_fy in (None, 0):
        note = "컨센서스 FY EPS 부재 — fair-value delta 보류."
    elif not consensus_reliable:
        note = "컨센서스 신뢰불가(reliability 가드, §①-B) — fair-value delta 보류."
    else:
        eps_delta_pct = (model_eps - consensus_eps_fy) / consensus_eps_fy
        fair_value_delta_pct = fair_value_elasticity * eps_delta_pct
        if eps_half_width_pct is not None:
            low_eps = model_eps * (1 - eps_half_width_pct)
            high_eps = model_eps * (1 + eps_half_width_pct)
            fair_value_delta_low = fair_value_elasticity * (low_eps - consensus_eps_fy) / consensus_eps_fy
            fair_value_delta_high = fair_value_elasticity * (high_eps - consensus_eps_fy) / consensus_eps_fy

    return ValuationBridgeResult(
        fiscal_year=fy.fiscal_year,
        model_eps_fy=model_eps,
        consensus_eps_fy=consensus_eps_fy,
        eps_delta_pct=eps_delta_pct,
        elasticity=fair_value_elasticity,
        fair_value_delta_pct=fair_value_delta_pct,
        fair_value_delta_low=fair_value_delta_low,
        fair_value_delta_high=fair_value_delta_high,
        overlay_risk_score=overlay_risk_score,
        overlays=overlay_list,
        note=note,
    )
