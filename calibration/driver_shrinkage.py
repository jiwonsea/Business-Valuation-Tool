"""James-Stein-style shrinkage recommender for ``active_drivers`` weights.

Hand-tuned ``active_drivers`` weights across ``profiles/*.yaml`` carry a lot
of idiosyncratic noise. This module pools observations by (sector, driver_id)
and pulls each weight toward the sector mean by an amount controlled by
``tau`` (prior strength). Recommendations are written to markdown; YAML
profiles are never modified automatically.

Sector key: the profile's explicit ``valuation_method`` field when present,
otherwise ``"auto"``. This is a static proxy -- running ``method_selector``
would require loading full inputs. The label is stable enough for pooling
once each profile's method settles in the weekly pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_PROFILES_DIR: Path = PROJECT_ROOT / "profiles"
DEFAULT_REPORT_DIR: Path = PROJECT_ROOT / "output" / "calibration"

DEFAULT_TAU: float = 5.0
MIN_OBSERVATIONS: int = 3
MIN_PROFILES: int = 2
LARGE_DELTA_THRESHOLD: float = 0.15

# Profiles that are hand-crafted test fixtures or not subject to the weekly
# pipeline's active_drivers generation -- exclude from pooling.
_EXCLUDED_PROFILES: frozenset[str] = frozenset(
    {"_template", "multiples_test", "nav_test", "kb_financial_rim"}
)


@dataclass(frozen=True)
class DriverWeightObservation:
    """Single (profile, sector, scenario, driver_id, weight) datum."""

    profile: str
    sector: str
    scenario_code: str
    driver_id: str
    weight: float


@dataclass
class DriverShrinkageRec:
    """Shrinkage recommendation for one (sector, driver_id) bucket."""

    sector: str
    driver_id: str
    n_observations: int
    n_profiles: int
    sector_mean_weight: float
    sector_std_weight: float | None
    # {profile: {scenario_code: {"current": w, "shrunk": w_hat}}}
    per_profile: dict[str, dict[str, dict[str, float]]]
    tau: float
    eligible: bool  # True only when n_obs >= min_obs AND n_profiles >= min_profiles
    notes: list[str] = field(default_factory=list)


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _sector_key(profile_data: dict[str, Any]) -> str:
    method = profile_data.get("valuation_method")
    if isinstance(method, str) and method.strip():
        return method.strip().lower()
    return "auto"


def collect_driver_observations(
    profiles_dir: Path | None = None,
) -> list[DriverWeightObservation]:
    """Walk ``profiles/*.yaml`` and extract every active_drivers weight."""
    profiles_dir = profiles_dir or DEFAULT_PROFILES_DIR
    observations: list[DriverWeightObservation] = []

    for path in sorted(profiles_dir.glob("*.yaml")):
        if path.stem in _EXCLUDED_PROFILES:
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping %s: failed to parse (%s)", path.name, exc)
            continue
        if not isinstance(data, dict):
            continue
        sector = _sector_key(data)
        scenarios = data.get("scenarios") or {}
        if not isinstance(scenarios, dict):
            continue
        for sc_code, sc in scenarios.items():
            if not isinstance(sc, dict):
                continue
            active = sc.get("active_drivers") or {}
            if not isinstance(active, dict):
                continue
            for driver_id, weight in active.items():
                if not isinstance(weight, (int, float)):
                    continue
                observations.append(
                    DriverWeightObservation(
                        profile=path.stem,
                        sector=sector,
                        scenario_code=str(sc_code),
                        driver_id=str(driver_id),
                        weight=_clip01(weight),
                    )
                )
    return observations


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def _std(xs: list[float], mu: float) -> float | None:
    if len(xs) < 2:
        return None
    variance = sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)
    return variance ** 0.5


def shrink_weights(
    observations: list[DriverWeightObservation],
    *,
    tau: float = DEFAULT_TAU,
    min_observations: int = MIN_OBSERVATIONS,
    min_profiles: int = MIN_PROFILES,
) -> list[DriverShrinkageRec]:
    """Shrink each weight toward its (sector, driver_id) bucket mean.

    For each observation ``w_i`` in a bucket with ``n`` observations and
    mean ``mu``, the shrunk estimate is::

        alpha = tau / (tau + n)
        w_hat = (1 - alpha) * w_i + alpha * mu

    Larger ``tau`` or smaller ``n`` pulls harder toward ``mu``. A bucket is
    eligible only when both ``n_observations >= min_observations`` AND
    ``n_profiles >= min_profiles``. Single-profile buckets (observations all
    come from one profile's scenarios) are suppressed because the spread
    across bull/base/bear is intentional scenario differentiation, not noise.
    """
    if tau <= 0:
        raise ValueError("tau must be positive")

    buckets: dict[tuple[str, str], list[DriverWeightObservation]] = {}
    for obs in observations:
        buckets.setdefault((obs.sector, obs.driver_id), []).append(obs)

    recs: list[DriverShrinkageRec] = []
    for (sector, driver_id), bucket in sorted(buckets.items()):
        weights = [o.weight for o in bucket]
        n = len(weights)
        distinct_profiles = {o.profile for o in bucket}
        n_profiles = len(distinct_profiles)
        mu = _mean(weights)
        std = _std(weights, mu)
        notes: list[str] = []
        per_profile: dict[str, dict[str, dict[str, float]]] = {}

        eligible = n >= min_observations and n_profiles >= min_profiles
        if not eligible:
            if n < min_observations:
                notes.append(
                    f"insufficient observations (n={n} < min={min_observations})."
                )
            if n_profiles < min_profiles:
                notes.append(
                    f"single-profile bucket (n_profiles={n_profiles} < "
                    f"min={min_profiles}); scenario spread is intentional, "
                    "shrinkage would wash out bull/bear differentiation."
                )
            for obs in bucket:
                per_profile.setdefault(obs.profile, {})[obs.scenario_code] = {
                    "current": obs.weight,
                    "shrunk": obs.weight,
                }
            recs.append(
                DriverShrinkageRec(
                    sector=sector,
                    driver_id=driver_id,
                    n_observations=n,
                    n_profiles=n_profiles,
                    sector_mean_weight=mu,
                    sector_std_weight=std,
                    per_profile=per_profile,
                    tau=tau,
                    eligible=False,
                    notes=notes,
                )
            )
            continue

        alpha = tau / (tau + n)
        for obs in bucket:
            shrunk = _clip01((1 - alpha) * obs.weight + alpha * mu)
            per_profile.setdefault(obs.profile, {})[obs.scenario_code] = {
                "current": obs.weight,
                "shrunk": shrunk,
            }
            if abs(shrunk - obs.weight) >= LARGE_DELTA_THRESHOLD:
                notes.append(
                    f"{obs.profile}:{obs.scenario_code} delta "
                    f"{shrunk - obs.weight:+.3f} (|delta| >= "
                    f"{LARGE_DELTA_THRESHOLD})"
                )

        recs.append(
            DriverShrinkageRec(
                sector=sector,
                driver_id=driver_id,
                n_observations=n,
                n_profiles=n_profiles,
                sector_mean_weight=mu,
                sector_std_weight=std,
                per_profile=per_profile,
                tau=tau,
                eligible=True,
                notes=notes,
            )
        )
    return recs


def _fmt(value: float | None, spec: str = ".3f") -> str:
    if value is None:
        return "n/a"
    return format(value, spec)


def render_report(
    recs: list[DriverShrinkageRec],
    *,
    tau: float = DEFAULT_TAU,
    report_date: date | None = None,
) -> str:
    """Render shrinkage recommendations as markdown."""
    report_date = report_date or date.today()
    lines: list[str] = []
    lines.append(f"# active_drivers Shrinkage Report -- {report_date.isoformat()}")
    lines.append("")
    lines.append(
        f"Prior strength `tau` = **{tau:.2f}** (tunable). "
        f"Eligibility: **n_obs >= {MIN_OBSERVATIONS}** AND "
        f"**n_profiles >= {MIN_PROFILES}**. "
        f"Large-delta flag threshold: **{LARGE_DELTA_THRESHOLD}**."
    )
    lines.append("")
    lines.append(
        "Recommendations are advisory. `profiles/*.yaml` is never modified "
        "automatically -- review and apply manually."
    )
    lines.append("")

    if not recs:
        lines.append("_No observations collected -- profiles/ is empty or no "
                     "active_drivers defined._")
        return "\n".join(lines) + "\n"

    lines.append("## Bucket summary")
    lines.append("")
    lines.append(
        "| Sector | Driver | N obs | N profiles | Sector mean | "
        "Sector std | Status |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---|")
    for rec in recs:
        if rec.eligible:
            status = "ok"
        elif rec.n_profiles < MIN_PROFILES:
            status = "single-profile"
        else:
            status = "insufficient"
        lines.append(
            f"| {rec.sector} | {rec.driver_id} | {rec.n_observations} | "
            f"{rec.n_profiles} | {_fmt(rec.sector_mean_weight)} | "
            f"{_fmt(rec.sector_std_weight)} | {status} |"
        )
    lines.append("")

    lines.append("## Per-profile recommendations")
    lines.append("")
    for rec in recs:
        if not rec.eligible:
            continue
        lines.append(f"### {rec.sector} / {rec.driver_id}")
        lines.append("")
        lines.append(
            f"mu = {_fmt(rec.sector_mean_weight)}, "
            f"sigma = {_fmt(rec.sector_std_weight)}, "
            f"n_obs = {rec.n_observations}, "
            f"n_profiles = {rec.n_profiles}"
        )
        lines.append("")
        lines.append("| Profile | Scenario | Current | Shrunk | Delta |")
        lines.append("|---|---|---:|---:|---:|")
        for profile in sorted(rec.per_profile):
            for scenario in sorted(rec.per_profile[profile]):
                entry = rec.per_profile[profile][scenario]
                delta = entry["shrunk"] - entry["current"]
                flag = " ⚠" if abs(delta) >= LARGE_DELTA_THRESHOLD else ""
                lines.append(
                    f"| {profile} | {scenario} | {entry['current']:.3f} | "
                    f"{entry['shrunk']:.3f} | {delta:+.3f}{flag} |"
                )
        if rec.notes:
            lines.append("")
            lines.append("Notes:")
            for note in rec.notes:
                lines.append(f"- {note}")
        lines.append("")

    single_profile = [
        r for r in recs
        if not r.eligible and r.n_profiles < MIN_PROFILES
    ]
    if single_profile:
        lines.append("## Suppressed: single-profile buckets")
        lines.append("")
        lines.append(
            "Scenario spread within one profile (bull/base/bear weights) is "
            "designer intent, not noise. Shrinkage would wash out the "
            "differentiation, so these are excluded from recommendations."
        )
        lines.append("")
        for rec in single_profile:
            profiles = ", ".join(sorted(rec.per_profile))
            lines.append(
                f"- **{rec.sector} / {rec.driver_id}** "
                f"(n_obs={rec.n_observations}, n_profiles={rec.n_profiles}): "
                f"{profiles}"
            )
        lines.append("")

    insufficient = [
        r for r in recs
        if not r.eligible
        and r.n_profiles >= MIN_PROFILES
        and r.n_observations < MIN_OBSERVATIONS
    ]
    if insufficient:
        lines.append("## Suppressed: insufficient observations")
        lines.append("")
        for rec in insufficient:
            profiles = ", ".join(sorted(rec.per_profile))
            lines.append(
                f"- **{rec.sector} / {rec.driver_id}** "
                f"(n_obs={rec.n_observations}, n_profiles={rec.n_profiles}): "
                f"{profiles}"
            )
        lines.append("")

    lines.append("## How to read")
    lines.append(
        "- Sector key is the profile's `valuation_method` field; `auto` covers "
        "profiles without an explicit method override. This axis is a proxy "
        "and will be replaced by a proper business-sector taxonomy once a "
        "scenario-role-aware redesign lands.\n"
        "- Shrinkage pulls each weight toward its (sector, driver) mean by "
        "`alpha = tau / (tau + n)`. Increase `tau` to pull harder.\n"
        "- Single-profile buckets are suppressed: cross-scenario weights "
        "within one profile are intentional bull/base/bear differentiation.\n"
        f"- `⚠` marks moves of at least {LARGE_DELTA_THRESHOLD:.2f} in "
        "absolute weight -- review before applying."
    )
    return "\n".join(lines) + "\n"


def write_report(
    recs: list[DriverShrinkageRec],
    *,
    tau: float = DEFAULT_TAU,
    output_dir: Path | None = None,
    report_date: date | None = None,
) -> Path:
    """Render and write the shrinkage report to ``output/calibration/``."""
    report_date = report_date or date.today()
    output_dir = output_dir or DEFAULT_REPORT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    text = render_report(recs, tau=tau, report_date=report_date)
    out_path = output_dir / f"driver_shrinkage_{report_date.isoformat()}.md"
    out_path.write_text(text, encoding="utf-8")
    logger.info(
        "Wrote driver shrinkage report: %s (%d buckets)", out_path, len(recs)
    )
    return out_path


def main() -> None:
    """Entry point for ``python -m calibration.driver_shrinkage``."""
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="active_drivers shrinkage recommender")
    parser.add_argument("--tau", type=float, default=DEFAULT_TAU,
                        help="prior strength (default: 5.0)")
    parser.add_argument("--profiles-dir", type=Path, default=None,
                        help="override profiles directory")
    parser.add_argument("--no-report", action="store_true",
                        help="skip writing markdown report")
    args = parser.parse_args()

    observations = collect_driver_observations(args.profiles_dir)
    recs = shrink_weights(observations, tau=args.tau)
    print(
        f"[DriverShrinkage] observations={len(observations)} "
        f"buckets={len(recs)} tau={args.tau}"
    )
    eligible = sum(1 for r in recs if r.eligible)
    single = sum(1 for r in recs if not r.eligible and r.n_profiles < MIN_PROFILES)
    print(
        f"[DriverShrinkage] eligible buckets: {eligible}, "
        f"single-profile suppressed: {single}"
    )
    if not args.no_report:
        out = write_report(recs, tau=args.tau)
        print(f"[DriverShrinkage] Report -> {out}")


if __name__ == "__main__":
    main()
