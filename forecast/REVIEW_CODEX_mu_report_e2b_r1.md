# MU FY2026 Q4 report R14 — E2-B 사전 게이트 리뷰 r1

> 결론: **BLOCKED — `conflict_confirmation.yaml` 미존재, ed1 파일 렌더 없음.**
> 본 문서는 투자 자문이 아니다. R14가 요구한 준비·원천 재계산·비렌더 사전 검사는 완료했으며, 발행 산출물은 만들지 않았다.

## 1. 서술 연결·fact 바인딩

### 1.1 기준선

| 입력 | 요구 SHA-256 | 재확인 | 판정 |
|---|---|---|---|
| `forecast/inputs/mu_fy2026q4_report_assumptions.yaml` | `292f4dce0ef5242e8072ce14d87320e022aa68ecb828712a8dd647752592c539` | 일치 | PASS |
| `forecast/REVIEW_CODEX_mu_report_rle_values_r2.md` | `8012d34a8881567568b20fc440771156390f2426b942c36c8b9f33f0847fa74a` | 일치 | PASS |
| `forecast/inputs/mu_fy2026q4_narrative_ed1.yaml` | `e64613caeabfaf9d833c88c4d4111c8c3d682c495fab99d631c8f57c3b651dfe` | 일치 | PASS |

### 1.2 연결 결과

- 초안 문장을 수정하지 않고 thesis·scenarios·risks·catalysts를 각각 2·8·10·11절에 넣는 ed1 전용 조립 경로를 추가했다. KO/EN의 구조와 fact 토큰 순서를 fail-closed로 검사한다.
- 나머지 절은 짧은 KO/EN 연결 문장 뒤에 기존 표·차트가 붙도록 분리했다. fixture와 DRYRUN은 기존 `section_stub` 경로를 그대로 사용한다.
- ed1 조립 경로에는 `section_stub`·`FIXTURE`·미해결 `{{fact:...}}`가 남으면 실패하는 게이트를 추가했다. 파일 렌더 없이 메모리 단위 테스트로 미해결 토큰 0을 확인했다.
- 부록 조립 경로에 R9 v1 규칙표, R12 사후 변경 3건(원안·변경·사유·근거 쪽), R13 A11 net-capex roll-forward 해석과 한계, R9-0 기록 시점 한계, 연간 `ΔNWC = k × (FY27E 매출 − FY26A 매출)` 적용 문장을 KO/EN으로 넣었다.
- 차트 ⑧과 재무 표의 라벨을 `순현금(SCA 예치금 미조정)` / `Net cash (not adjusted for SCA deposits)`으로 통일했다. 구 라벨은 ed1 조립 결과에 없다.
- 서술 문장에서 별도 사실 오류는 발견하지 않았다. 문장 자체는 변경하지 않았다.

### 1.3 원천 재계산과 초안 대조

`ex991.htm`, `mu_fy2026q4_SCORED.md`, RLE YAML 규칙을 각각 직접 읽어 재계산했다. 초안 값은 기재 자릿수의 반올림 허용범위로만 대조했으며 12개 모두 일치했다.

| manifest fact_id | 원천 재계산값 | 초안 값 | 판정 |
|---|---:|---:|---|
| `guidance.revenue_mid.FQ1FY27` | 61,500 | 61,500 | PASS |
| `guidance.revenue_lo.FQ1FY27` | 60,000 | 60,000 | PASS |
| `derived.weekly_growth.FQ1FY27_guide` | 0.221316440111 | 0.221316 | PASS |
| `bs.customer_contract_liabilities.FQ4FY26` | 12,895 | 12,895 | PASS |
| `scored.opex_gap_pct.FQ4FY26` | 0.772043010753 | 0.772 | PASS |
| `scored.eps_error.FQ4FY26` | 0.300000000000 | 0.30 | PASS |
| `rle.opex.FY27E` | 10,353 | 10,353 | PASS |
| `rle.revenue.FY27E.base` | 274,784.139585 | 274,784.14 | PASS |
| `rle.eps_gaap.FY27E.base` | 169.046535740 | 169.05 | PASS |
| `rle.eps_gaap.FY27E.bear` | 118.949491315 | 118.95 | PASS |
| `rle.eps_gaap.FY27E.bull` | 199.515745971 | 199.52 | PASS |
| `dividend.dps.declared_2026-09-30` | 0.15 | 0.15 | PASS |

## 2. E2B 사전 게이트

실행 명령: `python -m forecast.scripts.mu_report.build --phase E2B --edition 1`
종료 상태: `BLOCKED_CONFLICT_CONFIRMATION_MISSING_NO_RENDER` (의도된 exit code 2).

| 게이트 | 사전 검사 결과 | 비고 |
|---|---|---|
| G-1 | PASS | E2-A와 E2-B의 populated pin 전부 경로·SHA 일치 |
| G-2 | PASS | PREREG_A 표시값이 Freeze A와 일치 |
| G-3 | PASS | FY23A–FY25A 손익·재무상태·현금흐름 항등식 통과; FQ4 원천 수치는 별도 binding 재계산 통과 |
| G-4~G-6 | NOT APPLICABLE — PRE-RENDER | 현재 파이프라인에 비렌더 호출 대상 없음 |
| G-7 | PASS | 템플릿 숫자·직접 `open()` 검사 통과 |
| G-8 | NOT APPLICABLE — PRE-RENDER | 현재 파이프라인에 비렌더 호출 대상 없음 |
| G-9 | PASS | PREREG_A와 RLE 정보 계층 분리 |
| G-10~G-11 | NOT APPLICABLE — PRE-RENDER | 현재 파이프라인에 비렌더 호출 대상 없음 |
| G-12 | PASS | manifest 계약과 금지 valuation 필드 검사 통과 |
| G-12b | DEFERRED — RENDER | KO/EN 최종 면책문 검사는 산출물 생성 뒤 수행 |
| **G-12c** | **BLOCKED** | `forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml` 없음 |
| G-13 | DEFERRED — RENDER | 최종 차트 manifest 없음 |
| G-14 | PASS | 12개 fact 포함 source SHA·as-of·path, 계산 fact lineage 통과 |
| G-15 | PASS — STRUCTURE | KO/EN 절 구조와 fact 토큰 순서 일치; 최종 산출물 parity는 렌더 뒤 수행 |
| G-16 | DEFERRED — RENDER | 최종 캡션 없음 |
| G-17 | PASS — CONFIG | 정정 라벨 KO/EN 일치, 구 라벨 제거; 최종 출력 검사는 렌더 뒤 수행 |
| G-18 | PASS | 코드·설정·입력의 UTF-8/LF·trailing whitespace 검사 통과 |
| G-19 | PASS | 고정 비GAAP 브리지 fact 1개 계약 유지 |
| G-20 | PASS | E2-A+E2-B 모든 populated pin의 결정적 감사 목록 확인 |
| G-21 | DEFERRED — RENDER | md/html/pdf/xlsx가 없어 형식 QA 미실행 |

사전 검사 순서의 마지막에 충돌 확인 파일 존재 여부를 확인했다. 파일이 없으므로 G-12c에서 중단했고 최종 렌더 함수와 출력 경로에 진입하지 않았다.

## 3. 렌더 산출물·SHA

| 산출물 | 상태 | SHA-256 |
|---|---|---|
| KO md/html/pdf | 생성 안 함 | N/A |
| EN md/html/pdf | 생성 안 함 | N/A |
| 공유 xlsx | 생성 안 함 | N/A |
| manifest / input manifest | 생성 안 함 | N/A |
| 차트 PNG assets | 생성 안 함 | N/A |

`forecast/reports/mu_report_fy2026q4_ed1_*` 파일은 0개다.

## 4. 테스트

| 검사 | 결과 |
|---|---|
| `python -m compileall -q forecast/scripts/mu_report` | PASS |
| `python -m pytest forecast/tests/test_mu_report.py -q -p no:cacheprovider --basetemp ...` | **60 passed** |
| `python -m pytest forecast/tests/ -q -p no:cacheprovider --basetemp ...` | **482 passed, 3 skipped, 1 deselected, 1 xfailed** |
| E2B CLI 사전 검사 | PASS 후 G-12c BLOCKED, 렌더 없음 |

첫 forecast 전체 실행에서 `test_xlsx_rebuild_is_byte_deterministic`가 1회 실패했다. 같은 테스트의 즉시 단독 재실행과 최종 전체 재실행은 모두 통과했다. 코드 변경으로 재현되는 회귀가 아니라 XLSX 메타데이터 시간 경계에서 발생한 단발성 플레이크로 분리했다. 기존 Windows symlink/process-group 제약 skip 2건, gitignore된 derived EDGAR cache 부재 skip 1건, 기존 FYE-August Q1 라벨 xfail 1건은 유지했다.

최종 상태: **충돌 확인 레코드가 작성·검토되기 전까지 렌더 금지.**
