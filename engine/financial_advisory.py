"""Pure financial-routing advisories; never change methodology or financial inputs."""

from engine.industry_codes import is_financial_code
from engine.method_selector import _FINANCIAL_KEYWORDS, is_financial
from engine.warnings import make_warning
from schemas.models import EngineWarning, ValuationInput, ValuationResult


def build_financial_routing_advisories(
    vi: ValuationInput, result: ValuationResult
) -> list[EngineWarning]:
    """Report A1 segment treatment, A2 company signals and A3 disagreements."""
    financial_segments = []
    for code, info in sorted(vi.segments.items()):
        name = info.get("name", "") or ""
        keyword = next(
            (kw for kw in sorted(_FINANCIAL_KEYWORDS) if kw in name.lower()), None
        )
        if keyword is not None:
            financial_segments.append(
                (code, name, info.get("method") or "ev_ebitda", keyword)
            )

    manual_override = vi.valuation_method != "auto"
    severity = "warning" if manual_override else "review"
    warnings = []
    if result.primary_method == "sotp":
        for code, name, method, keyword in financial_segments:
            if method not in {"pbv", "pe"}:
                warnings.append(
                    make_warning(
                        "FINANCIAL_ROUTING_ADVISORY",
                        f"segment:{code}",
                        f"금융 세그먼트 '{name}'에 EV 방식({method})과 net_debt 차감이 적용됨 — "
                        "pbv/pe 전환 또는 segment_net_debt 분리 검토",
                        severity=severity,
                        segment_name=name,
                        segment_method=method,
                        keyword_hit=keyword,
                        manual_override=manual_override,
                    )
                )

    signal_truth = {
        "industry_keyword": is_financial(vi.industry or ""),
        "industry_code_financial": is_financial_code(vi.industry_code),
        "wacc_is_financial": bool(vi.wacc_params.is_financial),
        "financial_segments": bool(financial_segments),
    }
    # Flatten signals into scalar fields, preserving the J-2 warning schema.
    signals = {key: value for key, value in signal_truth.items() if value is not None}
    signals["financial_segments"] = f"{len(financial_segments)}/{len(vi.segments)}"
    company_signals = [
        key
        for key, value in signal_truth.items()
        if key != "financial_segments" and value is True
    ]
    if company_signals and result.primary_method not in {"ddm", "rim"}:
        warnings.append(
            make_warning(
                "FINANCIAL_ROUTING_ADVISORY",
                "result",
                f"금융업 신호({', '.join(company_signals)})인데 방법론 {result.primary_method} — DDM/RIM 검토",
                severity=severity,
                **signals,
                primary_method=result.primary_method,
                manual_override=manual_override,
            )
        )

    positive = [key for key, value in signal_truth.items() if value is True]
    negative = [key for key, value in signal_truth.items() if value is False]
    if positive and negative:
        warnings.append(
            make_warning(
                "FINANCIAL_ROUTING_ADVISORY",
                "input",
                f"금융업 신호 불일치: {', '.join(positive)} vs {', '.join(negative)}",
                severity="warning",
                **signals,
                de_ratio=vi.consolidated.get(vi.base_year, {}).get("de_ratio", 0.0),
            )
        )
    return warnings
