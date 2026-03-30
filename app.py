"""Streamlit 웹 UI — 기업가치 분석 플랫폼.

실행: streamlit run app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from cli import load_profile, run_valuation
from orchestrator import format_summary
from output.excel_builder import export

st.set_page_config(
    page_title="기업가치 분석 플랫폼",
    page_icon="📊",
    layout="wide",
)

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
        vi = load_profile(str(profile_names[selected]))
        result = run_valuation(vi)
        st.session_state["vi"] = vi
        st.session_state["result"] = result

if "vi" not in st.session_state:
    st.title("기업가치 분석 플랫폼")
    st.info("왼쪽에서 기업 프로필을 선택하고 '분석 실행'을 클릭하세요.")
    st.stop()

vi = st.session_state["vi"]
result = st.session_state["result"]
seg_names = {code: info["name"] for code, info in vi.segments.items()}
by = vi.base_year

# ── Header ──
st.title(f"{vi.company.name} 기업가치평가")
st.caption(f"분석일: {vi.company.analysis_date}  |  Base Year: {by}")

# ── KPI Cards ──
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("확률가중 주당 가치", f"{result.weighted_value:,}원")
with col2:
    st.metric("SOTP EV", f"{result.total_ev/100:,.0f}억원")
with col3:
    st.metric("DCF EV", f"{result.dcf.ev_dcf/100:,.0f}억원")
with col4:
    diff_pct = (result.dcf.ev_dcf - result.total_ev) / result.total_ev * 100
    st.metric("DCF vs SOTP", f"{diff_pct:+.1f}%")

st.divider()

# ── Tabs ──
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "시나리오 분석", "SOTP 분해", "DCF 예측", "민감도", "요약 리포트",
])

# ── Tab 1: 시나리오 분석 ──
with tab1:
    col_l, col_r = st.columns([2, 1])

    with col_l:
        # Football Field Chart
        sc_codes = list(vi.scenarios.keys())
        sc_names = [vi.scenarios[c].name for c in sc_codes]
        sc_values = [result.scenarios[c].post_dlom for c in sc_codes]
        sc_probs = [vi.scenarios[c].prob for c in sc_codes]

        colors = ["#1B2A4A", "#27AE60", "#E74C3C", "#F39C12", "#8E44AD"]

        fig_sc = go.Figure()
        for i, (code, name, val, prob) in enumerate(zip(sc_codes, sc_names, sc_values, sc_probs)):
            fig_sc.add_trace(go.Bar(
                name=f"{code}: {name} ({prob}%)",
                x=[val], y=[f"{code}: {name}"],
                orientation='h',
                marker_color=colors[i % len(colors)],
                text=f"{val:,}원",
                textposition='outside',
            ))
        fig_sc.update_layout(
            title="시나리오별 주당 가치",
            xaxis_title="원",
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
                st.write(f"**Equity Value:** {sr.equity_value:,}백만원")
                st.write(f"**주당가치 (DLOM 전):** {sr.pre_dlom:,}원")
                st.write(f"**주당가치 (DLOM 후):** {sr.post_dlom:,}원")
                st.write(f"**가중 기여:** {sr.weighted:,}원")
                if sc.desc:
                    st.caption(sc.desc)

# ── Tab 2: SOTP 분해 ──
with tab2:
    col_l2, col_r2 = st.columns([1, 1])

    with col_l2:
        active_segs = [(code, result.sotp[code]) for code in seg_names if result.sotp[code].ev > 0]
        labels = [seg_names[code] for code, _ in active_segs]
        values = [s.ev for _, s in active_segs]

        fig_pie = px.pie(
            names=labels, values=values,
            title="사업부별 EV 구성",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_pie.update_traces(textinfo='label+percent+value', texttemplate='%{label}<br>%{value:,.0f}백만원<br>(%{percent})')
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_r2:
        st.subheader("SOTP 상세")
        for code in seg_names:
            s = result.sotp[code]
            st.write(f"**{seg_names[code]}**: EBITDA {s.ebitda:,} × {s.multiple:.1f}x = **{s.ev:,}**백만원")
        st.divider()
        st.write(f"**Total EV: {result.total_ev:,}백만원 ({result.total_ev/100:,.0f}억원)**")

# ── Tab 3: DCF 예측 ──
with tab3:
    dcf = result.dcf

    years = [p.year for p in dcf.projections]
    ebitdas = [p.ebitda for p in dcf.projections]
    fcffs = [p.fcff for p in dcf.projections]

    fig_dcf = go.Figure()
    fig_dcf.add_trace(go.Bar(name='EBITDA', x=years, y=ebitdas, marker_color='#2E86C1'))
    fig_dcf.add_trace(go.Bar(name='FCFF', x=years, y=fcffs, marker_color='#27AE60'))
    fig_dcf.update_layout(
        title="DCF 예측기간 EBITDA vs FCFF",
        yaxis_title="백만원",
        barmode='group',
    )
    st.plotly_chart(fig_dcf, use_container_width=True)

    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        st.metric("PV(예측기간)", f"{dcf.pv_fcff_sum:,}백만원")
    with col_d2:
        st.metric("PV(Terminal)", f"{dcf.pv_terminal:,}백만원")
    with col_d3:
        st.metric("DCF EV", f"{dcf.ev_dcf:,}백만원")

# ── Tab 4: 민감도 ──
with tab4:
    if result.sensitivity_dcf:
        wacc_vals = sorted(set(r.row_val for r in result.sensitivity_dcf))
        tg_vals = sorted(set(r.col_val for r in result.sensitivity_dcf))
        dcf_lookup = {(r.row_val, r.col_val): r.value for r in result.sensitivity_dcf}

        z_data = []
        for w in wacc_vals:
            row = [dcf_lookup.get((w, tg), 0) for tg in tg_vals]
            z_data.append(row)

        fig_heat = go.Figure(data=go.Heatmap(
            z=z_data,
            x=[f"{tg:.1f}%" for tg in tg_vals],
            y=[f"{w:.1f}%" for w in wacc_vals],
            colorscale='RdYlGn',
            text=[[f"{v:,.0f}" for v in row] for row in z_data],
            texttemplate="%{text}",
        ))
        fig_heat.update_layout(
            title="WACC × 영구성장률 → DCF EV (백만원)",
            xaxis_title="영구성장률",
            yaxis_title="WACC",
        )
        st.plotly_chart(fig_heat, use_container_width=True)

# ── Tab 5: 요약 리포트 ──
with tab5:
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
