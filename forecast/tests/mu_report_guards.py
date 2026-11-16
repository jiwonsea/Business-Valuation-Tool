"""Skip guards for the MU report tests.

The report code imports PDF libraries that the ``forecast`` extra does not
install, and most of its pinned evidence lives under gitignored ``logs/`` and
``forecast/reports/.cache/``. On a clean checkout these tests would otherwise
stop pytest at collection or fail with FileNotFoundError; the guards turn both
into skips that name what is absent.
"""

from __future__ import annotations

import pytest

_REPORT_DEPENDENCIES = ("pypdf", "weasyprint", "pdfplumber")


def require_report_dependencies() -> None:
    """Skip the importing test module when a report PDF library is not installed."""
    for name in _REPORT_DEPENDENCIES:
        pytest.importorskip(name, reason=f"MU report dependency not installed: {name}")


def require_local_evidence() -> None:
    """Skip the calling test when pinned evidence files are absent from this checkout."""
    from forecast.scripts.mu_report.inputs import REPO_ROOT, load_pins

    pinned = [
        item["path"]
        for items in load_pins().values()
        for item in items
        if item["sha256"] is not None
    ]
    missing = [path for path in pinned if not (REPO_ROOT / path).exists()]
    if missing:
        pytest.skip(
            f"MU report evidence absent (gitignored): {len(missing)} of {len(pinned)} "
            f"pinned files, first {missing[0]}"
        )
