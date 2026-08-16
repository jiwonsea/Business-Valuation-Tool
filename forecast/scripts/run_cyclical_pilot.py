"""Run public-data cyclical driver pilots.

SEC companyfacts supplies reported quarterly revenue and net income. Operating
income is not consistently tagged across issuers, so these pilots score net
margin as the observable margin proxy. They do not mutate profiles.
"""

from __future__ import annotations

import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from engine.cyclical_drivers.calibration import expanding_driver_skill  # noqa: E402
from engine.cyclical_drivers.public_feeds import fetch_yahoo_monthly  # noqa: E402

SEC_HEADERS = {"User-Agent": "Portfolio reliability automation contact@example.com"}
PILOTS = {
    "oil_gas": {
        "company": "Chevron",
        "cik": "0000093410",
        "spread": "wti",
    },
    "steel": {
        "company": "United States Steel",
        "cik": "0001163302",
        "spread": "hrc_minus_iron_ore",
    },
}


def _quarter_label_from_frame(frame: str) -> str | None:
    if not re.fullmatch(r"CY\d{4}Q[1-4]", frame or ""):
        return None
    return frame[2:6] + "Q" + frame[-1]


def _latest_frame_values(facts: dict, tag: str) -> dict[str, float]:
    out: dict[str, tuple[str, float]] = {}
    for row in facts.get(tag, {}).get("units", {}).get("USD", []):
        label = _quarter_label_from_frame(row.get("frame", ""))
        if label is None:
            continue
        filed = str(row.get("filed", ""))
        current = out.get(label)
        if current is None or filed > current[0]:
            out[label] = (filed, float(row["val"]))
    return {label: value for label, (_, value) in out.items()}


def _companyfacts(cik: str) -> dict:
    req = urllib.request.Request(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
        headers=SEC_HEADERS,
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)["facts"]["us-gaap"]


def _quarterly_average(key: str) -> dict[str, float]:
    monthly = fetch_yahoo_monthly(key, period="10y")
    buckets: dict[str, list[float]] = defaultdict(list)
    for point in monthly:
        q = ((point.period.month - 1) // 3) + 1
        buckets[f"{point.period.year}Q{q}"].append(point.value)
    return {label: sum(values) / len(values) for label, values in buckets.items()}


def _spread_series(kind: str) -> dict[str, float]:
    if kind == "wti":
        return _quarterly_average("crude_wti")
    if kind == "hrc_minus_iron_ore":
        hrc = _quarterly_average("steel_hrc")
        ore = _quarterly_average("iron_ore_62fe")
        return {label: hrc[label] - ore[label] for label in set(hrc) & set(ore)}
    raise KeyError(kind)


def _run_one(name: str, config: dict[str, str]) -> dict:
    facts = _companyfacts(config["cik"])
    revenue = _latest_frame_values(facts, "Revenues")
    net_income = _latest_frame_values(facts, "NetIncomeLoss")
    spread = _spread_series(config["spread"])
    labels = sorted(set(revenue) & set(net_income) & set(spread))[-20:]
    margins = [net_income[label] / revenue[label] for label in labels]
    spreads = [spread[label] for label in labels]
    skill = expanding_driver_skill(spreads, margins, min_train=8)
    return {
        "pilot": name,
        "company": config["company"],
        "margin_proxy": "net_income / revenue",
        "spread": config["spread"],
        "quarters": labels,
        "n_quarters": len(labels),
        "driver_points": len(spread),
        "skill": skill.__dict__,
    }


def run() -> dict:
    return {name: _run_one(name, config) for name, config in PILOTS.items()}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
