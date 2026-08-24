"""Atomically add display-only forward and peer-beta snapshots to NVDA."""

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

from pipeline.forward_estimates import collect_forward_anchor
from pipeline.peer_beta_snapshot import collect_peer_beta_snapshot

PEERS = [
    {
        "name": "Advanced Micro Devices",
        "ticker": "AMD",
        "market": "US",
        "segment_code": "MAIN",
        "core_business_match": True,
        "qualification_reason": "data-center GPU and accelerator competitor",
    },
    {
        "name": "Broadcom",
        "ticker": "AVGO",
        "market": "US",
        "segment_code": "MAIN",
        "core_business_match": True,
        "qualification_reason": "AI networking and custom accelerator semiconductor peer",
    },
    {
        "name": "Marvell Technology",
        "ticker": "MRVL",
        "market": "US",
        "segment_code": "MAIN",
        "core_business_match": True,
        "qualification_reason": "data-center networking and custom compute semiconductor peer",
    },
    {
        "name": "Intel",
        "ticker": "INTC",
        "market": "US",
        "segment_code": "MAIN",
        "core_business_match": True,
        "qualification_reason": "data-center compute and accelerator competitor",
    },
    {
        "name": "Arm Holdings",
        "ticker": "ARM",
        "market": "US",
        "segment_code": "MAIN",
        "core_business_match": True,
        "qualification_reason": "listed compute-architecture supplier exposed to data-center AI",
    },
    {
        "name": "Qualcomm",
        "ticker": "QCOM",
        "market": "US",
        "segment_code": "MAIN",
        "core_business_match": True,
        "qualification_reason": "listed fabless compute semiconductor peer",
    },
    {
        "name": "SK hynix",
        "ticker": "000660.KS",
        "market": "KR",
        "segment_code": "MAIN",
        "core_business_match": True,
    },
    {
        "name": "Samsung Electronics",
        "ticker": "005930.KS",
        "market": "KR",
        "segment_code": "MAIN",
        "core_business_match": True,
    },
]


def _replace_or_insert(text: str, key: str, block: str) -> str:
    pattern = rf"(?ms)^{re.escape(key)}:\n.*?(?=^[A-Za-z_][A-Za-z0-9_]*:|\Z)"
    if re.search(pattern, text):
        return re.sub(pattern, block + "\n", text, count=1)
    marker = "news_key_issues:"
    if marker not in text:
        raise RuntimeError("profile insertion boundary not found")
    return text.replace(marker, block + "\n" + marker, 1)


def main() -> int:
    path = ROOT / "profiles" / "nvda.yaml"
    original = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    forward = collect_forward_anchor("NVDA", date(2026, 7, 17), target_fiscal_year=2027)
    peer = collect_peer_beta_snapshot(
        PEERS,
        date(2026, 7, 11),
        company_raw_bl=2.040,
        benchmark="^GSPC",
        frequency="weekly",
        calculation_method="ols_weekly_log_returns_adjusted_close",
    )
    blocks = {
        "forward_anchor": forward.model_dump(mode="json"),
        "peer_beta_snapshot": peer.model_dump(mode="json"),
    }
    refreshed = original
    for key, value in blocks.items():
        block = yaml.safe_dump(
            {key: value}, sort_keys=False, allow_unicode=True
        ).rstrip()
        refreshed = _replace_or_insert(refreshed, key, block)
    refreshed = refreshed.replace("\n", "\r\n")

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            handle.write(refreshed)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = handle.name
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

    delivered = path.read_bytes()
    loaded = yaml.safe_load(delivered.decode("utf-8"))
    if loaded["forward_anchor"]["basis"] != "consensus_estimate":
        raise RuntimeError("delivered forward anchor lost consensus label")
    if loaded["peer_beta_snapshot"]["judgement"]["status"] != "validated":
        raise RuntimeError("delivered peer beta judgement is not validated")
    print(
        "atomic_write_ok",
        f"lines={len(delivered.splitlines())}",
        f"sha256={hashlib.sha256(delivered).hexdigest()}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
