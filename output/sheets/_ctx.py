"""Shared context dataclass for Excel sheet builders."""

import logging
from dataclasses import dataclass, field

from engine.units import currency_symbol, display_decimals

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
    currency_decimals: int = 0

    @property
    def per_share_fmt(self) -> str:
        return "#,##0" if self.currency_decimals == 0 else "#,##0.00"


def make_ctx(vi: ValuationInput, result: ValuationResult, wb: Workbook) -> Ctx:
    if vi.company.currency not in {"KRW", "USD", "JPY", "EUR"}:
        logging.getLogger(__name__).warning(
            "미지원 통화 %s: 소수 2자리 표시", vi.company.currency
        )
    return Ctx(
        vi=vi,
        result=result,
        wb=wb,
        method=result.primary_method,
        by=vi.base_year,
        seg_names={code: info["name"] for code, info in vi.segments.items()},
        seg_codes=list(vi.segments.keys()),
        cons=vi.consolidated,
        years=sorted(vi.consolidated.keys()),
        unit=vi.company.currency_unit,
        currency_sym=currency_symbol(vi.company.currency),
        currency_decimals=display_decimals(vi.company.currency),
        sc_codes=list(vi.scenarios.keys()),
    )
