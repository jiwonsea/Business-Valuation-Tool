"""Canonical 9Q memory-path SHA recipe (offline-reproducible).

Documents the previously-undocumented invariant procedure flagged in
HANDOFF_nvda2.md: the consensus leg comes from
tests/fixtures/sk_hynix_yahoo_estimates.json (2026-05-30 snapshot), NOT from
reports/.cache yahoo vintages. With that fixture the sha256 of
BacktestResult.model_dump_json() reproduces
077ecb10986a5f2a7e81b31dc595ae47077b8ed7d6fb3ababfb1d5073891933c
(rev MAPE 8.99% / EPS MAPE 10.39% / bias -3.58%) from the committed DART
cache. Verified in the Cowork sandbox 2026-07-21 (post stage-2a, 9908180).

Usage: python scripts/verify_9q_sha.py [--dump PATH]
Exit code 0 = a known-good canonical sha reproduced; 1 = mismatch.
--dump writes the exact hashed JSON bytes to PATH for cross-environment diffs.

The sha is Python-minor-version-sensitive: CPython >= 3.12 uses Neumaier
compensated summation in builtin sum(), which moves the LAST ULP of exactly
two aggregate-mean fields (eps_mape, bias_revenue) vs 3.10/3.11. Verified by
byte-diff of the hashed JSON, sandbox (3.10.12/linux) vs host (3.14.3/win32),
2026-07-21: all other bytes identical. Hence one canonical sha PER
environment family; a regression is a hash not in KNOWN_GOOD under a stable
environment.
"""

import hashlib
import json
import platform
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

KNOWN_GOOD = {
    # Cowork sandbox baseline (EFE-1 exit 2026-07-10; re-verified post-2a).
    "077ecb10986a5f2a7e81b31dc595ae47077b8ed7d6fb3ababfb1d5073891933c":
        "sandbox canonical (CPython <= 3.11 sum(); measured 3.10.12/linux)",
    # Windows host baseline (measured 2026-07-21, post-2a, 9908180).
    "b979d79fc380939d0bfd25a121543b67195e2beed47ef857c56ad79d0be1f6e7":
        "host canonical (CPython >= 3.12 Neumaier sum(); measured 3.14.3/win32)",
}


def main() -> int:
    from engine.backtest import run_backtest
    from pipeline.consensus_loader import to_consensus_record
    from pipeline.dart_fetcher import fetch_quarterly_actuals_series
    from pipeline.ir_loader import load_profile

    profile = load_profile(REPO / "profiles" / "sk_hynix.yaml")
    start_year = int(str(profile["backtest_window"]["start_quarter"])[:4]) - 1
    end_year = max(
        int(str(profile["backtest_window"]["end_quarter"])[:4]),
        int(str(profile["forecast_window"]["start_quarter"])[:4]),
    )
    actuals = fetch_quarterly_actuals_series(
        profile["company"].corp_code_dart,
        start_year,
        end_year,
        profile["segment_revenue_split"],
        skip_unavailable=True,
    )
    fixture = REPO / "tests" / "fixtures" / "sk_hynix_yahoo_estimates.json"
    with open(fixture, encoding="utf-8") as f:
        yahoo_raw = json.load(f)
    consensus = to_consensus_record(
        yahoo_raw,
        profile["company"].ticker_yahoo,
        weighted_avg_basic_shares=profile["shares"].weighted_avg_basic,
    )

    end_q = str(profile["backtest_window"]["end_quarter"])
    history = [
        a
        for a in sorted(actuals, key=lambda x: x.period_end)
        if a.quarter_label <= end_q
    ]
    base = profile["scenarios"]["base"]
    bt = run_backtest(
        history,
        base[0],
        base[1],
        profile["anchor_margins"],
        base[2],
        profile["shares"],
        profile["historical_drivers"],
        int(profile["backtest_window"]["lookback_quarters"]),
        consensus_history=consensus.history,
    )
    payload = bt.model_dump_json()
    sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if "--dump" in sys.argv:
        dump_path = Path(sys.argv[sys.argv.index("--dump") + 1])
        dump_path.write_text(payload, encoding="utf-8")
        print(f"dumped hashed JSON -> {dump_path}")
    import pydantic

    print(f"env: python {platform.python_version()} · pydantic {pydantic.VERSION} · {sys.platform}")
    print(f"rev MAPE {bt.revenue_mape:.4%} · EPS MAPE {bt.eps_mape:.4%} · bias {bt.bias_eps:.4%}")
    print(f"sha256   {sha}")
    if sha in KNOWN_GOOD:
        print(f"MATCH: {KNOWN_GOOD[sha]}")
        return 0
    print("MISMATCH vs all known-good canonical hashes:")
    for known, label in KNOWN_GOOD.items():
        print(f"  {known}  ({label})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
