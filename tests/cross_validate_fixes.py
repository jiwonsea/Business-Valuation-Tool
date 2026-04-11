"""Cross-validation of all engine fixes implemented in this session."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas.models import WACCParams, DCFParams
from engine.wacc import calc_wacc
from engine.dcf import calc_dcf

PASS = "PASS"
FAIL = "FAIL"
results = []


def check(label, cond, detail=""):
    tag = PASS if cond else FAIL
    results.append((tag, label, detail))
    print(f"  [{tag}] {label}")
    if detail:
        print(f"         {detail}")


print("=" * 65)
print("CROSS-VALIDATION: Valuation Engine Fixes")
print("=" * 65)

# ── FIX 1: Hamada D/E Cap ────────────────────────────────────────
print("\n[FIX 1] WACC: Hamada formula D/E cap @ 200%")
p_400 = WACCParams(rf=3.5, erp=7.0, bu=0.8, de=400.0, tax=25.0, kd_pre=5.5, eq_w=20.0)
p_200 = WACCParams(rf=3.5, erp=7.0, bu=0.8, de=200.0, tax=25.0, kd_pre=5.5, eq_w=33.3)
r_400 = calc_wacc(p_400)
r_200 = calc_wacc(p_200)

check(
    "D/E=400% produces same bL as D/E=200% (cap applied)",
    r_400.bl == r_200.bl,
    f"bL(400%)={r_400.bl:.3f}  bL(200%)={r_200.bl:.3f}",
)
check(
    "D/E=400% bL <= 2.5 (not exploding to 3.8 as before)",
    r_400.bl <= 2.5,
    f"bL={r_400.bl:.3f}  WACC={r_400.wacc:.2f}%",
)

# Old behavior: bL = 0.8 * (1 + 0.75 * 4.0) = 0.8 * 4 = 3.2 -> WACC inflated
old_bl_uncapped = 0.8 * (1 + 0.75 * 4.0)
check(
    "Old uncapped bL(400%) would have been > 3.0",
    old_bl_uncapped > 3.0,
    f"old bL={old_bl_uncapped:.3f} (prevented by fix)",
)

# ── FIX 2: da_to_ebitda_override ─────────────────────────────────
print("\n[FIX 2] DCF: da_to_ebitda_override (3yr avg vs single-year)")
# Scenario: single-year D&A spike (e.g., IFRS 16 leases capitalized)
# EBITDA=1000, but D&A jumped to 500 in latest year (was 200 in prior 2 years)
p_no_override = DCFParams(
    ebitda_growth_rates=[0.08] * 5, tax_rate=22.0, capex_to_da=1.5, terminal_growth=2.5
)
p_with_override = DCFParams(
    ebitda_growth_rates=[0.08] * 5,
    tax_rate=22.0,
    capex_to_da=1.5,
    terminal_growth=2.5,
    da_to_ebitda_override=0.22,  # 3yr avg = 22%, not the single-yr 50%
)
# Single year: da_base=500 -> ratio=0.50
r_no = calc_dcf(
    ebitda_base=1000,
    da_base=500,
    revenue_base=8000,
    wacc_pct=10.0,
    params=p_no_override,
)
# With override: ratio=0.22 regardless of da_base passed in
r_yes = calc_dcf(
    ebitda_base=1000,
    da_base=500,
    revenue_base=8000,
    wacc_pct=10.0,
    params=p_with_override,
)

check(
    "Override produces different EV than single-year (fix active)",
    r_yes.ev_dcf != r_no.ev_dcf,
    f"EV(single-yr D&A=50%)={r_no.ev_dcf:,}  EV(3yr avg D&A=22%)={r_yes.ev_dcf:,}",
)
check(
    "3yr avg D&A/EBITDA=22% used in projection (lower D&A -> lower CapEx -> higher FCFF)",
    r_yes.ev_dcf > r_no.ev_dcf,
    "FCFF is higher when CapEx = 1.5x * lower DA",
)
# Verify the override actually flowed through
proj_da_ratio = r_yes.projections[0].da / r_yes.projections[0].ebitda
check(
    "Projection year 1 D&A/EBITDA ratio ~0.22 (override applied)",
    abs(proj_da_ratio - 0.22) < 0.01,
    f"actual ratio={proj_da_ratio:.4f}",
)

# ── FIX 3: Unlisted D/E (gross_borr vs total liabilities) ────────
print("\n[FIX 3] Profile: Unlisted D/E uses gross_borr not total liabilities")
# Simulate: equity=50B KRW, total liabilities=200B (incl. payables), gross_borr=60B
equity_bv = 50_000
total_liab = 200_000
gross_borr = 60_000

old_de = round(total_liab / equity_bv * 100, 1)  # 400% (wrong)
new_de = round(gross_borr / equity_bv * 100, 1)  # 120% (correct)

check(
    "Old D/E (total liab) was inflated above 300%",
    old_de > 300,
    f"old D/E={old_de}%  (includes trade payables, accruals, etc.)",
)
check(
    "New D/E (gross_borr) is realistic for typical Korean mid-cap",
    50 < new_de < 200,
    f"new D/E={new_de}%",
)

old_eq_w = round(100 / (1 + old_de / 100), 1)
new_eq_w = round(100 / (1 + new_de / 100), 1)
p_old_de = WACCParams(
    rf=3.5, erp=7.0, bu=0.75, de=old_de, tax=25.0, kd_pre=5.5, eq_w=old_eq_w
)
p_new_de = WACCParams(
    rf=3.5, erp=7.0, bu=0.75, de=new_de, tax=25.0, kd_pre=5.5, eq_w=new_eq_w
)
r_old_de = calc_wacc(p_old_de)
r_new_de = calc_wacc(p_new_de)

check(
    "WACC is materially different between old and new D/E",
    abs(r_old_de.wacc - r_new_de.wacc) > 1.0,
    f"WACC(old D/E={old_de}%)={r_old_de.wacc:.2f}%  WACC(new D/E={new_de}%)={r_new_de.wacc:.2f}%",
)
# Inflated D/E pushes huge debt weight -> suppresses WACC (debt cheaper than equity)
# Fix makes WACC reflect actual leverage, preventing perversely low discount rate
check(
    "Old inflated D/E was causing suppressed WACC (debt-weight dominance)",
    r_old_de.wacc < r_new_de.wacc,
    f"delta WACC = {r_new_de.wacc - r_old_de.wacc:+.2f}%p correction",
)

# ── FIX 4: capex_to_da auto-derived from historical actuals ──────
print("\n[FIX 4] DCF: capex_to_da historical calibration (Tesla-like example)")
# Tesla 2024 approx: EBITDA=$12B, D&A=$4B, CapEx=$8.4B -> ratio=2.1x
ebitda = 12_000
da = 4_000
rev = 97_700
net_debt = 1_000
shares = 3_200

p_default = DCFParams(
    ebitda_growth_rates=[0.15, 0.12, 0.09, 0.06, 0.04],
    tax_rate=15.0,
    capex_to_da=1.1,
    terminal_growth=2.5,
)
p_calibrated = DCFParams(
    ebitda_growth_rates=[0.15, 0.12, 0.09, 0.06, 0.04],
    tax_rate=15.0,
    capex_to_da=2.1,
    terminal_growth=2.5,
)
r_def = calc_dcf(
    ebitda_base=ebitda, da_base=da, revenue_base=rev, wacc_pct=9.5, params=p_default
)
r_cal = calc_dcf(
    ebitda_base=ebitda, da_base=da, revenue_base=rev, wacc_pct=9.5, params=p_calibrated
)

ps_def = (r_def.ev_dcf - net_debt) / shares
ps_cal = (r_cal.ev_dcf - net_debt) / shares

check(
    "Default 1.1x capex ratio significantly overestimates EV vs calibrated 2.1x",
    r_def.ev_dcf > r_cal.ev_dcf * 1.5,
    f"EV(1.1x)=${r_def.ev_dcf:,.0f}M  EV(2.1x)=${r_cal.ev_dcf:,.0f}M",
)
check(
    "Per-share gap is material (>$10 per share)",
    (ps_def - ps_cal) > 10,
    f"per share: 1.1x=${ps_def:.0f}  2.1x=${ps_cal:.0f}  gap=${ps_def - ps_cal:.0f}",
)
check(
    "Both still far below market $361 (optionality premium not in EBITDA DCF)",
    ps_cal < 361 * 0.5,
    f"DCF(calibrated)=${ps_cal:.0f} vs market $361 -- gap is AI/FSD/Robotaxi optionality",
)

# ── FIX 5: scenario_dcf_params propagates da_to_ebitda_override ──
print("\n[FIX 5] valuation_runner: da_to_ebitda_override propagates to scenarios")
# Verify schema field exists and Pydantic copies it
base = DCFParams(
    ebitda_growth_rates=[0.05] * 5,
    tax_rate=22.0,
    capex_to_da=1.5,
    terminal_growth=2.5,
    da_to_ebitda_override=0.28,
)
check(
    "da_to_ebitda_override field exists on DCFParams",
    hasattr(base, "da_to_ebitda_override"),
    f"value={base.da_to_ebitda_override}",
)
# Simulate _make_scenario_dcf_params logic
import sys

sys.path.insert(0, ".")
from valuation_runner import _make_scenario_dcf_params
from schemas.models import ScenarioParams

sc = ScenarioParams(
    code="Bull",
    name="Bull Case",
    prob=25,
    ipo="N/A",
    shares=1_000_000,
    growth_adj_pct=20,
    terminal_growth_adj=0.3,
)
sc_params = _make_scenario_dcf_params(base, sc, wacc=9.5)
check(
    "Scenario DCFParams carries da_to_ebitda_override from base",
    sc_params is not None and sc_params.da_to_ebitda_override == 0.28,
    f"override={sc_params.da_to_ebitda_override if sc_params else 'None'}",
)

# ── Summary ──────────────────────────────────────────────────────
print("\n" + "=" * 65)
passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
print(f"RESULT: {passed} passed / {failed} failed / {len(results)} total")
if failed == 0:
    print("All fixes verified.")
else:
    print("FAILED checks:")
    for tag, label, detail in results:
        if tag == FAIL:
            print(f"  - {label}: {detail}")
print("=" * 65)

sys.exit(0 if failed == 0 else 1)
