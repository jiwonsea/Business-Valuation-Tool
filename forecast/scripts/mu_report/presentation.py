"""R22 reader-facing labels; no financial calculations or input mutations."""
from __future__ import annotations

FIGURE_ORDER = (
    "02_business_unit_mix", "12_fq1_guidance_comparison", "16_sca_structure",
    "10_price_bit_ranges", "14_opex_net_capex_trend", "04_beat_history",
    "11_eps_error_waterfall", "05_scenario_fan", "09_gm_beat_compression",
    "03b_guidance_beat_history", "01_quarterly_revenue_margin", "06_annual_income",
    "08_cash_flow_capex_net_cash", "15_operating_income_waterfall",
    "13_scenario_sensitivity_eps", "07_valuation_heatmap",
)

SOURCE_TITLES = {
    "SRC-FIXTURE": ("고정 테스트 입력", "Fixed test inputs"),
    "SRC-EX991-FQ4FY26": ("Micron FQ4 FY26 실적 보도자료(8-K EX-99.1)", "Micron FQ4 FY26 earnings release (8-K EX-99.1)"),
    "SRC-REMARKS-FQ4FY26": ("Micron FQ4 FY26 준비문", "Micron FQ4 FY26 prepared remarks"),
    "SRC-REMARKS-FQ3-FY26": ("Micron FQ3 FY26 준비문", "Micron FQ3 FY26 prepared remarks"),
    "SRC-FROZEN": ("MU FQ4 FY26 사전등록 전망(Freeze A)", "MU FQ4 FY26 pre-registered forecast (Freeze A)"),
    "SRC-FROZEN-PREREG-A": ("MU FQ4 FY26 사전등록 전망(Freeze A)", "MU FQ4 FY26 pre-registered forecast (Freeze A)"),
    "SRC-SCORED-FQ4FY26": ("MU FQ4 FY26 사전등록 채점 문서", "MU FQ4 FY26 pre-registration scoring document"),
    "SRC-RLE-FY27": ("본 리포트 FY27E–FY28E 추정(RLE)", "This report's FY27E–FY28E estimates (RLE)"),
    "SRC-HANDOFF-R9-R12": ("저자 승인 사전 규칙·사후 변경·해석 정정", "Author-approved pre-print rules, post-print changes and interpretation correction"),
    "SRC-10K-FY23": ("Micron FY2023 Form 10-K", "Micron FY2023 Form 10-K"),
    "SRC-10K-FY25": ("Micron FY2025 Form 10-K", "Micron FY2025 Form 10-K"),
    "SRC-COMPANYFACTS": ("SEC EDGAR Micron 재무 공시 데이터", "SEC EDGAR Micron financial disclosures"),
    "SRC-PR-FQ3-FY26": ("Micron FQ3 FY26 실적 보도자료", "Micron FQ3 FY26 earnings release"),
    "SRC-PRICE-1": ("Nasdaq MU 2026-10-01 종가 기록 1", "Nasdaq MU 2026-10-01 closing-price record 1"),
    "SRC-PRICE-2": ("Nasdaq MU 2026-10-01 종가 기록 2", "Nasdaq MU 2026-10-01 closing-price record 2"),
}


def source_title(source_id: str, locale: str) -> str:
    if source_id.startswith(("SRC-GUIDANCE-", "SRC-BU-")):
        return "Micron 분기 실적 보도자료(8-K EX-99.1)" if locale == "ko" else "Micron quarterly earnings releases (8-K EX-99.1)"
    if source_id not in SOURCE_TITLES:
        raise ValueError(f"Unmapped public source title: {source_id}")
    return SOURCE_TITLES[source_id][0 if locale == "ko" else 1]


def source_titles(source_ids, locale: str) -> str:
    return "; ".join(dict.fromkeys(source_title(key, locale) for key in source_ids))


RULE_SENTENCES = {
    "A1_fq1_revenue": ("약세는 가이던스 하단, 기준·강세는 중간값에 과거 상회율을 적용한다.", "Bear uses the guidance low end; base and bull apply historical beats to the midpoint."),
    "A2_fq2_to_fq4_weekly_revenue_growth": ("후속 분기 매출은 전분기 주당 매출에 각 경로의 성장률을 적용한다.", "Later-quarter revenue applies each path's growth rate to prior-quarter revenue per week."),
    "A2_prime_decline_parallel_path": ("FQ1 주당 성장률이 −2% 이하이면 하락 병렬 경로를 발동한다. 주당 성장률은 FQ1 매출÷13주를 FQ4 실제 매출÷14주로 나눈 값에서 1을 뺀다.", "Activate the parallel decline path when FQ1 weekly growth is at most −2%. Weekly growth is (FQ1 revenue / 13) / (FQ4 actual revenue / 14) − 1."),
    "A3_gaap_gross_margin": ("분기별 매출총이익은 각 경로의 매출에 해당 분기 GAAP 매출총이익률을 곱한다.", "Quarterly gross profit equals each path's revenue times its GAAP gross margin."),
    "A4_gaap_opex": ("첫 분기 GAAP 가이던스와 연간 비용 안내를 분기별로 배분한다.", "Allocate first-quarter GAAP guidance and the annual expense outlook across quarters."),
    "A5_below_operating_pct_of_revenue": ("영업이익 아래 항목은 매출에 사전등록 비율을 곱한다.", "Below-operating items equal revenue times the pre-registered ratio."),
    "A6_gaap_effective_tax_rate": ("세전이익은 매출총이익에서 영업비용을 빼고 영업이익 아래 항목을 더한다. 가이던스 순이익과 세전이익으로 세율을 역산하며, 기준 경로의 잔여 세전 입력은 0이다.", "Pretax income equals gross profit less opex plus below-operating items. Backsolve tax from guided net income and pretax income; the base residual pretax input is 0."),
    "A7_diluted_shares": ("분기별 희석 가중평균 주식수는 첫 분기 가이던스를 유지하며 자사주 매입은 반영하지 않는다.", "Hold quarterly diluted weighted-average shares at first-quarter guidance; omit buybacks."),
    "A8_fy2028_revenue_growth": ("FY28E 매출은 FY27E 매출에 경로별 연간 성장률을 적용한다.", "FY28E revenue applies each path's annual growth rate to FY27E revenue."),
    "A9_fy2028_gross_margin": ("FY27 마지막 분기 매출총이익률에서 약세는 0.15, 기준은 0.03을 차감하고 강세는 유지한다.", "Subtract 0.15 in bear and 0.03 in base from FY27 final-quarter margin; hold bull flat."),
    "A10_fy2028_opex": ("FY28E 영업비용은 FY27E 영업비용에 1.08을 곱한다.", "FY28E opex equals FY27E opex times 1.08."),
    "A11_da": ("연간 감가상각률은 FY26 감가상각÷기초·기말 유형자산 평균, 분기율은 연간율÷4이다. 기말 유형자산은 기초 유형자산＋순설비투자−감가상각이다.", "Annual D&A rate is FY26 D&A / average opening and closing PP&E; quarterly rate is annual rate / 4. Closing PP&E is opening PP&E plus net capex less D&A."),
    "A12_sbc": ("과거 주식보상÷GAAP 영업비용 비율의 중앙값에 FY27E 영업비용을 곱한다.", "Multiply the historical median SBC / GAAP opex ratio by FY27E opex."),
    "A13_working_capital": ("운전자본 증가÷매출 증가의 과거 중앙값을 연간 매출 증가에 곱한다. 현금흐름에서는 이를 차감한다.", "Apply the historical median change in working capital / change in revenue to annual revenue growth; subtract it in cash flow."),
    "A14_net_capex": ("첫 분기·상반기 회사 안내를 사용하고 하반기는 상반기와 같은 하한으로 둔다.", "Use company first-quarter and first-half guidance; set second half equal to first half as a lower bound."),
    "A15_dividends": ("연간 배당은 분기 주당 배당×4분기×희석주식수이다.", "Annual dividends equal quarterly dividend per share × 4 quarters × diluted shares."),
    "A16_sca_deposits": ("SCA 예치금은 순현금에서 조정하지 않으며 예측하지 않는다.", "SCA deposits are neither adjusted out of net cash nor forecast."),
    "A17_nongaap_fy2027_fy2028": ("비GAAP 조정 가정이 없어 추정하지 않는다.", "No estimate without non-GAAP adjustment assumptions."),
}

FIELD_LABELS = {
    "bear": ("약세", "Bear"), "base": ("기준", "Base"), "bull": ("강세", "Bull"),
    "sensitivity_company_midpoint": ("회사 중간값 민감도", "Company-midpoint sensitivity"),
    "sensitivity_existing_slowdown": ("둔화 민감도", "Slowdown sensitivity"),
    "sensitivity_preregistered_original": ("사전등록 원안 민감도", "Original pre-print sensitivity"),
    "quarterly_all_scenarios": ("FQ1–FQ4 공통", "FQ1–FQ4, all paths"),
    "all_scenarios": ("모든 경로", "All paths"), "trigger": ("발동 조건", "Trigger"),
    "observed_direction": ("관측 성장률", "Observed growth"), "status": ("가용성", "Availability"),
    "fy2027_total": ("FY27E 합계", "FY27E total"), "fy2028_total": ("FY28E 합계", "FY28E total"),
    "buyback": ("자사주 매입", "Buybacks"), "sensitivity_reduction": ("주식수 감소 민감도", "Share-reduction sensitivity"),
    "fy2026_rate_d": ("FY26 연간율", "FY26 annual rate"), "quarterly_rate": ("분기율", "Quarterly rate"),
    "fy2027_ending_ppe": ("FY27E 기말 유형자산", "FY27E closing PP&E"),
    "median_rate": ("과거 중앙 비율", "Historical median ratio"), "median_k": ("과거 중앙 비율", "Historical median ratio"),
    "sensitivity_pct": ("민감도", "Sensitivity"), "quarterly_dps": ("분기 주당 배당", "Quarterly dividend per share"),
    "rle_periods": ("추정기간", "Estimate periods"), "value": ("가용성", "Availability"),
}
