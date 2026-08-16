"""Score TSLA Q2 2026 actuals against the immutable FROZEN forecast."""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import tempfile
from pathlib import Path

import yaml

from engine.generic_postmortem import score_generic_release
from engine.scoring_basis import compare_bases, format_gap_of_gap
from schemas.postmortem import FrozenPoint, GenericActualRelease, GenericPostmortemResult

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
FROZEN_PATH = REPO_ROOT / "reports" / "tsla_q2_2026_forecast_FROZEN.md"
HANDOFF_PATH = REPO_ROOT / "HANDOFF_CODEX_efe_q2_2026_tsla.md"
FROZEN_SHA256 = "10d1dca61074b0661dec52b5cc134addf17fc44ea501975ee253407b5cf291ff"
START_MARKER = "<!-- TSLA_Q2_2026_POSTMORTEM_START -->"
END_MARKER = "<!-- TSLA_Q2_2026_POSTMORTEM_END -->"

# One-time transcription from reports/tsla_q2_2026_forecast_FROZEN.md.
FROZEN_ANCHOR = {
    "unit_scale": 1_000_000.0,
    "prior_actual": {"revenue_total": 22_387.0, "eps_diluted": 0.1348},
    "scenarios": {
        "bear": {"revenue_total": 25_521.0, "operating_income": 893.0, "net_income": 523.0, "eps_diluted": 0.15, "diluted_shares": 3_538_000_000.0},
        "base": {"revenue_total": 26_864.0, "operating_income": 1_612.0, "net_income": 1_370.0, "eps_diluted": 0.39, "diluted_shares": 3_538_000_000.0},
        "bull": {"revenue_total": 27_984.0, "operating_income": 2_798.0, "net_income": 2_800.0, "eps_diluted": 0.79, "diluted_shares": 3_538_000_000.0},
    },
    "weighted": {"revenue_total": 26_808.0, "operating_income": 1_729.0, "net_income": 1_516.0, "eps_diluted": 0.43, "diluted_shares": 3_538_000_000.0},
    "consensus": {
        "ir": {"revenue_total": 27_580.0, "gaap_eps": 0.36, "non_gaap_eps": 0.55},
        "estimize": {"revenue_total": 26_400.0, "non_gaap_eps": 0.55},
    },
    "segments": {"automotive": 20_050.0, "energy": 3_770.0, "services": 3_760.0},
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_actual(path: Path) -> GenericActualRelease:
    """Load a UTF-8 YAML actual input into the strict schema."""
    return GenericActualRelease.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8"))
    )


def score_tsla(actual: GenericActualRelease) -> GenericPostmortemResult:
    """Score TSLA actuals using only the transcribed FROZEN anchor."""
    return score_generic_release(
        actual=actual,
        base=FrozenPoint.model_validate(FROZEN_ANCHOR["scenarios"]["base"]),
        weighted=FrozenPoint.model_validate(FROZEN_ANCHOR["weighted"]),
        prior_revenue=FROZEN_ANCHOR["prior_actual"]["revenue_total"],
        prior_eps=FROZEN_ANCHOR["prior_actual"]["eps_diluted"],
        consensus_eps=FROZEN_ANCHOR["consensus"]["ir"]["gaap_eps"],
        unit_scale=FROZEN_ANCHOR["unit_scale"],
        segment_forecasts=FROZEN_ANCHOR["segments"],
        include_tesla=True,
    )


def _pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:+.1f}%"


def _number(value: float | None, digits: int = 1) -> str:
    return "N/A" if value is None else f"{value:,.{digits}f}"


def _surprise_direction(
    model_eps: float,
    actual_eps: float,
    consensus_eps: float,
) -> tuple[str, float, float]:
    """Classify the model's EPS surprise call and retain both signed gaps."""
    model_gap = model_eps - consensus_eps
    actual_gap = actual_eps - consensus_eps
    if actual_gap == 0.0:
        status = "NO-SURPRISE"
    elif (model_gap > 0.0) == (actual_gap > 0.0) and model_gap != 0.0:
        status = "HIT"
    else:
        status = "MISS"
    return status, model_gap, actual_gap


def render_postmortem(result: GenericPostmortemResult) -> str:
    """Render the append-only TSLA postmortem Markdown block."""
    attr = result.attribution
    skill = result.skill
    tesla = result.tesla
    assert tesla is not None
    surprise_status, model_surprise, actual_surprise = _surprise_direction(
        result.eps_weighted.forecast,
        result.eps_weighted.actual,
        FROZEN_ANCHOR["consensus"]["ir"]["gaap_eps"],
    )
    basis_comparison = compare_bases(
        base={"revenue": result.revenue_base.forecast, "eps": result.eps_base.forecast},
        weighted={"revenue": result.revenue_weighted.forecast, "eps": result.eps_weighted.forecast},
        actual={"revenue": result.revenue_base.actual, "eps": result.eps_base.actual},
        consensus={
            "revenue": FROZEN_ANCHOR["consensus"]["ir"]["revenue_total"],
            "eps": FROZEN_ANCHOR["consensus"]["ir"]["gaap_eps"],
        },
    )
    lines = [
        START_MARKER,
        "### TSLA Q2 2026 사후 채점",
        "",
        "> **사후 귀인 — 예측 신호 아님.**",
        "",
        f"- 출처: {result.provenance.source} (as-of {result.provenance.as_of})",
        f"- 매출 base MAPE/bias: {_pct(result.revenue_base.mape)} / {_pct(result.revenue_base.bias)}",
        f"- 매출 weighted MAPE/bias: {_pct(result.revenue_weighted.mape)} / {_pct(result.revenue_weighted.bias)}",
        f"- GAAP EPS base MAPE/bias: {_pct(result.eps_base.mape)} / {_pct(result.eps_base.bias)}",
        f"- GAAP EPS weighted MAPE/bias: {_pct(result.eps_weighted.mape)} / {_pct(result.eps_weighted.bias)}",
        *format_gap_of_gap(basis_comparison),
        "",
        "#### 4-lever EPS 오차 귀인",
        "",
        "| 매출 | 영업이익률 | OP→NI | 주식수 | 합계 | 잔차 |",
        "|---:|---:|---:|---:|---:|---:|",
        f"| {attr.revenue:+.4f} | {attr.operating_margin:+.4f} | {attr.op_to_ni:+.4f} | {attr.share_count:+.4f} | {attr.eps_error_total:+.4f} | {attr.residual:+.2e} |",
        "",
        "#### Skill / surprise",
        "",
        f"- MASE 매출/EPS: {_number(skill.mase_revenue, 3)} / {_number(skill.mase_eps, 3)}",
        f"- Theil U2 매출/EPS: {_number(skill.theil_u2_revenue, 3)} / {_number(skill.theil_u2_eps, 3)}",
        f"- IR GAAP EPS 컨센 surprise 방향: **{surprise_status}** "
        f"(model {model_surprise:+.3f} / actual {actual_surprise:+.3f}, "
        f"consensus {FROZEN_ANCHOR['consensus']['ir']['gaap_eps']:.3f})",
        f"- 과거 호환 방향 정확도: {_pct(skill.surprise_direction_accuracy)}",
        "",
        "#### TSLA 특별 분리",
        "",
        f"- Automotive GP (크레딧 제외): ${_number(tesla.automotive_gross_profit_ex_credits)}M",
        f"- 규제 크레딧: ${_number(tesla.regulatory_credits)}M",
        f"- Automotive GP (크레딧 포함): ${_number(tesla.automotive_gross_profit_including_credits)}M",
        f"- OI&E: ${_number(tesla.other_income_expense)}M",
        f"- GAAP→non-GAAP EPS gap / SBC per share / 기타 bridge: {_number(tesla.gaap_to_non_gaap_eps_gap, 3)} / {_number(tesla.sbc_per_diluted_share, 3)} / {_number(tesla.non_sbc_bridge_per_share, 3)}",
    ]
    if result.segments:
        lines.extend(["", "#### 세그먼트 매출 오차", "", "| 세그먼트 | FROZEN | actual | MAPE |", "|---|---:|---:|---:|"])
        for segment in result.segments:
            lines.append(
                f"| {segment.segment} | {segment.forecast:,.0f} | {segment.actual:,.0f} | {segment.mape * 100:.1f}% |"
            )
    lines.extend([END_MARKER, ""])
    return "\n".join(lines)


def append_to_handoff(path: Path, block: str) -> None:
    """Insert or replace the postmortem block before section 5 atomically."""
    original = path.read_text(encoding="utf-8")
    if START_MARKER in original:
        start = original.index(START_MARKER)
        end = original.index(END_MARKER, start) + len(END_MARKER)
        updated = original[:start] + block.rstrip() + original[end:]
    else:
        marker = "\n## 5. 범위 가드레일"
        if marker not in original:
            raise ValueError("handoff section 5 marker not found")
        updated = original.replace(marker, "\n" + block.rstrip() + "\n" + marker, 1)

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", delete=False, dir=path.parent
    ) as handle:
        handle.write(updated)
        temp_path = Path(handle.name)
    try:
        os.replace(temp_path, path)
        reread = path.read_text(encoding="utf-8")
        if block.rstrip() not in reread:
            raise RuntimeError("handoff reread verification failed")
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--actual",
        type=Path,
        default=REPO_ROOT / "inputs" / "tsla_q2_2026_actual.yaml",
    )
    parser.add_argument("--append", action="store_true", help="append result to handoff section 4")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    before = _sha256(FROZEN_PATH)
    if before != FROZEN_SHA256:
        raise RuntimeError(f"FROZEN SHA mismatch: {before}")
    result = score_tsla(load_actual(args.actual))
    block = render_postmortem(result)
    logger.info("%s", block)
    if args.append:
        append_to_handoff(HANDOFF_PATH, block)
        logger.info("updated %s", HANDOFF_PATH)
    after = _sha256(FROZEN_PATH)
    if after != before:
        raise RuntimeError("FROZEN artifact changed during scoring")


if __name__ == "__main__":
    main()
