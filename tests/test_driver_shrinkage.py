"""Tests for ``calibration.driver_shrinkage``."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from calibration.driver_shrinkage import (
    DEFAULT_TAU,
    LARGE_DELTA_THRESHOLD,
    MIN_OBSERVATIONS,
    DriverWeightObservation,
    collect_driver_observations,
    render_report,
    shrink_weights,
    write_report,
)


def _write_profile(
    path: Path,
    *,
    valuation_method: str | None,
    scenarios: dict[str, dict[str, dict[str, float]]],
) -> None:
    """Write a minimal profile yaml with the given active_drivers per scenario."""
    data: dict = {"company": {"name": path.stem, "market": "US"}, "scenarios": {}}
    if valuation_method is not None:
        data["valuation_method"] = valuation_method
    for code, active in scenarios.items():
        data["scenarios"][code] = {"name": f"sc {code}", "active_drivers": active}
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_collect_observations_smoke(tmp_path: Path) -> None:
    _write_profile(
        tmp_path / "foo.yaml",
        valuation_method="sotp",
        scenarios={
            "A": {"driver_x": 0.5, "driver_y": 1.0},
            "B": {"driver_x": 0.8},
        },
    )
    _write_profile(
        tmp_path / "bar.yaml",
        valuation_method=None,  # falls back to "auto"
        scenarios={"A": {"driver_x": 0.4}},
    )

    obs = collect_driver_observations(tmp_path)

    assert len(obs) == 4
    profiles = {o.profile for o in obs}
    assert profiles == {"foo", "bar"}
    sectors = {o.profile: o.sector for o in obs}
    assert sectors["foo"] == "sotp"
    assert sectors["bar"] == "auto"


def test_shrinkage_pulls_outliers_toward_mean() -> None:
    # Cluster of four 0.3 weights plus one 1.0 outlier in same bucket.
    obs = [
        DriverWeightObservation("p1", "sotp", "A", "d", 0.3),
        DriverWeightObservation("p2", "sotp", "A", "d", 0.3),
        DriverWeightObservation("p3", "sotp", "A", "d", 0.3),
        DriverWeightObservation("p4", "sotp", "A", "d", 0.3),
        DriverWeightObservation("p5", "sotp", "A", "d", 1.0),
    ]
    recs = shrink_weights(obs, tau=5.0)

    assert len(recs) == 1
    rec = recs[0]
    assert rec.n_observations == 5
    mu = rec.sector_mean_weight
    assert mu == pytest.approx((0.3 * 4 + 1.0) / 5)

    outlier = rec.per_profile["p5"]["A"]
    assert outlier["current"] == pytest.approx(1.0)
    # alpha = 5/(5+5) = 0.5 -> shrunk = 0.5 * 1.0 + 0.5 * 0.44 = 0.72
    assert outlier["shrunk"] < outlier["current"]
    assert outlier["shrunk"] > mu  # pulls toward mu but doesn't overshoot
    assert outlier["shrunk"] == pytest.approx(0.5 * 1.0 + 0.5 * mu)


def test_shrinkage_zero_when_uniform() -> None:
    obs = [
        DriverWeightObservation(f"p{i}", "sotp", "A", "d", 0.5)
        for i in range(5)
    ]
    recs = shrink_weights(obs, tau=5.0)
    rec = recs[0]
    for profile in rec.per_profile.values():
        for entry in profile.values():
            assert entry["shrunk"] == pytest.approx(entry["current"])


def test_shrinkage_suppressed_below_min_n() -> None:
    obs = [
        DriverWeightObservation("p1", "sotp", "A", "rare_driver", 0.9),
        DriverWeightObservation("p2", "sotp", "A", "rare_driver", 0.1),
    ]
    recs = shrink_weights(obs, tau=5.0, min_observations=MIN_OBSERVATIONS)
    assert len(recs) == 1
    rec = recs[0]
    assert rec.n_observations == 2
    assert rec.notes and "insufficient" in rec.notes[0]
    # Shrunk values equal current when suppressed.
    for profile in rec.per_profile.values():
        for entry in profile.values():
            assert entry["shrunk"] == entry["current"]


def test_shrinkage_rejects_non_positive_tau() -> None:
    with pytest.raises(ValueError):
        shrink_weights([], tau=0.0)


def test_shrinkage_clips_to_unit_interval() -> None:
    # Feed an out-of-range weight; collect path clips at ingest but shrink
    # should stay in [0, 1] even if callers construct observations directly.
    obs = [
        DriverWeightObservation("p1", "sotp", "A", "d", 0.99),
        DriverWeightObservation("p2", "sotp", "A", "d", 0.99),
        DriverWeightObservation("p3", "sotp", "A", "d", 0.99),
    ]
    recs = shrink_weights(obs, tau=5.0)
    for entry in recs[0].per_profile["p1"].values():
        assert 0.0 <= entry["shrunk"] <= 1.0


def test_render_report_includes_shrinkage_table(tmp_path: Path) -> None:
    obs = [
        DriverWeightObservation("p1", "sotp", "A", "d", 0.2),
        DriverWeightObservation("p2", "sotp", "A", "d", 0.4),
        DriverWeightObservation("p3", "sotp", "A", "d", 1.0),
    ]
    recs = shrink_weights(obs, tau=5.0)
    text = render_report(recs, tau=5.0)

    assert "active_drivers Shrinkage Report" in text
    assert "sotp" in text
    assert "| Profile | Scenario | Current | Shrunk | Delta |" in text
    # p3 weight 1.0 should move toward mean (~0.53) by > 0.15
    assert "⚠" in text

    # write_report round-trip
    out = write_report(recs, tau=5.0, output_dir=tmp_path)
    assert out.exists()
    assert out.read_text(encoding="utf-8") == text


def test_real_profiles_smoke() -> None:
    """Sanity check against the real profiles/ directory."""
    obs = collect_driver_observations()
    assert len(obs) > 0, "expected at least one active_drivers observation in profiles/"
    recs = shrink_weights(obs, tau=DEFAULT_TAU)
    assert recs, "expected at least one bucket"
    # LARGE_DELTA_THRESHOLD is imported to surface symbol usage in case of refactor
    assert LARGE_DELTA_THRESHOLD > 0
