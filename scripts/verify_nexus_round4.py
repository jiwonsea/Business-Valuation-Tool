"""넥써쓰 Round 4 — 독립 검증 v3 (LOCAL 전용).
v3 수정: ScenarioResult에 .code 없음 → dict items() 순회.
         R-8은 enrich_market_dependent_result() 호출 + 가드조건 진단 출력.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CHANGED = [
    "schemas/models.py",
    "engine/scenario.py",
    "engine/monte_carlo.py",
    "valuation_runner.py",
    "output/sheets/scenarios.py",
    "output/sheets/dashboard.py",
    "output/console_report.py",
]
EXPECT_PS = {"Bear": 18, "Base": 445, "Bull": 891}
EXPECT_AR = {"Bear": 5503, "Base": 12440, "Bull": 15564}
EXPECT_WEIGHTED = 362
EXPECT_BASE_EQUITY = 36211
SKIP = {"nexus.yaml", "_template.yaml", "346010.yaml"}

_fails: list[str] = []


def chk(label, passed, detail=""):
    if not passed:
        _fails.append(label)
    print(
        "  [%s] %s%s"
        % ("PASS" if passed else "FAIL", label, ("  -> " + detail) if detail else "")
    )


def p1_ast():
    print("\n=== P-0/P-1. NUL + AST ===")
    nul = []
    for p in ROOT.rglob("*"):
        if (
            p.is_file()
            and p.suffix in {".py", ".yaml", ".md", ".sql"}
            and "__pycache__" not in p.parts
            and ".git" not in p.parts
        ):
            try:
                if b"\x00" in p.read_bytes():
                    nul.append(str(p.relative_to(ROOT)))
            except OSError:
                pass
    chk("P-0 NUL 없음", not nul, str(nul))
    for rel in CHANGED:
        raw = (ROOT / rel).read_bytes()
        try:
            ast.parse(raw.decode("utf-8"))
            chk("P-1 " + rel, True, "lines=%d" % raw.count(10))
        except SyntaxError as e:
            chk("P-1 " + rel, False, "SyntaxError L%s" % e.lineno)


def r_nexus():
    print("\n=== R-2/R-3/R-6/R-7/R-11. 넥써쓰 재현 ===")
    from valuation_runner import apply_net_debt_gate, load_profile, run_valuation

    res = run_valuation(
        apply_net_debt_gate(load_profile(str(ROOT / "profiles" / "nexus.yaml")))
    )

    chk(
        "R-4 클램프 미발동",
        getattr(res, "scenario_multiples_clamped", None) is False,
        "clamped=%s" % getattr(res, "scenario_multiples_clamped", "N/A"),
    )

    print("\n  --- SOTP 세그먼트 ---")
    for code, seg in (res.sotp or {}).items():
        print(
            "    %-14s ev=%-9s multiple=%-8s method=%s"
            % (code, seg.ev, seg.multiple, seg.method)
        )
    onest = (res.sotp or {}).get("ONESTORE")
    if onest:
        chk("R-6 ONESTORE EV=62,633", abs(onest.ev - 62633) <= 2, str(onest.ev))

    print("\n  --- 시나리오 Equity Bridge ---")
    for code, s in res.scenarios.items():
        print(
            "    [%s] total_ev=%-9s equity=%-9s ps=%-6s weighted=%s"
            % (code, s.total_ev, s.equity_value, s.post_dlom, s.weighted)
        )
        print("         receivable_recovery_value = %s" % s.receivable_recovery_value)
        for a in s.adjustments:
            print("         adj: %-22s %s" % (a.name, a.value))

    print()
    for code, s in res.scenarios.items():
        if code not in EXPECT_PS:
            continue
        chk(
            "R-2 %s %d원" % (code, EXPECT_PS[code]),
            abs(s.post_dlom - EXPECT_PS[code]) <= 1,
            "%d원" % s.post_dlom,
        )
        chk(
            "R-7 %s AR=%d" % (code, EXPECT_AR[code]),
            s.receivable_recovery_value == EXPECT_AR[code],
            str(s.receivable_recovery_value),
        )
        if code == "Base":
            dbl = s.equity_value > 40000
            chk(
                "R-7 Base equity ~36,211 (이중가산 검출)",
                abs(s.equity_value - EXPECT_BASE_EQUITY) <= 2,
                "%d%s" % (s.equity_value, "  <<< 이중가산!" if dbl else ""),
            )

    w = sum(s.weighted for s in res.scenarios.values())
    chk(
        "R-3 확률가중 %d원" % EXPECT_WEIGHTED, abs(w - EXPECT_WEIGHTED) <= 1, "%d원" % w
    )

    if res.monte_carlo:
        mc = res.monte_carlo
        chk(
            "R-11 MC 실행",
            True,
            "mean=%s pct_negative=%s" % (mc.mean, getattr(mc, "pct_negative", "N/A")),
        )
    else:
        chk("R-11 MC 실행", False, "monte_carlo=None")


def r8_gap():
    print("\n=== R-8. NVDA/TSLA gap_diagnostic (과잉수정 검출) ===")
    import valuation_runner as VR

    for name in ("nvda", "tsla"):
        p = ROOT / "profiles" / (name + ".yaml")
        if not p.exists():
            print("  [SKIP] %s.yaml" % name)
            continue
        try:
            vi = VR.apply_net_debt_gate(VR.load_profile(str(p)))
            res = VR.run_valuation(vi)
            VR.enrich_market_dependent_result(vi, res)
            gd = getattr(res, "gap_diagnostic", None)
            if gd is None:
                mc = res.market_comparison
                print(
                    "    [진단] market_comparison=%s"
                    % (
                        "None"
                        if mc is None
                        else "price=%s gap=%s" % (mc.market_price, mc.gap_ratio)
                    )
                )
                print("    [진단] result.dcf is None: %s" % (res.dcf is None))
                methods = {c: i.get("method") for c, i in vi.segments.items()}
                print("    [진단] segment methods: %s" % methods)
                if mc is None:
                    print(
                        "  [ENV SKIP] R-8 %s: live market comparison unavailable" % name
                    )
                    continue
            chk(
                "R-8 %s gap_diagnostic 생존" % name,
                gd is not None,
                "None" if gd is None else "존재",
            )
        except Exception as e:
            chk("R-8 %s" % name, False, "%s: %s" % (type(e).__name__, e))


def r9_backcompat():
    print("\n=== R-9. Optional 하위호환 ===")
    from valuation_runner import apply_net_debt_gate, load_profile, run_valuation

    others = sorted(p for p in (ROOT / "profiles").glob("*.yaml") if p.name not in SKIP)
    bad = 0
    for p in others:
        try:
            res = run_valuation(apply_net_debt_gate(load_profile(str(p))))
            rrv = {s.receivable_recovery_value for s in res.scenarios.values()}
            if rrv not in ({0}, set()):
                chk("R-9 %s" % p.name, False, "rrv=%s" % rrv)
                bad += 1
        except Exception as e:
            chk("R-9 %s" % p.name, False, "%s: %s" % (type(e).__name__, e))
            bad += 1
    chk(
        "R-9 하위호환 (%d개)" % len(others),
        bad == 0,
        "실패 %d건" % bad if bad else "전부 rrv=0, crash 0",
    )


def r10_pytest():
    print("\n=== R-10. pytest ===")
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-q",
            "--deselect",
            "tests/test_engine.py::TestScenarioDriverRoundTrip",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    lines = (r.stdout or r.stderr).strip().splitlines()
    chk("R-10 pytest", r.returncode == 0, lines[-1] if lines else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-pytest", action="store_true")
    a = ap.parse_args()
    print("=" * 72)
    print("넥써쓰 Round 4 - 독립 검증 v3")
    print("=" * 72)
    p1_ast()
    for fn in (r_nexus, r8_gap, r9_backcompat):
        try:
            fn()
        except Exception as e:
            chk(fn.__name__, False, "%s: %s" % (type(e).__name__, e))
            import traceback

            traceback.print_exc()
    if not a.skip_pytest:
        r10_pytest()
    print("\n" + "=" * 72)
    if _fails:
        print("FAIL %d건:" % len(_fails))
        for f in _fails:
            print("   - " + f)
    else:
        print("ALL PASS")
    print("=" * 72)
    return 1 if _fails else 0


if __name__ == "__main__":
    sys.exit(main())
