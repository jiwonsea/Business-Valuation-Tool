# MANIFEST — NVDA 2026-08 심층 리서치 동결 증빙

> 확정 2026-08-09 KST · INFO_CUTOFF_A = 2026-08-09 23:59 KST
> 이 해시들이 정보 컷오프의 기계적 증빙이다. 이후 어떤 파일도 수정되면 해시가 달라진다.
> 오류 발견 시 본문 수정 금지 — 별도 errata append 마커로만 처리한다 (P0 사실원장 정책).

| 파일 | sha256 | bytes | lines |
|---|---|---:|---:|
| `PLAN_nvda_2026-08_deep_dive.md` | `9a2650979f78034250cf239314397b61b0e3f448ac7ef3af97b4048c0f006c8d` | 32,513 | 377 |
| `HANDOFF_CODEX_nvda_2026-08_plan_review.md` | `4cf3cc7ffe3745e54ebc3cb6ebd24ed50cb6774d35abc4777172fc702c208427` | 14,248 | 155 |
| `nvda_2026q2_information_ledger_A.md` | `55d2ce36af7c72c6374dd42b61bb246b24f494a74da6979f7e1842c9e744d19f` | 21,073 | 215 |
| `nvda_2026q2_freeze_a_candidate.json` | `65bfb0a3201f73127c1034780e5eb99bc908ee86aa9d6cbadebd6301f8a4b693` | 2,797 | 107 |

**NUL 스캔:** 4/4 clean.

**재현:** `python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" <파일>`
