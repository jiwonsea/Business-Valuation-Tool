"""SEC EDGAR companyfacts client for US-issuer quarterly actuals (NVDA-1a).

Cache design (Codex-decided, REVIEW_nvidia_codex.md #2): the WHOLE companyfacts
blob is cached per CIK — one request preserves every concept plus later
filings' retroactively-adjusted comparatives, which is what makes offline
reproduction and accession-level audits possible. Concept slices are derived
in-memory, never cached separately.

    Cache: reports/.cache/edgar_companyfacts_CIK{cik:0>10}.json

Deliberately does NOT share the DART fetcher body (different auth, response
shape and rate behaviour); only the small HTTP conventions (UA, timeout,
bounded retry, atomic cache write) are re-implemented here.

Vintage discipline (NVDA-1a/1b):
- companyfacts holds BOTH the as-filed fact and later filings' retroactively
  split-adjusted comparatives for the same period. Facts are therefore always
  selected per-accession, never "first/last fact per period".
- A standalone quarter's revenue / net income / cost of revenue / diluted
  shares come from the SAME accession (the earliest filing that reports all of
  them for that period — normally the quarter's own 10-Q).
- Q4 is restored as annual − 9M. The two sides are necessarily different
  accessions (a 10-K carries no 9M column), but both are the ORIGINAL filings
  of the same fiscal year, so no disclosure vintage is mixed. Revenue/NI are
  split-invariant flows; Q4 diluted shares are derived as 4×FY − 3×9M with a
  plausibility guard against basis mixing.
- EPS facts are NEVER selected as data (old quarters may have no post-split
  comparative at all — REVIEW #1); the as-filed EPS is preserved only as a
  provenance note. Canonical EPS is derived at profile load from NI and
  split-adjusted shares (schemas/generic.py, NVDA-1c).

Fiscal↔model label contract (NVDA-1b): see :func:`model_label_for_period`.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from pipeline._ssl_setup import ensure_ssl_env

ensure_ssl_env()

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:  # dotenv optional
    pass

import httpx  # noqa: E402

logger = logging.getLogger("earnings-forecast")

CACHE_DIR = Path("reports/.cache")
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:0>10}.json"

# SEC fair-access policy requires a User-Agent with contact information.
# Override via SEC_EDGAR_USER_AGENT (e.g. in .env); the default is enough for
# cache-hit offline runs but SHOULD be personalised before live fetching.
_DEFAULT_UA = "earnings-forecast-engine/0.1 (set SEC_EDGAR_USER_AGENT in .env)"

# Fact-duration classes in days (14-week quarters and 53-week years included).
_DUR_QUARTER = (75, 105)
_DUR_9M = (250, 295)
_DUR_FY = (340, 385)

REVENUE_CONCEPTS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
)
NET_INCOME_CONCEPTS = ("NetIncomeLoss",)
COST_OF_REVENUE_CONCEPTS = ("CostOfRevenue", "CostOfGoodsAndServicesSold")
DILUTED_SHARES_CONCEPTS = ("WeightedAverageNumberOfDilutedSharesOutstanding",)
EPS_DILUTED_CONCEPTS = ("EarningsPerShareDiluted",)


def fetch_companyfacts(cik: str | int, use_cache: bool = True) -> dict:
    """Fetch (or serve from cache) the whole companyfacts blob for one CIK."""
    cik_text = f"{int(cik):010d}"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"edgar_companyfacts_CIK{cik_text}.json"
    if use_cache and cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    url = COMPANYFACTS_URL.format(cik=cik_text)
    headers = {
        "User-Agent": os.getenv("SEC_EDGAR_USER_AGENT", _DEFAULT_UA),
        "Accept-Encoding": "gzip, deflate",
    }
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = httpx.get(url, headers=headers, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            # Atomic cache write: never leave a truncated blob behind.
            tmp_path = cache_path.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp_path, cache_path)
            return data
        except Exception as exc:  # bounded retry with linear backoff
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


@dataclass(frozen=True)
class Fact:
    """One XBRL fact with its full disclosure context preserved."""

    concept: str
    unit: str
    start: date
    end: date
    val: float
    accn: str
    fy: int | None
    fp: str | None
    form: str
    filed: date
    frame: str | None

    @property
    def duration_days(self) -> int:
        return (self.end - self.start).days


def _parse_date(text: str) -> date:
    return datetime.strptime(text, "%Y-%m-%d").date()


def iter_facts(blob: dict, concepts: tuple[str, ...], taxonomy: str = "us-gaap") -> list[Fact]:
    """Flatten companyfacts entries for the given concepts, keeping all context."""
    out: list[Fact] = []
    tax = blob.get("facts", {}).get(taxonomy, {})
    for concept in concepts:
        units = tax.get(concept, {}).get("units", {})
        for unit, rows in units.items():
            for row in rows:
                if row.get("start") is None or row.get("end") is None or row.get("val") is None:
                    continue
                out.append(
                    Fact(
                        concept=concept,
                        unit=unit,
                        start=_parse_date(row["start"]),
                        end=_parse_date(row["end"]),
                        val=float(row["val"]),
                        accn=str(row.get("accn", "")),
                        fy=row.get("fy"),
                        fp=row.get("fp"),
                        form=str(row.get("form", "")),
                        filed=_parse_date(row["filed"]),
                        frame=row.get("frame"),
                    )
                )
    return out


def model_label_for_period(end: date, fiscal_year_end_month: int) -> str:
    """Map a fiscal-period END date to the model's quarter label.

    Contract (NVDA-1b): model labels are CALENDAR-quarter approximations of the
    issuer's fiscal quarters, derived from the period-end date only (the fy/fp
    tags in companyfacts describe the FILING's fiscal period, not the fact's,
    and are unreliable for labelling).

    - fiscal_year_end_month == 12 (calendar filer, e.g. TSLA):
      fiscal FY(N) Qq == model NQq (identity).
    - fiscal_year_end_month == 1 (Jan-ending filer, e.g. NVDA):
      fiscal FY(N) Qq -> model (N-1)Qq. Concretely: the fiscal quarter ending
      late Apr/early May is model Q1 of that calendar year; ... ending late
      Jan is model Q4 of the PREVIOUS calendar year (~1 month offset,
      documented in the profile notes; consensus alignment must use this map,
      never as_of calendar quarters — NVDA-2).
    """
    months_to_fye = (fiscal_year_end_month - end.month) % 12
    quarters_before_fye = round(months_to_fye / 3)
    quarter = 4 - quarters_before_fye
    if quarter < 1 or quarter > 4:
        raise ValueError(f"period end {end} does not map to a fiscal quarter (FYE month {fiscal_year_end_month})")
    year = end.year - 1 if (quarter == 4 and end.month <= 2) else end.year
    return f"{year}Q{quarter}"


def _in_range(days: int, bounds: tuple[int, int]) -> bool:
    return bounds[0] <= days <= bounds[1]


def _facts_for_period(facts: list[Fact], start: date, end: date) -> list[Fact]:
    return [f for f in facts if f.start == start and f.end == end]


def _same_accession_pick(
    period_facts_by_item: dict[str, list[Fact]],
    required: tuple[str, ...],
) -> dict[str, Fact] | None:
    """Pick one accession that reports every required item for the period.

    Accessions are tried in filed-date order, so the ORIGINAL (as-filed)
    disclosure wins whenever it carries all required line items; later
    retroactive comparatives are only reached if the original is incomplete.
    Returns None when no single accession covers all required items.
    """
    accn_filed: dict[str, date] = {}
    for item_facts in period_facts_by_item.values():
        for fact in item_facts:
            if fact.accn not in accn_filed or fact.filed < accn_filed[fact.accn]:
                accn_filed[fact.accn] = fact.filed
    for accn in sorted(accn_filed, key=lambda a: accn_filed[a]):
        picked: dict[str, Fact] = {}
        for item in required:
            candidates = [f for f in period_facts_by_item.get(item, []) if f.accn == accn]
            if not candidates:
                break
            picked[item] = candidates[0]
        else:
            # Optional items from the same accession only.
            for item, item_facts in period_facts_by_item.items():
                if item in picked:
                    continue
                candidates = [f for f in item_facts if f.accn == accn]
                if candidates:
                    picked[item] = candidates[0]
            return picked
    return None


def build_standalone_quarters(blob: dict, fiscal_year_end_month: int) -> list[dict]:
    """Assemble standalone fiscal quarters from a companyfacts blob.

    Returns rows sorted by period end, each a plain dict:
        {quarter_label, period_end, revenue, net_income, cost_of_revenue?,
         diluted_shares, eps_diluted_as_filed?, accn, form, filed, q4_derived}

    Q1–Q3 come from direct 3-month facts, all required items from one
    accession. Q4 = annual − 9M (original filings of the same fiscal year;
    see module docstring for the vintage argument). Raises when a quarter in
    the middle of the covered span cannot be built consistently — silent gaps
    are exactly the NVDA-1b defect this module exists to prevent.
    """
    items = {
        "revenue": iter_facts(blob, REVENUE_CONCEPTS),
        "net_income": iter_facts(blob, NET_INCOME_CONCEPTS),
        "cost_of_revenue": iter_facts(blob, COST_OF_REVENUE_CONCEPTS),
        "diluted_shares": iter_facts(blob, DILUTED_SHARES_CONCEPTS),
        "eps_diluted": iter_facts(blob, EPS_DILUTED_CONCEPTS),
    }
    required = ("revenue", "net_income", "diluted_shares")

    # --- Q1–Q3 (and any directly-reported Q4 comparative): direct 3M facts.
    quarter_periods = sorted(
        {(f.start, f.end) for f in items["net_income"] if _in_range(f.duration_days, _DUR_QUARTER)}
    )
    rows: list[dict] = []
    seen_labels: set[str] = set()
    for start, end in quarter_periods:
        by_item = {name: _facts_for_period(facts, start, end) for name, facts in items.items()}
        picked = _same_accession_pick(by_item, required)
        if picked is None:
            logger.warning("no single accession covers %s..%s — skipping direct quarter", start, end)
            continue
        label = model_label_for_period(end, fiscal_year_end_month)
        if label in seen_labels:
            continue  # keep the earliest-filed disclosure of a period already built
        seen_labels.add(label)
        ref = picked["net_income"]
        rows.append(
            {
                "quarter_label": label,
                "period_end": end,
                "revenue": picked["revenue"].val,
                "net_income": picked["net_income"].val,
                "cost_of_revenue": picked["cost_of_revenue"].val if "cost_of_revenue" in picked else None,
                "diluted_shares": picked["diluted_shares"].val,
                "eps_diluted_as_filed": picked["eps_diluted"].val if "eps_diluted" in picked else None,
                "accn": ref.accn,
                "form": ref.form,
                "filed": ref.filed,
                "q4_derived": False,
            }
        )

    # --- Q4 restoration: annual − 9M, original filings of the same fiscal year.
    fy_periods = sorted(
        {(f.start, f.end) for f in items["net_income"] if _in_range(f.duration_days, _DUR_FY)}
    )
    for fy_start, fy_end in fy_periods:
        label = model_label_for_period(fy_end, fiscal_year_end_month)
        if label in seen_labels:
            continue  # a direct Q4 fact already covered it
        ytd9_periods = {
            (f.start, f.end)
            for f in items["net_income"]
            if f.start == fy_start and _in_range(f.duration_days, _DUR_9M)
        }
        if not ytd9_periods:
            continue  # cannot restore this Q4 (e.g. oldest FY in the blob)
        ytd9_start, ytd9_end = sorted(ytd9_periods)[-1]

        fy_by_item = {n: _facts_for_period(f, fy_start, fy_end) for n, f in items.items()}
        ytd_by_item = {n: _facts_for_period(f, ytd9_start, ytd9_end) for n, f in items.items()}
        fy_picked = _same_accession_pick(fy_by_item, required)
        ytd_picked = _same_accession_pick(ytd_by_item, required)
        if fy_picked is None or ytd_picked is None:
            logger.warning("Q4 restoration failed for FY ending %s — missing facts", fy_end)
            continue

        fy_shares = fy_picked["diluted_shares"].val
        q4_shares = 4.0 * fy_shares - 3.0 * ytd_picked["diluted_shares"].val
        if not (0.5 * fy_shares <= q4_shares <= 2.0 * fy_shares):
            # Basis-mixing guard: FY 10-K and Q3 10-Q straddle a split.
            raise ValueError(
                f"Q4 diluted-share derivation for FY ending {fy_end} looks basis-mixed: "
                f"4×FY−3×9M = {q4_shares:,.0f} vs FY avg {fy_shares:,.0f}"
            )
        # 10-Ks sometimes carry a directly-reported Q4 EPS comparative — keep
        # it as provenance if it exists in the SAME 10-K accession.
        q4_eps_facts = [
            f
            for f in items["eps_diluted"]
            if f.end == fy_end and _in_range(f.duration_days, _DUR_QUARTER) and f.accn == fy_picked["net_income"].accn
        ]
        seen_labels.add(label)
        rows.append(
            {
                "quarter_label": label,
                "period_end": fy_end,
                "revenue": fy_picked["revenue"].val - ytd_picked["revenue"].val,
                "net_income": fy_picked["net_income"].val - ytd_picked["net_income"].val,
                "cost_of_revenue": (
                    fy_picked["cost_of_revenue"].val - ytd_picked["cost_of_revenue"].val
                    if "cost_of_revenue" in fy_picked and "cost_of_revenue" in ytd_picked
                    else None
                ),
                "diluted_shares": q4_shares,
                "eps_diluted_as_filed": q4_eps_facts[0].val if q4_eps_facts else None,
                "accn": f"{fy_picked['net_income'].accn} − {ytd_picked['net_income'].accn}",
                "form": "10-K−10-Q",
                "filed": fy_picked["net_income"].filed,
                "q4_derived": True,
            }
        )

    rows.sort(key=lambda r: r["period_end"])
    return rows
