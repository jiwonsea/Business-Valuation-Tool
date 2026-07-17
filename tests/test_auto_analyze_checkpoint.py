from pathlib import Path

import pytest
import yaml

from schemas.models import ValidationError, ValidationReport


def _failed_report(status="fail"):
    return ValidationReport(
        status=status,
        retryable=True,
        errors=[
            ValidationError(
                path="scenarios.Bull",
                code="ev_spread_too_low",
                message="spread",
            )
        ],
    )


def _raw():
    return {
        "draft": False,
        "generated": "manual",
        "curated": True,
        "peers": [{"name": "PeerCo"}],
        "scenarios": {"Bull": {}, "Base": {}, "Bear": {}},
    }


def test_repair_failure_preserves_peer_checkpoint(monkeypatch, tmp_path, caplog):
    from pipeline import profile_generator as pg

    path = tmp_path / "company.yaml"
    raw = _raw()
    pg._write_enrichment_checkpoint(str(path), raw)
    monkeypatch.setattr(
        pg,
        "_repair_scenarios_with_llm",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("secret response")),
    )

    report = pg._repair_scenarios_safely(None, raw, _failed_report(), "dcf")
    saved = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert saved["peers"] == [{"name": "PeerCo"}]
    assert saved["draft"] is True
    assert saved["scenario_validation"] == {"status": "pending"}
    assert report.status == "fail"
    assert report.retryable is False
    assert report.retry_attempts == 1
    assert report.errors[0].code == "ev_spread_too_low"
    assert "secret response" not in caplog.text


def test_second_write_failure_leaves_valid_checkpoint(monkeypatch, tmp_path):
    from pipeline import profile_generator as pg

    path = tmp_path / "company.yaml"
    raw = _raw()
    pg._write_enrichment_checkpoint(str(path), raw)
    monkeypatch.setattr(
        pg,
        "_atomic_write_yaml",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )

    with pytest.raises(OSError, match="disk full"):
        pg._atomic_write_yaml(str(path), raw)

    saved = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert saved["draft"] is True
    assert saved["peers"]


def test_checkpoint_is_overwriteable_on_rerun(tmp_path):
    from pipeline import profile_generator as pg

    path = tmp_path / "company.yaml"
    pg._write_enrichment_checkpoint(str(path), _raw())

    assert pg._profile_is_protected(Path(path)) is False


@pytest.mark.parametrize("status", ["fail", "warning", "skipped"])
def test_non_ok_validation_remains_draft(status):
    from pipeline.profile_generator import _is_enrichment_draft

    assert _is_enrichment_draft([1], [1], {"Base": {}}, _failed_report(status))


def test_ok_validation_can_clear_draft():
    from pipeline.profile_generator import _is_enrichment_draft

    report = ValidationReport(status="ok")
    assert not _is_enrichment_draft([1], [1], {"Base": {}}, report)
