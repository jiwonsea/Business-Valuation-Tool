"""Normalize raw Yahoo response into ConsensusRecord.

Maps yfinance field names to our schema and converts NaN -> None.
"""

from __future__ import annotations

from datetime import date
import math

from schemas.models import ConsensusRecord


def _clean(value: object) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric):
        return None
    return numeric


def _forward_quarters_from_as_of(as_of: date, count: int = 2) -> list[str]:
    year = as_of.year
    quarter = ((as_of.month - 1) // 3) + 1
    labels: list[str] = []
    for _ in range(count):
        labels.append(f"{year}Q{quarter}")
        quarter += 1
        if quarter == 5:
            year += 1
            quarter = 1
    return labels


def to_consensus_record(
    raw_yahoo: dict,
    ticker: str,
    as_of: date | None = None,
    weighted_avg_basic_shares: int | None = None,
) -> ConsensusRecord:
    """Convert a yfinance response dict to a typed ConsensusRecord.

    Args:
        raw_yahoo: Output of pipeline.yahoo_fetcher.fetch_consensus.
        ticker: Original ticker (echoed into record).
        as_of: Snapshot date. Defaults to today.

    Returns:
        ConsensusRecord. Missing values are explicit None, not skipped keys.
        ``notes`` records every warning for report display (absence + quality);
        ``quality_notes`` is the subset that are genuine data-quality failures
        (e.g. implausible implied net margin), which downstream reliability
        guards gate on — so a benign field absence does not suppress an otherwise
        valid bridge (Codex follow-up #1).

    Raises:
        NotImplementedError: Codex implementation.
    """
    as_of = as_of or date.today()
    notes: list[str] = []
    quality_notes: list[str] = []
    quarter_labels = _forward_quarters_from_as_of(as_of)

    revenue_q: dict[str, float | None] = {}
    eps_q: dict[str, float | None] = {}
    revenue_y: dict[int, float | None] = {}
    eps_y: dict[int, float | None] = {}

    for row in raw_yahoo.get("revenue_estimate") or []:
        period = row.get("period")
        value = _clean(row.get("avg"))
        if value is not None:
            value /= 1_000_000_000.0
        if period in ("0q", "+1q"):
            idx = 0 if period == "0q" else 1
            if idx < len(quarter_labels):
                revenue_q[quarter_labels[idx]] = value
        elif period in ("0y", "+1y"):
            revenue_y[as_of.year + (0 if period == "0y" else 1)] = value

    for row in raw_yahoo.get("earnings_estimate") or []:
        period = row.get("period")
        value = _clean(row.get("avg"))
        if period in ("0q", "+1q"):
            idx = 0 if period == "0q" else 1
            if idx < len(quarter_labels):
                eps_q[quarter_labels[idx]] = value
        elif period in ("0y", "+1y"):
            eps_y[as_of.year + (0 if period == "0y" else 1)] = value

    history: dict[str, dict[str, float | None]] = {}
    for row in raw_yahoo.get("earnings_history") or []:
        # yfinance indexes earnings_history by "quarter"; some legacy caches and
        # the committed fixture key it by "period". Accept either so vintage
        # consensus history is not silently dropped (empty history -> N=0 in the
        # surprise-direction / consensus-skill metrics).
        period = row.get("period") or row.get("quarter")
        if not period:
            continue
        period_date = date.fromisoformat(str(period)[:10])
        label = f"{period_date.year}Q{((period_date.month - 1) // 3) + 1}"
        history[label] = {
            "actual": _clean(row.get("epsActual")),
            "estimate": _clean(row.get("epsEstimate")),
            "surprise_pct": _clean(row.get("surprisePercent")),
        }

    # Absence warnings (display only — NOT reliability failures).
    if not revenue_q:
        notes.append("quarterly revenue consensus unavailable")
    if not eps_q:
        notes.append("quarterly EPS consensus unavailable")

    # Quality failure: implausible implied net margin (yfinance .KS estimates can
    # be ~3x reality, §①-B). This DOES gate reliability -> both notes + quality_notes.
    if weighted_avg_basic_shares:
        implied_margins: list[float] = []
        for quarter, eps in eps_q.items():
            revenue = revenue_q.get(quarter)
            if eps is not None and revenue not in (None, 0):
                implied_margins.append((eps * weighted_avg_basic_shares / 1_000_000_000.0) / revenue)
        for fiscal_year, eps in eps_y.items():
            revenue = revenue_y.get(fiscal_year)
            if eps is not None and revenue not in (None, 0):
                implied_margins.append((eps * weighted_avg_basic_shares / 1_000_000_000.0) / revenue)
        if any(margin > 0.60 for margin in implied_margins):
            msg = "yfinance .KS consensus unreliable: implied net margin >60%"
            notes.append(msg)
            quality_notes.append(msg)

    return ConsensusRecord(
        ticker=ticker,
        as_of=as_of,
        revenue_estimate_quarterly=revenue_q,
        eps_estimate_quarterly=eps_q,
        revenue_estimate_annual=revenue_y,
        eps_estimate_annual=eps_y,
        history=history,
        notes=notes,
        quality_notes=quality_notes,
    )
