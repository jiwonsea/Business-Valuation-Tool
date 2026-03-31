"""Streamlit 웹 UI — 기업가치 분석 플랫폼.

실행: streamlit run app.py
"""

from pathlib import Path

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from valuation_runner import load_profile as _load_profile, run_valuation as _run_valuation, _seg_names
from cli import _fetch_and_compare_market_price
from orchestrator import format_summary, _save_to_db
from output.excel_builder import export


@st.cache_data(show_spinner=False)
def _cached_load_profile(path: str):
    return _load_profile(path)


@st.cache_data(show_spinner=False)
def _cached_run_valuation(_vi_hash: str, path: str):
    """프로필 경로 기반 캐싱 — 동일 프로필 재실행 방지."""
    vi = _load_profile(path)
    return vi, _run_valuation(vi)

st.set_page_config(
    page_title="기업가치 분석 플랫폼",
    page_icon="📊",
    layout="wide",
)


# ── Helper: 통화 단위 ──

def _unit_label(vi) -> str:
    """표시 단위 (백만원, 억원, $M 등)."""
    return vi.company.currency_unit


def _currency_sym(vi) -> str:
    """통화 기호 (원, $)."""
    return "원" if vi.company.market == "KR" else "$"


def _format_ev(value: int, vi) -> str:
    """EV를 억원/$B 등 읽기 쉬운 형태로 변환."""
    unit = _unit_label(vi)
    if unit == "백만원":
        return f"{value/100:,.0f}억원"
    elif unit == "억원":
        return f"{value:,}억원"
    elif unit == "$M":
        if abs(value) >= 1000:
            return f"${value/1000:,.1f}B"
        return f"${value:,}M"
    return f"{value:,}{unit}"


# ── Sidebar: 프로필 선택 ──

st.sidebar.title("기업가치 분석 도구")

profile_dir = Path(__file__).parent / "profiles"
profiles = sorted(p for p in profile_dir.glob("*.yaml") if not p.name.startswith("_"))
profile_names = {p.stem: p for p in profiles}

if not profile_names:
    st.error("profiles/ 디렉토리에 YAML 프로필이 없습니다.")
    st.stop()

selected = st.sidebar.selectbox(
    "기업 프로필 선택",
    options=list(profile_names.keys()),
    format_func=lambda x: x.replace("_", " ").title(),
)

# ── 실행 ──

if st.sidebar.button("분석 실행", type="primary"):
    with st.spinner("밸류에이션 계산 중..."):
        profile_path = str(profile_names[selected])
        # 캐싱: 동일 프로필은 재계산 없이 즉시 반환
        vi, result = _cached_run_valuation(profile_path, profile_path)
        # 상장사 괴리율 자동 비교 (시장가는 실시간이므로 캐싱 미적용)
        result = _fetch_and_compare_market_price(vi, result)
        st.session_state["vi"] = vi
        st.session_state["result"] = result
        # DB 저장
        val_id = _save_to_db(vi, result, profile_path)
        if val_id:
            st.toast(f"DB 저장 완료", icon="✅")

if "vi" not in st.session_state:
    st.title("기업가치 분석 플랫폼")
    st.info("왼쪽에서 기업 프로필을 선택하고 '분석 실행'을 클릭하세요.")
    st.stop()

vi = st.session_state["vi"]
result = st.session_state["result"]
seg_names = _seg_names(vi)
by = vi.base_year
unit = _unit_label(vi)
sym = _currency_sym(vi)
is_sotp = result.primary_method == "sotp"
is_nav = result.primary_method == "nav"
is_multiples = result.primary_method == "multiples"

# ── Header ──

st.title(f"{vi.company.name} 기업가치평가")
st.caption(
    f"분석일: {vi.company.analysis_date}  |  Base Year: {by}  |  "
    f"방법론: **{result.primary_method.upper()}**"
)

# ── KPI Cards ──

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("확률가중 주당 가치", f"{result.weighted_value:,}{sym}")
with col2:
    if is_sotp:
        st.metric("SOTP EV", _format_ev(result.total_ev, vi))
    elif is_nav and result.nav:
        st.metric("NAV", f"{result.nav.nav:,}{unit}")
    elif is_multiples and result.multiples_primary:
        mp = result.multiples_primary
        st.metric(f"{mp.primary_multiple_method}", f"{mp.per_share:,}{sym}")
    else:
        st.metric("DCF EV", _format_ev(result.total_ev, vi))
with col3:
    if result.dcf:
        if is_sotp:
            st.metric("DCF EV", _format_ev(result.dcf.ev_dcf, vi))
        else:
            st.metric("WACC", f"{result.wacc.wacc}%")
    else:
        st.metric("WACC", f"{result.wacc.wacc}%")
with col4:
    if result.market_comparison and result.market_comparison.market_price > 0:
        gap = result.market_comparison.gap_ratio
        st.metric("괴리율", f"{gap:+.1%}",
                  delta=f"시장가 {result.market_comparison.market_price:,.0f}{sym}",
                  delta_color="inverse")
    elif is_sotp and result.dcf:
        diff_pct = (result.dcf.ev_dcf - result.total_ev) / result.total_ev * 100
        st.metric("DCF vs SOTP", f"{diff_pct:+.1f}%")
    else:
        st.metric("WACC", f"{result.wacc.wacc}%")

st.divider()

# ── 괴리율 경고 배너 ──

if result.market_comparison and result.market_comparison.flag:
    st.warning(
        f"⚠ **괴리율 경고**: 내재가치 {result.market_comparison.intrinsic_value:,}{sym} vs "
        f"시장가 {result.market_comparison.market_price:,.0f}{sym} "
        f"(괴리율 {result.market_comparison.gap_ratio:+.1%})\n\n"
        f"{result.market_comparison.flag}"
    )

# ── Tabs ──

tab_names = ["시나리오 분석"]
if is_sotp:
    tab_names.append("SOTP 분해")
if is_multiples and result.multiples_primary:
    tab_names.append("상대가치")
if is_nav and result.nav:
    tab_names.append("순자산가치(NAV)")
tab_names.extend(["DCF 예측", "민감도", "교차검증"])
if result.peer_stats:
    tab_names.append("Peer 분석")
if result.monte_carlo:
    tab_names.append("Monte Carlo")
tab_names.append("요약 리포트")

tabs = st.tabs(tab_names)
tab_idx = 0

# ── Tab: 시나리오 분석 ──

with tabs[tab_idx]:
    tab_idx += 1

    if result.scenarios:
        col_l, col_r = st.columns([2, 1])

        with col_l:
            sc_codes = list(vi.scenarios.keys())
            sc_names_list = [vi.scenarios[c].name for c in sc_codes]
            sc_values = [result.scenarios[c].post_dlom for c in sc_codes]
            sc_probs = [vi.scenarios[c].prob for c in sc_codes]

            colors = ["#1B2A4A", "#27AE60", "#E74C3C", "#F39C12", "#8E44AD"]

            fig_sc = go.Figure()
            for i, (code, name, val, prob) in enumerate(
                zip(sc_codes, sc_names_list, sc_values, sc_probs)
            ):
                fig_sc.add_trace(go.Bar(
                    name=f"{code}: {name} ({prob}%)",
                    x=[val], y=[f"{code}: {name}"],
                    orientation='h',
                    marker_color=colors[i % len(colors)],
                    text=f"{val:,}{sym}",
                    textposition='outside',
                ))
            fig_sc.add_vline(
                x=result.weighted_value,
                line_dash="dash", line_color="red",
                annotation_text=f"가중평균 {result.weighted_value:,}{sym}",
            )
            fig_sc.update_layout(
                title="시나리오별 주당 가치",
                xaxis_title=sym,
                showlegend=True,
                height=300,
                barmode='group',
            )
            st.plotly_chart(fig_sc, use_container_width=True)

        with col_r:
            st.subheader("시나리오 상세")
            for code in sc_codes:
                sc = vi.scenarios[code]
                sr = result.scenarios[code]
                with st.expander(f"{code}: {sc.name} ({sc.prob}%)"):
                    st.write(f"**Equity Value:** {sr.equity_value:,}{unit}")
                    st.write(f"**주당가치 (DLOM 전):** {sr.pre_dlom:,}{sym}")
                    st.write(f"**주당가치 (DLOM 후):** {sr.post_dlom:,}{sym}")
                    st.write(f"**가중 기여:** {sr.weighted:,}{sym}")
                    if sc.desc:
                        st.caption(sc.desc)
    else:
        st.info("시나리오가 정의되지 않았습니다.")

# ── Tab: SOTP 분해 (SOTP 경로만) ──

if is_sotp:
    with tabs[tab_idx]:
        tab_idx += 1

        col_l2, col_r2 = st.columns([1, 1])

        with col_l2:
            active_segs = [
                (code, result.sotp[code])
                for code in seg_names
                if code in result.sotp and result.sotp[code].ev > 0
            ]
            if active_segs:
                labels = [seg_names[code] for code, _ in active_segs]
                values = [s.ev for _, s in active_segs]

                fig_pie = px.pie(
                    names=labels, values=values,
                    title="사업부별 EV 구성",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                fig_pie.update_traces(
                    textinfo='label+percent+value',
                    texttemplate=f'%{{label}}<br>%{{value:,.0f}}{unit}<br>(%{{percent}})',
                )
                st.plotly_chart(fig_pie, use_container_width=True)

        with col_r2:
            st.subheader("SOTP 상세")
            for code in seg_names:
                if code in result.sotp:
                    s = result.sotp[code]
                    st.write(
                        f"**{seg_names[code]}**: EBITDA {s.ebitda:,} × "
                        f"{s.multiple:.1f}x = **{s.ev:,}**{unit}"
                    )
            st.divider()
            st.write(f"**Total EV: {result.total_ev:,}{unit} ({_format_ev(result.total_ev, vi)})**")

# ── Tab: 상대가치 (Multiples primary) ──

if is_multiples and result.multiples_primary:
    with tabs[tab_idx]:
        tab_idx += 1

        mp = result.multiples_primary

        st.subheader(f"상대가치평가법 — {mp.primary_multiple_method}")

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("적용 지표값", f"{mp.metric_value:,.0f}{unit}")
        with col_m2:
            st.metric("적용 배수", f"{mp.multiple:.1f}x")
        with col_m3:
            st.metric("주당 가치", f"{mp.per_share:,}{sym}")

        if mp.enterprise_value > 0:
            st.write(f"**Enterprise Value:** {mp.enterprise_value:,}{unit} ({_format_ev(mp.enterprise_value, vi)})")
        st.write(f"**Equity Value:** {mp.equity_value:,}{unit}")

        if result.peer_stats:
            st.divider()
            st.subheader("Peer 기반 멀티플 근거")
            for ps in result.peer_stats:
                name = ps.segment_name or ps.segment_code
                st.write(
                    f"- **{name}**: Median {ps.ev_ebitda_median:.1f}x, "
                    f"Q1-Q3 [{ps.ev_ebitda_q1:.1f}x ~ {ps.ev_ebitda_q3:.1f}x], "
                    f"적용 {ps.applied_multiple:.1f}x (N={ps.count})"
                )

# ── Tab: 순자산가치(NAV) ──

if is_nav and result.nav:
    with tabs[tab_idx]:
        tab_idx += 1

        nv = result.nav

        st.subheader("순자산가치(NAV) 평가")

        col_n1, col_n2, col_n3 = st.columns(3)
        with col_n1:
            st.metric("총자산(장부)", f"{nv.total_assets:,}{unit}")
        with col_n2:
            st.metric("재평가 조정", f"{nv.revaluation:+,}{unit}")
        with col_n3:
            st.metric("조정 총자산", f"{nv.adjusted_assets:,}{unit}")

        st.divider()
        col_n4, col_n5, col_n6 = st.columns(3)
        with col_n4:
            st.metric("총부채", f"{nv.total_liabilities:,}{unit}")
        with col_n5:
            st.metric("순자산가치(NAV)", f"{nv.nav:,}{unit}")
        with col_n6:
            st.metric("주당 NAV", f"{nv.per_share:,}{sym}")

        # 워터폴 차트
        fig_nav = go.Figure(go.Waterfall(
            name="NAV",
            orientation="v",
            measure=["absolute", "relative", "relative", "total"],
            x=["총자산(장부)", "재평가 조정", "부채 차감", "NAV"],
            y=[nv.total_assets, nv.revaluation, -nv.total_liabilities, nv.nav],
            text=[f"{nv.total_assets:,}", f"{nv.revaluation:+,}",
                  f"-{nv.total_liabilities:,}", f"{nv.nav:,}"],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
        ))
        fig_nav.update_layout(
            title=f"NAV 산출 과정 ({unit})",
            yaxis_title=unit,
        )
        st.plotly_chart(fig_nav, use_container_width=True)

# ── Tab: DCF 예측 ──

with tabs[tab_idx]:
    tab_idx += 1

    if result.dcf:
        dcf = result.dcf

        years = [p.year for p in dcf.projections]
        ebitdas = [p.ebitda for p in dcf.projections]
        fcffs = [p.fcff for p in dcf.projections]

        fig_dcf = go.Figure()
        fig_dcf.add_trace(go.Bar(name='EBITDA', x=years, y=ebitdas, marker_color='#2E86C1'))
        fig_dcf.add_trace(go.Bar(name='FCFF', x=years, y=fcffs, marker_color='#27AE60'))
        fig_dcf.update_layout(
            title="DCF 예측기간 EBITDA vs FCFF",
            yaxis_title=unit,
            barmode='group',
        )
        st.plotly_chart(fig_dcf, use_container_width=True)

        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            st.metric("PV(예측기간)", f"{dcf.pv_fcff_sum:,}{unit}")
        with col_d2:
            st.metric("PV(Terminal)", f"{dcf.pv_terminal:,}{unit}")
        with col_d3:
            st.metric("DCF EV", f"{dcf.ev_dcf:,}{unit}")

        # 프로젝션 테이블
        with st.expander("DCF 프로젝션 상세"):
            df_proj = pd.DataFrame([
                {
                    "연도": p.year,
                    f"EBITDA ({unit})": f"{p.ebitda:,}",
                    f"NOPAT ({unit})": f"{p.nopat:,}",
                    f"Capex ({unit})": f"{p.capex:,}",
                    f"ΔNWC ({unit})": f"{p.delta_nwc:,}",
                    f"FCFF ({unit})": f"{p.fcff:,}",
                    "성장률": f"{p.growth:.1%}",
                    f"PV ({unit})": f"{p.pv_fcff:,}",
                }
                for p in dcf.projections
            ])
            st.dataframe(df_proj, use_container_width=True, hide_index=True)
    else:
        st.info("DCF 결과 없음")

# ── Tab: 민감도 ──

with tabs[tab_idx]:
    tab_idx += 1

    def _render_heatmap(data, title, x_label, y_label, row_fmt=".1f", col_fmt=".1f",
                        row_suffix="%", col_suffix="%"):
        """민감도 히트맵 공통 렌더링."""
        row_vals = sorted(set(r.row_val for r in data))
        col_vals = sorted(set(r.col_val for r in data))
        lookup = {(r.row_val, r.col_val): r.value for r in data}
        z_data = [[lookup.get((rv, cv), 0) for cv in col_vals] for rv in row_vals]
        fig = go.Figure(data=go.Heatmap(
            z=z_data,
            x=[f"{cv:{col_fmt}}{col_suffix}" for cv in col_vals],
            y=[f"{rv:{row_fmt}}{row_suffix}" for rv in row_vals],
            colorscale='RdYlGn',
            text=[[f"{v:,.0f}" for v in row] for row in z_data],
            texttemplate="%{text}",
        ))
        fig.update_layout(title=title, xaxis_title=x_label, yaxis_title=y_label)
        st.plotly_chart(fig, use_container_width=True)

    sens_tabs = []
    sens_names = []
    if result.sensitivity_dcf:
        sens_names.append("WACC × 영구성장률")
    if result.sensitivity_multiples:
        sens_names.append("멀티플 민감도")
    if result.sensitivity_irr_dlom:
        sens_names.append("IRR × DLOM")

    if sens_names:
        sub_tabs = st.tabs(sens_names)
        sub_idx = 0

        if result.sensitivity_dcf:
            with sub_tabs[sub_idx]:
                sub_idx += 1
                _render_heatmap(
                    result.sensitivity_dcf,
                    f"WACC × 영구성장률 → DCF EV ({unit})",
                    "영구성장률", "WACC",
                )

        if result.sensitivity_multiples:
            with sub_tabs[sub_idx]:
                sub_idx += 1
                _render_heatmap(
                    result.sensitivity_multiples,
                    f"멀티플 민감도 → 주당가치 ({sym})",
                    "부문2 멀티플", "부문1 멀티플",
                    row_suffix="x", col_suffix="x",
                )

        if result.sensitivity_irr_dlom:
            with sub_tabs[sub_idx]:
                sub_idx += 1
                _render_heatmap(
                    result.sensitivity_irr_dlom,
                    f"FI IRR × DLOM → 주당가치 ({sym})",
                    "DLOM (%)", "FI IRR (%)",
                    col_fmt=".0f",
                )
    else:
        st.info("민감도 분석 결과 없음")

# ── Tab: 교차검증 ──

with tabs[tab_idx]:
    tab_idx += 1

    if result.cross_validations:
        # Football field chart
        methods = [cv.method for cv in result.cross_validations]
        per_shares = [cv.per_share for cv in result.cross_validations]

        fig_cv = go.Figure()
        colors_cv = ['#2E86C1', '#27AE60', '#E74C3C', '#F39C12', '#8E44AD']
        for i, (m, ps) in enumerate(zip(methods, per_shares)):
            fig_cv.add_trace(go.Bar(
                name=m, x=[ps], y=[m],
                orientation='h',
                marker_color=colors_cv[i % len(colors_cv)],
                text=f"{ps:,}{sym}",
                textposition='outside',
            ))
        fig_cv.add_vline(
            x=result.weighted_value,
            line_dash="dash", line_color="red",
            annotation_text=f"가중평균 {result.weighted_value:,}{sym}",
        )
        fig_cv.update_layout(
            title="방법론별 주당 가치 비교 (Football Field)",
            xaxis_title=f"주당 가치 ({sym})",
            height=max(250, len(methods) * 50 + 100),
            showlegend=False,
        )
        st.plotly_chart(fig_cv, use_container_width=True)

        # 교차검증 테이블
        df_cv = pd.DataFrame([
            {
                "방법론": cv.method,
                "지표값": f"{cv.metric_value:,.0f}",
                "배수": f"{cv.multiple:.1f}x",
                f"EV ({unit})": f"{cv.enterprise_value:,}",
                f"Equity ({unit})": f"{cv.equity_value:,}",
                f"주당가치 ({sym})": f"{cv.per_share:,}",
            }
            for cv in result.cross_validations
        ])
        st.dataframe(df_cv, use_container_width=True, hide_index=True)
    else:
        st.info("교차검증 결과 없음")

# ── Tab: Peer 분석 ──

if result.peer_stats:
    with tabs[tab_idx]:
        tab_idx += 1

        df_peer = pd.DataFrame([
            {
                "부문": ps.segment_name or ps.segment_code,
                "N": ps.count,
                "Median": f"{ps.ev_ebitda_median:.1f}x",
                "Mean": f"{ps.ev_ebitda_mean:.1f}x",
                "Q1": f"{ps.ev_ebitda_q1:.1f}x",
                "Q3": f"{ps.ev_ebitda_q3:.1f}x",
                "Min": f"{ps.ev_ebitda_min:.1f}x",
                "Max": f"{ps.ev_ebitda_max:.1f}x",
                "적용 멀티플": f"{ps.applied_multiple:.1f}x",
            }
            for ps in result.peer_stats
        ])
        st.dataframe(df_peer, use_container_width=True, hide_index=True)

        # Peer 멀티플 비교 차트
        fig_peer = go.Figure()
        for ps in result.peer_stats:
            name = ps.segment_name or ps.segment_code
            fig_peer.add_trace(go.Box(
                name=name,
                q1=[ps.ev_ebitda_q1], median=[ps.ev_ebitda_median],
                q3=[ps.ev_ebitda_q3], lowerfence=[ps.ev_ebitda_min],
                upperfence=[ps.ev_ebitda_max], mean=[ps.ev_ebitda_mean],
                boxpoints=False,
            ))
            fig_peer.add_trace(go.Scatter(
                x=[name], y=[ps.applied_multiple],
                mode='markers', marker=dict(symbol='diamond', size=12, color='red'),
                name=f"{name} 적용값",
                showlegend=False,
            ))
        fig_peer.update_layout(
            title="부문별 Peer EV/EBITDA 분포",
            yaxis_title="EV/EBITDA (x)",
        )
        st.plotly_chart(fig_peer, use_container_width=True)

# ── Tab: Monte Carlo ──

if result.monte_carlo:
    with tabs[tab_idx]:
        tab_idx += 1

        mc = result.monte_carlo

        col_mc1, col_mc2, col_mc3, col_mc4 = st.columns(4)
        with col_mc1:
            st.metric("Mean", f"{mc.mean:,}{sym}")
        with col_mc2:
            st.metric("Median", f"{mc.median:,}{sym}")
        with col_mc3:
            st.metric("5th %ile", f"{mc.p5:,}{sym}")
        with col_mc4:
            st.metric("95th %ile", f"{mc.p95:,}{sym}")

        # 히스토그램
        if mc.histogram_bins and mc.histogram_counts:
            fig_mc = go.Figure()
            fig_mc.add_trace(go.Bar(
                x=mc.histogram_bins,
                y=mc.histogram_counts,
                marker_color='#2E86C1',
                opacity=0.7,
            ))
            fig_mc.add_vline(x=result.weighted_value, line_dash="dash", line_color="red",
                             annotation_text=f"가중평균 {result.weighted_value:,}")
            fig_mc.add_vline(x=mc.median, line_dash="dot", line_color="orange",
                             annotation_text=f"Median {mc.median:,}")
            fig_mc.update_layout(
                title=f"Monte Carlo 시뮬레이션 ({mc.n_sims:,}회)",
                xaxis_title=f"주당 가치 ({sym})",
                yaxis_title="빈도",
            )
            st.plotly_chart(fig_mc, use_container_width=True)

        # 분포 통계 테이블
        with st.expander("분포 통계"):
            st.write(f"- **시뮬레이션 횟수**: {mc.n_sims:,}")
            st.write(f"- **Mean**: {mc.mean:,}{sym}  |  **Std**: {mc.std:,}{sym}")
            st.write(f"- **5th**: {mc.p5:,}  |  **25th**: {mc.p25:,}  |  **Median**: {mc.median:,}")
            st.write(f"- **75th**: {mc.p75:,}  |  **95th**: {mc.p95:,}")
            st.write(f"- **Min**: {mc.min_val:,}  |  **Max**: {mc.max_val:,}")

# ── Tab: 요약 리포트 ──

with tabs[tab_idx]:
    summary = format_summary(vi, result)
    st.markdown(summary)

    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        if st.button("Excel 내보내기"):
            path = export(vi, result)
            st.success(f"Excel 저장: {path}")
    with col_exp2:
        st.download_button(
            "리포트 다운로드 (MD)",
            data=summary,
            file_name=f"{vi.company.name}_valuation_report.md",
            mime="text/markdown",
        )
