"""Structured engine warnings, displayed without recomputing engine facts."""

import json

from engine.warnings import WARNING_ORDER

from ._ctx import Ctx
from ..excel_styles import style_header_row


def sheet_warnings(ctx: Ctx):
    ws = ctx.wb.create_sheet("경고", 0)
    ws.append(["code", "severity", "scope", "message", "fields(JSON)"])
    style_header_row(ws, 1, 5)
    for warning in sorted(
        ctx.result.engine_warnings, key=lambda w: (WARNING_ORDER.index(w.code), w.scope)
    ):
        ws.append(
            [
                warning.code,
                warning.severity,
                warning.scope,
                warning.message,
                json.dumps(warning.fields, ensure_ascii=False, sort_keys=True),
            ]
        )
    for column, width in {"A": 34, "B": 14, "C": 40, "D": 100, "E": 90}.items():
        ws.column_dimensions[column].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
