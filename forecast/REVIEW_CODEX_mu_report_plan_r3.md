# REVIEW — MU FY2026 Q4 리서치 리포트 PLAN rev-3

- 검토자: Codex
- 검토일: 2026-09-27 KST
- 대상: `forecast/PLAN_mu_report_fy2026q4.md` rev-3
- 대상 SHA-256: `6a7350871ebc804e6b359240065662e31fd1411172face01217f24be6097f324`
- 전체 판정: **PASS**
- 범위: 계획 재검토만 수행. 코드·리포트·가정 YAML은 만들지 않았다.

## 1. 결론

rev-3는 r2의 C-1~C-4와 미결 판정 Q-1·Q-5·Q-10·Q-13·Q-14·R-4를 모두 닫았다. 새로운 차단 이슈는 없다.

계획은 P3에서 Jiwon의 D1–D9 승인을 받을 수 있다. 승인 전에는 E1 또는 E2를 시작하지 않으며, 승인 후 Claude가 확정 계획을 `forecast/HANDOFF_CODEX_mu_report_exec.md`로 옮긴 다음 Codex가 실행한다.

## 2. 미결 항목 판정

| # | 판정 | 근거 |
|---|---|---|
| Q-1 | **PASS** | E2-A 외부 증거 20개가 정확한 상대경로와 전체 SHA-256으로 고정됐다. E2-B/E2-C는 예약 경로와 사후 SHA 확인 절차가 분리됐다. 외부 증거·내부 템플릿·생성물 재검증 읽기의 통제도 구분됐고, 커밋 감사 기록에서 시각을 제거해 결정성을 확보했다. |
| Q-5 | **PASS** | `NetCash_unadjusted`와 조건부 `NetCash_ex_SCA`의 계산 경로가 분리됐다. RLE 행 이름에 자사주·인수·차입 변동과 SCA 미조정 상태가 모두 드러난다. |
| Q-10 | **PASS** | `EV_adj`와 `NetCash_ex_SCA`가 동일한 공시 fact `bs.sca_customer_deposits`를 사용하며, 미공시이면 둘 다 `UNAVAILABLE`이다. 기본 EV와 조정 EV의 의미가 일관된다. |
| Q-13 | **PASS** | ed2가 `E2-C → E3-ed2 → E4-ed2`의 독립 검토·승인 경로를 가진다. ed1 승인이 ed2 commit/push 권한을 갈음하지 않는다. |
| Q-14 | **PASS** | 실제 현금에 포함된 예치금 효과를 `NetCash_ex_SCA = NetCash_unadjusted − outstanding SCA deposits`로 명시적으로 제거한다. 미공시 금액을 추정하지 않는다. |
| Q-15 조건 | **PASS** | `×52/53`은 매출·EPS·EBITDA·FCF 같은 flow에만 적용된다. 시가총액·EV·순현금에는 적용하지 않으며 본문 기본값으로 쓰지 않는다. |
| R-4 | **PASS** | 3표 행·식·가용성 계약의 순현금 정의와 라벨 모순이 해소됐다. |

## 3. C-1~C-4 확인

### C-1 — PASS

- 주 행: `NetCash_unadjusted`, SCA 예치금 미조정이라고 명시
- 보조 행: 공시된 미상환 예치금이 있을 때만 `NetCash_ex_SCA`
- RLE: 예치금 경로를 모델하지 않으므로 `NetCash_ex_SCA = UNAVAILABLE`
- 동일 예치금 fact가 `EV_adj`에도 사용됨

### C-2 — PASS

다음 세 수치가 별도 fact와 source/basis로 분리됐다.

| 수치 | basis |
|---|---|
| `−$321M` | GAAP 손익계산서의 other non-operating net |
| `$323M` | 10-Q 부채 주석의 debt-prepayment 인식 손실 |
| `$325M` | 보도자료 비GAAP reconciliation 조정 항목 |

`$2M` 차이를 임의로 조정하지 않으며 FROZEN도 수정하지 않는다.

### C-3 — PASS

- 20개 E2-A 증거 입력의 경로·전체 SHA 전수 일치
- E2-B/E2-C 예약 파일명과 Codex SHA 확인 선행 조건 명시
- 결정적 `input_manifest.json`과 비커밋 timestamped run log 분리
- 감사 기록 경로와 E4 commit candidate 여부 명시

### C-4 — PASS

ed2는 별도 Claude 재현 리뷰, Jiwon 승인, host PowerShell commit, 판별 push 승인을 거친다.

## 4. 검증 기록

- rev-3 SHA-256: `6a7350871ebc804e6b359240065662e31fd1411172face01217f24be6097f324`
- rev-2 보존본 SHA-256: `7f204ea2ec743a7997f6cd2c927facd2fd9be6aea283b05047ddf63fa2df1255`
- FROZEN SHA-256: `eab1184f721cd69460ffc4ddefd9851c59815207c35975db0dd1a2962b629f9a`
- MU profile SHA-256: `faa60912b6a364eee67f87d9ba21221a6c6da02f22695c4d980200260982dfd6`
- E2-A evidence SHA: **20/20 일치**
- 문서 위생: LF, NUL 0, trailing whitespace 0
- Markdown 표 열 불일치: 0
- `python -m pytest forecast/tests/test_frozen_integrity.py forecast/tests/test_valuation_allowlist.py -q`: **53 passed**
- `python forecast/scripts/verify_anchor.py`: **PASS**, canonical 9Q SHA MATCH
- FROZEN과 MU profile은 작업트리에서 변경되지 않았다.

## 5. 승인 이후 순서

1. Jiwon이 PLAN rev-3의 D1–D9를 승인한다.
2. Claude가 확정 계획 기반 E1 핸드오프를 작성한다.
3. Codex가 E2-A를 시작한다.
4. post-print 입력 네 가지가 모두 준비되기 전에는 E2-B로 넘어가지 않는다.
5. commit과 push는 각 판의 별도 승인 전에는 수행하지 않는다.

---

이 문서는 투자 자문이 아니다. This document is not investment advice.
