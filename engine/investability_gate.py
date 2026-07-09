"""Investability validation gate — the safety spine for auto-generated profiles.

Item 3 (2026-07). Auto-curation (discovery + profile_generator + LLM fill) is
judgment-heavy; bad curation yields confidently-wrong valuations. This gate is
what makes automation SAFE: an auto-produced profile is "investable" only if it
passes every BLOCKING check below. On any failure the profile stays / is marked
``draft: true`` → the existing draft guard in the orchestrator's fundamentals
adapter forces stance neutral / conviction low → the decision ABSTAINS. So an
unvalidated auto-curated name can never produce a confident trade.

The gate is PURE (no IO, no fetch, no LLM): it scores already-computed values so
it is deterministic and unit-testable. Fetching/curation and the adversarial
Codex review happen around it, not inside it.

Blocking checks (all must pass):
  1. dcf_vs_peer      — DCF / peer-median value ratio ∈ [0.7, 1.5]. A DCF that is
                        far from the market's peer multiples is unreconciled; we
                        cannot claim conviction. Missing peer comp is a block, not
                        a pass (nothing to cross-check against).
  2. quality_grade    — engine quality grade must be >= C (A/B/C ok; D/F block).
  3. segments_reconcile — when segment revenues are present they must sum to the
                        consolidated revenue within tolerance (default 5%). A
                        SOTP method with no segments is a block.
  4. no_placeholder_multiples — no multiple left at its auto-generated placeholder
                        (e.g. the 10.0 "TODO: Set appropriate multiple" default).
  5. no_todo_markers  — no TODO / "auto-generated draft profile" markers remain in
                        the profile text.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Spec thresholds (Item 3).
DCF_PEER_LOW = 0.7
DCF_PEER_HIGH = 1.5
MIN_GRADE = "C"
SEGMENT_RECONCILE_TOL = 0.05  # |sum(segments) - consolidated| / consolidated
_GRADE_ORDER = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
_TODO_PATTERNS = ("todo", "auto-generated draft profile", "fixme", "placeholder")


@dataclass(frozen=True)
class GateFinding:
    """One check's outcome. ``severity`` block => failing it forces draft."""

    check: str
    passed: bool
    severity: str  # "block" | "warn"
    detail: str


@dataclass(frozen=True)
class InvestabilityReport:
    investable: bool
    draft: bool  # True when not investable -> caller sets profile draft: true
    findings: list[GateFinding] = field(default_factory=list)

    @property
    def blockers(self) -> list[str]:
        return [f.detail for f in self.findings if f.severity == "block" and not f.passed]


@dataclass(frozen=True)
class GateInputs:
    """Already-computed values the gate scores. Populated by a fetch/curate step
    (or ``gate_inputs_from_profile`` below); the gate itself never fetches."""

    dcf_value: float | None
    peer_median_value: float | None
    quality_grade: str | None
    method: str = "dcf"
    segment_revenues: list[float] = field(default_factory=list)
    consolidated_revenue: float | None = None
    placeholder_multiples: list[str] = field(default_factory=list)
    text: str = ""
    optionality_flag: bool = False


def _check_dcf_vs_peer(
    dcf: float | None,
    peer_median: float | None,
    *,
    optionality_flag: bool = False,
) -> GateFinding:
    if dcf is None:
        return GateFinding(
            "dcf_vs_peer", False, "block",
            "no DCF value to cross-check against peer median (cannot confirm value)",
        )
    if peer_median is None or peer_median <= 0:
        return GateFinding(
            "dcf_vs_peer", False, "block",
            "no peer-median comp to cross-check DCF (cannot confirm value)",
        )
    ratio = dcf / peer_median
    ok = DCF_PEER_LOW <= ratio <= DCF_PEER_HIGH
    return GateFinding(
        "dcf_vs_peer", ok, "block",
        f"DCF/peer-median = {ratio:.2f} (need [{DCF_PEER_LOW}, {DCF_PEER_HIGH}]"
        + (", optionality not auto-widened" if optionality_flag else "")
        + ")",
    )


def _check_quality_grade(grade: str | None) -> GateFinding:
    rank = _GRADE_ORDER.get((grade or "").strip().upper())
    ok = rank is not None and rank >= _GRADE_ORDER[MIN_GRADE]
    return GateFinding(
        "quality_grade", bool(ok), "block",
        f"quality grade {grade!r} (need >= {MIN_GRADE})",
    )


def _check_segments_reconcile(
    method: str, segment_revenues: list[float], consolidated: float | None
) -> GateFinding:
    if not segment_revenues:
        if method.lower().startswith("sotp"):
            return GateFinding(
                "segments_reconcile", False, "block",
                "SOTP method but no segment revenues provided",
            )
        return GateFinding(
            "segments_reconcile", True, "block", "no segments to reconcile (non-SOTP)",
        )
    if not consolidated or consolidated <= 0:
        return GateFinding(
            "segments_reconcile", False, "block",
            "segments present but consolidated revenue missing",
        )
    diff = abs(sum(segment_revenues) - consolidated) / consolidated
    ok = diff <= SEGMENT_RECONCILE_TOL
    return GateFinding(
        "segments_reconcile", ok, "block",
        f"segment sum vs consolidated off by {diff:.1%} (tol {SEGMENT_RECONCILE_TOL:.0%})",
    )


def _check_no_placeholder_multiples(placeholders: list[str]) -> GateFinding:
    ok = not placeholders
    return GateFinding(
        "no_placeholder_multiples", ok, "block",
        "placeholder multiples remain: " + ", ".join(placeholders) if placeholders
        else "no placeholder multiples",
    )


def _check_no_todo_markers(text: str) -> GateFinding:
    lowered = (text or "").lower()
    hits = [pat for pat in _TODO_PATTERNS if pat in lowered]
    ok = not hits
    return GateFinding(
        "no_todo_markers", ok, "block",
        "draft/TODO markers present: " + ", ".join(hits) if hits else "no TODO markers",
    )


def evaluate_investability(inputs: GateInputs) -> InvestabilityReport:
    """Run every blocking check. Investable only if all block checks pass."""
    findings = [
        _check_dcf_vs_peer(
            inputs.dcf_value,
            inputs.peer_median_value,
            optionality_flag=inputs.optionality_flag,
        ),
        _check_quality_grade(inputs.quality_grade),
        _check_segments_reconcile(
            inputs.method, inputs.segment_revenues, inputs.consolidated_revenue
        ),
        _check_no_placeholder_multiples(inputs.placeholder_multiples),
        _check_no_todo_markers(inputs.text),
    ]
    investable = all(f.passed for f in findings if f.severity == "block")
    return InvestabilityReport(investable=investable, draft=not investable, findings=findings)


def apply_gate_to_profile(raw: dict, report: InvestabilityReport) -> dict:
    """Return a shallow copy of ``raw`` with ``draft: true`` when not investable.

    Never flips a failing profile back to investable — the gate can only add the
    draft flag, so a downstream curator cannot accidentally clear it here.
    """
    updated = dict(raw)
    if not report.investable:
        updated["draft"] = True
    return updated


# ── best-effort extraction (Codex to align to canonical profile fields) ──
def gate_inputs_from_profile(
    raw: dict,
    *,
    dcf_value: float | None,
    peer_median_value: float | None,
    quality_grade: str | None,
    consolidated_revenue: float | None,
    text: str = "",
) -> GateInputs:
    """Assemble GateInputs from a profile dict + already-computed valuation numbers.

    dcf_value/peer_median_value/quality_grade/consolidated_revenue come from the
    valuation run (BVT), not from this module. Segment revenues and placeholder
    multiples are read structurally from the profile. Placeholder detection: a
    multiple whose value equals the generator default (10.0) AND whose line is
    tagged TODO, OR any multiple explicitly flagged null/None.
    """
    segments_raw = raw.get("segments") or []
    if isinstance(segments_raw, dict):
        segments = [
            {"id": key, **value} if isinstance(value, dict) else {"id": key}
            for key, value in segments_raw.items()
        ]
    else:
        segments = segments_raw
    segment_revenues = [
        float(s["revenue"]) for s in segments
        if isinstance(s, dict) and isinstance(s.get("revenue"), (int, float))
    ]
    placeholders: list[str] = []
    for s in segments:
        if not isinstance(s, dict):
            continue
        mult = s.get("multiple")
        if mult is None:
            placeholders.append(f"{s.get('id', s.get('name', '?'))}.multiple=null")
        elif mult == 10.0 and "todo" in (text or "").lower():
            placeholders.append(f"{s.get('id', s.get('name', '?'))}.multiple=10.0(default)")
    method = str(raw.get("primary_method") or raw.get("method") or "dcf")
    optionality_flag = bool(
        raw.get("optionality_flag")
        or raw.get("has_optionality")
        or any(isinstance(s, dict) and s.get("optionality") for s in segments)
    )
    return GateInputs(
        dcf_value=dcf_value,
        peer_median_value=peer_median_value,
        quality_grade=quality_grade,
        method=method,
        segment_revenues=segment_revenues,
        consolidated_revenue=consolidated_revenue,
        placeholder_multiples=placeholders,
        text=text,
        optionality_flag=optionality_flag,
    )
