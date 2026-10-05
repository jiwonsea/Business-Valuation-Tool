# REVIEW — MU report rev-4.3 input pins r1

> 작성: Codex · 2026-10-01 KST  
> 범위: `forecast/HANDOFF_CODEX_mu_report_exec.md` 부록 R10  
> 이 문서는 투자 자문이 아니다. This document is not investment advice.

## 1. rev-4.3 diff 판정

**판정: PASS.**

- 현행 계획 `forecast/PLAN_mu_report_fy2026q4.md` SHA-256: `99de31cb5ccbb99aa9a4748ea955ea8cd946a64f6e1a379d9757a6add20d4492`.
- 보존 사본 `forecast/PLAN_mu_report_fy2026q4_rev4.2_superseded.md` SHA-256: `32fc96edbaffa1c0952f9dc1d5a9f4b5eb2743ce41e482ea1b50b681689d5734`.
- `git diff --no-index`로 두 파일을 비교했다. 변경은 다음 범위뿐이다.
  1. 제목의 `rev-4.2`를 `rev-4.3`으로 변경.
  2. 리비전 표에서 rev-4.2 강조를 해제하고 rev-4.3 행을 추가.
  3. §4-7 예약 경로 표의 E2-B 및 E2-C 경로를 `logs/mu/fy2026q4/postprint/` 아래로 변경.
  4. §6 Jiwon 요청 목록의 프린트 직후 저장 경로를 같은 회사·분기 폴더로 변경.
- 따라서 R10-3의 “경로 3곳 + 리비전 행 + 제목” 조건과 일치한다. E2-A 입력 20개의 경로·SHA 변경은 없다.

## 2. SHA-256 재계산 결과

PowerShell `Get-FileHash -Algorithm SHA256`으로 원본 바이트를 직접 재계산했다.

| 경로 | 재계산 SHA-256 | 부록 R10 값과 일치 |
|---|---|---|
| `logs/mu/fy2026q4/postprint/8k_index.html` | `bda394e8b8f41e492a0051b11b92a9469c2bdac5d280e273763b8946519861e4` | 예 |
| `logs/mu/fy2026q4/postprint/ex991.htm` | `5dad1ce5c2dd8958dad947ab1f12a1015bfcc29c7e8a29e48379e983f425120e` | 예 |
| `logs/mu/fy2026q4/postprint/remarks.pdf` | `2821d4ccaae50b40dcd28cd4e766c69c509e73d666e4109d5907c7205a03b700` | 예 |

`input_pins.yaml`에는 위 3개 SHA를 기록했다. 아직 확보되지 않은 가격 캡처 2개는 실제 확장자를 확정하지 않고 `<ext>` 예약 경로와 `sha256: null`을 유지했다. `forecast/reports/mu_fy2026q4_SCORED.md`와 E2-C 10-K도 `sha256: null`을 유지했다.

FQ4 실적 수치는 해석하거나 채점하지 않았다.

## 3. 변경 파일과 SHA-256

| 파일 | 변경 | SHA-256 |
|---|---|---|
| `forecast/scripts/mu_report/input_pins.yaml` | E2-B/E2-C 예약 경로 이동, 확보 원본 3개 SHA 기록 | `4c659675d765c1ccfeaee0dfd0d5227afb090405d4ef4b42cc77b175df92cdf3` |
| `forecast/tests/test_mu_report.py` | G-20 예약 경로 위반 주입 값을 새 EX-99.1 경로로 변경 | `0e1329b4f12e905030a36fa72877e5806fdbec59d0246b3ae978b1fff4261c8d` |
| `forecast/REVIEW_CODEX_mu_report_pins_r1.md` | 본 검토 보고서 | 자기 참조를 피하기 위해 파일 내부에는 SHA를 고정하지 않으며, 작성 완료 후 외부 회신에 기록한다. |

실행 코드와 `forecast/tests/test_mu_report.py`에서 구식 `logs/mu_postprint` 문자열을 검색한 결과는 0건이다. 계획·보존 사본·handoff의 역사 기록은 변경하지 않았다.

## 4. 테스트 및 위생 검사

### 4.1 MU 단독

명령:

```text
python -m pytest forecast/tests/test_mu_report.py -q --basetemp <허용된 작업용 임시 경로>/pytest-mu
```

결과: **56 passed**, 경고 1건, 7.99초. 경고는 저장소 `.pytest_cache` 생성 시 기존 경로와 충돌한 `PytestCacheWarning`이며 테스트 실패는 아니다.

최초 기본 임시 폴더 실행은 Windows 사용자 임시 폴더 접근 거부로 `tmp_path` fixture 12건이 setup 오류가 났고 44건은 통과했다. 코드 실패와 구분하기 위해 쓰기 허용된 별도 `--basetemp`로 재실행했고 전부 통과했다.

### 4.2 forecast 전체

명령:

```text
python -m pytest forecast/tests/ -q --basetemp <허용된 작업용 임시 경로>/pytest-forecast
```

결과: **478 passed, 3 skipped, 1 deselected, 1 xfailed**, 경고 1건, 65.30초.

- skipped 2건: Windows symlink 권한 및 process-group 비지원.
- skipped 1건: gitignored 파생 EDGAR cache 부재.
- xfailed 1건: 기존에 명시된 FYE-August Q1 label 계약 이슈(`NOTICED BUT NOT TOUCHING`).
- 경고 1건: 위와 같은 `.pytest_cache` 생성 경고.

### 4.3 파일 위생

- `forecast/scripts/mu_report/input_pins.yaml`: NUL 0, CRLF 0.
- `forecast/tests/test_mu_report.py`: NUL 0, CRLF 0.
- `forecast/REVIEW_CODEX_mu_report_pins_r1.md`: NUL 0, CRLF 0.
- git add/commit/push는 수행하지 않았다.

## 5. 결론

rev-4.3 경로 이동과 확보된 E2-B 원본 3개의 핀 기록은 완료됐고 관련 회귀 테스트는 통과했다. 가격 캡처 2개, SCORED 문서, FY26 10-K가 아직 미확보이므로 해당 핀은 의도대로 미확정 상태다. 이 작업에서는 실적 채점을 수행하지 않았다.
