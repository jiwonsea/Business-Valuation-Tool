"""One-off: assemble the GOOGL (CIK 1652044) DERIVED companyfacts cache.

Rows transcribed from SEC companyconcept API responses fetched via the
sanctioned web tool in the Cowork sandbox (data.sec.gov is proxy-403 for direct
process traffic). Window: periods ending >= 2024-04-01 (model quarters
2024Q2..2026Q1) — the span where Alphabet's original 10-Q filings tag a
same-accession 3-month diluted-share denominator (WeightedAverageNumberOf
DilutedSharesOutstanding); earlier interim filings do not, so those quarters
cannot be built under the same-accession integrity rule and are excluded.

All quarters are POST the 20:1 split (effective 2022-07-15), so shares are on a
single basis and split_history is empty in the profile. Later filings'
comparatives are included where present; build_standalone_quarters selects the
earliest-filed accession per period. On the host, delete this file and run
pipeline.edgar_fetcher.fetch_companyfacts(1652044) for the full audited blob.
"""

import json
from pathlib import Path

# Revenue: Alphabet tags older periods under RevenueFromContractWithCustomer...
# and 2025+ under Revenues; build_standalone_quarters merges both concepts.
RCC = "RevenueFromContractWithCustomerExcludingAssessedTax"
REVENUES = "Revenues"

# (start, end, val, accn, fy, fp, form, filed)
rev_rcc = [
    ("2024-04-01", "2024-06-30", 84742000000, "0001652044-24-000079", 2024, "Q2", "10-Q", "2024-07-24"),
    ("2024-07-01", "2024-09-30", 88268000000, "0001652044-24-000118", 2024, "Q3", "10-Q", "2024-10-30"),
    ("2024-01-01", "2024-09-30", 253549000000, "0001652044-24-000118", 2024, "Q3", "10-Q", "2024-10-30"),
    ("2024-01-01", "2024-12-31", 350018000000, "0001652044-25-000014", 2024, "FY", "10-K", "2025-02-05"),
    ("2025-01-01", "2025-03-31", 90234000000, "0001652044-25-000043", 2025, "Q1", "10-Q", "2025-04-25"),
]
rev_revenues = [
    ("2024-04-01", "2024-06-30", 84742000000, "0001652044-25-000062", 2025, "Q2", "10-Q", "2025-07-24"),
    ("2024-07-01", "2024-09-30", 88268000000, "0001652044-25-000091", 2025, "Q3", "10-Q", "2025-10-30"),
    ("2024-01-01", "2024-09-30", 253549000000, "0001652044-25-000091", 2025, "Q3", "10-Q", "2025-10-30"),
    ("2024-01-01", "2024-12-31", 350018000000, "0001652044-26-000018", 2025, "FY", "10-K", "2026-02-05"),
    ("2025-01-01", "2025-03-31", 90234000000, "0001652044-26-000048", 2026, "Q1", "10-Q", "2026-04-30"),
    ("2025-04-01", "2025-06-30", 96428000000, "0001652044-25-000062", 2025, "Q2", "10-Q", "2025-07-24"),
    ("2025-07-01", "2025-09-30", 102346000000, "0001652044-25-000091", 2025, "Q3", "10-Q", "2025-10-30"),
    ("2025-01-01", "2025-09-30", 289007000000, "0001652044-25-000091", 2025, "Q3", "10-Q", "2025-10-30"),
    ("2025-01-01", "2025-12-31", 402836000000, "0001652044-26-000018", 2025, "FY", "10-K", "2026-02-05"),
    ("2026-01-01", "2026-03-31", 109896000000, "0001652044-26-000048", 2026, "Q1", "10-Q", "2026-04-30"),
]
net_income = [
    ("2024-04-01", "2024-06-30", 23619000000, "0001652044-24-000079", 2024, "Q2", "10-Q", "2024-07-24"),
    ("2024-07-01", "2024-09-30", 26301000000, "0001652044-24-000118", 2024, "Q3", "10-Q", "2024-10-30"),
    ("2024-01-01", "2024-09-30", 73582000000, "0001652044-24-000118", 2024, "Q3", "10-Q", "2024-10-30"),
    ("2024-01-01", "2024-12-31", 100118000000, "0001652044-25-000014", 2024, "FY", "10-K", "2025-02-05"),
    ("2025-01-01", "2025-03-31", 34540000000, "0001652044-25-000043", 2025, "Q1", "10-Q", "2025-04-25"),
    ("2025-04-01", "2025-06-30", 28196000000, "0001652044-25-000062", 2025, "Q2", "10-Q", "2025-07-24"),
    ("2025-07-01", "2025-09-30", 34979000000, "0001652044-25-000091", 2025, "Q3", "10-Q", "2025-10-30"),
    ("2025-01-01", "2025-09-30", 97715000000, "0001652044-25-000091", 2025, "Q3", "10-Q", "2025-10-30"),
    ("2025-01-01", "2025-12-31", 132170000000, "0001652044-26-000018", 2025, "FY", "10-K", "2026-02-05"),
    ("2026-01-01", "2026-03-31", 62578000000, "0001652044-26-000048", 2026, "Q1", "10-Q", "2026-04-30"),
]
diluted_shares = [
    ("2024-04-01", "2024-06-30", 12495000000, "0001652044-24-000079", 2024, "Q2", "10-Q", "2024-07-24"),
    ("2024-07-01", "2024-09-30", 12419000000, "0001652044-24-000118", 2024, "Q3", "10-Q", "2024-10-30"),
    ("2024-01-01", "2024-09-30", 12480000000, "0001652044-24-000118", 2024, "Q3", "10-Q", "2024-10-30"),
    ("2024-01-01", "2024-12-31", 12447000000, "0001652044-25-000014", 2024, "FY", "10-K", "2025-02-05"),
    ("2025-01-01", "2025-03-31", 12291000000, "0001652044-25-000043", 2025, "Q1", "10-Q", "2025-04-25"),
    ("2025-04-01", "2025-06-30", 12198000000, "0001652044-25-000062", 2025, "Q2", "10-Q", "2025-07-24"),
    ("2025-07-01", "2025-09-30", 12203000000, "0001652044-25-000091", 2025, "Q3", "10-Q", "2025-10-30"),
    ("2025-01-01", "2025-09-30", 12230000000, "0001652044-25-000091", 2025, "Q3", "10-Q", "2025-10-30"),
    ("2025-01-01", "2025-12-31", 12230000000, "0001652044-26-000018", 2025, "FY", "10-K", "2026-02-05"),
    ("2026-01-01", "2026-03-31", 12238000000, "0001652044-26-000048", 2026, "Q1", "10-Q", "2026-04-30"),
]
eps_diluted = [
    ("2024-04-01", "2024-06-30", 1.89, "0001652044-24-000079", 2024, "Q2", "10-Q", "2024-07-24"),
    ("2024-07-01", "2024-09-30", 2.12, "0001652044-24-000118", 2024, "Q3", "10-Q", "2024-10-30"),
    ("2024-01-01", "2024-12-31", 8.04, "0001652044-25-000014", 2024, "FY", "10-K", "2025-02-05"),
    ("2025-01-01", "2025-03-31", 2.81, "0001652044-25-000043", 2025, "Q1", "10-Q", "2025-04-25"),
    ("2025-04-01", "2025-06-30", 2.31, "0001652044-25-000062", 2025, "Q2", "10-Q", "2025-07-24"),
    ("2025-07-01", "2025-09-30", 2.87, "0001652044-25-000091", 2025, "Q3", "10-Q", "2025-10-30"),
    ("2025-01-01", "2025-12-31", 10.81, "0001652044-26-000018", 2025, "FY", "10-K", "2026-02-05"),
    ("2026-01-01", "2026-03-31", 5.11, "0001652044-26-000048", 2026, "Q1", "10-Q", "2026-04-30"),
]


def rows(data):
    out = []
    for start, end, val, accn, fy, fp, form, filed in data:
        out.append({"start": start, "end": end, "val": val, "accn": accn,
                    "fy": fy, "fp": fp, "form": form, "filed": filed})
    return out


blob = {
    "cik": 1652044,
    "entityName": "Alphabet Inc.",
    "_derived_note": (
        "DERIVED concept-slice cache (not the full companyfacts blob). Built "
        "2026-07-22 in the Cowork sandbox from SEC companyconcept API responses "
        "(data.sec.gov proxy-403 for direct process traffic; fetched via the "
        "sanctioned web tool). Rows cover periods ending >= 2024-06-30 (model "
        "quarters 2024Q2..2026Q1) plus the 9M/FY facts needed to restore 2024Q4 "
        "and 2025Q4. Earlier interim filings do not tag a same-accession 3-month "
        "diluted-share denominator, so those quarters cannot be built under the "
        "same-accession rule and are omitted. All rows are POST the 20:1 split "
        "(2022-07-15) -> one share basis, empty split_history. On the host, "
        "delete this file and run edgar_fetcher.fetch_companyfacts(1652044)."
    ),
    "facts": {
        "us-gaap": {
            RCC: {"label": "Revenue", "units": {"USD": rows(rev_rcc)}},
            REVENUES: {"label": "Revenues", "units": {"USD": rows(rev_revenues)}},
            "NetIncomeLoss": {"label": "Net Income", "units": {"USD": rows(net_income)}},
            "WeightedAverageNumberOfDilutedSharesOutstanding": {
                "label": "Diluted shares", "units": {"shares": rows(diluted_shares)}},
            "EarningsPerShareDiluted": {
                "label": "EPS diluted", "units": {"USD/shares": rows(eps_diluted)}},
        }
    },
}

path = Path("reports/.cache/edgar_companyfacts_CIK0001652044.json")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(blob, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {path} ({path.stat().st_size} bytes)")
