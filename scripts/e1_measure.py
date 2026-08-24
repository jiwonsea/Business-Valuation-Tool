"""Summarize E1 events and guard an explicitly supplied controlled command."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

import portalocker


_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def summarize(path: Path, run_id: str | None = None) -> dict:
    events = []
    if path.exists():
        events = [
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        ]
    if run_id is not None:
        events = [event for event in events if event.get("run_id") == run_id]
    attempts = [event for event in events if event.get("event") == "attempt"]
    return {
        "events": len(events),
        "http_attempts": len(attempts),
        "blocked": sum(event.get("event") == "blocked" for event in events),
        "cache_hits": sum(event.get("event") == "cache_hit" for event in events),
        "cache_misses": sum(event.get("event") == "cache_miss" for event in events),
        "attempts_by_step": dict(
            Counter(event.get("step", "unknown") for event in attempts)
        ),
        "attempts_by_model": dict(
            Counter(event.get("model", "unknown") for event in attempts)
        ),
        "outcomes": dict(
            Counter(event.get("outcome", "unknown") for event in attempts)
        ),
    }


def record_approval(
    path: Path,
    run_id: str,
    command: list[str],
    estimated_attempts: int,
    estimated_cost: Decimal,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "approval",
        "run_id": run_id,
        "company": None,
        "step": "measurement",
        "operation": "primary",
        "command": command,
        "estimated_attempts": estimated_attempts,
        "estimated_cost_usd": str(estimated_cost),
    }
    with portalocker.Lock(str(path), mode="a", encoding="utf-8", timeout=10) as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        handle.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--events", type=Path, default=_PROJECT_ROOT / ".cache" / "llm_events.jsonl"
    )
    parser.add_argument("--cache-ns", default="e1_test")
    parser.add_argument("--estimated-attempts", type=int)
    parser.add_argument("--estimated-cost-usd")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if not args.command:
        print(json.dumps(summarize(args.events), ensure_ascii=False, indent=2))
        return 0

    if args.estimated_attempts is None or args.estimated_cost_usd is None:
        parser.error(
            "a paid command requires --estimated-attempts and --estimated-cost-usd"
        )
    try:
        estimated_cost = Decimal(args.estimated_cost_usd)
    except InvalidOperation:
        parser.error("--estimated-cost-usd must be a decimal amount")

    print(f"예상 HTTP attempts: {args.estimated_attempts}")
    print(f"예상 비용 상한: ${estimated_cost:.4f}")
    if input("유료 측정을 실행할까요? (y/N) ").strip().lower() != "y":
        print("취소했습니다.")
        return 1

    run_id = f"e1-{uuid4().hex}"
    record_approval(
        args.events,
        run_id,
        args.command,
        args.estimated_attempts,
        estimated_cost,
    )
    env = os.environ.copy()
    env.update(
        {
            "BVT_TELEMETRY": "1",
            "BVT_TELEMETRY_PATH": str(args.events),
            "BVT_CACHE_NS": args.cache_ns,
            "BVT_RUN_ID": run_id,
        }
    )
    process = subprocess.Popen(args.command, env=env)
    exceeded = False
    while process.poll() is None:
        if summarize(args.events, run_id)["http_attempts"] > args.estimated_attempts:
            exceeded = True
            process.terminate()
            break
        time.sleep(0.1)
    returncode = process.wait()
    actual = summarize(args.events, run_id)["http_attempts"]
    if actual > args.estimated_attempts:
        exceeded = True
    if exceeded:
        print(
            f"[ERROR] HTTP attempt 상한 초과: actual={actual}, "
            f"approved={args.estimated_attempts}",
            file=sys.stderr,
        )
        return 2
    return returncode


if __name__ == "__main__":
    sys.exit(main())
