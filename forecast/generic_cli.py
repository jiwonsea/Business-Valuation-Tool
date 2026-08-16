"""Generic-company forecast entry point (non-memory issuers).

    python generic_cli.py --profile profiles/nvda.generic.yaml
    python generic_cli.py --profile profiles/nvda.generic.yaml --json

Kept separate from cli.py (the memory/SK-Hynix pipeline) so the DRAM/NAND
backtest coupling and its 9Q invariant are never touched. Forecasting remains
profile-only; fiscal-aware Yahoo consensus is best-effort and replays from the
daily cache when available, so an offline run still emits the core report.

Output: Korean console summary + Markdown report (+ optional JSON) under reports/.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = REPO_ROOT / "reports"

sys.path.insert(0, str(REPO_ROOT))

from engine.generic_forecast import run_generic_forecast  # noqa: E402
from engine.generic_signal import (  # noqa: E402
    build_signal_block,
)
from engine.segment_revenue import _next_quarter_label  # noqa: E402
from engine.skill_metrics import SkillRow, compute_skill  # noqa: E402
from pipeline.generic_consensus import to_generic_consensus_record  # noqa: E402
from pipeline.yahoo_fetcher import fetch_consensus  # noqa: E402
from schemas.generic import GenericProfile  # noqa: E402
from schemas.models import ConsensusRecord  # noqa: E402


def load_generic_profile(path: Path) -> GenericProfile:
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return GenericProfile.model_validate(raw)


def _mape(pairs: list[tuple[float, float]]) -> float | None:
    errs = [abs(m - a) / abs(a) for m, a in pairs if a]
    return 100.0 * sum(errs) / len(errs) if errs else None


def _bias(pairs: list[tuple[float, float]]) -> float | None:
    errs = [(m - a) / a for m, a in pairs if a]
    return 100.0 * sum(errs) / len(errs) if errs else None


def _skill_rows(rows: list[dict]) -> list[SkillRow]:
    """Map generic backtest rows onto the shared ratio-based skill contract."""
    return [
        SkillRow(
            quarter_label=row["quarter"],
            actual_revenue=row["actual_rev"],
            model_revenue=row["model_rev"],
            rw_revenue=row["rw_rev"],
            actual_eps=row.get("actual_eps"),
            model_eps=row.get("model_eps"),
            rw_eps=row.get("rw_eps"),
        )
        for row in rows
    ]


def _summarize_window(
    rows: list[dict],
    consensus_history: dict[str, dict[str, float | None]] | None = None,
) -> dict:
    """Aggregate one row window; MAPE/bias are percent, skill values are ratios."""
    revenue_pairs = [(row["model_rev"], row["actual_rev"]) for row in rows]
    eps_pairs = [
        (row["model_eps"], row["actual_eps"])
        for row in rows
        if row.get("actual_eps") is not None and row.get("model_eps") is not None
    ]
    skill = compute_skill(
        _skill_rows(rows),
        consensus_history=consensus_history,
        include_trailing=False,
    )
    return {
        "n": len(revenue_pairs),
        "n_eps": skill.n_eps,
        "revenue_mape": _mape(revenue_pairs),
        "revenue_bias": _bias(revenue_pairs),
        "eps_mape": _mape(eps_pairs),
        "eps_bias": _bias(eps_pairs),
        "skill": skill.model_dump(),
        "rows": rows,
    }


def backtest_generic(
    profile: GenericProfile,
    consensus_history: dict[str, dict[str, float | None]] | None = None,
) -> dict:
    """One-step-ahead, seasonally-aware offline backtest over the actuals block.

    Predict each quarter's revenue as prior-actual x (1 + base growth[slot]);
    EPS via base op_margin/tax/net_interest at the same slot and the prior
    quarter's split-adjusted diluted share count (fixed-forward fallback for
    legacy rows). ``slot`` is the target quarter's calendar position
    (Q1->0 ... Q4->3) so a seasonal driver vector is matched to the right step
    rather than always using growth[0]. Compared against a naive random walk.
    """
    actuals = sorted(profile.actuals, key=lambda a: (int(a.quarter_label[:4]), int(a.quarter_label[-1])))
    if len(actuals) < 2:
        return {"n": len(actuals), "note": "actuals < 2 — backtest skipped"}

    # NVDA-1b contiguity guard: a 1-step backtest is only meaningful over
    # consecutive quarters. Historical NVDA/TSLA profiles had NO Q4 rows (and
    # mislabelled years), so sorted-adjacent rows silently joined Q3→Q1 and
    # corrupted the RW baseline, seasonal slots and every MAPE/MASE metric.
    # Refuse loudly instead of scoring a broken join.
    labels = [a.quarter_label for a in actuals]
    for prev_label, cur_label in zip(labels, labels[1:]):
        if _next_quarter_label(prev_label) != cur_label:
            return {
                "n": 0,
                "note": (
                    f"actuals 비연속({prev_label} → {cur_label}) — 1-step 백테스트 거부. "
                    "Q4 복원/라벨 수정 후 재실행 (NVDA-1b contiguity guard)"
                ),
            }

    n = profile.window.n_quarters
    methodology = profile.backtest_methodology or profile.base
    driver_n = 4 if profile.backtest_methodology is not None else n
    g = methodology.growth(driver_n)
    m = methodology.margin(driver_n)
    t = methodology.tax(driver_n)
    ni = methodology.net_interest(driver_n)
    scale = profile.unit_scale

    def _slot(label: str) -> int:
        if profile.backtest_methodology is not None:
            return int(label[-1]) - 1
        return min(int(label[-1]) - 1, n - 1)

    rev_pairs: list[tuple[float, float]] = []
    eps_pairs: list[tuple[float, float]] = []
    rw_rev_pairs: list[tuple[float, float]] = []
    rw_eps_pairs: list[tuple[float, float]] = []
    rows = []
    for prev, cur in zip(actuals, actuals[1:]):
        s = _slot(cur.quarter_label)
        model_rev = prev.revenue_total * (1.0 + g[s])
        op = model_rev * m[s]
        pretax = op + ni[s] * model_rev
        net = pretax * (1.0 - t[s])
        if prev.diluted_shares is not None:
            model_eps_shares = prev.diluted_shares * profile.split_factor(prev.period_end)
            share_convention = "prior_quarter_split_adjusted"
        else:
            model_eps_shares = profile.weighted_avg_diluted
            share_convention = "fixed_forward_fallback"
        model_eps = net * scale / model_eps_shares
        rev_pairs.append((model_rev, cur.revenue_total))
        rw_rev_pairs.append((prev.revenue_total, cur.revenue_total))
        # rw_rev/rw_eps = random-walk (persistence) baseline = prior-quarter actual.
        # Carried per-row so the signal block can recompute skill over a trailing
        # window (Item 1 dual-window reporting) without re-deriving the baseline.
        row = {
            "quarter": cur.quarter_label,
            "actual_rev": cur.revenue_total,
            "model_rev": model_rev,
            "rw_rev": prev.revenue_total,
            "model_eps_share_count": model_eps_shares,
            "model_eps_share_convention": share_convention,
        }
        if cur.eps_diluted is not None and prev.eps_diluted is not None:
            eps_pairs.append((model_eps, cur.eps_diluted))
            rw_eps_pairs.append((prev.eps_diluted, cur.eps_diluted))
            row["actual_eps"] = cur.eps_diluted
            row["model_eps"] = model_eps
            row["rw_eps"] = prev.eps_diluted
        rows.append(row)

    result = {
        "n": len(rev_pairs),
        "revenue_mape": _mape(rev_pairs),
        "revenue_bias": _bias(rev_pairs),
        "eps_mape": _mape(eps_pairs),
        "eps_bias": _bias(eps_pairs),
        "naive_rw_revenue_mape": _mape(rw_rev_pairs),
        "naive_rw_eps_mape": _mape(rw_eps_pairs),
        "rows": rows,
        "skill": compute_skill(
            _skill_rows(rows), consensus_history=consensus_history
        ).model_dump(),
    }
    if profile.regime_break_quarter is not None:
        pre_rows = [row for row in rows if row["quarter"] < profile.regime_break_quarter]
        post_rows = [row for row in rows if row["quarter"] >= profile.regime_break_quarter]
        result["windows"] = {
            "full": _summarize_window(rows, consensus_history),
            "pre_break": _summarize_window(pre_rows, consensus_history),
            "post_break": _summarize_window(post_rows, consensus_history),
        }
    return result


def _render_skill(skill: dict) -> str:
    """Render shared skill ratios; this is the sole ratio-to-percent conversion site."""
    def ratio(value: float | None) -> str:
        return "N/A" if value is None else f"{value:.3f}"

    rw_rev = skill.get("naive_rw_revenue_mape")
    rw_eps = skill.get("naive_rw_eps_mape")
    rw_rev_text = "N/A" if rw_rev is None else f"{rw_rev * 100:.1f}%"
    rw_eps_text = "N/A" if rw_eps is None else f"{rw_eps * 100:.1f}%"
    return (
        f"RW MAPE 매출 {rw_rev_text} / EPS {rw_eps_text} · "
        f"MASE 매출 {ratio(skill.get('mase_revenue'))} / EPS {ratio(skill.get('mase_eps'))} · "
        f"Theil U2 매출 {ratio(skill.get('theil_u2_revenue'))} / EPS {ratio(skill.get('theil_u2_eps'))} · "
        f"consensus N={skill.get('n_surprise_scored', 0)}"
    )


def _render_window(label: str, window: dict) -> list[str]:
    """Render one backtest window with percent errors and ratio-based skill."""
    def percent(value: float | None, *, signed: bool = False) -> str:
        if value is None:
            return "N/A"
        return f"{value:+.1f}%" if signed else f"{value:.1f}%"

    return [
        f"- **{label}** · N={window['n']} (EPS {window['n_eps']}) · "
        f"매출 MAPE {percent(window['revenue_mape'])} / bias {percent(window['revenue_bias'], signed=True)} · "
        f"EPS MAPE {percent(window['eps_mape'])} / bias {percent(window['eps_bias'], signed=True)}",
        f"  - {_render_skill(window['skill'])}",
    ]


def render_markdown(
    profile: GenericProfile,
    fc,
    bt: dict,
    consensus: ConsensusRecord | None = None,
) -> str:
    p = profile
    lines = [
        f"# {p.name_kr} ({p.name}) — 실적 전망 (Generic)",
        "",
        f"- 티커: `{p.ticker}` · 통화: {p.currency} ({p.reporting_unit}) · 희석주식수: {p.weighted_avg_diluted:,.0f}",
        f"- 시드 분기: {p.seed.quarter_label} (매출 {p.seed.revenue_total:,.0f})",
        f"- 전망 구간: {p.window.start_quarter}부터 {p.window.n_quarters}개 분기",
        "",
        "## 확률가중 분기 전망",
        "",
        "| 분기 | 매출 | 영업이익 | 순이익 | EPS(희석) |",
        "|---|---:|---:|---:|---:|",
    ]
    for q in fc.weighted_quarterly:
        lines.append(
            f"| {q.quarter_label} | {q.revenue_total:,.0f} | {q.operating_profit:,.0f} "
            f"| {q.net_profit:,.0f} | {q.eps_diluted:,.2f} |"
        )
    lines += ["", "## 연간 EPS (시나리오별)", "", "| FY | Bear | Base | Bull | 가중 |", "|---|---:|---:|---:|---:|"]
    years = [a.fiscal_year for a in fc.weighted_annual]
    for i, fy in enumerate(years):
        b = fc.scenarios_annual["bear"][i].eps_basic or 0.0
        ba = fc.scenarios_annual["base"][i].eps_basic or 0.0
        bu = fc.scenarios_annual["bull"][i].eps_basic or 0.0
        w = fc.weighted_annual[i].eps_basic or 0.0
        lines.append(f"| {fy} | {b:,.2f} | {ba:,.2f} | {bu:,.2f} | {w:,.2f} |")

    lines += ["", "## 오프라인 백테스트 (1-step, seasonally-aware)", ""]
    if bt.get("revenue_mape") is None:
        lines.append(f"- {bt.get('note', 'N/A')}")
    elif bt.get("windows"):
        windows = bt["windows"]
        lines += _render_window("Post-break (headline)", windows["post_break"])
        lines += _render_window("Full window", windows["full"])
        lines += _render_window("Pre-break", windows["pre_break"])
    else:
        lines.append(
            f"- N={bt['n']} · 매출 MAPE {bt['revenue_mape']:.1f}% (naive RW {bt['naive_rw_revenue_mape']:.1f}%) · 매출 bias {bt['revenue_bias']:+.1f}%"
        )
        if bt.get("eps_mape") is not None:
            lines.append(
                f"- EPS MAPE {bt['eps_mape']:.1f}% (naive RW {bt['naive_rw_eps_mape']:.1f}%) · EPS bias {bt['eps_bias']:+.1f}%"
            )
        lines.append(f"- {_render_skill(bt['skill'])}")
    lines += ["", "## Yahoo consensus (fiscal-aware)", ""]
    if consensus is None:
        lines.append("- unavailable")
    else:
        lines.append(f"- snapshot as-of: {consensus.as_of}")
        for label in consensus.revenue_estimate_quarterly:
            revenue = consensus.revenue_estimate_quarterly[label]
            eps = consensus.eps_estimate_quarterly.get(label)
            revenue_text = "N/A" if revenue is None else f"{revenue:,.2f}"
            eps_text = "N/A" if eps is None else f"{eps:,.2f}"
            lines.append(f"- {label}: revenue {revenue_text} · EPS {eps_text}")
        for fiscal_year in consensus.revenue_estimate_annual:
            revenue = consensus.revenue_estimate_annual[fiscal_year]
            eps = consensus.eps_estimate_annual.get(fiscal_year)
            revenue_text = "N/A" if revenue is None else f"{revenue:,.2f}"
            eps_text = "N/A" if eps is None else f"{eps:,.2f}"
            lines.append(f"- FY{fiscal_year}: revenue {revenue_text} · EPS {eps_text}")
        lines += [f"- quality: {note}" for note in consensus.quality_notes]
    if p.notes:
        lines += ["", "## 데이터 출처 / 주의", ""]
        lines += [f"- {n}" for n in p.notes]
    lines += [
        "",
        f"_시나리오 확률: bear {p.bear.probability:.0%} / base {p.base.probability:.0%} / bull {p.bull.probability:.0%}_",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generic-company earnings forecast")
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--json", action="store_true", help="also write JSON")
    args = parser.parse_args(argv)

    profile = load_generic_profile(args.profile)
    fc = run_generic_forecast(profile)
    raw_consensus = None
    consensus = None
    try:
        raw_consensus = fetch_consensus(profile.ticker)
        snapshot_as_of = date.fromisoformat(raw_consensus.get("as_of", date.today().isoformat()))
        consensus = to_generic_consensus_record(raw_consensus, profile, snapshot_as_of)
    except Exception:
        consensus = None
    bt = backtest_generic(profile, consensus.history if consensus is not None else None)

    REPORTS_DIR.mkdir(exist_ok=True)
    md = render_markdown(profile, fc, bt, consensus)
    stem = args.profile.stem.replace(".generic", "")
    md_path = REPORTS_DIR / f"{stem}_generic_forecast.md"
    md_path.write_text(md, encoding="utf-8")

    w_fy = fc.weighted_annual
    print(f"[{profile.name}] 확률가중 FY EPS:", ", ".join(f"{a.fiscal_year}={a.eps_basic:,.2f}" for a in w_fy))
    if bt.get("revenue_mape") is not None:
        headline = bt.get("windows", {}).get("post_break", bt)
        eps_txt = f" · EPS MAPE {headline['eps_mape']:.1f}%" if headline.get("eps_mape") is not None else ""
        label = "post-break " if bt.get("windows") else ""
        print(f"  백테스트 {label}N={headline['n']} · 매출 MAPE {headline['revenue_mape']:.1f}%{eps_txt}")
    else:
        print(f"  백테스트: {bt.get('note')}")
    print(f"  리포트: {md_path}")

    if args.json:
        json_path = REPORTS_DIR / f"{stem}_generic_forecast.json"
        weighted_annual = [a.model_dump() for a in fc.weighted_annual]
        weighted_quarterly = [q.model_dump() for q in fc.weighted_quarterly]
        target_fiscal_year = w_fy[0].fiscal_year if w_fy else None
        consensus_fy1 = (
            consensus.eps_estimate_annual.get(target_fiscal_year)
            if consensus is not None and target_fiscal_year is not None
            else None
        )
        payload = {
            "company": profile.name,
            "weighted_annual": weighted_annual,
            "weighted_quarterly": weighted_quarterly,
            "backtest": bt,
            "consensus": consensus.model_dump() if consensus is not None else None,
            "consensus_fetch_timestamp": (
                raw_consensus.get("fetch_timestamp") if raw_consensus is not None else None
            ),
            "signal": build_signal_block(
                weighted_annual, weighted_quarterly, bt, consensus_fy1
            ),
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"  JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
