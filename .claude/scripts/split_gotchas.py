"""Gotchas 자동 분리 스크립트.

SKILL.md의 Gotchas 섹션이 임계값(기본 10줄)을 초과하면
references/gotchas.md로 분리하고, SKILL.md에는 링크만 남긴다.

Usage:
    python .claude/scripts/split_gotchas.py [파일경로]
    python .claude/scripts/split_gotchas.py              # 전체 스킬 스캔
    python .claude/scripts/split_gotchas.py .claude/skills/profile/SKILL.md

Hook으로 사용 시:
    파일경로가 .claude/skills/*/SKILL.md 패턴이면 해당 파일만 처리.
"""

import io
import re
import sys
from pathlib import Path

# Windows cp949 인코딩 에러 방지
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

THRESHOLD = 10  # Gotchas 줄 수 임계값
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
LINK_LINE = "상세: [references/gotchas.md](references/gotchas.md)"


def _parse_gotchas(text: str) -> tuple[str | None, list[str], str, str]:
    """SKILL.md에서 Gotchas 섹션을 파싱.

    Returns:
        (섹션 헤더, gotcha 라인들, 섹션 이전 텍스트, 섹션 이후 텍스트)
        섹션이 없으면 (None, [], text, "")
    """
    lines = text.split("\n")
    start = None
    end = None
    header = None

    for i, line in enumerate(lines):
        if re.match(r"^##\s+Gotchas", line, re.IGNORECASE):
            start = i
            header = line
        elif start is not None and re.match(r"^##\s+", line):
            end = i
            break

    if start is None:
        return None, [], text, ""

    if end is None:
        end = len(lines)

    gotcha_lines = [l for l in lines[start + 1 : end] if l.strip()]
    before = "\n".join(lines[:start])
    after = "\n".join(lines[end:])
    return header, gotcha_lines, before, after


def _is_already_split(gotcha_lines: list[str]) -> bool:
    """이미 references/gotchas.md로 분리된 상태인지 확인."""
    return any("references/gotchas.md" in l for l in gotcha_lines)


def process_skill(skill_md: Path, dry_run: bool = False) -> bool:
    """단일 SKILL.md를 처리. 분리했으면 True."""
    text = skill_md.read_text(encoding="utf-8")
    header, gotcha_lines, before, after = _parse_gotchas(text)

    if header is None:
        return False

    if _is_already_split(gotcha_lines):
        return False

    if len(gotcha_lines) <= THRESHOLD:
        return False

    skill_name = skill_md.parent.name
    refs_dir = skill_md.parent / "references"
    refs_dir.mkdir(exist_ok=True)
    gotchas_file = refs_dir / "gotchas.md"

    if dry_run:
        print(f"[DRY] {skill_name}: {len(gotcha_lines)}줄 → 분리 대상")
        return True

    # references/gotchas.md 작성
    gotchas_content = f"# {skill_name} Gotchas\n\n" + "\n".join(gotcha_lines) + "\n"
    gotchas_file.write_text(gotchas_content, encoding="utf-8")

    # SKILL.md 재구성: Gotchas 섹션을 링크로 교체
    new_text = before.rstrip() + f"\n\n{header}\n{LINK_LINE}\n"
    if after.strip():
        new_text += "\n" + after.lstrip()
    skill_md.write_text(new_text, encoding="utf-8")

    print(f"[SPLIT] {skill_name}: {len(gotcha_lines)}줄 → references/gotchas.md 분리 완료")
    return True


def main():
    targets: list[Path] = []

    if len(sys.argv) > 1:
        p = Path(sys.argv[1]).resolve()
        if p.name == "SKILL.md" and p.exists():
            targets.append(p)
        else:
            print(f"대상 아님: {p}")
            return
    else:
        # 전체 스킬 디렉토리 스캔
        if SKILLS_DIR.exists():
            targets = sorted(SKILLS_DIR.glob("*/SKILL.md"))

    if not targets:
        print("처리할 SKILL.md 없음")
        return

    split_count = 0
    for skill_md in targets:
        if process_skill(skill_md):
            split_count += 1

    if split_count == 0:
        print(f"모든 스킬 Gotchas {THRESHOLD}줄 이하 — 분리 불필요")


if __name__ == "__main__":
    main()
