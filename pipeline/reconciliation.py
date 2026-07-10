"""Cross-source market-data reconciliation (Workstream BVT-1 / A4).

Deterministic, stdlib-only validators that compare registry data (DART /
SEC EDGAR / EDINET) against market data (yfinance / Yahoo) before an
auto-generated profile is persisted by ``pipeline/profile_generator.py``.

Default behavior is warn-and-persist: findings are written into the profile
under a ``data_reconciliation:`` section and printed as warnings. A hard
block (profile not persisted) is raised only for identity/unit failures that
materially corrupt per-share valuation:

- share count mismatch above 25% (registry shares vs market_cap / price),
- implied market cap (price * shares) vs fetched market cap above 25%,
- revenue / OP unit mismatch above 100% when two sources cover the same
  period (skipped when a second source is absent).

Relative difference convention: ``|a - b| / min(|a|, |b|)`` — the smaller
value must be scaled by more than (1 + threshold) to match the larger one.
A 2x shares error therefore scores 100% and always blocks.

No IO in this module; callers pass already-fetched dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# ── Thresholds ──────────────────────────────────────────────
# Soft warn floor for the 25%-block identity checks.
WARN_THRESHOLD = 0.10
# Hard-block thresholds (PLAN_skill_adoption.md, Workstream BVT-1).
SHARES_BLOCK_THRESHOLD = 0.25
MARKET_CAP_BLOCK_THRESHOLD = 0.25
UNIT_BLOCK_THRESHOLD = 1.00
# Soft warn floor for the unit check (two sources may legitimately differ
# on TTM-vs-FY or restatements; only shout well below the block line).
UNIT_WARN_THRESHOLD = 0.25

_SEVERITY_ORDER = {"ok": 0, "warn": 1, "block": 2}

_REGISTRY_BY_MARKET = {"KR": "DART", "US": "SEC EDGAR", "JP": "EDINET"}


@dataclass
class Finding:
    """One reconciliation check result."""

    check: str
    severity: str  # "ok" | "warn" | "block"
    message: str
    source_a: str | None = None
    value_a: float | None = None
    source_b: str | None = None
    value_b: float | None = None
    rel_diff_pct: float | None = None

    def to_dict(self) -> dict:
        d = {"check": self.check, "severity": self.severity, "message": self.message}
        if self.source_a is not None:
            d["source_a"] = self.source_a
            d["value_a"] = self.value_a
        if self.source_b is not None:
            d["source_b"] = self.source_b
            d["value_b"] = self.value_b
        if self.rel_diff_pct is not None:
            d["rel_diff_pct"] = self.rel_diff_pct
        return d


@dataclass
class ReconciliationReport:
    """Aggregate of all executed checks. ``status`` is the max severity."""

    status: str = "ok"
    findings: list[Finding] = field(default_factory=list)

    def add(self, finding: Finding | None) -> None:
        if finding is None:
            return
        self.findings.append(finding)
        if _SEVERITY_ORDER[finding.severity] > _SEVERITY_ORDER[self.status]:
            self.status = finding.severity

    @property
    def blocked(self) -> bool:
        return self.status == "block"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "as_of": date.today().isoformat(),
            "findings": [f.to_dict() for f in self.findings],
        }


def relative_diff(a: float | None, b: float | None) -> float | None:
    """``|a - b| / min(|a|, |b|)``; None when either side is missing or <= 0."""
    if a is None or b is None:
        return None
    if a <= 0 or b <= 0:
        return None
    return abs(a - b) / min(a, b)


def _classify(rel: float, block_threshold: float, warn_threshold: float) -> str:
    if rel > block_threshold:
        return "block"
    if rel > warn_threshold:
        return "warn"
    return "ok"


# ── Individual checks (each returns Finding | None if not computable) ──


def check_share_count(
    registry_shares: float | None,
    implied_shares: float | None,
    source_a: str = "registry shares_total",
    source_b: str = "market_cap / price",
) -> Finding | None:
    """Registry share count vs market-implied share count. Block > 25%."""
    rel = relative_diff(registry_shares, implied_shares)
    if rel is None:
        return None
    severity = _classify(rel, SHARES_BLOCK_THRESHOLD, WARN_THRESHOLD)
    return Finding(
        check="share_count",
        severity=severity,
        message=(
            f"주식수 불일치 {rel * 100:.1f}%: {source_a}={registry_shares:,.0f} vs "
            f"{source_b}={implied_shares:,.0f} (블록 기준 {SHARES_BLOCK_THRESHOLD * 100:.0f}%)"
        ),
        source_a=source_a,
        value_a=float(registry_shares),
        source_b=source_b,
        value_b=float(implied_shares),
        rel_diff_pct=round(rel * 100, 1),
    )


def check_market_cap(
    implied_mcap: float | None,
    fetched_mcap: float | None,
    source_a: str = "price * shares_total",
    source_b: str = "fetched market_cap",
) -> Finding | None:
    """Implied market cap (price * shares) vs fetched market cap. Block > 25%."""
    rel = relative_diff(implied_mcap, fetched_mcap)
    if rel is None:
        return None
    severity = _classify(rel, MARKET_CAP_BLOCK_THRESHOLD, WARN_THRESHOLD)
    return Finding(
        check="market_cap",
        severity=severity,
        message=(
            f"시가총액 불일치 {rel * 100:.1f}%: {source_a}={implied_mcap:,.0f} vs "
            f"{source_b}={fetched_mcap:,.0f} (블록 기준 {MARKET_CAP_BLOCK_THRESHOLD * 100:.0f}%)"
        ),
        source_a=source_a,
        value_a=float(implied_mcap),
        source_b=source_b,
        value_b=float(fetched_mcap),
        rel_diff_pct=round(rel * 100, 1),
    )


def check_unit_consistency(
    value_a: float | None,
    value_b: float | None,
    field_name: str,
    period: int | str,
    source_a: str,
    source_b: str,
) -> Finding | None:
    """Same field / same period across two sources. Block > 100% (unit error)."""
    rel = relative_diff(value_a, value_b)
    if rel is None:
        return None
    severity = _classify(rel, UNIT_BLOCK_THRESHOLD, UNIT_WARN_THRESHOLD)
    return Finding(
        check=f"unit_{field_name}",
        severity=severity,
        message=(
            f"{period} {field_name} 단위/수치 불일치 {rel * 100:.1f}%: "
            f"{source_a}={value_a:,.0f} vs {source_b}={value_b:,.0f} "
            f"(블록 기준 {UNIT_BLOCK_THRESHOLD * 100:.0f}%)"
        ),
        source_a=source_a,
        value_a=float(value_a),
        source_b=source_b,
        value_b=float(value_b),
        rel_diff_pct=round(rel * 100, 1),
    )


# ── Orchestrator ────────────────────────────────────────────


def reconcile_market_data(
    financials: dict,
    shares_info: dict,
    market: str = "KR",
    alt_financials: dict | None = None,
    registry_source: str | None = None,
) -> ReconciliationReport:
    """Run all applicable checks on fetched data before profile persistence.

    Args:
        financials: {year: {"revenue": ..., "op": ..., ...}} (primary source).
        shares_info: fetch_shares() result — shares_total, price, market_cap...
        market: "KR" | "US" | "JP" (labels only; no behavioral branching).
        alt_financials: optional second-source financials for the unit check;
            skipped when absent (current pipeline merges to one source).
        registry_source: label override for the share-registry source.

    Every check skips gracefully when its inputs are missing — absence of
    market data must never block an unlisted-company profile.
    """
    report = ReconciliationReport()
    registry = registry_source or _REGISTRY_BY_MARKET.get(market, "registry")

    shares_total = shares_info.get("shares_total") or 0
    price = shares_info.get("price") or 0
    market_cap = shares_info.get("market_cap") or 0

    # 1) Share-count identity: registry shares vs market_cap / price.
    if price > 0 and market_cap > 0:
        implied_shares = market_cap / price
        report.add(
            check_share_count(
                shares_total if shares_total > 0 else None,
                implied_shares,
                source_a=f"shares_total ({registry})",
                source_b="market_cap / price (yfinance)",
            )
        )

    # 2) Market-cap identity: price * shares vs fetched market cap.
    if shares_total > 0 and price > 0 and market_cap > 0:
        report.add(
            check_market_cap(
                price * shares_total,
                market_cap,
                source_a=f"price * shares_total ({registry})",
                source_b="market_cap (yfinance)",
            )
        )

    # 3) Unit check: two sources for the same field/period (skip if absent).
    if alt_financials:
        for year in sorted(set(financials) & set(alt_financials)):
            for field_name in ("revenue", "op"):
                report.add(
                    check_unit_consistency(
                        financials[year].get(field_name),
                        alt_financials[year].get(field_name),
                        field_name=field_name,
                        period=year,
                        source_a="primary",
                        source_b="secondary",
                    )
                )

    # 4) Soft sanity warns (never block).
    latest = max(financials) if financials else None
    if latest is not None:
        cons = financials[latest]
        revenue = cons.get("revenue", 0) or 0
        op = cons.get("op", 0) or 0
        if revenue > 0 and abs(op) > revenue:
            report.add(
                Finding(
                    check="op_exceeds_revenue",
                    severity="warn",
                    message=(
                        f"{latest} |영업이익|({op:,.0f}) > 매출({revenue:,.0f}) — "
                        "단위 또는 계정 매핑 오류 가능성"
                    ),
                    rel_diff_pct=None,
                )
            )
        if "liabilities" in cons and not cons.get("liabilities"):
            report.add(
                Finding(
                    check="zero_liabilities",
                    severity="warn",
                    message=f"{latest} liabilities=0 — 데이터 수집 오류 가능성 (영업기업 기준 비정상)",
                )
            )

    ordinary = shares_info.get("shares_ordinary") or 0
    treasury = shares_info.get("treasury_shares") or 0
    if ordinary > 0 and treasury >= ordinary:
        report.add(
            Finding(
                check="treasury_exceeds_ordinary",
                severity="warn",
                message=(
                    f"자사주({treasury:,.0f}) >= 보통주({ordinary:,.0f}) — "
                    "유통주식수 계산 불가 위험"
                ),
            )
        )

    return report
