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
    wacc_for_dcf: float = 0.0,
    dcf_last_fcff: int = 0,
    dcf_pv_fcff_sum: int = 0,
    dcf_n_periods: int = 5,
) -> MCResult:
    """Monte Carlo 시뮬레이션 실행.

    각 시뮬레이션에서:
    1. 부문별 멀티플을 정규분포에서 샘플링 (하한 0)
    2. SOTP EV = Σ(EBITDA_i × Multiple_i)
    3. WACC/TG 샘플링으로 DCF TV 변동 반영 (DCF 정보 제공 시)
    4. DLOM 적용한 주당 가치 산출

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
        wacc_for_dcf: DCF TV 샘플링용 기준 WACC (%, 0이면 DCF 미적용)
        dcf_last_fcff: DCF 마지막 연도 FCFF (TV 재계산용)
        dcf_pv_fcff_sum: DCF 예측기간 PV 합계 (고정)
        dcf_n_periods: DCF 예측 기간 수

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

    # WACC / Terminal Growth 샘플링 (DCF TV 변동 반영)
    wacc_samples = rng.normal(mc_input.wacc_mean, mc_input.wacc_std, n)
    wacc_samples = np.maximum(wacc_samples, 1.0)  # WACC ≥ 1%
    tg_samples = rng.normal(mc_input.tg_mean, mc_input.tg_std, n)
    tg_samples = np.clip(tg_samples, 0, wacc_samples - 0.5)  # TG < WACC - 0.5%

    use_dcf_tv = wacc_for_dcf > 0 and dcf_last_fcff > 0

    # CPS 상환금 계산 (IRR 기반)
    cps_repay = round(cps_principal * (1 + irr / 100) ** cps_years) if cps_principal > 0 else 0

    # 벡터화된 SOTP EV 계산
    ev = np.zeros(n)
    for code, ebitda in seg_ebitdas.items():
        if ebitda > 0 and code in multiples_samples:
            ev += ebitda * multiples_samples[code]

    # DCF TV 변동 반영 (벡터화)
    if use_dcf_tv:
        w = wacc_samples / 100
        g = tg_samples / 100
        valid = w > g
        tv_sample = np.where(valid, dcf_last_fcff * (1 + g) / (w - g), 0)
        pv_tv_sample = np.where(valid, tv_sample / (1 + w) ** dcf_n_periods, 0)
        dcf_ev_sample = dcf_pv_fcff_sum + pv_tv_sample

        # 기준 DCF EV (스칼라, 루프 밖에서 1회만 계산)
        w0 = wacc_for_dcf / 100
        g0 = mc_input.tg_mean / 100
        tv_base = dcf_last_fcff * (1 + g0) / (w0 - g0)
        pv_tv_base = tv_base / (1 + w0) ** dcf_n_periods
        dcf_ev_base = dcf_pv_fcff_sum + pv_tv_base

        if dcf_ev_base > 0:
            ev = np.where(valid, ev * (dcf_ev_sample / dcf_ev_base), ev)

    # Equity bridge (벡터화)
    claims = net_debt + cps_repay + rcps_repay + buyback + eco_frontier
    equity = ev - claims

    if shares > 0:
        ps = equity * (unit_multiplier / shares)
        ps *= (1 - dlom_samples / 100)
        results = np.maximum(ps, 0)
    else:
        results = np.zeros(n)

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
