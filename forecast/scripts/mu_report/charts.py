"""Manifest-driven deterministic chart rendering with semantic contracts."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from .facts import Manifest
from .inputs import atomic_write
from .theme import COLORS

CHART_NAMES = [
    "01_quarterly_revenue_margin", "02_business_unit_mix", "03b_guidance_beat_history",
    "04_beat_history", "05_scenario_fan", "06_annual_income", "07_valuation_heatmap",
    "08_cash_flow_capex_net_cash",
]


@dataclass(frozen=True)
class ChartPoint:
    label: str
    fact_id: str


@dataclass(frozen=True)
class ChartSpec:
    chart_id: str
    title: str
    points: list[ChartPoint]
    source_as_of: str
    chart_type: str = "line"
    series_count: int = 1
    allowed_families: tuple[str, ...] = ()
    placeholder_slots: tuple[str, ...] = ()
    series_labels: tuple[str, ...] = ()
    unit: str = "USD million"
    basis: str = "GAAP"
    figure_number: str = ""
    source_label: str = "canonical fact manifest"
    ui_text: tuple[str, ...] = ()


def fixture_specs(manifest: Manifest) -> list[ChartSpec]:
    ids = ["is.revenue.FY2026Q4.A-8K", "is.gross_margin.FY2026Q4.A-8K", "is.operating_margin.FY2026Q4.A-8K", "is.eps_gaap.FY2026Q4.PREREG_A"]
    return [ChartSpec(name, name.replace("_", " ").title(), [ChartPoint(str(i + 1), fact_id) for i, fact_id in enumerate(ids)], "2099-01-01 · FIXTURE") for name in CHART_NAMES]


def _period_sort(fact_id: str) -> tuple[int, int]:
    match = re.search(r"FY(\d{4})Q(\d)", fact_id)
    return tuple(int(value) for value in match.groups()) if match else (0, 0)


def _quarter_label(period: str) -> str:
    match = re.fullmatch(r"FY(\d{4})Q([1-4])", period)
    return f"FQ{match.group(2)}-{match.group(1)[2:]}" if match else period


def dryrun_specs(manifest: Manifest, locale: str, strings: dict) -> list[ChartSpec]:
    configs = strings["charts"]
    quarterly = sorted((key for key in manifest.facts if key.startswith("is.revenue.FY") and "Q" in key and key.endswith(".A")), key=_period_sort)
    quarterly_margins = [f"ratio.{metric}_margin.{manifest.fact(fact_id).period}.A" for metric in ("gross", "operating") for fact_id in quarterly]
    business_periods = ("FQ4-24", "FQ1-25", "FQ2-25", "FQ3-25", "FQ4-25", "FQ1-26", "FQ2-26", "FQ3-26")
    business = [key for period in business_periods for key in manifest.facts if key.startswith("bu.revenue.") and key.endswith(f".{period}.A")]
    history_periods = [f"FQ{quarter}-{year}" for year, quarter in ((24, 2), (24, 3), (24, 4), (25, 1), (25, 2), (25, 3), (25, 4), (26, 1), (26, 2), (26, 3))]
    gm = [f"{family}.{period}.CITED" for family in ("guidance.gm_gaap", "actual.gm_gaap") for period in history_periods]
    beat_revenue = [f"beat.revenue_pct.{period}.CITED" for period in history_periods]
    beat_eps = sorted((key for key in manifest.facts if key.startswith("beat.eps_gaap_usd.")), key=lambda key: history_periods.index(manifest.fact(key).period))
    fan = ["is.revenue.FY2026Q3.A", "prereg.revenue.bear.FY2026Q4.PREREG_A", "prereg.revenue.base.FY2026Q4.PREREG_A", "prereg.revenue.bull.FY2026Q4.PREREG_A"]
    annual = [
        *[f"is.{metric}.FY{year}A" for metric in ("revenue", "operating_income", "net_income") for year in (2023, 2024, 2025)],
        "is.revenue.FY2026E.PREREG_A", "is.net_income.FY2026E.PREREG_A",
    ]
    cash = [
        *[f"cf.fcf_adjusted.FY{year}A" for year in (2023, 2024, 2025)],
        *[f"cf.net_capex.FY{year}A" for year in (2023, 2024, 2025)],
        *[f"bs.net_cash_unadjusted.FY{year}.A" for year in (2023, 2024, 2025)],
    ]
    definitions = {
        "01_quarterly_revenue_margin": ("bar_line", 3, ("is.revenue.", "ratio.gross_margin.", "ratio.operating_margin."), ("FQ4-26",), [*quarterly, *quarterly_margins]),
        "02_business_unit_mix": ("stacked_bar", 4, ("bu.revenue.",), ("FQ4-26",), business),
        "03b_guidance_beat_history": ("guidance_actual", 2, ("guidance.gm_gaap.", "actual.gm_gaap."), ("FQ4-26",), gm),
        "04_beat_history": ("two_panel", 2, ("beat.revenue_pct.", "beat.eps_gaap_usd."), ("FQ4-26",), [*beat_revenue, *beat_eps]),
        "05_scenario_fan": ("fan", 4, ("is.revenue.", "prereg.revenue."), ("FY2027Q1", "FY2027Q2", "FY2027Q3", "FY2027Q4"), fan),
        "06_annual_income": ("grouped_bar", 3, ("is.revenue.", "is.operating_income.", "is.net_income."), ("FY2026A-8K", "FY2027E", "FY2028E"), annual),
        "07_valuation_heatmap": ("heatmap", 1, (), ("PRICE_UNAVAILABLE",), []),
        "08_cash_flow_capex_net_cash": ("multi_series", 3, ("cf.fcf_adjusted.", "cf.net_capex.", "bs.net_cash_unadjusted."), ("SCA_UNAVAILABLE",), cash),
    }
    specs = []
    for chart_id in CHART_NAMES:
        chart_type, count, families, slots, fact_ids = definitions[chart_id]
        config = configs[chart_id]
        specs.append(ChartSpec(
            chart_id, f"{config['figure']} {config['title']}", [ChartPoint(_quarter_label(manifest.fact(fact_id).period), fact_id) for fact_id in fact_ids], "2026-09-25",
            chart_type, count, families, slots, tuple(config["series"]), config["unit"], config["basis"], config["figure"], config["source"],
            tuple([config["title"], config["x_axis"], config["y_axis"], *config["series"]]),
        ))
    return specs


def e2b_specs(manifest: Manifest, locale: str, strings: dict) -> list[ChartSpec]:
    configs = strings["charts"]
    quarterly = sorted(
        (key for key in manifest.facts if key.startswith("is.revenue.FY") and "Q" in key and key.endswith(".A")),
        key=_period_sort,
    )
    quarterly_margins = [
        f"ratio.{metric}_margin.{manifest.fact(fact_id).period}.A"
        for metric in ("gross", "operating") for fact_id in quarterly
    ]
    business_periods = ("FQ4-24", "FQ1-25", "FQ2-25", "FQ3-25", "FQ4-25", "FQ1-26", "FQ2-26", "FQ3-26", "FQ4-26")
    business = [key for period in business_periods for key in manifest.facts if key.startswith("bu.revenue.") and key.endswith(f".{period}.A")]
    history_periods = [f"FQ{quarter}-{year}" for year, quarter in ((24, 2), (24, 3), (24, 4), (25, 1), (25, 2), (25, 3), (25, 4), (26, 1), (26, 2), (26, 3), (26, 4))]
    gm = [f"{family}.{period}.CITED" for family in ("guidance.gm_gaap", "actual.gm_gaap") for period in history_periods]
    beat_revenue = [f"beat.revenue_pct.{period}.CITED" for period in history_periods]
    beat_eps = [f"beat.eps_gaap_usd.{period}.CITED" for period in history_periods]
    fan = ["is.revenue.FY2026Q4.A-8K", *[f"rle.revenue.FY2027Q{quarter}.{scenario}" for scenario in ("bear", "base", "bull") for quarter in range(1, 5)]]
    annual = [
        *[f"is.{metric}.FY{year}A" for metric in ("revenue", "operating_income", "net_income") for year in (2023, 2024, 2025)],
        "is.revenue.FY2026E.PREREG_A", "is.net_income.FY2026E.PREREG_A",
        *[f"is.{metric}.FY2026A.A-8K" for metric in ("revenue", "operating_income", "net_income")],
        *[f"is.{metric}.FY{year}E.base" for metric in ("revenue", "operating_income", "net_income") for year in (2027, 2028)],
    ]
    heatmap = [f"val.pe_sensitivity.r{row}.c{column}.FY2027E" for row in range(5) for column in range(5)]
    cash = [
        *[f"cf.fcf_adjusted.FY{year}A" for year in (2023, 2024, 2025)], "cf.fcf_adjusted.FY2026A",
        "cf.fcf_adjusted.FY2027E.base", "cf.fcf_adjusted.FY2028E.base",
        *[f"cf.net_capex.FY{year}A" for year in (2023, 2024, 2025)], "cf.net_capex.FY2026A",
        "cf.net_capex.FY2027E.base", "cf.net_capex.FY2028E.base",
        *[f"bs.net_cash_unadjusted.FY{year}.A" for year in (2023, 2024, 2025)], "bs.net_cash_unadjusted.FY2026.A-8K",
        "bs.net_cash_unadjusted.FY2027E.base", "bs.net_cash_unadjusted.FY2028E.base",
    ]
    definitions = {
        "01_quarterly_revenue_margin": ("bar_line", 3, ("is.revenue.", "ratio.gross_margin.", "ratio.operating_margin."), [*quarterly, *quarterly_margins]),
        "02_business_unit_mix": ("stacked_bar", 4, ("bu.revenue.",), business),
        "03b_guidance_beat_history": ("guidance_actual", 2, ("guidance.gm_gaap.", "actual.gm_gaap."), gm),
        "04_beat_history": ("two_panel", 2, ("beat.revenue_pct.", "beat.eps_gaap_usd."), [*beat_revenue, *beat_eps]),
        "05_scenario_fan": ("fan", 4, ("is.revenue.", "rle.revenue."), fan),
        "06_annual_income": ("grouped_bar", 3, ("is.revenue.", "is.operating_income.", "is.net_income."), annual),
        "07_valuation_heatmap": ("heatmap", 1, ("val.pe_sensitivity.",), heatmap),
        "08_cash_flow_capex_net_cash": ("multi_series", 3, ("cf.fcf_adjusted.", "cf.net_capex.", "bs.net_cash_unadjusted."), cash),
    }
    specs = []
    for chart_id in CHART_NAMES:
        chart_type, count, families, fact_ids = definitions[chart_id]
        config = configs[chart_id]
        specs.append(ChartSpec(
            chart_id, f"{config['figure']} {config['title']}",
            [ChartPoint(_quarter_label(manifest.fact(fact_id).period), fact_id) for fact_id in fact_ids],
            "2026-10-04", chart_type, count, families, (), tuple(config["series"]), config["unit"], config["basis"],
            config["figure"], config["source"], tuple([config["title"], config["x_axis"], config["y_axis"], *config["series"]]),
        ))
    return specs


def _values(manifest: Manifest, spec: ChartSpec) -> tuple[list[float], list[str]]:
    values, refs = [], []
    for point in spec.points:
        fact = manifest.fact(point.fact_id)
        if not isinstance(fact.raw_value, (int, float)):
            raise ValueError(f"chart fact is not numeric: {point.fact_id}")
        values.append(float(fact.raw_value)); refs.append(point.fact_id)
    return values, refs


def _series(spec: ChartSpec, values: list[float], prefix: str) -> list[tuple[ChartPoint, float]]:
    return [(point, value) for point, value in zip(spec.points, values, strict=True) if point.fact_id.startswith(prefix)]


def render_charts(
    manifest: Manifest,
    specs: list[ChartSpec],
    output_dir: str | Path,
    locale: str = "en",
    write_manifest: bool = True,
) -> dict[str, dict]:
    output = Path(output_dir); output.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.family"] = "Malgun Gothic" if locale == "ko" else "Noto Sans"
    plt.rcParams["axes.unicode_minus"] = False
    chart_manifest: dict[str, dict] = {}
    for spec in specs:
        values, refs = _values(manifest, spec)
        figure, axis = plt.subplots(figsize=(7.2, 3.8), dpi=120)
        figure.patch.set_facecolor(COLORS["paper"]); axis.set_facecolor(COLORS["paper"])
        if spec.chart_type == "heatmap":
            if spec.placeholder_slots:
                axis.text(.5, .5, "UNAVAILABLE", ha="center", va="center", color=COLORS["gray_dark"], fontsize=14); axis.set_xticks([]); axis.set_yticks([])
            else:
                matrix = [values[index:index + 5] for index in range(0, 25, 5)]
                image = axis.imshow(matrix, cmap="Blues", aspect="auto")
                offsets = ["-4%p", "-2%p", "0%p", "+2%p", "+4%p"]
                axis.set_xticks(range(5), offsets); axis.set_yticks(range(5), offsets)
                axis.add_patch(plt.Rectangle((1.5, 1.5), 1, 1, fill=False, edgecolor=COLORS["warning"], linewidth=2))
                for row in range(5):
                    for column in range(5):
                        axis.text(column, row, f"{matrix[row][column]:.1f}x", ha="center", va="center", fontsize=7)
                figure.colorbar(image, ax=axis, fraction=.045, pad=.03)
        elif spec.chart_type == "bar_line":
            revenue = _series(spec, values, "is.revenue."); periods = [point.label for point, _ in revenue] + (["FQ4-26"] if spec.placeholder_slots else [])
            axis.bar(periods, [value for _, value in revenue] + ([0] if spec.placeholder_slots else []), color=COLORS["blue_pale"], label=spec.series_labels[0])
            margin_axis = axis.twinx()
            for prefix, label, color, style in (("ratio.gross_margin.", spec.series_labels[1], COLORS["primary"], "-"), ("ratio.operating_margin.", spec.series_labels[2], COLORS["warning"], "--")):
                margin_axis.plot(periods[:-1] if spec.placeholder_slots else periods, [value for _, value in _series(spec, values, prefix)], label=label, color=color, linestyle=style, marker="o")
            if spec.placeholder_slots:
                axis.text(len(periods) - 1, 0, "UNAVAILABLE", rotation=90, va="bottom", ha="center", fontsize=7)
            handles, labels = axis.get_legend_handles_labels(); other_h, other_l = margin_axis.get_legend_handles_labels()
            axis.legend(handles + other_h, labels + other_l, frameon=False, ncols=3, fontsize=7, loc="upper left")
        elif spec.chart_type == "stacked_bar":
            periods = list(dict.fromkeys(point.label for point in spec.points)) + (["FQ4-26"] if spec.placeholder_slots else []); units = list(dict.fromkeys(point.fact_id.split(".")[2] for point in spec.points)); bottoms = [0.0] * len(periods)
            for unit, label, color in zip(units, spec.series_labels, (COLORS["primary"], COLORS["warning"], COLORS["blue_mid"], COLORS["gray_dark"]), strict=True):
                series = [value for point, value in zip(spec.points, values, strict=True) if point.fact_id.split(".")[2] == unit] + ([0] if spec.placeholder_slots else [])
                axis.bar(periods, series, bottom=bottoms, label=label, color=color); bottoms = [bottom + value for bottom, value in zip(bottoms, series, strict=True)]
            if spec.placeholder_slots:
                axis.text(len(periods) - 1, 0, "UNAVAILABLE", rotation=90, va="bottom", ha="center", fontsize=7)
            axis.legend(frameon=False, ncols=4, fontsize=7)
        elif spec.chart_type == "guidance_actual":
            periods = [point.label for point, _ in _series(spec, values, "guidance.gm_gaap.")] + (["FQ4-26"] if spec.placeholder_slots else [])
            for prefix, label, color, style in (("guidance.gm_gaap.", spec.series_labels[0], COLORS["gray_dark"], "--"), ("actual.gm_gaap.", spec.series_labels[1], COLORS["primary"], "-")):
                axis.plot(periods[:-1] if spec.placeholder_slots else periods, [value for _, value in _series(spec, values, prefix)], label=label, color=color, linestyle=style, marker="o")
            if spec.placeholder_slots:
                axis.text(len(periods) - 1, 0, "UNAVAILABLE", rotation=90, va="bottom", ha="center", fontsize=7)
            axis.legend(frameon=False, fontsize=7)
        elif spec.chart_type == "two_panel":
            figure.clear(); top, bottom = figure.subplots(2, 1, sharex=True); revenue = _series(spec, values, "beat.revenue_pct."); eps = _series(spec, values, "beat.eps_gaap_usd."); periods = [point.label for point, _ in revenue] + (["FQ4-26"] if spec.placeholder_slots else [])
            top.bar(periods, [value for _, value in revenue] + ([0] if spec.placeholder_slots else []), color=COLORS["primary"], label=spec.series_labels[0]); bottom.bar([point.label for point, _ in eps], [value for _, value in eps], color=COLORS["warning"], label=spec.series_labels[1])
            if spec.placeholder_slots:
                top.text(len(periods) - 1, 0, "UNAVAILABLE", rotation=90, va="bottom", ha="center", fontsize=7)
            for panel in (top, bottom): panel.legend(frameon=False, fontsize=7); panel.grid(axis="y", alpha=.2); panel.spines[["top", "right"]].set_visible(False)
            top.set_ylabel("%"); bottom.set_ylabel("USD per share"); bottom.set_xlabel(spec.ui_text[1])
            axis = top
        elif spec.chart_type == "fan":
            anchor = values[0]
            if spec.placeholder_slots:
                for value, label, color, style in zip(values[1:], spec.series_labels[1:4], (COLORS["gray_dark"], COLORS["primary"], COLORS["warning"]), ("--", "-", ":"), strict=True): axis.plot(["FQ3-26 A", "FQ4-26 PREREG_A"], [anchor, value], label=label, color=color, linestyle=style, marker="o")
                axis.axvspan(1.05, 4, color=COLORS["gray_pale"]); axis.text(2.4, min(values[1:]), "UNAVAILABLE · RLE FY27", ha="center", fontsize=8); axis.set_xlim(-.1, 4)
            else:
                periods = ["FQ4-26 A", "FQ1-27E", "FQ2-27E", "FQ3-27E", "FQ4-27E"]
                for scenario, label, color, style in zip(("bear", "base", "bull"), spec.series_labels[1:4], (COLORS["gray_dark"], COLORS["primary"], COLORS["warning"]), ("--", "-", ":"), strict=True):
                    scenario_values = [value for point, value in zip(spec.points, values, strict=True) if f".{scenario}" in point.fact_id]
                    axis.plot(periods, [anchor, *scenario_values], label=label, color=color, linestyle=style, marker="o")
            axis.legend(frameon=False, fontsize=7)
        elif spec.chart_type == "grouped_bar":
            periods = ["FY23A", "FY24A", "FY25A", "FY26E PREREG_A", "FY26A A-8K", "FY27E", "FY28E"]; width = .24
            for offset, (prefix, label, color) in enumerate((("is.revenue.", spec.series_labels[0], COLORS["primary"]), ("is.operating_income.", spec.series_labels[1], COLORS["blue_mid"]), ("is.net_income.", spec.series_labels[2], COLORS["warning"]))):
                mapping = {}
                for point, value in _series(spec, values, prefix):
                    key = "FY26E PREREG_A" if "FY2026E.PREREG_A" in point.fact_id else "FY26A A-8K" if "FY2026A.A-8K" in point.fact_id else "FY27E" if "FY2027E.base" in point.fact_id else "FY28E" if "FY2028E.base" in point.fact_id else f"FY{re.search(r'FY(\d{4})', point.fact_id).group(1)[2:]}A"
                    mapping[key] = value
                series = [mapping.get(key, 0) for key in periods]
                axis.bar([index + (offset - 1) * width for index in range(len(periods))], series, width=width, label=label, color=color)
            axis.set_xticks(range(len(periods)), periods)
            if spec.placeholder_slots:
                for index in (4, 5, 6): axis.text(index, 0, "UNAVAILABLE", rotation=90, va="bottom", ha="center", fontsize=6)
            axis.text(3, 0, "53w", ha="center", va="bottom", fontsize=7); axis.text(4, 0, "53w", ha="center", va="bottom", fontsize=7); axis.legend(frameon=False, fontsize=7, ncols=3)
        elif spec.chart_type == "multi_series":
            periods = ["FY23A", "FY24A", "FY25A", "FY26A A-8K", "FY27E", "FY28E"]
            width = .24
            for offset, (prefix, label, color) in enumerate((("cf.fcf_adjusted.", spec.series_labels[0], COLORS["primary"]), ("cf.net_capex.", spec.series_labels[1], COLORS["warning"]), ("bs.net_cash_unadjusted.", spec.series_labels[2], COLORS["gray_dark"]))):
                rows = _series(spec, values, prefix)
                mapping = {int(re.search(r"FY(\d{4})", point.fact_id).group(1)): value for point, value in rows}
                series = [mapping.get(year, 0) for year in (2023, 2024, 2025, 2026, 2027, 2028)]
                axis.bar([index + (offset - 1) * width for index in range(len(periods))], series, width=width, label=label, color=color)
            axis.set_xticks(range(len(periods)), periods); axis.legend(frameon=False, fontsize=7, ncols=3)
            if spec.placeholder_slots:
                for index in (3, 4, 5): axis.text(index, 0, "UNAVAILABLE", rotation=90, va="bottom", ha="center", fontsize=6)
        else:
            axis.plot([point.label for point in spec.points], values, marker="o", color=COLORS["primary"])
        title = spec.title
        if spec.chart_id == "08_cash_flow_capex_net_cash" and locale == "en":
            from textwrap import fill

            title = fill(title, width=70)
        axis.set_title(title, loc="left", color=COLORS["ink"], fontweight="bold")
        if len(spec.ui_text) >= 3 and spec.chart_type != "two_panel":
            axis.set_xlabel(spec.ui_text[1]); axis.set_ylabel(spec.ui_text[2])
        axis.spines[["top", "right"]].set_visible(False); axis.grid(axis="y", alpha=.2)
        if spec.chart_type != "heatmap":
            axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
        axis.tick_params(axis="x", labelrotation=38, labelsize=7); plt.setp(axis.get_xticklabels(), ha="right"); figure.tight_layout()
        path = output / f"{spec.chart_id}_{locale}.png"; temporary = path.with_name(f".{path.stem}.tmp.png")
        try:
            figure.savefig(temporary, metadata={"Software": "MU report builder", "Creation Time": ""}); os.replace(temporary, path)
        finally:
            plt.close(figure)
            if temporary.exists(): temporary.unlink()
        sources = sorted({manifest.fact(fact_id).source_id for fact_id in refs})
        if len(sources) > 4:
            grouped: dict[str, int] = {}
            for source in sources:
                family = source.rsplit("-", 1)[0] if re.search(r"-[0-9a-f]{12}$", source) else source
                grouped[family] = grouped.get(family, 0) + 1
            sources = [f"{family}×{count}" if count > 1 else family for family, count in sorted(grouped.items())]
        source = spec.source_label + (" [" + ", ".join(sources) + "]" if sources else "")
        caption = {"number": spec.figure_number, "title": spec.ui_text[0] if spec.ui_text else spec.title, "unit": spec.unit, "source": source, "as_of": spec.source_as_of, "basis": spec.basis}
        series_periods = {
            family: [manifest.fact(fact_id).period for fact_id in refs if fact_id.startswith(family)]
            for family in spec.allowed_families
        }
        chart_manifest[spec.chart_id] = {"path": path.name, "fact_ids": refs, "values": values, "periods": [manifest.fact(fact_id).period for fact_id in refs], "series_periods": series_periods, "source_as_of": spec.source_as_of, "chart_type": spec.chart_type, "series_count": spec.series_count, "allowed_families": list(spec.allowed_families), "placeholder_slots": list(spec.placeholder_slots), "caption": caption, "ui_text": list(spec.ui_text), "locale": locale}
    if write_manifest:
        atomic_write(output / f"chart_manifest_{locale}.json", (json.dumps(chart_manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        if locale == "en":
            atomic_write(output / "chart_manifest.json", (json.dumps(chart_manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return chart_manifest
