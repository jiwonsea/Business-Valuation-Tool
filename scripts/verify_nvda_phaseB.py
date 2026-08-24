"""NVDA Phase B TTM contract verification."""

from __future__ import annotations

import ast
import os
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.edgar_client import get_company_facts
from pipeline.edgar_parser import extract_quarterly_facts, parse_ttm_financials
from valuation_runner import load_profile, run_valuation


EXPECTED = {
    "revenue": 253_491,
    "op": 162_285,
    "net_income": 159_613,
    "adjusted_net_income": 143_451,
    "dep": 3_229,
    "capex": 6_553,
}


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    if not condition:
        raise AssertionError(name)


def main() -> int:
    facts = get_company_facts("1045810")
    q2 = extract_quarterly_facts(facts, ["Revenues"], 2026, "Q2", date(2026, 7, 17))
    check("B-1 reported discrete 10-Q", q2["value"] == 46_743, str(q2["value"]))

    parsed = parse_ttm_financials("1045810", 2026, date(2026, 7, 17))
    check("B-2 SEC TTM available", parsed is not None)
    auto_values, provenance = parsed
    profile = yaml.safe_load(
        (ROOT / "profiles" / "nvda.yaml").read_text(encoding="utf-8")
    )
    values = profile["ttm_anchor"]
    for field, expected in EXPECTED.items():
        actual = values[field]
        check(
            f"B-2 {field}",
            abs(actual - expected) / max(abs(expected), 1) <= 0.01,
            f"{actual:,} vs {expected:,}",
        )
    check("B-2 GAAP primary", values["net_income"] == auto_values["net_income"])

    required_fact_keys = {
        "concept",
        "unit",
        "annual",
        "prior_ytd",
        "current_ytd",
        "result",
    }
    check(
        "B-3 fact-level provenance",
        all(
            required_fact_keys <= set(field_data)
            for field_data in profile["ttm_provenance"]["fields"].values()
        ),
    )
    check("B-3 SEC accession terminology", "rcept_no" not in str(provenance))

    vi = load_profile(str(ROOT / "profiles" / "nvda.yaml"))
    check("B-4 TTM selected", vi.financial_anchor == "ttm")
    check("B-4 FY preserved", vi.fy_base_financials["revenue"] == 215_938)
    check(
        "B-4 engine consumes TTM", vi.consolidated[vi.base_year]["revenue"] == 253_491
    )

    result = run_valuation(vi)
    ttm_base = result.scenarios["Base"].post_dlom
    fy_segment_data = {
        year: {code: dict(data) for code, data in segments.items()}
        for year, segments in vi.segment_data.items()
    }
    if len(vi.segments) == 1:
        only_code = next(iter(vi.segments))
        fy_segment_data[vi.base_year][only_code].update(
            {
                "revenue": vi.fy_base_financials["revenue"],
                "op": vi.fy_base_financials["op"],
            }
        )
    fy_vi = vi.model_copy(
        update={
            "financial_anchor": "fy",
            "consolidated": {
                **vi.consolidated,
                vi.base_year: dict(vi.fy_base_financials),
            },
            "segment_data": fy_segment_data,
        }
    )
    fy_base = run_valuation(fy_vi).scenarios["Base"].post_dlom
    check(
        "B-5 same-assumption FY/TTM anchor delta",
        ttm_base > fy_base > 0,
        f"FY ${fy_base} -> TTM ${ttm_base}",
    )

    phase_a = __import__("subprocess").run(
        [sys.executable, str(ROOT / "scripts" / "verify_nvda_phaseA_v2.py")],
        cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )
    check("B-6/B-7 Phase A + Nexus invariants", phase_a.returncode == 0)

    for path in (
        ROOT / "engine" / "ttm.py",
        ROOT / "pipeline" / "edgar_parser.py",
        ROOT / "pipeline" / "profile_generator.py",
        ROOT / "valuation_runner.py",
        ROOT / "schemas" / "models.py",
    ):
        ast.parse(path.read_text(encoding="utf-8"))
    bad = [
        str(path)
        for path in ROOT.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and "__pycache__" not in path.parts
        and path.suffix in {".py", ".yaml", ".md", ".sql"}
        and b"\x00" in path.read_bytes()
    ]
    check("B-10 AST/NUL", not bad, str(bad))
    print("Phase B core verification: ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
