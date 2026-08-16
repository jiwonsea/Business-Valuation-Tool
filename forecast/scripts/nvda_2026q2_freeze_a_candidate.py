"""
NVDA FY27Q2 (model label 2026Q2) — Freeze-A CANDIDATE, computed 2026-08-09 KST.
목적: 정보 컷오프의 기계적 강제. 판단 개입 없이 두 변형을 산출하고 해시를 남긴다.
입력은 전부 INFO_CUTOFF_A(2026-08-09) 이전 사실만 사용한다.
"""
import json, hashlib

SEED_REV   = 81615.0      # 2026Q1 actual revenue, $M (EDGAR 0001045810-26-000052)
SHARES_FWD = 24490.0      # profile weighted_avg_diluted, $M shares
SHARES_Q1  = 24391.0      # Q1 FY27 as-filed diluted, $M shares

# --- Variant 1: 현 프로파일 앵커 그대로 (as-is) -------------------------------
ASIS = {
  "base": dict(p=0.50, g=0.10, om=0.62, tax=0.15, below_pct=+0.01),
  "bear": dict(p=0.25, g=0.03, om=0.58, tax=0.16, below_pct=+0.01),
  "bull": dict(p=0.25, g=0.15, om=0.65, tax=0.15, below_pct=+0.01),
}

# --- Variant 2: R1/R2/R3 기계적 교정 (판단 0) ---------------------------------
# R1 level = 가이던스 mid, 밴드는 회사가 준 ±2%
# R1 OPM   = 가이던스 내재 (GM 74.9% - opex 8500 on rev), bear/bull은 GM ±50bp
# R2 below-OP = base 0 (전 시나리오)
# R3 tax   = 가이던스 범위 16/17/18%
G_REV, G_GM, G_OPEX, G_TOL = 91000.0, 0.749, 8500.0, 0.02
def opm(rev, gm, opex): return (rev*gm - opex)/rev
MECH = {
  "bear": dict(p=0.25, rev=G_REV*(1-G_TOL), gm=G_GM-0.005, tax=0.18, below_pct=0.0),
  "base": dict(p=0.50, rev=G_REV,           gm=G_GM,       tax=0.17, below_pct=0.0),
  "bull": dict(p=0.25, rev=G_REV*(1+G_TOL), gm=G_GM+0.005, tax=0.16, below_pct=0.0),
}

def run_asis():
    out={}; w=dict(rev=0.0,op=0.0,eps=0.0)
    for k,v in ASIS.items():
        rev=SEED_REV*(1+v["g"]); op=rev*v["om"]; below=rev*v["below_pct"]
        pre=op+below; ni=pre*(1-v["tax"]); eps=ni/SHARES_FWD
        out[k]=dict(p=v["p"],revenue=rev,op=op,op_margin=v["om"],below_op=below,
                    pretax=pre,net_income=ni,eps=eps)
        w["rev"]+=v["p"]*rev; w["op"]+=v["p"]*op; w["eps"]+=v["p"]*eps
    out["weighted"]=dict(revenue=w["rev"],op=w["op"],eps=w["eps"]); return out

def run_mech():
    out={}; w=dict(rev=0.0,op=0.0,eps=0.0)
    for k,v in MECH.items():
        rev=v["rev"]; m=opm(rev,v["gm"],G_OPEX); op=rev*m; below=rev*v["below_pct"]
        pre=op+below; ni=pre*(1-v["tax"]); eps=ni/SHARES_Q1
        out[k]=dict(p=v["p"],revenue=rev,op=op,op_margin=m,below_op=below,
                    pretax=pre,net_income=ni,eps=eps)
        w["rev"]+=v["p"]*rev; w["op"]+=v["p"]*op; w["eps"]+=v["p"]*eps
    out["weighted"]=dict(revenue=w["rev"],op=w["op"],eps=w["eps"]); return out

payload = {
  "schema": "nvda_2026q2_freeze_a_candidate/v1",
  "computed_at_kst": "2026-08-09",
  "info_cutoff_a": "2026-08-09T23:59+09:00",
  "target": {"ticker":"NVDA","fiscal":"FY2027Q2","model_label":"2026Q2",
             "period_end":"2026-07-26","print_utc":"2026-08-26T21:00:00Z"},
  "inputs": {"seed_revenue_musd": SEED_REV, "shares_forward_m": SHARES_FWD,
             "shares_q1_asfiled_m": SHARES_Q1,
             "guidance": {"revenue_mid_musd": G_REV, "revenue_tol": G_TOL,
                          "gaap_gross_margin": G_GM, "gaap_opex_musd": G_OPEX,
                          "tax_range": [0.16,0.18], "china_dc_compute": 0}},
  "variant_1_profile_as_is": run_asis(),
  "variant_2_mechanical_r1r2r3": run_mech(),
  "notes": [
    "GAAP 기준. below-OP는 variant_2에서 R2에 따라 전 시나리오 0 (지분증권 평가손익 예측 불가).",
    "variant_2는 판단 개입 0의 기계적 산출이다. 실제 Freeze-A가 이와 다르면 그 차이가 곧 '분석가의 뷰'이며, 항목별로 근거를 대야 한다.",
    "이 파일의 sha256이 정보 컷오프의 기계적 증빙이다."
  ],
}
blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
open("freeze_a_candidate.json","w",encoding="utf-8").write(blob+"\n")
print(blob)
print("\nSHA-256:", hashlib.sha256((blob+"\n").encode()).hexdigest())
