# START — NVDA 2026-08-10 실행 (T-3 역방향 DCF 착수)

> 작성 2026-08-09 KST · 계획 검토 워크스트림 종료 시점에 남김
> **새 세션에서 아래 프롬프트를 그대로 사용한다.** 이전 세션 컨텍스트를 상속하지 않는 것이 목적이다 — T-3은 판단 오염에 민감하다.

---

## 새 세션 첫 프롬프트 (그대로 복사)

```
F:/dev/Portfolio/earnings-forecast-engine 프로젝트, 이전 세션과 무관.
PLAN_nvda_2026-08_deep_dive.md rev-3b와 REPLY_nvda_2026-08_plan_codex.md를 기준으로 08-10 실행을 시작해줘.
우선 T-3 역방향 DCF를 수행하되, 착수 전:
1. rev-3b 커밋·매니페스트·후보 v1/v2·정보원장 A 해시를 읽기 전용 검증
2. BVT 기존 7/10 모델과 필요한 입력·출력 확인
3. T-3의 명시적 완료 조건과 검증식을 짧게 제시
T-1은 1일 타임박스로 병행하되 T-3을 막지 말고, BASIS 경험 검증과 V-SEG는 계획의 fail-closed/중단 규칙을 준수해줘.
계획서와 동결 후보는 승인 없이 수정하지 마.
```

---

## 검증 1단계용 기준 해시 (읽기 전용 대조)

재현: `python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" <파일>`

| 파일 | sha256 | 상태 |
|---|---|---|
| `PLAN_nvda_2026-08_deep_dive.md` | `e0c55630ea121fd3d6a8100d17cdcc9117d338954fa34a192eb34b66601b00c6` | **rev-3b-final · 유효** (31,160 bytes, 352 lines) |
| `REPLY_nvda_2026-08_plan_codex.md` | `48156776e461c531df18b5e7afb87358a50449bad63aa017d8f16fc0c1d4c58d` | rev-3a · 유효 (12,229 bytes, 116 lines) |
| `HANDOFF_CODEX_nvda_2026-08_plan_review.md` | `4cf3cc7ffe3745e54ebc3cb6ebd24ed50cb6774d35abc4777172fc702c208427` | rev-2 · 불변 |
| `reports/nvda_2026q2_information_ledger_A.md` | `55d2ce36af7c72c6374dd42b61bb246b24f494a74da6979f7e1842c9e744d19f` | **INFO_CUTOFF_A 증빙 · 무수정** |
| `reports/nvda_2026q2_freeze_a_candidate.json` | `65bfb0a3201f73127c1034780e5eb99bc908ee86aa9d6cbadebd6301f8a4b693` | v1 · **감사추적 보존, 수정 금지** |
| `reports/nvda_2026q2_freeze_a_candidate_v2.json` | `60cc8d23cc916444d062a530eb49c0f627b1e10ac8239fd9affe9e06419bfbef` | **v2 · CANONICAL = `variant_2a`** |

⚠️ `REVIEW_nvda_2026-08_plan_codex.md`(Codex 판정서)는 해시 미등록 — Codex 산출물이므로 대조 대상 아님.
매니페스트: `reports/MANIFEST_nvda_2026-08-09.md` + `reports/MANIFEST_ADDENDUM_nvda_2026-08-09_rev3.md` (rev-3 / rev-3a / rev-3b 이력 append-only).

**불일치 시:** 즉시 중단하고 사용자에게 보고한다. 후보·원장이 바뀌었다면 **정보 컷오프 증빙이 깨진 것**이므로 Freeze-A를 진행할 수 없다.

---

## 08-10 실행 항목 (계획 §7)

| 순위 | 항목 | 계획 참조 | 완료 조건 |
|---|---|---|---|
| **1** | **T-3 역방향 DCF** | §0.3 | $223.96과 PT $302.83 각각이 요구하는 성장·마진·듀레이션·WACC 역산 → "시장이 가격에 넣은 가정" 1페이지 |
| 2 | **BASIS 경험 검증** (30분) | §2-3 | 3개 애그리게이터 × 과거 3분기 actual EPS 조회 → 소스별 `BASIS_DECLARED`/`BASIS_VERIFIED_EMPIRICALLY`/`BASIS_UNKNOWN` 등급 부여 |
| 3 | **V-SEG 점검** | §5 | 7/10 SOTP의 SEG1~3 매핑 vs Q1 FY27 신기준(Hyperscale/ACIE/Edge). **stale이면 프린트-전 BVT 중단** |
| 4 | **T-1 벤더파이낸싱** (1일 타임박스, 병행) | §0.3 | counterparty-project dedupe + realized/committed/negotiating 3분 + 매출 인식기간 정의. **불가 시 즉시 정성 강등** |

**T-3을 막지 않는다:** 2·3·4 중 무엇이 막혀도 T-3은 진행한다.

---

## 지켜야 할 규칙 (계획에서 발췌)

- **계획서·동결 후보·정보원장은 승인 없이 수정 금지.** 오류 발견 시 errata append 마커로만.
- **모든 표는 스크립트 생성.** 손타이핑 금지 (rev-1·rev-2에서 같은 표에 연속 2회 산술 오류가 났다).
- **레버 귀인은 순서 고정+명시 또는 Shapley 병기** (N-1 규약, 신규 적용 승인됨).
- **BVT 프린트-전은 공정가치 숫자를 산출하지 않는다.** 실적 앵커가 08-27까지 불변이므로 "$207→$21X"는 주가 상승의 재기술이다.
- **V5(시나리오 확률)는 프린트 후.** 주가를 보고 확률을 정한 뒤 그 확률가중값을 주가와 비교하면 순환.
- **N-2(R2 3버킷)는 보류** — NVDA 국소 적용만, generic 스키마 무변경.
- 샌드박스 EDGAR는 **WebFetch로만** 접근(프로세스 레벨 403). 리포 실행은 tar→stage→/tmp 추출.

---

## 이후 일정 (계획 §7)

`08-11~12 T-4 판정 초안·T-2` → `08-13 프로파일 교정 + Freeze-A(후보 v2 variant_2a 재현 검증) → SendUserFile` → `08-14 13F(06-30 기준) → T-2 ②버킷` → `08-14~26 원장 B·트리거 감시` → **`08-27 03:00 KST Freeze-B`** → **`08-27 06:00 KST 프린트`** → `08-27 채점 3단 분리 발주(§6.1)` → `08-28~29 T-4 최종` → `08-30~31 적대적 검증 → PDF`

**미착수 별도 트랙(§9):** G-A/G-B/G-C(EFE 하드닝 세션) · N-3(rolling-origin benchmark). **투자판단 critical path 아님 — 이것들이 막혀도 T-3/T-4는 진행한다.**
