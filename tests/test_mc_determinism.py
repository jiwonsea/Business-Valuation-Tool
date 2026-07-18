"""Cross-process regression tests for Monte Carlo determinism."""

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _nexus_snapshot(hash_seed: int) -> dict:
    code = """
import json
from valuation_runner import load_profile, run_valuation
result = run_valuation(load_profile('profiles/nexus.yaml'))
mc = result.monte_carlo
print(json.dumps({
    'weighted_value': result.weighted_value,
    'scenarios': {k: v.post_dlom for k, v in sorted(result.scenarios.items())},
    'equity': {k: v.equity_value for k, v in sorted(result.scenarios.items())},
    'receivable': {
        k: v.receivable_recovery_value for k, v in sorted(result.scenarios.items())
    },
    'scenario_multiples_clamped': result.scenario_multiples_clamped,
    'mc': {k: getattr(mc, k) for k in ('p5', 'median', 'p95', 'mean', 'std')},
}, sort_keys=True))
"""
    env = {
        **os.environ,
        "PYTHONHASHSEED": str(hash_seed),
        "PYTHONIOENCODING": "utf-8",
    }
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_nexus_mc_is_deterministic_across_hash_seeds():
    seed_zero = _nexus_snapshot(0)
    seed_one = _nexus_snapshot(1)

    assert seed_zero == seed_one
    assert seed_zero["weighted_value"] == 362
    assert seed_zero["scenarios"] == {"Base": 445, "Bear": 18, "Bull": 891}
    assert seed_zero["equity"] == {"Base": 36_211, "Bear": 1_475, "Bull": 72_524}
    assert seed_zero["receivable"] == {
        "Base": 12_440,
        "Bear": 5_503,
        "Bull": 15_564,
    }
    assert seed_zero["scenario_multiples_clamped"] is False


def test_nexus_mc_assumptions_only_list_active_drivers():
    from valuation_runner import load_profile, run_valuation

    result = run_valuation(load_profile("profiles/nexus.yaml"))
    assumptions = result.monte_carlo.input_assumptions

    assert "Multiple(GAME)" in assumptions
    assert "Multiple(CROSS_SERVICE)" in assumptions
    assert "Multiple(ONESTORE)" in assumptions
    assert "Revenue(GAME)" in assumptions
    assert "Revenue(CROSS_SERVICE)" in assumptions
    assert "DLOM" in assumptions
    assert "WACC" not in assumptions
    assert "Terminal Growth" not in assumptions
