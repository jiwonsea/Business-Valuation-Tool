"""Repository-level integrity gate for immutable ``*_FROZEN.md`` reports."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

FORECAST_ROOT = Path(__file__).resolve().parents[1]
CONVENTION_DATE = "2026-08-05"
CONVENTION_PROFILES = {
    "amd_q2_2026_forecast_FROZEN.md": "profiles/amd.generic.yaml",
    "sndk_fy2026q4_forecast_FROZEN.md": "profiles/sndk.generic.yaml",
    "spcx_q2_2026_forecast_FROZEN.md": "profiles/spcx.generic.yaml",
    "vst_q2_2026_forecast_FROZEN.md": "profiles/vst.generic.yaml",
}
LEGACY_BOUNDARY_EXCEPTIONS = {
    "gev_q2_2026_forecast_FROZEN.md": "514ed089acf7d1671bc0aa8b1b666b0479694fe6",
    "tsla_q2_2026_forecast_FROZEN.md": "514ed089acf7d1671bc0aa8b1b666b0479694fe6",
}
KST = timezone(timedelta(hours=9))
SHA_TOKEN = re.compile(r"(?i)([0-9a-f]{64}|[0-9a-f]{8}…[0-9a-f]{4})")
REMEDIATION = "FROZEN은 편집 금지. 정정은 *_errata.md 형제 파일로."


@dataclass
class IntegrityResult:
    """Aggregate visible coverage and failures for one repository scan."""

    checked: int = 0
    passed: int = 0
    skipped: int = 0
    supported_skipped: int = 0
    failures: list[str] = field(default_factory=list)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
    )


def _git_root(forecast_root: Path) -> Path | None:
    if shutil.which("git") is None:
        return None
    resolved = _git(forecast_root, "rev-parse", "--show-toplevel")
    if resolved.returncode != 0:
        return None
    output = resolved.stdout.decode("utf-8").strip()
    return Path(output) if output else None


def _freeze_commit(repo: Path, relative_paths: list[str]) -> str | None:
    for relative_path in relative_paths:
        history = _git(
            repo,
            "log",
            "--full-history",
            "--diff-filter=A",
            "--format=%H",
            "--",
            relative_path,
        )
        if history.returncode != 0:
            continue
        commits = [line for line in history.stdout.decode("ascii").splitlines() if line]
        if commits:
            return commits[-1]
    return None


def _first_blob(repo: Path, commit: str, relative_paths: list[str]) -> bytes | None:
    for relative_path in relative_paths:
        blob = _git(repo, "show", f"{commit}:{relative_path}")
        if blob.returncode == 0:
            return blob.stdout
    return None


def _commit_date_kst(repo: Path, commit: str) -> date | None:
    # Git convention classification only, not evidence of the information cutoff
    # or the report's self-declared frozen_at.
    result = _git(repo, "show", "-s", "--format=%cI", commit)
    if result.returncode != 0:
        return None
    try:
        timestamp = datetime.fromisoformat(result.stdout.decode("utf-8").strip())
        if timestamp.tzinfo is None:
            return None
        return timestamp.astimezone(KST).date()
    except (ValueError, UnicodeDecodeError, OverflowError):
        return None


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


def verify_frozen_integrity(forecast_root: Path = FORECAST_ROOT) -> IntegrityResult:
    """Check FROZEN coverage, allowing only date-qualified legacy skips.

    Basic Git tracking, ignore, and HEAD-blob checks apply to every report.
    Profile SHA checks compare the header with the profile blob in the commit
    that first added the FROZEN report, never with the evolving working tree.
    """

    result = IntegrityResult()
    frozen_files = sorted((forecast_root / "reports").glob("*_FROZEN.md"))
    if not frozen_files:
        _record_failure(result, forecast_root / "reports", "no *_FROZEN.md files found")
        return result

    repo = _git_root(forecast_root)
    if repo is None:
        for path in frozen_files:
            relative_path = path.relative_to(forecast_root).as_posix()
            print(f"SKIPPED: {relative_path} - git unavailable")
            result.skipped += 1
            if path.name in CONVENTION_PROFILES:
                result.supported_skipped += 1
        print(
            f"SUMMARY: 검사 {result.checked}건 / PASS {result.passed}건 / "
            f"SKIP {result.skipped}건 / 지원 SKIP {result.supported_skipped}건"
        )
        print("HOST REQUIRED: run this gate in the Git checkout on the Windows host.")
        return result

    for path in frozen_files:
        relative_path = path.relative_to(repo).as_posix()
        display_path = path.relative_to(forecast_root).as_posix()
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

        freeze_commit = _freeze_commit(
            repo,
            [f"reports/{path.name}", relative_path],
        )
        if freeze_commit is None:
            _record_failure(result, path.relative_to(repo), "freeze commit could not be identified")
            result.supported_skipped += 1
            continue

        if profile_path is None:
            commit_date = _commit_date_kst(repo, freeze_commit)
            if commit_date is None:
                _record_failure(
                    result, path.relative_to(repo), "freeze commit date unavailable or invalid"
                )
                result.supported_skipped += 1
                continue
            convention_date = date.fromisoformat(CONVENTION_DATE)
            if commit_date < convention_date:
                reason = f"legacy: commit date {commit_date} KST before {CONVENTION_DATE}"
            elif (
                commit_date == convention_date
                and LEGACY_BOUNDARY_EXCEPTIONS.get(path.name) == freeze_commit
            ):
                reason = f"legacy boundary exception: commit {freeze_commit} ({commit_date} KST)"
            else:
                _record_failure(
                    result,
                    path.relative_to(repo),
                    f"unregistered FROZEN: commit date {commit_date} KST on/after {CONVENTION_DATE}",
                )
                result.supported_skipped += 1
                continue
            print(f"SKIPPED: {display_path} - {reason}")
            result.skipped += 1
            continue

        profile_blob = _first_blob(
            repo,
            freeze_commit,
            [f"forecast/{profile_path}", profile_path],
        )
        if profile_blob is None:
            _record_failure(
                result,
                path.relative_to(repo),
                f"profile forecast/{profile_path} or {profile_path} unavailable "
                f"at freeze commit {freeze_commit[:12]}",
            )
            continue
        expected_sha = hashlib.sha256(profile_blob).hexdigest()
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
        result.passed += 1

    print(
        f"SUMMARY: 검사 {result.checked}건 / PASS {result.passed}건 / "
        f"SKIP {result.skipped}건 / 지원 SKIP {result.supported_skipped}건"
    )
    return result


def test_frozen_integrity() -> None:
    result = verify_frozen_integrity()
    if _git_root(FORECAST_ROOT) is None:
        pytest.skip("git unavailable; FROZEN integrity gate must run on the Windows host")
    assert result.checked == result.passed == len(CONVENTION_PROFILES)
    assert result.supported_skipped == 0
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
    assert result.passed == 0
    assert result.skipped == len(list((FORECAST_ROOT / "reports").glob("*_FROZEN.md")))
    assert result.supported_skipped == len(CONVENTION_PROFILES)
    assert "git unavailable" in output
    assert "HOST REQUIRED" in output
    assert "SUMMARY: 검사 0건 / PASS 0건 / SKIP" in output


@pytest.fixture
def isolated_forecast(tmp_path: Path) -> Path:
    if shutil.which("git") is None:
        pytest.skip("git required for isolated history tests")
    _fixture_git(tmp_path, "init", "--initial-branch=main")
    forecast_root = tmp_path / "forecast"
    (forecast_root / "reports").mkdir(parents=True)
    return forecast_root


def _fixture_git(repo: Path, *args: str, timestamp: str = "2026-09-01T00:00:00+09:00") -> str:
    env = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_DATE": timestamp,
        "GIT_COMMITTER_DATE": timestamp,
    }
    result = subprocess.run(
        [
            "git",
            "-c",
            "core.autocrlf=false",
            "-c",
            f"core.hooksPath={repo / 'no-hooks'}",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=Gate Test",
            "-c",
            "user.email=gate@example.invalid",
            *args,
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8").strip()


def _fixture_commit(repo: Path, timestamp: str = "2026-09-01T00:00:00+09:00") -> str:
    _fixture_git(repo, "add", ".", timestamp=timestamp)
    _fixture_git(repo, "commit", "-m", "fixture", timestamp=timestamp)
    return _fixture_git(repo, "rev-parse", "HEAD")


def _fixture_report(
    root: Path,
    name: str,
    profile_path: str = "profiles/test.yaml",
    blob: bytes = b"v: 1\n",
) -> Path:
    profile = root / profile_path
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_bytes(blob)
    report = root / "reports" / name
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        f"# Fixture\nprofile sha256: {hashlib.sha256(blob).hexdigest()}\n", encoding="utf-8"
    )
    return report


@pytest.mark.parametrize(
    ("timestamp", "legacy"),
    [
        ("2026-08-04T23:59:59+09:00", True),
        ("2026-08-04T14:59:59+00:00", True),
        ("2026-08-05T00:00:00+09:00", False),
        ("2026-08-04T15:00:00+00:00", False),
        ("2026-08-04T11:00:00-04:00", False),
        ("2026-09-28T05:00:00+09:00", False),
    ],
)
def test_unregistered_report_uses_kst_commit_date(
    isolated_forecast: Path,
    capsys: pytest.CaptureFixture[str],
    timestamp: str,
    legacy: bool,
) -> None:
    _fixture_report(isolated_forecast, "mu_fy2026q4_forecast_FROZEN.md")
    _fixture_commit(isolated_forecast.parent, timestamp)
    result = verify_frozen_integrity(isolated_forecast)
    output = capsys.readouterr().out
    assert result.checked == result.passed == 0
    assert result.skipped == int(legacy)
    assert result.supported_skipped == int(not legacy)
    assert len(result.failures) == int(not legacy)
    if legacy:
        assert "2026-08-04" in output and "KST" in output
    else:
        assert "unregistered" in output
        assert "frozen before" not in output


@pytest.mark.parametrize("case", ["gev", "tsla", "wrong_name", "wrong_commit"])
def test_boundary_exception_requires_exact_identity(
    isolated_forecast: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    case: str,
) -> None:
    ticker = case if case in ("gev", "tsla") else "gev"
    exception_name = f"{ticker}_q2_2026_forecast_FROZEN.md"
    name = "other_FROZEN.md" if case == "wrong_name" else exception_name
    _fixture_report(isolated_forecast, name)
    commit = _fixture_commit(isolated_forecast.parent, "2026-08-05T00:40:19+09:00")
    if case != "wrong_commit":
        monkeypatch.setitem(LEGACY_BOUNDARY_EXCEPTIONS, exception_name, commit)
    result = verify_frozen_integrity(isolated_forecast)
    output = capsys.readouterr().out
    valid = case in ("gev", "tsla")
    assert result.skipped == int(valid)
    assert result.supported_skipped == int(not valid)
    assert len(result.failures) == int(not valid)
    assert ("legacy boundary exception" in output) == valid
    assert "frozen before" not in output


@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize(
    "failure", ["no_history", "date_command", "invalid_date", "naive_date", "bad_utf8"]
)
def test_provenance_failures_are_closed(
    isolated_forecast: Path,
    monkeypatch: pytest.MonkeyPatch,
    registered: bool,
    failure: str,
) -> None:
    name = "test_FROZEN.md"
    _fixture_report(isolated_forecast, name)
    _fixture_commit(isolated_forecast.parent)
    if registered:
        monkeypatch.setitem(CONVENTION_PROFILES, name, "profiles/test.yaml")
    real_git = _git

    def broken_git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
        if failure == "no_history" and args[0] == "log":
            return subprocess.CompletedProcess(args, 0, b"", b"")
        if args[:3] == ("show", "-s", "--format=%cI"):
            if failure == "date_command":
                return subprocess.CompletedProcess(args, 128, b"", b"date unavailable")
            dates = {
                "invalid_date": b"not-a-date",
                "naive_date": b"2026-08-05T00:40:19",
                "bad_utf8": b"\xff",
            }
            return subprocess.CompletedProcess(args, 0, dates[failure], b"")
        return real_git(repo, *args)

    monkeypatch.setitem(globals(), "_git", broken_git)
    result = verify_frozen_integrity(isolated_forecast)
    must_fail = failure == "no_history" or not registered
    assert result.supported_skipped == int(must_fail)
    assert len(result.failures) == int(must_fail)
    assert result.passed == int(registered and not must_fail)


@pytest.mark.parametrize("with_b", [False, True])
def test_mapping_growth_checks_each_freeze_profile(
    isolated_forecast: Path,
    monkeypatch: pytest.MonkeyPatch,
    with_b: bool,
) -> None:
    fixture_mapping = {f"fixture_{i}_FROZEN.md": f"profiles/fixture_{i}.yaml" for i in range(4)}
    monkeypatch.setitem(globals(), "CONVENTION_PROFILES", fixture_mapping)
    for name, profile_path in CONVENTION_PROFILES.items():
        _fixture_report(isolated_forecast, name, profile_path)
    # Supported reports remain SHA-checked even before the convention date.
    _fixture_commit(isolated_forecast.parent, "2026-08-01T00:00:00+09:00")
    profile_path = "profiles/mu.generic.yaml"
    name_a = "mu_fy2026q4_forecast_FROZEN.md"
    _fixture_report(isolated_forecast, name_a, profile_path, b"version: A\n")
    monkeypatch.setitem(CONVENTION_PROFILES, name_a, profile_path)
    _fixture_commit(isolated_forecast.parent, "2026-09-28T05:00:00+09:00")
    if with_b:
        name_b = "mu_fy2026q4_rev1_FROZEN.md"
        _fixture_report(isolated_forecast, name_b, profile_path, b"version: B\n")
        monkeypatch.setitem(CONVENTION_PROFILES, name_b, profile_path)
        _fixture_commit(isolated_forecast.parent, "2026-09-29T05:00:00+09:00")
    # A later profile revision must not invalidate either historical report.
    (isolated_forecast / profile_path).write_bytes(b"version: current\n")
    _fixture_commit(isolated_forecast.parent, "2026-09-30T05:00:00+09:00")
    result = verify_frozen_integrity(isolated_forecast)
    assert result.checked == result.passed == 5 + int(with_b)
    assert result.supported_skipped == 0
    assert not result.failures
    real_verify = verify_frozen_integrity
    monkeypatch.setitem(
        globals(), "verify_frozen_integrity", lambda: real_verify(isolated_forecast)
    )
    monkeypatch.setitem(globals(), "FORECAST_ROOT", isolated_forecast)
    # Exercise the actual repository assertion, including the removed literal.
    test_frozen_integrity()


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        ("untracked", "not tracked by git"),
        ("head_missing", "HEAD blob unavailable"),
        ("head_changed", "working tree differs from HEAD blob"),
        ("profile_missing", "unavailable at freeze commit"),
        ("sha_mismatch", "profile SHA mismatch"),
        ("ignored", "matched by .gitignore"),
    ],
)
def test_existing_failures_remain_failures(
    isolated_forecast: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    reason: str,
) -> None:
    name = "protected_FROZEN.md"
    report = _fixture_report(isolated_forecast, name)
    monkeypatch.setitem(CONVENTION_PROFILES, name, "profiles/test.yaml")
    if failure == "sha_mismatch":
        report.write_text("# Fixture\nprofile: " + "0" * 64 + "\n", encoding="utf-8")
    if failure == "profile_missing":
        (isolated_forecast / "profiles/test.yaml").unlink()
    if failure == "head_missing":
        _fixture_git(isolated_forecast.parent, "add", ".")
    elif failure != "untracked":
        _fixture_commit(isolated_forecast.parent)
    if failure == "head_changed":
        report.write_bytes(report.read_bytes() + b"changed\n")
    if failure == "ignored":
        real_git = _git

        def ignored_git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
            if args[0] == "check-ignore":
                return subprocess.CompletedProcess(args, 0, b"", b"")
            return real_git(repo, *args)

        monkeypatch.setitem(globals(), "_git", ignored_git)
    result = verify_frozen_integrity(isolated_forecast)
    assert result.checked == 1 and result.passed == 0
    assert len(result.failures) == 1 and reason in result.failures[0]


@pytest.mark.parametrize("historical", [False, True])
def test_both_history_and_profile_path_candidates(
    isolated_forecast: Path,
    monkeypatch: pytest.MonkeyPatch,
    historical: bool,
) -> None:
    repo = isolated_forecast.parent
    name = "path_FROZEN.md"
    source_root = repo if historical else isolated_forecast
    _fixture_report(source_root, name)
    first_commit = _fixture_commit(repo)
    if historical:
        for directory in ("reports", "profiles"):
            for path in (repo / directory).iterdir():
                destination = isolated_forecast / directory / path.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                path.rename(destination)
        _fixture_commit(repo, "2026-09-02T00:00:00+09:00")
    monkeypatch.setitem(CONVENTION_PROFILES, name, "profiles/test.yaml")
    real_git = _git
    calls = []

    def recording_git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
        calls.append(args)
        return real_git(repo, *args)

    monkeypatch.setitem(globals(), "_git", recording_git)
    result = verify_frozen_integrity(isolated_forecast)
    assert result.checked == result.passed == 1 and not result.failures
    log_paths = [args[-1] for args in calls if args[0] == "log"]
    expected = [f"reports/{name}"]
    if not historical:
        expected.append(f"forecast/reports/{name}")
    assert log_paths == expected
    blob_calls = [
        args[1] for args in calls if args[0] == "show" and args[1].startswith(first_commit)
    ]
    expected_blobs = [f"{first_commit}:forecast/profiles/test.yaml"]
    if historical:
        expected_blobs.append(f"{first_commit}:profiles/test.yaml")
    assert blob_calls == expected_blobs
