"""Git provenance for future offline D10 measurements (no batch runner yet)."""

import logging
import re
import subprocess
from pathlib import Path, PurePosixPath

logger = logging.getLogger(__name__)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "--no-optional-locks", "--literal-pathspecs", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        raise ValueError(
            f"Git provenance check failed ({args[0]}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def resolve_commit(repo: Path, commit: str) -> str:
    """Resolve a stored SHA prefix; symbolic refs are not provenance identifiers."""
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", commit):
        raise ValueError("bvt_commit must contain 7-40 hexadecimal characters")
    return _git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}")


def input_blob_shas(repo: Path, commit: str, profile: str) -> dict[str, str]:
    """Read historical blob IDs without requiring the historical checkout."""
    path = PurePosixPath(profile)
    if path.is_absolute() or ".." in path.parts or ":" in profile or "\\" in profile:
        raise ValueError("profile must be a repository-relative POSIX path")
    resolved = resolve_commit(repo, commit)
    paths = {
        "profile": profile,
        "dcf_engine": "engine/dcf.py",
        "wacc_engine": "engine/wacc.py",
    }
    blobs = {}
    for key, filename in paths.items():
        object_name = f"{resolved}:{filename}"
        if _git(repo, "cat-file", "-t", object_name) != "blob":
            raise ValueError(f"Input is not a blob: {filename}")
        blobs[key] = _git(repo, "rev-parse", "--verify", object_name)
    return blobs


def collect_provenance(repo: Path, profile: str) -> dict:
    """Record HEAD blobs only after Git confirms clean, tracked input files.

    Call immediately before measurement. This check does not lock the checkout;
    callers must prevent concurrent edits while measuring.
    """
    repo = Path(_git(repo, "rev-parse", "--show-toplevel"))
    commit = _git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    blobs = input_blob_shas(repo, commit, profile)
    for filename in (profile, "engine/dcf.py", "engine/wacc.py"):
        _git(repo, "ls-files", "--error-unmatch", "--", filename)
        # Comparing against the captured commit includes staged changes and lets
        # Git handle CRLF normalization. Never substitute a worktree hash.
        try:
            _git(repo, "diff", "--quiet", "--no-ext-diff", commit, "--", filename)
        except ValueError as exc:
            raise ValueError(
                f"dirty input or diff failure (git diff vs {commit[:7]}): {filename}"
            ) from exc
    if not _git(repo, "branch", "-r", "--contains", commit):
        logger.warning(
            "BVT commit %s is not reachable from locally known remote branches", commit
        )
    return {"bvt_commit": commit, "input_sha": blobs}
