"""TXN 2026 Q2 사후 채점 스캐폴드 (프린트-전 조립, 프린트-후 즉시 실행).

동결 예측(reports/txn_q2_2026_forecast_FROZEN.md, commit e66bee5)은 이미 고정돼 있다.
이 스크립트는 **실적 발표 순간** IR 릴리스/8-K의 숫자 몇 개를 아래 ACTUALS에 채워 실행하면
전체 스코어카드를 즉시 산출한다(오염 없음 — 예측은 불변, 여기선 대조만).

    편집: 아래 ACTUALS의 None을 채운다 (USD_million / EPS는 USD/주).
    실행: python scripts/score_txn_q2_2026.py            # 스코어카드 → stdout + reports/txn_q2_2026_SCORED.md
          python scripts/score_txn_q2_2026.py --selftest # 합성 실적으로 산식 자기검증(4-lever 합=EPS오차)

채점 항목(COMMON §3 + FROZEN 사후계획):
  1. 매출·EPS 포인트 오차 + bias(부호)  vs 동결 가중/시나리오
  2. 컨센 대비 surprise 방향 적중 (우리는 '소폭 하회' 콜)
  3. 4-lever generic 귀인: 매출 / 영업이익률 / OP→NI 전환(세금+below-OP) / 주식수  (합 = EPS 오차)
  4. ★GM 오차 분해: 감가상각(고정) vs 가동률·믹스(변동)   ← TXN 특별지시
  5. 차기(Q3) 가이던스 레인지 적중 + 컨센 대비 미드(스톡무버)
  6. 사전등록 스윙팩터 발화 판정 (세금/below-OP, GM/가동률)

예측치(가중/시나리오/opm/conv)는 커밋된 profiles/txn.generic.yaml에서 **로드**한다(하드코드 드리프트 방지).
컨센·GM추정·가이던스예측은 애널리스트 레이어 상수(FROZEN 기재값, provenance 주석).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from generic_cli import load_generic_profile  # noqa: E402
from engine.generic_forecast import run_generic_forecast  # noqa: E402
from engine.scoring_basis import compare_bases, format_gap_of_gap  # noqa: E402

# ──────────────────────────────────────────────────────────────────────────
# ACTUALS — 프린트 시 채운다 (USD_million; EPS는 USD/주; 마진·세율은 소수, 예: 0.585).
#   출처: TXN Q2'26 IR 어닝 릴리스 / 8-K (분기 종료 2026-06-30).
# ──────────────────────────────────────────────────────────────────────────
# 입력 완료 2026-07-22 (발표 후). 출처: TXN Q2'26 8-K/IR 릴리스, 분기 종료 2026-06-30.
#   매출 $5,463M · GP $3,352M(GM 61.4%) · OP $2,310M(42.3%) · NI $1,980M · EPS $2.14 ·
#   희석주식 920M · 세율 11.5% · 감가상각 $547M · capex $514M(CHIPS 환입 $549M) ·
#   세그: Analog $4,365M / Embedded $788M / Other $310M · 재고 $4.61B(199일).
#   Q3'26 가이드: 매출 $5.65–6.15B(미드 5.90) · EPS $2.23–2.57(미드 2.40). Q3 컨센 ≈ 매출 5,630 / EPS 2.16.
ACTUALS: dict[str, float | None] = {
    "q2_revenue": 5463.0,
    "q2_operating_income": 2310.0,
    "q2_net_income": 1980.0,             # 총 순이익(GAAP)
    "q2_income_allocated_to_common": None,  # 보통주귀속이익(EPS 분자). None이면 EPS×주식수로 파생.
    "q2_eps_diluted": 2.14,              # 보고 희석 EPS = 보통주귀속이익 ÷ 희석주식 (RSU 배분 차감 후)
    "q2_diluted_shares": 920_000_000.0,
    "q2_gross_margin_pct": 0.614,
    "q2_cogs": None,
    "q2_depreciation": 547.0,
    "q2_effective_tax_rate": 0.115,
    "q3_guide_rev_low": 5650.0,
    "q3_guide_rev_high": 6150.0,
    "q3_guide_eps_low": 2.23,
    "q3_guide_eps_high": 2.57,
    "q3_consensus_rev": 5630.0,
    "q3_consensus_eps": 2.16,
    "q2_source": "TXN Q2'26 8-K/IR earnings release 2026-07-22 (10-Q pending; IAC 파생=EPS×주식수)",
}

# ── 동결 애널리스트 레이어 상수 (FROZEN 기재값, 불변) ──────────────────────
CONSENSUS_Q2_REV = 5240.0   # $5.24B (Alphastreet 26명; 호스트 Yahoo fiscal-aware $5,237.29 정합)
CONSENSUS_Q2_EPS = 1.92     # $1.92 (범위 $1.66–2.04; Yahoo $1.94)
OUR_CALL_VS_CONSENSUS = "below"  # 동결 (d): 매출·EPS 공히 컨센 소폭 하회

GM_EST = 0.587              # (b) GM 포인트 추정 58.7%
GM_PRIOR_Q1 = 0.5796       # 2026Q1 실제 GM 57.96%
REV_Q1 = 4825.0            # 2026Q1 매출
DEPREC_Q1 = 541.0          # 2026Q1 감가상각
# (b) 예측 GM 분해(포인트, 동결 (b) 기재값): 가동률 +1.5, 믹스·가격 −0.5, 감가상각 +0.2.
# ⚠ 성분 합 = +1.2pt이나 동결 헤드라인 GM 포인트는 58.7%(prior 57.96% 대비 +0.74pt) — 동결 리포트 (b)의
#   내부 산술 슬립(Codex 검토 확인). 채점은 헤드라인 GM 포인트(GM_EST=58.7%)에 대해 수행; 성분표는 참고.
#   (forward 개선: 분해 성분 합=포인트 순변화 정합을 리포트 생성 단계에서 강제.)
GM_DECOMP_PRED = {"utilization": +1.5, "mix_pricing": -0.5, "depreciation": +0.2}

# 회사 Q2 가이던스(참고) & 우리 Q3 가이던스 예측 (c)
COMPANY_Q2_GUIDE = {"rev": (5000.0, 5400.0), "eps": (1.77, 2.05)}  # mid 5200 / 1.91
Q3_GUIDE_PRED = {"rev": (5300.0, 5700.0), "eps": (1.95, 2.25)}     # mid 5500 / 2.10, 방향 '상향'
Q2_GUIDE_MID_REV = 5200.0

SCALE = 1_000_000.0  # USD_million → USD


# ── 동결 예측 팩터 로드 (커밋된 프로파일에서, 하드코드 드리프트 방지) ──────
def load_frozen() -> dict:
    p = load_generic_profile(REPO / "profiles" / "txn.generic.yaml")
    fc = run_generic_forecast(p)
    def factors(q):
        rev, op, ni, eps = q.revenue_total, q.operating_profit, q.net_profit, q.eps_diluted
        return {"rev": rev, "op": op, "ni": ni, "eps": eps,
                "opm": op / rev, "conv": ni / op, "shares": p.weighted_avg_diluted}
    return {
        "weighted": factors(fc.weighted_quarterly[0]),
        "base": factors(fc.scenarios_quarterly["base"][0]),
        "bear": factors(fc.scenarios_quarterly["bear"][0]),
        "bull": factors(fc.scenarios_quarterly["bull"][0]),
        "shares": p.weighted_avg_diluted,
        "label": fc.weighted_quarterly[0].quarter_label,
    }


def _pct(x: float) -> str:
    return f"{x*100:+.2f}%"


def _eps_from(rev, opm, conv, shares) -> float:
    """EPS = rev × opm × (NI/OP) × scale / shares  (4개 팩터 곱)."""
    return rev * opm * conv * SCALE / shares


# ── 채점 섹션 ───────────────────────────────────────────────────────────────
def score_point(a: dict, f: dict, lines: list[str]) -> None:
    rev_a, eps_a = a["q2_revenue"], a["q2_eps_diluted"]
    lines += ["## 1. 매출·EPS 포인트 오차 (vs 동결)", ""]
    lines += ["| 기준 | 예측 | 실제 | 오차 | %오차(bias) |", "|---|---:|---:|---:|---:|"]
    for tag in ("weighted", "base"):
        rp, ep = f[tag]["rev"], f[tag]["eps"]
        lines.append(f"| 매출 {tag} | {rp:,.0f} | {rev_a:,.0f} | {rev_a-rp:+,.0f} | {_pct((rev_a-rp)/rev_a)} |")
        lines.append(f"| EPS {tag} | {ep:.2f} | {eps_a:.2f} | {eps_a-ep:+.2f} | {_pct((eps_a-ep)/eps_a)} |")
    # 시나리오 밴드 적중
    band = "base" if f["bear"]["eps"] <= eps_a <= f["bull"]["eps"] else "밴드 밖"
    lines += ["", f"- 시나리오 밴드(bear {f['bear']['eps']:.2f} ~ bull {f['bull']['eps']:.2f}) 내 실제 EPS {eps_a:.2f}: **{band}**", ""]


def score_consensus(a: dict, lines: list[str]) -> None:
    rev_a, eps_a = a["q2_revenue"], a["q2_eps_diluted"]
    rev_surp, eps_surp = rev_a - CONSENSUS_Q2_REV, eps_a - CONSENSUS_Q2_EPS
    actual_dir = "above" if eps_surp > 0 else ("below" if eps_surp < 0 else "inline")
    hit = (actual_dir == OUR_CALL_VS_CONSENSUS)
    lines += ["## 2. 컨센서스 대비 surprise + 방향 적중", ""]
    lines.append(f"- 컨센: 매출 {CONSENSUS_Q2_REV:,.0f} / EPS {CONSENSUS_Q2_EPS:.2f}")
    lines.append(f"- 실제: 매출 {rev_a:,.0f} ({rev_surp:+,.0f}, {_pct(rev_surp/CONSENSUS_Q2_REV)}) · EPS {eps_a:.2f} ({eps_surp:+.2f}, {_pct(eps_surp/CONSENSUS_Q2_EPS)})")
    lines.append(f"- 실제 surprise 방향: **{actual_dir}** · 우리 콜: **{OUR_CALL_VS_CONSENSUS}** → **{'적중 ✅' if hit else '미스 ❌'}**")
    lines.append("")


def income_to_common(a: dict) -> tuple[float, str]:
    """EPS 분자 = 보통주귀속이익(NI − RSU/참여증권 배분). TXN 등은 NI를 그대로 쓰지 않는다.
    10-Q 값(q2_income_allocated_to_common)이 있으면 사용, 없으면 EPS×주식수로 파생."""
    if a.get("q2_income_allocated_to_common") is not None:
        return a["q2_income_allocated_to_common"], "10-Q 보고"
    return a["q2_eps_diluted"] * a["q2_diluted_shares"] / SCALE, "파생(EPS×주식수)"


def score_four_lever(a: dict, f: dict, lines: list[str]) -> None:
    need = ("q2_revenue", "q2_operating_income", "q2_net_income", "q2_diluted_shares", "q2_eps_diluted")
    if any(a[k] is None for k in need):
        lines += ["## 3. 4-lever 귀인", "", "- (건너뜀: q2_operating_income / q2_diluted_shares / q2_eps_diluted 필요)", ""]
        return
    rev_a, op_a, ni_a, sh_a = a["q2_revenue"], a["q2_operating_income"], a["q2_net_income"], a["q2_diluted_shares"]
    iac_a, iac_src = income_to_common(a)      # EPS 분자 = 보통주귀속이익
    rsu = ni_a - iac_a                         # RSU/참여증권 배분(NI − IAC)
    p = f["weighted"]
    Rp, Mp, Cp, Sp = p["rev"], p["opm"], p["conv"], p["shares"]  # 예측 conv = 예측NI/OP (동결 모델은 RSU 미반영)
    # 실제 전환 C_a = 보통주귀속이익/OP → OP→NI(세금·below-OP) + NI→보통주귀속(RSU배분)을 모두 포착.
    Ra, Ma, Ca, Sa = rev_a, op_a / rev_a, iac_a / op_a, sh_a
    e0 = _eps_from(Rp, Mp, Cp, Sp)          # 전부 예측
    e1 = _eps_from(Ra, Mp, Cp, Sp)          # + 매출 실제
    e2 = _eps_from(Ra, Ma, Cp, Sp)          # + 영업이익률 실제
    e3 = _eps_from(Ra, Ma, Ca, Sp)          # + OP→보통주귀속 전환 실제(세금+below-OP+RSU배분)
    e4 = _eps_from(Ra, Ma, Ca, Sa)          # + 주식수 실제  = 보고 EPS (분자=IAC라 정확 재구성)
    d_rev, d_opm, d_conv, d_sh = e1-e0, e2-e1, e3-e2, e4-e3
    total = e4 - e0
    resid = e4 - a["q2_eps_diluted"]
    lines += ["## 3. 4-lever generic 귀인 (기여 합 = EPS 오차)", ""]
    lines.append(f"- EPS 분자 = **보통주귀속이익 {iac_a:,.1f}M** ({iac_src}); NI {ni_a:,.0f}M − RSU/참여증권 배분 {rsu:,.1f}M ({100*rsu/ni_a:.2f}% of NI).")
    lines += ["", "| 레버 | 기여(EPS) | 설명 |", "|---|---:|---|"]
    lines.append(f"| 매출 | {d_rev:+.3f} | 실제 {Ra:,.0f} vs 예측 {Rp:,.0f} |")
    lines.append(f"| 영업이익률 | {d_opm:+.3f} | 실제 {Ma*100:.1f}% vs 예측 {Mp*100:.1f}% |")
    lines.append(f"| OP→보통주귀속 전환 | {d_conv:+.3f} | 실제 IAC/OP {Ca*100:.1f}% vs 예측 NI/OP {Cp*100:.1f}% (세금+below-OP+RSU배분) |")
    lines.append(f"| 주식수 | {d_sh:+.3f} | 실제 {Sa:,.0f} vs 예측 {Sp:,.0f} |")
    lines.append(f"| **합계** | **{total:+.3f}** | 예측 {e0:.3f} → 재구성 {e4:.3f} = 보고 {a['q2_eps_diluted']:.2f} (잔차 {resid:+.4f}) |")
    dom = max([("매출", d_rev), ("영업이익률", d_opm), ("OP→보통주귀속", d_conv), ("주식수", d_sh)], key=lambda kv: abs(kv[1]))
    lines += ["", f"- **최대 오차원: {dom[0]} ({dom[1]:+.3f})** · 재구성 잔차 {resid:+.4f}(분자=IAC로 정확 정합)", ""]


def score_gm(a: dict, lines: list[str]) -> None:
    lines += ["## 4. ★ GM 오차 분해 — 감가상각(고정) vs 가동률·믹스(변동)", ""]
    gm_a = a["q2_gross_margin_pct"]
    if gm_a is None and a["q2_cogs"] is not None and a["q2_revenue"] is not None:
        gm_a = (a["q2_revenue"] - a["q2_cogs"]) / a["q2_revenue"]
    if gm_a is None:
        lines += ["- (건너뜀: q2_gross_margin_pct 또는 q2_cogs 필요)", ""]
        return
    err = (gm_a - GM_EST) * 100
    lines.append(f"- 실제 GM **{gm_a*100:.2f}%** vs 예측 {GM_EST*100:.1f}% → GM 오차 **{err:+.2f}pt**")
    dqoq = (gm_a - GM_PRIOR_Q1) * 100
    lines.append(f"- QoQ ΔGM = {dqoq:+.2f}pt (Q1'26 {GM_PRIOR_Q1*100:.2f}% 대비)")
    if a["q2_depreciation"] is not None and a["q2_revenue"] is not None:
        dep_pct_q1 = DEPREC_Q1 / REV_Q1
        dep_pct_a = a["q2_depreciation"] / a["q2_revenue"]
        dep_eff = (dep_pct_q1 - dep_pct_a) * 100          # 감가상각/매출 하락 = GM 양(+)
        util_mix = dqoq - dep_eff                          # 잔차 = 가동률·믹스(변동)
        lines += ["", "| 분해 | 실제(pt) | 예측(pt) |", "|---|---:|---:|"]
        lines.append(f"| 감가상각(고정) | {dep_eff:+.2f} | {GM_DECOMP_PRED['depreciation']:+.2f} |")
        lines.append(f"| 가동률+믹스(변동) | {util_mix:+.2f} | {GM_DECOMP_PRED['utilization']+GM_DECOMP_PRED['mix_pricing']:+.2f} |")
        pred_net_headline = (GM_EST - GM_PRIOR_Q1) * 100
        lines.append(f"| 순 ΔGM | {dqoq:+.2f} | {pred_net_headline:+.2f} |")
        lines.append(f"- ⚠ 예측 성분 합 = {sum(GM_DECOMP_PRED.values()):+.2f}pt이나 동결 헤드라인 순 ΔGM = {pred_net_headline:+.2f}pt(GM 58.7% vs 57.96%) — 동결 (b) 내부 산술 슬립; 채점은 헤드라인 포인트 기준.")
        lines.append(f"- 감가상각 실제 {a['q2_depreciation']:,.0f}(매출의 {dep_pct_a*100:.2f}%) vs Q1 {DEPREC_Q1:,.0f}({dep_pct_q1*100:.2f}%)")
        surprise = "감가상각(고정)" if abs(dep_eff-GM_DECOMP_PRED['depreciation']) > abs(util_mix-(GM_DECOMP_PRED['utilization']+GM_DECOMP_PRED['mix_pricing'])) else "가동률·믹스(변동)"
        lines.append(f"- **GM 오차의 주된 출처: {surprise}**")
    else:
        lines.append("- (감가상각 분해 건너뜀: q2_depreciation 필요)")
    lines.append("")


def score_guidance(a: dict, f: dict, lines: list[str]) -> None:
    lines += ["## 5. 차기(Q3'26) 가이던스 채점", ""]
    if a["q3_guide_rev_low"] is None or a["q3_guide_eps_low"] is None:
        lines += ["- (건너뜀: q3_guide_* 필요)", ""]
        return
    rl, rh = a["q3_guide_rev_low"], a["q3_guide_rev_high"]
    el, eh = a["q3_guide_eps_low"], a["q3_guide_eps_high"]
    rmid, emid = (rl+rh)/2, (el+eh)/2
    pr, pe = Q3_GUIDE_PRED["rev"], Q3_GUIDE_PRED["eps"]
    rev_hit = pr[0] <= rmid <= pr[1]
    eps_hit = pe[0] <= emid <= pe[1]
    direction = "상향" if rmid > Q2_GUIDE_MID_REV else ("하향" if rmid < Q2_GUIDE_MID_REV else "유지")
    lines.append(f"- 실제 Q3 가이드: 매출 {rl:,.0f}–{rh:,.0f}(미드 {rmid:,.0f}) · EPS {el:.2f}–{eh:.2f}(미드 {emid:.2f})")
    lines.append(f"- 우리 예측: 매출 {pr[0]:,.0f}–{pr[1]:,.0f} · EPS {pe[0]:.2f}–{pe[1]:.2f} → 매출미드 **{'적중 ✅' if rev_hit else '미스 ❌'}** · EPS미드 **{'적중 ✅' if eps_hit else '미스 ❌'}**")
    lines.append(f"- 방향(vs Q2 가이드 미드 {Q2_GUIDE_MID_REV:,.0f}): **{direction}** (우리 예측 '상향')")
    if a["q3_consensus_rev"] is not None:
        d = rmid - a["q3_consensus_rev"]
        lines.append(f"- **스톡무버**: Q3 가이드 미드 {rmid:,.0f} vs 컨센 {a['q3_consensus_rev']:,.0f} = {d:+,.0f} ({'컨센 상회→불리시' if d>0 else '컨센 하회→베어리시'})")
    lines.append("")


def score_swings(a: dict, f: dict, lines: list[str]) -> None:
    lines += ["## 6. 사전등록 스윙팩터 발화 판정", ""]
    if a["q2_operating_income"] and a["q2_revenue"] and a["q2_net_income"]:
        p = f["weighted"]
        conv_a = a["q2_net_income"] / a["q2_operating_income"]
        opm_a = a["q2_operating_income"] / a["q2_revenue"]
        conv_gap = abs(conv_a - p["conv"]) * 100
        opm_gap = abs(opm_a - p["opm"]) * 100
        lines.append(f"- (f1) 세금/below-OP: NI/OP 실제 {conv_a*100:.1f}% vs 예측 {p['conv']*100:.1f}% (갭 {conv_gap:.1f}pt) — {'발화' if conv_gap>2 else '미미'}"
                     + (f"; 실효세율 {a['q2_effective_tax_rate']*100:.1f}% vs 가정 13%" if a['q2_effective_tax_rate'] else ""))
        lines.append(f"- (f2) GM/가동률: 영업이익률 실제 {opm_a*100:.1f}% vs 예측 {p['opm']*100:.1f}% (갭 {opm_gap:.1f}pt) — {'발화' if opm_gap>2 else '미미'}")
    else:
        lines.append("- (건너뜀: OP/NI/매출 실제 필요)")
    lines.append("")


def build_scorecard(a: dict, f: dict) -> str:
    basis_comparison = compare_bases(
        base={"revenue": f["base"]["rev"], "eps": f["base"]["eps"]},
        weighted={"revenue": f["weighted"]["rev"], "eps": f["weighted"]["eps"]},
        actual={"revenue": a["q2_revenue"], "eps": a["q2_eps_diluted"]},
        consensus={"revenue": CONSENSUS_Q2_REV, "eps": CONSENSUS_Q2_EPS},
    )
    lines = [f"# TXN {f['label']} 사후 채점 (SCORED)", "",
             "> 동결 예측(FROZEN, commit e66bee5) ↔ 실제 대조. 채점은 '사후 귀인 — 예측 신호 아님'.",
             f"> 실제 출처: {a.get('q2_source') or '(미기재)'}", ""]
    lines.extend(format_gap_of_gap(basis_comparison))
    lines.append("")
    score_point(a, f, lines)
    score_consensus(a, lines)
    score_four_lever(a, f, lines)
    score_gm(a, lines)
    score_guidance(a, f, lines)
    score_swings(a, f, lines)
    lines += ["---", "_다음: 결론(스윙팩터 발화 여부·YAML 앵커 수정 가능한 체계적 편향 vs 리스크밴드 구조항목),",
              "skill_metrics 갱신, HANDOFF_CODEX_efe_q2_2026_txn.md에 before/after 추기._"]
    return "\n".join(lines)


def _selftest() -> int:
    """합성 실적으로 산식 검증: EPS 분자=보통주귀속이익(IAC)일 때 4-lever 합=(보고EPS−예측EPS),
    재구성 e4=보고 EPS(정확), RSU 배분이 합리 범위."""
    f = load_frozen()
    demo = {"q2_revenue": 5300.0, "q2_operating_income": 2150.0, "q2_net_income": 1800.0,
            "q2_eps_diluted": 1.94, "q2_diluted_shares": 910_000_000.0,
            "q2_income_allocated_to_common": None}
    iac, _ = income_to_common(demo)                 # = 1.94×910 = 1765.4 (IAC)
    rsu = demo["q2_net_income"] - iac
    assert 0.0 <= rsu <= 0.03 * demo["q2_net_income"], rsu
    p = f["weighted"]
    Ra, Ma, Ca, Sa = demo["q2_revenue"], demo["q2_operating_income"]/demo["q2_revenue"], iac/demo["q2_operating_income"], demo["q2_diluted_shares"]
    e0 = _eps_from(p["rev"], p["opm"], p["conv"], p["shares"])
    e1 = _eps_from(Ra, p["opm"], p["conv"], p["shares"])
    e2 = _eps_from(Ra, Ma, p["conv"], p["shares"])
    e3 = _eps_from(Ra, Ma, Ca, p["shares"])
    e4 = _eps_from(Ra, Ma, Ca, Sa)
    total = (e1-e0)+(e2-e1)+(e3-e2)+(e4-e3)
    assert abs(total - (e4 - e0)) < 1e-9, (total, e4 - e0)
    assert abs(e4 - demo["q2_eps_diluted"]) < 1e-9, (e4, demo["q2_eps_diluted"])  # 분자=IAC → 보고 EPS 정확
    print(f"selftest OK: 예측 {e0:.4f} → 재구성 {e4:.4f} = 보고 {demo['q2_eps_diluted']:.4f}; "
          f"4-lever 합 {total:+.4f}; RSU 배분 {rsu:.1f}M")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if "--selftest" in argv:
        return _selftest()
    f = load_frozen()
    required = ["q2_revenue", "q2_net_income", "q2_eps_diluted"]
    missing = [k for k in required if ACTUALS.get(k) is None]
    if missing:
        print("SCAFFOLD READY — 아래 필수 ACTUALS를 채운 뒤 재실행:")
        print("  필수:", ", ".join(required), "| 권장: q2_operating_income, q2_diluted_shares, q2_gross_margin_pct(or q2_cogs), q2_depreciation, q3_guide_*")
        print(f"  미입력: {', '.join(missing)}")
        print(f"\n채점 대상(동결 가중 {f['label']}): 매출 {f['weighted']['rev']:,.0f} · EPS {f['weighted']['eps']:.2f}"
              f" | 컨센 {CONSENSUS_Q2_REV:,.0f}/{CONSENSUS_Q2_EPS:.2f}(우리 '{OUR_CALL_VS_CONSENSUS}') | GM추정 {GM_EST*100:.1f}%"
              f" | Q3가이드예측 rev {Q3_GUIDE_PRED['rev']} eps {Q3_GUIDE_PRED['eps']}")
        return 0
    md = build_scorecard(ACTUALS, f)
    out = REPO / "reports" / "txn_q2_2026_SCORED.md"
    out.write_text(md, encoding="utf-8")
    print(md)
    print(f"\n[저장] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
