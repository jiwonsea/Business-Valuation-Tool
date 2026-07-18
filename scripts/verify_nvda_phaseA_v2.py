"""NVDA Phase A 구현 검증 v2 (LOCAL 전용).
v2: βL 기대값 1.697(실측 2yr 주간 OLS) + beta_provenance 완결성 체크.
    1.811은 info[beta] 기반 Claude 추정치였고, 실측 raw OLS βL=2.040 → Blume 1.697이 정답.
Usage: python scripts/verify_nvda_phaseA_v2.py
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_fails = []


def chk(label, ok, detail=""):
    if not ok:
        _fails.append(label)
    print("  [%s] %s%s" % ("PASS" if ok else "FAIL", label, ("  -> " + detail) if detail else ""))


def main():
    import yaml
    from valuation_runner import apply_net_debt_gate, load_profile, run_valuation

    print("=" * 70)
    print("NVDA Phase A 검증 v2")
    print("=" * 70)

    y = yaml.safe_load((ROOT / "profiles" / "nvda.yaml").read_text(encoding="utf-8"))
    bp = y.get("beta_provenance", {})
    w = y["wacc_params"]

    print("\n--- 프로필 입력값 ---")
    chk("bu = 1.694", abs(w["bu"] - 1.694) < 0.003, str(w["bu"]))
    chk("erp = 4.18 (snapshot)", abs(w["erp"] - 4.18) < 0.01, str(w["erp"]))
    chk("rf = 4.44 (snapshot basis)", abs(w["rf"] - 4.44) < 0.01, str(w["rf"]))
    chk("tax = 17.0", abs(w["tax"] - 17.0) < 0.05, str(w["tax"]))
    chk("beta status = consumed_blume", bp.get("status") == "consumed_blume", str(bp.get("status")))

    print("\n--- Blume 산식 역검증 (raw OLS 2.040 → Blume → unlever) ---")
    raw = 2.040
    blume = 0.67 * raw + 0.33
    bu_calc = blume / (1 + (1 - w["tax"] / 100) * w["de"] / 100)
    chk("Blume math: 0.67*2.040+0.33 → unlever = bu", abs(bu_calc - w["bu"]) < 0.003,
        "blume=%.4f bu=%.4f (프로필 %.3f)" % (blume, bu_calc, w["bu"]))

    print("\n--- 🔴 beta_provenance 완결성 (내 §A3 사양 대비) ---")
    for f in ("raw_levered_beta", "blume_adjusted", "normalized_bu",
              "window_start", "window_end", "frequency", "calculation_method"):
        chk("provenance 필드 '%s' 값 기록" % f, f in bp, "누락 (감사 시 캐시 재계산 필요)")
    chk("source_hash 존재", bool(bp.get("source_hash")), str(bp.get("source_hash"))[:16])

    print("\n--- 캐시 파일 무결성 (source_hash 대조) ---")
    cache = list((ROOT / ".cache" / "beta_observations").glob("NVDA_*.json"))
    if cache:
        raw_bytes = cache[0].read_bytes()
        h = hashlib.sha256(raw_bytes).hexdigest()
        chk("캐시 SHA-256 == 프로필 source_hash",
            h == bp.get("source_hash"),
            "cache=%s.. profile=%s.." % (h[:12], str(bp.get("source_hash"))[:12]))
        cj = json.loads(raw_bytes)
        n_stock = len(cj.get("stock_returns", []))
        chk("캐시 관측치 >= 80주", n_stock >= 80, "n=%d" % n_stock)
        chk("캐시 observation_count == 프로필",
            n_stock == bp.get("observation_count") or
            n_stock + 1 == bp.get("observation_count"),
            "cache_returns=%d profile=%s" % (n_stock, bp.get("observation_count")))
    else:
        chk("캐시 파일 존재", False, "없음")

    print("\n--- 엔진 실행: WACC + 품질 게이트 ---")
    vi = apply_net_debt_gate(load_profile(str(ROOT / "profiles" / "nvda.yaml")))
    res = run_valuation(vi)
    chk("WACC ≈ 11.52%", abs(res.wacc.wacc - 11.52) < 0.05, "%.2f%%" % res.wacc.wacc)
    chk("βL ≈ 1.697", abs(res.wacc.bl - 1.697) < 0.02, "%.4f" % res.wacc.bl)
    q = res.quality
    chk("CV convergence = 0/25", getattr(q, "cv_convergence", None) == 0,
        str(getattr(q, "cv_convergence", None)))
    chk("품질 total ≈ 45 이하 (gate 전) 또는 0 (gate 후)",
        getattr(q, "total", 99) <= 45, "total=%s grade=%s" % (getattr(q, "total", "?"), getattr(q, "grade", "?")))

    print("\n--- 🔴 넥써쓰 불변 (과잉수정 검출) ---")
    xr = run_valuation(apply_net_debt_gate(load_profile(str(ROOT / "profiles" / "nexus.yaml"))))
    ps = {c: s.post_dlom for c, s in xr.scenarios.items()}
    ar = {c: s.receivable_recovery_value for c, s in xr.scenarios.items()}
    wsum = sum(s.weighted for s in xr.scenarios.values())
    chk("넥써쓰 주당 18/445/891", ps == {"Bear": 18, "Base": 445, "Bull": 891}, str(ps))
    chk("넥써쓰 AR 5503/12440/15564",
        ar == {"Bear": 5503, "Base": 12440, "Bull": 15564}, str(ar))
    chk("넥써쓰 확률가중 362", wsum == 362, str(wsum))
    chk("넥써쓰 Base equity 36,211", xr.scenarios["Base"].equity_value == 36211,
        str(xr.scenarios["Base"].equity_value))
    chk("넥써쓰 net_debt 51,687", xr.scenarios["Base"].net_debt == 51687,
        str(xr.scenarios["Base"].net_debt))

    print("\n" + "=" * 70)
    print("FAIL %d건: %s" % (len(_fails), _fails) if _fails else "ALL PASS")
    print("=" * 70)
    return 1 if _fails else 0


if __name__ == "__main__":
    sys.exit(main())
