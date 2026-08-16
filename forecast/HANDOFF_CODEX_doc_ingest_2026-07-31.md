# HANDOFF_CODEX — 문서 인제스트 완전성 (doc-ingest completeness)

**작성:** Claude (Cowork 세션, 2026-07-31) · **상태:** REVIEW-ONLY, 코드 변경 0건
**베이스:** `f49942a` (2026-07-28) + 워킹트리 미커밋 변경 9건(§9)
**루프:** COMMON §5 6축(정확성·건전성·회귀안전·범위규율·검증가능성·유지보수성) 교차검증.
**아래 주장(파일:라인·수치·git 이력)을 그대로 믿지 말고 독립 재현할 것.** 재현 명령은 §8.

---

## 0. 이 핸드오프가 묻는 것 (한 줄)

Claude가 제안한 **(a) 오진 정정 · (b) 인제스트 하한 게이트 · (c) 원문 읽기 규칙**의 3종 세트를
"한 커밋으로 묶는" 원안이 맞는지, 아니면 **(b)가 죽은 코드를 대상으로 한 범위규율 위반**이라
Claude 스스로 뒤집은 rev-1이 맞는지 — **6축 판정**.

---

## 1. 발단

다른 세션에서 "pdfplumber가 38,846자 문서에서 13,535자(34.8%)만 추출하고 있었다 →
그동안 Codex 핸드오프 일부가 반쯤 빈 텍스트로 평가받았을 가능성"이라는 지적이 나왔다.
사용자 지시: **EFE 폴더도 같은 문제인지 확인.**

---

## 2. 확인된 사실 (F1–F7)

| # | 사실 | 근거 |
|---|---|---|
| F1 | 레포에 **pdfplumber 의존성이 없다.** PDF 인제스트는 단 한 곳, `pipeline/disclosure_loader.py:55` `raw_text = "\n".join(page.get_text() for page in pdf)` (pymupdf/`fitz`) | `requirements.txt` = `pymupdf>=1.24`; `grep -rniE "pdfplumber\|pypdf\|pdfminer"` → .py 히트 0 |
| F2 | 그런데 `HANDOFF_generic_engine.md:32`는 **"1 fail = PDF dep(pdfplumber) 환경이슈, 코드무관"** 이라고 적고 있다 — 존재하지 않는 의존성에 실패를 귀속시킨 **오진** | 해당 라인 원문 |
| F3 | 그 실패의 진짜 정체는 `tests/test_disclosure_loader.py::test_fetch_dart_mdna_nonempty` — **라이브 DART를 때리는 네트워크 의존 테스트**(rcpNo `20240814003052` 하드코딩, 목/픽스처 없음) | 테스트 파일 전문 |
| F4 | 레포 PDF 2개 실측: pdfplumber/fitz 문자수 비 **85.6%**(sk_hynix_20260530, 6p) · **90.5%**(20260710, 11p). **한글 문자수는 양쪽 동일**(207 / 852) → 차이는 공백·개행 처리. **34.8% 급 누락 재현 안 됨** | §8 재현 스크립트 |
| F5 | `load_ir_decks`에 **추출량 하한 게이트가 전혀 없다.** `char_count_kr`를 계산해 필드에 넣기만 하고 프로덕션 코드 어디도 검사하지 않음(전체 grep 상 검사는 테스트의 `> 0` 1건뿐). 이미지 레이어 deck → 빈 문자열이 예외 없이 LLM 추출기로 유입 | `disclosure_loader.py:38-66`, `grep -rn "char_count_kr"` |
| F6 | `fetch_dart_mdna`의 유일한 가드는 `char_count_kr == 0`(:147). 캐시에 **통과 실증**이 남아 있음: `reports/.cache/mdna_20240814003052.json` = **67자** `"IV. 이사의 경영진단 및 분석의견 / 기업공시서식 작성기준에 의거하여 분·반기보고서에는 본 항목을 기재하지 아니하였습니다."` → `char_count_kr=50`으로 게이트 통과·정상 문서로 캐시됨 | 캐시 파일 전문 |
| F7 | 추가로 `_find_mdna_params`(:98-113)는 조건을 만족하는 **첫 노드 하나**의 `offset/length`만 사용 → 섹션이 복수 `eleId`로 분할된 보고서에서는 부분 추출이 조용히 성립 | 함수 본문 |

**F6 해석 주의(내 초안의 과장 지점):** 이 67자는 추출 실패가 아니라 **소스가 실제로 비어 있는 것**이다
(한국 분·반기보고서는 MD&A 미기재가 정상). 결함은 "잘못 뽑았다"가 아니라
**"소스 공백과 추출 실패를 구분하지 못하는 게이트"** 라는 점에 한정된다. 또한 이 rcpNo는
프로파일 주석에 `# 예시(2024 반기보고서) — 본인이 최신 rcpNo로 교체`라고 적혀 있던 **예시값**이다.

---

## 3. 핵심 반전 — 그 경로는 이미 죽어 있다

| # | 사실 | 근거 |
|---|---|---|
| F8 | `load_ir_decks` / `fetch_dart_mdna`의 **유일한 호출자는 `cli.py`의 Phase-B 모드 2개**(`run_signal_backtest_mode:429`, `run_call_brief_mode:487`)이고, 둘 다 진입 즉시 `profile["raw"].get("signal_layer")` 없으면 `return 2` | `cli.py:409-412, 470-473` |
| F9 | **현재 `profiles/` 12개 파일 중 `signal_layer` 섹션을 가진 것은 0개.** `grep -rln "signal_layer" profiles/` → 히트 없음 | grep |
| F10 | `signal_layer`는 **2026-07-10 커밋 `4ebeb7c`**("roll forward window to 2026Q2")에서 `profiles/sk_hynix.yaml`에서 제거됨(`decks_dir`·`topic_taxonomy`·`decks`·`call_brief.mdna.rcp_no` 블록 통째) | `git log -S signal_layer -- profiles/` = `4ebeb7c`, `a7a5c6d`(초기) 2건 |
| F11 | `generic_cli.py`는 텍스트 인제스트를 아예 쓰지 않음 — `engine.generic_signal.build_signal_block`(수치 skill 블록)만 사용 | `grep -n "disclosure\|signal" generic_cli.py` |
| F12 | 세션 캐시 증거도 일치: `reports/.cache/signal_*.json` **0건**, `mdna_*.json` **1건**(위 예시 rcpNo) → LLM 텍스트 추출이 실제 리포트 생산에 쓰인 흔적 없음 | ls |

**따라서 F5/F6/F7은 "현재 예측·채점 파이프라인을 오염시키고 있는 결함"이 아니라
"Phase-B를 되살릴 때 폭발할 지뢰"다.** 내 첫 보고는 이 구분을 하지 않았다 — 정정한다.

---

## 4. 그러면 실제로 살아 있는 노출은 어디인가

**핸드오프에 들어가는 원문 수치는 레포 코드가 뽑은 게 아니라 세션이 그때그때 읽은 것이다.**

- 예: `HANDOFF_CODEX_efe_q2_2026_gev.md:391` §16 — "Codex 수치를 믿지 않고 10-Q 원문 대조,
  source: `gev_webcast_10q_07222026.pdf`" → OP 653/5.88%·유효세율 29.8%·희석주식수 270M을 확정하고
  이 수치로 §16 최종 설계(A/세율/주식수/C 앵커)를 확정했다.
- 그런데 **그 PDF는 폴더 어디에도 없다**(`find . -iname "*10q*.pdf"` → 0건). 즉 §16의 근거는
  **지금 재검증 불가능**하다. 추출기가 무엇이었는지, 몇 자를 읽었는지, 손익계산서 표가 온전히
  들어왔는지에 대한 기록이 없다.
- `START-efe-q2-2026-00-COMMON.md` / `PROMPT_autofreeze_COMMON.md` / `CLAUDE.md` / `AGENTS.md`
  어디에도 **원문 읽기의 완전성 확인 규칙이 없다**(`grep -nE "원문|전문|추출|truncat"` 기준).

**즉 다른 세션이 발견한 그 실패 모드(예외 없이 성공하는 부분 추출)에 대해, EFE는
코드 경로에서는 pdfplumber를 쓰지 않아 무관하지만, 세션 경로에서는 무방비다.**

---

## 5. Claude 원안 (사용자에게 제시했던 것)

> (a) `HANDOFF_generic_engine.md:32` 오진 정정
> (b) `load_ir_decks`/`fetch_dart_mdna`에 하한 게이트 + 완전성 로그 추가
> (c) `START-COMMON`에 원문 보존·자수 기록 규칙 추가
> — **이 셋을 한 커밋으로 묶는다.**

## 6. Claude 자기반박 (§3 확인 후)

1. **(b)는 범위규율 위반 소지.** 호출자가 0인 코드에 게이트를 넣는 것은 검증 불가능한 변경이다
   (테스트로 게이트가 실제로 막는지 보이려면 픽스처를 새로 만들어야 하고, 그 픽스처는
   프로덕션에서 재현되지 않는 경로를 검증한다). 6축 "검증가능성"에서 약하다.
2. **(b)를 하려면 선행 질문이 먼저다:** Phase-B 텍스트 신호 레이어를 **되살릴 것인가, 폐기할 것인가.**
   되살릴 계획이 없다면 게이트가 아니라 **폐기 표식**(모듈 docstring에 DORMANT 명시 +
   네트워크 테스트 skip 마커)이 옳다. 게이트를 다는 건 죽은 코드에 유지보수 부채를 더하는 것.
3. **3종을 한 커밋으로 묶는 것도 틀렸다.** (a)는 문서 1줄, (c)는 프로세스 규칙, (b)는 코드+테스트다.
   회귀안전 성격이 전혀 다르므로 분리 커밋이 맞다.
4. **반대로 (c)의 우선순위는 내가 과소평가했다.** §4가 유일하게 살아 있는 노출이고,
   이미 GEV §16에서 재검증 불가 상태를 실제로 만들어냈다.

## 7. Claude 수정안 rev-1 (Codex 판정 대상)

| 항목 | 판정 | 내용 | 근거 축 |
|---|---|---|---|
| **P0 — (c)** | 채택 | `START-efe-q2-2026-00-COMMON.md`에 "원문 인용 3종 기록" 규칙 신설: 원문을 읽고 핸드오프/동결에 수치를 넣을 때 ① 파일명·URL·취득일, ② **총 문자수·페이지수**, ③ **기대 섹션 앵커 존재 확인**(예: 10-Q면 `CONDENSED CONSOLIDATED STATEMENTS OF INCOME` 문자열 히트 여부)을 인용 블록에 함께 적는다. 셋 중 하나라도 없으면 그 수치는 **동결 근거로 쓰지 않는다.** | 검증가능성 |
| **P0 — (c')** | 채택 | 인용 원본 파일을 `reports/.cache/src/<티커>_<문서>_<YYYYMMDD>.pdf`로 **보존**. `.gitignore`가 이미 `reports/.cache/`를 제외하므로 **레포 비대·배포 리스크 없음**(로컬/호스트 재검증 전용). | 검증가능성·범위규율 |
| **P1 — (a)** | 채택(축소) | `HANDOFF_generic_engine.md:32`를 "1 fail = `test_fetch_dart_mdna_nonempty`(라이브 DART 네트워크 의존), pdfplumber 무관 — 레포에 해당 의존성 없음"으로 정정. **문서 1줄, 별도 커밋.** | 정확성 |
| **P2 — (b)** | **보류로 변경** | 대신 **선행 결정**을 요청: Phase-B 텍스트 신호 레이어 = **부활 / 폐기 / 동면 명시** 중 택1. 부활이면 게이트+픽스처를 정식 스펙으로, 폐기면 `disclosure_loader`·`ai/extractor`·관련 cli 모드 제거 PR, 동면이면 docstring DORMANT 표기 + `test_fetch_dart_mdna_nonempty`에 `@pytest.mark.network` skip만. | 범위규율·유지보수성 |

**가드레일(불변):** forward 회귀 0 · 9Q sha `b979…f6e7` · FROZEN 파일 미수정 · 5종 회귀표.
rev-1은 P0/P1 모두 **엔진 코드 0줄 변경**이라 위 가드레일에 구조적으로 접촉하지 않는다.

---

## 8. Codex에 묻는 것 (Q1–Q5)

- **Q1 (범위규율).** §6-1/2가 맞는가? 호출자 0인 `load_ir_decks`/`fetch_dart_mdna`에 하한 게이트를
  넣는 것이 지금 정당화되는가, 아니면 P2 선행 결정이 먼저인가.
- **Q2 (유지보수성).** Phase-B 텍스트 레이어 3안(부활/폐기/동면) 중 무엇을 권고하는가.
  판단 근거: `signal_layer`가 `4ebeb7c`(7/10)에서 제거된 것이 **의도적 은퇴**였는지
  **롤포워드 중 부수 유실**이었는지 — 커밋 diff에서 판정해 달라. (나는 판단 못 했다.)
- **Q3 (검증가능성).** P0 (c)의 "3종 기록"이 실효적인가. 특히 ③ 섹션 앵커 확인이
  **부분 추출을 실제로 잡아내는가** — 표(table)만 누락되고 헤더는 살아남는 케이스에서
  헛것을 잡는 게이트가 아닌지 반박해 달라. 더 나은 프록시가 있으면 대체안 제시.
- **Q4 (정확성).** F4의 85.6%/90.5%는 **레포가 스스로 생성한 리포트 PDF** 기준이다.
  진짜 입력(10-Q·IR deck)에서의 비율은 측정되지 않았다. 이 표본으로
  "EFE는 무관"이라고 결론 낸 것이 과일반화인가? 그렇다면 어떤 표본으로 재측정해야 하는가.
- **Q5 (회귀안전).** GEV §16이 재검증 불가 상태라는 §4 지적에 대해 —
  **이미 확정된 §16 설계(op_margin 연결 GAAP OP 앵커·세율 23–30%·주식수 268–270M·steady below-OP 1.6%)를
  재검증 없이 유지해도 되는가**, 아니면 2026Q3 구현 전에 10-Q 원문 재취득으로
  네 수치를 다시 확인해야 하는가. 이게 이 핸드오프에서 유일하게 **모델 결과에 직접 닿는** 질문이다.

---

## 9. 재현 명령

```bash
# F1 — pdfplumber 부재
grep -rniE "pdfplumber|pypdf|pdfminer|fitz" --include="*.py" . ; cat requirements.txt

# F3 — 네트워크 의존 테스트
sed -n '1,40p' tests/test_disclosure_loader.py

# F4 — 추출기 비교 (pip install pymupdf pdfplumber 필요)
python - <<'PY'
import fitz, pdfplumber, glob, warnings; warnings.filterwarnings("ignore")
kr=lambda s: sum(1 for c in s if 0xAC00 <= ord(c) <= 0xD7A3)   # 한글 리터럴 금지(cp949에서 깨짐)
for p in sorted(glob.glob("reports/*.pdf")):
    with fitz.open(p) as d: n=len(d); a="\n".join(pg.get_text() for pg in d)
    with pdfplumber.open(p) as d: b="\n".join((pg.extract_text() or "") for pg in d.pages)
    print(f"{p} pages={n} fitz={len(a)}({kr(a)}) plumber={len(b)}({kr(b)}) ratio={len(b)/len(a):.1%}")
PY

# F5/F6/F7
sed -n '38,66p;96,160p' pipeline/disclosure_loader.py
cat reports/.cache/mdna_20240814003052.json

# F8–F12 — 죽은 경로
grep -n "signal_layer" cli.py ; grep -rln "signal_layer" profiles/ ; echo "hits=$?"
git log --oneline -S "signal_layer" -- profiles/
git show 4ebeb7c -- profiles/sk_hynix.yaml | grep -E "^[-+].*(signal_layer|decks|mdna|rcp_no)"
ls reports/.cache/signal_*.json 2>/dev/null | wc -l   # 0
```

**워킹트리 주의:** 현재 미커밋 변경 9건(`generic_cli.py`, `schemas/generic.py`,
`profiles/tsla.generic.yaml`, `reports/{nvda,tsla}_generic_forecast.{json,md}`,
`HANDOFF_CODEX_efe_q2_2026_ibm.md`, `HANDOFF_nvda2.md`) + 미추적 신규 문서 다수.
위 재현은 이 상태에서 수행됐다. clean 베이스에서 재현 시 F4를 제외하면 결과 동일해야 한다.

---

## 10. Codex 회신 형식

각 Q에 대해 **[수용 / 반박 / 조건부 수용]** + 6축 중 근거 축 명시 + (반박 시) 대체안.
P2 3안은 반드시 택1로 답할 것 — 미결로 두면 이 지뢰가 다음 Phase-B 부활 때 그대로 터진다.
구현은 Codex 판정 회신 이후, **문서 커밋(P1)과 프로세스 커밋(P0)을 분리**하여 진행한다.

---

# rev-2 — Codex 6축 회신 반영 + 실행 (2026-07-31, Claude)

## 11. Codex 판정 요약과 처리

| Q | Codex 판정 | Claude 처리 |
|---|---|---|
| Q1 게이트 지금 넣나 | **수용** — P2 선행 결정이 먼저. 단순 문자수 하한은 정상적으로 짧은 MD&A와 추출 실패를 구분 못함 | **수용.** 코드 게이트 미구현. 대신 알려진 결함을 `disclosure_loader` STATUS docstring에 명문화(구현 아님, 경고) |
| Q1 부기 — "호출자 0"은 부정확 | **수용, 내 표현 정정** | 정적 호출자는 존재하고 **현재 구성에서 도달 불가**가 정확. 본문 §3 및 docstring 표현을 "unreachable in the current configuration"으로 통일 |
| Q2 3안 | **동면 명시** — 4ebeb7c만으로 의도적 은퇴 판정 불가(커밋 본문에 은퇴 언급 없음, docs 4종은 여전히 설계된 기능으로 기술) | **수용, 실행 완료**(§14) |
| Q3 3종 기록 | **조건부 수용** — 헤더만 살고 표만 누락되는 케이스를 못 잡음. 7항 계약으로 대체 | **수용, 7항 그대로 채택** + 샌드박스 SHA-256 제약·스크립트 인코딩 규칙 2건 추가(§12) |
| Q4 "EFE 무관" 결론 | **반박** — 과일반화. 표본이 레포 자체 생성 PDF | **수용**(결론 문구를 Codex 제안대로 교체). **단 한글자수 0/0 주장은 반박** → §12 |
| Q5 GEV | **반박** — Q3 구현 전 원문 재취득 필수 | **수용, 즉시 실행 → 전 항목 일치**(§13) |

## 12. F4 정정 — Codex Q4의 한 갈래를 되반박

**Codex 주장:** "한글 문자수 207/852는 재현되지 않았고 두 추출기 모두 0/0이었다."
**Claude 재현(코드포인트 기반 재측정):**

| 파일 | SHA-256(앞16) | 페이지 | fitz len/KR | pdfplumber len/KR | 비율 |
|---|---|---|---|---|---|
| sk_hynix_20260530.pdf | `09aca25211383421` | 6 | 5,687 / **207** | 4,870 / **207** | 85.6% |
| sk_hynix_20260710.pdf | `113ac010fdcad7e9` | 11 | 11,582 / **852** | 10,476 / **852** | 90.5% |

추출 한글 샘플(escape): `하이닉스`(하이닉스) · `반기보고서`(반기보고서) ·
`리스크밴드`(리스크밴드). **자모 분리 문자(U+1100–U+11FF)는 0개** → NFD 정규화 이슈 아님.
문자수 비율이 양측에서 **동일하게** 나온 것은 같은 바이트를 읽었다는 뜻이므로, 차이는 **세는 방법**에만 있다.

**근본원인 판정:** 내가 §9에 넣은 재현 스크립트가 한글 리터럴 비교(`'가' <= c <= '힣'`)를 쓴다.
이 소스가 Windows 콘솔/파일 인코딩(cp949)을 경유하며 깨지면 비교가 **아무것도 매치하지 않고 0을 반환**한다 —
예외 없이. **이 계약이 막으려는 실패 유형(조용한 부분/영 추출)을 계약 문서 자신이 저지른 것**이므로
교훈을 P0 계약 말미에 규칙으로 박았다(코드포인트 사용 강제). §9 스크립트도 교체했다.

**Codex Q4의 나머지(표본 대표성)는 전면 수용.** F4의 결론 문구를 다음으로 확정한다:
> 레포의 PyMuPDF 경로에서는 34.8% 누락이 **아직 재현되지 않았다.** 그러나 표본이 레포 자체 생성
> 리포트 PDF 2건뿐이라 **실제 입력(10-Q·IR deck·스캔본·복수열 표·DART 복수 eleId)에 대한 완전성은 검증되지 않았다.**
> fitz 문자수도 ground truth가 아니다 — 기준은 렌더링 페이지와 핵심 표 셀의 사람 대조다.

## 13. Q5 실행 — GEV 10-Q 원문 재취득 결과 (감사 사슬 복구)

**출처:** SEC EDGAR accession **0001996810-26-000148**, GE Vernova Inc.(CIK 0001996810),
form 10-Q, filed **2026-07-22**, period 2026-06-30. 대조 문서 = XBRL 렌더링
`R2.htm`("CONSOLIDATED STATEMENT OF INCOME (LOSS) (UNAUDITED)", FilingSummary.xml로 위치 확인).
취득 2026-07-31 KST, 도구 = WebFetch(markdown 변환본).

**3개월(2026Q2) 연결 손익 — 항등식 검증:**

| 항목 | 값($M) | 검증 |
|---|---|---|
| 총매출 | 11,104 | — |
| 매출원가 | 8,744 | 11,104 − 8,744 = **2,360 = GP** ✓ |
| SG&A / R&D | 1,372 / 334 | 2,360 − 1,372 − 334 = 654 vs **보고 653** → **반올림 −1, 기록** |
| **영업이익** | **653** | 653 / 11,104 = **5.881%** ✓ (§16 "5.88%") |
| 이자·기타금융(순) / 비영업연금 / 기타 | 73 / 119 / 80 | 합 **272** = below-OP, 272/11,104 = **2.450%** ✓ (§16 "+2.45%") |
| 세전이익 | 925 | 653 + 272 = **925** ✓ |
| 법인세 | 276 | 276 / 925 = **29.84%** ✓ (§16 "29.8%") |
| 순이익 / 지배주주 | 649 / 668 | 925 − 276 = **649** ✓ (지배주주 668 = 비지배 −19) |
| 희석 EPS / 희석주식수 | 2.47 / **270** | 668 / 270 = **2.474 ≈ 2.47** ✓ |

**판정: §16의 네 수치(OP $653M·5.88% / 세율 29.8% / 희석주식수 270M / below-OP +2.45%)는 전부 원문과 일치.
불일치 0건 → Q3 앵커 수정 불필요, 현재 설계 유지.**

**단 하나 명확히 해둘 것 — steady below-OP "1.6%":** 실측 steady(이자 73 + 비영업연금 119 = 192)는
192/11,104 = **1.73%**다. §16이 채택한 1.6%는 오독이 아니라 **실측보다 낮게 잡은 의도적 보수 설정**이다
(below-OP를 낮게 잡으면 EPS가 낮아진다). 후속 세션이 "1.73%인데 1.6%로 잘못 읽었다"고 되돌리지 말 것.

**미완 1건(정직 기재):** 샌드박스는 `www.sec.gov` 프로세스 접근이 프록시 403(`CONNECT tunnel failed`)이라
**원문 바이트 저장과 SHA-256 계산을 하지 못했다.** WebFetch 결과는 markdown 변환본이므로 바이트 동일성이 없다.
→ `reports/.cache/src/gev_10q_20260722.htm` + `.meta.json` 저장은 **호스트/Codex 몫으로 남긴다.**
현재 감사 사슬의 실체는 **accession 0001996810-26-000148 + R2.htm + 위 항등식**이다.

## 14. 실행 내역 (변경 파일)

**커밋 1 — P1 문서 정정**
- `HANDOFF_generic_engine.md:32` — pdfplumber 오진 → `test_fetch_dart_mdna_nonempty`(라이브 DART 네트워크 의존)로 정정

**커밋 2 — P0 프로세스 계약**
- `START-efe-q2-2026-00-COMMON.md` — §7 "원문 인용 계약" 신설(Codex 7항 + 원본 보존 규정 + 샌드박스 SHA-256 제약 + 스크립트 인코딩 규칙), §3-1에 포인터 1줄

**커밋 3 — Phase-B 동면 명시 (코드 게이트 없음)**
- `pipeline/disclosure_loader.py` — 모듈 docstring에 STATUS: DORMANT + 알려진 결함 3건 + "게이트를 여기 넣지 않는 이유"
- `ai/extractor.py` — STATUS: DORMANT(+ `signal_*.json` 0건 = 실사용 이력 없음)
- `cli.py` — `run_signal_backtest_mode` / `run_call_brief_mode` docstring에 DORMANT + 재활성화 조건
- `tests/test_disclosure_loader.py` — `@pytest.mark.network` + "이 assert는 완전성을 증명하지 않는다" 주석
- `pyproject.toml` — `markers` 등록(strict-markers 대응) + `addopts`에 `-m 'not network'`
- `docs/methodology.md` §12 / `docs/ai_collaboration.md` / `docs/data_sources.md` / `HANDOFF_phase_b.md` — DORMANT 배너

**검증(수행함):** 5개 .py/toml 구문 파싱 OK · pytest 설정 격리 재현(정상 1 passed·network 1 deselected,
`-m network` 시 실행됨, 미등록 마커는 여전히 strict 에러) · START-COMMON 144줄·11,734바이트 재read OK.
**엔진 코드 0줄 변경** → forward 회귀·9Q sha·FROZEN 무접촉.

**남은 것 (호스트/Codex):**
1. 3개 커밋 실행 — START-COMMON §5는 git을 호스트/Codex 전담으로 규정하므로 Claude가 커밋하지 않았다.
   워킹트리에 **무관한 미커밋 변경 9건**이 있으므로 반드시 경로 지정 `git add`로 격리할 것.
2. GEV 원문 바이트 보존 + SHA-256(§13 미완 1건).
3. Phase-B 재활성화를 실제 일정에 올릴 때: 프로파일 복원 + 실제 deck/DART fixture + 완전성 계약을 **한 작업**으로.
