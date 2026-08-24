"""Pure trailing-twelve-month financial rollup."""

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class FactValue:
    value: int
    period_start: str
    period_end: str
    source: Mapping[str, object]


@dataclass(frozen=True)
class AnnualFacts:
    fiscal_year: int
    fields: Mapping[str, FactValue]


@dataclass(frozen=True)
class InterimYtdFacts:
    fiscal_year: int
    fiscal_period: str
    fields: Mapping[str, FactValue]


@dataclass(frozen=True)
class TTMResult:
    fields: Mapping[str, int]
    formula: str = "fy_minus_prior_ytd_plus_current_ytd"


def roll_ttm(
    annual: AnnualFacts,
    prior_ytd: InterimYtdFacts,
    current_ytd: InterimYtdFacts,
    required_fields: tuple[str, ...],
) -> TTMResult:
    """Return FY - prior comparable YTD + current YTD.

    Inputs must describe comparable fiscal periods. Missing values are rejected;
    a reported zero remains a valid value.
    """
    if prior_ytd.fiscal_period != current_ytd.fiscal_period:
        raise ValueError("prior/current YTD fiscal periods are not comparable")
    if annual.fiscal_year != prior_ytd.fiscal_year:
        raise ValueError("annual and prior YTD fiscal years are not aligned")
    if current_ytd.fiscal_year != annual.fiscal_year + 1:
        raise ValueError("current YTD must follow the confirmed annual fiscal year")

    result: dict[str, int] = {}
    for field in required_fields:
        missing = [
            label
            for label, facts in (
                ("annual", annual.fields),
                ("prior_ytd", prior_ytd.fields),
                ("current_ytd", current_ytd.fields),
            )
            if field not in facts
        ]
        if missing:
            raise ValueError(f"{field}: missing from {', '.join(missing)}")

        annual_fact = annual.fields[field]
        prior_fact = prior_ytd.fields[field]
        current_fact = current_ytd.fields[field]
        if prior_fact.period_start != annual_fact.period_start:
            raise ValueError(f"{field}: annual/prior YTD period starts differ")
        if current_fact.period_start == prior_fact.period_start:
            raise ValueError(
                f"{field}: current YTD uses the prior fiscal-year boundary"
            )
        result[field] = annual_fact.value - prior_fact.value + current_fact.value

    return TTMResult(fields=result)
