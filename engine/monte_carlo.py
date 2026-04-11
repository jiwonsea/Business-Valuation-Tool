"""Monte Carlo simulation -- valuation distribution via random sampling of key variables.

Applies probability distributions to multiples, WACC, DLOM, etc. to generate
the distribution of per-share values.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class MCInput:
    """Monte Carlo simulation input parameters."""
    # Per-segment multiples: {code: (mean, std)}
    multiple_params: dict[str, tuple[float, float]]
    # WACC: (mean, std)
    wacc_mean: float
    wacc_std: float
    # DLOM: (mean, std) -- clipped to 0%~50% range
    dlom_mean: float
    dlom_std: float
    # Terminal growth: (mean, std)
    tg_mean: float
    tg_std: float
    n_sims: int = 10_000
    seed: int | None = 42
    # Per-segment valuation method: {code: "ev_ebitda"|"ev_revenue"}
    segment_methods: dict[str, str] = field(default_factory=dict)
    # Per-segment revenue uncertainty: {code: (mean, std)} for ev_revenue segments
    revenue_params: dict[str, tuple[float, float]] = field(default_factory=dict)


@dataclass
class MCResult:
    """Monte Carlo simulation result."""
    n_sims: int
    mean: int
    median: int
    std: int
    p5: int   # 5th percentile
    p25: int
    p75: int
    p95: int
    min_val: int
    max_val: int
    distribution: list[int] = field(default_factory=list)  # Full distribution (for histogram)
    histogram_bins: list[int] = field(default_factory=list)
    histogram_counts: list[int] = field(default_factory=list)
    pct_negative: float = 0.0  # Percentage of simulations with negative/zero equity


def run_monte_carlo(
    mc_input: MCInput,
    seg_ebitdas: dict[str, int],
    net_debt: int,
    eco_frontier: int,
    cps_principal: int,
    cps_years: int,
    rcps_repay: int,
    buyback: int,
    shares: int,
    irr: float = 5.0,
    unit_multiplier: int = 1_000_000,
    wacc_for_dcf: float = 0.0,
    dcf_last_fcff: int = 0,
    dcf_pv_fcff_sum: int = 0,
    dcf_n_periods: int = 5,
    seg_revenues: dict[str, int] | None = None,
    cps_dividend_rate: float = 0.0,
) -> MCResult:
    """Run Monte Carlo simulation.

    Per simulation:
    1. Sample per-segment multiples from normal distribution (floor at 0)
    2. SOTP EV = sum(EBITDA_i x Multiple_i)
    3. Sample WACC/TG to reflect DCF TV variation (when DCF info provided)
    4. Compute per-share value with DLOM applied

    Args:
        mc_input: Simulation parameters (with segment_methods for ev_revenue dispatch)
        seg_ebitdas: segment code -> EBITDA (base for ev_ebitda segments)
        net_debt: Net debt
        eco_frontier: Eco Frontier derivative liability
        cps_principal: CPS principal
        cps_years: CPS remaining years
        rcps_repay: RCPS redemption amount
        buyback: Common share buyback amount
        shares: Applied share count
        irr: FI IRR (for CPS redemption calculation)
        wacc_for_dcf: Base WACC for DCF TV sampling (%, 0 disables DCF)
        dcf_last_fcff: Last-year FCFF from DCF (for TV recalculation)
        dcf_pv_fcff_sum: DCF projection period PV sum (fixed)
        dcf_n_periods: Number of DCF projection periods
        seg_revenues: segment code -> Revenue (base for ev_revenue segments)

    Returns:
        MCResult with distribution statistics
    """
    rng = np.random.default_rng(mc_input.seed)
    n = mc_input.n_sims

    # Sampling
    multiples_samples = {}
    for code, (mu, sigma) in mc_input.multiple_params.items():
        samples = rng.normal(mu, sigma, n)
        samples = np.maximum(samples, 0)  # Multiple >= 0
        multiples_samples[code] = samples

    dlom_samples = rng.normal(mc_input.dlom_mean, mc_input.dlom_std, n)
    dlom_samples = np.clip(dlom_samples, 0, 50)  # 0% ~ 50%

    # WACC / Terminal Growth sampling (reflects DCF TV variation)
    wacc_samples = rng.normal(mc_input.wacc_mean, mc_input.wacc_std, n)
    wacc_samples = np.maximum(wacc_samples, 1.0)  # WACC ≥ 1%
    tg_samples = rng.normal(mc_input.tg_mean, mc_input.tg_std, n)
    tg_samples = np.clip(tg_samples, 0, wacc_samples - 0.5)  # TG < WACC - 0.5%

    use_dcf_tv = wacc_for_dcf > 0 and dcf_last_fcff > 0

    # CPS redemption calculation (effective_rate = IRR - dividend_rate, consistent with calc_scenario)
    effective_irr = max(irr - cps_dividend_rate, 0.0)
    cps_repay = round(cps_principal * (1 + effective_irr / 100) ** cps_years) if cps_principal > 0 else 0

    # Revenue uncertainty sampling for ev_revenue segments
    revenue_samples: dict[str, np.ndarray] = {}
    for code, (r_mu, r_sigma) in mc_input.revenue_params.items():
        if r_sigma > 0:
            rev_s = rng.normal(r_mu, r_sigma, n)
            revenue_samples[code] = np.maximum(rev_s, 0)  # Revenue >= 0

    # Vectorized SOTP EV calculation (ev_ebitda: EBITDA*mult, ev_revenue: Revenue*mult)
    ev_ebitda_part = np.zeros(n)
    ev_revenue_part = np.zeros(n)
    for code, ebitda in seg_ebitdas.items():
        if code not in multiples_samples:
            continue
        method = mc_input.segment_methods.get(code, "ev_ebitda")
        if method == "ev_revenue":
            if code in revenue_samples:
                ev_revenue_part += revenue_samples[code] * multiples_samples[code]
            else:
                rev = (seg_revenues or {}).get(code, 0)
                if rev > 0:
                    ev_revenue_part += rev * multiples_samples[code]
        elif method in ("pbv", "pe"):
            # PBV/PE segments use book value or net income, not EBITDA — skip in MC
            continue
        else:
            # Include negative EBITDA segments (consistent with calc_sotp)
            ev_ebitda_part += ebitda * multiples_samples[code]

    # DCF TV variation applies only to EBITDA-based EV (not revenue-based optionality)
    if use_dcf_tv:
        w = wacc_samples / 100
        g = tg_samples / 100
        valid = w > g
        tv_sample = np.where(valid, dcf_last_fcff * (1 + g) / (w - g), 0)
        pv_tv_sample = np.where(valid, tv_sample / (1 + w) ** dcf_n_periods, 0)
        dcf_ev_sample = dcf_pv_fcff_sum + pv_tv_sample

        # Base DCF EV (scalar, computed once outside loop)
        w0 = wacc_for_dcf / 100
        g0 = mc_input.tg_mean / 100
        tv_base = dcf_last_fcff * (1 + g0) / (w0 - g0)
        pv_tv_base = tv_base / (1 + w0) ** dcf_n_periods
        dcf_ev_base = dcf_pv_fcff_sum + pv_tv_base

        if dcf_ev_base > 0:
            ratio = np.where(valid, dcf_ev_sample / dcf_ev_base, 1.0)
            ratio = np.clip(ratio, 0.0, 3.0)  # Cap TV scaling to prevent fat-tail contamination
            ev_ebitda_part = np.where(valid, ev_ebitda_part * ratio, ev_ebitda_part)

    ev = ev_ebitda_part + ev_revenue_part

    # Equity bridge (vectorized)
    claims = net_debt + cps_repay + rcps_repay + buyback + eco_frontier
    equity = ev - claims

    if shares > 0:
        ps = equity * (unit_multiplier / shares)
        ps *= (1 - dlom_samples / 100)
        results = ps  # preserve negatives — clipping upward-biases mean/percentiles
    else:
        results = np.zeros(n)

    results_int = np.round(results).astype(int)

    # Count true negatives (before any histogram filtering)
    neg_mask = results_int < 0
    pct_neg = round(float(neg_mask.sum()) / n * 100, 1) if n > 0 else 0.0

    # Histogram uses positive-only set (display: negative equity not plotted)
    valid = results_int[~neg_mask]
    n_bins = min(50, max(10, n // 200))
    if len(valid) > 0:
        counts, bin_edges = np.histogram(valid, bins=n_bins)
        hist_bins = [int(b) for b in bin_edges[:-1]]
        hist_counts = [int(c) for c in counts]
    else:
        hist_bins, hist_counts = [], []

    # Statistics on full distribution (negatives included) for unbiased percentiles
    stats_set = results_int if len(results_int) > 0 else valid

    return MCResult(
        n_sims=n,
        mean=int(np.mean(stats_set)),
        median=int(np.median(stats_set)),
        std=int(np.std(stats_set)),
        p5=int(np.percentile(stats_set, 5)),
        p25=int(np.percentile(stats_set, 25)),
        p75=int(np.percentile(stats_set, 75)),
        p95=int(np.percentile(stats_set, 95)),
        min_val=int(np.min(stats_set)),
        max_val=int(np.max(stats_set)),
        distribution=results_int.tolist(),
        histogram_bins=hist_bins,
        histogram_counts=hist_counts,
        pct_negative=pct_neg,
    )
