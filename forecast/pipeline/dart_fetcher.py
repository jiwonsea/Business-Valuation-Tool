"""DART OpenAPI client for quarterly financial statements.

Cache: reports/.cache/dart_{corp_code}_{year}_{reprt_code}.json
Amounts returned to the engine are KRW billions.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import date
from pathlib import Path

from pipeline._ssl_setup import ensure_ssl_env
from schemas.models import QuarterlyActual, SegmentForecast

ensure_ssl_env()

# Load DART_API_KEY (and peers) from the repo-root .env so ANY entry point that
# triggers a DART fetch sees the key — including the otherwise-offline generic
# profile generator, whose CLI does not call load_dotenv itself. Existing env
# vars win (load_dotenv does not override), so a host-set key is respected.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:  # dotenv optional; host may set the key directly
    pass

import httpx  # noqa: E402

logger = logging.getLogger("earnings-forecast")

CACHE_DIR = Path("reports/.cache")
API_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"

REPRT_CODE_Q1 = "11013"
REPRT_CODE_H1 = "11012"
REPRT_CODE_Q3 = "11014"
REPRT_CODE_ANNUAL = "11011"
REPRT_CODES_BY_QUARTER = {
    1: REPRT_CODE_Q1,
    2: REPRT_CODE_H1,
    3: REPRT_CODE_Q3,
    4: REPRT_CODE_ANNUAL,
}


def fetch_quarterly_financials(
    corp_code: str,
    year: int,
    reprt_code: str,
    use_cache: bool = True,
) -> dict:
    """Fetch a single fnlttSinglAcntAll.json response."""
    api_key = os.getenv("DART_API_KEY")
    if not api_key:
        raise RuntimeError("DART_API_KEY env var is required")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"dart_{corp_code}_{year}_{reprt_code}.json"
    if use_cache and cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": str(year),
        "reprt_code": reprt_code,
        "fs_div": "CFS",
    }
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = httpx.get(API_URL, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            if data.get("status") not in (None, "000"):
                raise RuntimeError(f"DART API error {data.get('status')}: {data.get('message')}")
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return data
        except Exception as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def fetch_quarterly_actuals_series(
    corp_code: str,
    start_year: int,
    end_year: int,
    segment_revenue_split: dict[str, float],
    use_cache: bool = True,
    skip_unavailable: bool = False,
) -> list[QuarterlyActual]:
    """Fetch annual/interim reports and return standalone quarterly actuals.

    DART CIS thstrm_amount is already standalone for Q1, H1(Q2) and Q3.
    Q4 is decomposed as annual thstrm_amount minus Q3 thstrm_add_amount.

    skip_unavailable: when True, a quarter whose report cannot be fetched (e.g.
    a not-yet-filed future quarter probed from an offline sandbox where only
    cached reports resolve) is skipped with a LOUD warning instead of raising.
    Intended for read-only diagnostics / tests; production cli keeps the default
    (raise) so a live data failure is never silently absorbed.
    """
    actuals: list[QuarterlyActual] = []
    for year in range(start_year, end_year + 1):
        raws: dict[int, dict] = {}
        for quarter, reprt_code in REPRT_CODES_BY_QUARTER.items():
            try:
                raws[quarter] = fetch_quarterly_financials(corp_code, year, reprt_code, use_cache=use_cache)
            except RuntimeError as exc:
                message = str(exc)
                if "DART API error 013" in message or "No data" in message:
                    continue
                if skip_unavailable:
                    logger.warning("skipping %sQ%s: %s", year, quarter, exc)
                    continue
                raise
            except Exception as exc:
                if skip_unavailable:
                    logger.warning("skipping %sQ%s: %s", year, quarter, exc)
                    continue
                raise

        for quarter in (1, 2, 3):
            raw = raws.get(quarter)
            if raw is None:
                continue
            actuals.append(
                QuarterlyActual.model_validate(
                    extract_quarterly_actual(raw, f"{year}Q{quarter}", segment_revenue_split=segment_revenue_split)
                )
            )

        if 4 in raws and 3 in raws:
            actuals.append(
                QuarterlyActual.model_validate(
                    extract_quarterly_actual(
                        raws[4],
                        f"{year}Q4",
                        q3_raw_dart=raws[3],
                        segment_revenue_split=segment_revenue_split,
                    )
                )
            )

    return sorted(actuals, key=lambda item: item.period_end)


def extract_quarterly_actual(
    raw_dart: dict,
    quarter_label: str,
    q3_raw_dart: dict | None = None,
    segment_revenue_split: dict[str, float] | None = None,
) -> dict:
    """Map a DART report response to a QuarterlyActual dict."""
    rows = [row for row in raw_dart.get("list", []) if row.get("sj_div") in ("IS", "CIS")]
    if not rows:
        raise KeyError("no IS/CIS rows in DART response")

    def amount(row: dict, field: str = "thstrm_amount", *, krw_billions: bool = True) -> float | None:
        value = row.get(field)
        if value in (None, "", "-"):
            return None
        numeric = float(str(value).replace(",", ""))
        return numeric / 1_000_000_000.0 if krw_billions else numeric

    def find_by_ids(source_rows: list[dict], ids: set[str], names: tuple[str, ...] = ()) -> dict:
        for row in source_rows:
            if row.get("account_id") in ids:
                return row
        for row in source_rows:
            name = str(row.get("account_nm", ""))
            if any(token in name for token in names):
                return row
        raise KeyError(f"missing line item: {ids or names}")

    def line_amount(ids: set[str], names: tuple[str, ...] = ()) -> float:
        if quarter_label.endswith("Q4"):
            if q3_raw_dart is None:
                raise ValueError("Q4 extraction requires q3_raw_dart")
            q3_rows = [row for row in q3_raw_dart.get("list", []) if row.get("sj_div") in ("IS", "CIS")]
            annual = amount(find_by_ids(rows, ids, names), "thstrm_amount")
            nine_month = amount(find_by_ids(q3_rows, ids, names), "thstrm_add_amount")
            if annual is None or nine_month is None:
                raise KeyError(f"required Q4 decomposition amount is empty: {ids or names}")
            return annual - nine_month
        current = amount(find_by_ids(rows, ids, names), "thstrm_amount")
        if current is None:
            raise KeyError(f"required amount is empty: {ids or names}")
        return current

    def eps_amount(ids: set[str], names: tuple[str, ...] = ()) -> float | None:
        try:
            row = find_by_ids(rows, ids, names)
        except KeyError:
            return None
        if quarter_label.endswith("Q4"):
            if q3_raw_dart is None:
                return None
            q3_rows = [q3 for q3 in q3_raw_dart.get("list", []) if q3.get("sj_div") in ("IS", "CIS")]
            try:
                q3_row = find_by_ids(q3_rows, ids, names)
            except KeyError:
                return None
            annual = amount(row, "thstrm_amount", krw_billions=False)
            nine_month = amount(q3_row, "thstrm_add_amount", krw_billions=False)
            if annual is None or nine_month is None:
                return None
            return annual - nine_month
        return amount(row, "thstrm_amount", krw_billions=False)

    revenue = line_amount({"ifrs-full_Revenue"}, ("매출", "Revenue"))
    gross_profit = line_amount({"ifrs-full_GrossProfit"}, ("매출총이익", "Gross"))
    op = line_amount({"dart_OperatingIncomeLoss"}, ("영업", "Operating"))
    ni = line_amount(
        {"ifrs-full_ProfitLoss", "ifrs-full_ProfitLossAttributableToOwnersOfParent"},
        ("당기", "분기순이익", "Profit"),
    )
    eps_basic = eps_amount({"ifrs-full_BasicEarningsLossPerShare"}, ("기본주당", "Basic"))
    eps_diluted = eps_amount({"ifrs-full_DilutedEarningsLossPerShare"}, ("희석주당", "Diluted"))

    split = segment_revenue_split or {"unallocated": 1.0}
    split_total = sum(split.values())
    if abs(split_total - 1.0) > 1e-6:
        raise ValueError(f"segment_revenue_split must sum to 1.0, got {split_total}")

    year = int(quarter_label[:4])
    quarter = int(quarter_label[-1])
    month = quarter * 3
    period_end = date(year, month, 31 if month in {3, 12} else 30)
    actual = QuarterlyActual(
        quarter_label=quarter_label,
        period_end=period_end,
        revenue_total=revenue,
        revenue_by_segment=[
            SegmentForecast(segment_id=segment_id, revenue=revenue * share)
            for segment_id, share in split.items()
        ],
        gross_profit=gross_profit,
        operating_profit=op,
        net_profit=ni,
        eps_basic=eps_basic,
        eps_diluted=eps_diluted if eps_diluted is not None else eps_basic,
    )
    return actual.model_dump()
