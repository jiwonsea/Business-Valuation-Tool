"""P1 multi-year point-in-time assembly + P2 LTM multiple observations (IO).

Contract (HANDOFF_CODEX_phase2_impl_scope_2026-07-18 §2/§7, no relaxation):

- Financial values flow ONLY through the parser contract:
  extract_reported_values (basis separation) + select_point_in_time
  (original-only, available_at<=t, missing stays missing). The legacy
  parse_financial_statements / ACCOUNT_MAP dict path is never consumed here.
- Stage-1 data source is the pilot snapshot
  (research/pilot_v2/raw_payloads.json — Samsung Electronics / SK hynix /
  LG Electronics x FY2016-2025). NO automatic DART network calls: if the
  snapshot does not cover the company, the band is skipped with a warning
  (§7-2). New-company collection is Phase 2b (§6-4 quota contract).
- Price = raw close (auto_adjust=False) on the latest trading day <= t within
  PRICE_SEARCH_WINDOW_DAYS calendar days; post-t prices are look-ahead and
  never consumed. Every exclusion carries a mechanical reason
  (PriceExclusionReason / missing accounts / fixed note) — §7-4.
- Output feeds engine/multiple_band.py (pure) and reporting only. It is not
  a valuation input.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Optional, Sequence

from engine.multiple_band import build_band
from pipeline.dart_parser import extract_reported_values
from schemas.point_in_time import (
    EXCLUSION_NOTE_DENOMINATOR_NON_POSITIVE,
    PRICE_SEARCH_WINDOW_DAYS,
    ExcludedYear,
    HistoricalBand,
    MultipleObservation,
    PriceExclusionReason,
    ReportedFinancialValue,
    select_point_in_time,
)

logger = logging.getLogger(__name__)

# ── Stage-1 pilot scope (snapshot-backed only) ──

PILOT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent
    / "research"
    / "pilot_v2"
    / "raw_payloads.json"
)

# KR ticker -> (snapshot company key, Yahoo Finance ticker). Stage-1 only:
# these are the three pilot companies the offline snapshot covers.
PILOT_TICKER_MAP: dict[str, tuple[str, str]] = {
    "005930": ("Samsung Electronics", "005930.KS"),
    "000660": ("SK hynix", "000660.KS"),
    "066570": ("LG Electronics", "066570.KS"),
}

# Normalized company-name aliases -> KR ticker (mechanical lookup, no fuzzy).
PILOT_NAME_ALIASES: dict[str, str] = {
    "삼성전자": "005930",
    "samsung electronics": "005930",
    "sk하이닉스": "000660",
    "sk hynix": "000660",
    "에스케이하이닉스": "000660",
    "lg전자": "066570",
    "lg electronics": "066570",
}

# Multiple label -> denominator account (parser-contract internal keys).
_LABEL_DENOMINATOR: dict[str, str] = {"P/B": "equity", "P/S": "revenue"}

# Fixed mechanical note strings (grep-able) for non-price exclusions.
NOTE_NO_RCEPT_NO = "payload_missing_rcept_no"

# PriceProvider: (yahoo_ticker, start, end) ->
#   (raw closes by trading day within [start, end], split dates within
#    [start, end]). closes must be raw (auto_adjust=False). splits=None means
#   the source cannot establish the corporate-action basis at all -> every
#   year in that window is excluded with SHARES_BASIS_MISMATCH (§7-4).
PriceProvider = Callable[
    [str, date, date], tuple[dict[date, float], Optional[list[date]]]
]


def _parse_history_frame(
    hist, start: date, end: date
) -> tuple[dict[date, float], Optional[list[date]]]:
    """(closes, splits) from ONE successful history(actions=True) response.

    §10 contract (Codex 보류 조건 2): prices and corporate actions come from
    the SAME fetch, so a source failure is distinguishable from "no splits":
      - empty/absent frame        -> ({}, None)  : source failure — no prices
        AND no action basis (fail-closed, never "known empty");
      - frame without the "Stock Splits" column -> (closes, None): the source
        cannot establish the action basis for this window;
      - "Stock Splits" present    -> (closes, [dates with non-zero ratio]);
        an all-zero column is a KNOWN-empty split history.
    """
    if hist is None or getattr(hist, "empty", True):
        return {}, None
    closes: dict[date, float] = {}
    for idx, row in hist.iterrows():
        d = idx.date()
        if start <= d <= end:
            c = row.get("Close")
            if c is not None and c == c:  # NaN guard
                closes[d] = float(c)
    if "Stock Splits" not in hist.columns:
        return closes, None
    splits: list[date] = []
    for idx, row in hist.iterrows():
        d = idx.date()
        v = row.get("Stock Splits")
        if start <= d <= end and v is not None and v == v and float(v) != 0.0:
            splits.append(d)
    return closes, splits


def yfinance_price_provider(
    ticker: str, start: date, end: date
) -> tuple[dict[date, float], Optional[list[date]]]:
    """Default provider: yfinance raw close (auto_adjust=False) + splits from
    the SAME history(actions=True) call (§10 — single fetch, shared basis).

    Imports stay inside the function: offline callers (tests, sandbox) inject
    their own provider and must not pay the yfinance import. _ssl_fix must
    precede any yfinance/curl_cffi import (repo rule — non-ASCII Windows user
    paths break curl's CA bundle, curl error 77); cli.py applies it for CLI
    runs, this covers direct provider calls.
    """
    try:
        import _ssl_fix  # noqa: F401, PLC0415 — must precede yfinance import
    except ImportError:
        pass
    import yfinance as yf  # noqa: PLC0415 — deliberate lazy import

    try:
        hist = yf.Ticker(ticker).history(
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),  # yfinance end exclusive
            auto_adjust=False,
            actions=True,
        )
    except Exception:  # noqa: BLE001 — source failure: no prices, no basis
        return {}, None
    return _parse_history_frame(hist, start, end)


def _resolve_price(closes: dict[date, float], t: date) -> Optional[tuple[date, float]]:
    """Latest raw close on a trading day <= t within the 7-calendar-day window.

    Post-t prices are look-ahead and never considered (§7-4).
    """
    window_start = t - timedelta(days=PRICE_SEARCH_WINDOW_DAYS)
    eligible = [d for d in closes if window_start <= d <= t]
    if not eligible:
        return None
    d = max(eligible)
    return d, closes[d]


def _shares_outstanding(stock_year: Optional[dict]) -> Optional[int]:
    """발행보통주 - 자기보통주 from the filing's stockTotqySttus payload.

    Mechanical: ordinary shares only (the observed price is the ordinary
    line); preferred handling is out of stage-1 scope. Missing or non-positive
    -> None (caller excludes with SHARES_BASIS_MISSING).
    """
    if not stock_year:
        return None
    shares = stock_year.get("shares") or {}
    ordinary = shares.get("shares_ordinary")
    treasury = shares.get("treasury_ordinary")
    if ordinary is None or treasury is None:
        return None
    out = int(ordinary) - int(treasury)
    return out if out > 0 else None


def load_pilot_snapshot(path: Optional[Path] = None) -> Optional[dict]:
    """Load the offline pilot snapshot; None (with warning) when absent.

    Absent snapshot NEVER triggers a network fallback (§7-2).
    """
    p = path or PILOT_SNAPSHOT_PATH
    if not p.exists():
        logger.warning(
            "[band] 스냅샷 없음(%s) — 네트워크 수집은 하지 않습니다(§7-2). 밴드 생략.",
            p,
        )
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def resolve_pilot_company(
    name: Optional[str] = None, ticker: Optional[str] = None
) -> Optional[tuple[str, str]]:
    """(snapshot key, yahoo ticker) for a pilot company; None if out of scope."""
    if ticker:
        hit = PILOT_TICKER_MAP.get(ticker.strip().upper().replace(".KS", ""))
        if hit:
            return hit
    if name:
        t = PILOT_NAME_ALIASES.get(name.strip().lower())
        if t:
            return PILOT_TICKER_MAP[t]
    return None


def extract_company_values(
    company_payload: dict,
) -> tuple[list[ReportedFinancialValue], dict[int, tuple[str, date]]]:
    """All ReportedFinancialValues for a snapshot company + per-FY filing time.

    Returns (pool, {fiscal_year: (rcept_no, available_at)}). Years whose
    payload has no rcept_no are absent from the map (caller excludes with
    NOTE_NO_RCEPT_NO — no available_at means no point-in-time participation).
    """
    pool: list[ReportedFinancialValue] = []
    filing_at: dict[int, tuple[str, date]] = {}
    for year_str, payload in sorted(company_payload.get("financial", {}).items()):
        year = int(year_str)
        items = payload.get("items") or []
        try:
            values = extract_reported_values(items, year)
        except ValueError:
            continue  # no rcept_no -> year mechanically excluded by caller
        pool.extend(values)
        originals = [v for v in values if v.basis == "original"]
        if originals:
            filing_at[year] = (originals[0].rcept_no, originals[0].available_at)
    return pool, filing_at


def fetch_price_data(
    price_provider: PriceProvider,
    yahoo_ticker: str,
    filing_at: dict[int, tuple[str, date]],
) -> tuple[dict[date, float], Optional[list[date]]]:
    """ONE provider call covering every filing date's search window.

    §10 contract (Codex 보류 조건 1): exactly one fetch per company; the
    result is shared by every label (P/B·P/S). No filings -> ({}, []) with no
    provider call at all (known-empty basis: nothing to price).

    §11: the span extends THROUGH TODAY, not just to the last filing date —
    a split occurring after the last filing still retroactively adjusts every
    historical Yahoo close, so the corporate-action basis must be known up to
    the retrieval date. Closes after each filing's t remain unconsumed
    (_resolve_price's d <= t gate).
    """
    t_values = [at for _, at in filing_at.values()]
    if not t_values:
        return {}, []
    span_start = min(t_values) - timedelta(days=PRICE_SEARCH_WINDOW_DAYS)
    span_end = max(max(t_values), date.today())
    return price_provider(yahoo_ticker, span_start, span_end)


def build_observations(
    label: str,
    company_key: str,
    company_payload: dict,
    price_data: tuple[dict[date, float], Optional[list[date]]],
) -> tuple[list[MultipleObservation], list[ExcludedYear]]:
    """Point-in-time LTM multiple observations for one pilot company.

    Per FY annual report: t = receipt date; denominator = original FY value
    via select_point_in_time at t; shares = 발행-자기 of the same filing;
    price = raw close <= t (7-day window) from the company-level price_data
    (fetch_price_data — one provider call shared across labels, §10). Every
    failed year is recorded with its mechanical exclusion reason — never
    silently dropped, never imputed. splits=None means the price source could
    not establish the corporate-action basis (source failure included) — every
    priced year is then excluded with SHARES_BASIS_MISMATCH, fail-closed.

    Exclusion order (mechanical, deterministic): no-rcept -> denominator
    missing -> denominator non-positive -> shares missing -> action basis
    unknown -> split after FYE (§11 retroactive-adjustment guard) -> no price
    in window.
    """
    denominator_account = _LABEL_DENOMINATOR[label]  # KeyError = out of scope
    pool, filing_at = extract_company_values(company_payload)
    stock = company_payload.get("stock", {})
    years = sorted(int(y) for y in company_payload.get("financial", {}))

    if not years:
        return [], []

    closes, splits = price_data

    observations: list[MultipleObservation] = []
    excluded: list[ExcludedYear] = []

    for fy in years:
        if fy not in filing_at:
            excluded.append(ExcludedYear(fiscal_year=fy, note=NOTE_NO_RCEPT_NO))
            continue
        rcept_no, t = filing_at[fy]

        chosen = select_point_in_time(pool, denominator_account, fy, t)
        if chosen is None:  # missing stays missing (§7.2-5)
            excluded.append(
                ExcludedYear(fiscal_year=fy, missing_accounts=(denominator_account,))
            )
            continue
        if chosen.value_mkrw <= 0:
            excluded.append(
                ExcludedYear(
                    fiscal_year=fy, note=EXCLUSION_NOTE_DENOMINATOR_NON_POSITIVE
                )
            )
            continue

        shares = _shares_outstanding(stock.get(str(fy)))
        if shares is None:
            excluded.append(
                ExcludedYear(
                    fiscal_year=fy,
                    price_reason=PriceExclusionReason.SHARES_BASIS_MISSING,
                )
            )
            continue

        if splits is None:  # action basis unknowable -> mismatch (§7-4)
            excluded.append(
                ExcludedYear(
                    fiscal_year=fy,
                    price_reason=PriceExclusionReason.SHARES_BASIS_MISMATCH,
                )
            )
            continue

        # §11 (Codex 실측 결함): Yahoo historical closes are RETROACTIVELY
        # split-adjusted even with auto_adjust=False, while DART share counts
        # are on the fiscal-year-end basis. Any split AFTER this FY's year-end
        # therefore puts price (post-split basis) and shares (pre-split basis)
        # on different bases — ~50x distortion observed on Samsung FY2016-17
        # (2018-05 50:1 split). Fail-closed: exclude the year. Splits at or
        # before FYE are consistent (shares already post-split). Stage-1
        # mechanical assumption: Dec-31 fiscal year end (true for all three
        # pilot companies).
        fye = date(fy, 12, 31)
        if any(s > fye for s in splits):
            excluded.append(
                ExcludedYear(
                    fiscal_year=fy,
                    price_reason=PriceExclusionReason.SPLIT_ADJUSTMENT_DETECTED,
                )
            )
            continue

        resolved = _resolve_price(closes, t)
        if resolved is None:
            excluded.append(
                ExcludedYear(
                    fiscal_year=fy,
                    price_reason=PriceExclusionReason.NO_PRICE_WITHIN_WINDOW,
                )
            )
            continue
        price_date, close = resolved

        market_cap_mkrw = close * shares / 1_000_000
        observations.append(
            MultipleObservation(
                label=label,
                company=company_key,
                fiscal_year=fy,
                t=t,
                price_date=price_date,
                price_close_raw_krw=close,
                shares_outstanding=shares,
                market_cap_mkrw=market_cap_mkrw,
                denominator_mkrw=chosen.value_mkrw,
                multiple=market_cap_mkrw / chosen.value_mkrw,
                rcept_no=rcept_no,
            )
        )

    return observations, excluded


def build_band_reports(
    company_name: Optional[str] = None,
    ticker: Optional[str] = None,
    labels: Sequence[str] = ("P/B", "P/S"),
    price_provider: Optional[PriceProvider] = None,
    snapshot_path: Optional[Path] = None,
) -> Optional[list[HistoricalBand]]:
    """Historical LTM P/B·P/S bands for a pilot company; None when skipped.

    Skips (warning, NO network fallback) when the company is outside the
    stage-1 snapshot scope or the snapshot file is absent (§7-2).
    """
    resolved = resolve_pilot_company(name=company_name, ticker=ticker)
    if resolved is None:
        logger.warning(
            "[band] '%s'(ticker=%s)는 1단계 스냅샷 범위(파일럿 3사) 밖 — 밴드 생략. "
            "신규 수집은 Phase 2b 계약(사용자 승인) 대상입니다.",
            company_name,
            ticker,
        )
        return None
    company_key, yahoo_ticker = resolved

    snapshot = load_pilot_snapshot(snapshot_path)
    if snapshot is None:
        return None
    company_payload = snapshot.get("companies", {}).get(company_key)
    if company_payload is None:
        logger.warning("[band] 스냅샷에 '%s' 없음 — 밴드 생략.", company_key)
        return None

    provider = price_provider or yfinance_price_provider
    # Exactly ONE provider call per company; both labels share it (§10).
    _, filing_at = extract_company_values(company_payload)
    price_data = fetch_price_data(provider, yahoo_ticker, filing_at)

    bands: list[HistoricalBand] = []
    for label in labels:
        obs, exc = build_observations(label, company_key, company_payload, price_data)
        bands.append(build_band(label, company_key, obs, exc))
    return bands
