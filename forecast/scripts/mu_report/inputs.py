"""Pinned evidence access with deterministic and runtime audit records."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[2]
PIN_FILE = PACKAGE_DIR / "input_pins.yaml"


class InputGateError(RuntimeError):
    """Raised when an evidence read violates the phase allowlist or hash pin."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _relative_path(path: str | Path) -> str:
    candidate = Path(path)
    resolved = (REPO_ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError as exc:
        raise InputGateError(f"input escapes repository root: {path}") from exc


def load_pins() -> dict[str, list[dict[str, Any]]]:
    data = yaml.safe_load(PIN_FILE.read_text(encoding="utf-8"))
    return data["phases"]


@dataclass(frozen=True)
class AuditEntry:
    path: str
    sha256: str
    phase: str
    kind: str = "evidence"


@dataclass(frozen=True)
class ConflictConfirmation:
    author: str
    ticker: str
    status: str
    confirmed_at_kst: datetime
    edition: str
    path: str
    git_blob_sha: str
    read_at_kst: str
    kind: str = "internal_config"


class EvidenceReader:
    """The sole access path for externally archived report evidence."""

    def __init__(self, phase: str, pins: dict[str, list[dict[str, Any]]] | None = None):
        self.phase = phase
        self.pins = pins or load_pins()
        if phase not in self.pins:
            raise InputGateError(f"unknown phase: {phase}")
        phase_order = {"E2-A": ["E2-A"], "E2-B": ["E2-A", "E2-B"], "E2-C": ["E2-A", "E2-B", "E2-C"]}
        allowed_phases = phase_order[phase]
        self.allowed = {
            item["path"]: item["sha256"]
            for allowed_phase in allowed_phases
            for item in self.pins[allowed_phase]
        }
        self.audit: list[AuditEntry] = []

    def read_bytes(self, path: str | Path) -> bytes:
        rel = _relative_path(path)
        if rel not in self.allowed:
            raise InputGateError(f"path is not allowlisted for {self.phase}: {rel}")
        expected = self.allowed[rel]
        if expected is None:
            raise InputGateError(f"input pin is not populated: {rel}")
        payload = (REPO_ROOT / rel).read_bytes()
        actual = sha256_bytes(payload)
        if actual != expected:
            raise InputGateError(f"SHA-256 mismatch for {rel}: expected {expected}, got {actual}")
        self.audit.append(AuditEntry(path=rel, sha256=actual, phase=self.phase))
        return payload

    def read_text(self, path: str | Path, encoding: str = "utf-8") -> str:
        return self.read_bytes(path).decode(encoding)

    def audit_payload(self) -> bytes:
        unique = {(entry.path, entry.sha256, entry.phase, entry.kind): entry for entry in self.audit}
        rows = [entry.__dict__ for entry in sorted(unique.values(), key=lambda item: item.path)]
        return (json.dumps({"phase": self.phase, "reads": rows}, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

    def write_audit(self, path: str | Path) -> None:
        atomic_write(Path(path), self.audit_payload())

    def write_runtime_log(self, directory: str | Path | None = None) -> Path:
        log_dir = Path(directory) if directory else REPO_ROOT / "logs" / "_mu_report_runs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        target = log_dir / f"{self.phase.lower()}_{stamp}.json"
        payload = json.loads(self.audit_payload())
        payload["created_at_utc"] = stamp
        atomic_write(target, (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        return target


def read_input(path: str | Path, phase: str) -> bytes:
    """Read one pinned input; callers needing an audit trail use EvidenceReader."""
    return EvidenceReader(phase).read_bytes(path)


def load_conflict_confirmation(
    path: str | Path,
    edition: str,
    now_kst: datetime,
) -> ConflictConfirmation:
    """Load the strict internal conflict-confirmation record without consulting a clock."""
    rel = _relative_path(path)
    payload = (REPO_ROOT / rel).read_bytes()
    parsed = yaml.safe_load(payload.decode("utf-8"))
    required = {"author", "ticker", "status", "confirmed_at_kst", "edition"}
    if not isinstance(parsed, dict) or set(parsed) != required:
        raise InputGateError(f"conflict confirmation keys must be exactly {sorted(required)}")
    if parsed["author"] != "김지원" or parsed["ticker"] != "MU":
        raise InputGateError("unknown conflict confirmation author or ticker")
    if parsed["status"] not in {"not_held", "held"}:
        raise InputGateError(f"unknown conflict confirmation status: {parsed['status']}")
    if parsed["edition"] not in {"ed1", "ed2"}:
        raise InputGateError(f"unknown conflict confirmation edition: {parsed['edition']}")
    if edition not in {"ed1", "ed2"}:
        raise InputGateError(f"unknown build edition: {edition}")
    if now_kst.tzinfo is None or now_kst.utcoffset() != timedelta(hours=9):
        raise InputGateError("now_kst must be timezone-aware KST")
    try:
        confirmed = datetime.fromisoformat(str(parsed["confirmed_at_kst"]))
    except ValueError as exc:
        raise InputGateError("invalid confirmed_at_kst") from exc
    if confirmed.tzinfo is None or confirmed.utcoffset() != timedelta(hours=9):
        raise InputGateError("confirmed_at_kst must be timezone-aware KST")
    header = f"blob {len(payload)}\0".encode("ascii")
    blob_sha = hashlib.sha1(header + payload).hexdigest()
    return ConflictConfirmation(
        author=parsed["author"],
        ticker=parsed["ticker"],
        status=parsed["status"],
        confirmed_at_kst=confirmed,
        edition=parsed["edition"],
        path=rel,
        git_blob_sha=blob_sha,
        read_at_kst=now_kst.isoformat(),
    )


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_bytes(payload)
    os.replace(temp, path)
