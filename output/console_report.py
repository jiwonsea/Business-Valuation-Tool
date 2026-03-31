"""콘솔 리포트 출력."""

from schemas.models import ValuationInput, ValuationResult
from valuation_runner import _seg_names


def print_report(vi: ValuationInput, result: ValuationResult):
    """밸류에이션 결과를 콘솔에 출력."""
    by = vi.base_year
    seg_names = _seg_names(vi)
    unit = vi.company.currency_unit
    currency_sym = "원" if vi.company.market == "KR" else "$"

    print("=" * 60)
    print(f"{vi.company.name} 기업가치평가 모델 [{result.primary_method.upper()}]")
    print("=" * 60)

    # WACC
    w = result.wacc
    print(f"\n[WACC] βL={w.bl}, Ke={w.ke}%, Kd(세후)={w.kd_at}%, WACC={w.wacc}%")

    # Mixed SOTP 판단
    is_mixed = bool(vi.segment_net_debt) and any(
        info.get("method") in ("pbv", "pe") for info in vi.segments.values()
    )

    # D&A 배분 (SOTP인 경우만)
    if result.da_allocations and by in result.da_allocations:
        total_da = vi.consolidated[by]["dep"] + vi.consolidated[by]["amort"]
        da_note = " (금융 부문 제외)" if is_mixed else ""
        print(f"\n[D&A 배분{da_note}] 총 D&A = {total_da:,}{unit}")
        if is_mixed:
            print(f"{'부문':<18} {'Method':<10} {'자산비중':>8} {'D&A':>12} {'EBITDA':>14}")
        else:
            print(f"{'부문':<20} {'자산비중':>10} {'D&A':>12} {'EBITDA':>14}")
        print("-" * 65)
        alloc = result.da_allocations[by]
        for code in vi.segments:
            if code in alloc:
                a = alloc[code]
                if is_mixed:
                    method = vi.segments[code].get("method", "ev_ebitda")
                    m_lbl = {"ev_ebitda": "EV/EBITDA", "pbv": "P/BV", "pe": "P/E"}.get(method, method)
                    print(f"{seg_names.get(code, code):<18} {m_lbl:<10} {a.asset_share:>7.2f}% {a.da_allocated:>11,} {a.ebitda:>13,}")
                else:
                    print(f"{seg_names.get(code, code):<20} {a.asset_share:>9.2f}% {a.da_allocated:>11,} {a.ebitda:>13,}")

    # SOTP (있는 경우)
    if result.sotp:
        sotp_ev = sum(s.ev for s in result.sotp.values())
        if is_mixed:
            print(f"\n[SOTP (Mixed Method)]")
            for code in vi.segments:
                if code in result.sotp:
                    s = result.sotp[code]
                    method = getattr(s, "method", "ev_ebitda")
                    m_lbl = {"ev_ebitda": "EV/EBITDA", "pbv": "P/BV", "pe": "P/E"}.get(method, method)
                    eq_tag = " [Equity]" if getattr(s, "is_equity_based", False) else " [EV]"
                    print(f"  {seg_names.get(code, code):<18} {m_lbl:<10} {s.multiple:.1f}x → {s.ev:>14,}{unit}{eq_tag}")
            print(f"  {'합계':<30} {sotp_ev:>14,}{unit}")
            # Equity Bridge
            fin_debt = sum(
                vi.segment_net_debt.get(c, 0)
                for c, info in vi.segments.items()
                if info.get("method") in ("pbv", "pe")
            )
            eff_nd = vi.net_debt - fin_debt
            ev_part = sum(s.ev for s in result.sotp.values() if not getattr(s, "is_equity_based", False))
            eq_part = sum(s.ev for s in result.sotp.values() if getattr(s, "is_equity_based", False))
            print(f"\n[Equity Bridge]")
            print(f"  연결 순차입금:     {vi.net_debt:>14,}{unit}")
            print(f"  (-) 금융부문 부채: {fin_debt:>14,}{unit}")
            print(f"  유효 순차입금:     {eff_nd:>14,}{unit}")
            print(f"  제조 EV:           {ev_part:>14,}{unit}")
            print(f"  제조 Equity:       {ev_part - eff_nd:>14,}{unit}")
            print(f"  (+) 금융 Equity:   {eq_part:>14,}{unit}")
            print(f"  Total Equity:      {ev_part - eff_nd + eq_part:>14,}{unit}")
        else:
            print(f"\n[SOTP EV] {sotp_ev:>14,}{unit}")

    # 시나리오
    if result.scenarios:
        print(f"\n[시나리오 분석]")
        for code, sc in vi.scenarios.items():
            if code in result.scenarios:
                r = result.scenarios[code]
                print(f"  시나리오 {code} ({sc.name}, {sc.prob}%): "
                      f"Equity={r.equity_value:>12,}{unit}, "
                      f"주당(DLOM후)={r.post_dlom:>8,}{currency_sym}, "
                      f"가중기여={r.weighted:>6,}{currency_sym}")
        print(f"\n  >> 확률가중 주당 가치: {result.weighted_value:,}{currency_sym}")

    # DDM
    if result.ddm:
        d = result.ddm
        print(f"\n[DDM (Gordon Growth)]")
        if d.buyback_per_share > 0:
            print(f"  DPS: {d.dps:,.0f}{currency_sym}, 자사주매입: {d.buyback_per_share:,.0f}{currency_sym}")
            print(f"  Total Payout: {d.total_payout:,.0f}{currency_sym}, 성장률: {d.growth}%, Ke: {d.ke}%")
        else:
            print(f"  DPS: {d.dps:,.0f}{currency_sym}, 배당성장률: {d.growth}%, Ke: {d.ke}%")
        print(f"  주당 내재가치: {d.equity_per_share:,}{currency_sym}")

    # RIM
    if result.rim:
        r = result.rim
        print(f"\n[RIM (잔여이익모델)]")
        print(f"  장부가치(BV): {r.bv_current:,}{unit}, Ke: {r.ke}%")
        print(f"  PV(RI): {r.pv_ri_sum:,}{unit}, PV(TV): {r.pv_terminal:,}{unit}")
        print(f"  자기자본가치: {r.equity_value:,}{unit}")
        print(f"  주당 내재가치: {r.per_share:,}{currency_sym}")

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

    # 시장가격 비교
    if result.market_comparison:
        mc = result.market_comparison
        print(f"\n[시장가격 비교]")
        print(f"  내재가치: {mc.intrinsic_value:,}{currency_sym}")
        print(f"  현재 주가: {mc.market_price:,.0f}{currency_sym}")
        print(f"  괴리율: {mc.gap_ratio:+.1%}")
        if mc.flag:
            print(f"  ⚠ {mc.flag}")

    # Monte Carlo
    if result.monte_carlo:
        mc = result.monte_carlo
        print(f"\n[Monte Carlo 시뮬레이션 ({mc.n_sims:,}회)]")
        print(f"  Mean: {mc.mean:>10,}{currency_sym}  |  Median: {mc.median:>10,}{currency_sym}  |  Std: {mc.std:>8,}{currency_sym}")
        print(f"  5th: {mc.p5:>11,}{currency_sym}  |  25th: {mc.p25:>12,}{currency_sym}")
        print(f"  75th: {mc.p75:>10,}{currency_sym}  |  95th: {mc.p95:>12,}{currency_sym}")

    # Peer
    if result.peer_stats:
        print(f"\n[Peer 멀티플 통계 (EV/EBITDA)]")
        print(f"{'부문':<20} {'N':>3} {'Median':>8} {'Mean':>8} {'Q1':>8} {'Q3':>8} {'적용':>8}")
        print("-" * 68)
        for ps in result.peer_stats:
            print(f"{ps.segment_name:<20} {ps.count:>3} {ps.ev_ebitda_median:>7.1f}x "
                  f"{ps.ev_ebitda_mean:>7.1f}x {ps.ev_ebitda_q1:>7.1f}x "
                  f"{ps.ev_ebitda_q3:>7.1f}x {ps.applied_multiple:>7.1f}x")

    # 멀티플 교차검증
    if result.cross_validations:
        # Trading Multiple 판별: 시장가와 ±5% 이내이면 Trading
        market_ps = result.market_comparison.market_price if result.market_comparison else 0
        print(f"\n[멀티플 교차검증]")
        print(f"{'방법론':<28} {'지표값':>12} {'배수':>8} {'EV':>14} {'Equity':>14} {'주당가치':>10}")
        print("-" * 90)
        for cv in result.cross_validations:
            tag = ""
            if market_ps > 0 and cv.per_share > 0 and cv.method not in ("SOTP (EV/EBITDA)", "DCF (FCFF)"):
                gap = abs(cv.per_share - market_ps) / market_ps
                tag = " [T]" if gap < 0.05 else " [P]"
            label = f"{cv.method}{tag}"
            print(f"{label:<28} {cv.metric_value:>12,.0f} {cv.multiple:>7.1f}x "
                  f"{cv.enterprise_value:>13,} {cv.equity_value:>13,} {cv.per_share:>9,}")
        # 범례
        has_trading = market_ps > 0 and any(
            cv.method not in ("SOTP (EV/EBITDA)", "DCF (FCFF)") for cv in result.cross_validations
        )
        if has_trading:
            print(f"  [T] Trading Multiple (시장가 역산)  [P] Peer/독립 추정")

    print("\n" + "=" * 60)
    print(f"완료! [{result.primary_method.upper()}] 확률가중 주당 가치: {result.weighted_value:,}{currency_sym}")
    print("=" * 60)
