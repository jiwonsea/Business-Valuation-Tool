# MANIFEST ADDENDUM — NVDA 2026-08-10 실행 (T-3·V2·BASIS·T-1)

> `MANIFEST_nvda_2026-08-09.md` 에 append. **기존 해시는 수정하지 않는다** (P0 사실원장 정책).
> 본 부록의 모든 해시는 `scripts/t3/gen_manifest.py` 가 **파일에서 직접 계산**했다 — 손타이핑 0.
> 재현: `cd scripts/t3 && LC_ALL=C PYTHONIOENCODING=ascii python3 gen_manifest.py`

**정보 컷오프:** INFO_CUTOFF_A(2026-08-09 23:59 KST) 불변. 08-10 산출물은 원장 A 사실 + 컷오프 이내 1차 자료(2026-08-07 Treasury, NVDA 분기 보도자료)만 사용. 컷오프 이후 관측치 노출은 각 문서의 '컷오프 위생' 절에 기록.

**Codex 검증 이력:** T-3 rev-1 `FAIL` → rev-2 `CONDITIONAL PASS` → rev-4 `PASS` → rev-6 `FAIL`(정의 혼재) → **rev-7 `PASS`** · V2/BASIS 검증 `PASS`.

| 파일 | sha256 | bytes | NUL | 비고 |
|---|---|---:|:--:|---|
| `reports/T3_nvda_2026-08-10.md` | `a0844e0c74432ce366a809d2371644a8dddf38a6deab952ee77938ca6235fdb1` | 27,185 | clean | T-3 역방향 DCF rev-7 — Codex 검증 rev-1 FAIL→rev-4 PASS→rev-7 PASS |
| `reports/V2_rf_overlay_nvda_2026-08-10.md` | `9d3a776d4ef9b569957c4120eecf68b04ca0228327bde31abb74c13ddc860781` | 6,091 | clean | V2 — 2026-08-07 UST 10Y 4.65% 확정, βL 0.874 (rf 해소·ERP 미해소) |
| `reports/BASIS_consensus_verification_nvda_2026-08-10.md` | `d5028e3b3e36d8b9af3ddcf9405cd2b5e8a409c0858c4561cebca4b928ad1b4d` | 9,339 | clean | BASIS — 3/3 BASIS_UNKNOWN · 결정 ②((d) 영구 서술용 강등) · Codex PASS. ⚠️ supersedes 초판 `a71ea3e9…be83`(결정 ②·재사용규칙 반영 전, 미배포 폐기) |
| `reports/T1_vendor_financing_nvda_2026-08-10.md` | `16b029cc5a51ebba8bdcdeb0723499d1bcb1bf0cdb874c645c604299a02e1d9f` | 9,543 | clean | T-1 — 착수조건 3건 충족, 밴드 하단 34,060(realized)뿐 → 정성 강등 |
| `HANDOFF_CODEX_nvda_2026-08_t3_reverse_dcf_rev7.md` | `ab9664a967f5a84ca00595e4632e22a78145bcee499c751472228db9b24bc58f` | 20,387 | clean | 검증 요청 최종본 (rev-2~6 은 감사추적 보존) |
| `scripts/t3/bvt_dcf.py` | `c8727462cdbc6032cbf48468f9832a85b920f2df25a7a2a618e068938a82321a` | 7,340 | clean | BVT 엔진 포팅 (V1 게이트 검증) |
| `scripts/t3/t3_reverse_dcf.py` | `c1e326d8493a78e0991d31e63a0832f1a98828471a04b1b2c0b65c46f5479d8e` | 13,965 | clean | 앵커·축 정의 |
| `scripts/t3/t3_final.py` | `2880d38a11b13ede67f5c4dae715105c5ee56131c4ce72493905cebed9ea5815` | 41,575 | clean | T-3 산출물 생성기 |
| `scripts/t3/gen_handoff.py` | `eca8fd29f41939b11a5b61fe199ebf43ac84e84f02f592d9608a174a9c82826a` | 29,537 | clean | 핸드오프 생성기 |
| `scripts/t3/gen_v2.py` | `99057f76343ca8cb00ef211562be06158e31000d70583a291a59776a439b547a` | 9,715 | clean | V2 생성기 |
| `scripts/t3/gen_basis.py` | `ca56a9920d3c8ca06025a87ee5b3075b478db81f68faada9f747c1dd881a6ca7` | 13,475 | clean | BASIS 생성기 |
| `scripts/t3/gen_t1.py` | `90e400b9edcd9dea5be9a8a3dd72f47a998ebfd04f6e50be0e6e37bfd5bc5320` | 14,321 | clean | T-1 생성기 |

**해시 정정 기록 (Codex 지적, 2026-08-12):** BASIS 문서의 세션 대화 인용 해시 `a71ea3e9…be83` 은 **결정 ②·재사용 규칙 반영 전 초판**이다. 유효 해시는 위 표의 값이며, 이후 인용은 본 매니페스트를 기준으로 한다.

**감사추적 보존 (무수정):** `HANDOFF_..._rev2.md` `2d9d1c13…` · `_rev3.md` `8bbb5355…` · `_rev4.md` `07502322…` · `_rev5.md` `bd315249…` · `_rev6.md` `1bffa4ca…` — 각 rev 발주 시점 사본. 수정·삭제 금지.

---

*본 문서는 투자 자문이 아니며, 모델 방법론 검증 목적의 내부 분석이다.*