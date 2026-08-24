"""Fill a profile's peers block with REAL peer multiples -- no LLM, no API key.

Why this exists: the `--auto` path routes peer selection AND peer multiples
through the LLM. That burns quota, and the multiples come out model-generated
rather than observed. yfinance serves `enterpriseToEbitda` for free.

Which fetcher: NOT pipeline/peer_fetcher.py -- that one calls Yahoo's
quoteSummary v10 REST endpoint, which now requires crumb/cookie auth and returns
nothing (observed: all 7 semis peers skipped, no error). calibration/peer_fetcher.py
goes through the yfinance library, which handles the crumb handshake, and is the
path the calibration code already trusts.

It also sets the segment's applied multiple from the peer statistics, so the
placeholder `multiple: 10.0` in a draft profile does not silently drive the
valuation.

Usage:
    python scripts/fill_peers.py --profile profiles/nvda.yaml \
        --peers AMD,AVGO,QCOM,MRVL,TSM,MU,INTC \
        --set-multiple median

    # per-segment mapping when the profile has more than one segment:
    python scripts/fill_peers.py --profile profiles/x.yaml \
        --peers "AMD:DC,AVGO:DC,EA:GAMING"

Then run:
    python cli.py --profile profiles/nvda.yaml --excel
"""

from __future__ import annotations

import argparse
import shutil
import statistics
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from calibration.peer_fetcher import fetch_peer_multiples  # noqa: E402
from engine.peer_analysis import explain_multiple  # noqa: E402

STAT_CHOICES = ("median", "mean", "q1", "q3")


def parse_peers(spec: str, default_segment: str) -> list[tuple[str, str]]:
    """'AMD,AVGO:DC' -> [('AMD', default_segment), ('AVGO', 'DC')]"""
    out = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" in chunk:
            ticker, seg = chunk.split(":", 1)
            out.append((ticker.strip().upper(), seg.strip()))
        else:
            out.append((chunk.upper(), default_segment))
    return out


def pick_stat(vals: list[float], stat: str) -> float:
    s = sorted(vals)
    n = len(s)
    if stat == "mean":
        return statistics.mean(s)
    if stat == "median":
        return statistics.median(s)
    if n >= 4:
        q1 = statistics.median(s[: n // 2])
        q3 = statistics.median(s[(n + 1) // 2 :])
    else:
        q1, q3 = s[0], s[-1]
    return q1 if stat == "q1" else q3


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--peers", required=True, help="TICKER[:SEGMENT] comma-separated")
    ap.add_argument(
        "--set-multiple",
        default="median",
        choices=STAT_CHOICES + ("none",),
        help="Which peer statistic becomes the applied multiple (default: median)",
    )
    args = ap.parse_args()

    path = Path(args.profile)
    profile = yaml.safe_load(path.read_text(encoding="utf-8"))

    segments = profile.get("segments") or {}
    if not segments:
        print("[ERROR] profile has no segments")
        return 1
    default_seg = next(iter(segments))

    wanted = parse_peers(args.peers, default_seg)
    unknown = {seg for _, seg in wanted if seg not in segments}
    if unknown:
        print(f"[ERROR] unknown segment code(s): {sorted(unknown)}")
        print(f"        profile segments: {list(segments)}")
        return 1

    seg_of = dict(wanted)
    tickers = [t for t, _ in wanted]

    print(f"[1/3] Fetching {len(tickers)} peers via yfinance (no API key needed)...")
    rows = fetch_peer_multiples(tickers)

    good = [r for r in rows if r.ev_ebitda and r.ev_ebitda > 0]
    for r in rows:
        if r not in good:
            print(f"      [skip] {r.ticker}: no EV/EBITDA returned")
    if not good:
        print(
            "[ERROR] no peer returned an EV/EBITDA. Check tickers / network / yfinance version."
        )
        return 1

    print(f"[2/3] Got {len(good)} peers:")
    for r in good:
        pe = r.trailing_pe or 0.0
        print(
            f"      {r.ticker:<6} EV/EBITDA {r.ev_ebitda:>6.1f}x  P/E {pe:>6.1f}  EV/Rev {r.ev_revenue or 0:>5.1f}x"
        )

    profile["peers"] = [
        {
            "name": r.ticker,
            "ticker": r.ticker,
            "segment_code": seg_of[r.ticker],
            "ev_ebitda": round(float(r.ev_ebitda), 1),
            "trailing_pe": round(float(r.trailing_pe), 1) if r.trailing_pe else None,
            "forward_pe": round(float(r.forward_pe), 1) if r.forward_pe else None,
            "ev_revenue": round(float(r.ev_revenue), 1) if r.ev_revenue else None,
            "source": "yahoo",
            "notes": "yfinance enterpriseToEbitda (observed, not LLM-estimated)",
        }
        for r in good
    ]

    if args.set_multiple != "none":
        by_seg: dict[str, list[float]] = {}
        for r in good:
            by_seg.setdefault(seg_of[r.ticker], []).append(float(r.ev_ebitda))

        print(f"[3/3] Setting applied multiple = peer {args.set_multiple}")
        for seg, vals in by_seg.items():
            applied = round(pick_stat(vals, args.set_multiple), 1)
            # segments[].multiple is the source of truth -- valuation_runner.py:177
            # rebuilds `multiples` from it. Only mirror into a top-level
            # `multiples:` block if the profile already has one (don't create a
            # second, divergent source).
            segments[seg]["multiple"] = applied
            if isinstance(profile.get("multiples"), dict):
                profile["multiples"][seg] = applied

            s = sorted(vals)
            n = len(s)
            q1 = statistics.median(s[: n // 2]) if n >= 4 else s[0]
            q3 = statistics.median(s[(n + 1) // 2 :]) if n >= 4 else s[-1]
            _, _, why = explain_multiple(
                applied=applied,
                median=round(statistics.median(s), 1),
                q1=round(q1, 1),
                q3=round(q3, 1),
                lo=round(min(s), 1),
                hi=round(max(s), 1),
                n=n,
            )
            print(f"      {seg}: {applied}x")
            print(f"        {why}")
    else:
        print("[3/3] --set-multiple none: leaving segment multiples untouched")

    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    path.write_text(
        yaml.safe_dump(
            profile, sort_keys=False, allow_unicode=True, default_flow_style=False
        ),
        encoding="utf-8",
    )
    print(f"\nWrote {path} (backup: {backup.name})")
    print(f"Next: python cli.py --profile {path.as_posix()} --excel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
