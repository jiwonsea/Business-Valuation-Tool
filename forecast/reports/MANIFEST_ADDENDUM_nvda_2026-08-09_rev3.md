# MANIFEST ADDENDUM — NVDA 2026-08 (rev-3, 2026-08-09 KST)

> 2026-08-09 `MANIFEST_nvda_2026-08-09.md`에 append. **기존 해시는 수정하지 않는다** (P0 사실원장 정책).
> 정정 사유: Codex 판정서 `REVIEW_nvda_2026-08_plan_codex.md` CONDITIONAL 조건 7건 + 세션 신규지적 4건.
> **INFO_CUTOFF_A 불변** — 후보 v2는 v1과 동일 정보집합이며 산식만 정정했다.

## 신규 (rev-3)

| 파일 | sha256 | bytes | lines |
|---|---|---:|---:|
| `PLAN_nvda_2026-08_deep_dive.md` | `7f6321bee925e1cc59b77e688ffa55faf5ebb1d9fa1bf3193de4185f4e82366f` | 27,980 | 327 |
| `REPLY_nvda_2026-08_plan_codex.md` | `da4029fc2539e0704f4174ab8621721369338dbf7bc8522ffa9e26c207b2af1e` | 11,776 | 115 |
| `nvda_2026q2_freeze_a_candidate_v2.json` | `60cc8d23cc916444d062a530eb49c0f627b1e10ac8239fd9affe9e06419bfbef` | 8,390 | 297 |
| `nvda_2026q2_freeze_a_candidate_v2.py` | `ca8c1dd528f56f527ce8d85027bbdd2652e5cd7dfb1b845f3b4f701c3311f10c` | 5,913 | 98 |

## 기존 (불변 · 감사추적 보존)

| 파일 | sha256 |
|---|---|
| `PLAN_nvda_2026-08_deep_dive.md (rev-2, SUPERSEDED)` | `9a2650979f78034250cf239314397b61b0e3f448ac7ef3af97b4048c0f006c8d` |
| `HANDOFF_CODEX_nvda_2026-08_plan_review.md (rev-2, 불변)` | `4cf3cc7ffe3745e54ebc3cb6ebd24ed50cb6774d35abc4777172fc702c208427` |
| `reports/nvda_2026q2_information_ledger_A.md (불변)` | `55d2ce36af7c72c6374dd42b61bb246b24f494a74da6979f7e1842c9e744d19f` |
| `reports/nvda_2026q2_freeze_a_candidate.json (v1, 무수정 보존)` | `65bfb0a3201f73127c1034780e5eb99bc908ee86aa9d6cbadebd6301f8a4b693` |

**supersede 관계:** 후보 v1 `65bfb0a3…b693` → v2 `60cc8d23…bfef` (v1 파일은 삭제·수정하지 않음). PLAN rev-2 `9a265097…6c8d` → rev-3.

**NUL 스캔:** 4/4 clean.

---

## rev-3a 정정 (2026-08-09, Codex 2차 회신 반영)

> 정정 2건: ① §3-4 "결정적 검증" → **`BASIS_VERIFIED_EMPIRICALLY` 3등급**으로 강등 (데이터 제공자가 actual/estimate를 항상 동일 조정기준으로 저장한다는 보장 없음) ② REPLY 서두 "신규 지적 3건" → **4건** (§3 실제 항목수와 불일치).
> **후보 v1·v2, 원장 A는 무수정.** 정보 컷오프·수치 불변.

| 파일 | sha256 (rev-3a) | bytes | lines |
|---|---|---:|---:|
| `PLAN_nvda_2026-08_deep_dive.md` | `ec251eacf4a844c56c85ebf65a2ebdc6727eb617d363bc8e6d2369987ab2c0d4` | 28,785 | 336 |
| `REPLY_nvda_2026-08_plan_codex.md` | `48156776e461c531df18b5e7afb87358a50449bad63aa017d8f16fc0c1d4c58d` | 12,229 | 116 |

**supersede:** PLAN rev-3 `7f6321be…366f` → rev-3a · REPLY `da4029fc…af1e` → rev-3a. **NUL 스캔 2/2 clean.**

**errata (rev-3a-final):** 위 rev-3a 표의 PLAN 해시는 부분 패치 시점 값이다. 잔여 3개소('결정적 검증' 표기) 정리 후 최종 해시는 `c885e98383aff54f2bc2ac0d2a83826daac55d81fba25d0f1ae33e2a05d4fdba` (28,858 bytes, 336 lines)이며, 이 값이 유효하다.

---

## rev-3b (2026-08-09, 사용자 결정 2건 확정)

> ① **사후 채점 = 분리 판정 확정** — Codex(산술) + fresh Cowork 세션(발화·테제, source packet만) + 사용자 최종 승인. §6.1에 packet 포함/제외 규격 명문화.
> ② **N-1(레버 Shapley 규약) 신규 적용 승인** — NVDA가 첫 적용, 기존 7종 소급 감사 미실시(주석만). **N-2(R2 3버킷) 보류** — NVDA 국소 적용만, generic 스키마 무변경.
> 후보 v1·v2, 원장 A 무수정. 수치·정보컷오프 불변.

| 파일 | sha256 (rev-3b) | bytes | lines |
|---|---|---:|---:|
| `PLAN_nvda_2026-08_deep_dive.md` | `5d6f47433539c9e234c732e25bc39223d726ea82960cc342c1e6fdcaa0c85b30` | 30,998 | 352 |

**supersede:** rev-3a-final `c885e983…fdba` → rev-3b. **NUL 스캔 clean.**

**errata (rev-3b-final):** 소급 표기 2개소 정리 후 최종 해시 `e0c55630ea121fd3d6a8100d17cdcc9117d338954fa34a192eb34b66601b00c6` (31,160 bytes, 352 lines). 이 값이 유효하다.
