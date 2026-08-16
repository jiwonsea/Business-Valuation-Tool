"""Below-the-line (tax/finance) bias diagnosis — PLAN_tax_finance.md 3.1.

Read-only. Changes no forecast numbers and no profile assumptions.

Session C confirmed the model's only systematic weakness is a -10.55% EPS bias,
and engine.attribution localized it to the OP->NI conversion lever (tax/finance,
mean ~-8%). That lever lumps tax and all non-operating finance into one realized
ratio c = NI/OP, so it cannot say *which* below-the-line item drives the miss.

This script opens the realized OP->NI bridge from DART and splits the model's
below-the-line NI miss (given ACTUAL operating profit and revenue) into two
additive, sign-carrying pieces:

    NI_model|OP_a = OP_a * (1 - t_model) + rev_a * net_interest_pct_model
    NI_actual     = (OP_a + block_a) * (1 - t_a)          # block_a = pretax - OP

    tax  term  = OP_a * (t_a - t_model)                   # 0.20 vs realized rate
    block term = [OP_a*(1 - t_a) + rev_a*net_interest_pct_model] - NI_actual

    block_a = net_financial + net_other_nonop + equity (+ residual)
            = FinanceIncome - FinanceCosts            (FX valuation lives here)
            + OtherGains    - OtherLosses
            + ShareOfProfitLossOfAssociates

The two terms sum to the full model-vs-actual below-the-line NI miss; expressed
as a share of actual NI they approximate the tax/finance EPS-error contribution
reported by diagnose_divergence.py. The goal is NOT to remove the bias here but
to isolate the fixable part (effective tax rate) from the structurally volatile
part (net financial / FX / one-offs).

Usage:
    python scripts/diagnose_tax_finance.py --company sk_hynix
    python scripts/diagnose_tax_finance.py --company sk_hynix --no-cache  # live DART

Offline (sandbox): cache hits in reports/.cache/ need no network, but the DART
client still requires DART_API_KEY set to any non-empty value.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.dart_fetcher import (  # noqa: E402
    REPRT_CODES_BY_QUARTER,
    fetch_quarterly_financials,
)
from pipeline.ir_loader import load_profile  # noqa: E402

# Account ids on the DART CIS statement, below operating income.
ID_OP = {"dart_OperatingIncomeLoss"}
ID_PRETAX = {"ifrs-full_ProfitLossBeforeTax"}
ID_TAX = {"ifrs-full_IncomeTaxExpenseContinuingOperations"}
ID_NI = {"ifrs-full_ProfitLoss"}
ID_FIN_INCOME = {"ifrs-full_FinanceIncome"}
ID_FIN_COSTS = {"ifrs-full_FinanceCosts"}
ID_OTHER_GAINS = {"dart_OtherGains"}
ID_OTHER_LOSSES = {"dart_OtherLosses"}
# Equity-method line carries a long IFRS id; match by prefix.
PREFIX_EQUITY = "ifrs-full_ShareOfProfitLossOfAssociates"

KRW_BN = 1_000_000_000.0


def _quarter_sort_key(label: str) -> tuple[int, int]:
    year_text, quarter_text = label.split("Q", 1)
    return int(year_text), int(quarter_text)


def _pct(value: float | None) -> str:
    return "   n/a" if value is None else f"{value * 100:+.1f}%"


def _rows(raw: dict) -> list[dict]:
    return [r for r in raw.get("list", []) if r.get("sj_div") in ("IS", "CIS")]


def _amount(rows: list[dict], ids: set[str], field: str, prefix: str | None = None) -> float | None:
    """Return one line's amount (KRW billions), or None if absent/empty."""
    row = None
    for candidate in rows:
        if candidate.get("account_id") in ids:
            row = candidate
            break
    if row is None and prefix is not None:
        for candidate in rows:
            if str(candidate.get("account_id", "")).startswith(prefix):
                row = candidate
                break
    if row is None:
        return None
    value = row.get(field)
    if value in (None, "", "-"):
        return None
    return float(str(value).replace(",", "")) / KRW_BN


def _line(
    annual_or_q_rows: list[dict],
    q3_rows: list[dict] | None,
    is_q4: bool,
    ids: set[str],
    prefix: str | None = None,
) -> float | None:
    """Standalone-quarter amount, Q4 = annual(thstrm) - 9M(Q3 thstrm_add)."""
    if is_q4:
        if q3_rows is None:
            return None
        annual = _amount(annual_or_q_rows, ids, "thstrm_amount", prefix)
        nine_month = _amount(q3_rows, ids, "thstrm_add_amount", prefix)
        if annual is None or nine_month is None:
            return None
        return annual - nine_month
    return _amount(annual_or_q_rows, ids, "thstrm_amount", prefix)


def _backtest_quarters(profile: dict) -> list[str]:
    window = profile["backtest_window"]
    start = _quarter_sort_key(str(window["start_quarter"]))
    end = _quarter_sort_key(str(window["end_quarter"]))
    labels: list[str] = []
    year, quarter = start
    while (year, quarter) <= end:
        labels.append(f"{year}Q{quarter}")
        quarter += 1
        if quarter == 5:
            year, quarter = year + 1, 1
    return labels


def diagnose(profile: dict, use_cache: bool) -> list[dict]:
    """Extract realized below-the-line items + model/actual split per quarter."""
    corp_code = profile["company"].corp_code_dart
    _base_assumptions, _base_margin, base_finance = profile["scenarios"]["base"]
    t_model = base_finance.effective_tax_rate
    ni_pct_model = base_finance.net_interest_pct_of_revenue

    raw_cache: dict[tuple[int, str], dict] = {}

    def raw(year: int, reprt_code: str) -> dict:
        key = (year, reprt_code)
        if key not in raw_cache:
            raw_cache[key] = fetch_quarterly_financials(corp_code, year, reprt_code, use_cache=use_cache)
        return raw_cache[key]

    out: list[dict] = []
    for label in _backtest_quarters(profile):
        year = int(label[:4])
        quarter = int(label[-1])
        is_q4 = quarter == 4
        period_rows = _rows(raw(year, REPRT_CODES_BY_QUARTER[quarter]))
        q3_rows = _rows(raw(year, REPRT_CODES_BY_QUARTER[3])) if is_q4 else None

        op = _line(period_rows, q3_rows, is_q4, ID_OP)
        pretax = _line(period_rows, q3_rows, is_q4, ID_PRETAX)
        tax = _line(period_rows, q3_rows, is_q4, ID_TAX)
        ni = _line(period_rows, q3_rows, is_q4, ID_NI)
        fin_income = _line(period_rows, q3_rows, is_q4, ID_FIN_INCOME)
        fin_costs = _line(period_rows, q3_rows, is_q4, ID_FIN_COSTS)
        other_gains = _line(period_rows, q3_rows, is_q4, ID_OTHER_GAINS) or 0.0
        other_losses = _line(period_rows, q3_rows, is_q4, ID_OTHER_LOSSES) or 0.0
        equity = _line(period_rows, q3_rows, is_q4, set(), PREFIX_EQUITY) or 0.0
        revenue = _line(period_rows, q3_rows, is_q4, {"ifrs-full_Revenue"})

        if None in (op, pretax, tax, ni, revenue):
            raise KeyError(f"{label}: missing core below-the-line line item")

        net_financial = (fin_income or 0.0) - (fin_costs or 0.0)
        net_other_nonop = other_gains - other_losses
        block = pretax - op  # exact: pretax - operating
        residual = block - net_financial - net_other_nonop - equity
        t_actual = tax / pretax if pretax else None

        # Model below-the-line NI given ACTUAL op & revenue, vs realized NI.
        ni_model_at_actual_op = op * (1.0 - t_model) + revenue * ni_pct_model
        # Additive split of total_miss = ni_model_at_actual_op - ni:
        #   tax_term   = ni_model_at_actual_op - NI_A   (swap 0.20 -> realized rate on OP)
        #   block_term = NI_A - ni                       (swap flat proxy -> realized block)
        # where NI_A = op*(1 - t_actual) + revenue*ni_pct_model.
        tax_term = op * (t_actual - t_model) if t_actual is not None else None
        block_term = (op * (1.0 - t_actual) + revenue * ni_pct_model) - ni if t_actual is not None else None
        total_miss = ni_model_at_actual_op - ni  # >0 => model over-predicts NI

        out.append(
            {
                "label": label,
                "revenue": revenue,
                "op": op,
                "pretax": pretax,
                "tax": tax,
                "ni": ni,
                "t_actual": t_actual,
                "net_financial": net_financial,
                "net_other_nonop": net_other_nonop,
                "equity": equity,
                "residual": residual,
                "block": block,
                "model_net_interest": revenue * ni_pct_model,
                "tax_term": tax_term,
                "block_term": block_term,
                "total_miss": total_miss,
                # contributions to relative EPS error (~ share of actual NI)
                "tax_contrib": (tax_term / ni) if (tax_term is not None and ni) else None,
                "block_contrib": (block_term / ni) if (block_term is not None and ni) else None,
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Below-the-line (tax/finance) bias diagnosis")
    parser.add_argument("--company", required=True, help="Profile name (without .yaml)")
    parser.add_argument("--no-cache", action="store_true", help="Force live DART (default: cache)")
    args = parser.parse_args(argv)

    profile = load_profile(REPO_ROOT / "profiles" / f"{args.company}.yaml")
    _a, _m, base_finance = profile["scenarios"]["base"]
    rows = diagnose(profile, use_cache=not args.no_cache)

    print(
        f"Model base assumptions: effective_tax_rate={base_finance.effective_tax_rate:.0%}, "
        f"net_interest_pct_of_revenue={base_finance.net_interest_pct_of_revenue:+.1%}\n"
    )

    # --- Table 1: realized below-the-line waterfall (KRW bn) + effective tax. ---
    h1 = (
        f"{'Quarter':<8} {'OP':>9} {'net_fin':>9} {'non-op':>8} {'equity':>7} "
        f"{'resid':>7} {'=block':>9} {'pretax':>9} {'eff_tax':>8}"
    )
    print(h1)
    print("-" * len(h1))
    for r in rows:
        print(
            f"{r['label']:<8} {r['op']:>9,.0f} {r['net_financial']:>9,.0f} "
            f"{r['net_other_nonop']:>8,.0f} {r['equity']:>7,.0f} {r['residual']:>7,.0f} "
            f"{r['block']:>9,.0f} {r['pretax']:>9,.0f} {_pct(r['t_actual']):>8}"
        )

    # --- Table 2: model-vs-actual below-the-line split, as EPS-error contribution. ---
    print()
    h2 = (
        f"{'Quarter':<8} {'eff_tax':>8} {'vs 0.20':>8} | {'block':>9} "
        f"{'model_ni':>9} | {'tax-term':>9} {'block-term':>11}  (% of actual NI)"
    )
    print(h2)
    print("-" * len(h2))
    n = 0
    sum_tax = sum_block = 0.0
    for r in rows:
        dt = (r["t_actual"] - base_finance.effective_tax_rate) if r["t_actual"] is not None else None
        print(
            f"{r['label']:<8} {_pct(r['t_actual']):>8} {_pct(dt):>8} | "
            f"{r['block']:>9,.0f} {r['model_net_interest']:>9,.0f} | "
            f"{_pct(r['tax_contrib']):>9} {_pct(r['block_contrib']):>11}"
        )
        if r["tax_contrib"] is not None:
            sum_tax += r["tax_contrib"]
            sum_block += r["block_contrib"]
            n += 1
    if n:
        print("-" * len(h2))
        print(
            f"{'MEAN':<8} {'':>8} {'':>8} | {'':>9} {'':>9} | "
            f"{_pct(sum_tax / n):>9} {_pct(sum_block / n):>11}"
        )
        msg = (
            "\nReading: tax-term = EPS-error contribution from the effective-rate gap "
            "(realized vs assumed 0.20).\n"
            "block-term = contribution from the below-OP block (net financial / FX / "
            "one-offs) vs the flat\nnet_interest proxy. tax-term + block-term sum to the "
            "model's below-the-line NI miss; their\nper-quarter sum matches the "
            "diagnose_divergence.py tax/fin lever (mean ~-8%)."
        )
        print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
