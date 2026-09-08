"""Standing seal: which profiles may carry a ``valuation:`` block.

D10 다종목 확장은 두 번째 ``valuation:`` 블록을 추가하는 순간
"FROZEN 대응 프로파일은 전부 미보유" 라는 안전 근거를 소멸시킨다.
그 근거를 문서가 아니라 테스트로 강제한다. 사람의 주의력을 게이트로 삼지 않는다.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml

from forecast.tests.test_frozen_integrity import CONVENTION_PROFILES

FORECAST_ROOT = Path(__file__).resolve().parents[1]
PROFILE_SUFFIXES = (".yaml", ".yml")
# New ticker characters or period formats require an explicit convention entry.
FROZEN_REPORT = re.compile(
    r"^(?P<ticker>[a-z0-9]+)_(?P<period>q[1-4]_\d{4}|fy\d{4}q[1-4])_forecast_FROZEN\.md$"
)
VALUATION_ALLOWLIST = frozenset({"sk_hynix.yaml"})
REMEDIATION = (
    "valuation: 보유 집합은 VALUATION_ALLOWLIST와 정확히 일치해야 한다(부분집합 아님). "
    "종목을 추가하려면 같은 PR에서 이 테스트의 allowlist도 함께 고쳐라 — "
    "그 마찰이 설계 의도다."
)
FROZEN_REMEDIATION = (
    "FROZEN 대응 프로파일은 valuation:을 가질 수 없다. "
    "FROZEN은 편집 금지이며 탄력도 변경이 FROZEN 산출물에 도달해서는 안 된다."
)


@dataclass
class AllowlistResult:
    """Aggregate one repository scan of ``valuation:`` holders."""

    scanned: int = 0
    holders: set[str] = field(default_factory=set)
    # report -> profile filename; None means the name cannot be resolved.
    frozen_profiles: dict[str, str | None] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


def _profile_files(profiles_dir: Path) -> list[Path]:
    if not profiles_dir.is_dir():
        return []
    return sorted(
        path
        for path in profiles_dir.iterdir()
        if path.is_file() and path.suffix in PROFILE_SUFFIXES
    )


def _has_valuation_key(path: Path) -> tuple[bool, str | None]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return False, str(exc)
    if not isinstance(raw, dict):
        return False, "top-level YAML value is not a mapping"
    return "valuation" in raw, None


def _frozen_profile_names(forecast_root: Path) -> dict[str, str | None]:
    frozen_profiles = {}
    for report in sorted((forecast_root / "reports").glob("*_FROZEN.md")):
        configured = CONVENTION_PROFILES.get(report.name)
        if configured:
            profile_name = Path(configured).name
        else:
            match = FROZEN_REPORT.fullmatch(report.name)
            profile_name = f"{match['ticker']}.generic.yaml" if match else None
        frozen_profiles[report.name] = profile_name
    return frozen_profiles


def verify_valuation_allowlist(forecast_root: Path = FORECAST_ROOT) -> AllowlistResult:
    profiles_dir = forecast_root / "profiles"
    profile_files = _profile_files(profiles_dir)
    result = AllowlistResult(frozen_profiles=_frozen_profile_names(forecast_root))

    if not profile_files:
        result.failures.append(f"no profile files found: {profiles_dir}")

    for path in profile_files:
        result.scanned += 1
        has_valuation, reason = _has_valuation_key(path)
        if reason is not None:
            result.failures.append(f"UNREADABLE: {path.name} - {reason}")
        elif has_valuation:
            result.holders.add(path.name)

    existing_profiles = {path.name for path in profile_files}
    for report_name, profile_name in result.frozen_profiles.items():
        if profile_name is None:
            result.failures.append(
                f"UNRESOLVED: {report_name} - 규약 비대상 파일명 "
                "(CONVENTION_PROFILES에 명시 등재하라)"
            )
        elif profile_name not in existing_profiles:
            result.failures.append(
                f"UNRESOLVED: {report_name} -> {profile_name} 이 존재하지 않는다 "
                "(유도 프로필 부재 — 파일 생성 또는 CONVENTION_PROFILES 명시 등재 필요)"
            )
        elif profile_name in result.holders:
            result.failures.append(
                f"FROZEN CONTAMINATED: {profile_name} 이 valuation:을 보유한다 "
                f"(FROZEN 리포트 {report_name})"
            )

    unexpected = result.holders - VALUATION_ALLOWLIST
    missing = VALUATION_ALLOWLIST - result.holders
    result.failures.extend(f"UNEXPECTED HOLDER: {name}" for name in sorted(unexpected))
    result.failures.extend(f"MISSING HOLDER: {name}" for name in sorted(missing))

    print(
        f"SUMMARY: 스캔 {result.scanned}건 / 보유 {len(result.holders)}건 / "
        f"FROZEN 대응 {len(result.frozen_profiles)}건 / 실패 {len(result.failures)}건"
    )
    return result


def _atomic_write(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _make_repo(
    tmp_path: Path,
    *,
    profiles: dict[str, bool],
    reports: list[str],
) -> Path:
    """Build a synthetic forecast root: profiles/ + reports/ only."""

    profiles_dir = tmp_path / "profiles"
    reports_dir = tmp_path / "reports"
    profiles_dir.mkdir()
    reports_dir.mkdir()
    for name, has_valuation in profiles.items():
        text = "company:\n  name: stub\n"
        if has_valuation:
            text += "valuation:\n  fair_value_elasticity: 1.2\n"
        _atomic_write(profiles_dir / name, text)
    for name in reports:
        _atomic_write(reports_dir / name, "")
    return tmp_path


def test_real_profiles_match_allowlist_exactly() -> None:
    result = verify_valuation_allowlist()

    assert result.failures == [], "\n".join([*result.failures, REMEDIATION])
    assert result.holders == {"sk_hynix.yaml"}


def test_real_frozen_profiles_carry_no_valuation() -> None:
    result = verify_valuation_allowlist()

    assert not set(result.frozen_profiles.values()) & result.holders, FROZEN_REMEDIATION


def test_real_frozen_reports_all_resolve_to_existing_profiles() -> None:
    result = verify_valuation_allowlist()

    assert len(result.frozen_profiles) == 9
    assert not [failure for failure in result.failures if failure.startswith("UNRESOLVED:")]


def test_contaminated_frozen_profile_is_rejected(tmp_path: Path) -> None:
    root = _make_repo(
        tmp_path,
        profiles={"sk_hynix.yaml": True, "amd.generic.yaml": True},
        reports=["amd_q2_2026_forecast_FROZEN.md"],
    )

    result = verify_valuation_allowlist(root)

    assert any(
        "FROZEN CONTAMINATED" in failure and "amd.generic.yaml" in failure
        for failure in result.failures
    )


def test_unlisted_profile_with_valuation_is_rejected(tmp_path: Path) -> None:
    root = _make_repo(
        tmp_path,
        profiles={"sk_hynix.yaml": True, "other.yaml": True},
        reports=[],
    )

    result = verify_valuation_allowlist(root)

    assert "UNEXPECTED HOLDER: other.yaml" in result.failures


def test_allowlisted_profile_losing_valuation_is_rejected(tmp_path: Path) -> None:
    root = _make_repo(tmp_path, profiles={"sk_hynix.yaml": False}, reports=[])

    result = verify_valuation_allowlist(root)

    assert "MISSING HOLDER: sk_hynix.yaml" in result.failures


def test_empty_valuation_key_counts_as_holder(tmp_path: Path) -> None:
    root = _make_repo(tmp_path, profiles={"sk_hynix.yaml": False}, reports=[])
    _atomic_write(root / "profiles" / "sk_hynix.yaml", "valuation:\n")

    result = verify_valuation_allowlist(root)

    assert result.holders == {"sk_hynix.yaml"}
    assert result.failures == []


def test_yml_extension_is_scanned(tmp_path: Path) -> None:
    root = _make_repo(
        tmp_path,
        profiles={"sk_hynix.yaml": True, "other.yml": True},
        reports=[],
    )

    result = verify_valuation_allowlist(root)

    assert result.scanned == 2
    assert "UNEXPECTED HOLDER: other.yml" in result.failures


def test_unparseable_profile_is_reported_not_raised(tmp_path: Path) -> None:
    root = _make_repo(
        tmp_path,
        profiles={"sk_hynix.yaml": True, "broken.yaml": False},
        reports=[],
    )
    _atomic_write(root / "profiles" / "broken.yaml", "key: [unterminated\n")

    result = verify_valuation_allowlist(root)

    assert result.scanned == 2
    assert result.holders == {"sk_hynix.yaml"}
    assert any(failure.startswith("UNREADABLE: broken.yaml -") for failure in result.failures)


def test_unresolvable_frozen_report_is_rejected(tmp_path: Path) -> None:
    report_name = "sk_hynix_q2_2026_forecast_FROZEN.md"
    root = _make_repo(
        tmp_path,
        profiles={"sk_hynix.yaml": True},
        reports=[report_name],
    )

    result = verify_valuation_allowlist(root)

    assert result.frozen_profiles == {report_name: None}
    assert any(
        failure.startswith(f"UNRESOLVED: {report_name} - 규약 비대상 파일명")
        for failure in result.failures
    )


def test_underscore_report_does_not_resolve_to_existing_prefix(tmp_path: Path) -> None:
    report_name = "vst_v2_q2_2026_forecast_FROZEN.md"
    root = _make_repo(
        tmp_path,
        profiles={"sk_hynix.yaml": True, "vst.generic.yaml": True, "vst_v2.generic.yaml": False},
        reports=[report_name],
    )

    result = verify_valuation_allowlist(root)

    assert result.frozen_profiles == {report_name: None}
    assert any(failure.startswith("UNRESOLVED:") for failure in result.failures)
    assert not any(failure.startswith("FROZEN CONTAMINATED:") for failure in result.failures)
    assert "UNEXPECTED HOLDER: vst.generic.yaml" in result.failures


def test_explicit_underscore_mapping_resolves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report_name = "vst_v2_q2_2026_forecast_FROZEN.md"
    monkeypatch.setitem(CONVENTION_PROFILES, report_name, "profiles/vst_v2.generic.yaml")
    root = _make_repo(
        tmp_path,
        profiles={"sk_hynix.yaml": True, "vst.generic.yaml": False, "vst_v2.generic.yaml": False},
        reports=[report_name],
    )

    result = verify_valuation_allowlist(root)

    assert result.frozen_profiles == {report_name: "vst_v2.generic.yaml"}
    assert result.failures == []


@pytest.mark.parametrize("period", ["q2_2026", "fy2026q4"])
def test_single_token_report_resolves_by_convention(tmp_path: Path, period: str) -> None:
    report_name = f"abc123_{period}_forecast_FROZEN.md"
    root = _make_repo(
        tmp_path,
        profiles={"sk_hynix.yaml": True, "abc123.generic.yaml": False},
        reports=[report_name],
    )

    result = verify_valuation_allowlist(root)

    assert result.frozen_profiles == {report_name: "abc123.generic.yaml"}
    assert result.failures == []


def test_missing_derived_profile_is_rejected(tmp_path: Path) -> None:
    report_name = "absent_q2_2026_forecast_FROZEN.md"
    root = _make_repo(tmp_path, profiles={"sk_hynix.yaml": True}, reports=[report_name])

    result = verify_valuation_allowlist(root)

    assert result.frozen_profiles == {report_name: "absent.generic.yaml"}
    assert any(
        failure.startswith(f"UNRESOLVED: {report_name} -> absent.generic.yaml")
        and "유도 프로필 부재" in failure
        for failure in result.failures
    )


@pytest.mark.parametrize(
    "report_name",
    [
        "vst_q2_2026_FROZEN.md",
        "vst_2026_forecast_FROZEN.md",
        "vst_h1_2026_forecast_FROZEN.md",
        "vst_q5_2026_forecast_FROZEN.md",
        "VST_q2_2026_forecast_FROZEN.md",
        "vst.a_q2_2026_forecast_FROZEN.md",
    ],
)
def test_nonconforming_report_is_rejected(tmp_path: Path, report_name: str) -> None:
    root = _make_repo(
        tmp_path,
        profiles={"sk_hynix.yaml": True, "vst.generic.yaml": False},
        reports=[report_name],
    )

    result = verify_valuation_allowlist(root)

    assert result.frozen_profiles == {report_name: None}
    assert any(
        failure.startswith(f"UNRESOLVED: {report_name} - 규약 비대상 파일명")
        for failure in result.failures
    )
