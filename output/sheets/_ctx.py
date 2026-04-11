"""Shared context dataclass for Excel sheet builders."""

from dataclasses import dataclass, field

from openpyxl import Workbook

from schemas.models import ValuationInput, ValuationResult


@dataclass
class Ctx:
    """Shared context across sheet functions."""
    vi: ValuationInput
    result: ValuationResult
    wb: Workbook
    method: str
    by: int
    seg_names: dict
    seg_codes: list
    cons: dict
    years: list
    unit: str
    currency_sym: str
    sc_codes: list = field(default_factory=list)


def make_ctx(vi: ValuationInput, result: ValuationResult, wb: Workbook) -> Ctx:
    return Ctx(
        vi=vi, result=result, wb=wb,
        method=result.primary_method,
        by=vi.base_year,
        seg_names={code: info["name"] for code, info in vi.segments.items()},
        seg_codes=list(vi.segments.keys()),
        cons=vi.consolidated,
        years=sorted(vi.consolidated.keys()),
        unit=vi.company.currency_unit,
        currency_sym="원" if vi.company.market == "KR" else "$",
        sc_codes=list(vi.scenarios.keys()),
    )
