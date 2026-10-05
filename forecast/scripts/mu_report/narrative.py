"""E2-B narrative loading, source recomputation, binding, and section assembly."""

from __future__ import annotations

import hashlib
import html
import re
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .facts import Fact, Manifest, Source, dryrun_manifest_from_extracts
from .rle import ReportLayerAssumptions, annual_rle_results, fy2027_scenario_results, load_assumptions_text, margin_bridge
from .valuation import implied_valuation, trailing_pb

FACT_TOKEN = re.compile(r"\{\{fact:([^}]+)}}")


def load_narrative_text(text: str) -> dict[str, Any]:
    narrative = yaml.safe_load(text)
    if not isinstance(narrative, dict):
        raise ValueError("narrative must be a mapping")
    return narrative


def _row_first_number(table: pd.DataFrame, label: str) -> float:
    rows = table[table.iloc[:, 0].astype(str).str.strip().str.casefold() == label.casefold()]
    if len(rows) != 1:
        raise ValueError(f"source row must occur exactly once: {label}")
    for cell in rows.iloc[0, 3:]:
        if isinstance(cell, (int, float)) and not pd.isna(cell):
            return float(cell)
        match = re.fullmatch(r"\(?\$?([\d,.]+)\)?", str(cell).strip())
        if match:
            return float(match.group(1).replace(",", ""))
    raise ValueError(f"source row has no numeric value: {label}")


def _ex991_values(text: str) -> dict[str, float]:
    tables = pd.read_html(StringIO(text))
    quarterly = next(table for table in tables if "Quarterly Financial Results" in " ".join(map(str, table.iloc[1].tolist())))
    outlook = next(table for table in tables if "GAAP(1) Outlook" in " ".join(map(str, table.astype(str).values.flatten())))
    balance = next(table for table in tables if "Noncurrent customer contract liabilities" in set(table.iloc[:, 0].astype(str)))
    outlook_text = " ".join(map(str, outlook.astype(str).values.flatten()))
    guidance = re.search(r"\$(\d+(?:\.\d+)?) billion\s*[±�]\s*\$(\d+(?:\.\d+)?) billion", outlook_text)
    if not guidance:
        raise ValueError("FQ1 revenue guidance was not found in ex991.htm")
    plain = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())
    dividend = re.search(r"declared a quarterly dividend of \$(\d+(?:\.\d+)?) per share", plain)
    if not dividend:
        raise ValueError("declared dividend was not found in ex991.htm")
    midpoint = float(guidance.group(1)) * 1000.0
    half_range = float(guidance.group(2)) * 1000.0
    def outlook_cell(label: str, column: int) -> str:
        rows = outlook[outlook.iloc[:, 0].astype(str).str.strip() == label]
        if len(rows) != 1:
            raise ValueError(f"FQ1 outlook row must occur exactly once: {label}")
        return str(rows.iloc[0, column])

    def outlook_number(label: str, column: int, scale: float = 1.0) -> float:
        match = re.search(r"[-+]?\$?([\d.]+)", outlook_cell(label, column))
        if not match:
            raise ValueError(f"FQ1 outlook value was not found: {label}/{column}")
        return float(match.group(1)) * scale

    guidance_shares = re.search(r"approximately\s+([\d.]+)\s*billion diluted shares", plain, re.I)
    if not guidance_shares:
        raise ValueError("FQ1 guidance diluted shares were not found in ex991.htm")
    return {
        "guidance_mid": midpoint,
        "guidance_low": midpoint - half_range,
        "guidance_revenue_tolerance": half_range,
        "fq4_revenue": _row_first_number(quarterly, "Revenue"),
        "fq4_opex": _row_first_number(quarterly, "Operating expenses"),
        "fq4_eps": _row_first_number(quarterly, "Diluted earnings per share"),
        "customer_contract_liabilities": _row_first_number(balance, "Noncurrent customer contract liabilities"),
        "dividend_dps": float(dividend.group(1)),
        "guidance_gm_gaap": outlook_number("Gross margin", 3),
        "guidance_gm_nongaap": outlook_number("Gross margin", 6),
        "guidance_opex_gaap": outlook_number("Operating expenses", 3, 1000.0),
        "guidance_opex_nongaap": outlook_number("Operating expenses", 6, 1000.0),
        "guidance_eps_gaap": outlook_number("Diluted earnings per share", 3),
        "guidance_eps_nongaap": outlook_number("Diluted earnings per share", 6),
        "guidance_eps_tolerance": float(re.findall(r"\$([\d.]+)", outlook_cell("Diluted earnings per share", 3))[1]),
        "guidance_shares": float(guidance_shares.group(1)) * 1000.0,
    }


def _remarks_values(text: str) -> dict[str, str]:
    plain = " ".join(text.split())
    required = {
        "dram_bits": "mid-single-digit percentage range",
        "dram_pricing": "high-teens percentage range",
        "nand_bits": "approximately 10%",
        "nand_pricing": "approximately 30%",
    }
    missing = [value for value in required.values() if value not in plain]
    if missing:
        raise ValueError(f"FQ4 prepared-remarks categories were not found: {missing}")
    return required


def _scored_values(text: str) -> dict[str, float | str]:
    cleaned = text.replace("**", "")
    rows: dict[str, list[list[str]]] = {}
    for line in cleaned.splitlines():
        if line.strip().startswith("|"):
            cells = [cell.strip().replace("`", "") for cell in line.strip().strip("|").split("|")]
            if cells:
                rows.setdefault(cells[0], []).append(cells[1:])

    def scored_row(label: str) -> list[str]:
        return next((row for row in rows.get(label, []) if len(row) >= 4), [])

    def lever_row(label: str) -> list[str]:
        return next((row for row in rows.get(label, []) if len(row) == 2), [])

    def number(value: str) -> float:
        normalized = value.replace("−", "-")
        match = re.search(r"[-+]?\$?([\d,]+(?:\.\d+)?)", normalized)
        if not match:
            raise ValueError(f"SCORED numeric value was not found: {value}")
        sign = -1.0 if match.group(0).startswith("-") else 1.0
        return sign * float(match.group(1).replace(",", ""))

    required = ("매출", "GAAP 희석 EPS", "비GAAP 희석 EPS", "GAAP opex")
    if any(not scored_row(key) for key in required):
        raise ValueError("required SCORED rows were not found")
    revenue, eps, nongaap, opex = (scored_row(key) for key in required)
    band = re.search(r"밴드 커버리지\s+PASS.*?매출\s*∈\s*\[([\d,]+),\s*([\d,]+)]\s*·\s*GAAP EPS\s*∈\s*\[([\d.]+),\s*([\d.]+)]", cleaned)
    if not band:
        raise ValueError("SCORED band coverage was not found")
    return {
        "revenue_actual": number(revenue[0]), "revenue_forecast": number(revenue[1]),
        "revenue_error": number(revenue[2]), "revenue_ape": number(revenue[3]) / 100.0,
        "eps_actual": number(eps[0]), "eps_forecast": number(eps[1]),
        "eps_error": number(eps[2]), "eps_ape": number(eps[3]) / 100.0,
        "nongaap_eps_actual": number(nongaap[0]), "nongaap_eps_forecast": number(nongaap[1]),
        "nongaap_eps_error": number(nongaap[2]), "nongaap_eps_ape": number(nongaap[3]) / 100.0,
        "opex_actual": number(opex[0]), "opex_forecast": number(opex[1]),
        "opex_error": number(opex[2]), "opex_ape": number(opex[3]) / 100.0,
        "band_coverage": "PASS",
        "revenue_band_low": number(band.group(1)), "revenue_band_high": number(band.group(2)),
        "eps_band_low": number(band.group(3)), "eps_band_high": number(band.group(4)),
        "lever_revenue": number(lever_row("매출")[0]), "lever_op_margin": number(lever_row("영업이익률")[0]),
        "lever_op_to_ni": number(lever_row("OP→NI 전환")[0]), "lever_shares": number(lever_row("주식수")[0]),
        "lever_total": number(lever_row("합")[0]), "labels_hit": 4.0, "sf7": "MISS",
    }


def recompute_fact_bindings(
    narrative: dict[str, Any],
    ex991_text: str,
    scored_text: str,
    assumptions: ReportLayerAssumptions,
) -> dict[str, float]:
    ex991 = _ex991_values(ex991_text)
    scored = _scored_values(scored_text)
    rle = fy2027_scenario_results(assumptions)
    values = {
        "guidance.revenue_mid.FQ1FY27": ex991["guidance_mid"],
        "guidance.revenue_lo.FQ1FY27": ex991["guidance_low"],
        "derived.weekly_growth.FQ1FY27_guide": (ex991["guidance_mid"] / 13) / (ex991["fq4_revenue"] / 14) - 1,
        "bs.customer_contract_liabilities.FQ4FY26": ex991["customer_contract_liabilities"],
        "scored.opex_gap_pct.FQ4FY26": scored["opex_actual"] / scored["opex_forecast"] - 1,
        "scored.eps_error.FQ4FY26": scored["eps_actual"] - scored["eps_forecast"],
        "rle.opex.FY27E": float(assumptions.rules["A4_gaap_opex"]["fy2027_total"]["value"]),
        "rle.revenue.FY27E.base": rle["base"]["revenue"],
        "rle.eps_gaap.FY27E.base": rle["base"]["eps_gaap"],
        "rle.eps_gaap.FY27E.bear": rle["bear"]["eps_gaap"],
        "rle.eps_gaap.FY27E.bull": rle["bull"]["eps_gaap"],
        "dividend.dps.declared_2026-09-30": ex991["dividend_dps"],
    }
    proposed = {item["token"]: float(item["value"]) for item in narrative["fact_bindings"]}
    if set(values) != set(proposed):
        raise ValueError("narrative fact_bindings do not match the recomputed fact set")
    for fact_id, value in values.items():
        precision = len(str(next(item["value"] for item in narrative["fact_bindings"] if item["token"] == fact_id)).split(".")[1]) if "." in str(next(item["value"] for item in narrative["fact_bindings"] if item["token"] == fact_id)) else 0
        tolerance = 0.5 * 10 ** (-precision)
        if abs(value - proposed[fact_id]) > tolerance:
            raise ValueError(f"narrative proposed value mismatch: {fact_id}: {proposed[fact_id]} != {value}")
    return values


def _display(fact_id: str, value: float) -> dict[str, str]:
    if fact_id in {"derived.weekly_growth.FQ1FY27_guide", "scored.opex_gap_pct.FQ4FY26"}:
        return _fact_display(value, "fraction")
    elif fact_id.startswith("guidance.revenue"):
        return _fact_display(value, "USD_million_compact")
    elif fact_id in {"bs.customer_contract_liabilities.FQ4FY26", "rle.opex.FY27E"}:
        return _fact_display(value, "USD_million_compact")
    elif fact_id == "rle.revenue.FY27E.base":
        return _fact_display(value, "USD_million_compact_2")
    elif "eps" in fact_id or fact_id.startswith("dividend."):
        return _fact_display(value, "USD_per_share")
    else:
        return _fact_display(value, "USD_million")


def _number(value: Any) -> float:
    text = str(value).strip().replace("$", "").replace(",", "")
    if text in {"—", "-", "nan"}:
        return 0.0
    negative = text.startswith("(") and text.endswith(")")
    number = float(text.strip("()"))
    return -number if negative else number


def _row_value(table: pd.DataFrame, label: str, column: int, occurrence: int = 0) -> float:
    rows = table[table.iloc[:, 0].astype(str).str.strip() == label]
    if len(rows) <= occurrence:
        raise ValueError(f"source row missing: {label}/{occurrence}")
    return _number(rows.iloc[occurrence, column])


def _fact_display(value: float | int | str, unit: str, *, signed: bool = False, precision: int | None = None, explicit: bool = False) -> dict[str, str]:
    if isinstance(value, (int, float)) and value == 0:
        value = 0.0
    if isinstance(value, str):
        rendered = value
    elif unit in {"percent", "fraction"}:
        digits = 1 if precision is None else precision
        rendered = f"{float(value) * (100 if unit == 'fraction' else 1):.{digits}f}%"
    elif unit == "percentage_points":
        rendered = f"{float(value):+.1f}%p"
    elif unit == "USD_per_share":
        sign = ("+" if float(value) >= 0 else "−") if signed else ("−" if float(value) < 0 else "")
        rendered = f"{sign}${abs(float(value)):,.2f}"
    elif unit == "multiple":
        rendered = f"{float(value):,.2f}x"
    elif unit == "date":
        rendered = str(value)
    elif unit == "million_shares":
        rendered = f"{float(value):,.0f}M"
    elif unit == "days":
        rendered = f"{float(value):,.1f}"
    elif unit == "USD_million":
        rendered = f"USD {float(value):,.0f} million" if explicit else f"{float(value):,.0f}"
    elif unit == "USD_million_compact":
        rendered = f"${float(value):,.0f}M"
    elif unit == "USD_million_compact_2":
        rendered = f"${float(value):,.2f}M"
    elif unit == "count":
        rendered = f"{int(value):,}"
    elif unit == "number":
        rendered = f"{float(value):g}"
    else:
        rendered = f"{float(value):,.2f}"
    return {"ko": rendered, "en": rendered}


def _put_fact(
    manifest: Manifest,
    fact_id: str,
    value: float | int | str,
    unit: str,
    period: str,
    basis: str,
    label: str,
    source_id: str,
    lineage: dict[str, Any] | None = None,
) -> None:
    manifest.facts[fact_id] = Fact(
        fact_id, value, _fact_display(value, unit), unit, period, basis, label, source_id,
        lineage=lineage,
    )


def _extend_e2b_manifest(
    manifest: Manifest,
    assumptions: ReportLayerAssumptions,
    ex991_text: str,
    remarks_text: str,
    scored_text: str,
    source_paths: dict[str, str],
) -> None:
    tables = pd.read_html(StringIO(ex991_text))
    ex991 = _ex991_values(ex991_text)
    remarks = _remarks_values(remarks_text)
    scored = _scored_values(scored_text)
    income, balance, cashflow, business, adjusted = tables[5], tables[6], tables[7], tables[3], tables[9]
    repo_root = Path(__file__).resolve().parents[3]
    for source_id, title, as_of in (
        ("SRC-PRICE-1", "MU 2026-10-01 Nasdaq close capture 1", "2026-10-01"),
        ("SRC-PRICE-2", "MU 2026-10-01 Nasdaq close capture 2", "2026-10-01"),
    ):
        default_name = "price_2026-10-01_src1.png" if source_id == "SRC-PRICE-1" else "price_2026-10-01_src2.png"
        path = source_paths.get(source_id, f"logs/mu/fy2026q4/postprint/{default_name}")
        manifest.sources[source_id] = Source(
            source_id, title, path, hashlib.sha256((repo_root / path).read_bytes()).hexdigest(), as_of,
        )
    qualitative_ko = {
        "qual.dram.bit_shipments.FQ3-26.CITED": "한 자릿수 초반 비율 범위",
        "qual.dram.pricing.FQ3-26.CITED": "60대 초반 비율 범위, 타이트한 업황과 유리한 믹스가 주도",
        "qual.nand.bit_shipments.FQ3-26.CITED": "한 자릿수 중반 비율 범위",
        "qual.nand.pricing.FQ3-26.CITED": "80대 중반 비율 범위, 타이트한 NAND 업황과 유리한 믹스가 주도",
    }
    for fact_id, translated in qualitative_ko.items():
        manifest.fact(fact_id).display["ko"] = translated
    qualitative_fq4 = {
        "qual.dram.bit_shipments.FQ4-26.CITED": (remarks["dram_bits"], "한 자릿수 중반 비율 상승"),
        "qual.dram.pricing.FQ4-26.CITED": (remarks["dram_pricing"], "십 퍼센트대 후반 상승"),
        "qual.nand.bit_shipments.FQ4-26.CITED": (remarks["nand_bits"], "약 10% 상승"),
        "qual.nand.pricing.FQ4-26.CITED": (remarks["nand_pricing"], "약 30% 상승"),
    }
    for fact_id, (value, translated) in qualitative_fq4.items():
        _put_fact(manifest, fact_id, value, "categorical", "FQ4-26", "CITED", fact_id, "SRC-REMARKS-FQ4FY26")
        manifest.fact(fact_id).display["ko"] = translated
        manifest.fact(fact_id).display["en"] = "↑ " + value

    income_rows = {
        "revenue": ("Revenue", 0), "cogs": ("Cost of goods sold", 0), "gross_profit": ("Gross margin", 0),
        "r_and_d": ("Research and development", 0), "sg_and_a": ("Selling, general, and administrative", 0),
        "other_operating": ("Other operating (income) expense, net", 0), "operating_income": ("Operating income", 0),
        "interest_income": ("Interest income", 0), "interest_expense": ("Interest expense", 0),
        "other_nonoperating": ("Other non-operating income (expense), net", 0), "tax": ("Income tax (provision) benefit", 0),
        "equity_method": ("Equity in net income (loss) of equity method investees", 0), "net_income": ("Net income", 0),
        "diluted_eps": ("Diluted", 0), "diluted_shares": ("Diluted", 1),
    }
    actual_income: dict[str, float] = {}
    for metric, (label, occurrence) in income_rows.items():
        value = _row_value(income, label, 13, occurrence)
        actual_income[metric] = value
        unit = "USD_per_share" if metric == "diluted_eps" else "million_shares" if metric == "diluted_shares" else "USD_million"
        _put_fact(manifest, f"is.{metric}.FY2026A.A-8K", value, unit, "FY2026", "A-8K", label, "SRC-EX991-FQ4FY26")
    actual_income["restructuring"] = 0.0
    actual_income["pretax_income"] = (
        actual_income["operating_income"] + actual_income["interest_income"] + actual_income["interest_expense"] + actual_income["other_nonoperating"]
    )
    _put_fact(manifest, "is.restructuring.FY2026A.A-8K", 0, "USD_million", "FY2026", "A-8K", "Restructuring", "SRC-EX991-FQ4FY26")
    _put_fact(
        manifest, "is.opex.FY2026A.A-8K",
        actual_income["r_and_d"] + actual_income["sg_and_a"] + actual_income["other_operating"],
        "USD_million", "FY2026", "A-8K", "Operating expenses", "SRC-EX991-FQ4FY26",
    )
    _put_fact(
        manifest, "is.below_op.FY2026A.A-8K",
        actual_income["interest_income"] + actual_income["interest_expense"] + actual_income["other_nonoperating"],
        "USD_million", "FY2026", "CALCULATED", "Below-operating items", "SRC-EX991-FQ4FY26",
        {"formula": "below_op_v1", "inputs": ["is.interest_income.FY2026A.A-8K", "is.interest_expense.FY2026A.A-8K", "is.other_nonoperating.FY2026A.A-8K"]},
    )
    _put_fact(
        manifest, "is.pretax_income.FY2026A.A-8K", actual_income["pretax_income"], "USD_million", "FY2026", "CALCULATED",
        "Pretax income", "SRC-EX991-FQ4FY26",
        {"formula": "pretax_from_components_v1", "inputs": [
            "is.operating_income.FY2026A.A-8K", "is.interest_income.FY2026A.A-8K",
            "is.interest_expense.FY2026A.A-8K", "is.other_nonoperating.FY2026A.A-8K",
        ]},
    )

    balance_rows = {
        "cash": "Cash and equivalents", "short_term_investments": "Short-term investments", "receivables": "Receivables",
        "inventories": "Inventories", "total_current_assets": "Total current assets",
        "long_term_investments": "Long-term marketable investments", "ppe": "Property, plant, and equipment",
        "total_assets": "Total assets", "accounts_payable_accrued": "Accounts payable and accrued expenses",
        "current_debt": "Current debt", "total_current_liabilities": "Total current liabilities",
        "long_term_debt": "Long-term debt", "total_liabilities": "Total liabilities", "total_equity": "Total equity",
    }
    actual_balance: dict[str, float] = {}
    for metric, label in balance_rows.items():
        value = _row_value(balance, label, 4)
        actual_balance[metric] = value
        _put_fact(manifest, f"bs.{metric}.FY2026.A-8K", value, "USD_million", "FY2026", "A-8K", label, "SRC-EX991-FQ4FY26")
    _put_fact(manifest, "meta.fiscal_year_end.FY2026.A-8K", "2026-09-03", "date", "FY2026", "A-8K", "Fiscal year end", "SRC-EX991-FQ4FY26")
    _put_fact(manifest, "meta.equity_date.FY2026.A-8K", "2026-09-03", "date", "FY2026", "A-8K", "Equity date", "SRC-EX991-FQ4FY26")
    _put_fact(manifest, "meta.period_weeks.FY2026.A-8K", 53, "weeks", "FY2026", "A-8K", "Fiscal period weeks", "SRC-EX991-FQ4FY26")

    cash_rows = {
        "net_income": "Net income", "d_and_a": "Depreciation expense and amortization of intangible assets",
        "sbc": "Stock-based compensation", "receivables_change": "Receivables", "inventories_change": "Inventories",
        "accounts_payable_change": "Accounts payable and accrued expenses", "other_current_liabilities_change": "Other current liabilities",
        "operating_cash_flow": "Net cash provided by operating activities", "ppe_expenditures": "Expenditures for property, plant, and equipment",
        "government_incentives": "Proceeds from government incentives", "investing_cash_flow": "Net cash used for investing activities",
        "debt_repayments": "Repayments of debt", "debt_issuance": "Proceeds from issuance of debt",
        "dividends": "Payments of dividends to shareholders", "financing_cash_flow": "Net cash provided by (used for) financing activities",
        "fx_effect": "Effect of changes in currency exchange rates on cash, cash equivalents, and restricted cash",
        "cash_change": "Net increase in cash, cash equivalents, and restricted cash",
    }
    actual_cash: dict[str, float] = {}
    for metric, label in cash_rows.items():
        value = _row_value(cashflow, label, 4)
        actual_cash[metric] = value
        _put_fact(manifest, f"cf.{metric}.FY2026A", value, "USD_million", "FY2026", "A-8K", label, "SRC-EX991-FQ4FY26")
    disposal = _row_value(adjusted, "Proceeds from sales of property, plant, and equipment", 13)
    net_capex = abs(_row_value(adjusted, "Investments in capital expenditures, net", 13))
    fcf = _row_value(adjusted, "Adjusted free cash flow", 13)
    repurchase_withholding = _row_value(cashflow, "Repurchases of common stock - withholdings on employee equity awards", 4)
    repurchase_program = _row_value(cashflow, "Repurchases of common stock - repurchase program", 4)
    for metric, value, label in (
        ("ppe_disposal_proceeds", disposal, "PPE disposal proceeds"), ("net_capex", net_capex, "Net capital expenditures"),
        ("fcf_adjusted", fcf, "Adjusted free cash flow"), ("share_repurchases", repurchase_withholding + repurchase_program, "Share repurchases"),
    ):
        _put_fact(manifest, f"cf.{metric}.FY2026A", value, "USD_million", "FY2026", "A-8K", label, "SRC-EX991-FQ4FY26")

    fq4_revenue = _row_value(income, "Revenue", 4)
    fq4_gross = _row_value(income, "Gross margin", 4)
    fq4_op = _row_value(income, "Operating income", 4)
    fq4_eps = _row_value(income, "Diluted", 4, 0)
    fq4_shares = _row_value(income, "Diluted", 4, 1)
    for fact_id, value, unit, label in (
        ("is.revenue.FY2026Q4.A-8K", fq4_revenue, "USD_million", "Revenue"),
        ("is.revenue.FY2026Q4.A", fq4_revenue, "USD_million", "Revenue"),
        ("is.eps_gaap.FY2026Q4.A-8K", fq4_eps, "USD_per_share", "GAAP diluted EPS"),
        ("is.diluted_shares.FY2026Q4.A-8K", fq4_shares, "million_shares", "Diluted shares"),
    ):
        _put_fact(manifest, fact_id, value, unit, "FY2026Q4", "A-8K", label, "SRC-EX991-FQ4FY26")
    for metric, numerator in (("gross", fq4_gross), ("operating", fq4_op)):
        value = numerator / fq4_revenue * 100
        _put_fact(
            manifest, f"ratio.{metric}_margin.FY2026Q4.A", value, "percent", "FY2026Q4", "CALCULATED",
            f"{metric.title()} margin", "SRC-EX991-FQ4FY26",
            {"formula": "margin_v1", "inputs": [f"is.{('gross_profit' if metric == 'gross' else 'operating_income')}.FY2026A.A-8K", "is.revenue.FY2026Q4.A-8K"]},
        )
        _put_fact(
            manifest, f"is.{metric}_margin.FY2026Q4.A-8K", value / 100.0, "fraction", "FY2026Q4", "CALCULATED",
            f"{metric.title()} margin", "SRC-EX991-FQ4FY26",
            {"formula": "margin_v1", "inputs": ["is.revenue.FY2026Q4.A-8K"]},
        )
    fq3_revenue = float(manifest.fact("is.revenue.FY2026Q3.A").raw_value)
    fq3_gross = float(manifest.fact("is.gross_profit.FY2026Q3.A").raw_value)
    fq3_op = float(manifest.fact("is.operating_income.FY2026Q3.A").raw_value)
    fq3_opex = fq3_gross - fq3_op
    fq4_opex = fq4_gross - fq4_op
    for fact_id, value, period, label, inputs in (
        ("is.opex.FY2026Q3.A", fq3_opex, "FY2026Q3", "GAAP operating expenses", ["is.gross_profit.FY2026Q3.A", "is.operating_income.FY2026Q3.A"]),
        ("is.opex.FY2026Q4.A-8K", fq4_opex, "FY2026Q4", "GAAP operating expenses", ["is.revenue.FY2026Q4.A-8K"]),
    ):
        _put_fact(manifest, fact_id, value, "USD_million", period, "CALCULATED", label, "SRC-EX991-FQ4FY26", {"formula": "gross_profit_minus_operating_income_v1", "inputs": inputs})
    for unit, row_label in (("CMBU", "Cloud Memory Business Unit"), ("CDBU", "Core Data Center Business Unit"), ("MCBU", "Mobile and Client Business Unit"), ("AEBU", "Automotive and Embedded Business Unit")):
        rows = business[business.iloc[:, 0].astype(str).str.strip() == row_label]
        row_index = rows.index[0] + 1
        value = _number(business.iloc[row_index, 4])
        _put_fact(manifest, f"bu.revenue.{unit}.FQ4-26.A", value, "USD_million", "FQ4-26", "A-8K", row_label, "SRC-EX991-FQ4FY26")

    price, shares = 1097.39, fq4_shares
    _put_fact(manifest, "market.price.2026-10-01.CITED", price, "USD_per_share", "2026-10-01", "CITED", "Reference share price", "SRC-PRICE-1")
    _put_fact(manifest, "market.shares_outstanding.CITED", shares, "million_shares", "FY2026Q4", "CITED", "FQ4 diluted weighted-average shares", "SRC-EX991-FQ4FY26")
    _put_fact(manifest, "meta.price_date.2026-10-01.CITED", "2026-10-01", "date", "2026-10-01", "CITED", "Price date", "SRC-PRICE-1")
    _put_fact(manifest, "meta.shares_date.CITED", "2026-09-03", "date", "2026-09-03", "CITED", "Shares date", "SRC-EX991-FQ4FY26")
    market_cap = price * shares
    _put_fact(
        manifest, "market.market_cap.2026-10-01.CALCULATED", market_cap, "USD_million", "2026-10-01", "CALCULATED",
        "Market capitalization", "SRC-PRICE-1", {"formula": "market_cap_v1", "inputs": ["market.price.2026-10-01.CITED", "market.shares_outstanding.CITED"]},
    )
    manifest.fact("market.market_cap.2026-10-01.CALCULATED").display.update(_fact_display(market_cap, "USD_million", explicit=True))
    pb = trailing_pb(price, actual_balance["total_equity"], shares)
    _put_fact(
        manifest, "val.pb_trailing.FY2026.A-8K", float(pb), "multiple", "FY2026", "CALCULATED", "Trailing P/B", "SRC-PRICE-1",
        {"formula": "trailing_pb_v1", "inputs": ["market.price.2026-10-01.CITED", "bs.total_equity.FY2026.A-8K", "market.shares_outstanding.CITED"]},
    )

    net_cash = actual_balance["cash"] + actual_balance["short_term_investments"] + actual_balance["long_term_investments"] - actual_balance["current_debt"] - actual_balance["long_term_debt"]
    _put_fact(
        manifest, "bs.net_cash_unadjusted.FY2026.A-8K", net_cash, "USD_million", "FY2026", "CALCULATED",
        "Net cash (not adjusted for SCA deposits)", "SRC-EX991-FQ4FY26", {"formula": "net_cash_unadjusted_v1", "inputs": [
            "bs.cash.FY2026.A-8K", "bs.short_term_investments.FY2026.A-8K", "bs.long_term_investments.FY2026.A-8K",
            "bs.current_debt.FY2026.A-8K", "bs.long_term_debt.FY2026.A-8K",
        ]},
    )
    sca_deposits = 12895.0
    _put_fact(manifest, "bs.sca_customer_deposits.FY2026Q4", sca_deposits, "USD_million", "FY2026Q4", "A-8K", "SCA customer deposits", "SRC-EX991-FQ4FY26")
    _put_fact(
        manifest, "bs.net_cash_ex_sca.FY2026Q4", net_cash - sca_deposits, "USD_million", "FY2026Q4", "CALCULATED",
        "Net cash excluding SCA", "SRC-EX991-FQ4FY26",
        {"formula": "net_cash_ex_sca_v1", "inputs": ["bs.net_cash_unadjusted.FY2026.A-8K", "bs.sca_customer_deposits.FY2026Q4"]},
    )
    _put_fact(
        manifest, "valuation.ev_adj.FY2026Q4", market_cap - (net_cash - sca_deposits), "USD_million", "FY2026Q4", "CALCULATED",
        "Adjusted EV", "SRC-PRICE-1",
        {"formula": "sca_adjusted_ev_v1", "inputs": ["market.market_cap.2026-10-01.CALCULATED", "bs.net_cash_unadjusted.FY2026.A-8K", "bs.sca_customer_deposits.FY2026Q4"]},
    )
    inventory_days_value = (
        (float(manifest.fact("bs.inventories.FY2025A").raw_value) + actual_balance["inventories"]) / 2.0
    ) / actual_income["cogs"] * 371
    actual_ratios = {
        "gross_margin": actual_income["gross_profit"] / actual_income["revenue"],
        "operating_margin": actual_income["operating_income"] / actual_income["revenue"],
        "etr": -actual_income["tax"] / actual_income["pretax_income"],
        "roe": actual_income["net_income"] / ((54165.0 + actual_balance["total_equity"]) / 2.0),
        "inventory_days": inventory_days_value,
        "net_capex_revenue": net_capex / actual_income["revenue"],
    }
    for metric, value in actual_ratios.items():
        unit = "days" if metric == "inventory_days" else "fraction"
        lineage_inputs = (
            ["bs.inventories.FY2025A", "bs.inventories.FY2026.A-8K", "is.cogs.FY2026A.A-8K", "meta.period_weeks.FY2026.A-8K"]
            if metric == "inventory_days" else ["is.revenue.FY2026A.A-8K"]
        )
        _put_fact(
            manifest, f"ratio.{metric}.FY2026.A-8K", value, unit, "FY2026", "CALCULATED", metric.replace("_", " ").title(),
            "SRC-EX991-FQ4FY26", {"formula": f"{metric}_v1", "inputs": lineage_inputs},
        )

    rle = annual_rle_results(assumptions)
    income_keys = ("revenue", "cogs", "gross_profit", "opex", "operating_income", "below_op", "pretax", "tax", "net_income", "diluted_shares", "diluted_eps")
    cash_keys = ("d_and_a", "sbc", "working_capital_investment", "operating_cash_flow", "net_capex", "fcf_adjusted", "dividends")
    for scenario, years in rle.items():
        for year, values in years.items():
            period = f"FY{year}E"
            for metric in income_keys:
                unit = "USD_per_share" if metric == "diluted_eps" else "million_shares" if metric == "diluted_shares" else "USD_million"
                presentation_value = -values[metric] if metric == "tax" else values[metric]
                _put_fact(manifest, f"is.{metric}.{period}.{scenario}", presentation_value, unit, period, "RLE", metric.replace("_", " ").title(), "SRC-RLE-FY27")
            for metric, ratio_value in (
                ("gross_margin", values["gross_margin"]), ("operating_margin", values["operating_margin"]),
                ("etr", values["etr"]), ("net_capex_revenue", values["net_capex"] / values["revenue"]),
            ):
                _put_fact(manifest, f"ratio.{metric}.{period}.{scenario}", ratio_value, "fraction", period, "RLE", metric.replace("_", " ").title(), "SRC-RLE-FY27")
            for metric in cash_keys:
                presentation_value = -values[metric] if metric in {"working_capital_investment", "dividends"} else values[metric]
                _put_fact(manifest, f"cf.{metric}.{period}.{scenario}", presentation_value, "USD_million", period, "RLE", metric.replace("_", " ").title(), "SRC-RLE-FY27")
            _put_fact(manifest, f"bs.net_cash_unadjusted.{period}.{scenario}", values["net_cash_unadjusted"], "USD_million", period, "RLE", "Net cash (not adjusted for SCA deposits)", "SRC-RLE-FY27")
        for quarter, revenue in enumerate(years[2027]["quarterly_revenue"], start=1):
            _put_fact(manifest, f"rle.revenue.FY2027Q{quarter}.{scenario}", revenue, "USD_million", f"FY2027Q{quarter}", "RLE", f"{scenario.title()} revenue", "SRC-RLE-FY27")

    for metric, value, unit, label in (
        ("guidance.gm_gaap.FQ4-26.CITED", 86.0, "percent", "GAAP GM guidance midpoint"),
        ("actual.gm_gaap.FQ4-26.CITED", fq4_gross / fq4_revenue * 100, "percent", "Actual GAAP GM"),
        ("beat.revenue_pct.FQ4-26.CITED", fq4_revenue / 50000.0 * 100 - 100, "percent", "Revenue versus guidance midpoint"),
        ("beat.eps_gaap_usd.FQ4-26.CITED", fq4_eps - 31.73, "USD_per_share", "GAAP EPS versus guidance high"),
    ):
        _put_fact(manifest, metric, value, unit, "FQ4-26", "SCORED", label, "SRC-SCORED-FQ4FY26")

    scored_facts = {
        "scored.revenue_actual.FQ4FY26": (scored["revenue_actual"], "USD_million"), "scored.revenue_forecast.FQ4FY26": (scored["revenue_forecast"], "USD_million"),
        "scored.revenue_error.FQ4FY26": (scored["revenue_error"], "USD_million"), "scored.revenue_ape.FQ4FY26": (scored["revenue_ape"], "fraction"),
        "scored.revenue_band_low.FQ4FY26": (scored["revenue_band_low"], "USD_million"), "scored.revenue_band_high.FQ4FY26": (scored["revenue_band_high"], "USD_million"),
        "scored.eps_ape.FQ4FY26": (scored["eps_ape"], "fraction"), "scored.eps_band_low.FQ4FY26": (scored["eps_band_low"], "USD_per_share"),
        "scored.eps_band_high.FQ4FY26": (scored["eps_band_high"], "USD_per_share"),
        "scored.nongaap_eps_actual.FQ4FY26": (scored["nongaap_eps_actual"], "USD_per_share"), "scored.nongaap_eps_forecast.FQ4FY26": (scored["nongaap_eps_forecast"], "USD_per_share"),
        "scored.nongaap_eps_error.FQ4FY26": (scored["nongaap_eps_error"], "USD_per_share"), "scored.nongaap_eps_ape.FQ4FY26": (scored["nongaap_eps_ape"], "fraction"),
        "scored.opex_error.FQ4FY26": (scored["opex_error"], "USD_million"), "scored.opex_ape.FQ4FY26": (scored["opex_ape"], "fraction"),
        "scored.lever.revenue.FQ4FY26": (scored["lever_revenue"], "USD_per_share"), "scored.lever.op_margin.FQ4FY26": (scored["lever_op_margin"], "USD_per_share"),
        "scored.lever.op_to_ni.FQ4FY26": (scored["lever_op_to_ni"], "USD_per_share"), "scored.lever.shares.FQ4FY26": (scored["lever_shares"], "USD_per_share"),
        "scored.lever.total.FQ4FY26": (scored["lever_total"], "USD_per_share"), "scored.labels_hit.FQ4FY26": (scored["labels_hit"], "count"),
        "scored.band_coverage.FQ4FY26": (scored["band_coverage"], "categorical"), "scored.sf7.FQ1FY27": (scored["sf7"], "categorical"),
    }
    for fact_id, (value, unit) in scored_facts.items():
        _put_fact(manifest, fact_id, value, unit, "FY2026Q4", "SCORED", fact_id.split(".")[-2], "SRC-SCORED-FQ4FY26")
        if fact_id.startswith("scored.lever."):
            manifest.fact(fact_id).display.update(_fact_display(value, unit, signed=True))

    guidance_facts = {
        "guidance.revenue_gaap.FQ1FY27": (ex991["guidance_mid"], "USD_million"),
        "guidance.revenue_nongaap.FQ1FY27": (ex991["guidance_mid"], "USD_million"),
        "guidance.revenue_tolerance.FQ1FY27": (ex991["guidance_revenue_tolerance"], "USD_million"),
        "guidance.gm_gaap.FQ1FY27": (ex991["guidance_gm_gaap"], "percent"),
        "guidance.gm_nongaap.FQ1FY27": (ex991["guidance_gm_nongaap"], "percent"),
        "guidance.opex_gaap.FQ1FY27": (ex991["guidance_opex_gaap"], "USD_million"),
        "guidance.opex_nongaap.FQ1FY27": (ex991["guidance_opex_nongaap"], "USD_million"),
        "guidance.eps_gaap.FQ1FY27": (ex991["guidance_eps_gaap"], "USD_per_share"),
        "guidance.eps_nongaap.FQ1FY27": (ex991["guidance_eps_nongaap"], "USD_per_share"),
        "guidance.eps_tolerance.FQ1FY27": (ex991["guidance_eps_tolerance"], "USD_per_share"),
        "guidance.diluted_shares.FQ1FY27": (ex991["guidance_shares"], "million_shares"),
    }
    for fact_id, (value, unit) in guidance_facts.items():
        _put_fact(manifest, fact_id, value, unit, "FQ1FY27", "GUIDANCE", fact_id, "SRC-EX991-FQ4FY26")
        if unit == "percent":
            manifest.fact(fact_id).display.update(_fact_display(value, unit, precision=2))

    bridge_facts = {
        "bridge.gm.FY2026Q3.A": (fq3_gross / fq3_revenue * 100, "percent", ["is.gross_profit.FY2026Q3.A", "is.revenue.FY2026Q3.A"]),
        "bridge.gm.FY2026Q4.A": (fq4_gross / fq4_revenue * 100, "percent", ["is.revenue.FY2026Q4.A-8K"]),
        "bridge.gm.delta.FY2026Q3_to_Q4": (fq4_gross / fq4_revenue * 100 - fq3_gross / fq3_revenue * 100, "percentage_points", ["bridge.gm.FY2026Q3.A", "bridge.gm.FY2026Q4.A"]),
        "bridge.opex.FY2026Q3.A": (fq3_opex, "USD_million", ["is.opex.FY2026Q3.A"]),
        "bridge.opex.FY2026Q4.A": (fq4_opex, "USD_million", ["is.opex.FY2026Q4.A-8K"]),
        "bridge.opex.delta.FY2026Q3_to_Q4": (fq4_opex - fq3_opex, "USD_million", ["is.opex.FY2026Q3.A", "is.opex.FY2026Q4.A-8K"]),
        "bridge.gm.FY2026A": (actual_ratios["gross_margin"] * 100, "percent", ["ratio.gross_margin.FY2026.A-8K"]),
        "bridge.gm.FY2027E.base": (rle["base"][2027]["gross_margin"] * 100, "percent", ["ratio.gross_margin.FY2027E.base"]),
        "bridge.gm.delta.FY2026A_to_FY2027E.base": ((rle["base"][2027]["gross_margin"] - actual_ratios["gross_margin"]) * 100, "percentage_points", ["ratio.gross_margin.FY2026.A-8K", "ratio.gross_margin.FY2027E.base"]),
        "bridge.opex.FY2026A": (actual_income["r_and_d"] + actual_income["sg_and_a"] + actual_income["other_operating"], "USD_million", ["is.opex.FY2026A.A-8K"]),
        "bridge.opex.FY2027E.base": (rle["base"][2027]["opex"], "USD_million", ["is.opex.FY2027E.base"]),
        "bridge.opex.delta.FY2026A_to_FY2027E.base": (rle["base"][2027]["opex"] - actual_income["r_and_d"] - actual_income["sg_and_a"] - actual_income["other_operating"], "USD_million", ["is.opex.FY2026A.A-8K", "is.opex.FY2027E.base"]),
    }
    for fact_id, (value, unit, inputs) in bridge_facts.items():
        _put_fact(manifest, fact_id, value, unit, "FY2026–FY2027E", "CALCULATED", fact_id, "SRC-EX991-FQ4FY26", {"formula": "margin_bridge_display_v1", "inputs": inputs})
    for start, end, delta, start_ratio, end_ratio, inputs in (
        ("FY2026Q3.A", "FY2026Q4.A", "FY2026Q3_to_Q4", fq3_opex / fq3_revenue, fq4_opex / fq4_revenue, ["is.opex.FY2026Q3.A", "is.revenue.FY2026Q3.A", "is.opex.FY2026Q4.A-8K", "is.revenue.FY2026Q4.A-8K"]),
        ("FY2026A", "FY2027E.base", "FY2026A_to_FY2027E.base", manifest.fact("is.opex.FY2026A.A-8K").raw_value / actual_income["revenue"], rle["base"][2027]["opex"] / rle["base"][2027]["revenue"], ["is.opex.FY2026A.A-8K", "is.revenue.FY2026A.A-8K", "is.opex.FY2027E.base", "is.revenue.FY2027E.base"]),
    ):
        for fact_id, value, unit in (
            (f"bridge.opex_ratio.{start}", start_ratio, "fraction"),
            (f"bridge.opex_ratio.{end}", end_ratio, "fraction"),
            (f"bridge.opex_ratio.contribution.{delta}", (start_ratio - end_ratio) * 100, "percentage_points"),
        ):
            _put_fact(manifest, fact_id, value, unit, "FY2026–FY2027E", "CALCULATED", "Operating-expense contribution to operating margin", "SRC-EX991-FQ4FY26", {"formula": "opex_margin_contribution_v1", "inputs": inputs})

    ev = implied_valuation(
        price, shares, actual_balance["cash"], actual_balance["short_term_investments"] + actual_balance["long_term_investments"],
        actual_balance["current_debt"] + actual_balance["long_term_debt"], actual_income["net_income"],
        actual_income["operating_income"] + actual_cash["d_and_a"], fcf, 12895.0,
    )
    for fact_id, value, label in (
        ("val.market_cap.2026-10-01", ev.market_cap, "Market capitalization"),
        ("val.ev.FY2026.A-8K", ev.ev, "Enterprise value"), ("val.ev_adj.FY2026.A-8K", ev.ev_adj, "SCA-adjusted enterprise value"),
    ):
        _put_fact(manifest, fact_id, float(value), "USD_million", "FY2026", "CALCULATED", label, "SRC-PRICE-1", {"formula": fact_id, "inputs": ["market.market_cap.2026-10-01.CALCULATED"]})
    valuation_periods = {
        "FY2025A": {
            "revenue": manifest.fact("is.revenue.FY2025A").raw_value, "eps": manifest.fact("is.diluted_eps.FY2025A").raw_value,
            "ebitda": manifest.fact("is.operating_income.FY2025A").raw_value + manifest.fact("cf.d_and_a.FY2025A").raw_value,
            "fcf": manifest.fact("cf.fcf_adjusted.FY2025A").raw_value,
        },
        "FY2026A": {"revenue": actual_income["revenue"], "eps": actual_income["diluted_eps"], "ebitda": actual_income["operating_income"] + actual_cash["d_and_a"], "fcf": fcf},
    }
    for scenario in ("bear", "base", "bull"):
        for year in (2027, 2028):
            values = rle[scenario][year]
            valuation_periods[f"FY{year}E.{scenario}"] = {"revenue": values["revenue"], "eps": values["diluted_eps"], "ebitda": values["operating_income"] + values["d_and_a"], "fcf": values["fcf_adjusted"]}
    for period, values in valuation_periods.items():
        for metric, value in (
            ("pe", price / values["eps"] if values["eps"] > 0 else "N/M"),
            ("ev_ebitda", ev.ev / values["ebitda"] if values["ebitda"] > 0 else "N/M"),
            ("ev_sales", ev.ev / values["revenue"] if values["revenue"] > 0 else "N/M"),
            ("fcf_yield", values["fcf"] / market_cap),
        ):
            unit = "fraction" if metric == "fcf_yield" else "multiple"
            _put_fact(manifest, f"val.{metric}.{period}", value, unit, period.split(".")[0], "CALCULATED", metric, "SRC-PRICE-1", {"formula": metric, "inputs": ["market.price.2026-10-01.CITED"]})

    base_rules = assumptions.rules
    base_revenue = rle["base"][2027]["quarterly_revenue"]
    opex = [float(value) for value in base_rules["A4_gaap_opex"]["quarterly_all_scenarios"]["value"]]
    below = float(base_rules["A5_below_operating_pct_of_revenue"]["all_scenarios"]["value"])
    tax = float(base_rules["A6_gaap_effective_tax_rate"]["base"]["value"])
    gm_base = [float(value) for value in base_rules["A3_gaap_gross_margin"]["base"]["value"]]
    growth_base = [float(value) for value in base_rules["A2_fq2_to_fq4_weekly_revenue_growth"]["base"]["value"]]
    for row, gm_shift in enumerate((-0.04, -0.02, 0.0, 0.02, 0.04)):
        for column, growth_shift in enumerate((-0.04, -0.02, 0.0, 0.02, 0.04)):
            revenues = [base_revenue[0]]
            for rate in growth_base:
                revenues.append(revenues[-1] * (1.0 + rate + growth_shift))
            ni = sum(margin_bridge(revenue, gm + gm_shift, expense, revenue * below, tax, 0.0, shares)["net_income"] for revenue, gm, expense in zip(revenues, gm_base, opex, strict=True))
            pe = price / (ni / shares)
            _put_fact(manifest, f"val.pe_sensitivity.r{row}.c{column}.FY2027E", pe, "multiple", "FY2027E", "CALCULATED", "P/E sensitivity", "SRC-PRICE-1", {"formula": "pe_sensitivity_v1", "inputs": ["market.price.2026-10-01.CITED", "is.diluted_eps.FY2027E.base"]})


def e2b_manifest_from_inputs(
    source_dir: str | Path,
    narrative_text: str,
    assumptions_text: str,
    ex991_text: str,
    remarks_text: str,
    scored_text: str,
    source_paths: dict[str, str],
) -> tuple[Manifest, dict[str, Any], ReportLayerAssumptions, dict[str, float]]:
    narrative = load_narrative_text(narrative_text)
    assumptions = load_assumptions_text(assumptions_text)
    values = recompute_fact_bindings(narrative, ex991_text, scored_text, assumptions)
    manifest = dryrun_manifest_from_extracts(source_dir)
    source_payloads = {
        "SRC-EX991-FQ4FY26": ex991_text.encode("utf-8"),
        "SRC-REMARKS-FQ4FY26": remarks_text.encode("utf-8"),
        "SRC-SCORED-FQ4FY26": scored_text.encode("utf-8"),
        "SRC-RLE-FY27": assumptions_text.encode("utf-8"),
    }
    for source_id, payload in source_payloads.items():
        path = source_paths[source_id]
        if source_id == "SRC-REMARKS-FQ4FY26":
            payload = (Path(__file__).resolve().parents[3] / path).read_bytes()
        manifest.sources[source_id] = Source(
            source_id,
            source_id.replace("SRC-", "").replace("-", " "),
            path,
            hashlib.sha256(payload).hexdigest(),
            "2026-09-30" if source_id == "SRC-REMARKS-FQ4FY26" else "2026-10-04",
        )
    ex991 = _ex991_values(ex991_text)
    scored = _scored_values(scored_text)
    support = {
        "is.revenue.FY2026Q4.A-8K": (ex991["fq4_revenue"], "USD_million", "FY2026Q4", "A-8K", "Revenue", "SRC-EX991-FQ4FY26"),
        "guidance.revenue_mid.FQ1FY27": (values["guidance.revenue_mid.FQ1FY27"], "USD_million", "FQ1FY27", "GUIDANCE", "Revenue guidance midpoint", "SRC-EX991-FQ4FY26"),
        "guidance.revenue_lo.FQ1FY27": (values["guidance.revenue_lo.FQ1FY27"], "USD_million", "FQ1FY27", "GUIDANCE", "Revenue guidance low", "SRC-EX991-FQ4FY26"),
        "bs.customer_contract_liabilities.FQ4FY26": (values["bs.customer_contract_liabilities.FQ4FY26"], "USD_million", "FY2026Q4", "A-8K", "Noncurrent customer contract liabilities", "SRC-EX991-FQ4FY26"),
        "rle.opex.FY27E": (values["rle.opex.FY27E"], "USD_million", "FY2027E", "RLE", "GAAP operating expenses", "SRC-RLE-FY27"),
        "rle.revenue.FY27E.base": (values["rle.revenue.FY27E.base"], "USD_million", "FY2027E", "RLE", "Base revenue", "SRC-RLE-FY27"),
        "rle.eps_gaap.FY27E.base": (values["rle.eps_gaap.FY27E.base"], "USD_per_share", "FY2027E", "RLE", "Base GAAP EPS", "SRC-RLE-FY27"),
        "rle.eps_gaap.FY27E.bear": (values["rle.eps_gaap.FY27E.bear"], "USD_per_share", "FY2027E", "RLE", "Bear GAAP EPS", "SRC-RLE-FY27"),
        "rle.eps_gaap.FY27E.bull": (values["rle.eps_gaap.FY27E.bull"], "USD_per_share", "FY2027E", "RLE", "Bull GAAP EPS", "SRC-RLE-FY27"),
        "dividend.dps.declared_2026-09-30": (values["dividend.dps.declared_2026-09-30"], "USD_per_share", "2026-09-30", "DECLARED", "Quarterly dividend", "SRC-EX991-FQ4FY26"),
        "scored.opex_actual.FQ4FY26": (scored["opex_actual"], "USD_million", "FY2026Q4", "SCORED", "Actual GAAP operating expenses", "SRC-SCORED-FQ4FY26"),
        "scored.opex_forecast.FQ4FY26": (scored["opex_forecast"], "USD_million", "FY2026Q4", "SCORED", "Forecast GAAP operating expenses", "SRC-SCORED-FQ4FY26"),
        "scored.eps_actual.FQ4FY26": (scored["eps_actual"], "USD_per_share", "FY2026Q4", "SCORED", "Actual GAAP EPS", "SRC-SCORED-FQ4FY26"),
        "scored.eps_forecast.FQ4FY26": (scored["eps_forecast"], "USD_per_share", "FY2026Q4", "SCORED", "Forecast GAAP EPS", "SRC-SCORED-FQ4FY26"),
    }
    for fact_id, (value, unit, period, basis, label, source_id) in support.items():
        manifest.facts[fact_id] = Fact(fact_id, value, _display(fact_id, value), unit, period, basis, label, source_id)
    calculated = {
        "derived.weekly_growth.FQ1FY27_guide": ("weekly_growth_v1", ["guidance.revenue_mid.FQ1FY27", "is.revenue.FY2026Q4.A-8K"], "SRC-EX991-FQ4FY26", "FQ1 revenue guidance per-week growth"),
        "scored.opex_gap_pct.FQ4FY26": (
            "actual_div_forecast_minus_one_v1",
            ["scored.opex_actual.FQ4FY26", "scored.opex_forecast.FQ4FY26"],
            "SRC-SCORED-FQ4FY26",
            "GAAP opex gap",
        ),
        "scored.eps_error.FQ4FY26": (
            "actual_minus_forecast_v1",
            ["scored.eps_actual.FQ4FY26", "scored.eps_forecast.FQ4FY26"],
            "SRC-SCORED-FQ4FY26",
            "GAAP EPS error",
        ),
    }
    for fact_id, (formula, inputs, source_id, label) in calculated.items():
        value = values[fact_id]
        manifest.facts[fact_id] = Fact(
            fact_id, value, _display(fact_id, value),
            "fraction" if "pct" in fact_id or "growth" in fact_id else "USD_per_share",
            "FY2026Q4" if "FQ4" in fact_id else "FQ1FY27", "CALCULATED", label, source_id,
            lineage={"formula": formula, "inputs": inputs},
        )
    _extend_e2b_manifest(manifest, assumptions, ex991_text, remarks_text, scored_text, source_paths)
    manifest.metadata = {"information_cutoff": "2026-10-04", "layer": "E2-B", "fixture_values": False}
    manifest.validate()
    return manifest, narrative, assumptions, values


def narrative_section_markdown(
    section_id: str,
    locale: str,
    narrative: dict[str, Any],
    replace_fact,
    strings: dict[str, Any],
) -> list[str]:
    data = narrative[section_id][locale]
    ui = strings["narrative_ui"]
    out: list[str] = []
    if section_id == "thesis":
        out.extend([replace_fact(data["intro"], "intro"), ""])
        for side in ("bull", "bear"):
            out.extend([f"### {ui[side]}", ""])
            for index, item in enumerate(data[side], start=1):
                out.extend([
                    f"#### {replace_fact(item['claim'], f'{side}:{index}:claim')}", "",
                    replace_fact(item["detail"], f"{side}:{index}:detail"), "",
                    f"**{ui['falsifier']}** {replace_fact(item['falsifier'], f'{side}:{index}:falsifier')}", "",
                    f"*{ui['source']}: {item['src']}*", "",
                ])
    elif section_id == "scenarios":
        for index, paragraph in enumerate(data, start=1):
            out.extend([replace_fact(paragraph, f"paragraph:{index}"), ""])
    elif section_id == "risks":
        for index, item in enumerate(data, start=1):
            out.extend([
                f"### {item['title']}", "", replace_fact(item["body"], f"risk:{index}:body"), "",
                f"*{ui['source']}: {item['src']}*", "",
            ])
    elif section_id == "catalysts":
        out.extend([
            f"| {ui['when']} | {ui['what']} | {ui['source']} |",
            "|---|---|---|",
        ])
        for index, item in enumerate(data, start=1):
            out.append(f"| {item['when']} | {replace_fact(item['what'], f'catalyst:{index}:what')} | {item['src']} |")
        out.append("")
    else:
        raise ValueError(f"unsupported narrative section: {section_id}")
    return out


def appendix_markdown(assumptions: ReportLayerAssumptions, locale: str, strings: dict[str, Any]) -> list[str]:
    ui = strings["appendix"]
    rules = assumptions.rules

    def numeric_tokens(value: str) -> list[str]:
        return re.findall(r"(?<!\w)[-+]?\$?\d(?:[\d,]*\d)?(?:\.\d+)?%?", value)

    def collect(node: Any, key: str) -> list[Any]:
        if isinstance(node, dict):
            found: list[Any] = []
            for name, value in node.items():
                if name == key:
                    found.append(value)
                else:
                    found.extend(collect(value, key))
            return found
        if isinstance(node, list):
            return [child for value in node for child in collect(value, key)]
        return []

    def leaf_values(node: Any, prefix: str = "") -> list[str]:
        if isinstance(node, dict):
            values: list[str] = []
            for name, value in node.items():
                if name in {"source_id", "formula"}:
                    continue
                values.extend(leaf_values(value, f"{prefix}.{name}" if prefix else name))
            return values
        if isinstance(node, list):
            return [("값: " if locale == "ko" else "value: ") + "/".join(f"{float(value):g}" if isinstance(value, (int, float)) else str(value) for value in node)]
        rendered = f"{float(node):g}" if isinstance(node, (int, float)) else str(node)
        if locale == "ko" and re.search(r"[A-Za-z]", rendered):
            original = rendered
            status = {
                "AVAILABLE": "가용", "AVAILABLE_BACKSOLVED": "역산 가용", "PASS_GAAP": "GAAP 기준 통과",
                "NOT_ACTIVATED": "미발동", "UNAVAILABLE": "미가용", "UNAVAILABLE_WITHOUT_ASSUMPTIONS": "가정 부재로 미가용",
            }
            rendered = status.get(rendered, "계약 원문 참조")
            tokens = numeric_tokens(original)
            if tokens and not all(token in rendered for token in tokens):
                rendered += " (" + " · ".join(tokens) + ")"
        return [("값: " if locale == "ko" else "value: ") + rendered]

    out = [
        f"### {ui['r9_title']}", "", ui["confidence_note"], "",
        f"| {ui['rule']} | {ui['value']} | {ui['formula']} | {ui['grade']} | {ui['source']} |",
        "|---|---|---|---|---|",
    ]
    display_inputs = {
        "A1_fq1_revenue": ("bear", "base", "bull", "sensitivity_company_midpoint"),
        "A2_fq2_to_fq4_weekly_revenue_growth": ("bear", "base", "bull", "sensitivity_existing_slowdown"),
        "A2_prime_decline_parallel_path": ("trigger", "observed_direction", "status"),
        "A3_gaap_gross_margin": ("bear", "base", "bull", "sensitivity_preregistered_original"),
        "A4_gaap_opex": ("quarterly_all_scenarios", "fy2027_total"),
        "A5_below_operating_pct_of_revenue": ("all_scenarios",),
        "A6_gaap_effective_tax_rate": ("status", "bear", "base", "bull"),
        "A7_diluted_shares": ("quarterly_all_scenarios", "buyback", "sensitivity_reduction"),
        "A8_fy2028_revenue_growth": ("bear", "base", "bull"),
        "A9_fy2028_gross_margin": ("bear", "base", "bull"),
        "A10_fy2028_opex": ("all_scenarios",),
        "A11_da": ("fy2026_rate_d", "quarterly_rate", "fy2027_total", "fy2027_ending_ppe"),
        "A12_sbc": ("median_rate", "fy2027_total"),
        "A13_working_capital": ("status", "median_k"),
        "A14_net_capex": ("quarterly_all_scenarios", "fy2027_total", "fy2028_total", "sensitivity_pct"),
        "A15_dividends": ("quarterly_dps", "fy2027_total"),
        "A16_sca_deposits": ("rle_periods",),
        "A17_nongaap_fy2027_fy2028": ("value",),
    }
    for key in sorted(rules, key=lambda item: (int(re.match(r"A(\d+)", item).group(1)) if re.match(r"A(\d+)", item) else 99, item)):
        if not key.startswith("A"):
            continue
        selected = {name: rules[key][name] for name in display_inputs[key]}
        values = "; ".join(leaf_values(selected))
        formulas = "; ".join(dict.fromkeys(str(value) for value in collect(rules[key], "formula"))) or "—"
        formulas = formulas.replace("*", "×")
        sources = "; ".join(dict.fromkeys(
            source for value in collect(rules[key], "source_id") for source in (value if isinstance(value, list) else [value])
        ))
        name = ui.get("rule_names", {}).get(key, key)
        rule_number = int(re.match(r"A(\d+)", key).group(1))
        input_grade = "D" if rule_number in {4, 6, 8, 9, 10} else "E"
        if key == "A2_fq2_to_fq4_weekly_revenue_growth":
            input_grade = "E·D"
        if rule_number == 14:
            input_grade = "E(하한)" if locale == "ko" else "E(lower bound)"
        grade = input_grade + (" / —" if rule_number >= 15 else " / J")
        out.append(f"| {key} · {name} | {values} | {formulas} | {grade} | {sources} |")
    out.extend(["", ui["timing_limit"], "", f"### {ui['r12_title']}", ""])
    headers = ui["change_headers"]
    out.extend(["| " + " | ".join(headers) + " |", "|---|---|---|---|---|"])
    ko_reasons = {
        "A3_base": "준비문은 첫 분기를 다음 회계연도 매출총이익률의 바닥으로 제시한다. 이후 분기를 같은 수준으로 둔 것은 새 수치를 만들지 않는 보수적 처리다.",
        "A4_opex": "준비문의 비GAAP 영업비용 증가 안내와 첫 분기 주식보상 차이를 GAAP 기준으로 연결했다.",
        "A14_net_capex": "준비문은 상반기 투자 규모와 하반기 증가 방향을 제시한다. 하반기를 상반기와 같게 둔 것은 FCF를 높게 만드는 공개된 하한 가정이다.",
    }

    ko_changes = {
        "A3_base": (
            "FQ1 = M1; 이후 분기마다 -0.5 퍼센트포인트",
            "FQ1 = M1; FQ4까지 동일; 사전등록 -0.5 퍼센트포인트 경로는 민감도로 유지",
        ),
        "A4_opex": (
            "FY2026 GAAP 영업비용 × 52/53 + 1000; FQ1=X1; 잔액을 30:33:37로 배분",
            "(6841 비GAAP 영업비용 + 2500) + 253×4 = 10353; 분기별 2310/2413/2654/2976",
        ),
        "A14_net_capex": (
            "FQ4 실제 순설비투자 × 1.05, 보합; FY2027 수치 가이던스 발표 시 대체",
            "11500/13500/12500/12500; FY2027 합계 50000; FY2028 합계 50000",
        ),
    }

    def localized_change(key: str, index: int, value: str) -> str:
        if locale != "ko":
            return value
        return ko_changes[key][index]

    for key in ("A3_base", "A4_opex", "A14_net_capex"):
        change = assumptions.post_print_change[key]
        reason = ko_reasons[key] if locale == "ko" else str(change.reason.value)
        if locale == "ko":
            reason_numbers = numeric_tokens(str(change.reason.value))
            if reason_numbers:
                reason += " (" + " · ".join(reason_numbers) + ")"
        out.append("| " + " | ".join([
            key, localized_change(key, 0, str(change.original.value)), localized_change(key, 1, str(change.change.value)),
            reason, str(change.page.value),
        ]) + " |")
    note = assumptions.interpretation_note["A11_net_capex_roll_forward"]
    if locale == "ko":
        note_lines = [
            "순설비투자를 유형자산 이월 계산에 사용한다. 기말 유형자산은 기초 유형자산에 순설비투자를 더하고 감가상각을 뺀 값이다. 분기 감가상각은 기초·기말 유형자산 평균에 분기율을 곱한다.",
            "이전 회계연도 공시는 자본적 지출 관련 정부 인센티브가 유형자산을 줄인다고 설명한다.",
            "정부 인센티브 수령과 유형자산 차감의 시차 및 미실현 정부 인센티브 잔액은 모델링하지 않는다.",
        ]
        for index, key in enumerate(("corrected_interpretation", "evidence", "limitation")):
            tokens = numeric_tokens(str(note[key].value))
            if tokens:
                note_lines[index] += " (" + " · ".join(tokens) + ")"
    else:
        note_lines = [str(note["corrected_interpretation"].value), str(note["evidence"].value), str(note["limitation"].value)]
    out.extend([
        "", f"### {ui['a11_title']}", "", note_lines[0], "",
        note_lines[1], "", note_lines[2], "",
        ui["nwc_note"], "",
    ])
    return out
