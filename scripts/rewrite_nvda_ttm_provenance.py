"""Atomically refresh NVDA TTM provenance from SEC Company Facts."""

from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.edgar_parser import parse_ttm_financials


def main() -> int:
    path = ROOT / "profiles" / "nvda.yaml"
    original = path.read_text(encoding="utf-8")
    parsed = parse_ttm_financials("1045810", 2026, date(2026, 7, 17))
    if parsed is None:
        raise RuntimeError("SEC TTM facts unavailable")
    values, provenance = parsed
    provenance["adjustments"] = [
        {
            "field": "adjusted_net_income",
            "value": 143451,
            "kind": "company_reported_non_gaap_rollup",
            "formula": (
                "FY2026 non-GAAP NI - Q1 FY2026 non-GAAP NI "
                "+ Q1 FY2027 non-GAAP NI"
            ),
            "components": {
                "annual": 116997,
                "prior_ytd": 19094,
                "current_ytd": 45548,
            },
            "source": "NVIDIA earnings releases furnished with Form 8-K",
        }
    ]
    block = yaml.safe_dump(
        {"ttm_provenance": provenance},
        sort_keys=False,
        allow_unicode=True,
    ).rstrip()
    refreshed, count = re.subn(
        r"(?ms)^ttm_provenance:\n.*?(?=^news_key_issues:)",
        block + "\n",
        original,
        count=1,
    )
    if count != 1:
        raise RuntimeError("ttm_provenance block boundary not found")
    refreshed = refreshed.replace("\r\n", "\n").replace("\n", "\r\n")

    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as tmp:
            tmp.write(refreshed)
            tmp.flush()
            os.fsync(tmp.fileno())
            temp_path = tmp.name
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

    delivered = path.read_bytes()
    loaded = yaml.safe_load(delivered.decode("utf-8"))
    fields = loaded["ttm_provenance"]["fields"]
    if set(fields) != {"revenue", "op", "net_income", "dep", "capex"}:
        raise RuntimeError("incomplete delivered provenance")
    if loaded["ttm_anchor"]["capex"] != values["capex"]:
        raise RuntimeError("TTM anchor/provenance mismatch")
    print(
        "atomic_write_ok",
        f"lines={len(delivered.splitlines())}",
        f"sha256={hashlib.sha256(delivered).hexdigest()}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
