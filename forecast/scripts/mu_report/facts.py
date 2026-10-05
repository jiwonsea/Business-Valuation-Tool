"""Canonical fact manifest used by tables, prose, charts, and both locales."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .inputs import atomic_write
from .rle import inventory_days
from .valuation import trailing_pb

UNAVAILABLE_STATUSES = {
    "UNAVAILABLE",
    "NOT_IN_SOURCE",
    "UNAVAILABLE_FOR_COMPARISON",
    "UNAVAILABLE_WITHOUT_ASSUMPTIONS",
}
FORBIDDEN_FIELDS = {
    "target_price",
    "fair_value_per_share",
    "expected_share_price",
    "probability_weighted_share_price",
    "expected_value",
    "scenario_weighted_central_value",
    "mc_mean",
}


@dataclass(frozen=True)
class Source:
    source_id: str
    title: str
    path: str
    sha256: str
    as_of: str
    accession: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class Fact:
    fact_id: str
    raw_value: float | int | str | None
    display: dict[str, str]
    unit: str
    period: str
    basis: str
    label: str
    source_id: str
    status: str = "AVAILABLE"
    lineage: dict[str, Any] | None = None
    extraction: dict[str, Any] | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class Manifest:
    facts: dict[str, Fact]
    sources: dict[str, Source]
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.facts:
            raise ValueError("manifest has no facts")
        forbidden = _forbidden_keys(self.to_dict())
        if forbidden:
            raise ValueError(f"forbidden manifest fields: {forbidden}")
        bridge = [key for key in self.facts if key.startswith("bridge.nongaap_fixed_027")]
        if bridge:
            if len(bridge) != 1:
                raise ValueError("at most one fixed +$0.27 bridge fact is allowed")
            fixed = self.facts[bridge[0]]
            if fixed.period != "FY2026Q4" or fixed.basis != "PREREG_A_ASSUMPTION":
                raise ValueError("fixed +$0.27 bridge is scoped only to FY2026Q4 PREREG_A")
        for fact in self.facts.values():
            if fact.fact_id != fact.fact_id.strip() or not fact.fact_id:
                raise ValueError("invalid fact_id")
            if fact.source_id not in self.sources:
                raise ValueError(f"unknown source_id for {fact.fact_id}: {fact.source_id}")
            if fact.status not in UNAVAILABLE_STATUSES | {"AVAILABLE", "N/M"}:
                raise ValueError(f"invalid status for {fact.fact_id}: {fact.status}")
            if fact.status == "AVAILABLE" and fact.raw_value is None:
                raise ValueError(f"available fact has no value: {fact.fact_id}")
            if fact.basis == "CALCULATED" and not fact.lineage:
                raise ValueError(f"calculated fact lacks lineage: {fact.fact_id}")
            if fact.fact_id.startswith("bridge.nongaap_fixed_027") and fact.raw_value != 0.27:
                raise ValueError("fixed bridge value must be 0.27")
        self._validate_sca_dependency()
        self._validate_debt_prepayment()

    def _validate_sca_dependency(self) -> None:
        deposits = [fact for key, fact in self.facts.items() if key.startswith("bs.sca_customer_deposits")]
        if not deposits:
            return
        deposit = deposits[0]
        dependent = [fact for fact in self.facts.values() if fact.fact_id.startswith(("bs.net_cash_ex_sca", "valuation.ev_adj"))]
        for fact in dependent:
            inputs = set((fact.lineage or {}).get("inputs", []))
            if deposit.fact_id not in inputs:
                raise ValueError(f"SCA-dependent fact does not share deposit fact: {fact.fact_id}")
            if deposit.status != "AVAILABLE" and fact.status != "UNAVAILABLE":
                raise ValueError(f"SCA-dependent fact must be unavailable: {fact.fact_id}")

    def _validate_debt_prepayment(self) -> None:
        expected = {
            "is.other_nonop_net.FY2026Q3.A": -321,
            "note.debt_prepayment_loss.FY2026Q3.A": 323,
            "bridge.debt_prepayment_adjustment.FY2026Q3.A": 325,
        }
        present = {key: self.facts[key].raw_value for key in expected if key in self.facts}
        if present and present != expected:
            raise ValueError(f"debt-prepayment bases must remain separate: {present}")

    def fact(self, fact_id: str) -> Fact:
        return self.facts[fact_id]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "sources": {key: asdict(value) for key, value in sorted(self.sources.items())},
            "facts": {key: asdict(value) for key, value in sorted(self.facts.items())},
        }

    def to_bytes(self) -> bytes:
        self.validate()
        return (json.dumps(self.to_dict(), indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")

    def write(self, path: str | Path) -> None:
        atomic_write(Path(path), self.to_bytes())

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Manifest:
        manifest = cls(
            facts={key: Fact(**value) for key, value in payload["facts"].items()},
            sources={key: Source(**value) for key, value in payload["sources"].items()},
            metadata=payload.get("metadata", {}),
        )
        manifest.validate()
        return manifest


def fixture_manifest() -> Manifest:
    source = Source(
        source_id="SRC-FIXTURE",
        title="FIXTURE — NOT REAL DATA",
        path="forecast/tests/fixtures/mu_report/fake_postprint.yaml",
        sha256="0" * 64,
        as_of="2099-01-01",
    )
    values = {
        "is.revenue.FY2026Q4.A-8K": (99999, "USD_million", "FY2026Q4", "A-8K", "Revenue"),
        "is.gross_margin.FY2026Q4.A-8K": (0.777, "ratio", "FY2026Q4", "A-8K", "Gross margin"),
        "is.operating_margin.FY2026Q4.A-8K": (0.733, "ratio", "FY2026Q4", "A-8K", "Operating margin"),
        "is.eps_gaap.FY2026Q4.PREREG_A": (30.73, "USD_per_share", "FY2026Q4", "PREREG_A", "GAAP EPS"),
        "bridge.nongaap_fixed_027.FY2026Q4": (0.27, "USD_per_share", "FY2026Q4", "PREREG_A_ASSUMPTION", "Fixed non-GAAP bridge"),
        "is.other_nonop_net.FY2026Q3.A": (-321, "USD_million", "FY2026Q3", "GAAP", "Other non-operating, net"),
        "note.debt_prepayment_loss.FY2026Q3.A": (323, "USD_million", "FY2026Q3", "10-Q_NOTE", "Debt-prepayment loss"),
        "bridge.debt_prepayment_adjustment.FY2026Q3.A": (325, "USD_million", "FY2026Q3", "NON_GAAP_RECONCILIATION", "Debt-prepayment adjustment"),
        "bs.sca_customer_deposits.FY2026Q4": (None, "USD_million", "FY2026Q4", "A-8K", "SCA customer deposits"),
        "consensus.revenue.FY2027": (None, "USD_million", "FY2027", "CONSENSUS_WEEK_BASIS_UNKNOWN", "FY2027 revenue consensus"),
        "market.price.2026-10-01.CITED": (123.45, "USD_per_share", "2026-10-01", "CITED", "Reference share price"),
        "market.shares_outstanding.CITED": (1000.0, "million_shares", "2026-09-01", "CITED", "Shares outstanding"),
        "meta.price_date.2026-10-01.CITED": ("2026-10-01", "date", "2026-10-01", "CITED", "Price date"),
        "meta.shares_date.CITED": ("2026-09-01", "date", "2026-09-01", "CITED", "Shares date"),
        "meta.equity_date.FY2026.A-8K": ("2026-09-03", "date", "FY2026", "A-8K", "Equity date"),
        "meta.fiscal_year_end.FY2026.A-8K": ("2026-09-03", "date", "FY2026", "A-8K", "Fiscal year end"),
        "bs.total_equity.FY2026.A-8K": (55555.0, "USD_million", "FY2026", "A-8K", "Total equity"),
        "bs.inventories.FY2025.A": (8888.0, "USD_million", "FY2025", "GAAP_A", "Inventories"),
        "bs.inventories.FY2026.A-8K": (9999.0, "USD_million", "FY2026", "A-8K", "Inventories"),
        "is.cogs.FY2026.A-8K": (22222.0, "USD_million", "FY2026", "A-8K", "Cost of goods sold"),
        "meta.period_weeks.FY2026.A-8K": (53, "weeks", "FY2026", "A-8K", "Fiscal period weeks"),
    }
    facts: dict[str, Fact] = {}
    for key, (value, unit, period, basis, label) in values.items():
        if key.startswith("consensus."):
            status = "UNAVAILABLE_FOR_COMPARISON"
            display = {"ko": status, "en": status}
        else:
            status = "UNAVAILABLE" if value is None else "AVAILABLE"
            display = {"ko": str(value) if value is not None else "UNAVAILABLE", "en": str(value) if value is not None else "UNAVAILABLE"}
        facts[key] = Fact(key, value, display, unit, period, basis, label, source.source_id, status)
    deposit_id = "bs.sca_customer_deposits.FY2026Q4"
    for key, label in (("bs.net_cash_ex_sca.FY2026Q4", "Net cash excluding SCA"), ("valuation.ev_adj.FY2026Q4", "Adjusted EV")):
        facts[key] = Fact(key, None, {"ko": "UNAVAILABLE", "en": "UNAVAILABLE"}, "USD_million", "FY2026Q4", "CALCULATED", label, source.source_id, "UNAVAILABLE", {"formula": key, "inputs": [deposit_id]})
    market_inputs = [
        "market.price.2026-10-01.CITED",
        "market.shares_outstanding.CITED",
    ]
    market_cap = float(facts[market_inputs[0]].raw_value) * float(facts[market_inputs[1]].raw_value)
    facts["market.market_cap.2026-10-01.CALCULATED"] = Fact(
        "market.market_cap.2026-10-01.CALCULATED",
        market_cap,
        {"ko": f"{market_cap:,.0f}", "en": f"{market_cap:,.0f}"},
        "USD_million",
        "2026-10-01",
        "CALCULATED",
        "Market capitalization",
        source.source_id,
        lineage={"formula": "market_cap_v1", "inputs": market_inputs},
    )
    inventory_inputs = [
        "bs.inventories.FY2025.A",
        "bs.inventories.FY2026.A-8K",
        "is.cogs.FY2026.A-8K",
        "meta.period_weeks.FY2026.A-8K",
    ]
    inventory_value = inventory_days(8888.0, 9999.0, 22222.0, 53)
    facts["ratio.inventory_days.FY2026.A-8K"] = Fact(
        "ratio.inventory_days.FY2026.A-8K",
        inventory_value,
        {"ko": f"{inventory_value:.1f}", "en": f"{inventory_value:.1f}"},
        "days",
        "FY2026",
        "CALCULATED",
        "Inventory days",
        source.source_id,
        lineage={"formula": "inventory_days_v1", "inputs": inventory_inputs},
    )
    for period in ("FY2027", "FY2028"):
        key = f"ratio.inventory_days.{period}.RLE"
        facts[key] = Fact(
            key,
            None,
            {"ko": "UNAVAILABLE", "en": "UNAVAILABLE"},
            "days",
            period,
            "RLE",
            "Inventory days",
            source.source_id,
            "UNAVAILABLE",
        )
    pb_inputs = [
        "market.price.2026-10-01.CITED",
        "bs.total_equity.FY2026.A-8K",
        "market.shares_outstanding.CITED",
    ]
    pb_value = trailing_pb(123.45, 55555.0, 1000.0)
    facts["val.pb_trailing.FY2026.A-8K"] = Fact(
        "val.pb_trailing.FY2026.A-8K",
        pb_value,
        {"ko": f"{pb_value:.2f}x", "en": f"{pb_value:.2f}x"},
        "multiple",
        "FY2026",
        "CALCULATED",
        "Trailing P/B",
        source.source_id,
        lineage={"formula": "trailing_pb_v1", "inputs": pb_inputs},
    )
    return Manifest(facts, {source.source_id: source}, {"fixture": True, "warning": "FIXTURE — NOT REAL DATA"})


def historical_manifest_from_extracts(source_dir: str | Path) -> Manifest:
    directory = Path(source_dir)
    annual = json.loads((directory / "annual_financials.json").read_text(encoding="utf-8"))
    sources = {
        "SRC-10K-FY25": Source("SRC-10K-FY25", "Micron FY2025 Form 10-K", annual["source"]["path"], annual["source"]["sha256"], annual["source"]["as_of"], annual["source"]["accession"]),
        "SRC-10K-FY23": Source("SRC-10K-FY23", "Micron FY2023 Form 10-K", annual["supplemental_source"]["path"], annual["supplemental_source"]["sha256"], annual["supplemental_source"]["as_of"], annual["supplemental_source"]["accession"]),
    }
    prefixes = {"income_statement": "is", "balance_sheet": "bs", "cash_flow": "cf"}
    facts: dict[str, Fact] = {}
    for period, statements in annual["years"].items():
        for statement, prefix in prefixes.items():
            source_id = "SRC-10K-FY23" if statement == "balance_sheet" and period == "FY2023A" else "SRC-10K-FY25"
            for metric, value in statements[statement].items():
                fact_id = f"{prefix}.{metric}.{period}"
                unit = "USD_per_share" if metric == "diluted_eps" else "USD_million"
                display = f"{value:,.2f}" if metric == "diluted_eps" else f"{value:,.0f}"
                facts[fact_id] = Fact(
                    fact_id,
                    value,
                    {"ko": display, "en": display},
                    unit,
                    period,
                    "GAAP_A",
                    metric.replace("_", " ").title(),
                    source_id,
                    extraction=statements["coordinates"][statement][metric],
                )
    inventory_balances = annual["inventory_balances"]
    fy22 = inventory_balances["FY2022A"]
    facts["bs.inventories.FY2022A"] = Fact(
        "bs.inventories.FY2022A",
        fy22["value"],
        {"ko": f"{fy22['value']:,.0f}", "en": f"{fy22['value']:,.0f}"},
        "USD_million",
        "FY2022A",
        "GAAP_A",
        "Inventories",
        "SRC-10K-FY23",
        extraction=fy22["coordinate"],
    )
    fy22_equity = annual["equity_balances"]["FY2022A"]
    facts["bs.total_equity.FY2022A"] = Fact(
        "bs.total_equity.FY2022A",
        fy22_equity["value"],
        {"ko": f"{fy22_equity['value']:,.0f}", "en": f"{fy22_equity['value']:,.0f}"},
        "USD_million",
        "FY2022A",
        "GAAP_A",
        "Total equity",
        "SRC-10K-FY23",
        extraction=fy22_equity["coordinate"],
    )
    for year in (2023, 2024, 2025):
        period = f"FY{year}A"
        prior_period = f"FY{year - 1}A"
        source_id = "SRC-10K-FY23" if year == 2023 else "SRC-10K-FY25"
        weeks_id = f"meta.period_weeks.{period}"
        facts[weeks_id] = Fact(
            weeks_id,
            52,
            {"ko": "52", "en": "52"},
            "weeks",
            period,
            "GAAP_A",
            "Fiscal period weeks",
            source_id,
        )
        inputs = [
            f"bs.inventories.{prior_period}",
            f"bs.inventories.{period}",
            f"is.cogs.{period}",
            weeks_id,
        ]
        value = inventory_days(
            float(facts[inputs[0]].raw_value),
            float(facts[inputs[1]].raw_value),
            float(facts[inputs[2]].raw_value),
            52,
        )
        ratio_id = f"ratio.inventory_days.FY{year}.A"
        facts[ratio_id] = Fact(
            ratio_id,
            value,
            {"ko": f"{value:.1f}", "en": f"{value:.1f}"},
            "days",
            f"FY{year}",
            "CALCULATED",
            "Inventory days",
            source_id,
            lineage={"formula": "inventory_days_v1", "inputs": inputs},
        )
        for metric, numerator_id in (
            ("gross_margin", f"is.gross_profit.{period}"),
            ("operating_margin", f"is.operating_income.{period}"),
        ):
            revenue_id = f"is.revenue.{period}"
            ratio = float(facts[numerator_id].raw_value) / float(facts[revenue_id].raw_value) * 100
            fact_id = f"ratio.{metric}.FY{year}.A"
            facts[fact_id] = Fact(
                fact_id, ratio, {"ko": f"{ratio:.1f}%", "en": f"{ratio:.1f}%"}, "percent", f"FY{year}",
                "CALCULATED", metric.replace("_", " ").title(), source_id,
                lineage={"formula": "margin_v1", "inputs": [numerator_id, revenue_id]},
            )
        pretax_id = f"is.pretax_income.{period}"
        tax_id = f"is.tax.{period}"
        etr = -float(facts[tax_id].raw_value) / float(facts[pretax_id].raw_value) * 100 if facts[pretax_id].raw_value else 0.0
        facts[f"ratio.etr.FY{year}.A"] = Fact(
            f"ratio.etr.FY{year}.A", etr, {"ko": f"{etr:.1f}%", "en": f"{etr:.1f}%"}, "percent", f"FY{year}",
            "CALCULATED", "Effective tax rate", source_id,
            lineage={"formula": "etr_v1", "inputs": [tax_id, pretax_id]},
        )
        net_cash_inputs = [
            f"bs.cash.{period}", f"bs.short_term_investments.{period}", f"bs.long_term_investments.{period}",
            f"bs.current_debt.{period}", f"bs.long_term_debt.{period}",
        ]
        net_cash = sum(float(facts[key].raw_value) for key in net_cash_inputs[:3]) - sum(
            float(facts[key].raw_value) for key in net_cash_inputs[3:]
        )
        facts[f"bs.net_cash_unadjusted.FY{year}.A"] = Fact(
            f"bs.net_cash_unadjusted.FY{year}.A", net_cash,
            {"ko": f"{net_cash:,.0f}", "en": f"{net_cash:,.0f}"}, "USD_million", f"FY{year}",
            "CALCULATED", "Net cash, unadjusted for SCA deposits", source_id,
            lineage={"formula": "net_cash_unadjusted_v1", "inputs": net_cash_inputs},
        )
        capex_id = f"cf.ppe_expenditures.{period}"
        incentive_id = f"cf.government_incentives.{period}"
        revenue_id = f"is.revenue.{period}"
        net_capex = -float(facts[capex_id].raw_value) - float(facts[incentive_id].raw_value)
        net_capex_id = f"cf.net_capex.{period}"
        facts[net_capex_id] = Fact(
            net_capex_id, net_capex, {"ko": f"{net_capex:,.0f}", "en": f"{net_capex:,.0f}"}, "USD_million",
            period, "CALCULATED", "Net capital expenditures; no disposal-proceeds line reported", source_id,
            lineage={"formula": "company_net_capex_as_filed_v1", "inputs": [capex_id, incentive_id]},
        )
        ratio = net_capex / float(facts[revenue_id].raw_value) * 100
        ratio_id = f"ratio.net_capex_revenue.FY{year}.A"
        facts[ratio_id] = Fact(
            ratio_id, ratio, {"ko": f"{ratio:.1f}%", "en": f"{ratio:.1f}%"}, "percent", f"FY{year}",
            "CALCULATED", "Net capex / revenue", source_id,
            lineage={"formula": "net_capex_revenue_v1", "inputs": [net_capex_id, revenue_id]},
        )
        ocf_id = f"cf.operating_cash_flow.{period}"
        fcf = float(facts[ocf_id].raw_value) - net_capex
        fcf_id = f"cf.fcf_adjusted.{period}"
        facts[fcf_id] = Fact(
            fcf_id, fcf, {"ko": f"{fcf:,.0f}", "en": f"{fcf:,.0f}"}, "USD_million", period,
            "CALCULATED", "Adjusted free cash flow", source_id,
            lineage={"formula": "company_adjusted_fcf_v1", "inputs": [ocf_id, net_capex_id]},
        )
        prior_equity_id = f"bs.total_equity.FY{year - 1}A"
        equity_id = f"bs.total_equity.{period}"
        net_income_id = f"is.net_income.{period}"
        roe = float(facts[net_income_id].raw_value) / ((float(facts[prior_equity_id].raw_value) + float(facts[equity_id].raw_value)) / 2) * 100
        roe_id = f"ratio.roe.FY{year}.A"
        facts[roe_id] = Fact(
            roe_id, roe, {"ko": f"{roe:.1f}%", "en": f"{roe:.1f}%"}, "percent", f"FY{year}",
            "CALCULATED", "Return on average equity", source_id,
            lineage={"formula": "roe_average_equity_v1", "inputs": [net_income_id, prior_equity_id, equity_id]},
        )
    manifest = Manifest(facts, sources, {"information_cutoff": "2026-09-25", "layer": "historical"})
    manifest.validate()
    return manifest


def dryrun_manifest_from_extracts(source_dir: str | Path) -> Manifest:
    directory = Path(source_dir)
    manifest = historical_manifest_from_extracts(directory)
    facts = manifest.facts
    sources = manifest.sources

    remarks = json.loads((directory / "prepared_remarks.json").read_text(encoding="utf-8"))
    remarks_source = remarks["source"]
    sources["SRC-REMARKS-FQ3-FY26"] = Source(
        "SRC-REMARKS-FQ3-FY26", "Micron FQ3 FY2026 prepared remarks", remarks_source["path"],
        remarks_source["sha256"], remarks_source["as_of"],
    )
    for product, metrics in remarks["product_metrics"].items():
        for metric, value in metrics.items():
            fact_id = f"qual.{product.lower()}.{metric}.FQ3-26.CITED"
            facts[fact_id] = Fact(
                fact_id, value, {"ko": value, "en": value}, "categorical", "FQ3-26", "CITED",
                f"{product} {metric.replace('_', ' ')}", "SRC-REMARKS-FQ3-FY26",
            )

    quarterly = json.loads((directory / "companyfacts_quarterly.json").read_text(encoding="utf-8"))
    quarterly_source = quarterly["source"]
    sources["SRC-COMPANYFACTS"] = Source(
        "SRC-COMPANYFACTS",
        "SEC EDGAR companyfacts",
        quarterly_source["path"],
        quarterly_source["sha256"],
        quarterly_source["as_of"],
    )
    series = quarterly["series"]
    by_metric = {name: value["quarters"] for name, value in series.items()}
    for revenue in by_metric["revenue"]:
        year = int(revenue["fy"])
        quarter = int(revenue["fp"][1])
        if year < 2023:
            continue
        period = f"FY{year}Q{quarter}"
        revenue_value = float(revenue["val"]) / 1_000_000
        revenue_id = f"is.revenue.{period}.A"
        facts[revenue_id] = Fact(
            revenue_id,
            revenue_value,
            {"ko": f"{revenue_value:,.0f}", "en": f"{revenue_value:,.0f}"},
            "USD_million",
            period,
            "GAAP_A",
            "Revenue",
            "SRC-COMPANYFACTS",
            extraction={key: revenue.get(key) for key in ("accn", "start", "end", "filed", "form")},
        )
        for metric, label in (("gross_profit", "Gross margin"), ("operating_income", "Operating margin")):
            matching = next(
                item for item in by_metric[metric]
                if int(item["fy"]) == year and item["fp"] == revenue["fp"]
            )
            numerator_id = f"is.{metric}.{period}.A"
            numerator = float(matching["val"]) / 1_000_000
            facts[numerator_id] = Fact(
                numerator_id,
                numerator,
                {"ko": f"{numerator:,.0f}", "en": f"{numerator:,.0f}"},
                "USD_million",
                period,
                "GAAP_A",
                metric.replace("_", " ").title(),
                "SRC-COMPANYFACTS",
                extraction={key: matching.get(key) for key in ("accn", "start", "end", "filed", "form")},
            )
            ratio_id = f"ratio.{metric.replace('_income', '').replace('_profit', '')}_margin.{period}.A"
            ratio = numerator / revenue_value * 100
            facts[ratio_id] = Fact(
                ratio_id,
                ratio,
                {"ko": f"{ratio:.1f}%", "en": f"{ratio:.1f}%"},
                "percent",
                period,
                "CALCULATED",
                label,
                "SRC-COMPANYFACTS",
                lineage={"formula": "margin_v1", "inputs": [numerator_id, revenue_id]},
            )

    business = json.loads((directory / "business_units.json").read_text(encoding="utf-8"))
    for record in business["records"]:
        if record["metric"] != "revenue":
            continue
        source_id = f"SRC-BU-{record['source_sha256'][:12]}"
        sources.setdefault(
            source_id,
            Source(source_id, "Micron business-unit release table", record["source_path"], record["source_sha256"], record["period"]),
        )
        fact_id = f"bu.revenue.{record['unit']}.{record['period']}.A"
        value = float(record["value"])
        facts[fact_id] = Fact(
            fact_id,
            value,
            {"ko": f"{value:,.0f}", "en": f"{value:,.0f}"},
            "USD_million",
            record["period"],
            "GAAP_A",
            record["full_name"],
            source_id,
            extraction=record["coordinate"],
        )

    guidance = json.loads((directory / "guidance_history.json").read_text(encoding="utf-8"))
    for record in guidance["guidance_records"]:
        if "gaap_eps_beat_high" not in record:
            continue
        source_id = f"SRC-GUIDANCE-{record['source_sha256'][:12]}"
        sources.setdefault(
            source_id,
            Source(source_id, "Micron quarterly outlook and actuals", record["source_path"], record["source_sha256"], record["target_period"]),
        )
        for family, value, label in (
            ("guidance.eps_gaap_high", record["gaap_eps_guidance_high"], "GAAP EPS guidance high"),
            ("actual.eps_gaap", record["gaap_eps_actual"], "Actual GAAP EPS"),
            ("beat.eps_gaap_usd", record["gaap_eps_beat_high"], "GAAP EPS versus guidance high"),
        ):
            fact_id = f"{family}.{record['target_period']}.CITED"
            facts[fact_id] = Fact(
                fact_id, value, {"ko": f"{value:.2f}", "en": f"{value:.2f}"}, "USD_per_share",
                record["target_period"], "CITED", label, source_id,
            )

    freeze = json.loads((directory / "freeze_prereg.json").read_text(encoding="utf-8"))
    freeze_source = freeze["source"]
    sources["SRC-FROZEN"] = Source(
        "SRC-FROZEN",
        "MU FY2026 Q4 frozen forecast",
        freeze_source["path"],
        freeze_source["sha256"],
        freeze_source["as_of"],
    )

    def normalized_period(period: str) -> str:
        match = re.fullmatch(r"FY(\d{2}) Q([1-4])", period)
        if not match:
            raise ValueError(f"unexpected frozen-history period: {period}")
        return f"FQ{match.group(2)}-{match.group(1)}"

    for record in freeze["gm_guidance_history"]:
        period = normalized_period(record["period"])
        for family, value, label in (
            ("guidance.gm_gaap", record["guidance_midpoint_pct"], "GAAP GM guidance midpoint"),
            ("actual.gm_gaap", record["actual_pct"], "Actual GAAP GM"),
            ("beat.gm_gaap_pt", record["difference_pt"], "GAAP GM versus guidance"),
        ):
            fact_id = f"{family}.{period}.CITED"
            facts[fact_id] = Fact(
                fact_id, value, {"ko": f"{value:.2f}%", "en": f"{value:.2f}%"}, "percentage_points",
                period, "CITED", label, "SRC-FROZEN",
            )
    for record in freeze["beat_history"]:
        period = normalized_period(record["period"])
        for family, value, unit, label in (
            ("guidance.revenue_midpoint", record["revenue_guidance_midpoint"], "USD_million", "Revenue guidance midpoint"),
            ("actual.revenue", record["revenue_actual"], "USD_million", "Actual revenue"),
            ("beat.revenue_pct", record["revenue_beat_pct"], "percent", "Revenue versus guidance midpoint"),
            ("beat.eps_above_high", int(record["gaap_eps_above_high"]), "indicator", "GAAP EPS above guidance high"),
        ):
            fact_id = f"{family}.{period}.CITED"
            display = f"{value:.2f}%" if unit == "percent" else f"{value:,.0f}"
            facts[fact_id] = Fact(fact_id, value, {"ko": display, "en": display}, unit, period, "CITED", label, "SRC-FROZEN")
    for metric, value in freeze["annual_prereg"].items():
        fact_id = f"is.{metric}.FY2026E.PREREG_A"
        display = f"{value:.2f}" if metric == "diluted_eps" else f"{value:,.0f}"
        facts[fact_id] = Fact(
            fact_id, value, {"ko": display, "en": display},
            "USD_per_share" if metric == "diluted_eps" else "USD_million", "FY2026E", "PREREG_A",
            metric.replace("_", " ").title(), "SRC-FROZEN",
        )

    debt = json.loads((directory / "debt_fcf.json").read_text(encoding="utf-8"))
    debt_source = debt["sources"][0]
    sources["SRC-PR-FQ3-FY26"] = Source(
        "SRC-PR-FQ3-FY26", "Micron FQ3 FY2026 earnings release", debt_source["path"],
        debt_source["sha256"], debt_source["as_of"],
    )
    company_fcf = debt["company_defined_fq3_fy26"]
    for metric, label in (("adjusted_free_cash_flow", "Adjusted free cash flow"), ("net_capex", "Net capital expenditures")):
        family = "fcf_adjusted" if metric == "adjusted_free_cash_flow" else "net_capex"
        value = float(company_fcf[metric])
        fact_id = f"cf.{family}.FQ3-26.A"
        facts[fact_id] = Fact(
            fact_id, value, {"ko": f"{value:,.0f}", "en": f"{value:,.0f}"}, "USD_million", "FQ3-26", "GAAP_A",
            label, "SRC-PR-FQ3-FY26", extraction=company_fcf["component_coordinates"][metric],
        )

    def prereg_number(label: str, scenario: str) -> float:
        row = next(item for item in freeze["prereg_a_display_rows"] if item["label_markdown"] == label)
        value = row["display_text"][scenario].replace(",", "").replace("+", "").replace("−", "-")
        return float(value.removesuffix("%").removesuffix("M"))

    for scenario in ("bear", "base", "bull", "weighted"):
        value = prereg_number("매출", scenario)
        fact_id = f"prereg.revenue.{scenario}.FY2026Q4.PREREG_A"
        facts[fact_id] = Fact(fact_id, value, {"ko": f"{value:,.0f}", "en": f"{value:,.0f}"}, "USD_million", "FY2026Q4", "PREREG_A", "Revenue", "SRC-FROZEN")
    eps = prereg_number("**GAAP 희석 EPS**", "base")
    facts["is.eps_gaap.FY2026Q4.PREREG_A"] = Fact(
        "is.eps_gaap.FY2026Q4.PREREG_A", eps, {"ko": f"{eps:.2f}", "en": f"{eps:.2f}"}, "USD_per_share", "FY2026Q4", "PREREG_A", "GAAP diluted EPS", "SRC-FROZEN"
    )
    facts["bridge.nongaap_fixed_027.FY2026Q4"] = Fact(
        "bridge.nongaap_fixed_027.FY2026Q4", 0.27, {"ko": "+0.27", "en": "+0.27"}, "USD_per_share", "FY2026Q4", "PREREG_A_ASSUMPTION", "Fixed non-GAAP bridge", "SRC-FROZEN"
    )

    def unavailable(
        fact_id: str,
        unit: str,
        period: str,
        basis: str,
        label: str,
        lineage: dict[str, Any] | None = None,
        raw_value: str | None = None,
    ) -> None:
        facts[fact_id] = Fact(
            fact_id,
            raw_value,
            {"ko": "UNAVAILABLE", "en": "UNAVAILABLE"},
            unit,
            period,
            basis,
            label,
            "SRC-FROZEN",
            "UNAVAILABLE",
            lineage,
        )

    unavailable("is.revenue.FY2026Q4.A-8K", "USD_million", "FY2026Q4", "A-8K", "Revenue")
    unavailable("is.gross_margin.FY2026Q4.A-8K", "percent", "FY2026Q4", "A-8K", "Gross margin")
    unavailable("is.operating_margin.FY2026Q4.A-8K", "percent", "FY2026Q4", "A-8K", "Operating margin")
    unavailable("consensus.revenue.FY2027", "USD_million", "FY2027", "CONSENSUS", "FY2027 revenue consensus")
    unavailable("bs.inventories.FY2026.A-8K", "USD_million", "FY2026", "A-8K", "Inventories")
    unavailable("ratio.inventory_days.FY2026.A-8K", "days", "FY2026", "A-8K", "Inventory days")
    unavailable("ratio.inventory_days.FY2027.RLE", "days", "FY2027", "RLE", "Inventory days")
    unavailable("ratio.inventory_days.FY2028.RLE", "days", "FY2028", "RLE", "Inventory days")
    unavailable("market.price.2026-10-01.CITED", "USD_per_share", "2026-10-01", "CITED", "Reference share price")
    unavailable("market.shares_outstanding.CITED", "million_shares", "UNAVAILABLE", "CITED", "Shares outstanding")
    unavailable("meta.price_date.2026-10-01.CITED", "date", "2026-10-01", "CITED", "Price date")
    unavailable("meta.shares_date.CITED", "date", "UNAVAILABLE", "CITED", "Shares date")
    unavailable("meta.equity_date.FY2026.A-8K", "date", "FY2026", "A-8K", "Equity date")
    unavailable("meta.fiscal_year_end.FY2026.A-8K", "date", "FY2026", "A-8K", "Fiscal year end")
    unavailable("bs.total_equity.FY2026.A-8K", "USD_million", "FY2026", "A-8K", "Total equity")
    unavailable(
        "market.market_cap.2026-10-01.CALCULATED",
        "USD_million",
        "2026-10-01",
        "CALCULATED",
        "Market capitalization",
        {"formula": "market_cap_v1", "inputs": ["market.price.2026-10-01.CITED", "market.shares_outstanding.CITED"]},
    )
    unavailable(
        "val.pb_trailing.FY2026.A-8K",
        "multiple",
        "FY2026",
        "CALCULATED",
        "Trailing P/B",
        {"formula": "trailing_pb_v1", "inputs": ["market.price.2026-10-01.CITED", "bs.total_equity.FY2026.A-8K", "market.shares_outstanding.CITED"]},
        "UNAVAILABLE",
    )
    manifest.metadata = {"information_cutoff": "2026-09-25", "layer": "DRYRUN", "fixture_values": False}
    manifest.validate()
    return manifest


def _forbidden_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        found = set(value) & FORBIDDEN_FIELDS
        for child in value.values():
            found |= _forbidden_keys(child)
        return found
    if isinstance(value, list):
        found: set[str] = set()
        for child in value:
            found |= _forbidden_keys(child)
        return found
    return set()
