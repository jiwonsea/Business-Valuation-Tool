"""Model (base case) vs Yahoo consensus gap calculation.

Per-period: model_value, consensus_value, gap_abs, gap_pct, direction.
`interpretation` field is intentionally left blank — user fills in 1-2 sentences
(thesis why the gap exists). Auto-generated interpretations are forbidden.
"""

from __future__ import annotations

from schemas.models import ConsensusGap, ConsensusRecord, ScenarioTree


IN_LINE_THRESHOLD_PCT = 0.02   # within ±2% counted as in-line


def compute_consensus_gap(
    model_tree: ScenarioTree,
    consensus: ConsensusRecord,
) -> list[ConsensusGap]:
    """Compare base-case model output to consensus per quarter and per fiscal year.

    Args:
        model_tree: Full scenario tree — base case is used for comparison.
        consensus: yfinance-derived consensus snapshot.

    Returns:
        List of ConsensusGap covering all periods where either model or consensus
        has a value. When consensus is missing, direction="n_a" and gap_* are None.

    Note:
        The `interpretation` field is left empty by design — user populates
        after reading the gap. See docs/sk_hynix_thesis.md.

    Raises:
        NotImplementedError: Codex implementation.
    """
    gaps: list[ConsensusGap] = []

    def build(period_label: str, metric: str, model_value: float, consensus_value: float | None) -> None:
        if consensus_value in (None, 0):
            gap_abs = None
            gap_pct = None
            direction = "n_a"
        else:
            gap_abs = model_value - consensus_value
            gap_pct = gap_abs / consensus_value
            if gap_pct > IN_LINE_THRESHOLD_PCT:
                direction = "above"
            elif gap_pct < -IN_LINE_THRESHOLD_PCT:
                direction = "below"
            else:
                direction = "in_line"
        gaps.append(
            ConsensusGap(
                period_label=period_label,
                metric=metric,  # type: ignore[arg-type]
                model_value=model_value,
                consensus_value=consensus_value,
                gap_abs=gap_abs,
                gap_pct=gap_pct,
                direction=direction,  # type: ignore[arg-type]
                interpretation="",
            )
        )

    for quarter in model_tree.base.quarterly:
        build(
            quarter.quarter_label,
            "revenue",
            quarter.revenue_total,
            consensus.revenue_estimate_quarterly.get(quarter.quarter_label),
        )
        if quarter.eps_basic is not None:
            build(
                quarter.quarter_label,
                "eps",
                quarter.eps_basic,
                consensus.eps_estimate_quarterly.get(quarter.quarter_label),
            )

    for annual in model_tree.base.annual:
        label = f"FY{str(annual.fiscal_year)[-2:]}"
        build(
            label,
            "revenue",
            annual.revenue_total,
            consensus.revenue_estimate_annual.get(annual.fiscal_year),
        )
        if annual.eps_basic is not None:
            build(label, "eps", annual.eps_basic, consensus.eps_estimate_annual.get(annual.fiscal_year))
    return gaps
