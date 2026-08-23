"""preflight_lint.py — 판정 문서 저술 pre-flight lint (P-4, Codex ADOPT P0)

규격: docs/CONVENTIONS_verdict_authoring.md §P-4. **FAIL 은 명확한 구조 불변식만**(L-1/L-3/L-6),
자연어 패턴은 WARN(의심 지점 표시)으로 제한한다(L-2/L-4/L-5). 자연어의 의미 정합성 판정은
Codex 적대 검증의 몫이다.

사용: python3 preflight_lint.py <doc.md> [--profile t4] [--config <config.json>]
종료코드: FAIL ≥1 → 1, 아니면 0 (WARN 은 종료코드에 영향 없음).

기본 프로파일 "t4" 는 T-4 계열 판정 문서용이며, config JSON 으로 대체/확장할 수 있다:
{
  "forbidden_in_section": {"섹션 시작 정규식": ["금지 토큰", ...]},
  "required_in_section":  {"섹션 시작 정규식": ["필수 토큰", ...]},
  "trigger_rcs": ["RC-1'", ...],          # 판정 트리거 (′ 는 ' 로도 허용)
  "descriptive_rcs": ["RC-3'", ...],      # 서술 층 — 판정 경로 문장 출현 시 FAIL
  "trigger_row_required": ["관측원 키워드", ...]  # L-3: 트리거 표 행 필수 요소
}
"""
from __future__ import annotations
import json, re, sys

SEV_FAIL, SEV_WARN = "FAIL", "WARN"

DEFAULT_PROFILES = {
    "t4": {
        # L-1: 정량 채점 절(§5)에 UNVERIFIABLE 계열·비채점 수치 금지
        "forbidden_in_section": {
            r"^## §5\.": ["UNVERIFIABLE", "BASIS_UNKNOWN", "βL", "CAGR", "§0.4-1"],
        },
        "required_in_section": {},
        "trigger_rcs": ["RC-1′", "RC-2′"],
        "descriptive_rcs": ["RC-3′"],
        # L-3: 판정 트리거 행이 갖춰야 할 요소의 표식 (관측원/임계값/층)
        "trigger_row_required": ["관측", "≥"],
    },
}

# L-2: 총칭 표현 (열거 없이 RC 집합을 뭉뚱그리는 표현)
GENERIC_PATTERNS = [
    (r"RC\s*전부", "총칭 'RC 전부' — 열거형(RC-1′·RC-2′ …)으로 쓸 것"),
    (r"모든\s*RC", "총칭 '모든 RC'"),
    (r"[0-9]개\s*모두(?!\s*미발화.*RC-)", "총칭 'N개 모두'"),
]
# L-4: 단일축/역산 결과 문맥 인접 결합 서술
AXIS_KEY = r"(단일축|단일-변수|역산|축\b|CAGR|WACC|βL|β<|마진\s*[0-9])"
CONJ_PATTERNS = [
    (r"동시에?\s*(성립|필요|충족)", "축 결합 서술 '동시 성립/필요' — OR·비식별 프레임 확인"),
    (r"그리고[^\n]{0,20}(필요|성립)", "'X 그리고 Y 필요' — 결합 명제 의심"),
    (r"모두\s*필요", "'모두 필요' — 결합 명제 의심"),
]
# L-5: 앵커 상대 결론
ANCHOR_CLAIM = r"(안전마진\s*부재|고평가\s*확정|저평가\s*확정)"
ANCHOR_MARK = r"기준"


def _in_quotes(line: str, m) -> bool:
    """매치가 따옴표(" … " 또는 「'」) 안에 있으면 True — 결함 인용/정정 이력 오탐 방지."""
    before = line[:m.start()]
    return before.count('"') % 2 == 1


def lint(text: str, cfg: dict):
    findings = []
    lines = text.split("\n")

    # 섹션 분해
    def section_slices():
        idx = [(i, l) for i, l in enumerate(lines) if l.startswith("## ")]
        for n, (i, l) in enumerate(idx):
            end = idx[n + 1][0] if n + 1 < len(idx) else len(lines)
            yield l, i, end

    # L-1 / required
    for sec_re, toks in cfg.get("forbidden_in_section", {}).items():
        for head, s, e in section_slices():
            if re.match(sec_re, head):
                body = "\n".join(lines[s:e])
                for t in toks:
                    if t in body:
                        findings.append((SEV_FAIL, "L-1", s + 1,
                                         f"금지 구역 [{head.strip()}] 에 금지 토큰 `{t}` 출현"))
    for sec_re, toks in cfg.get("required_in_section", {}).items():
        for head, s, e in section_slices():
            if re.match(sec_re, head):
                body = "\n".join(lines[s:e])
                for t in toks:
                    if t not in body:
                        findings.append((SEV_FAIL, "L-1R", s + 1,
                                         f"[{head.strip()}] 에 필수 토큰 `{t}` 부재"))

    norm = text.replace("'", "′")  # ′/' 동일 취급
    trig = [t.replace("'", "′") for t in cfg.get("trigger_rcs", [])]
    desc = [t.replace("'", "′") for t in cfg.get("descriptive_rcs", [])]

    # L-2 (따옴표 안 인용은 제외 — 정정 이력이 결함 문구를 인용하는 경우)
    for i, line in enumerate(lines):
        for pat, msg in GENERIC_PATTERNS:
            m = re.search(pat, line)
            if m and not _in_quotes(line, m):
                findings.append((SEV_WARN, "L-2", i + 1, msg))

    # L-3: 트리거 RC 정의 표 행 = 임계 표식(비교 연산·방향어) + 관측원 표식 둘 다 필수 (구조 불변식)
    thr_marks = cfg.get("threshold_markers", ["≥", "≤", "대비", "이상", "이하", "증가", "감소"])
    src_marks = cfg.get("source_markers", ["보도자료", "10-Q", "PR", "CFS", "공시"])
    for i, line in enumerate(lines):
        nline = line.replace("'", "′")
        if re.match(r"\|\s*\*\*RC-", nline) and any(t in nline for t in trig):
            missing = []
            if not any(k in nline for k in thr_marks):
                missing.append("임계 표식")
            if not any(k in nline for k in src_marks):
                missing.append("관측원 표식")
            if missing:
                findings.append((SEV_FAIL, "L-3", i + 1,
                                 f"판정 트리거 표 행에 {'·'.join(missing)} 부재"))

    # L-4 (마크다운 강조 제거 후 매칭 — "**동시에** 성립" 류)
    for i, line in enumerate(lines):
        plain = line.replace("**", "")
        if re.search(AXIS_KEY, plain):
            for pat, msg in CONJ_PATTERNS:
                m = re.search(pat, plain)
                if m and not _in_quotes(plain, m):
                    findings.append((SEV_WARN, "L-4", i + 1, msg))

    # L-5 (부정문·따옴표 인용 제외 — "'고평가 확정' 으로는 올리지 않는다" 류)
    for i, line in enumerate(lines):
        m = re.search(ANCHOR_CLAIM, line)
        if (m and ANCHOR_MARK not in line and not _in_quotes(line, m)
                and not re.search(r"(않|금지|아니)", line)):
            findings.append((SEV_WARN, "L-5", i + 1,
                             "앵커 식별자('X 기준') 없는 밸류에이션 결론 의심"))

    # L-6: 서술 층 RC 가 판정 경로 문장(발화/미발화 포함, '서술' 표식 없음)에 출현
    for i, line in enumerate(lines):
        nline = line.replace("'", "′")
        if any(d in nline for d in desc) and re.search(r"발화", nline):
            if "서술" not in nline and "불포함" not in nline:
                findings.append((SEV_FAIL, "L-6", i + 1,
                                 "서술 층 RC 가 판정 경로 문장에 출현 (서술/불포함 표식 없음)"))
    return findings


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    path = argv[0]
    profile = "t4"
    cfg = None
    if "--profile" in argv:
        profile = argv[argv.index("--profile") + 1]
    if "--config" in argv:
        cfg = json.load(open(argv[argv.index("--config") + 1], encoding="utf-8"))
    if cfg is None:
        cfg = DEFAULT_PROFILES[profile]
    text = open(path, encoding="utf-8").read()
    findings = lint(text, cfg)
    fails = [f for f in findings if f[0] == SEV_FAIL]
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    for sev, code, ln, msg in findings:
        try:
            print(f"{sev} {code} L{ln}: {msg}")
        except Exception:
            print(f"{sev} {code} L{ln}: <msg print failed>")
    print(f"RESULT {'FAIL' if fails else 'PASS'} fail={len(fails)} warn={len(findings)-len(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
