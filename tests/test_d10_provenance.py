import ast
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.d10_measure_elasticity import (
    collect_provenance,
    input_blob_shas,
    resolve_commit,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "profiles/example.yaml"


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], encoding="utf-8", stderr=subprocess.PIPE
    ).strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init")
    git(tmp_path, "config", "user.name", "Provenance Test")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "core.autocrlf", "true")
    git(tmp_path, "config", "commit.gpgsign", "false")
    for name in (PROFILE, "engine/dcf.py", "engine/wacc.py"):
        target = tmp_path / name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(b"value: 1\r\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "fixture")
    return tmp_path


def test_historical_hynix_record_matches_commit_blobs():
    # Read committed provenance, not an AI-regenerated working profile.
    raw = git(ROOT, "show", "HEAD:forecast/profiles/sk_hynix.yaml")
    record = yaml.safe_load(raw)["valuation"]["elasticity_provenance"]
    if git(ROOT, "rev-parse", "--is-shallow-repository") == "true":
        pytest.skip("Historical provenance requires full Git history; no network fetch")
    commit = resolve_commit(ROOT, record["bvt_commit"])
    assert len(commit) == 40
    assert commit.startswith(record["bvt_commit"])
    assert input_blob_shas(ROOT, commit, record["bvt_profile"]) == record["input_sha"]


def test_clean_crlf_inputs_record_head_and_warn_without_remote(repo, caplog):
    result = collect_provenance(repo, PROFILE)
    assert result["bvt_commit"] == git(repo, "rev-parse", "HEAD")
    assert result["input_sha"] == input_blob_shas(repo, result["bvt_commit"], PROFILE)
    assert len(result["input_sha"]["profile"]) == 40
    assert "locally known remote branches" in caplog.text
    assert set(result) == {"bvt_commit", "input_sha"}


def test_local_remote_ref_suppresses_warning_without_network(repo, caplog):
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    collect_provenance(repo, PROFILE)
    assert not caplog.records


@pytest.mark.parametrize("filename", [PROFILE, "engine/dcf.py", "engine/wacc.py"])
@pytest.mark.parametrize("staged", [False, True])
def test_dirty_input_is_rejected(repo, filename, staged):
    (repo / filename).write_bytes(b"changed\r\n")
    if staged:
        git(repo, "add", filename)
    with pytest.raises(ValueError, match="diff"):
        collect_provenance(repo, PROFILE)


def test_unrelated_dirty_file_does_not_block(repo):
    (repo / "notes.txt").write_text("unrelated", encoding="utf-8")
    assert collect_provenance(repo, PROFILE)["bvt_commit"]


def test_input_removed_from_index_is_rejected(repo):
    git(repo, "rm", "--cached", PROFILE)
    with pytest.raises(ValueError, match="ls-files"):
        collect_provenance(repo, PROFILE)


@pytest.mark.parametrize("commit", ["0" * 40, "HEAD", "abc", "--help"])
def test_invalid_or_missing_commit_is_rejected(repo, commit):
    with pytest.raises(ValueError):
        resolve_commit(repo, commit)


@pytest.mark.parametrize("profile", ["profiles/typo.yaml", "../outside", "engine"])
def test_missing_or_invalid_input_path_is_rejected(repo, profile):
    with pytest.raises(ValueError):
        collect_provenance(repo, profile)


def test_historical_lookup_is_independent_of_current_head(repo):
    old = git(repo, "rev-parse", "HEAD")
    before = input_blob_shas(repo, old, PROFILE)
    (repo / PROFILE).write_bytes(b"value: 2\r\n")
    git(repo, "add", PROFILE)
    git(repo, "commit", "-m", "new input")
    assert input_blob_shas(repo, old[:7], PROFILE) == before
    assert collect_provenance(repo, PROFILE)["input_sha"] != before


def test_ac5_measure_imports_only_standard_library():
    tree = ast.parse((ROOT / "scripts/d10_measure_elasticity.py").read_text("utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            imports.add(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "__import__"
    # All direct dependencies are standard library, so no transitive local
    # dependency can introduce forecast imports either.
    assert imports <= {"logging", "re", "subprocess", "pathlib"}
