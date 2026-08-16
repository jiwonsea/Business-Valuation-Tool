"""Regenerate a generic profile's `actuals:` block from EDGAR companyfacts (NVDA-1).

Read-only with respect to profiles: prints the YAML block + verification report;
the block is pasted into profiles/<name>.generic.yaml by hand (assumptions stay
human-owned per CLAUDE.md workflow).

    python scripts/build_generic_actuals.py --cik 1045810 --fye-month 1  --start 2019Q3 --end 2026Q1
    python scripts/build_generic_actuals.py --cik 1318605 --fye-month 12 --start 2019Q3 --end 2026Q1

Verification (fails loudly, never emits a bad block):
- fiscal-year identity: sum of the 4 standalone quarters == the FY fact for
  revenue and net income (catches any transcription/derivation error);
- quarter-label contiguity over [start, end] (the NVDA-1b guarantee);
- NI / shares / as-filed EPS coherence per quarter (|NI/shares - eps| small,
  on the as-filed basis) where an as-filed EPS exists.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.edgar_fetcher import (  # noqa: E402
    build_standalone_quarters,
    fetch_companyfacts,
    iter_facts,
    NET_INCOME_CONCEPTS,
    REVENUE_CONCEPTS,
)


def _key(label: str) -> tuple[int, int]:
    year_text, quarter_text = label.split("Q", 1)
    return int(year_text), int(quarter_text)


def _next_label(label: str) -> str:
    year, quarter = _key(label)
    return f"{year}Q{quarter + 1}" if quarter < 4 else f"{year + 1}Q1"


def verify(rows: list[dict], blob: dict, unit_scale: float) -> list[str]:
    problems: list[str] = []

    # 1. Contiguity.
    labels = [r["quarter_label"] for r in rows]
    for prev, cur in zip(labels, labels[1:]):
        if _next_label(prev) != cur:
            problems.append(f"non-contiguous: {prev} -> {cur}")

    # 2. FY identity: 4 quarters must sum to the FY fact (rev & NI).
    fy_rev = {(f.start, f.end): f.val for f in iter_facts(blob, REVENUE_CONCEPTS) if f.duration_days > 340}
    fy_ni = {(f.start, f.end): f.val for f in iter_facts(blob, NET_INCOME_CONCEPTS) if f.duration_days > 340}
    by_label = {r["quarter_label"]: r for r in rows}
    for (fy_start, fy_end), rev_total in fy_rev.items():
        q4 = next((r for r in rows if r["period_end"] == fy_end), None)
        if q4 is None:
            continue
        year, _ = _key(q4["quarter_label"])
        quarter_labels = [f"{year}Q{q}" for q in (1, 2, 3, 4)]
        if not all(lab in by_label for lab in quarter_labels):
            continue  # window truncates this FY — identity not checkable
        rev_sum = sum(by_label[lab]["revenue"] for lab in quarter_labels)
        ni_sum = sum(by_label[lab]["net_income"] for lab in quarter_labels)
        if abs(rev_sum - rev_total) > 2e6:
            problems.append(f"FY({fy_end}) revenue identity off: {rev_sum:,.0f} != {rev_total:,.0f}")
        if abs(ni_sum - fy_ni.get((fy_start, fy_end), ni_sum)) > 2e6:
            problems.append(f"FY({fy_end}) NI identity off: {ni_sum:,.0f} != {fy_ni[(fy_start, fy_end)]:,.0f}")

    # 3. As-filed EPS coherence (same basis: as-filed shares).
    for r in rows:
        eps = r.get("eps_diluted_as_filed")
        if eps is None or not r["diluted_shares"]:
            continue
        implied = r["net_income"] / r["diluted_shares"]
        if abs(implied - eps) > max(0.03, abs(eps) * 0.03):
            problems.append(
                f"{r['quarter_label']}: as-filed EPS {eps} vs NI/shares {implied:.3f} — basis mismatch?"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure_stdout):
        reconfigure_stdout(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build generic-profile actuals from EDGAR")
    parser.add_argument("--cik", required=True, type=int)
    parser.add_argument("--fye-month", required=True, type=int)
    parser.add_argument("--start", required=True, help="first model quarter label, e.g. 2019Q3")
    parser.add_argument("--end", required=True, help="last model quarter label, e.g. 2026Q1")
    parser.add_argument("--unit", default="USD_million", choices=["USD_million", "USD"])
    args = parser.parse_args(argv)

    blob = fetch_companyfacts(args.cik)
    rows = build_standalone_quarters(blob, fiscal_year_end_month=args.fye_month)
    rows = [r for r in rows if _key(args.start) <= _key(r["quarter_label"]) <= _key(args.end)]
    scale = 1e6 if args.unit == "USD_million" else 1.0

    problems = verify(rows, blob, scale)
    if problems:
        for p in problems:
            print(f"VERIFY FAIL: {p}", file=sys.stderr)
        return 1

    print("actuals:")
    for r in rows:
        eps_note = f"as-filed EPS {r['eps_diluted_as_filed']}" if r.get("eps_diluted_as_filed") is not None else "as-filed EPS n/a"
        src = f"EDGAR {r['form']} {r['accn']} filed {r['filed']} ({eps_note}, as-filed basis)"
        print(
            "  - { "
            f"quarter_label: \"{r['quarter_label']}\", period_end: {r['period_end']}, "
            f"revenue_total: {r['revenue'] / scale:.0f}, net_profit: {r['net_income'] / scale:.0f}, "
            f"diluted_shares: {r['diluted_shares']:.0f}, "
            f"source: \"{src}\" }}"
        )
    print(f"\n# VERIFIED: {len(rows)} contiguous quarters {rows[0]['quarter_label']}..{rows[-1]['quarter_label']}; "
          "FY sum identity + as-filed EPS coherence green", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
