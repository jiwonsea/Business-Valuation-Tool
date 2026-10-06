"""R20 source-bound additions for edition 1, revision 1."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from io import StringIO
from pathlib import Path

import pandas as pd

from .rle import fy2027_scenario_results

REVISION_CHARTS = {
    "09_gm_beat_compression": ("gm_compression", 3, ("derived.gm_beat.", "derived.gm_qoq.", "guidance.gm_gaap.")),
    "10_price_bit_ranges": ("range_bar", 2, ("judgment.price_bit.",)),
    "11_eps_error_waterfall": ("waterfall", 1, ("scored.eps_", "scored.lever.")),
    "12_fq1_guidance_comparison": ("guidance_comparison", 2, ("prereg.guide_mid.", "guidance.revenue_", "derived.guide_weekly.")),
    "13_scenario_sensitivity_eps": ("eps_bar", 1, ("rle.eps_gaap.", "sensitivity.eps.")),
    "14_opex_net_capex_trend": ("cost_trend", 4, ("is.opex.", "cf.net_capex.", "rle.opex.", "rle.net_capex.")),
    "15_operating_income_waterfall": ("waterfall", 1, ("is.operating_income.", "bridge.op_amount.")),
    "16_sca_structure": ("sca_structure", 2, ("sca.",)),
}
RANGE_J = {
    "low-single-digit": (1, 3), "mid-single-digit": (4, 6), "approximately 10%": (9, 11),
    "high-teens": (16, 19), "approximately 30%": (28, 32), "low-60s": (60, 63), "mid-80s": (84, 86),
}
NEW_BINDINGS = (
    "derived.gm_beat.FQ2-26", "derived.gm_beat.FQ3-26", "derived.gm_beat.FQ4-26",
    "guidance.revenue_lo.FQ4FY26", "guidance.revenue_hi.FQ4FY26", "is.revenue.FY2026Q4.A-8K",
    "guidance.gm_gaap.FQ1FY27",
)
NEW_SECTIONS = ("abbreviations", "company", "fq4_reading", "gm_compression", "price_bit_note", "business_structure", "methodology")


def extend_revision(manifest, narrative, assumptions, remarks_text, values):
    from .narrative import _number, _put_fact, _row_first_number

    def put(key, value, unit, period, basis, source, inputs=(), formula="r20_v1"):
        _put_fact(manifest, key, value, unit, period, basis, key, source,
                  {"formula": formula, "inputs": list(inputs)} if inputs else None)

    history = json.loads((Path(__file__).parent / "sources/guidance_history.json").read_text(encoding="utf-8"))
    periods = [row["target_period"] for row in history["guidance_records"]]
    for index, period in enumerate(periods):
        actual_id, guide_id = f"actual.gm_gaap.{period}.CITED", f"guidance.gm_gaap.{period}.CITED"
        actual, guide = manifest.fact(actual_id), manifest.fact(guide_id)
        put(f"derived.gm_beat.{period}", actual.raw_value - guide.raw_value, "percentage_points", period,
            "CALCULATED", actual.source_id, (actual_id, guide_id), "actual_minus_guidance_midpoint_v1")
        display = f"{actual.raw_value - guide.raw_value:+.2f}%p"
        manifest.fact(f"derived.gm_beat.{period}").display.update({"ko": display, "en": display})
        if index:
            previous = f"actual.gm_gaap.{periods[index - 1]}.CITED"
            put(f"derived.gm_qoq.{period}", actual.raw_value - manifest.fact(previous).raw_value,
                "percentage_points", period, "CALCULATED", actual.source_id, (actual_id, previous), "gm_qoq_v1")
    for side, value in (("lo", 49000), ("hi", 51000)):
        frozen = Path(manifest.sources["SRC-FROZEN"].path).read_text(encoding="utf-8")
        if "$49.0B ~ $51.0B" not in frozen:
            raise ValueError("FROZEN revenue no-difference band was not found")
        put(f"guidance.revenue_{side}.FQ4FY26", value, "USD_million_compact", "FY2026Q4", "PREREG_A", "SRC-FROZEN")
    for product in ("dram", "nand"):
        for period in ("FQ3-26", "FQ4-26"):
            for metric in ("pricing", "bit_shipments"):
                source_id = f"qual.{product}.{metric}.{period}.CITED"
                fact = manifest.fact(source_id)
                phrase = next((key for key in RANGE_J if key in str(fact.raw_value)), None)
                if phrase is None:
                    raise ValueError(f"no approved J range for {source_id}: {fact.raw_value}")
                for side, number in zip(("low", "high"), RANGE_J[phrase], strict=True):
                    key = f"judgment.price_bit.{product}.{metric}.{period}.{side}"
                    put(key, number, "percent", period, "J", fact.source_id, (source_id,), "R20_J_range_conversion")
                    manifest.fact(key).lineage["grade"] = "J"
                    manifest.fact(key).lineage["company_wording"] = str(fact.raw_value)

    frozen_text = Path(manifest.sources["SRC-FROZEN"].path).read_text(encoding="utf-8")
    line = next(line for line in frozen_text.splitlines() if line.startswith("| **예측 가이던스 중간값**"))
    mids = [float(value.replace(",", "")) for value in re.findall(r"(?:≈\s*)([\d,]+)", line)]
    if len(mids) != 3:
        raise ValueError("FROZEN c-2 must have three guidance midpoints")
    for scenario, midpoint in zip(("bear", "base", "bull"), mids, strict=True):
        key = f"prereg.guide_mid.FQ1FY27.{scenario}"
        put(key, midpoint, "USD_million", "FQ1FY27", "PREREG_A", "SRC-FROZEN")
        put(f"derived.guide_weekly.FQ1FY27.{scenario}", (midpoint / 13) / (manifest.fact("is.revenue.FY2026Q4.A-8K").raw_value / 14) - 1,
            "fraction", "FQ1FY27", "CALCULATED", "SRC-FROZEN", (key, "is.revenue.FY2026Q4.A-8K"), "per_week_vs_actual_fq4_v1")
    put("guidance.revenue_hi.FQ1FY27", manifest.fact("guidance.revenue_mid.FQ1FY27").raw_value + manifest.fact("guidance.revenue_tolerance.FQ1FY27").raw_value,
        "USD_million", "FQ1FY27", "CALCULATED", "SRC-EX991-FQ4FY26",
        ("guidance.revenue_mid.FQ1FY27", "guidance.revenue_tolerance.FQ1FY27"), "midpoint_plus_tolerance_v1")
    alternatives = {"slowdown": [.03, .02, .01], "zero": [0, 0, 0], "r8": [.045, .04, .03], "original_gm": None}
    for name, growth in alternatives.items():
        rules = copy.deepcopy(assumptions.rules)
        if growth is None:
            rules["A3_gaap_gross_margin"]["base"]["value"] = rules["A3_gaap_gross_margin"]["sensitivity_preregistered_original"]["value"]
        else:
            rules["A2_fq2_to_fq4_weekly_revenue_growth"]["base"]["value"] = growth
        result = fy2027_scenario_results(assumptions.model_copy(update={"rules": rules}))["base"]
        put(f"sensitivity.eps.{name}.FY2027E", result["eps_gaap"], "USD_per_share", "FY2027E", "RLE", "SRC-RLE-FY27")

    missing = []
    for record in history["guidance_records"]:
        quarter, year = map(int, re.fullmatch(r"FQ([1-4])-(\d{2})", record["target_period"]).groups())
        quarter, year = (4, year - 1) if quarter == 1 else (quarter - 1, year)
        period = f"FY20{year}Q{quarter}"
        source = next(source for source in manifest.sources.values() if source.path == record["source_path"])
        payload = Path(source.path).read_bytes()
        if hashlib.sha256(payload).hexdigest() != source.sha256:
            raise ValueError(f"C14 source SHA mismatch: {source.path}")
        candidates = []
        for table in pd.read_html(StringIO(payload.decode("utf-8"))):
            heading = " ".join(str(value) for value in table.iloc[:4].values.flatten())
            if "Quarterly Financial Results" in heading:
                put(f"is.opex.{period}.A", _row_first_number(table, "Operating expenses"), "USD_million", period, "A", source.source_id)
            for _, row in table.iterrows():
                if "capital expenditures, net" in str(row.iloc[0]).lower():
                    candidates.append(abs(_number(row.iloc[3])))
        if len(candidates) == 1:
            put(f"cf.net_capex.{period}.A", candidates[0], "USD_million", period, "A", source.source_id)
        else:
            missing.append({"period": period, "series": "net_capex", "reason": "No unique quarterly net-capex row in pinned release"})
    # FQ4 release has a directly disclosed quarterly adjusted cash-flow row.
    source = manifest.sources["SRC-EX991-FQ4FY26"]
    quarterly_capex = []
    for table in pd.read_html(StringIO(Path(source.path).read_text(encoding="utf-8"))):
        for _, row in table.iterrows():
            if "capital expenditures, net" in str(row.iloc[0]).lower():
                quarterly_capex.append(abs(_number(row.iloc[3])))
    if len(quarterly_capex) != 1:
        missing.append({"period": "FY2026Q4", "series": "net_capex", "reason": "No unique quarterly net-capex row in pinned release"})
    else:
        put("cf.net_capex.FY2026Q4.A", quarterly_capex[0], "USD_million", "FY2026Q4", "A-8K", source.source_id)
    for year in (2024, 2025, 2026):
        for quarter in range(1, 5):
            period = f"FY{year}Q{quarter}"
            key = f"is.opex.{period}.A" if quarter != 4 or year != 2026 else "is.opex.FY2026Q4.A-8K"
            if key not in manifest.facts:
                gross, op = f"is.gross_profit.{period}.A", f"is.operating_income.{period}.A"
                if gross in manifest.facts and op in manifest.facts:
                    put(key, manifest.fact(gross).raw_value - manifest.fact(op).raw_value, "USD_million", period,
                        "CALCULATED", manifest.fact(gross).source_id, (gross, op), "gross_profit_minus_operating_income_v1")
                else:
                    missing.append({"period": period, "series": "opex", "reason": "Gross profit or operating income absent from pinned quarterly facts"})
    for metric, rule in (("opex", "A4_gaap_opex"), ("net_capex", "A14_net_capex")):
        for quarter, number in enumerate(assumptions.rules[rule]["quarterly_all_scenarios"]["value"], 1):
            put(f"rle.{metric}.FY2027Q{quarter}.base", float(number), "USD_million", f"FY2027Q{quarter}", "RLE", "SRC-RLE-FY27")
    start_rev = manifest.fact("is.revenue.FY2026A.A-8K").raw_value
    end_rev = manifest.fact("is.revenue.FY2027E.base").raw_value
    start_gm = manifest.fact("ratio.gross_margin.FY2026.A-8K").raw_value
    end_gm = manifest.fact("ratio.gross_margin.FY2027E.base").raw_value
    for name, value, inputs in (
        ("revenue", (end_rev - start_rev) * start_gm, ("is.revenue.FY2026A.A-8K", "is.revenue.FY2027E.base", "ratio.gross_margin.FY2026.A-8K")),
        ("gm", end_rev * (end_gm - start_gm), ("is.revenue.FY2027E.base", "ratio.gross_margin.FY2026.A-8K", "ratio.gross_margin.FY2027E.base")),
        ("opex", manifest.fact("is.opex.FY2026A.A-8K").raw_value - manifest.fact("is.opex.FY2027E.base").raw_value, ("is.opex.FY2026A.A-8K", "is.opex.FY2027E.base")),
    ):
        put(f"bridge.op_amount.{name}.FY2026A_to_FY2027E", value, "USD_million", "FY2027E", "CALCULATED", "SRC-RLE-FY27", inputs, "op_amount_bridge_v1")
    plain = " ".join(remarks_text.split())
    patterns = {
        "contracts": (r"signed (\d+) SCAs", "count", 1),
        "revenue_floor": (r"over (\d+)% of our revenue through 2030", "percent", 1),
        "commitments": (r"commitments from customers have increased to \$(\d+) billion", "USD_million", 1000),
        "deposits": (r"balance sheet at the end of fiscal Q4 were \$([\d.]+) billion", "USD_million", 1000),
    }
    for name, (pattern, unit, scale) in patterns.items():
        match = re.search(pattern, plain)
        if not match:
            raise ValueError(f"C16 prepared-remarks source not found: {name}")
        put(f"sca.{name}.FQ4FY26", float(match.group(1)) * scale, unit, "FY2026Q4", "CITED", "SRC-REMARKS-FQ4FY26")
    for name, phrase, value in (("defined_pricing", "Three-quarters", 75), ("market_pricing", "remaining quarter", 25)):
        if phrase not in plain:
            raise ValueError(f"C16 pricing phrase absent: {phrase}")
        put(f"sca.{name}.FQ4FY26", value, "percent", "FY2026Q4", "CALCULATED", "SRC-REMARKS-FQ4FY26", ("sca.revenue_floor.FQ4FY26",), "verbatim_fraction_to_percent_v1")
    scored_text = Path(manifest.sources["SRC-SCORED-FQ4FY26"].path).read_text(encoding="utf-8")
    verdict_section = scored_text.split("## 4. 가이던스 대비 라벨", 1)[1].split("## 5.", 1)[0]
    verdicts = []
    for line in verdict_section.splitlines():
        if not line.startswith("| "):
            continue
        cells = [re.sub(r"[*`]|[✅❌]", "", cell).strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 6 or cells[0] not in {"매출", "GAAP 희석 EPS", "비GAAP 희석 EPS", "GAAP GM", "GAAP opex"}:
            continue
        index = len(verdicts)
        for column, text in enumerate(cells):
            put(f"scored.verdict.{index}.{column}.FQ4FY26", text, "categorical", "FY2026Q4", "SCORED", "SRC-SCORED-FQ4FY26")
        verdicts.append(index)
    if len(verdicts) != 5:
        raise ValueError("SCORED must provide five guidance-verdict rows")
    manifest.metadata.update({"revision": 1, "c14_missing": missing})
    narrative["meta"]["sections"].extend(NEW_SECTIONS)
    for key in NEW_BINDINGS:
        fact = manifest.fact(key)
        values[key] = float(fact.raw_value)
        narrative["fact_bindings"].append({"token": key, "value": fact.raw_value, "unit": fact.unit, "src": fact.source_id, "proposed": False})


def revision_specs(manifest, locale, strings):
    from .charts import ChartPoint, ChartSpec

    period_ids = [f"FQ{quarter}-{year}" for year in (24, 25, 26) for quarter in range(1, 5)]
    gm = [f"derived.gm_beat.{period}" for period in period_ids if f"derived.gm_beat.{period}" in manifest.facts]
    gm += [f"derived.gm_qoq.{period}" for period in period_ids if f"derived.gm_qoq.{period}" in manifest.facts]
    gm += ["guidance.gm_gaap.FQ1FY27"]
    ranges = [f"judgment.price_bit.{product}.{metric}.{period}.{side}" for period in ("FQ3-26", "FQ4-26")
              for product in ("dram", "nand") for metric in ("pricing", "bit_shipments") for side in ("low", "high")]
    eps = ["scored.eps_forecast.FQ4FY26", *[f"scored.lever.{key}.FQ4FY26" for key in ("revenue", "op_margin", "op_to_ni", "shares")], "scored.eps_actual.FQ4FY26"]
    guidance = [*[f"prereg.guide_mid.FQ1FY27.{scenario}" for scenario in ("bear", "base", "bull")],
                *[f"guidance.revenue_{side}.FQ1FY27" for side in ("lo", "mid", "hi")]]
    sensitivity = [*[f"rle.eps_gaap.FY27E.{scenario}" for scenario in ("bear", "base", "bull")],
                   *[f"sensitivity.eps.{name}.FY2027E" for name in ("slowdown", "zero", "r8", "original_gm")]]
    costs = [fact.fact_id for fact in manifest.facts.values() if fact.period in {f"FY{year}Q{quarter}" for year in (2024, 2025, 2026, 2027) for quarter in range(1, 5)}
             and fact.fact_id.startswith(("is.opex.", "cf.net_capex.", "rle.opex.", "rle.net_capex.")) and isinstance(fact.raw_value, (int, float))]
    costs.sort(key=lambda key: (manifest.fact(key).period, key))
    bridge = ["is.operating_income.FY2026A.A-8K", *[f"bridge.op_amount.{name}.FY2026A_to_FY2027E" for name in ("revenue", "gm", "opex")], "is.operating_income.FY2027E.base"]
    sca = [f"sca.{name}.FQ4FY26" for name in ("contracts", "revenue_floor", "defined_pricing", "market_pricing", "commitments", "deposits")]
    groups = (gm, ranges, eps, guidance, sensitivity, costs, bridge, sca)
    specs = []
    for (chart_id, (kind, count, families)), ids in zip(REVISION_CHARTS.items(), groups, strict=True):
        config = strings["revision_charts"][chart_id]
        note = ""
        if chart_id.startswith("10_"):
            note = ("J(판단) 환산; 회사 수치 아님: " if locale == "ko" else "J (judgement) conversion, not company figures: ")
            note += "; ".join(f"{key.replace('approximately ', '≈')} = {low}–{high}%" for key, (low, high) in RANGE_J.items())
        elif chart_id.startswith("14_"):
            missing = manifest.metadata["c14_missing"]
            note = ("실선=실제, 점선=RLE; 제외 분기: " if locale == "ko" else "Solid=actual, dashed=RLE; excluded quarters: ")
            reasons = {"No unique quarterly net-capex row in pinned release": "pin된 보도자료에 분기 순 capex 원문 행이 유일하게 확인되지 않음", "Gross profit or operating income absent from pinned quarterly facts": "pin된 분기 자료에 매출총이익 또는 영업이익이 없음"}
            note += "; ".join(f"{row['period']}/{row['series']}: {reasons[row['reason']] if locale == 'ko' else row['reason']}" for row in missing) if missing else ("없음(원천 12개 분기 확인)." if locale == "ko" else "none (12 quarters verified in sources).")
            note += " " + ("원천 누락은 빈칸이며 추정·보간하지 않는다." if locale == "ko" else "Missing source values remain blank, without estimation or interpolation.")
        elif chart_id.startswith("16_"):
            note = ("35% 이상은 2030년까지 총매출 중 SCA 비중의 하한; 75%/25%는 SCA 매출 내부 비중. 예치금 $12.7B는 준비문 잔액이며 EX-99.1 비유동 고객계약부채 12,895와 별도다." if locale == "ko" else "Over 35% is the SCA share of total revenue through 2030; 75%/25% split SCA revenue. Deposits of $12.7B are the prepared-remarks balance, distinct from EX-99.1 noncurrent customer contract liabilities of 12,895.")
        elif chart_id.startswith("12_"):
            note = ("예측은 사전등록 전망 §(c-2)의 가이던스 중간값(≈). 범위 막대는 회사 가이던스 하단–상단, 점은 중간값이다. % 라벨은 실제 FQ4 매출/14주 대비 FQ1/13주의 주당 성장률이다." if locale == "ko" else "Forecasts are approximate guidance midpoints from the pre-registered forecast §(c-2). The range bar spans company guidance low to high; the point marks the midpoint. % labels are per-week growth: FQ1/13 weeks versus actual FQ4 revenue/14 weeks.")
        elif chart_id.startswith("09_"):
            note = ("막대·선은 좌측 %p, FQ1 FY27 가이던스 점은 우측 GAAP GM %. 첫 분기의 전분기 변화는 원천 비교점 부족으로 빈칸." if locale == "ko" else "Bars and lines use left-axis percentage points; FQ1 FY27 guidance uses right-axis GAAP GM %. First-quarter QoQ is blank without a preceding source point.")
        specs.append(ChartSpec(chart_id, f"{config['figure']} {config['title']}", [ChartPoint(manifest.fact(key).period, key) for key in ids],
                               "2026-10-04", kind, count, families, (), tuple(config["series"]), config["unit"], config["basis"],
                               config["figure"], config["source"], tuple([config["title"], config["x_axis"], config["y_axis"], *config["series"]]), note))
    return specs


def draw_revision_chart(figure, axis, manifest, spec, values, locale):
    """Populate axes only; the caller controls whether any image is written."""
    from .theme import COLORS

    labels = {
        "ko": {"steps": ["PREREG_A", "매출", "영업마진", "OP→NI", "주식수", "실제"], "bridge": ["FY26A", "매출", "GM", "opex", "FY27E base"],
               "paths": ["약세", "기준", "강세", "둔화", "성장 없음", "R8 원안", "GM 원안"]},
        "en": {"steps": ["PREREG_A", "Revenue", "OP margin", "OP to NI", "Shares", "Actual"], "bridge": ["FY26A", "Revenue", "GM", "Opex", "FY27E base"],
               "paths": ["Bear", "Base", "Bull", "Slowdown", "Zero growth", "R8 original", "Original GM"]},
    }[locale]
    if spec.chart_type == "waterfall":
        names = labels["steps"] if spec.chart_id.startswith("11_") else labels["bridge"]
        total = values[0]
        tops = [total]
        axis.bar(0, total, color=COLORS["primary"])
        for index, delta in enumerate(values[1:-1], 1):
            axis.bar(index, abs(delta), bottom=min(total, total + delta), color=COLORS["blue_mid"] if delta >= 0 else COLORS["warning"])
            tops.append(max(total, total + delta))
            total += delta
        # Published four-lever components are rounded; show the disclosed total.
        axis.bar(len(values) - 1, values[-1], color=COLORS["primary"])
        tops.append(values[-1])
        axis.set_xticks(range(len(values)), names)
        eps_chart = spec.chart_id.startswith("11_")
        for index, value in enumerate(values):
            label = f"{value:+,.2f}" if eps_chart else f"{value:+,.0f}"
            axis.annotate(label, (index, tops[index]), xytext=(0, 6), textcoords="offset points", ha="center", fontsize=8)
        if eps_chart:
            axis.set_ylim(31.5, 34.0)
            # A visible break marks the truncated zero-based start/end bars.
            for y in (-.015, .015):
                axis.plot([-.01, .01], [y - .01, y + .01], transform=axis.transAxes, color=COLORS["ink"], clip_on=False)
        else:
            axis.set_ylim(0, max(tops) * 1.16)
    elif spec.chart_type == "range_bar":
        names = []
        for point in spec.points[::2]:
            parts = point.fact_id.split(".")
            metric = ("가격" if parts[3] == "pricing" else "비트") if locale == "ko" else ("price" if parts[3] == "pricing" else "bits")
            names.append(f"{parts[4]} {parts[2].upper()} {metric}")
        axis.barh(range(len(names)), [values[i + 1] - values[i] for i in range(0, len(values), 2)], left=values[::2], color=COLORS["primary"])
        axis.set_yticks(range(len(names)), names)
        axis.invert_yaxis()
    elif spec.chart_type == "eps_bar":
        axis.bar(labels["paths"], values, color=[COLORS["gray_dark"], COLORS["primary"], COLORS["blue_mid"], *[COLORS["warning"]] * 4])
    elif spec.chart_type == "cost_trend":
        periods = [f"FY{year}Q{quarter}" for year in (2024, 2025, 2026, 2027) for quarter in range(1, 5)]
        for prefix, color in (("is.opex.", COLORS["primary"]), ("cf.net_capex.", COLORS["warning"]), ("rle.opex.", COLORS["primary"]), ("rle.net_capex.", COLORS["warning"])):
            mapping = {point.label: value for point, value in zip(spec.points, values, strict=True) if point.fact_id.startswith(prefix)}
            # NaN deliberately breaks the line at missing observations.
            actual = [mapping.get(period, float("nan")) for period in periods]
            is_rle = prefix.startswith("rle.")
            index = 0 if "opex" in prefix else 1
            label = spec.series_labels[index]
            if is_rle:
                label = label.replace("Actual ", "").replace(" 실제", "") + " RLE"
            axis.plot(range(len(periods)), actual, linestyle="--" if is_rle else "-", marker="o", color=color, label=label)
        axis.set_xticks(range(len(periods)), [p.replace("FY20", "FY") for p in periods])
        axis.legend(frameon=False, fontsize=7)
    elif spec.chart_type == "guidance_comparison":
        mids, low, mid, high = values[:3], *values[3:]
        names = [*labels["paths"][:3], "가이던스" if locale == "ko" else "Guidance"]
        axis.bar(range(3), mids, width=.65, color=COLORS["blue_mid"])
        axis.bar(3, high - low, bottom=low, width=.65, color=COLORS["primary"], alpha=.7)
        axis.scatter([3], [mid], color=COLORS["ink"], zorder=3)
        axis.set_xticks(range(4), names)
        anchor = manifest.fact("is.revenue.FY2026Q4.A-8K").raw_value
        for index, value in enumerate([*mids, mid]):
            growth = ((value / 13) / (anchor / 14) - 1) * 100
            axis.annotate(f"{growth:+.1f}%", (index, high if index == 3 else value),
                          xytext=(0, 8), textcoords="offset points", ha="center", fontsize=8)
        axis.set_ylim(0, high * 1.13)
    elif spec.chart_type == "gm_compression":
        beat = [(point.label, value) for point, value in zip(spec.points, values, strict=True) if point.fact_id.startswith("derived.gm_beat.")]
        qoq = {point.label: value for point, value in zip(spec.points, values, strict=True) if point.fact_id.startswith("derived.gm_qoq.")}
        names = [period for period, _ in beat] + ["FQ1-27"]
        axis.bar(range(len(beat)), [value for _, value in beat], color=COLORS["blue_mid"], label=spec.series_labels[0])
        axis.plot(range(len(beat)), [qoq.get(period, float("nan")) for period, _ in beat], "-o", color=COLORS["primary"], label=spec.series_labels[1])
        axis.set_xticks(range(len(names)), names)
        right = axis.twinx()
        right.scatter([len(beat)], [values[-1]], color=COLORS["warning"], label=spec.series_labels[2])
        right.set_ylabel("GAAP GM (%)")
        handles, names = axis.get_legend_handles_labels()
        other_handles, other_names = right.get_legend_handles_labels()
        figure.legend(handles + other_handles, names + other_names, frameon=False,
                      fontsize=7, loc="lower center", bbox_to_anchor=(.5, .01), ncols=1)
    elif spec.chart_type == "sca_structure":
        figure.clear()
        left, right = figure.subplots(1, 2)
        left.bar(["가격 틀" if locale == "ko" else "Pricing framework", "시장가" if locale == "ko" else "Market pricing"], values[2:4], color=[COLORS["primary"], COLORS["warning"]])
        left.set_ylabel("% SCA")
        right.bar(["고객 약정" if locale == "ko" else "Commitments", "예치금" if locale == "ko" else "Deposits"], values[4:6], color=[COLORS["blue_mid"], COLORS["primary"]])
        right.set_ylabel("USD million")
        return left
    return axis
