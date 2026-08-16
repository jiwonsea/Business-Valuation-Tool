"""
NVDA FY27Q2 (2026Q2) — Freeze-A CANDIDATE **v2**, 2026-08-09 KST.
v1(sha 65bfb0a3…b693)은 감사 추적 보존을 위해 수정하지 않는다. 본 파일이 v1을 supersede한다.
정정 사유: Codex 판정서 REVIEW_nvda_2026-08_plan_codex.md 조건 2 + 세션 자체 발견(R2 세분화).
정보 컷오프 불변: INFO_CUTOFF_A = 2026-08-09 23:59 KST (v1과 동일 정보집합).
"""
import json, hashlib, itertools, statistics

SEED_REV   = 81615.0
SHARES_ENG = 24490.0   # profile weighted_avg_diluted (엔진 경로)
SHARES_Q1  = 24391.0   # Q1 FY27 as-filed diluted (override 후보)
G_REV, G_TOL = 91000.0, 0.02
G_GM_GAAP, G_OPEX_GAAP = 0.749, 8500.0
G_GM_NG,   G_OPEX_NG   = 0.750, 8300.0
TAX = {"bear":0.18,"base":0.17,"bull":0.16}
P   = {"bear":0.25,"base":0.50,"bull":0.25}
# R2 세분화: 경상 순이자(예측가능) vs 마크(예측불가)
NETINT_PCT_Q1 = (540.0-102.0)/SEED_REV     # +0.5367% of revenue

def scen_rev(k): return {"bear":G_REV*(1-G_TOL),"base":G_REV,"bull":G_REV*(1+G_TOL)}[k]

def build(gm_base, opex, shares, netint_pct, gm_step=0.005, label=""):
    out={}; w={"rev":0.0,"op":0.0,"eps":0.0}
    for k in ("bear","base","bull"):
        rev=scen_rev(k); gm=gm_base+{"bear":-gm_step,"base":0.0,"bull":gm_step}[k]
        op=rev*gm-opex; below=rev*netint_pct; pre=op+below
        ni=pre*(1-TAX[k]); eps=ni/shares
        out[k]=dict(p=P[k],revenue=rev,gross_margin=gm,op=op,op_margin=op/rev,
                    below_op=below,pretax=pre,tax_rate=TAX[k],net_income=ni,eps=eps)
        w["rev"]+=P[k]*rev; w["op"]+=P[k]*op; w["eps"]+=P[k]*eps
    out["weighted"]=dict(revenue=w["rev"],op=w["op"],eps=w["eps"]); out["_label"]=label
    out["_shares_used"]=shares; return out

# variant_1: 현 프로파일 as-is
V1={}; w={"rev":0.0,"op":0.0,"eps":0.0}
for k,g,om in (("bear",0.03,0.58),("base",0.10,0.62),("bull",0.15,0.65)):
    rev=SEED_REV*(1+g); op=rev*om; below=rev*0.01; pre=op+below
    tax={"bear":0.16,"base":0.15,"bull":0.15}[k]; ni=pre*(1-tax); eps=ni/SHARES_ENG
    V1[k]=dict(p=P[k],revenue=rev,op=op,op_margin=om,below_op=below,pretax=pre,
               tax_rate=tax,net_income=ni,eps=eps)
    w["rev"]+=P[k]*rev; w["op"]+=P[k]*op; w["eps"]+=P[k]*eps
V1["weighted"]=dict(revenue=w["rev"],op=w["op"],eps=w["eps"])
V1["_label"]="현 프로파일 as-is"; V1["_shares_used"]=SHARES_ENG

V2a=build(G_GM_GAAP,G_OPEX_GAAP,SHARES_ENG,0.0,label="R1/R3 + R2-blunt(below=0), 엔진 주식수 24,490 [CANONICAL]")
V2b=build(G_GM_GAAP,G_OPEX_GAAP,SHARES_Q1 ,0.0,label="V2a + 주식수 명시적 override 24,391 [OVERRIDE]")
V3 =build(G_GM_GAAP,G_OPEX_GAAP,SHARES_ENG,NETINT_PCT_Q1,label="R1/R3 + R2-refined(경상 순이자 앵커 + 마크 0), 엔진 주식수")
V4 =build(G_GM_NG  ,G_OPEX_NG  ,SHARES_ENG,NETINT_PCT_Q1,label="비GAAP 기준 가이드 직접산출 + 경상 순이자, 엔진 주식수")

# 레버 분해: 순차(고정 순서) + Shapley(전순열 평균·범위)
A=dict(rev=SEED_REV*1.10,om=0.62,below=0.01,tax=0.15,sh=SHARES_ENG)
B=dict(rev=G_REV,om=(G_REV*G_GM_GAAP-G_OPEX_GAAP)/G_REV,below=0.0,tax=0.17,sh=SHARES_Q1)
def _eps(rev,om,below,tax,sh): return (rev*om+rev*below)*(1-tax)/sh
KEYS=["rev","om","below","tax","sh"]
cur=dict(A); prev=_eps(**cur); seq={}
for k in KEYS: cur[k]=B[k]; n=_eps(**cur); seq[k]=n-prev; prev=n
allc={k:[] for k in KEYS}
for perm in itertools.permutations(KEYS):
    cur=dict(A); p=_eps(**cur)
    for k in perm: cur[k]=B[k]; n=_eps(**cur); allc[k].append(n-p); p=n
levers={k:dict(sequential=seq[k],shapley=statistics.mean(allc[k]),
               min=min(allc[k]),max=max(allc[k])) for k in KEYS}

payload={
 "schema":"nvda_2026q2_freeze_a_candidate/v2",
 "supersedes":{"file":"nvda_2026q2_freeze_a_candidate.json",
   "sha256":"65bfb0a3201f73127c1034780e5eb99bc908ee86aa9d6cbadebd6301f8a4b693",
   "reason":"Codex REVIEW 조건2(주식수 규약) + R2 세분화(경상 순이자 분리). v1은 수정 없이 보존."},
 "computed_at_kst":"2026-08-09","info_cutoff_a":"2026-08-09T23:59+09:00",
 "target":{"ticker":"NVDA","fiscal":"FY2027Q2","model_label":"2026Q2",
           "period_end":"2026-07-26","print_utc":"2026-08-26T21:00:00Z"},
 "inputs":{"seed_revenue_musd":SEED_REV,"shares_engine_m":SHARES_ENG,
   "shares_q1_asfiled_m":SHARES_Q1,"recurring_net_interest_pct_of_rev_q1":NETINT_PCT_Q1,
   "guidance":{"revenue_mid_musd":G_REV,"revenue_tol":G_TOL,
     "gaap_gross_margin":G_GM_GAAP,"gaap_opex_musd":G_OPEX_GAAP,
     "nongaap_gross_margin":G_GM_NG,"nongaap_opex_musd":G_OPEX_NG,
     "tax_range":[0.16,0.18],"china_dc_compute":0}},
 "variant_1_profile_as_is":V1,
 "variant_2a_mechanical_engine_shares":V2a,
 "variant_2b_mechanical_shares_override":V2b,
 "variant_3_r2_refined":V3,
 "variant_4_nongaap_basis":V4,
 "lever_decomposition_v1_to_v2b":levers,
 "notes":[
  "CANONICAL = variant_2a. 엔진 주식수를 쓰므로 project_scenario 재현 대조가 가능하다.",
  "variant_2b의 주식수 변경은 별도 레버로 분리 보고한다 (Codex 조건2).",
  "variant_3: R2의 'base 0'은 예측불가 마크에만 적용하고, 현금 50,335에서 나오는 경상 순이자(+0.5367% of rev)는 앵커한다.",
  "variant_4: 컨센 기준이 비GAAP일 경우의 동질 비교 대상. GAAP/비GAAP 어느 쪽인지 확정 전까지 둘 다 보유.",
  "레버 분해는 경로 의존적이다. sequential은 고정 순서(rev→om→below→tax→sh), shapley는 5!=120 순열 평균.",
 ],
}
blob=json.dumps(payload,ensure_ascii=False,sort_keys=True,indent=2)
open("nvda_2026q2_freeze_a_candidate_v2.json","w",encoding="utf-8").write(blob+"\n")
h=hashlib.sha256((blob+"\n").encode()).hexdigest()
for name,v in (("V1",V1),("V2a",V2a),("V2b",V2b),("V3",V3),("V4",V4)):
    b=v["base"]; wt=v["weighted"]
    print(f"{name:4} {v['_label'][:52]:54} base rev {b['revenue']:>8,.0f} OP {b['op']:>7,.0f} OPM {b['op_margin']*100:5.2f}% EPS {b['eps']:.4f} | wtd EPS {wt['eps']:.4f}")
print("\nSHA-256:",h)
