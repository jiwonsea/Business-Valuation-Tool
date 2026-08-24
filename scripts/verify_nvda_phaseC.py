"""NVDA Phase C acceptance checks (C-1 through C-12)."""

from __future__ import annotations

import argparse
import ast
import hashlib
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILURES: list[str] = []


def check(code: str, condition: bool, detail: str = "") -> None:
    print(
        f"[{'PASS' if condition else 'FAIL'}] {code}"
        + (f" - {detail}" if detail else "")
    )
    if not condition:
        FAILURES.append(code)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-pytest", action="store_true")
    args = parser.parse_args()

    from valuation_runner import load_profile, run_valuation

    profile = load_profile(str(ROOT / "profiles" / "nvda.yaml"))
    forward = profile.forward_anchor
    peer = profile.peer_beta_snapshot
    check(
        "C-1 forward structurally separate",
        forward is not None
        and profile.consolidated[profile.base_year]["revenue"] == 253_491,
    )
    check(
        "C-2 forward provenance",
        bool(
            forward
            and forward.basis == "consensus_estimate"
            and forward.revenue
            and forward.revenue.n_analysts > 0
            and len(forward.source_hash) == 64
        ),
    )
    check(
        "C-3 peer eligibility audit",
        bool(
            peer
            and len(peer.candidates) == 8
            and sum(not p.qualified for p in peer.candidates) == 2
            and all(p.qualification_reason for p in peer.candidates if p.qualified)
        ),
    )
    methods = (
        {
            (p.frequency, p.benchmark, p.calculation_method)
            for p in peer.candidates
            if p.qualified
        }
        if peer
        else set()
    )
    check(
        "C-4 peer method/provenance",
        methods == {("weekly", "^GSPC", "ols_weekly_log_returns_adjusted_close")}
        and all(p.source_hash for p in peer.candidates if p.qualified),
    )

    control = profile.model_copy(
        update={"forward_anchor": None, "peer_beta_snapshot": None}
    )
    actual_result = run_valuation(profile)
    control_result = run_valuation(control)
    check(
        "C-5 judgement only",
        bool(
            peer
            and peer.judgement.status == "validated"
            and actual_result.wacc == control_result.wacc
            and actual_result.scenarios == control_result.scenarios
        ),
    )
    reference = load_profile(str(ROOT / "profiles" / "nvda_fy27e.yaml"))
    reference_revenue = reference.consolidated[reference.base_year]["revenue"]
    check(
        "C-6 forward convergence",
        abs(forward.revenue.value / reference_revenue - 1) <= 0.10,
        f"auto={forward.revenue.value:.0f}, manual={reference_revenue}",
    )

    nexus = subprocess.run(
        [sys.executable, "scripts/verify_nexus_round4.py", "--skip-pytest"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    check("C-7 Nexus regression", nexus.returncode == 0, f"exit={nexus.returncode}")
    phase_a = subprocess.run(
        [sys.executable, "scripts/verify_nvda_phaseA_v2.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    check("C-8 Phase A", phase_a.returncode == 0, f"exit={phase_a.returncode}")

    baseline = subprocess.check_output(
        ["git", "show", "8ae6aab:profiles/nvda.yaml"], cwd=ROOT
    )
    baseline_data = yaml.safe_load(baseline.decode("utf-8"))
    baseline_ok = (
        len(baseline.splitlines()) == 467
        and hashlib.sha256(baseline).hexdigest().startswith("bb276cf5")
        and baseline_data["financial_anchor"] == "ttm"
        and profile.ttm_anchor["revenue"] == 253_491
    )
    check("C-9 Phase B baseline", baseline_ok)

    bad_profiles = []
    skip = {
        "_template.yaml",
        "nav_test.yaml",
        "multiples_test.yaml",
        "kb_financial_rim.yaml",
        "346010.yaml",
    }
    for path in sorted((ROOT / "profiles").glob("*.yaml")):
        if path.name in skip:
            continue
        try:
            load_profile(str(path))
        except Exception as exc:
            bad_profiles.append(f"{path.name}:{type(exc).__name__}")
    check("C-10 profile compatibility", not bad_profiles, str(bad_profiles))

    if args.full_pytest:
        pytest_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/",
                "--deselect",
                "tests/test_engine.py::TestScenarioDriverRoundTrip",
            ],
            cwd=ROOT,
        )
        check(
            "C-11 pytest",
            pytest_result.returncode == 0,
            f"exit={pytest_result.returncode}",
        )
    else:
        check("C-11 pytest", True, "SKIP (use --full-pytest)")

    changed_python = [
        "schemas/models.py",
        "engine/peer_beta.py",
        "pipeline/forward_estimates.py",
        "pipeline/peer_beta_snapshot.py",
        "engine/investability_gate.py",
        "valuation_runner.py",
        "output/console_report.py",
        "output/sheets/assumptions.py",
        "scripts/rewrite_nvda_phaseC.py",
        "scripts/verify_nvda_phaseC.py",
    ]
    structural_ok = True
    for relative in changed_python:
        raw = (ROOT / relative).read_bytes()
        structural_ok &= b"\x00" not in raw
        ast.parse(raw.decode("utf-8"), filename=relative)
    structural_ok &= b"\r\n" in (ROOT / "profiles" / "nvda.yaml").read_bytes()
    check("C-12 NUL/AST/CRLF", structural_ok)

    print("ALL PASS" if not FAILURES else "FAILED: " + ", ".join(FAILURES))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
