"""ValuationConfig validation (Codex follow-up #2).

The valuation section was a raw dict passthrough — a negative elasticity or a typo'd
key would surface as a runtime arithmetic error / silent sign flip. A typed config
(extra=forbid, non-negative bounds) fails loudly at profile load instead.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from pipeline.ir_loader import load_profile
from schemas.models import ValuationConfig

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_defaults() -> None:
    cfg = ValuationConfig()
    assert cfg.fair_value_elasticity == 1.2
    assert cfg.overlay_weight == 1.0


def test_rejects_negative_values() -> None:
    with pytest.raises(ValidationError):
        ValuationConfig(fair_value_elasticity=-0.5)
    with pytest.raises(ValidationError):
        ValuationConfig(overlay_weight=-1.0)


def test_rejects_unknown_key() -> None:
    with pytest.raises(ValidationError):
        ValuationConfig(elasticty=1.2)  # typo -> extra=forbid


def test_ir_loader_returns_validated_config() -> None:
    profile = load_profile(REPO_ROOT / "profiles" / "sk_hynix.yaml")
    cfg = profile["valuation"]
    assert isinstance(cfg, ValuationConfig)
    assert cfg.fair_value_elasticity >= 0.0
    assert cfg.overlay_weight >= 0.0


def test_load_profile_rejects_malformed_valuation_yaml(tmp_path) -> None:
    """A bad valuation: block in a real profile must fail at load_profile().

    Pins the requirement at the loader boundary (not just the model), per the
    Codex re-eval recommendation: negative elasticity and unknown keys both raise
    ValidationError when fed through the actual profile loader.
    """
    full = load_profile(REPO_ROOT / "profiles" / "sk_hynix.yaml")

    negative = copy.deepcopy(full["raw"])
    negative["valuation"] = {"fair_value_elasticity": -0.5, "overlay_weight": 1.0}
    neg_path = tmp_path / "negative_elasticity.yaml"
    neg_path.write_text(yaml.safe_dump(negative, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_profile(neg_path)

    typo = copy.deepcopy(full["raw"])
    typo["valuation"] = {"elasticty": 1.2}  # unknown key -> extra=forbid
    typo_path = tmp_path / "typo_key.yaml"
    typo_path.write_text(yaml.safe_dump(typo, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_profile(typo_path)
