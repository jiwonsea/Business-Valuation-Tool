# REVIEW — Claude: MU 리포트 E2-A 산출물 r2

- 검토자: Claude (E3, 범위 = **E2-A 수정분**)
- 검토일: 2026-09-27 KST
- 기준: PLAN rev-3 `6a7350871ebc804e6b359240065662e31fd1411172face01217f24be6097f324` · HANDOFF `e4d6b587f767c4c1159cf67dc72db7d09e1262992ab3d52a8b9357aa7aa72bd7` · 직전 리뷰 r1 `0249ba02bd6c3665a7914dd802ce805e8bca88b8ab4034867765423fcbfd469a`
- 전체 판정: **PASS (E2-A)** — E2-B로 넘길 조건 2건(C-1·C-2). 테스트 수는 호스트 재확인 대기(§4)
- 🔴 투자 자문 아님. This review is not investment advice.

## 1. 독립 확인

| 항목 | 결과 |
|---|---|
| 24개 파일 SHA-256 | Codex 보고값과 **전부 일치**. 변경 파일: `facts.py` `585429c2…` · `gates.py` `38c484f8…` · `render.py` `ee447c43…` · `i18n/en.yaml` `1f957420…` · `i18n/ko.yaml` `43c0e36b…` · `test_mu_report.py` `f0226d6c…`. `xlsx_builder.mjs` 삭제 확인 |
| 범위 | 신규는 허용 경로 3곳뿐 · `forecast/reports/mu_report_*` 0개 · `forecast/inputs/` RLE YAML 없음 · `.git/index.lock` 없음 |
| 역사 추출본 | `sources/*.json` 9개 SHA가 r1 시점과 동일 — 수정 과정에서 역사 데이터가 바뀌지 않았다 |

## 2. r1 지적 해소

| # | r1 요구 | 확인 결과 | 판정 |
|---|---|---|---|
| F-1 | XLSX를 Python으로, Codex 런타임 의존 제거 | `render.py`에서 `node`·`.mjs`·`artifact-tool`·`codex-runtimes`·`subprocess` 흔적 0. `openpyxl.Workbook`으로 작성, 문서 속성 created/modified 2000-01-01 고정, ZIP 멤버를 이름순·고정 시각(2000-01-01)·DEFLATED로 재기록. `test_xlsx_builder_uses_python_only` · `test_xlsx_rebuild_is_byte_deterministic` 존재 | **PASS** |
| F-2 | G-17·G-17b 로캘별 + 렌더 결과 적용 + fact 기반 | `gate_g17_labels(text, locale)` — ko는 `14주`·`53주`, en은 `14 weeks`·`53 weeks`. `gate_g17b_consensus(reference_log, manifest)` — `UNAVAILABLE_FOR_COMPARISON` fact는 역할 `display`로만 참조 가능, 이 fact를 입력으로 쓰는 계산 fact 금지(문장 매칭 아님). **`render_fixture_bundle`이 ko·en 각각의 렌더 결과에 두 게이트를 실행** | **PASS** |
| F-3 | G-15 위치 키·차트·보조 검사 | 참조가 `position`(표 셀·placeholder·`chart:<id>:series:0:point:<n>`) · `kind` · `role` · `fact_id` · 값·단위·기간·basis·라벨·상태를 가진다. 위치 집합 일치 + 위치별 전 필드 일치 + manifest 대조 + 정규화 숫자 다중집합 일치. 렌더 경로에서 실행 | **PASS** |

## 3. E2-B로 넘길 조건 (지금 수정 불요 — 실제 산출물이 생길 때 필요)

- **C-1 빌드 경로의 게이트 완결성.** 현재 렌더 경로에서 실행되는 것은 G-15·G-17·G-17b다. G-12b(면책)·G-13/13b(차트)·G-14(출처)·G-16(캡션)·G-18(위생)·G-21(형식 QA)은 **테스트가 fixture 번들에 대해** 실행한다. E2-B의 `build.py --phase E2-B`는 이 게이트 전부를 **ko·en 각 판과 공유 XLSX에 대해 실행한 뒤에만** `forecast/reports/`에 쓰도록 하라(실패 시 아무것도 쓰지 않음).
- **C-2 의도된 KO/EN 차이 allowlist.** `_number_multiset`에는 계획 §4-6의 allowlist(날짜 표기·절 번호 등)가 아직 없다. 지금은 차이가 있으면 **실패하는 쪽(fail-closed)** 이라 안전하다. 실제 본문에 로캘별 날짜 형식(`2026년 10월 1일` vs `2026-10-01`)이 들어가면 필요해진다 — 그때 allowlist를 **명시 규칙으로** 추가하고, 규칙이 fact 값 자체를 가리지 못하게 위반 주입 테스트를 붙여라.

## 4. 호스트 재확인 (Jiwon)

이 VM은 Python 3.10·WeasyPrint 미설치라 테스트를 돌릴 수 없다. r1 §4 명령을 **수정본 기준으로** 다시 실행해 결과를 남겨 달라(Codex 보고 수치는 증거로 취급하지 않는다).

```powershell
chcp 65001 > $null; $env:PYTHONIOENCODING='utf-8'
python -m pytest forecast/tests/test_mu_report.py -q
python -m pytest forecast/tests/ -q
python forecast/scripts/verify_anchor.py
Get-FileHash forecast\scripts\mu_report\sources\*.json -Algorithm SHA256 | Format-Table Hash, Path
python forecast/scripts/mu_report/build.py --phase E2-A
Get-FileHash forecast\scripts\mu_report\sources\*.json -Algorithm SHA256 | Format-Table Hash, Path
```

기대: MU 테스트 29 passed · 전체 451 passed / 3 skipped / 1 deselected / 1 xfailed · anchor PASS · 두 해시 목록 동일하고 §1과 일치.

## 5. 다음 단계

E2-A는 여기서 끝난다. E2-B는 계획 §6 입력 게이트 4개(프린트 8-K/EX-99.1·준비문 + SHA, `mu_fy2026q4_SCORED.md` + 커밋·SHA, 2026-10-01 종가 2경로, P3·E1 — 충족)와 **Claude의 RLE 가정값 표**(프린트 후 FQ1 FY27 가이던스가 앵커) 이후에 시작한다.

---

*본 문서는 투자 자문이 아니다. This document is not investment advice.*
