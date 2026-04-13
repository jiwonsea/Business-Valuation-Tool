"""Bucket aggregation: BacktestRecord → (market, sector, horizon) groups.

Sector is proxied by ``primary_method`` (see calibration/__init__.py).
Scenario role (bull/base/bear) is assigned by post_dlom value rank within
each record so the calibration is robust to heterogeneous scenario codes
(A/B/C in one profile, A/B/C/D in another).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, NamedTuple

from dateutil.relativedelta import relativedelta

from backtest.models import BacktestRecord, ScenarioSnapshot

HORIZONS: tuple[str, ...] = ("t3m", "t6m", "t12m")
ROLES: tuple[str, ...] = ("bull", "base", "bear")


class BucketKey(NamedTuple):
    market: str
    sector: str
    horizon: str


@dataclass
class Bucket:
    key: BucketKey
    records: list[BacktestRecord] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.records)


def horizon_is_mature(record: BacktestRecord, horizon: str, today: date | None = None) -> bool:
    """True iff enough calendar time has elapsed for the horizon to be evaluable.

    A record is mature even if the price column is None — that signals a fetch
    failure, not an immature horizon. Maturity is purely a calendar check.
    """
    today = today or date.today()
    months = {"t3m": 3, "t6m": 6, "t12m": 12}[horizon]
    return record.analysis_date + relativedelta(months=months) <= today


def _sector_of(record: BacktestRecord) -> str:
    return record.primary_method or "unknown"


def bucket_records(
    records: Iterable[BacktestRecord],
    *,
    today: date | None = None,
) -> dict[BucketKey, Bucket]:
    """Partition records into (market, sector, horizon) buckets.

    A record with a valid (>0) price at horizon H is added to that horizon's
    bucket. Records missing a price at H are skipped for that horizon only —
    they may still appear in other horizons. Unlisted records are excluded.
    """
    today = today or date.today()
    buckets: dict[BucketKey, Bucket] = defaultdict(lambda: Bucket(key=None))  # type: ignore[arg-type]

    for r in records:
        if not r.is_listed:
            continue
        if not r.scenarios:
            continue
        for horizon in HORIZONS:
            price = r.get_price(horizon)
            if price is None or price <= 0:
                continue
            if not horizon_is_mature(r, horizon, today=today):
                continue
            key = BucketKey(market=r.market, sector=_sector_of(r), horizon=horizon)
            bucket = buckets[key]
            if bucket.key is None:
                bucket.key = key
            bucket.records.append(r)

    return dict(buckets)


def classify_scenarios(scenarios: list[ScenarioSnapshot]) -> dict[str, list[ScenarioSnapshot]]:
    """Assign each scenario a role (bull/base/bear) by post_dlom value rank.

    Rules:
      - 1 scenario  → all 'base'
      - 2 scenarios → highest 'bull', lowest 'bear', no 'base'
      - 3 scenarios → highest 'bull', lowest 'bear', middle 'base'
      - 4+          → highest 'bull', lowest 'bear', remainder 'base'

    Ties are broken by scenario code (lexicographic) for determinism.
    """
    roles: dict[str, list[ScenarioSnapshot]] = {r: [] for r in ROLES}
    if not scenarios:
        return roles

    ordered = sorted(scenarios, key=lambda s: (s.post_dlom, s.code))
    n = len(ordered)
    if n == 1:
        roles["base"].append(ordered[0])
    elif n == 2:
        roles["bear"].append(ordered[0])
        roles["bull"].append(ordered[1])
    else:
        roles["bear"].append(ordered[0])
        roles["bull"].append(ordered[-1])
        roles["base"].extend(ordered[1:-1])
    return roles
