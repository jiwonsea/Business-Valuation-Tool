"""General-purpose Excel builder -- auto-dispatch sheets by methodology.

ValuationInput + ValuationResult -> xlsx
Supported methods: sotp, dcf_primary, ddm, rim, nav, multiples

Sheet modules live in output/sheets/.
"""

import os
import re
from pathlib import Path

from openpyxl import Workbook

from schemas.models import ValuationInput, ValuationResult
from .sheets._ctx import Ctx, make_ctx
from .sheets.assumptions import sheet_assumptions
from .sheets.financials import sheet_financials
from .sheets.valuation import VALUATION_MAP, valuation_dcf
from .sheets.rnpv import valuation_rnpv
from .sheets.peers import sheet_peers
from .sheets.scenarios import sheet_scenarios
from .sheets.sensitivity import sheet_sensitivity
from .sheets.dashboard import sheet_dashboard


def export(vi: ValuationInput, result: ValuationResult, output_dir: str | None = None) -> str:
    """Create and save Excel workbook."""
    wb = Workbook()
    # Remove default empty sheet (Assumptions becomes the first sheet)
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    ctx = make_ctx(vi, result, wb)

    sheet_assumptions(ctx)
    sheet_financials(ctx)

    # Method-specific Valuation sheet
    if ctx.method == "rnpv":
        valuation_rnpv(ctx)
    else:
        VALUATION_MAP.get(ctx.method, valuation_dcf)(ctx)

    sheet_peers(ctx)
    if ctx.result.scenarios:
        sheet_scenarios(ctx)
    sheet_sensitivity(ctx)
    sheet_dashboard(ctx)

    # Save
    if output_dir is None:
        output_dir = str(Path(__file__).parent.parent)
    safe_name = re.sub(r"[^\w\s\-.,()&]", "_", vi.company.name)[:100]
    filename = f"{safe_name}_밸류에이션_모델.xlsx"
    filepath = os.path.join(output_dir, filename)
    wb.save(filepath)
    return filepath
