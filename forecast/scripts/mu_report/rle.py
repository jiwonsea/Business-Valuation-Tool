"""Pure report-layer estimate calculations; no input/output occurs here."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import yaml
from forecast.engine.generic_forecast import run_generic_forecast
from forecast.schemas.generic import GenericProfile
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReportUnits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    money: Literal["USD_million"]
    shares: Literal["million"]
    ratio: Literal["fraction"]


class SourceCatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    role: str


class SourcedValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Any
    source_id: str | list[str]
    formula: str | None = None
    reason: str | None = None
    sensitivity: float | None = None

    @model_validator(mode="after")
    def _source_id_is_not_empty(self) -> "SourcedValue":
        if isinstance(self.source_id, list) and not self.source_id:
            raise ValueError("source_id list must not be empty")
        return self


class PostPrintChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original: SourcedValue
    change: SourcedValue
    reason: SourcedValue
    page: SourcedValue
    grade: SourcedValue


class ReportLayerAssumptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["report_layer"]
    information_cutoff: date
    information_cutoff_precision: Literal["date_only"]
    information_cutoff_timezone: Literal["Asia/Seoul"]
    sources: list[str] = Field(min_length=1)
    units: ReportUnits
    week_basis: dict[str, str]
    confidence: Literal["low"]
    input_sha256: dict[str, str]
    source_catalog: dict[str, SourceCatalogEntry]
    post_print_inputs: dict[str, SourcedValue]
    post_print_change: dict[str, PostPrintChange]
    interpretation_note: dict[str, dict[str, SourcedValue]]
    rules: dict[str, Any]

    @model_validator(mode="after")
    def _validate_contract(self) -> "ReportLayerAssumptions":
        if set(self.source_catalog) != set(self.sources):
            raise ValueError("source_catalog keys must exactly match sources")
        if set(self.post_print_change) != {"A3_base", "A4_opex", "A14_net_capex"}:
            raise ValueError("post_print_change must contain exactly A3_base, A4_opex, and A14_net_capex")
        if "A11_net_capex_roll_forward" not in self.interpretation_note:
            raise ValueError("interpretation_note must contain A11_net_capex_roll_forward")
        if set(self.week_basis) != {"FY2027", "FY2028"}:
            raise ValueError("week_basis must contain exactly FY2027 and FY2028")
        for path, sha256 in self.input_sha256.items():
            if not path or len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
                raise ValueError(f"invalid input SHA-256 pin: {path}")

        known_sources = set(self.sources)

        def validate_sourced_values(value: Any, path: str) -> None:
            if isinstance(value, dict):
                if "value" in value:
                    if "source_id" not in value:
                        raise ValueError(f"value missing source_id: {path}")
                    source_ids = value["source_id"]
                    if not isinstance(source_ids, list):
                        source_ids = [source_ids]
                    unknown = set(source_ids) - known_sources
                    if unknown:
                        raise ValueError(f"unknown source_id at {path}: {sorted(unknown)}")
                for key, child in value.items():
                    validate_sourced_values(child, f"{path}.{key}")
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    validate_sourced_values(child, f"{path}[{index}]")

        validate_sourced_values(
            {
                "post_print_inputs": {key: value.model_dump() for key, value in self.post_print_inputs.items()},
                "post_print_change": {key: value.model_dump() for key, value in self.post_print_change.items()},
                "interpretation_note": {
                    key: {note: value.model_dump() for note, value in notes.items()}
                    for key, notes in self.interpretation_note.items()
                },
                "rules": self.rules,
            },
            "assumptions",
        )
        return self


def load_assumptions_text(text: str) -> ReportLayerAssumptions:
    return ReportLayerAssumptions.model_validate(yaml.safe_load(text))


def quarterly_da_roll_forward(opening_ppe: float, net_capex: list[float], annual_rate: float) -> list[dict[str, float]]:
    """Roll PP&E forward with quarterly D&A based on average beginning/ending PP&E."""
    if opening_ppe < 0:
        raise ValueError("opening_ppe must be non-negative")
    if not net_capex:
        raise ValueError("net_capex must contain at least one quarter")
    if annual_rate < 0:
        raise ValueError("annual_rate must be non-negative")

    quarterly_rate = annual_rate / 4.0
    ppe_begin = opening_ppe
    rows: list[dict[str, float]] = []
    for capex in net_capex:
        if capex < 0:
            raise ValueError("net_capex must be non-negative")
        depreciation = quarterly_rate * (ppe_begin + capex / 2.0) / (1.0 + quarterly_rate / 2.0)
        ppe_end = ppe_begin + capex - depreciation
        rows.append(
            {
                "ppe_begin": ppe_begin,
                "net_capex": capex,
                "da": depreciation,
                "ppe_end": ppe_end,
            }
        )
        ppe_begin = ppe_end
    return rows


@dataclass(frozen=True)
class CashAssumptions:
    da: float
    sbc: float
    working_capital_change: float
    other_cfo: float
    ppe_purchases: float
    ppe_disposal_proceeds: float
    government_incentives: float
    dividends: float


def raw_growth_from_weekly(growth_weekly: float, prior_weeks: int, weeks: int) -> float:
    return (1.0 + growth_weekly) * weeks / prior_weeks - 1.0


def project_generic(profile: GenericProfile, scenario_overrides: dict[str, dict[str, Any]]):
    updated = profile
    for scenario in ("bear", "base", "bull"):
        current = getattr(updated, scenario)
        updated = updated.model_copy(update={scenario: current.model_copy(update=scenario_overrides[scenario])})
    return run_generic_forecast(updated)


def fy2027_scenario_results(assumptions: ReportLayerAssumptions) -> dict[str, dict[str, float]]:
    """Reproduce the three unweighted FY2027 RLE paths from the signed assumptions."""
    rules = assumptions.rules
    inputs = assumptions.post_print_inputs
    fq4_revenue = float(inputs["A4_fq4_fy2026_actual_revenue_14w"].value)
    shares = float(rules["A7_diluted_shares"]["quarterly_all_scenarios"]["value"][0])
    opex = [float(value) for value in rules["A4_gaap_opex"]["quarterly_all_scenarios"]["value"]]
    below_op_pct = float(rules["A5_below_operating_pct_of_revenue"]["all_scenarios"]["value"])
    results: dict[str, dict[str, float]] = {}
    for scenario in ("bear", "base", "bull"):
        revenue = [float(rules["A1_fq1_revenue"][scenario]["value"])]
        for rate in rules["A2_fq2_to_fq4_weekly_revenue_growth"][scenario]["value"]:
            revenue.append(revenue[-1] * (1.0 + float(rate)))
        margins = [float(value) for value in rules["A3_gaap_gross_margin"][scenario]["value"]]
        tax_rate = float(rules["A6_gaap_effective_tax_rate"][scenario]["value"])
        quarterly = [
            margin_bridge(sales, margin, expense, sales * below_op_pct, tax_rate, 0.0, shares)
            for sales, margin, expense in zip(revenue, margins, opex, strict=True)
        ]
        annual_revenue = sum(row["revenue"] for row in quarterly)
        annual_net_income = sum(row["net_income"] for row in quarterly)
        results[scenario] = {
            "revenue": annual_revenue,
            "net_income": annual_net_income,
            "eps_gaap": annual_net_income / shares,
            "fq4_seed_revenue": fq4_revenue,
        }
    return results


def annual_rle_results(assumptions: ReportLayerAssumptions) -> dict[str, dict[int, dict[str, float]]]:
    """Return the unweighted FY2027/FY2028 income, cash-flow, and net-cash paths."""
    rules = assumptions.rules
    inputs = assumptions.post_print_inputs
    fy2026_revenue = float(inputs["fy2026_revenue"].value)
    shares = float(rules["A7_diluted_shares"]["quarterly_all_scenarios"]["value"][0])
    below_op_pct = float(rules["A5_below_operating_pct_of_revenue"]["all_scenarios"]["value"])
    fy2027_opex = [float(value) for value in rules["A4_gaap_opex"]["quarterly_all_scenarios"]["value"]]
    fy2027_da = float(rules["A11_da"]["fy2027_total"]["value"])
    fy2027_ending_ppe = float(rules["A11_da"]["fy2027_ending_ppe"]["value"])
    fy2027_sbc = float(rules["A12_sbc"]["fy2027_total"]["value"])
    sbc_rate = float(rules["A12_sbc"]["median_rate"]["value"])
    annual_da_rate = float(rules["A11_da"]["fy2026_rate_d"]["value"])
    working_capital_k = float(rules["A13_working_capital"]["median_k"]["value"])
    dividends = float(rules["A15_dividends"]["fy2027_total"]["value"])
    opening_net_cash = float(rules["opening_net_cash_unadjusted"]["amount"]["value"])
    fy2027_net_capex = float(rules["A14_net_capex"]["fy2027_total"]["value"])
    fy2028_net_capex = float(rules["A14_net_capex"]["fy2028_total"]["value"])
    fy2028_da = sum(
        row["da"]
        for row in quarterly_da_roll_forward(
            fy2027_ending_ppe,
            [fy2028_net_capex / 4.0] * 4,
            annual_da_rate,
        )
    )
    results: dict[str, dict[int, dict[str, float]]] = {}
    for scenario in ("bear", "base", "bull"):
        revenue = [float(rules["A1_fq1_revenue"][scenario]["value"])]
        for rate in rules["A2_fq2_to_fq4_weekly_revenue_growth"][scenario]["value"]:
            revenue.append(revenue[-1] * (1.0 + float(rate)))
        margins = [float(value) for value in rules["A3_gaap_gross_margin"][scenario]["value"]]
        tax_rate = float(rules["A6_gaap_effective_tax_rate"][scenario]["value"])
        quarters = [
            margin_bridge(sales, margin, expense, sales * below_op_pct, tax_rate, 0.0, shares)
            for sales, margin, expense in zip(revenue, margins, fy2027_opex, strict=True)
        ]
        fy2027 = {key: sum(row[key] for row in quarters) for key in (
            "revenue", "cogs", "gross_profit", "opex", "operating_income", "below_op", "pretax", "tax", "net_income"
        )}
        fy2027["diluted_shares"] = shares
        fy2027["diluted_eps"] = fy2027["net_income"] / shares
        fy2027["gross_margin"] = fy2027["gross_profit"] / fy2027["revenue"]
        fy2027["operating_margin"] = fy2027["operating_income"] / fy2027["revenue"]
        fy2027["etr"] = fy2027["tax"] / fy2027["pretax"]
        fy2027["d_and_a"] = fy2027_da
        fy2027["sbc"] = fy2027_sbc
        fy2027["working_capital_investment"] = working_capital_k * (fy2027["revenue"] - fy2026_revenue)
        fy2027["operating_cash_flow"] = fy2027["net_income"] + fy2027_da + fy2027_sbc - fy2027["working_capital_investment"]
        fy2027["net_capex"] = fy2027_net_capex
        fy2027["fcf_adjusted"] = fy2027["operating_cash_flow"] - fy2027_net_capex
        fy2027["dividends"] = dividends
        fy2027["net_cash_unadjusted"] = roll_forward_net_cash(opening_net_cash, fy2027["fcf_adjusted"], dividends)
        fy2027["quarterly_revenue"] = revenue

        fy2028_revenue = fy2027["revenue"] * (1.0 + float(rules["A8_fy2028_revenue_growth"][scenario]["value"]))
        fy2028_margin = float(rules["A9_fy2028_gross_margin"][scenario]["value"])
        fy2028_opex = float(rules["A10_fy2028_opex"]["all_scenarios"]["value"])
        fy2028 = margin_bridge(
            fy2028_revenue,
            fy2028_margin,
            fy2028_opex,
            fy2028_revenue * below_op_pct,
            tax_rate,
            0.0,
            shares,
        )
        fy2028["diluted_shares"] = shares
        fy2028["diluted_eps"] = fy2028.pop("eps")
        fy2028["gross_margin"] = fy2028_margin
        fy2028["operating_margin"] = fy2028["operating_income"] / fy2028_revenue
        fy2028["etr"] = tax_rate
        fy2028["d_and_a"] = fy2028_da
        fy2028["sbc"] = fy2028_opex * sbc_rate
        fy2028["working_capital_investment"] = working_capital_k * (fy2028_revenue - fy2027["revenue"])
        fy2028["operating_cash_flow"] = fy2028["net_income"] + fy2028_da + fy2028["sbc"] - fy2028["working_capital_investment"]
        fy2028["net_capex"] = fy2028_net_capex
        fy2028["fcf_adjusted"] = fy2028["operating_cash_flow"] - fy2028_net_capex
        fy2028["dividends"] = dividends
        fy2028["net_cash_unadjusted"] = roll_forward_net_cash(fy2027["net_cash_unadjusted"], fy2028["fcf_adjusted"], dividends)
        results[scenario] = {2027: fy2027, 2028: fy2028}
    return results


def margin_bridge(revenue: float, gross_margin: float, opex: float, below_op: float, tax_rate: float, equity_method: float, shares_million: float) -> dict[str, float]:
    gross_profit = revenue * gross_margin
    cogs = revenue - gross_profit
    operating_income = gross_profit - opex
    pretax = operating_income + below_op
    tax = pretax * tax_rate
    net_income = pretax - tax + equity_method
    eps = net_income / shares_million
    return {
        "revenue": revenue,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "opex": opex,
        "operating_income": operating_income,
        "below_op": below_op,
        "pretax": pretax,
        "tax": tax,
        "equity_method": equity_method,
        "net_income": net_income,
        "eps": eps,
    }


def cash_flow(net_income: float, assumptions: CashAssumptions) -> dict[str, float]:
    operating_cash_flow = net_income + assumptions.da + assumptions.sbc - assumptions.working_capital_change + assumptions.other_cfo
    net_capex = assumptions.ppe_purchases - assumptions.ppe_disposal_proceeds - assumptions.government_incentives
    adjusted_fcf = operating_cash_flow - net_capex
    return {"operating_cash_flow": operating_cash_flow, "net_capex": net_capex, "adjusted_fcf": adjusted_fcf}


def roll_forward_net_cash(opening_net_cash: float, adjusted_fcf: float, dividends: float) -> float:
    """Before buybacks, acquisitions and debt changes; not adjusted for SCA deposits."""
    return opening_net_cash + adjusted_fcf - dividends


def inventory_days(
    inventory_begin: float | None,
    inventory_end: float | None,
    cogs: float | None,
    period_weeks: int,
    same_scope: bool = True,
) -> float | str:
    """Calculate company inventory days without normalizing a 53-week fiscal year."""
    if inventory_begin is None or inventory_end is None or cogs is None or not same_scope:
        return "UNAVAILABLE"
    if cogs <= 0:
        return "N/M"
    if period_weeks <= 0:
        raise ValueError("period_weeks must be positive")
    return ((inventory_begin + inventory_end) / 2.0) / cogs * (period_weeks * 7)
