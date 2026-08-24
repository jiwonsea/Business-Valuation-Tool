"""Markdown report for engine-vs-peer multiple deviation.

Output: ``output/calibration/peer_deviation_<TICKER>_YYYY-MM-DD.md``. Report-only;
never rewrites profile YAML. Follows the rendering pattern of ``calibration.report``.
"""

from __future__ import annotations

import argparse
import logging
import statistics
from datetime import date
from pathlib import Path

import yaml

from .peer_deviation import Deviation, compute_profile_deviations
from .peer_fetcher import InfoFetcher, PeerMultiples, fetch_peer_multiples

logger = logging.getLogger(__name__)

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR: Path = PROJECT_ROOT / "output" / "calibration"


def _fmt(value: float | None, digits: int = 1, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}{suffix}"


def _extract_scenario_ev_ebitda(profile: dict) -> dict[str, float]:
    """Average each scenario's segment_multiples into one applied EV/EBITDA.

    Scenarios hold per-segment multiples; peers carry a single consolidated
    EV/EBITDA, so we collapse with a simple mean to enable apples-to-apples
    comparison. Excludes scenarios without segment_multiples.
    """
    out: dict[str, float] = {}
    for label, sc in (profile.get("scenarios") or {}).items():
        seg_mults = (sc or {}).get("segment_multiples") or {}
        vals = [float(v) for v in seg_mults.values() if v]
        if vals:
            out[str(label)] = round(statistics.mean(vals), 2)
    return out


def render_peer_report(
    deviations: list[Deviation],
    *,
    ticker: str,
    peers: list[PeerMultiples],
    report_date: date | None = None,
) -> str:
    report_date = report_date or date.today()
    lines: list[str] = []
    lines.append(f"# Peer Deviation Report — {ticker} — {report_date.isoformat()}")
    lines.append("")
    lines.append(
        "Compares engine-estimated multiples against peer trading multiples "
        "(yfinance). Report-only — profiles are not auto-modified. `⚠️` flags "
        "|deviation| ≥ 25% or robust |z| ≥ 1.5."
    )
    lines.append("")

    lines.append(f"**Peer universe** (N={len(peers)}):")
    lines.append("")
    lines.append("| Ticker | EV/EBITDA | EV/Rev | Trailing P/E | Forward P/E | D/E |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for p in peers:
        lines.append(
            f"| {p.ticker} | {_fmt(p.ev_ebitda)} | {_fmt(p.ev_revenue)} | "
            f"{_fmt(p.trailing_pe)} | {_fmt(p.forward_pe)} | {_fmt(p.de_ratio)} |"
        )
    lines.append("")

    lines.append("## Deviation")
    lines.append("")
    lines.append(
        "| Multiple | Scope | Engine | Peer N | Tier | Median | Q1 | Q3 | Deviation | z (IQR) | Flag | Notes |"
    )
    lines.append("|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|---|")
    for d in deviations:
        lines.append(
            f"| {d.multiple_type} | {d.scope} | {_fmt(d.engine_value, 2)} | "
            f"{d.stats.n} | {d.stats.tier} | {_fmt(d.stats.median, 2)} | "
            f"{_fmt(d.stats.q1, 2)} | {_fmt(d.stats.q3, 2)} | "
            f"{_fmt(d.deviation_pct, 1, '%')} | {_fmt(d.zscore_iqr, 2)} | "
            f"{d.flag} | {'; '.join(d.notes)} |"
        )
    lines.append("")
    lines.append("## How to read")
    lines.append(
        "- **stable** (N≥10): deviation values are reliable.\n"
        "- **preliminary** (N≥5): directional only — peer group too thin for hard targets.\n"
        "- **insufficient** (N<5): suppressed; broaden `peers:` in the profile.\n"
        "- A `⚠️` row suggests the engine estimate drifts from market consensus. Review before accepting the valuation."
    )
    return "\n".join(lines) + "\n"


def emit_peer_report(
    profile_path: Path,
    *,
    output_dir: Path | None = None,
    report_date: date | None = None,
    fetcher: InfoFetcher | None = None,
) -> Path:
    """Load profile, fetch peers, compute deviations, write markdown."""
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    company = profile.get("company") or {}
    ticker = str(company.get("ticker") or profile_path.stem).upper()

    peer_tickers = [str(t) for t in (profile.get("peer_tickers") or [])]
    if not peer_tickers:
        # Fallback: older profiles list peers as dicts with inline ev_ebitda. Skip
        # those here — Phase 3 expects explicit ticker symbols under `peer_tickers:`.
        logger.warning(
            "profile %s has no peer_tickers field — empty peer universe", profile_path
        )

    peers = fetch_peer_multiples(peer_tickers, fetcher=fetcher)

    deviations = compute_profile_deviations(
        peers,
        pe_multiple=profile.get("pe_multiple"),
        ev_revenue_multiple=profile.get("ev_revenue_multiple"),
        scenario_ev_ebitda=_extract_scenario_ev_ebitda(profile),
    )

    report_date = report_date or date.today()
    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"peer_deviation_{ticker}_{report_date.isoformat()}.md"
    out_path.write_text(
        render_peer_report(
            deviations, ticker=ticker, peers=peers, report_date=report_date
        ),
        encoding="utf-8",
    )
    logger.info("Wrote peer deviation report: %s", out_path)
    return out_path


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="Emit peer deviation markdown report.")
    parser.add_argument("--profile", required=True, help="Path to profiles/*.yaml")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    out = emit_peer_report(
        Path(args.profile),
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )
    print(f"Peer deviation report → {out}")


if __name__ == "__main__":
    main()
