# REVIEW — Claude: MU 리포트 E2-A 산출물 r1

- 검토자: Claude (E3, 범위 = **E2-A**)
- 검토일: 2026-09-27 KST
- 기준: PLAN rev-3 `6a7350871ebc804e6b359240065662e31fd1411172face01217f24be6097f324` · HANDOFF `e4d6b587f767c4c1159cf67dc72db7d09e1262992ab3d52a8b9357aa7aa72bd7`
- 전체 판정: **CHANGES REQUESTED** — 차단 1건(F-1), E2-B 전 필수 2건(F-2·F-3), 참고 3건
- 🔴 투자 자문 아님. This review is not investment advice.

## 1. 독립 확인한 것

| 항목 | 결과 |
|---|---|
| E2-A 산출 25개 파일 SHA-256 | Codex 보고값과 **전부 일치**(앞 16자리 대조) · 행 수 일치 |
| 범위 | `git --no-optional-locks status`: 신규는 `forecast/scripts/mu_report/` · `forecast/tests/fixtures/mu_report/` · `forecast/tests/test_mu_report.py`(+ 계획·리뷰 문서)뿐. `forecast/reports/mu_report_*` **0개** · `forecast/inputs/`에 RLE YAML **없음** · `.git/index.lock` 없음 |
| 불변 입력 | PLAN · HANDOFF · FROZEN `eab1184f…` · 프로파일 `faa60912…` 불변 |
| 입력 계층 | `inputs.py::EvidenceReader` — allowlist·전체 SHA 확인, 예약 핀 `null`이면 거부, 감사 기록 시각 없음·경로 정렬, 실행 로그는 `logs/_mu_report_runs/`(gitignore). `extract.py`의 외부 입력 읽기는 전부 `reader.read_*` 경유 |
| E2-A 경계 | `build.py`가 `--phase E2-A` 외 거부, `forecast/reports` 하위 출력 거부 |
| SCA·브릿지·debt | `facts.py`: 예치금 fact `UNAVAILABLE`이면 `NetCash_ex_SCA`·`EV_adj`도 `UNAVAILABLE` · `bridge.nongaap_fixed_027`은 FY2026Q4 1건·값 0.27 · debt-prepayment 3개 fact 분리 |
| G-3 허용오차 | 계획 §5 식 그대로(항 수 × 0.5, EPS 식 동일) |

**독립 재실행 한계**: 이 VM은 Python 3.10이고 WeasyPrint가 없다. `inputs.py`가 `datetime.UTC`(3.11+)를 쓰고 `render.py`가 import 시점에 WeasyPrint를 불러오므로 **테스트를 VM에서 재실행할 수 없다.** 테스트 수·결정성은 §4 호스트 명령으로 Jiwon이 재확인한다(Codex 보고 수치는 증거로 취급하지 않음).

## 2. 발견 사항

### F-1 [차단] XLSX가 Codex 전용 런타임에 의존 — 재현 불가

- `render.py:121-124`가 `NODE_PATH = ~/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules`로 `node xlsx_builder.mjs`를 호출하고, `xlsx_builder.mjs`는 `require("@oai/artifact-tool")`을 쓴다. 이 패키지는 리포 어디에도 선언돼 있지 않다(`package.json` 없음).
- 결과: Codex 런타임 밖(Jiwon 단독 실행, Claude E3 재현, 다른 PC)에서는 **XLSX를 만들 수 없고**, Codex 런타임이 업데이트되면 출력이 바뀔 수 있다. 계획 D5 *"호스트에서 결정적 재생성"* 과 §5 *"E3에서 독립 재실행"* 에 어긋난다.
- **요구**: XLSX를 **openpyxl(Python)** 로 다시 구현하고 `xlsx_builder.mjs`와 Node 호출을 제거하라(선례 `valuation-results/2026-08-26-nvda-q2-preview/scripts/build_xlsx.py`). 미리보기 PNG가 QA에 필요하면 게이트는 openpyxl 읽기 검사로 충분하다. 빌더 안의 고정 문자열(`2099-01-01 FIXTURE` 등)도 manifest·i18n에서 받도록 하라.

### F-2 [E2-B 전 필수] G-17·G-17b가 렌더 결과에 적용되지 않고, 영어 토큰만 검사

- `gate_g17_labels`·`gate_g17b_consensus`는 단위 테스트에서 영어 문자열로만 호출된다. 렌더 경로(`render.py`)는 두 게이트를 부르지 않는다.
- G-17 토큰은 `"14 weeks"`·`"53 weeks"` 영어 고정 → 한국어판(`14주`, `53주`)은 검사되지 않는다. G-17b는 소문자 `"fy27 consensus"`가 있을 때만 작동 → 한국어 문장(`FY27 컨센서스`)은 우회된다.
- **요구**: (i) 로캘별 필수 라벨 집합(ko·en) (ii) G-17b를 **fact 기반**으로 — `UNAVAILABLE_FOR_COMPARISON` 상태 fact를 참조하는 문장·표 셀·차트에 비교 fact(gap·차이)나 방향 표현이 함께 오면 실패 (iii) 두 게이트를 **ko·en 렌더 결과 각각에** 빌드 경로에서 실행. 위반 주입 테스트에 **한국어 사례**를 추가.

### F-3 [E2-B 전 필수] G-15 패리티가 위치 키·차트·보조 검사를 빠뜨림

- `gate_g15_parity`는 요약 표 placeholder의 **fact_id 순서 목록만** 비교한다. 계획 §5 G-15는 (a) 위치 키(표 id·행·열 / placeholder 순번 / series·점) **와** fact_id 쌍 비교 (b) 표 셀·본문·**차트 series** 전부 (c) 보조로 정규화 숫자 토큰 다중집합 비교 + 의도된 차이 allowlist를 요구한다.
- **요구**: 참조 로그를 `(kind, location, fact_id)`로 바꾸고 세 종류 모두 수집·비교. 보조 숫자 토큰 검사와 allowlist 추가. 위반 주입: 위치만 바꾼 경우·차트 series 1점만 다른 경우.

### 참고 (조치 불요, 기록만)

- N-1 `datetime.UTC`는 3.11+ — 호스트 3.14에서는 문제 없음. VM 재현 불가의 원인일 뿐.
- N-2 Poppler가 한글 사용자 경로(`C:\Users\김지원\…`)에서 리소스 경고를 냈다고 보고됨. G-21 PDF 검사는 경고가 없는 경로(PyMuPDF 또는 pypdf)로 판정하도록 고정하라.
- N-3 G-7은 `open()` 이름 호출만 잡는다. 내부 파일(`facts.py`의 sources JSON, i18n) 읽기는 계획상 허용 범주이므로 현 상태 유지 가능. 외부 증거 파일을 `Path.read_*`로 직접 읽는 새 코드가 생기지 않도록 **외부 경로 상수가 `reader` 밖에서 쓰이면 실패**하는 검사를 권장.

## 3. 판정

| 구분 | 판정 |
|---|---|
| 역사 추출·manifest·입력 계층·E2-A 경계·SCA/브릿지/debt 계약 | **PASS** (정적 검토 + SHA 대조) |
| XLSX 재현성 | **FAIL** (F-1) |
| 게이트 완결성 | **CHANGES REQUESTED** (F-2·F-3) |
| 테스트 수·결정성 | 호스트 재확인 대기(§4) |

F-1~F-3 수정 후 Codex는 수정 파일 SHA와 회귀표(추가된 한국어·위치·차트 위반 사례 포함)를 다시 보고한다. E2-B는 이 리뷰 PASS + 계획 §6 입력 게이트 4개 충족 전까지 시작하지 않는다.

## 4. 호스트 재확인 명령 (Jiwon, 리포 루트 PowerShell)

```powershell
chcp 65001 > $null; $env:PYTHONIOENCODING='utf-8'
python -m pytest forecast/tests/test_mu_report.py -q
python -m pytest forecast/tests/ -q
python forecast/scripts/verify_anchor.py
Get-FileHash forecast\scripts\mu_report\sources\*.json -Algorithm SHA256 | Format-Table Hash, Path
python forecast/scripts/mu_report/build.py --phase E2-A
Get-FileHash forecast\scripts\mu_report\sources\*.json -Algorithm SHA256 | Format-Table Hash, Path
```

두 번의 `Get-FileHash` 출력이 같고 Codex 보고 SHA와 같아야 결정성 확인이다.

---

*본 문서는 투자 자문이 아니다. This document is not investment advice.*
