# MANIFEST ADDENDUM — NVDA 2026-08-13 (T-4 초안 · T-2 ①③)

> `MANIFEST_ADDENDUM_nvda_2026-08-10_exec.md` 에 이어 append. **기존 매니페스트 무수정** (P0 정책).
> 모든 해시는 `scripts/t3/gen_manifest_t4.py` 가 파일에서 직접 계산했다 — 손타이핑 0.
> 재현: `cd scripts/t3 && LC_ALL=C PYTHONIOENCODING=ascii python3 gen_manifest_t4.py`

**승인 범위 (사용자 2026-08-13, 5항목):** ① 08-10 매니페스트 읽기 전용 검증·입력 고정 ② T-4 초안(GAAP OP·OPM 만 정량 채점, T-3/V2/T-1 은 조건·반증요건) ③ 반증조건 3개 관측 가능성 검증·UNVERIFIABLE 결론 제외 ④ T-2 ①③ 별도 진단(T-4 비오염) ⑤ 본 부록 append-only 기록. **전항 이행.**

**입력 고정 결과:** `gen_t4.py` 가 08-10 매니페스트 등재 해시 4건 + 후보 v2 `60cc8d23…bfef` 를 재계산 대조 — **전건 일치** (불일치 시 생성이 실패하는 fail-closed 구조).

**Codex 검증 이력 (T-4):** rev-1 `CONDITIONAL` — 기계 검증(해시 11건·결정성·입력 고정·UNVERIFIABLE 미유입 검사·RC-1′/2′ 관측 가능성) 전건 PASS, 판정 논리 정정 3건 요구 → rev-2 반영: ① 축 결합 논리("동시 성립" → 단일-변수 조건부 해·조합 비식별) ② "안전마진 부재 확정" → "7/10 as-run DCF 기준" 한정 ③ RC-1′/2′ = 약화 관측(반전 트리거 아님). rev-2 `CONDITIONAL` — ①~③ 정확 반영·재생성 해시 일치 확인, 잔여 1건 → rev-3 반영: ④ RC-3′ 수치 임계값 사전등록 부재 → 서술적 약화 신호로 강등, **관측 판정은 RC-1′·RC-2′ 2개로만** (사용자 승인 2026-08-13; 임계값 사전등록 대안은 N=1·비정상 잔액이라 기각). rev-3 `CONDITIONAL` — ④ 반영·diff 국한성·수치 불변·F-2 파괴시험 전건 PASS, 잔여 문구 1건 → **rev-4 반영**: ⑤ §3 역방향 문장 "RC 전부 미발화" → "RC-1′·RC-2′ 모두 미발화" (Codex 권장 문구 채택, RC-3′ 를 판정 경로에서 완전 제거). rev-1~3 원본은 `_rev1/_rev2/_rev3_superseded.md` 로 보존. 핸드오프 rev-4 는 본 부록 이후 생성 — 해시는 핸드오프 자신의 §1 과 세션 보고에 기록.

| 파일 | sha256 | bytes | NUL | 비고 |
|---|---|---:|:--:|---|
| `reports/T4_verdict_draft_nvda_2026-08-13.md` | `b250f9b887604cdc63dd66e3a1ef943b4fbdafdc30ed3ef156934c36e5fda7de` | 11,490 | clean | T-4 판정 초안 **rev-4** — "적정 상단~고평가 · 7/10 as-run DCF 기준 안전마진 부재 확정 · 확신도 낮음". 정정 ①~⑤ 반영: 단일축 조건부 해·as-run 기준 라벨·RC 약화-비반전·RC-3′ 서술 강등(판정 트리거는 RC-1′·RC-2′ 2개)·역방향 문장 RC-1′·RC-2′ 한정 |
| `reports/T4_verdict_draft_nvda_2026-08-13_rev1_superseded.md` | `f6d828448d898331e7675454a88edeca8e878029b7a3d52832b332d437254854` | 8,866 | clean | 감사추적 — rev-1 원본 보존 (Codex CONDITIONAL 대상판, 수정·삭제 금지) |
| `reports/T4_verdict_draft_nvda_2026-08-13_rev2_superseded.md` | `ab7b97f4f85988d63ab92e0d91e5cb1d92d419bac7463440e74f12380c35569a` | 10,205 | clean | 감사추적 — rev-2 원본 보존 (Codex CONDITIONAL: ①~③ 반영 확인·잔여 ④, 수정·삭제 금지) |
| `reports/T4_verdict_draft_nvda_2026-08-13_rev3_superseded.md` | `655f61c1087910db36dc5a31604fd4a30004b22d338d666f658bb5f222339ee3` | 11,168 | clean | 감사추적 — rev-3 원본 보존 (Codex CONDITIONAL: ④ 반영 확인·잔여 ⑤ 문구 1건, 수정·삭제 금지) |
| `reports/T2_buckets_1_3_nvda_2026-08-13.md` | `65d8eda557ab94fe5faf9ac2c862ff52b1004f9839c2af3a7b995608709230f2` | 4,483 | clean | T-2 ①(경상 순이자 앵커 +488@mid)·③(UNFORECASTABLE 선언) — 진단 전용, T-4 비오염. ② 는 13F 후 |
| `HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev1.md` | `467ce5c7508d6301f3656c9c768c2a6e70a9bb16cd0f6dcbfabb4847d2278220` | 8,807 | clean | 감사추적 — rev-1 검증 발주 시점 사본 (Codex 판정: CONDITIONAL) |
| `HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev2.md` | `8c741764dd8e62580c570928cb0807673fe376a5af767ffcd430ea667b2b1083` | 11,073 | clean | 감사추적 — rev-2 검증 발주 시점 사본 (Codex 판정: CONDITIONAL, ①~③ 반영 확인) |
| `HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev3.md` | `49ba9c4e42519d749f660341794edb5eb12ba7acd384722934e6ed23f9bce835` | 11,937 | clean | 감사추적 — rev-3 검증 발주 시점 사본 (Codex 판정: CONDITIONAL, ④ 반영 확인·잔여 ⑤) |
| `scripts/t3/gen_t4.py` | `c0b0dc123e0e9171132052db1f56dc20a9ad0868e2d70b14785e6b7d2920476b` | 17,065 | clean | T-4 생성기 rev-4 (입력 5건 해시 fail-closed 검증 내장) |
| `scripts/t3/gen_t2.py` | `a49c4d4567edebabeaf8d56f2e5b769ff2133a3d63b6268ec955f60aa6d63e19` | 7,841 | clean | T-2 ①③ 생성기 (후보 v2 해시 검증 내장) |
| `scripts/t3/gen_handoff_t4.py` | `02a7407c498b7215dda4c4919adc14ee4e340f9d93c988c5657c4f1afb61ff86` | 18,217 | clean | 핸드오프 생성기 (UNVERIFIABLE 미유입 기계 검사 F-5 내장) |

**미착수 (예정):** T-2 ② 시장성 마크 — 13F(06-30 기준) 수신 후 08-14 · Freeze-A — 08-13 후보 v2 `variant_2a` 재현 검증 · T-4 최종 — 08-28~29 (§6.1 3단 분리 채점 이후).

---

*본 문서는 투자 자문이 아니며, 모델 방법론 검증 목적의 내부 분석이다.*