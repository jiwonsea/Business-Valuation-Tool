"""General-purpose Excel builder -- auto-dispatch sheets by methodology.

ValuationInput + ValuationResult -> xlsx
Supported methods: sotp, dcf_primary, ddm, rim, nav, multiples

Sheet modules live in output/sheets/.
"""

import os
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from schemas.models import ValuationInput, ValuationResult
from .sheets._ctx import make_ctx
from .sheets._guide import apply_guides
from .sheets.assumptions import sheet_assumptions
from .sheets.raw_data import sheet_raw_data
from .sheets.financials import sheet_financials
from .sheets.valuation import VALUATION_MAP, valuation_dcf
from .sheets.rnpv import valuation_rnpv
from .sheets.peers import sheet_peers
from .sheets.scenarios import sheet_scenarios
from .sheets.sensitivity import sheet_sensitivity
from .sheets.dashboard import sheet_dashboard
from .sheets.relative import sheet_relative
from .sheets.history import sheet_valuation_history


def export(
    vi: ValuationInput,
    result: ValuationResult,
    output_dir: str | None = None,
    band_reports: list | None = None,
    band_current: dict | None = None,
) -> str:
    """Create and save Excel workbook.

    band_reports (opt-in, --band --excel only): historical LTM multiple bands
    (schemas.point_in_time.HistoricalBand). Default None keeps the workbook
    unchanged (Phase 2 §7.1 #8 — reporting-only, not a valuation input).
    """
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
    sheet_relative(ctx)
    if band_reports:
        from .sheets.band import sheet_historical_band

        sheet_historical_band(ctx, band_reports, band_current)
    sheet_valuation_history(ctx)
    sheet_dashboard(ctx)

    # Raw Data goes LAST in build order but FIRST in tab order (create_sheet index 0).
    # It must not be built first: sheet_assumptions() claims wb.active, which would
    # rename the Raw Data sheet to "Assumptions".
    sheet_raw_data(ctx)

    # Per-sheet "build it yourself" notes -- written into reserved blank rows, so
    # no insert_rows() and no broken conditional formatting / chart anchors.
    apply_guides(wb)

    if vi.draft or result.draft:
        warning = wb.create_sheet("DRAFT WARNING", 0)
        warning["A1"] = "DRAFT / NOT FOR PUBLICATION"
        warning["A2"] = "Assumptions are not fully verified; publication is blocked."
        warning["A1"].font = Font(bold=True, color="FFFFFF", size=16)
        warning["A1"].fill = PatternFill("solid", fgColor="C00000")
        warning.column_dimensions["A"].width = 72

    # Save
    if output_dir is None:
        output_dir = str(Path(__file__).parent.parent)
    safe_name = re.sub(r"[^\w\s\-.,()&]", "_", vi.company.name)[:100]
    filename = f"{safe_name}_밸류에이션_모델.xlsx"
    filepath = os.path.join(output_dir, filename)
    wb.save(filepath)
    return filepath
