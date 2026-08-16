"""SNDK 회계 FY2026 Q4 (달력 2026 Q2) 사후 채점.

동결 예측은 `reports/sndk_fy2026q4_forecast_FROZEN.md` (commit 0168c65, 동결 2026-08-05
01:13 KST)에 고정돼 있고, 이 스크립트는 **대조만** 한다. 예측치는 커밋된
`profiles/sndk.generic.yaml`에서 로드한다(하드코드 드리프트 방지).

    실행: python scripts/score_sndk_fy2026q4.py
          python scripts/score_sndk_fy2026q4.py --selftest   # 산식 자기검증(잔차 0)

채점 항목 (COMMON §3 + DELTA §R6 + FROZEN §9):
  1. 매출·EPS 포인트 오차 + bias(부호), GAAP/비GAAP 각각 (R5: 같은 기준끼리만)
  2. 밴드 커버리지 + 밴드 내 위치 + 밴드폭÷base 캘리브레이션
  3. 컨센 서프라이즈 HIT / MISS / NO_SURPRISE + 가이던스 대비 위치
  4. 4-lever generic 귀인 (매출 / 영업이익률 / OP→NI 전환 / 주식수), **잔차 0**
     + OP→NI 전환 레버를 below-OP와 세율로 2차 분해
  5. 세그먼트(Datacenter/Edge/Consumer) 오차
  6. 1-step 스킬: 나이브 RW 대비 상대오차비(단일 분기 MASE 대용)
  7. 차기(FY27 Q1) 가이던스 예측 적중
  8. 사전등록 스윙팩터 SF1~SF7 발화 판정

주의: SNDK는 참여증권 배분이 없다 — 보고 EPS = NI ÷ 희석주식수가 정확히 성립한다
(6,903 ÷ 157 = 43.968 ≈ 43.97). TXN형 IAC 보정이 필요 없다.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from engine.generic_forecast import run_generic_forecast  # noqa: E402
from engine.scoring_basis import compare_bases, format_gap_of_gap  # noqa: E402
from generic_cli import load_generic_profile  # noqa: E402

SCALE = 1_000_000.0
PROFILE = REPO / "profiles" / "sndk.generic.yaml"
OUT = REPO / "reports" / "sndk_fy2026q4_SCORED.md"

# ──────────────────────────────────────────────────────────────────────────
# ACTUALS — 8-K accession 0001628280-26-053346 (filed 2026-08-05), EX-99.1
#   https://www.sec.gov/Archives/edgar/data/2023554/000162828026053346/sndkq4-26ex991xpressrelease.htm
#   회계 FY2026 Q4 = 13주, 종료 2026-07-03. actual_source_stage = press_release_8k
#   (FY2026 10-K는 2026-08-07 기준 미제출.)
# ──────────────────────────────────────────────────────────────────────────
ACTUAL: dict[str, float] = {
    "revenue": 8965.0,
    "cost_of_revenue": 1383.0,
    "gross_profit": 7582.0,
    "opex": 545.0,
    "operating_income": 7037.0,
    "below_op_total": 812.0,          # incl. gain on equity securities +804
    "gain_on_equity_securities": 804.0,
    "interest_income": 30.0,
    "interest_expense": -2.0,
    "other_income_expense_net": -20.0,
    "pretax": 7849.0,
    "tax": 946.0,
    "net_income": 6903.0,
    "eps_diluted_gaap": 43.97,
    "diluted_shares": 157_000_000.0,
    # 비GAAP
    "non_gaap_net_income": 6162.0,
    "eps_diluted_non_gaap": 39.25,
    "non_gaap_operating_income": 7104.0,
    "non_gaap_opex": 484.0,
    # 세그먼트
    "seg_datacenter": 2977.0,
    "seg_edge": 5432.0,
    "seg_consumer": 556.0,
    # 차기 가이던스 (FY2027 Q1)
    "g_rev_low": 10300.0,
    "g_rev_high": 10800.0,
    "g_eps_ng_low": 44.0,
    "g_eps_ng_high": 46.0,
    "g_gm_ng_low": 0.830,
    "g_gm_ng_high": 0.850,
    "g_tax_rate": 0.150,
    "g_shares": 155_000_000.0,
}
ACTUAL_SOURCE_STAGE = "press_release_8k (accession 0001628280-26-053346, EX-99.1)"

# 동결 시점에 기록한 애널리스트 레이어 상수 (FROZEN §(d) 기재값, provenance 포함)
CONSENSUS_REV = 8420.0          # TipRanks 17인, as-of 2026-07-31 (Zacks 2026-08-03 $8,300)
CONSENSUS_EPS_NG = 34.67        # FactSet ~2026-07-30 (비GAAP)
OUR_CALL_VS_CONSENSUS = "above"
GUIDE_REV_LOW, GUIDE_REV_MID, GUIDE_REV_HIGH = 7750.0, 8000.0, 8250.0
GUIDE_EPS_NG_HIGH = 33.00
NG_BRIDGE_PER_SHARE = 0.32      # FROZEN §(a-2) base 브릿지 (GAAP → 비GAAP)
# FROZEN §(c) 예측
PRED_G_REV_LOW, PRED_G_REV_HIGH = 10500.0, 11500.0
PRED_G_EPS_LOW, PRED_G_EPS_HIGH = 40.0, 45.0
# FROZEN §(b) 세그먼트 base 예측
PRED_SEG = {"Datacenter": 2714.0, "Edge": 5421.0, "Consumer": 910.0}
# 나이브 RW 기준 = 직전 분기 실적 (FY26Q3)
RW_REV, RW_EPS_GAAP, RW_EPS_NG = 5950.0, 23.03, 23.41


def _pct(x: float) -> str:
    return f"{x * 100:+.2f}%"


def load_frozen() -> dict:
    profile = load_generic_profile(PROFILE)
    forecast = run_generic_forecast(profile)

    def factors(q):
        return {
            "rev": q.revenue_total,
            "op": q.operating_profit,
            "ni": q.net_profit,
            "eps": q.eps_diluted,
            "opm": q.operating_profit / q.revenue_total,
            "conv": q.net_profit / q.operating_profit,
        }

    out = {
        tag: factors(forecast.scenarios_quarterly[tag][0]) for tag in ("bear", "base", "bull")
    }
    out["weighted"] = factors(forecast.weighted_quarterly[0])
    out["shares"] = profile.weighted_avg_diluted
    out["label"] = forecast.weighted_quarterly[0].quarter_label
    # 확률가중 below-OP (= net_interest_pct x revenue 를 시나리오 확률로 가중)
    out["weighted_below_op"] = sum(
        getattr(profile, tag).probability
        * getattr(profile, tag).net_interest(1)[0]
        * forecast.scenarios_quarterly[tag][0].revenue_total
        for tag in ("bear", "base", "bull")
    )
    for tag in ("bear", "base", "bull"):
        out[tag]["below_op"] = (
            getattr(profile, tag).net_interest(1)[0] * forecast.scenarios_quarterly[tag][0].revenue_total
        )
    return out


def _eps_from(rev: float, opm: float, conv: float, shares: float) -> float:
    return rev * opm * conv * SCALE / shares


def section_point(a: dict, f: dict, lines: list[str]) -> None:
    lines += ["## 1. 포인트 오차 (R5: 같은 기준끼리만 비교)", ""]
    lines += ["| 지표 | 예측 | 실제 | 오차 | %오차 |", "|---|---:|---:|---:|---:|"]
    for tag in ("base", "weighted"):
        rp = f[tag]["rev"]
        lines.append(
            f"| 매출 ({tag}) | {rp:,.0f} | {a['revenue']:,.0f} | {rp - a['revenue']:+,.0f} | "
            f"{_pct((rp - a['revenue']) / a['revenue'])} |"
        )
    for tag in ("base", "weighted"):
        ep = f[tag]["eps"]
        lines.append(
            f"| GAAP 희석 EPS ({tag}) | {ep:.2f} | {a['eps_diluted_gaap']:.2f} | "
            f"{ep - a['eps_diluted_gaap']:+.2f} | {_pct((ep - a['eps_diluted_gaap']) / a['eps_diluted_gaap'])} |"
        )
    for tag in ("base", "weighted"):
        ng = f[tag]["eps"] + NG_BRIDGE_PER_SHARE
        lines.append(
            f"| **비GAAP 희석 EPS ({tag})** | **{ng:.2f}** | **{a['eps_diluted_non_gaap']:.2f}** | "
            f"{ng - a['eps_diluted_non_gaap']:+.2f} | **{_pct((ng - a['eps_diluted_non_gaap']) / a['eps_diluted_non_gaap'])}** |"
        )
    gm_pred, gm_act = 0.840, a["gross_profit"] / a["revenue"]
    opm_act = a["operating_income"] / a["revenue"]
    lines += [
        "",
        f"- GAAP 매출총이익률: 예측 {gm_pred*100:.1f}% vs 실제 **{gm_act*100:.2f}%** ({(gm_pred-gm_act)*100:+.2f}%p)",
        f"- GAAP 영업이익률: 예측 {f['base']['opm']*100:.1f}% vs 실제 **{opm_act*100:.2f}%** ({(f['base']['opm']-opm_act)*100:+.2f}%p)",
        f"- GAAP 영업이익: 예측 {f['base']['op']:,.0f} vs 실제 {a['operating_income']:,.0f} "
        f"(**{_pct((f['base']['op']-a['operating_income'])/a['operating_income'])}**)",
        f"- 영업비용: 예측 555 vs 실제 {a['opex']:,.0f} · 유효세율: 예측 13.5% vs 실제 "
        f"**{a['tax']/a['pretax']*100:.2f}%** · 희석주식수: 예측 158.0M vs 실제 {a['diluted_shares']/1e6:.0f}M",
        "",
    ]


def section_band(a: dict, f: dict, lines: list[str]) -> None:
    lines += ["## 2. 밴드 커버리지 + 캘리브레이션 (R6)", ""]
    lines += ["| 지표 | bear | bull | 실제 | 커버 | 밴드 내 위치 | 밴드폭÷base |", "|---|---:|---:|---:|:--:|---:|---:|"]
    rows = [
        ("매출", f["bear"]["rev"], f["bull"]["rev"], a["revenue"], f["base"]["rev"]),
        ("GAAP EPS", f["bear"]["eps"], f["bull"]["eps"], a["eps_diluted_gaap"], f["base"]["eps"]),
        (
            "비GAAP EPS",
            f["bear"]["eps"] + NG_BRIDGE_PER_SHARE,
            f["bull"]["eps"] + NG_BRIDGE_PER_SHARE,
            a["eps_diluted_non_gaap"],
            f["base"]["eps"] + NG_BRIDGE_PER_SHARE,
        ),
    ]
    for name, lo, hi, act, base in rows:
        covered = lo <= act <= hi
        pos = (act - lo) / (hi - lo)
        lines.append(
            f"| {name} | {lo:,.2f} | {hi:,.2f} | {act:,.2f} | {'✅' if covered else '❌'} | "
            f"{pos*100:.1f}% | {(hi-lo)/base*100:.1f}% |"
        )
    lines += [
        "",
        "- below-OP 밴드는 **별도 판정**: 예측 bear −1.0% ~ bull +0.6% of revenue "
        f"(−{0.010*a['revenue']:,.0f} ~ +{0.006*a['revenue']:,.0f}) vs 실제 **+{a['below_op_total']:,.0f}** "
        f"(매출의 {a['below_op_total']/a['revenue']*100:+.2f}%) → **밴드 밖 (실패)**",
        "",
    ]


def section_consensus(a: dict, lines: list[str]) -> None:
    lines += ["## 3. 컨센 서프라이즈 + 가이던스 대비", ""]
    rev_s = a["revenue"] - CONSENSUS_REV
    eps_s = a["eps_diluted_non_gaap"] - CONSENSUS_EPS_NG
    direction = "above" if eps_s > 0 else ("below" if eps_s < 0 else "inline")
    verdict = "HIT" if direction == OUR_CALL_VS_CONSENSUS else ("NO_SURPRISE" if direction == "inline" else "MISS")
    lines += [
        f"- 컨센(비GAAP 기준): 매출 {CONSENSUS_REV:,.0f} / EPS {CONSENSUS_EPS_NG:.2f}",
        f"- 실제: 매출 {a['revenue']:,.0f} ({rev_s:+,.0f}, {_pct(rev_s/CONSENSUS_REV)}) · "
        f"비GAAP EPS {a['eps_diluted_non_gaap']:.2f} ({eps_s:+.2f}, {_pct(eps_s/CONSENSUS_EPS_NG)})",
        f"- 우리 콜 **{OUR_CALL_VS_CONSENSUS}** vs 실제 **{direction}** → **{verdict}**",
        "",
        f"- 가이던스 대비: 실제 매출이 중간값 {GUIDE_REV_MID:,.0f} 대비 "
        f"{_pct((a['revenue']-GUIDE_REV_MID)/GUIDE_REV_MID)}, 상단 {GUIDE_REV_HIGH:,.0f} 대비 "
        f"{_pct((a['revenue']-GUIDE_REV_HIGH)/GUIDE_REV_HIGH)} (우리 예측: +13.1% / +9.6%)",
        f"- 비GAAP EPS는 가이던스 상단 {GUIDE_EPS_NG_HIGH:.2f} 대비 "
        f"{_pct((a['eps_diluted_non_gaap']-GUIDE_EPS_NG_HIGH)/GUIDE_EPS_NG_HIGH)} (우리 예측 +17.8%)",
        "",
    ]


def section_four_lever(a: dict, f: dict, lines: list[str]) -> None:
    p = f["weighted"]
    Rp, Mp, Cp, Sp = p["rev"], p["opm"], p["conv"], f["shares"]
    Ra = a["revenue"]
    Ma = a["operating_income"] / a["revenue"]
    Ca = a["net_income"] / a["operating_income"]
    Sa = a["diluted_shares"]
    e0 = _eps_from(Rp, Mp, Cp, Sp)
    e1 = _eps_from(Ra, Mp, Cp, Sp)
    e2 = _eps_from(Ra, Ma, Cp, Sp)
    e3 = _eps_from(Ra, Ma, Ca, Sp)
    e4 = _eps_from(Ra, Ma, Ca, Sa)
    resid = e4 - a["eps_diluted_gaap"]
    lines += ["## 4. 4-lever generic 귀인 (GAAP EPS · 기여 합 = 오차)", ""]
    lines += ["| 레버 | 기여(EPS) | 설명 |", "|---|---:|---|"]
    lines.append(f"| 매출 | {e1-e0:+.3f} | 실제 {Ra:,.0f} vs 예측 {Rp:,.0f} |")
    lines.append(f"| 영업이익률 | {e2-e1:+.3f} | 실제 {Ma*100:.2f}% vs 예측 {Mp*100:.2f}% |")
    lines.append(f"| **OP→NI 전환** | **{e3-e2:+.3f}** | 실제 {Ca*100:.2f}% vs 예측 {Cp*100:.2f}% (below-OP + 세율) |")
    lines.append(f"| 주식수 | {e4-e3:+.3f} | 실제 {Sa/1e6:.0f}M vs 예측 {Sp/1e6:.0f}M |")
    lines.append(
        f"| **합계** | **{e4-e0:+.3f}** | 예측 {e0:.3f} → 재구성 {e4:.3f} = 보고 "
        f"{a['eps_diluted_gaap']:.2f} (**잔차 {resid:+.4f}**) |"
    )
    # OP→NI 전환 레버 2차 분해: below-OP vs 세율.
    # 전환계수 C = (1 + below_op/OP) x (1 - t) 로 분해하면 두 하위 기여가 정확히 C 레버 합이 된다.
    b_p = f["weighted_below_op"] / p["op"]          # 예측(확률가중) below-OP 비율
    t_p = 1.0 - Cp / (1.0 + b_p)                    # 예측 함의 유효세율
    b_a = a["below_op_total"] / a["operating_income"]
    t_a = a["tax"] / a["pretax"]
    e2b = _eps_from(Ra, Ma, (1.0 + b_a) * (1.0 - t_p), Sp)   # below-OP만 실제로
    d_belowop, d_tax = e2b - e2, e3 - e2b
    lines += [
        "",
        f"**OP→NI 전환 레버 2차 분해** (전환계수 C = (1 + below-OP/OP) × (1 − 유효세율); "
        f"예측 below-OP 비율 {b_p*100:+.2f}% · 예측 함의 세율 {t_p*100:.2f}%):",
        "",
        "| 하위 레버 | 기여(EPS) | 설명 |",
        "|---|---:|---|",
        f"| **below-OP** | **{d_belowop:+.3f}** | 실제 +{a['below_op_total']:,.0f} (OP의 "
        f"{b_a*100:+.2f}%, 지분증권 평가이익 +{a['gain_on_equity_securities']:,.0f} 포함) vs 예측 "
        f"{f['weighted_below_op']:+,.0f} |",
        f"| 유효세율 | {d_tax:+.3f} | 실제 {t_a*100:.2f}% vs 예측 함의 {t_p*100:.2f}% |",
        f"| 합 | {d_belowop+d_tax:+.3f} | = OP→NI 전환 레버 {e3-e2:+.3f} (**잔차 {d_belowop+d_tax-(e3-e2):+.6f}**) |",
        "",
        f"- **최대 오차원: OP→NI 전환 ({e3-e2:+.3f}, 총오차의 {abs(e3-e2)/abs(e4-e0)*100:.1f}%)** — "
        "전액이 사전등록 SF3(below-OP) 블록이다.",
        "",
        "**비GAAP 기준 재채점(R5)**: 비GAAP은 지분증권 평가이익을 제외하므로 위 오차원이 사라진다. "
        f"비GAAP EPS 예측 {f['base']['eps']+NG_BRIDGE_PER_SHARE:.2f} vs 실제 {a['eps_diluted_non_gaap']:.2f} "
        f"→ **{_pct((f['base']['eps']+NG_BRIDGE_PER_SHARE-a['eps_diluted_non_gaap'])/a['eps_diluted_non_gaap'])}**.",
        "",
    ]
    return None


def section_segments(a: dict, lines: list[str]) -> None:
    lines += ["## 5. 세그먼트 오차 (FROZEN §(b))", ""]
    lines += ["| 세그먼트 | 예측 | 실제 | 오차 | %오차 | 예측 QoQ | 실제 QoQ |", "|---|---:|---:|---:|---:|---:|---:|"]
    prev = {"Datacenter": 1467.0, "Edge": 3663.0, "Consumer": 820.0}
    act = {"Datacenter": a["seg_datacenter"], "Edge": a["seg_edge"], "Consumer": a["seg_consumer"]}
    for k in ("Datacenter", "Edge", "Consumer"):
        pv, av = PRED_SEG[k], act[k]
        lines.append(
            f"| {k} | {pv:,.0f} | {av:,.0f} | {pv-av:+,.0f} | {_pct((pv-av)/av)} | "
            f"{_pct(pv/prev[k]-1)} | {_pct(av/prev[k]-1)} |"
        )
    lines += ["", f"- 합계 검산: 예측 {sum(PRED_SEG.values()):,.0f} / 실제 {sum(act.values()):,.0f}", ""]


def section_skill(a: dict, f: dict, lines: list[str]) -> None:
    lines += ["## 6. 1-step 스킬 — 나이브 RW 대비 (단일 분기)", ""]
    lines += ["| 지표 | 모델 오차 | RW 오차 | 상대비(<1이면 RW 우위) |", "|---|---:|---:|---:|"]
    rows = [
        ("매출", abs(f["base"]["rev"] - a["revenue"]) / a["revenue"], abs(RW_REV - a["revenue"]) / a["revenue"]),
        (
            "GAAP EPS",
            abs(f["base"]["eps"] - a["eps_diluted_gaap"]) / abs(a["eps_diluted_gaap"]),
            abs(RW_EPS_GAAP - a["eps_diluted_gaap"]) / abs(a["eps_diluted_gaap"]),
        ),
        (
            "비GAAP EPS",
            abs(f["base"]["eps"] + NG_BRIDGE_PER_SHARE - a["eps_diluted_non_gaap"]) / abs(a["eps_diluted_non_gaap"]),
            abs(RW_EPS_NG - a["eps_diluted_non_gaap"]) / abs(a["eps_diluted_non_gaap"]),
        ),
    ]
    for name, me, rw in rows:
        lines.append(f"| {name} | {me*100:.2f}% | {rw*100:.2f}% | **{me/rw:.3f}** |")
    lines += [
        "",
        "- 동결 시점 백테스트는 post-break MASE 매출 0.859 / EPS 0.817, Theil ≈0.95~0.99로 "
        "**RW를 사실상 못 이긴다**고 기록했다. 이번 분기 실측은 그 예상을 크게 상회한다.",
        "",
    ]


def section_guidance(a: dict, lines: list[str]) -> None:
    lines += ["## 7. 차기(FY2027 Q1) 가이던스 예측 적중", ""]
    lines += ["| 항목 | 우리 예측 | 실제 가이던스 | 판정 |", "|---|---|---|---|"]
    mid_p, mid_a = (PRED_G_REV_LOW + PRED_G_REV_HIGH) / 2, (a["g_rev_low"] + a["g_rev_high"]) / 2
    overlap_rev = not (PRED_G_REV_HIGH < a["g_rev_low"] or a["g_rev_high"] < PRED_G_REV_LOW)
    mid_pe, mid_ae = (PRED_G_EPS_LOW + PRED_G_EPS_HIGH) / 2, (a["g_eps_ng_low"] + a["g_eps_ng_high"]) / 2
    overlap_eps = not (PRED_G_EPS_HIGH < a["g_eps_ng_low"] or a["g_eps_ng_high"] < PRED_G_EPS_LOW)
    lines.append(
        f"| 매출 레인지 | ${PRED_G_REV_LOW/1000:.1f}B–${PRED_G_REV_HIGH/1000:.1f}B (mid {mid_p/1000:.2f}) | "
        f"${a['g_rev_low']/1000:.1f}B–${a['g_rev_high']/1000:.1f}B (mid {mid_a/1000:.2f}) | "
        f"{'구간 중첩 ✅' if overlap_rev else '중첩 없음 ❌'}, mid 오차 {_pct((mid_p-mid_a)/mid_a)} |"
    )
    lines.append(
        f"| 비GAAP EPS 레인지 | ${PRED_G_EPS_LOW:.0f}–${PRED_G_EPS_HIGH:.0f} (mid {mid_pe:.1f}) | "
        f"${a['g_eps_ng_low']:.0f}–${a['g_eps_ng_high']:.0f} (mid {mid_ae:.1f}) | "
        f"{'구간 중첩 ✅' if overlap_eps else '중첩 없음 ❌'}, mid 오차 {_pct((mid_pe-mid_ae)/mid_ae)} |"
    )
    lines.append(
        f"| 비GAAP GM | 84%–87% | {a['g_gm_ng_low']*100:.1f}%–{a['g_gm_ng_high']*100:.1f}% | "
        "구간 하단만 중첩 (우리가 약간 높음) |"
    )
    lines.append("| 방향 판정 | 대폭 상향(RAISE), 확신도 상 | 전분기 대비 mid +17.7% | **적중 ✅** |")
    lines.append("| FY2027 연간 가이던스 | 8/5 콜에서 안 나온다(확신도 중) | 제시 안 됨, 8/13 Investor Day로 이연 | **적중 ✅** |")
    lines.append("")



SWINGS = [
    ("SF1", "op_margin 앵커 방향 반전(상향 적용)", "적중",
     "예측 GAAP 영업이익률 77.9% vs 실제 78.49% (−0.59%p). 영업이익 예측 7,045 vs 실제 7,037로 오차 +0.12%. "
     "11분기 중앙값 앵커 9.0%를 썼다면 영업이익을 ~88% 과소추정했다 — R1의 상향 적용이 결정적이었다."),
    ("SF2", "GM이 EPS를 지배 / 가이던스 대비 상회폭 압축", "적중",
     "예측 GAAP GM 84.0% vs 실제 84.57% (−0.57%p). 가이던스(78.9~80.9%) 대비 실제 상회폭은 +4.7%p로, "
     "우리가 가정한 '압축'(FQ2 +9.1%p·FQ3 +12.5%p → +3~4%p)이 맞았다. 매출원가는 1,383(예측 1,447 대비 −4.4%)."),
    ("SF3", "below-OP (Flash Ventures 지분법)", "발화 — 밴드 실패",
     "예측 밴드 −$90M ~ +$54M vs 실제 **+$812M**. 원인은 우리가 지목한 Flash Ventures 지분법이 아니라 "
     "**직전 분기까지 존재하지 않던 신설 라인 `Gain (loss) on equity securities, net` +$804M**이었다. "
     "GAAP EPS 오차의 90.2%가 여기서 나왔다. 비GAAP은 이 항목을 제외하므로 영향 0."),
    ("SF4", "분사 잔여 일회성 + 유효세율", "부분 적중",
     "실제 유효세율 12.05%로 시나리오 밴드(11.5~17.0%) 안, base 13.5% 대비 −1.45%p (EPS +$0.79 기여). "
     "일회성 영업비용은 이번 분기 0(부채상환손실·분사비용·구조조정 전부 —)이라 FQ3형 서프라이즈는 없었다."),
    ("SF5", "주식수", "적중",
     "예측 158.0M vs 실제 157M (−0.63%, EPS +$0.28 기여). $6B 자사주 중 **$4,524M을 실제로 집행**했으나 "
     "희석주식수는 157M로 유지됐다(기본주식수만 148→147). 우리가 지적한 '전환·RSU 희석이 자사주 효과를 상쇄'가 실현."),
    ("SF6", "차기 가이던스가 진짜 스톡무버", "적중",
     "더블 비트(매출 +6.5%·비GAAP EPS +13.2% vs 컨센)에도 주가는 8/6 −5.3%, 8/7 −3.0%로 이틀 누적 약 −9.6%. "
     "원인은 FY27Q1 가이던스 중간값 $10.55B가 스트리트 ~$10.82B를 하회한 것. FY2027 연간 가이던스는 "
     "제시되지 않고 8/13 Investor Day로 이연 — 우리가 확신도 '중'으로 예측한 그대로다."),
    ("SF7", "7월 교정의 반대방향 과잉적용", "미발화 → 키옥시아 리드스루 검증",
     "사전등록 판정 기준은 '매출 오차 −8% 이상(과대)이면 발화, ±3% 이내면 리드스루가 재사용 자산으로 승격'이었다. "
     "실제 매출 오차는 **+0.88%** — 상방 극단으로 갔음에도 과잉적용이 아니었다. "
     "동일 팹 파트너(키옥시아)의 선행 프린트를 레벨 앵커로 쓰는 방법이 검증됐다."),
]


def section_swings(lines: list[str]) -> None:
    lines += ["## 8. 사전등록 스윙팩터 SF1~SF7 발화 판정", ""]
    lines += ["| ID | 항목 | 판정 | 근거 |", "|---|---|---|---|"]
    for sid, name, verdict, why in SWINGS:
        lines.append(f"| {sid} | {name} | **{verdict}** | {why} |")
    lines.append("")

def build(a: dict, f: dict) -> str:
    basis_comparison = compare_bases(
        base={"revenue": f["base"]["rev"], "non_gaap_eps": f["base"]["eps"] + NG_BRIDGE_PER_SHARE},
        weighted={"revenue": f["weighted"]["rev"], "non_gaap_eps": f["weighted"]["eps"] + NG_BRIDGE_PER_SHARE},
        actual={"revenue": a["revenue"], "non_gaap_eps": a["eps_diluted_non_gaap"]},
        consensus={"revenue": CONSENSUS_REV, "non_gaap_eps": CONSENSUS_EPS_NG},
    )
    lines: list[str] = [
        "# SNDK 회계 FY2026 Q4 (달력 2026 Q2) — 사후 채점",
        "",
        "> **사후 귀인 — 예측 신호 아님.** 동결 예측은 `reports/sndk_fy2026q4_forecast_FROZEN.md`",
        "> (commit `0168c65`, 동결 2026-08-05 01:13 KST)에 고정돼 있으며 이 채점으로 수정되지 않는다.",
        "",
        f"- 실적 출처: **{ACTUAL_SOURCE_STAGE}**, 분기 종료 2026-07-03, 발표 2026-08-05 16:05 ET",
        f"- 예측 라벨: `{f['label']}` (회계 FY2026 Q4 = 달력 2026 Q2)",
        "",
    ]
    lines.extend(format_gap_of_gap(basis_comparison))
    lines.append("")
    section_point(a, f, lines)
    section_band(a, f, lines)
    section_consensus(a, lines)
    section_four_lever(a, f, lines)
    section_segments(a, lines)
    section_skill(a, f, lines)
    section_guidance(a, lines)
    section_swings(lines)
    return "\n".join(lines) + "\n"


def _selftest() -> int:
    """합성 실적으로 4-lever 재구성 잔차가 0인지 검증."""
    f = load_frozen()
    synthetic = dict(ACTUAL)
    synthetic.update({"revenue": 9000.0, "operating_income": 7000.0, "net_income": 6000.0,
                      "diluted_shares": 160_000_000.0})
    synthetic["eps_diluted_gaap"] = synthetic["net_income"] * SCALE / synthetic["diluted_shares"]
    Ra = synthetic["revenue"]
    Ma = synthetic["operating_income"] / Ra
    Ca = synthetic["net_income"] / synthetic["operating_income"]
    e4 = _eps_from(Ra, Ma, Ca, synthetic["diluted_shares"])
    resid = e4 - synthetic["eps_diluted_gaap"]
    print(f"selftest residual = {resid:.12f}")
    assert abs(resid) < 1e-9, resid
    # 실제 데이터 항등식
    a = ACTUAL
    assert a["revenue"] - a["cost_of_revenue"] == a["gross_profit"]
    assert a["gross_profit"] - a["opex"] == a["operating_income"]
    assert a["operating_income"] + a["below_op_total"] == a["pretax"]
    assert a["pretax"] - a["tax"] == a["net_income"]
    assert abs(a["net_income"] * SCALE / a["diluted_shares"] - a["eps_diluted_gaap"]) < 0.01
    assert a["seg_datacenter"] + a["seg_edge"] + a["seg_consumer"] == a["revenue"]
    print("actual identities OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in argv:
        return _selftest()
    f = load_frozen()
    text = build(ACTUAL, f)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n[written] {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
