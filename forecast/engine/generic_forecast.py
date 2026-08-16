"""Generic (sector-agnostic) top-down earnings forecast.

Pure functions. Consumes a :class:`schemas.generic.GenericProfile` and produces
:class:`schemas.models.QuarterlyForecast` / ``AnnualForecast`` objects so the rest
of the pipeline (scenario weighting shape, skill metrics) stays shared with the
memory path. See schemas/generic.py for the model rationale.

Per-quarter recursion (see module docstring in schemas/generic.py):
    revenue_q = revenue_{q-1} x (1 + growth_qoq[i])
    op        = revenue_q x op_margin[i]
    pretax    = op + net_interest_pct[i] x revenue_q
    net       = pretax x (1 - tax[i])
    eps       = net x unit_scale / shares
"""

from __future__ import annotations

from schemas.generic import GenericProfile, GenericScenarioAssumptions
from schemas.models import AnnualForecast, QuarterlyForecast, SegmentForecast
from engine.scenario import aggregate_quarterly_to_annual
from engine.segment_revenue import _next_quarter_label


def project_scenario(
    profile: GenericProfile,
    assumptions: GenericScenarioAssumptions,
    scenario: str,
) -> list[QuarterlyForecast]:
    """Project the forward window for one scenario from the seed quarter."""
    n = profile.window.n_quarters
    growth = assumptions.growth(n)
    op_margin = assumptions.margin(n)
    tax = assumptions.tax(n)
    net_int = assumptions.net_interest(n)
    scale = profile.unit_scale
    shares = profile.weighted_avg_diluted

    revenue = profile.seed.revenue_total
    label = profile.seed.quarter_label
    out: list[QuarterlyForecast] = []
    for i in range(n):
        label = _next_quarter_label(label)
        revenue = revenue * (1.0 + growth[i])
        op = revenue * op_margin[i]
        pretax = op + net_int[i] * revenue
        net = pretax * (1.0 - tax[i])
        eps = net * scale / shares
        out.append(
            QuarterlyForecast(
                quarter_label=label,
                scenario=scenario,  # type: ignore[arg-type]
                revenue_total=revenue,
                revenue_by_segment=[SegmentForecast(segment_id="total", revenue=revenue)],
                gross_profit=0.0,  # generic path does not decompose gross margin
                operating_profit=op,
                net_profit=net,
                gp_margin=0.0,
                op_margin=op_margin[i],
                np_margin=(net / revenue) if revenue else 0.0,
                eps_basic=eps,
                eps_diluted=eps,
            )
        )
    return out


def _weight_quarterly(
    scenarios: dict[str, list[QuarterlyForecast]], probs: dict[str, float]
) -> list[QuarterlyForecast]:
    labels = scenarios["base"]
    weighted: list[QuarterlyForecast] = []
    for idx, ref in enumerate(labels):
        rev = sum(probs[s] * scenarios[s][idx].revenue_total for s in scenarios)
        op = sum(probs[s] * scenarios[s][idx].operating_profit for s in scenarios)
        net = sum(probs[s] * scenarios[s][idx].net_profit for s in scenarios)
        eps = sum(probs[s] * (scenarios[s][idx].eps_diluted or 0.0) for s in scenarios)
        weighted.append(
            QuarterlyForecast(
                quarter_label=ref.quarter_label,
                scenario="weighted",
                revenue_total=rev,
                revenue_by_segment=[SegmentForecast(segment_id="total", revenue=rev)],
                gross_profit=0.0,
                operating_profit=op,
                net_profit=net,
                gp_margin=0.0,
                op_margin=(op / rev) if rev else 0.0,
                np_margin=(net / rev) if rev else 0.0,
                eps_basic=eps,
                eps_diluted=eps,
            )
        )
    return weighted


class GenericForecast:
    """Container for a full generic run (kept plain to avoid CompanyMeta coupling)."""

    def __init__(
        self,
        profile: GenericProfile,
        scenarios_quarterly: dict[str, list[QuarterlyForecast]],
        scenarios_annual: dict[str, list[AnnualForecast]],
        weighted_quarterly: list[QuarterlyForecast],
        weighted_annual: list[AnnualForecast],
    ) -> None:
        self.profile = profile
        self.scenarios_quarterly = scenarios_quarterly
        self.scenarios_annual = scenarios_annual
        self.weighted_quarterly = weighted_quarterly
        self.weighted_annual = weighted_annual


def run_generic_forecast(profile: GenericProfile) -> GenericForecast:
    """Build bear/base/bull cases, annualise, and probability-weight them."""
    cases = {"bear": profile.bear, "base": profile.base, "bull": profile.bull}
    probs = {name: c.probability for name, c in cases.items()}

    scen_q: dict[str, list[QuarterlyForecast]] = {}
    scen_a: dict[str, list[AnnualForecast]] = {}
    for name, assumptions in cases.items():
        q = project_scenario(profile, assumptions, name)
        scen_q[name] = q
        scen_a[name] = aggregate_quarterly_to_annual(q, scenario=name)

    weighted_q = _weight_quarterly(scen_q, probs)
    weighted_a = aggregate_quarterly_to_annual(weighted_q, scenario="weighted")
    return GenericForecast(profile, scen_q, scen_a, weighted_q, weighted_a)
