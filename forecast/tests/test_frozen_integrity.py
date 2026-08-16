"""Repository-level integrity gate for immutable ``*_FROZEN.md`` reports."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONVENTION_DATE = "2026-08-05"
CONVENTION_PROFILES = {
    "amd_q2_2026_forecast_FROZEN.md": "profiles/amd.generic.yaml",
    "sndk_fy2026q4_forecast_FROZEN.md": "profiles/sndk.generic.yaml",
    "spcx_q2_2026_forecast_FROZEN.md": "profiles/spcx.generic.yaml",
    "vst_q2_2026_forecast_FROZEN.md": "profiles/vst.generic.yaml",
}
SHA_TOKEN = re.compile(r"(?i)([0-9a-f]{64}|[0-9a-f]{8}…[0-9a-f]{4})")
REMEDIATION = "FROZEN은 편집 금지. 정정은 *_errata.md 형제 파일로."


@dataclass
class IntegrityResult:
    """Aggregate visible coverage and failures for one repository scan."""

    checked: int = 0
    skipped: int = 0
    failures: list[str] = field(default_factory=list)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
    )


def _freeze_commit(repo: Path, relative_path: str) -> str | None:
    history = _git(
        repo,
        "log",
        "--diff-filter=A",
        "--format=%H",
        "--",
        relative_path,
    )
    if history.returncode != 0:
        return None
    commits = [line for line in history.stdout.decode("ascii").splitlines() if line]
    return commits[-1] if commits else None


def _header_profile_shas(path: Path) -> list[str]:
    header = "\n".join(path.read_text(encoding="utf-8").splitlines()[:40])
    profile_lines = "\n".join(
        line for line in header.splitlines() if "profile" in line.lower() or "프로파일" in line
    )
    return SHA_TOKEN.findall(profile_lines)


def _sha_matches(expected: str, token: str) -> bool:
    normalized = token.lower()
    if "…" not in normalized:
        return normalized == expected
    prefix, suffix = normalized.split("…", 1)
    return expected.startswith(prefix) and expected.endswith(suffix)


def _record_failure(result: IntegrityResult, path: Path, reason: str) -> None:
    message = f"FAIL: {path.as_posix()} - {reason}"
    result.failures.append(message)
    print(message)
    print(f"  -> {REMEDIATION}")


def verify_frozen_integrity(repo: Path = REPO) -> IntegrityResult:
    """Check every FROZEN report and visibly skip unsupported conventions.

    Basic Git tracking, ignore, and HEAD-blob checks apply to every report.
    Profile SHA checks compare the header with the profile blob in the commit
    that first added the FROZEN report, never with the evolving working tree.
    """

    result = IntegrityResult()
    frozen_files = sorted((repo / "reports").glob("*_FROZEN.md"))
    if not frozen_files:
        _record_failure(result, repo / "reports", "no *_FROZEN.md files found")
        return result

    if shutil.which("git") is None or not (repo / ".git").exists():
        for path in frozen_files:
            print(f"SKIPPED: {path.relative_to(repo).as_posix()} - git unavailable")
            result.skipped += 1
        print(f"SUMMARY: 검사 {result.checked}건 / SKIP {result.skipped}건")
        print("HOST REQUIRED: run this gate in the Git checkout on the Windows host.")
        return result

    for path in frozen_files:
        relative_path = path.relative_to(repo).as_posix()
        profile_path = CONVENTION_PROFILES.get(path.name)
        if profile_path is not None:
            result.checked += 1

        tracked = _git(repo, "ls-files", "--error-unmatch", "--", relative_path)
        if tracked.returncode != 0:
            _record_failure(result, path.relative_to(repo), "not tracked by git")
            continue

        ignored = _git(repo, "check-ignore", "--quiet", "--", relative_path)
        if ignored.returncode == 0:
            _record_failure(result, path.relative_to(repo), "matched by .gitignore")
            continue
        if ignored.returncode not in (0, 1):
            _record_failure(result, path.relative_to(repo), "git check-ignore could not run")
            continue

        head_blob = _git(repo, "show", f"HEAD:{relative_path}")
        if head_blob.returncode != 0:
            _record_failure(result, path.relative_to(repo), "HEAD blob unavailable")
            continue
        if path.read_bytes() != head_blob.stdout:
            _record_failure(result, path.relative_to(repo), "working tree differs from HEAD blob")
            continue

        if profile_path is None:
            print(
                f"SKIPPED: {relative_path} - "
                f"convention N/A (frozen before {CONVENTION_DATE})"
            )
            result.skipped += 1
            continue

        freeze_commit = _freeze_commit(repo, relative_path)
        if freeze_commit is None:
            print(f"SKIPPED: {relative_path} - freeze commit could not be identified")
            result.skipped += 1
            continue

        profile_blob = _git(repo, "show", f"{freeze_commit}:{profile_path}")
        if profile_blob.returncode != 0:
            _record_failure(
                result,
                path.relative_to(repo),
                f"profile {profile_path} unavailable at freeze commit {freeze_commit[:12]}",
            )
            continue
        expected_sha = hashlib.sha256(profile_blob.stdout).hexdigest()
        header_shas = _header_profile_shas(path)
        if not any(_sha_matches(expected_sha, token) for token in header_shas):
            rendered = ", ".join(header_shas) or "none"
            _record_failure(
                result,
                path.relative_to(repo),
                f"profile SHA mismatch at freeze commit {freeze_commit[:12]} "
                f"(expected {expected_sha}, header {rendered})",
            )
            continue

        print(
            f"PASS: {relative_path} - tracked, not ignored, HEAD-clean, "
            f"freeze profile SHA matched at {freeze_commit[:12]}"
        )

    print(f"SUMMARY: 검사 {result.checked}건 / SKIP {result.skipped}건")
    return result


def test_frozen_integrity() -> None:
    result = verify_frozen_integrity()
    if shutil.which("git") is None or not (REPO / ".git").exists():
        pytest.skip("git unavailable; FROZEN integrity gate must run on the Windows host")
    assert not result.failures, "\n".join([*result.failures, REMEDIATION])


def test_git_absence_is_a_loud_graceful_skip(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)

    result = verify_frozen_integrity()

    output = capsys.readouterr().out
    assert not result.failures
    assert result.checked == 0
    assert result.skipped == len(list((REPO / "reports").glob("*_FROZEN.md")))
    assert "git unavailable" in output
    assert "HOST REQUIRED" in output
    assert "SUMMARY: 검사 0건 / SKIP" in output
