"""Monte Carlo 시뮬레이션 — 핵심 변수 랜덤 샘플링 기반 밸류에이션 분포.

멀티플, WACC, DLOM 등에 확률분포를 적용하여 주당가치의 분포를 산출한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class MCInput:
    """Monte Carlo 시뮬레이션 입력 파라미터."""
    # 부문별 멀티플: {code: (mean, std)}
    multiple_params: dict[str, tuple[float, float]]
    # WACC: (mean, std)
    wacc_mean: float
    wacc_std: float
    # DLOM: (mean, std) — 0% ~ 50% 범위 clip
    dlom_mean: float
    dlom_std: float
    # Terminal growth: (mean, std)
    tg_mean: float
    tg_std: float
    n_sims: int = 10_000
    seed: int | None = 42


@dataclass
class MCResult:
    """Monte Carlo 시뮬레이션 결과."""
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
    distribution: list[int] = field(default_factory=list)  # 전체 분포 (히스토그램용)
    histogram_bins: list[int] = field(default_factory=list)
    histogram_counts: list[int] = field(default_factory=list)


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
) -> MCResult:
    """Monte Carlo 시뮬레이션 실행.

    각 시뮬레이션에서:
    1. 부문별 멀티플을 정규분포에서 샘플링 (하한 0)
    2. SOTP EV = Σ(EBITDA_i × Multiple_i)
    3. DLOM 적용한 주당 가치 산출

    Args:
        mc_input: 시뮬레이션 파라미터
        seg_ebitdas: segment code → EBITDA
        net_debt: 순차입금
        eco_frontier: 에코프론티어 파생상품부채
        cps_principal: CPS 원금
        cps_years: CPS 잔여연수
        rcps_repay: RCPS 상환액
        buyback: 보통주 매입액
        shares: 적용 주식수
        irr: FI IRR (CPS 상환금 계산용)

    Returns:
        MCResult with distribution statistics
    """
    rng = np.random.default_rng(mc_input.seed)
    n = mc_input.n_sims

    # 샘플링
    multiples_samples = {}
    for code, (mu, sigma) in mc_input.multiple_params.items():
        samples = rng.normal(mu, sigma, n)
        samples = np.maximum(samples, 0)  # 멀티플 ≥ 0
        multiples_samples[code] = samples

    dlom_samples = rng.normal(mc_input.dlom_mean, mc_input.dlom_std, n)
    dlom_samples = np.clip(dlom_samples, 0, 50)  # 0% ~ 50%

    # CPS 상환금 계산 (IRR 기반)
    cps_repay = round(cps_principal * (1 + irr / 100) ** cps_years) if cps_principal > 0 else 0

    # 시뮬레이션
    results = np.zeros(n)

    for i in range(n):
        # SOTP EV
        ev = 0
        for code, ebitda in seg_ebitdas.items():
            if ebitda > 0 and code in multiples_samples:
                ev += ebitda * multiples_samples[code][i]

        # Equity bridge
        equity = ev - net_debt - cps_repay - rcps_repay - buyback - eco_frontier

        if equity > 0 and shares > 0:
            ps = equity * unit_multiplier / shares
            # DLOM 적용
            ps *= (1 - dlom_samples[i] / 100)
            results[i] = max(ps, 0)
        else:
            results[i] = 0

    results_int = np.round(results).astype(int)

    # 히스토그램
    n_bins = min(50, max(10, n // 200))
    valid = results_int[results_int > 0]
    if len(valid) > 0:
        counts, bin_edges = np.histogram(valid, bins=n_bins)
        hist_bins = [int(b) for b in bin_edges[:-1]]
        hist_counts = [int(c) for c in counts]
    else:
        hist_bins, hist_counts = [], []

    return MCResult(
        n_sims=n,
        mean=int(np.mean(results_int)),
        median=int(np.median(results_int)),
        std=int(np.std(results_int)),
        p5=int(np.percentile(results_int, 5)),
        p25=int(np.percentile(results_int, 25)),
        p75=int(np.percentile(results_int, 75)),
        p95=int(np.percentile(results_int, 95)),
        min_val=int(np.min(results_int)),
        max_val=int(np.max(results_int)),
        distribution=results_int.tolist(),
        histogram_bins=hist_bins,
        histogram_counts=hist_counts,
    )
