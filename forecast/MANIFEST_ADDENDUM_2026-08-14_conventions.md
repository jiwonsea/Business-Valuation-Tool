# MANIFEST ADDENDUM — 2026-08-14 (개선 채택분 구현: P-1~P-6·P-8)

> `MANIFEST_ADDENDUM_nvda_2026-08-14_freeze_a.md` 에 이어 append. **기존 매니페스트 무수정** (P0 정책).
> 모든 해시는 `scripts/t3/gen_manifest_conv.py` 가 파일에서 직접 계산 — 손타이핑 0.

**Codex 판정 (2026-08-14):** P-1·P-2·P-3·P-4 `ADOPT P0` · P-5·P-6·P-8 `ADOPT P1` · P-7 `DEFER P2` (조건: 다음 신규 생성기와 함께 최소 genlib 도입 → 신규 2개 이상에서 인터페이스 검증 → 기존 해시 고정 생성기는 영구 비이관). REJECT 없음. **사용자 승인 (2026-08-14): 구현 순서 ①~④ 전부.**

**경계 준수 확인:** 계획 rev-3b 무개정 (08-28 T-4 최종은 현행 로컬 규약, 3요소 규격은 차기 템플릿부터) · 기존 해시 고정 산출물·생성기 무수정 · P-6 은 읽기 전용 목록화까지 — 활성 스크립트 실수정은 별도 승인 대상으로 미착수 · genlib 미생성 (P-7 DEFER).

| 파일 | sha256 | bytes | 비고 |
|---|---|---:|---|
| `docs/CONVENTIONS_verdict_authoring.md` | `08ce7a34e3f57c869e6fe52bdf24aa4f06675273e546fa77fc4bb7c37aa813b7` | 4,669 | P-1~P-4 규약: RC 3요소(관측원·임계값 사전등록·층 라벨)·역산 OR/비식별 서술·앵커 상대 라벨·pre-flight lint 경계(FAIL=구조 불변식만) |
| `docs/CONVENTIONS_rev_audit.md` | `7814c514265baed9ce3bbfb943396687c4c12cb64dbe80e098d153b51be2eec8` | 2,789 | P-5·P-8 규약: rev 갱신 5단계(_revN_superseded→덮어쓰기→supersede→§0 이력→diff 국한성)·크로스 환경 재생성 게이트(샌드박스 ×2 + 디바이스 ×1 비트 동일·CRLF 0) |
| `scripts/t3/preflight_lint.py` | `9518edc695db8c4f4104448699a85d3ca2e69d1dfbc66d35c87947c4c0103aad` | 7,922 | P-4 구조 불변식 lint (L-1/3/6 FAIL·L-2/4/5 WARN). 검증: T-4 rev-4 무결(0/0), rev-1 에서 과거 결함 C-①(L-4)·C-②(L-5)·총칭(L-2) 검출, rev-3 에서 C-⑤ 검출 |
| `reports/scan_console_safety_2026-08-14.json` | `5afae6dab8a6d92682768610ce01e79e0384b25d3d32a9dc4d50eaf94b0170f3` | 2,643 | P-6 스캔 원본 (디바이스 리포 139개 .py, 읽기 전용, 플래그 18건) |
| `reports/AUDIT_console_safety_nvda_2026-08-14.md` | `736b41dd92ec7ef06cc482f51968322e113dfeeedda31f8869ded10dcfbfe90d` | 4,410 | P-6 감사 보고서 — 동결 5건 무수정·채점 고정 2건 보류·활성 11건 수정 후보 목록화 (**수정은 별도 승인 대상**) |
| `scripts/t3/gen_audit_p6.py` | `0995f6e1f370aa52a0e0ce42abf535d5770215919c70464688ecc29b7880662e` | 5,140 | P-6 보고서 생성기 |
| `HANDOFF_CODEX_efe_improvements_2026-08-14.md` | `47b159ffd43bedb964382c25cedfbeee97b7607ea759c659b9daaad2e3ba333e` | 6,398 | 판단 요청 핸드오프 (Codex 판정의 대상 문서) |

**lint 검증 기록 (P-4):** 현행 T-4 rev-4 → `RESULT PASS fail=0 warn=0`. 감사 사본 회귀 시험 — rev-1 → C-①(L-4 동시 성립)·C-②(L-5 앵커 부재)·총칭(L-2) 3건 검출, rev-3 → C-⑤(L-2 "RC 전부") 검출. 즉 Codex 정정 5건 중 저술 시점 기계 검출 가능했던 유형을 실제 과거 문서에서 재현 검출함. 오탐 교정 3건(인용문 내 총칭·부정문 내 "고평가 확정"·L-3 표식 규칙)은 lint 소스에 반영.

**미착수 (별도 승인·별도 작업):** 활성 스크립트 콘솔/개행 수정 (AUDIT 권고 1·2) · P-7 genlib (다음 신규 생성기 시 재평가) · ERP 갱신 · NVDA 산출물 git 커밋 결정 · T-2 ② (새 세션).

---

*본 문서는 투자 자문이 아니며, 프로세스 기록 문서이다.*