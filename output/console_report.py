"""Console report output."""

from schemas.models import ValuationInput, ValuationResult
from valuation_runner import _seg_names


def print_report(vi: ValuationInput, result: ValuationResult):
    """Print valuation results to the console."""
    if vi.draft or result.draft:
        print("!" * 60)
        print("DRAFT / NOT FOR PUBLICATION - assumptions are not fully verified")
        print("!" * 60)
    by = vi.base_year
    seg_names = _seg_names(vi)
    unit = vi.company.currency_unit
    currency_sym = "원" if vi.company.market == "KR" else "$"

    # Dynamic column width for segment names
    _seg_w = max((len(n) for n in seg_names.values()), default=12)
    _seg_w = max(_seg_w, 8)  # minimum width

    print("=" * 60)
    print(f"{vi.company.name} 기업가치평가 모델 [{result.primary_method.upper()}]")
    print("=" * 60)
    print(f"재무 앵커: {vi.financial_anchor.upper()} (base year FY{vi.base_year})")
    if vi.financial_anchor == "ttm" and vi.fy_base_financials:
        fy_revenue = vi.fy_base_financials.get("revenue", 0)
        ttm_revenue = vi.consolidated[by].get("revenue", 0)
        if fy_revenue:
            delta = (ttm_revenue / fy_revenue - 1) * 100
            print(
                f"FY/TTM 매출 차이: {fy_revenue:,} → {ttm_revenue:,}{unit} "
                f"({delta:+.1f}%)"
            )
    elif vi.financial_anchor_fallback_reason:
        print(f"TTM fallback: {vi.financial_anchor_fallback_reason}")
    if vi.forward_anchor:
        forward = vi.forward_anchor
        metrics = []
        if forward.revenue:
            metrics.append(
                f"매출 {forward.revenue.value:,.0f}{forward.revenue.unit} "
                f"(n={forward.revenue.n_analysts})"
            )
        if forward.eps:
            metrics.append(
                f"EPS {forward.eps.value:,.2f} {forward.eps.unit} "
                f"(n={forward.eps.n_analysts})"
            )
        period_label = forward.fiscal_period or f"컨센서스 {forward.relative_period}"
        print(
            f"{period_label} 컨센서스 (예측치, {forward.provider}): "
            + " | ".join(metrics)
        )
    if vi.peer_beta_snapshot:
        judgement = vi.peer_beta_snapshot.judgement
        print(
            f"Peer beta 판정: {judgement.status} "
            f"(raw βL={judgement.company_raw_bl:.3f}, n={judgement.n_qualified})"
        )
    for warning in vi.scenario_spread_warnings:
        print(f"⚠ {warning}")
    for warning in vi.share_count_warnings:
        print(f"⚠ {warning}")

    # WACC
    w = result.wacc
    print(f"\n[WACC] βL={w.bl}, Ke={w.ke}%, Kd(세후)={w.kd_at}%, WACC={w.wacc}%")

    # Distress discount (SOTP only) -- report the engine result; never recalculate here.
    multiple_changes = []
    if result.primary_method == "sotp":
        for code, segment_result in result.sotp.items():
            original = vi.multiples.get(code, 0)
            applied = segment_result.multiple
            if abs(original - applied) > 1e-9:
                multiple_changes.append((code, original, applied))
    if multiple_changes:
        print("\n[Distress Haircut] 엔진 적용 배수")
        for code, original, applied in multiple_changes:
            print(f"  {seg_names.get(code, code)}: {original:.4g}x → {applied:.4g}x")

    # Mixed SOTP determination (any non-default method: ev_revenue, pbv, pe)
    is_mixed = any(
        info.get("method") not in (None, "ev_ebitda") for info in vi.segments.values()
    )

    # D&A allocation (SOTP only)
    if result.da_allocations and by in result.da_allocations:
        total_da = vi.consolidated[by]["dep"] + vi.consolidated[by]["amort"]
        da_note = " (금융 부문 제외)" if is_mixed else ""
        print(f"\n[D&A 배분{da_note}] 총 D&A = {total_da:,}{unit}")
        if is_mixed:
            print(
                f"{'부문':<{_seg_w}} {'Method':<10} {'자산비중':>8} {'D&A':>12} {'EBITDA':>14}"
            )
        else:
            print(f"{'부문':<{_seg_w + 2}} {'자산비중':>10} {'D&A':>12} {'EBITDA':>14}")
        print("-" * (_seg_w + 50))
        alloc = result.da_allocations[by]
        for code in vi.segments:
            if code in alloc:
                a = alloc[code]
                if is_mixed:
                    method = vi.segments[code].get("method", "ev_ebitda")
                    rev_type = vi.segments[code].get("revenue_type", "ltm")
                    rev_tag = (
                        f" ({rev_type.upper()})"
                        if method == "ev_revenue" and rev_type != "ltm"
                        else ""
                    )
                    m_lbl = {
                        "ev_ebitda": "EV/EBITDA",
                        "pbv": "P/BV",
                        "pe": "P/E",
                        "ev_revenue": "EV/Revenue",
                    }.get(method, method)
                    print(
                        f"{seg_names.get(code, code):<{_seg_w}} {m_lbl}{rev_tag:<10} {a.asset_share:>7.2f}% {a.da_allocated:>11,} {a.ebitda:>13,}"
                    )
                else:
                    print(
                        f"{seg_names.get(code, code):<{_seg_w + 2}} {a.asset_share:>9.2f}% {a.da_allocated:>11,} {a.ebitda:>13,}"
                    )

    # SOTP (if available)
    if result.sotp:
        sotp_ev = sum(s.ev for s in result.sotp.values())
        if is_mixed:
            print("\n[SOTP (Mixed Method)]")
            for code in vi.segments:
                if code in result.sotp:
                    s = result.sotp[code]
                    method = getattr(s, "method", "ev_ebitda")
                    rev_type_tag = (
                        f" ({s.revenue_type.upper()})"
                        if method == "ev_revenue" and s.revenue_type != "ltm"
                        else ""
                    )
                    m_lbl = {
                        "ev_ebitda": "EV/EBITDA",
                        "pbv": "P/BV",
                        "pe": "P/E",
                        "ev_revenue": "EV/Revenue",
                    }.get(method, method)
                    eq_tag = (
                        " [Equity]" if getattr(s, "is_equity_based", False) else " [EV]"
                    )
                    print(
                        f"  {seg_names.get(code, code):<{_seg_w}} {m_lbl}{rev_type_tag:<10} {s.multiple:.5g}x → {s.ev:>14,}{unit}{eq_tag}"
                    )
            print(f"  {'합계':<{_seg_w + 12}} {sotp_ev:>14,}{unit}")
            # Equity Bridge (only when pbv/pe equity-based segments exist)
            has_equity_methods = any(
                info.get("method") in ("pbv", "pe") for info in vi.segments.values()
            )
            if has_equity_methods:
                fin_debt = sum(
                    vi.segment_net_debt.get(c, 0)
                    for c, info in vi.segments.items()
                    if info.get("method") in ("pbv", "pe")
                )
                eff_nd = vi.net_debt - fin_debt
                ev_part = sum(
                    s.ev
                    for s in result.sotp.values()
                    if not getattr(s, "is_equity_based", False)
                )
                eq_part = sum(
                    s.ev
                    for s in result.sotp.values()
                    if getattr(s, "is_equity_based", False)
                )
                print("\n[Equity Bridge]")
                print(f"  연결 순차입금:     {vi.net_debt:>14,}{unit}")
                print(f"  (-) 금융부문 부채: {fin_debt:>14,}{unit}")
                print(f"  유효 순차입금:     {eff_nd:>14,}{unit}")
                print(f"  제조 EV:           {ev_part:>14,}{unit}")
                print(f"  제조 Equity:       {ev_part - eff_nd:>14,}{unit}")
                print(f"  (+) 금융 Equity:   {eq_part:>14,}{unit}")
                print(f"  Total Equity:      {ev_part - eff_nd + eq_part:>14,}{unit}")
        else:
            # Check if any optionality segments are present (ev=0 in base, value in scenarios)
            opt_codes = [
                c for c, info in vi.segments.items() if info.get("optionality")
            ]
            has_opt = bool(opt_codes)
            label = "SOTP EV (기본 운영 세그먼트)" if has_opt else "SOTP EV"
            print(f"\n[{label}] {sotp_ev:>14,}{unit}")
            if has_opt:
                print(
                    f"  ※ 옵셔널리티 세그먼트({', '.join(seg_names.get(c, c) for c in opt_codes)})는 "
                    f"시나리오별 가중치에 반영됨 (기본 SOTP 제외)"
                )

        if result.holding_discount and result.holding_discount.enabled:
            hd = result.holding_discount
            print("\n[Holding Discount Bridge]")
            print(f"  Gross SOTP:                     {hd.gross_sotp_value:>14,}{unit}")
            print(
                f"  Listed Subsidiary Look-through: {hd.listed_subsidiary_lookthrough_value:>14,}{unit}"
            )
            print(
                f"  Parent Access Discount:        -{hd.parent_access_discount:>14,}{unit}"
            )
            print(
                f"  Governance Discount:           -{hd.governance_discount:>14,}{unit}"
            )
            print(
                f"  Overhang Discount:             -{hd.overhang_discount:>14,}{unit}"
            )
            print(f"  Net Parent Equity:              {hd.net_equity_value:>14,}{unit}")
            for warning in hd.warnings:
                print(f"  - {warning}")

    # Scenarios
    if result.scenarios:
        print("\n[시나리오 분석]")
        for code, sc in vi.scenarios.items():
            if code in result.scenarios:
                r = result.scenarios[code]
                print(
                    f"  시나리오 {code} ({sc.name}, {sc.prob}%): "
                    f"Equity={r.equity_value:>12,}{unit}, "
                    + (
                        f"AR회수={r.receivable_recovery_value:>10,}{unit}, "
                        if r.receivable_recovery_value
                        else ""
                    )
                    + f"주당(DLOM후)={r.post_dlom:>8,}{currency_sym}, "
                    f"가중기여={r.weighted:>6,}{currency_sym}"
                )
        print(f"\n  >> 확률가중 주당 가치: {result.weighted_value:,}{currency_sym}")

    # DDM
    if result.ddm:
        d = result.ddm
        print("\n[DDM (Gordon Growth)]")
        if d.buyback_per_share > 0:
            print(
                f"  DPS: {d.dps:,.0f}{currency_sym}, 자사주매입: {d.buyback_per_share:,.0f}{currency_sym}"
            )
            print(
                f"  Total Payout: {d.total_payout:,.0f}{currency_sym}, 성장률: {d.growth}%, Ke: {d.ke}%"
            )
        else:
            print(
                f"  DPS: {d.dps:,.0f}{currency_sym}, 배당성장률: {d.growth}%, Ke: {d.ke}%"
            )
        print(f"  주당 내재가치: {d.equity_per_share:,}{currency_sym}")

    # RIM
    if result.rim:
        r = result.rim
        print("\n[RIM (잔여이익모델)]")
        print(f"  장부가치(BV): {r.bv_current:,}{unit}, Ke: {r.ke}%")
        print(f"  PV(RI): {r.pv_ri_sum:,}{unit}, PV(TV): {r.pv_terminal:,}{unit}")
        print(f"  자기자본가치: {r.equity_value:,}{unit}")
        print(f"  주당 내재가치: {r.per_share:,}{currency_sym}")

    # rNPV
    if result.rnpv:
        rn = result.rnpv
        print("\n[rNPV (파이프라인 밸류에이션)]")
        print(f"  할인율: {rn.discount_rate:.1f}%")
        print(
            f"  {'약물':<25s} {'단계':<12s} {'PoS':>6s} {'피크매출':>12s} {'NPV':>12s} {'rNPV':>12s}"
        )
        print(f"  {'-' * 25} {'-' * 12} {'-' * 6} {'-' * 12} {'-' * 12} {'-' * 12}")
        for dr in rn.drug_results:
            print(
                f"  {dr.name:<25s} {dr.phase:<12s} {dr.success_prob:>5.0%} "
                f"{dr.peak_sales:>12,} {dr.npv_unadjusted:>12,} {dr.rnpv:>12,}"
            )
        print(
            f"  {'':>25s} {'':>12s} {'':>6s} {'총 rNPV':>12s} {'':>12s} {rn.total_rnpv:>12,}{unit}"
        )
        if rn.r_and_d_cost_pv:
            print(f"  R&D 비용 PV: -{rn.r_and_d_cost_pv:,}{unit}")
        print(f"  파이프라인 가치: {rn.pipeline_value:,}{unit}")
        print(f"  기업가치(EV): {rn.enterprise_value:,}{unit}")
        print(f"  주당 내재가치: {rn.per_share:,}{currency_sym}")

    # Reverse rNPV
    if result.reverse_rnpv:
        rv = result.reverse_rnpv
        print(
            f"\n[역방향 rNPV 분석] 모델 EV {rv.model_ev:,} vs 시장 EV {rv.target_ev:,}{unit} (괴리 {rv.gap_pct:+.1f}%)"
        )
        if rv.implied_pos_scale is not None:
            print(
                f"  시장 내재 PoS 배수: {rv.implied_pos_scale:.3f}x (전체 PoS × {rv.implied_pos_scale:.3f})"
            )
            for d in rv.implied_pos_per_drug:
                print(
                    f"    {d.name:<30s} {d.base_value:>5.0%} → {d.implied_value:>5.0%}"
                )
        if rv.implied_peak_scale is not None:
            print(f"  시장 내재 Peak Sales 배수: {rv.implied_peak_scale:.3f}x")
            for d in rv.implied_peak_per_drug:
                print(
                    f"    {d.name:<30s} {int(d.base_value):>12,} → {int(d.implied_value):>12,}"
                )
        if rv.implied_discount_rate is not None:
            dr_current = result.rnpv.discount_rate if result.rnpv else 0
            print(
                f"  시장 내재 할인율: {rv.implied_discount_rate:.2f}% (현재 {dr_current:.2f}%)"
            )
        # Per-drug independent PoS (solo analysis)
        solo_drugs = [d for d in rv.implied_pos_solo if not d.skipped]
        if solo_drugs:
            direction = "시장 낙관" if rv.gap_pct < 0 else "시장 비관"
            print(f"  약물별 독립 PoS ({direction}):")
            for d in solo_drugs:
                if d.solvable and d.implied_pos is not None:
                    print(
                        f"    {d.name:<35s} {d.base_pos:>5.0%} → {d.implied_pos:>5.0%}  (최대 기여 {d.max_ev_contribution:>8,}{unit})"
                    )
                else:
                    print(
                        f"    {d.name:<35s} {d.base_pos:>5.0%} → 해소불가   (최대 기여 {d.max_ev_contribution:>8,}{unit})"
                    )
            print(
                "  ※ 각 약물은 다른 약물을 현재 가정으로 고정한 독립 분석. 결과는 합산 불가."
            )

    # Tornado (per-drug peak sales sensitivity)
    if result.rnpv_tornado:
        print("\n[Tornado 분석] Peak Sales ±20% → 주당가치 영향")
        print(f"  {'약물':<30s} {'Low':>8s} {'Base':>8s} {'High':>8s} {'Swing':>8s}")
        print(f"  {'-' * 30} {'-' * 8} {'-' * 8} {'-' * 8} {'-' * 8}")
        for t in result.rnpv_tornado:
            swing = t.high_value - t.low_value
            print(
                f"  {t.name:<30s} {t.low_value:>8,} {t.base_value:>8,} {t.high_value:>8,} {swing:>+8,}"
            )

    # DCF
    if result.dcf:
        dcf = result.dcf
        dcf_note = " (제조 부문 기준)" if is_mixed else ""
        print(f"\n[DCF{dcf_note}]")
        print(f"  DCF EV: {dcf.ev_dcf:>12,}{unit}")
        if result.sotp:
            sotp_ev = sum(s.ev for s in result.sotp.values())
            if sotp_ev > 0:
                diff_pct = (dcf.ev_dcf - sotp_ev) / sotp_ev * 100
                print(f"  SOTP EV: {sotp_ev:>12,}{unit}")
                print(f"  DCF vs SOTP: {diff_pct:>+.1f}%")

    # Market price comparison
    if result.market_comparison:
        mc = result.market_comparison
        print("\n[시장가격 비교]")
        print(f"  내재가치: {mc.intrinsic_value:,}{currency_sym}")
        print(f"  현재 주가: {mc.market_price:,.0f}{currency_sym}")
        print(f"  괴리율: {mc.gap_ratio:+.1%}")
        if mc.flag:
            print(f"  ⚠ {mc.flag}")

    # Reverse-DCF gap diagnostic
    if result.gap_diagnostic:
        from engine.gap_diagnostics import format_gap_diagnostic

        print(format_gap_diagnostic(result.gap_diagnostic, is_listed=True))
        if result.gap_diagnostic.primary_reason:
            print(f"  Primary reason: {result.gap_diagnostic.primary_reason}")
        if result.gap_diagnostic.secondary_reasons:
            print(
                f"  Secondary reasons: {', '.join(result.gap_diagnostic.secondary_reasons)}"
            )

    # Monte Carlo
    if result.monte_carlo:
        mc = result.monte_carlo
        print(f"\n[Monte Carlo 시뮬레이션 ({mc.n_sims:,}회)]")
        print(
            f"  Mean: {mc.mean:>10,}{currency_sym}  |  Median: {mc.median:>10,}{currency_sym}  |  Std: {mc.std:>8,}{currency_sym}"
        )
        print(
            f"  5th: {mc.p5:>11,}{currency_sym}  |  25th: {mc.p25:>12,}{currency_sym}"
        )
        print(
            f"  75th: {mc.p75:>10,}{currency_sym}  |  95th: {mc.p95:>12,}{currency_sym}"
        )
        if mc.scenario_mc:
            print("  시나리오별 MC:")
            for sc_code, sc_mc in mc.scenario_mc.items():
                sc_name = vi.scenarios.get(sc_code, None)
                label = sc_name.name if sc_name else sc_code
                print(
                    f"    {label:<16} P5={sc_mc.p5:>8,}{currency_sym}  Mean={sc_mc.mean:>8,}{currency_sym}  P95={sc_mc.p95:>8,}{currency_sym}"
                )

    # Peer
    if result.peer_stats:
        print("\n[Peer 멀티플 통계]")
        _pw = max((len(ps.segment_name) for ps in result.peer_stats), default=12)
        _pw = max(_pw, 8)
        print(
            f"{'부문':<{_pw}} {'방법':>11} {'N':>3} {'Median':>8} "
            f"{'Mean':>8} {'Q1':>8} {'Q3':>8} {'적용':>8}"
        )
        print("-" * (_pw + 60))
        for ps in result.peer_stats:
            if ps.count == 0 or ps.multiple_median is None:
                print(
                    f"{ps.segment_name:<{_pw}} {ps.multiple_label:>11} "
                    f"{ps.count:>3}  비교 생략 — {ps.warning}"
                )
                continue
            print(
                f"{ps.segment_name:<{_pw}} {ps.multiple_label:>11} {ps.count:>3} "
                f"{ps.multiple_median:>7.3f}x {ps.multiple_mean:>7.3f}x "
                f"{ps.multiple_q1:>7.3f}x {ps.multiple_q3:>7.3f}x "
                f"{ps.applied_multiple:>7.3f}x"
            )

    # Multiple cross-validation
    if result.cross_validations:
        # Trading Multiple detection: Trading if within +/-5% of market price
        market_ps = (
            result.market_comparison.market_price if result.market_comparison else 0
        )
        print("\n[멀티플 교차검증]")
        print(
            f"{'방법론':<28} {'지표값':>12} {'배수':>8} {'EV':>14} {'Equity':>14} {'주당가치':>10}"
        )
        print("-" * 90)
        for cv in result.cross_validations:
            tag = ""
            if (
                market_ps > 0
                and cv.per_share > 0
                and cv.method not in ("SOTP (EV/EBITDA)", "SOTP (Mixed)", "DCF (FCFF)")
            ):
                gap = abs(cv.per_share - market_ps) / market_ps
                tag = " [T]" if gap < 0.05 else " [P]"
            label = f"{cv.method}{tag}"
            print(
                f"{label:<28} {cv.metric_value:>12,.0f} {cv.multiple:>7.1f}x "
                f"{cv.enterprise_value:>13,} {cv.equity_value:>13,} {cv.per_share:>9,}"
            )
        # Legend
        has_trading = market_ps > 0 and any(
            cv.method not in ("SOTP (EV/EBITDA)", "SOTP (Mixed)", "DCF (FCFF)")
            for cv in result.cross_validations
        )
        if has_trading:
            print("  [T] Trading Multiple (시장가 역산)  [P] Peer/독립 추정")

    # Relative valuation diagnostics (P/E, P/B, PEG/PEGY, justified multiples)
    rv = result.relative_valuation
    if rv and rv.ratios:
        print("\n[상대가치 진단 배수]")
        print(f"{'지표':<12} {'값':>10}  비고")
        print("-" * 60)
        for m in rv.ratios:
            if m.value is None:
                shown = "N/A"
            elif m.name in ("Div Yield", "PEG", "PEGY"):
                unit = "%" if m.name == "Div Yield" else ""
                shown = f"{m.value:.2f}{unit}"
            else:
                shown = f"{m.value:.2f}x"
            flag = (
                ""
                if m.status == "ok"
                else f"  ⚠ {m.note}"
                if m.status == "caution"
                else f"  – {m.note}"
            )
            print(f"{m.name:<12} {shown:>10}{flag}")
        if rv.verdicts:
            print("\n  [정당배수 대비 판정]")
            for v in rv.verdicts:
                a = f"{v.actual:.2f}x" if v.actual is not None else "N/A"
                j = f"{v.justified:.2f}x" if v.justified is not None else "N/A"
                gap = f"{v.gap_pct:+.1f}%" if v.gap_pct is not None else "—"
                print(
                    f"  {v.name:<5} 실제 {a:>8} vs 정당 {j:>8} ({gap})  → {v.verdict}"
                )
        # Peer median comparison (aggregate EV/EBITDA across peer segments)
        _peer_meds = [
            ps.ev_ebitda_median
            for ps in result.peer_stats
            if getattr(ps, "ev_ebitda_median", 0)
        ]
        _evb = next(
            (m for m in rv.ratios if m.name == "EV/EBITDA" and m.value is not None),
            None,
        )
        if _peer_meds and _evb is not None:
            from statistics import median as _median

            _pm = _median(_peer_meds)
            if _evb.value > _pm * 1.1:
                _rel = "피어 대비 프리미엄"
            elif _evb.value < _pm * 0.9:
                _rel = "피어 대비 할인"
            else:
                _rel = "피어 수준"
            # NOTE: 아래 print는 Codex write 시 mid-string truncation → 가시 의도대로 최소 복원 (2026-07-17). 추가 후속 라인이 있었다면 Codex 원자적 재기록 필요.
            print(
                f"\n  [피어 median 대비] EV/EBITDA 자사 {_evb.value:.1f}x vs median {_pm:.1f}x → {_rel}"
            )
