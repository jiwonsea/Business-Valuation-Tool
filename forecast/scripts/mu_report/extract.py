"""Deterministic extraction from pinned MU filings and archived releases."""

from __future__ import annotations

import json
import math
import re
import warnings
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from forecast.engine.generic_forecast import run_generic_forecast
from forecast.schemas.generic import GenericProfile
from pypdf import PdfReader

from .inputs import PACKAGE_DIR, EvidenceReader, atomic_write

PR_PATHS = [
    "logs/_claude_scratch/mu_G2024Q2_ex991.htm",
    "logs/_claude_scratch/mu_G2024Q3_ex991.htm",
    "logs/_claude_scratch/mu_G2024Q4_ex991.htm",
    "logs/_claude_scratch/mu_FY2024Q4_ex991.htm",
    "logs/_claude_scratch/mu_G2025Q2_ex991.htm",
    "logs/_claude_scratch/mu_G2025Q3_ex991.htm",
    "logs/_claude_scratch/mu_G2025Q4_ex991.htm",
    "logs/_claude_scratch/mu_FY2025Q4_ex991.htm",
    "logs/_claude_scratch/mu_G2026Q2_ex991.htm",
    "logs/_claude_scratch/mu_G2026Q3_ex991.htm",
    "logs/mu_ho5_S2_release.html",
]
TEN_K_2025 = "logs/_claude_scratch/mu-20250828.htm"
TEN_K_2023 = "logs/_claude_scratch/mu-20230831.htm"
COMPANYFACTS = "forecast/reports/.cache/edgar_companyfacts_CIK0000723125.json"
TEN_Q_FY26Q3 = "logs/mu_ho5_S3_10q.html"
REMARKS_FY26Q3 = "logs/mu_ho5_Q3_remarks.pdf"
FROZEN = "forecast/reports/mu_fy2026q4_forecast_FROZEN.md"
PROFILE = "forecast/profiles/mu.generic.yaml"


def _number(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip().replace("$", "").replace(",", "")
    if text.lower() in {"", "nan", "—", "–", "-"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def _group_value(row: pd.Series, start: int) -> float | None:
    for cell in row.iloc[start : start + 3]:
        value = _number(cell)
        if value is not None:
            return value
    return None


def _table_rows(payload: bytes, table_index: int) -> pd.DataFrame:
    return pd.read_html(BytesIO(payload), flavor="lxml")[table_index]


def _find_row(table: pd.DataFrame, label: str, occurrence: int = 0) -> tuple[int, pd.Series]:
    matches = []
    for index, row in table.iterrows():
        if str(row.iloc[0]).strip() == label:
            matches.append((int(index), row))
    if len(matches) <= occurrence:
        raise ValueError(f"row not found: {label} occurrence {occurrence}")
    return matches[occurrence]


def _full_rows(table: pd.DataFrame, columns: dict[str, int]) -> list[dict[str, Any]]:
    rows = []
    seen: dict[str, int] = {}
    for row_index, row in table.iterrows():
        label = str(row.iloc[0]).strip()
        if label.lower() == "nan":
            continue
        values = {year: _group_value(row, start) for year, start in columns.items()}
        if all(value is None for value in values.values()):
            continue
        occurrence = seen.get(label, 0)
        seen[label] = occurrence + 1
        rows.append({"label": label, "occurrence": occurrence, "values": values, "coordinate": {"row": int(row_index), "columns": {year: [start, start + 2] for year, start in columns.items()}}})
    return rows


def extract_annual(reader: EvidenceReader) -> dict[str, Any]:
    payload = reader.read_bytes(TEN_K_2025)
    income = _table_rows(payload, 18)
    balance = _table_rows(payload, 20)
    cash_flow = _table_rows(payload, 22)
    years = {"FY2025A": 3, "FY2024A": 6, "FY2023A": 9}
    income_map = {
        "revenue": ("Revenue", 0),
        "cogs": ("Cost of goods sold", 0),
        "gross_profit": ("Gross margin", 0),
        "r_and_d": ("Research and development", 0),
        "sg_and_a": ("Selling, general, and administrative", 0),
        "restructuring": ("Restructure and asset impairments", 0),
        "other_operating": ("Other operating (income) expense, net", 0),
        "operating_income": ("Operating income (loss)", 0),
        "interest_income": ("Interest income", 0),
        "interest_expense": ("Interest expense", 0),
        "other_nonoperating": ("Other non-operating income (expense), net", 0),
        "tax": ("Income tax (provision) benefit", 0),
        "equity_method": ("Equity in net income (loss) of equity method investees", 0),
        "net_income": ("Net income (loss)", 0),
        "diluted_eps": ("Diluted", 0),
        "diluted_shares": ("Diluted", 1),
    }
    annual: dict[str, Any] = {}
    for year, start in years.items():
        values: dict[str, Any] = {}
        coordinates: dict[str, Any] = {}
        for key, (label, occurrence) in income_map.items():
            row_index, row = _find_row(income, label, occurrence)
            values[key] = _group_value(row, start)
            coordinates[key] = {"table": 18, "row": row_index, "columns": [start, start + 2]}
        pretax_row = 16
        values["pretax_income"] = _group_value(income.iloc[pretax_row], start)
        coordinates["pretax_income"] = {"table": 18, "row": pretax_row, "columns": [start, start + 2], "anchor": "unlabeled subtotal after other non-operating"}
        annual[year] = {"income_statement": values, "coordinates": {"income_statement": coordinates}}

    for year, start in {"FY2025A": 3, "FY2024A": 6}.items():
        rows: dict[str, Any] = {}
        coords: dict[str, Any] = {}
        for key, label in {
            "cash": "Cash and cash equivalents",
            "short_term_investments": "Short-term investments",
            "receivables": "Receivables",
            "inventories": "Inventories",
            "total_current_assets": "Total current assets",
            "long_term_investments": "Long-term marketable investments",
            "ppe": "Property, plant, and equipment",
            "accounts_payable_accrued": "Accounts payable and accrued expenses",
            "current_debt": "Current debt",
            "total_current_liabilities": "Total current liabilities",
            "long_term_debt": "Long-term debt",
            "total_assets": "Total assets",
            "total_liabilities": "Total liabilities",
            "total_equity": "Total equity",
        }.items():
            row_index, row = _find_row(balance, label)
            rows[key] = _group_value(row, start)
            coords[key] = {"table": 20, "row": row_index, "columns": [start, start + 2]}
        annual[year]["balance_sheet"] = rows
        annual[year]["coordinates"]["balance_sheet"] = coords

    old_payload = reader.read_bytes(TEN_K_2023)
    old_balance = _table_rows(old_payload, 20)
    rows = {}
    coords = {}
    for key, label in {
        "cash": "Cash and equivalents",
        "short_term_investments": "Short-term investments",
        "receivables": "Receivables",
        "inventories": "Inventories",
        "total_current_assets": "Total current assets",
        "long_term_investments": "Long-term marketable investments",
        "ppe": "Property, plant, and equipment",
        "accounts_payable_accrued": "Accounts payable and accrued expenses",
        "current_debt": "Current debt",
        "total_current_liabilities": "Total current liabilities",
        "long_term_debt": "Long-term debt",
        "total_assets": "Total assets",
        "total_liabilities": "Total liabilities",
        "total_equity": "Total equity",
    }.items():
        row_index, row = _find_row(old_balance, label)
        rows[key] = _group_value(row, 3)
        coords[key] = {"table": 20, "row": row_index, "columns": [3, 5]}
    annual["FY2023A"]["balance_sheet"] = rows
    annual["FY2023A"]["coordinates"]["balance_sheet"] = coords

    for year, start in years.items():
        rows = {}
        coords = {}
        for key, label in {
            "net_income": "Net income (loss)",
            "d_and_a": "Depreciation expense and amortization of intangible assets",
            "sbc": "Stock-based compensation",
            "receivables_change": "Receivables",
            "inventories_change": "Inventories",
            "accounts_payable_change": "Accounts payable and accrued expenses",
            "other_current_liabilities_change": "Other current liabilities",
            "operating_cash_flow": "Net cash provided by operating activities",
            "ppe_expenditures": "Expenditures for property, plant, and equipment",
            "government_incentives": "Proceeds from government incentives",
            "debt_repayments": "Repayments of debt",
            "debt_issuance": "Proceeds from issuance of debt",
            "dividends": "Payments of dividends to shareholders",
        }.items():
            row_index, row = _find_row(cash_flow, label)
            rows[key] = _group_value(row, start)
            coords[key] = {"table": 22, "row": row_index, "columns": [start, start + 2]}
        annual[year]["cash_flow"] = rows
        annual[year]["coordinates"]["cash_flow"] = coords

    full_income = _full_rows(income, years)
    full_cash_flow = _full_rows(cash_flow, years)
    full_balance_recent = _full_rows(balance, {"FY2025A": 3, "FY2024A": 6})
    full_balance_fy23 = _full_rows(old_balance, {"FY2023A": 3})
    for year in years:
        annual[year]["as_filed_rows"] = {
            "income_statement": [row for row in full_income if row["values"][year] is not None],
            "cash_flow": [row for row in full_cash_flow if row["values"][year] is not None],
            "balance_sheet": [row for row in (full_balance_fy23 if year == "FY2023A" else full_balance_recent) if row["values"].get(year) is not None],
        }

    for year, start in years.items():
        for key, label in {
            "investing_cash_flow": "Net cash used for investing activities",
            "financing_cash_flow": "Net cash provided by (used for) financing activities",
            "fx_effect": "Effect of changes in currency exchange rates on cash, cash equivalents, and restricted cash",
            "cash_change": "Net increase (decrease) in cash, cash equivalents, and restricted cash",
        }.items():
            row_index, row = _find_row(cash_flow, label)
            annual[year]["cash_flow"][key] = _group_value(row, start)
            annual[year]["coordinates"]["cash_flow"][key] = {"table": 22, "row": row_index, "columns": [start, start + 2]}

    inventory_balances = {}
    inventory_sources = (
        ("FY2022A", old_balance, 6, TEN_K_2023),
        ("FY2023A", old_balance, 3, TEN_K_2023),
        ("FY2024A", balance, 6, TEN_K_2025),
        ("FY2025A", balance, 3, TEN_K_2025),
    )
    for period, table, start, source_path in inventory_sources:
        row_index, row = _find_row(table, "Inventories")
        inventory_balances[period] = {
            "value": _group_value(row, start),
            "caption": "Inventories",
            "source_path": source_path,
            "source_sha256": reader.allowed[source_path],
            "coordinate": {"table": 20, "row": row_index, "columns": [start, start + 2]},
        }

    equity_balances = {}
    for period, table, start, source_path in (
        ("FY2022A", old_balance, 6, TEN_K_2023),
        ("FY2023A", old_balance, 3, TEN_K_2023),
        ("FY2024A", balance, 6, TEN_K_2025),
        ("FY2025A", balance, 3, TEN_K_2025),
    ):
        row_index, row = _find_row(table, "Total equity")
        equity_balances[period] = {
            "value": _group_value(row, start),
            "caption": "Total equity",
            "source_path": source_path,
            "source_sha256": reader.allowed[source_path],
            "coordinate": {"table": 20, "row": row_index, "columns": [start, start + 2]},
        }

    return {
        "source": {"path": TEN_K_2025, "sha256": reader.allowed[TEN_K_2025], "accession": "0000723125-25-000028", "as_of": "2025-08-28"},
        "supplemental_source": {"path": TEN_K_2023, "sha256": reader.allowed[TEN_K_2023], "accession": "0000723125-23-000084", "as_of": "2023-08-31"},
        "unit": "USD_million_except_per_share",
        "inventory_balances": inventory_balances,
        "equity_balances": equity_balances,
        "years": annual,
    }


def _quarter_entries(companyfacts: dict[str, Any], tag: str) -> list[dict[str, Any]]:
    units = companyfacts["facts"]["us-gaap"][tag]["units"]
    unit = "USD" if "USD" in units else next(iter(units))
    entries = []
    for entry in units[unit]:
        if entry.get("form") not in {"10-Q", "10-K"} or "start" not in entry:
            continue
        days = (pd.Timestamp(entry["end"]) - pd.Timestamp(entry["start"])).days
        if 80 <= days <= 105 and 2022 <= int(entry["end"][:4]) <= 2026:
            entries.append(entry)
    by_period: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in entries:
        key = (entry["start"], entry["end"])
        current = by_period.get(key)
        if current is None or entry["filed"] < current["filed"]:
            by_period[key] = entry
    return sorted(by_period.values(), key=lambda item: item["end"])


def extract_companyfacts(reader: EvidenceReader) -> dict[str, Any]:
    payload = json.loads(reader.read_text(COMPANYFACTS))
    tags = {
        "revenue": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "gross_profit": "GrossProfit",
        "operating_income": "OperatingIncomeLoss",
        "net_income": "NetIncomeLoss",
    }
    annual_tags = {
        "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "USD"),
        "operating_income": ("OperatingIncomeLoss", "USD"),
        "net_income": ("NetIncomeLoss", "USD"),
        "diluted_eps": ("EarningsPerShareDiluted", "USD/shares"),
        "total_assets": ("Assets", "USD"),
        "total_liabilities": ("Liabilities", "USD"),
        "total_equity": ("StockholdersEquity", "USD"),
        "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities", "USD"),
    }
    year_ends = {"FY2023A": "2023-08-31", "FY2024A": "2024-08-29", "FY2025A": "2025-08-28"}
    annual_crosscheck: dict[str, dict[str, Any]] = {year: {} for year in year_ends}
    for metric, (tag, unit) in annual_tags.items():
        entries = payload["facts"]["us-gaap"][tag]["units"][unit]
        for year, end in year_ends.items():
            candidates = [entry for entry in entries if entry.get("end") == end and entry.get("form") == "10-K"]
            if not candidates:
                continue
            candidate = sorted(candidates, key=lambda item: item["filed"])[0]
            annual_crosscheck[year][metric] = {key: candidate[key] for key in ("val", "accn", "filed", "end")}
    return {
        "source": {"path": COMPANYFACTS, "sha256": reader.allowed[COMPANYFACTS], "as_of": "2026-06-25"},
        "unit": "USD",
        "series": {name: {"tag": tag, "quarters": _quarter_entries(payload, tag)} for name, tag in tags.items()},
        "annual_crosscheck": annual_crosscheck,
        "method": "earliest as-filed filing per approximately three-month start/end period; Q4 may be derived separately as FY minus 9M",
    }


def _plain_text(payload: bytes) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        return " ".join(BeautifulSoup(payload, "lxml").get_text(" ", strip=True).split())


def extract_releases(reader: EvidenceReader) -> dict[str, Any]:
    releases = []
    row_anchors = (
        "revenue",
        "cost of goods sold",
        "gross margin",
        "research and development",
        "selling, general",
        "restructure",
        "other operating",
        "operating income",
        "other non-operating",
        "income tax",
        "equity in net income",
        "net income",
        "diluted earnings",
        "diluted shares",
        "business unit",
        "net cash provided",
        "capital expenditures",
        "government incentives",
        "adjusted free cash flow",
        "loss on debt prepayments",
    )
    for path in PR_PATHS:
        payload = reader.read_bytes(path)
        tables = pd.read_html(BytesIO(payload), flavor="lxml")
        selected = []
        for index, table in enumerate(tables):
            rows = []
            for row_index, row in table.iterrows():
                label = str(row.iloc[0]).strip()
                if any(anchor in label.lower() for anchor in row_anchors):
                    rows.append({"row": int(row_index), "label": label, "values": [str(value) if not pd.isna(value) else "" for value in row.tolist()]})
            if rows:
                headers = [[str(value) if not pd.isna(value) else "" for value in row] for row in table.iloc[:5].to_numpy().tolist()]
                selected.append({"table": index, "headers": headers, "rows": rows})
        releases.append({"path": path, "sha256": reader.allowed[path], "selected_tables": selected})
    return {"sources": releases, "row_anchors": list(row_anchors), "release_count": len(releases)}


def extract_guidance(reader: EvidenceReader) -> dict[str, Any]:
    records = []
    actual_eps: dict[str, float] = {}
    for path in PR_PATHS:
        payload = reader.read_bytes(path)
        tables = pd.read_html(BytesIO(payload), flavor="lxml")
        for table in tables:
            flat = " ".join(str(value) for value in table.fillna("").to_numpy().flatten())
            if "Quarterly Financial Results" not in flat:
                continue
            eps_rows = [
                row for _, row in table.iterrows()
                if str(row.iloc[0]).startswith("Diluted earnings") and "per share" in str(row.iloc[0])
            ]
            if not eps_rows or len(table) < 4:
                continue
            eps_row = eps_rows[0]
            for start in (3, 6, 9):
                if start >= len(table.columns):
                    continue
                period = str(table.iloc[3, start])
                value = _group_value(eps_row, start)
                if re.fullmatch(r"FQ[1-4]-\d{2}", period) and value is not None:
                    actual_eps[period] = float(value)
            break
        for table_index, table in enumerate(tables):
            flat = " ".join(str(value) for value in table.fillna("").to_numpy().flatten())
            if "Outlook" not in flat or "Revenue" not in flat or "Gross margin" not in flat:
                continue
            period_match = re.search(r"FQ[1-4]-\d{2}", flat)
            rows = []
            for row_index, row in table.iterrows():
                raw_label = str(row.iloc[0])
                is_eps = raw_label.startswith("Diluted earnings") and "per share" in raw_label
                if raw_label in {"Revenue", "Gross margin", "Operating expenses"} or is_eps:
                    label = "Diluted earnings (loss) per share" if is_eps else raw_label
                    rows.append({"label": label, "values_verbatim": list(dict.fromkeys(str(value) for value in row.iloc[3:].tolist() if str(value).lower() != "nan")), "coordinate": {"table": table_index, "row": int(row_index)}})
            if rows:
                records.append({"target_period": period_match.group(0) if period_match else "UNRESOLVED", "source_path": path, "source_sha256": reader.allowed[path], "table": table_index, "rows": rows})
                break
    for record in records:
        eps = next((row for row in record["rows"] if row["label"] == "Diluted earnings (loss) per share"), None)
        if eps and record["target_period"] in actual_eps:
            text = eps["values_verbatim"][0]
            midpoint_match = re.search(r"\(?\$([0-9.]+)\)?", text)
            tolerance_match = re.search(r"±\s*\$([0-9.]+)", text)
            if midpoint_match and tolerance_match:
                midpoint = float(midpoint_match.group(1)) * (-1 if "(" in midpoint_match.group(0) else 1)
                record["gaap_eps_guidance_high"] = midpoint + float(tolerance_match.group(1))
                record["gaap_eps_actual"] = actual_eps[record["target_period"]]
                record["gaap_eps_beat_high"] = record["gaap_eps_actual"] - record["gaap_eps_guidance_high"]
    return {"guidance_records": records, "count": len(records), "policy": "Values remain verbatim; basis comes from table column headings."}


def extract_business_units(reader: EvidenceReader) -> dict[str, Any]:
    source_paths = [
        "logs/_claude_scratch/mu_FY2025Q4_ex991.htm",
        "logs/_claude_scratch/mu_G2026Q2_ex991.htm",
        "logs/_claude_scratch/mu_G2026Q3_ex991.htm",
        "logs/mu_ho5_S2_release.html",
    ]
    unit_rows = {
        "CMBU": ("Cloud Memory Business Unit", 4),
        "CDBU": ("Core Data Center Business Unit", 9),
        "MCBU": ("Mobile and Client Business Unit", 14),
        "AEBU": ("Automotive and Embedded Business Unit", 19),
    }
    history: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for path in source_paths:
        payload = reader.read_bytes(path)
        tables = pd.read_html(BytesIO(payload), flavor="lxml")
        match_index = next(index for index, table in enumerate(tables) if "Quarterly Business Unit Financial Results" in " ".join(str(value) for value in table.fillna("").to_numpy().flatten()))
        table = tables[match_index]
        periods = [str(table.iloc[2, start]) for start in (3, 6, 9)]
        for unit, (full_name, heading_row) in unit_rows.items():
            for metric, offset in (("revenue", 1), ("gross_margin_pct", 2), ("operating_margin_pct", 3)):
                row_index = heading_row + offset
                for period, start in zip(periods, (3, 6, 9), strict=True):
                    value = _group_value(table.iloc[row_index], start)
                    key = (period, unit, metric)
                    history.setdefault(key, []).append({"value": value, "source_path": path, "source_sha256": reader.allowed[path], "coordinate": {"table": match_index, "row": row_index, "columns": [start, start + 2]}, "full_name": full_name})
    selected = []
    revisions = []
    for (period, unit, metric), versions in sorted(history.items()):
        latest = versions[-1]
        selected.append({"period": period, "unit": unit, "metric": metric, **latest})
        distinct = {version["value"] for version in versions}
        if len(distinct) > 1:
            revisions.append({"period": period, "unit": unit, "metric": metric, "versions": versions})
    return {"records": selected, "periods": sorted({row["period"] for row in selected}), "latest_release_wins": True, "rewrites": revisions}


def extract_debt_and_fcf(reader: EvidenceReader) -> dict[str, Any]:
    pr_path = "logs/mu_ho5_S2_release.html"
    pr_payload = reader.read_bytes(pr_path)
    pr_tables = pd.read_html(BytesIO(pr_payload), flavor="lxml")
    debt_rows = []
    fcf_rows = []
    for table_index, table in enumerate(pr_tables):
        for row_index, row in table.iterrows():
            label = str(row.iloc[0])
            if "Other non-operating income (expense), net" in label or "Loss on debt prepayments" in label:
                debt_rows.append({"label": label, "values": [str(value) for value in row.tolist()], "coordinate": {"table": table_index, "row": int(row_index)}})
            if any(term in label for term in ("Net cash provided by operating activities", "Expenditures for property", "Proceeds from sales of property", "Government incentives", "Adjusted free cash flow")):
                fcf_rows.append({"label": label, "values": [str(value) for value in row.tolist()], "coordinate": {"table": table_index, "row": int(row_index)}})
    ten_q_text = _plain_text(reader.read_bytes(TEN_Q_FY26Q3))
    match = re.search(r"recognized losses in other non-operating income \(expense\) of \$\s*(\d+) million and \$\s*(\d+) million[^.]*\.", ten_q_text, re.IGNORECASE)
    if not match:
        raise ValueError("FY26Q3 10-Q debt-prepayment anchor not found")
    gaap_debt_row = next(row for row in debt_rows if row["label"] == "Other non-operating income (expense), net")
    bridge_debt_row = next(row for row in debt_rows if row["label"] == "Loss on debt prepayments")
    gaap_value = _number(gaap_debt_row["values"][3])
    bridge_value = _number(bridge_debt_row["values"][3])
    if gaap_value is None or bridge_value is None:
        raise ValueError("debt-prepayment release values are missing")
    fcf_table = pr_tables[8]
    fcf_labels = {
        "operating_cash_flow": "GAAP net cash provided by operating activities",
        "ppe_expenditures": "Expenditures for property, plant, and equipment",
        "ppe_disposal_proceeds": "Proceeds from sales of property, plant, and equipment",
        "government_incentives": "Proceeds from government incentives",
        "net_capex": "Investments in capital expenditures, net",
        "adjusted_free_cash_flow": "Adjusted free cash flow",
    }
    fcf_values = {}
    fcf_coordinates = {}
    for key, label in fcf_labels.items():
        row_index, row = _find_row(fcf_table, label)
        value = _group_value(row, 3)
        if value is None:
            raise ValueError(f"FQ3 FY26 FCF component is missing: {label}")
        fcf_values[key] = abs(value) if key in {"ppe_expenditures", "net_capex"} else value
        fcf_coordinates[key] = {"table": 8, "row": row_index, "columns": [3, 5]}
    return {
        "sources": [
            {"path": pr_path, "sha256": reader.allowed[pr_path], "as_of": "2026-05-28"},
            {"path": TEN_Q_FY26Q3, "sha256": reader.allowed[TEN_Q_FY26Q3], "accession": "0000723125-26-000015", "as_of": "2026-05-28"},
        ],
        "debt_prepayment": {
            "gaap_other_nonoperating_net": gaap_value,
            "ten_q_debt_note_loss": int(match.group(1)),
            "nongaap_reconciliation_adjustment": bridge_value,
            "ten_q_anchor": match.group(0),
            "release_rows": debt_rows,
            "basis_note": "Separate bases; the $2M difference is not adjusted away.",
        },
        "company_defined_fq3_fy26": {
            **fcf_values,
            "component_coordinates": fcf_coordinates,
            "identities": [
                f"{fcf_values['ppe_expenditures']:.0f} - {fcf_values['ppe_disposal_proceeds']:.0f} - {fcf_values['government_incentives']:.0f} = {fcf_values['net_capex']:.0f}",
                f"{fcf_values['operating_cash_flow']:.0f} - {fcf_values['net_capex']:.0f} = {fcf_values['adjusted_free_cash_flow']:.0f}",
            ],
            "release_rows": fcf_rows,
        },
    }


def normalize_pdf_text(text: str) -> str:
    """Collapse PDF layout whitespace and restore intra-word hyphenation."""
    collapsed = " ".join(text.split())
    return re.sub(r"(?<=\w)\s*-\s*(?=\w)", "-", collapsed)


def extract_remarks(reader: EvidenceReader) -> dict[str, Any]:
    payload = reader.read_bytes(REMARKS_FY26Q3)
    pdf = PdfReader(BytesIO(payload))
    text = normalize_pdf_text(" ".join(page.extract_text() or "" for page in pdf.pages))
    anchors = []
    for pattern in (r"DRAM[^.]{0,400}\.", r"NAND[^.]{0,400}\.", r"low[- ]60s[^.]{0,200}\.", r"bit shipments[^.]{0,300}\."):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            anchors.append({"pattern": pattern, "verbatim": match.group(0)})
    product_metrics = {}
    for product, pattern in {
        "DRAM": r"DRAM revenue was.*?Bit shipments were up ([^.]+)\.\s*Prices increased in the ([^.]+)\.",
        "NAND": r"NAND revenue was.*?Bit shipments increased in the ([^.]+)\.\s*Prices increased in the ([^.]+)\.",
    }.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            raise ValueError(f"prepared-remarks categorical anchor missing: {product}")
        product_metrics[product] = {"bit_shipments": match.group(1).strip(), "pricing": match.group(2).strip()}
    return {
        "source": {"path": REMARKS_FY26Q3, "sha256": reader.allowed[REMARKS_FY26Q3], "as_of": "2026-05-28"},
        "anchors": anchors,
        "product_metrics": product_metrics,
        "policy": "Qualitative pricing and bit ranges remain verbatim categorical strings and are never numericized.",
    }


def extract_freeze_a(reader: EvidenceReader) -> dict[str, Any]:
    text = reader.read_text(FROZEN)
    lines = text.splitlines()
    header_index = next(index for index, line in enumerate(lines) if line.startswith("| | bear (**0.20**)"))
    rows = []
    for line_index in range(header_index + 2, len(lines)):
        line = lines[line_index]
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        rows.append(
            {
                "label_markdown": cells[0],
                "display_markdown": {"bear": cells[1], "base": cells[2], "bull": cells[3], "weighted": cells[4]},
                "display_text": {key: value.replace("**", "") for key, value in zip(("bear", "base", "bull", "weighted"), cells[1:], strict=True)},
                "coordinate": {"line": line_index + 1, "section": "(a-1)"},
            }
        )
    profile = GenericProfile.model_validate(yaml.safe_load(reader.read_text(PROFILE)))
    forecast = run_generic_forecast(profile)
    profile_path = {}
    for scenario, quarters in forecast.scenarios_quarterly.items():
        profile_path[scenario] = [
            {
                "quarter_label": quarter.quarter_label,
                "revenue": quarter.revenue_total,
                "operating_income": quarter.operating_profit,
                "gaap_eps": quarter.eps_diluted,
            }
            for quarter in quarters
        ]
    def markdown_rows(marker: str) -> list[list[str]]:
        marker_index = next(index for index, line in enumerate(lines) if marker in line)
        table_start = marker_index if lines[marker_index].startswith("|") else next(
            index for index in range(marker_index + 1, len(lines)) if lines[index].startswith("|")
        )
        parsed = []
        for line in lines[table_start + 2:]:
            if not line.startswith("|"):
                break
            parsed.append([cell.strip().replace("**", "") for cell in line.strip("|").split("|")])
        return parsed

    gm_history = [
        {
            "period": cells[0],
            "guidance_midpoint_pct": float(re.sub(r"[^0-9.-]", "", cells[1].replace("약 ", ""))),
            "actual_pct": float(re.sub(r"[^0-9.-]", "", cells[2])),
            "difference_pt": float(re.sub(r"[^0-9.+-]", "", cells[3]).replace("−", "-")),
        }
        for cells in markdown_rows("**GM 가이던스 대비 실적 기록")
    ]
    beat_history = []
    for cells in markdown_rows("**사후 break 10분기 가이던스 상회 기록"):
        if "집계" in cells[0]:
            continue
        beat_history.append(
            {
                "period": cells[0],
                "revenue_guidance_midpoint": float(cells[1].replace(",", "")),
                "revenue_actual": float(cells[2].replace(",", "")),
                "revenue_beat_pct": float(cells[3].replace("+", "").replace("%", "")),
                "revenue_above_high": cells[4] == "✓",
                "gaap_eps_above_high": cells[5] == "✓",
            }
        )
    annual_rows = markdown_rows("9M 실적 (FQ3 PR)")
    annual_prereg = {
        "revenue": float(annual_rows[0][3].replace(",", "")),
        "net_income": float(annual_rows[1][3].replace(",", "")),
        "diluted_eps": float(re.sub(r"[^0-9.]", "", annual_rows[2][3].split("(")[0])),
    }
    return {
        "source": {"path": FROZEN, "sha256": reader.allowed[FROZEN], "as_of": "2026-09-25", "freeze_commit": "f8cfd47"},
        "profile_source": {"path": PROFILE, "sha256": reader.allowed[PROFILE], "as_of": "2026-09-25"},
        "prereg_a_display_rows": rows,
        "profile_path_basis": "PREREG_A_PROFILE_PATH_ONLY_NOT_RLE_INPUT",
        "profile_path": profile_path,
        "gm_guidance_history": gm_history,
        "beat_history": beat_history,
        "annual_prereg": annual_prereg,
    }


def build_sources(output_dir: str | Path | None = None, write_runtime_log: bool = True) -> list[Path]:
    reader = EvidenceReader("E2-A")
    for pin in reader.pins["E2-A"]:
        reader.read_bytes(pin["path"])
    target = Path(output_dir) if output_dir else PACKAGE_DIR / "sources"
    outputs = {
        "annual_financials.json": extract_annual(reader),
        "companyfacts_quarterly.json": extract_companyfacts(reader),
        "release_tables.json": extract_releases(reader),
        "guidance_history.json": extract_guidance(reader),
        "business_units.json": extract_business_units(reader),
        "debt_fcf.json": extract_debt_and_fcf(reader),
        "prepared_remarks.json": extract_remarks(reader),
        "freeze_prereg.json": extract_freeze_a(reader),
    }
    written = []
    for name, data in outputs.items():
        path = target / name
        atomic_write(path, (json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))
        written.append(path)
    audit_path = target / "input_audit.json"
    reader.write_audit(audit_path)
    written.append(audit_path)
    if write_runtime_log:
        reader.write_runtime_log()
    return written


if __name__ == "__main__":
    for output in build_sources():
        print(output.relative_to(PACKAGE_DIR.parents[2]).as_posix())
