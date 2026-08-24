"""Valuation execution engine -- YAML loading + method-specific dispatch."""

import hashlib
import logging
from datetime import date

import yaml

logger = logging.getLogger(__name__)

from schemas.models import (
    CompanyProfile,
    WACCParams,
    WACCResult,
    ScenarioParams,
    DCFParams,
    DDMParams,
    NAVParams,
    HoldingStructure,
    RNPVParams,
    RIMParams,
    RIMProjectionResult,
    RIMValuationResult,
    PeerCompany,
    ValuationInput,
    ValuationResult,
    CrossValidationItem,
    MonteCarloResult,
    DDMValuationResult,
    NAVResult,
    MultiplesResult,
    RNPVValuationResult,
    RNPVDrugResult,
    NewsDriver,
    PipelineDrug,
    ValidationReport,
    RelativeInputs,
    GapDiagnostic,
)
from engine.drivers import resolve_drivers
from engine.normalize import NetDebtResolution, resolve_net_debt
from schemas.provenance import (
    LEGACY_VERSION,
    NORMALIZATION_VERSION,
    NetDebtComponents,
)
from engine.wacc import calc_wacc
from engine.sotp import allocate_da, calc_sotp
from engine.distress import calc_distress_discount, apply_distress_discount
from engine.dcf import calc_dcf
from engine.ddm import calc_ddm as calc_ddm_engine
from engine.rim import calc_rim as calc_rim_engine
from engine.scenario import calc_scenario
from engine.sensitivity import (
    sensitivity_multiples,
    sensitivity_irr_dlom,
    sensitivity_dcf,
    sensitivity_ddm,
    sensitivity_rim,
    sensitivity_nav,
    sensitivity_multiple_range,
    sensitivity_rnpv,
    sensitivity_rnpv_tornado,
)
from engine.multiples import cross_validate, calc_pe, calc_pbv
from engine.peer_analysis import calc_peer_stats
from engine.quality import calc_quality_score
from engine.nav import calc_nav
from engine.rnpv import calc_rnpv
from engine.holding_discount import build_holding_discount_bridge
from engine.units import detect_unit, per_share
from engine.method_selector import suggest_method, is_financial, infer_valuation_bucket
from engine.investability_gate import (
    evaluate_investability,
    gate_inputs_from_profile,
)


# Minimum segment asset share (%) to qualify for healthy-segment half-discount.
# Prevents tiny profitable segments from masking consolidated distress signals.
_HEALTHY_MIN_ASSET_SHARE_PCT = 20.0


def _seg_names(vi: ValuationInput) -> dict[str, str]:
    """Extract {code: name} mapping from segments dictionary."""
    return {code: info["name"] for code, info in vi.segments.items()}


def _adjust_wacc(base: WACCResult, wacc_adj: float, eq_w: float = 100.0) -> WACCResult:
    """Per-scenario WACC adjustment. wacc_adj shifts Ke; WACC is recomputed from components.

    Args:
        base: Base WACC result
        wacc_adj: Ke shift in %p (e.g., +0.5 -> Ke + 0.5%p)
        eq_w: Equity weight (%) from WACCParams -- needed to recompute WACC correctly
    """
    if wacc_adj == 0:
        return base
    new_ke = round(base.ke + wacc_adj, 4)
    dw = 100 - eq_w
    new_wacc = round(new_ke * eq_w / 100 + base.kd_at * dw / 100, 4)
    return WACCResult(
        bl=base.bl,
        ke=new_ke,
        kd_at=base.kd_at,
        wacc=new_wacc,
    )


def _sotp_scenarios_undifferentiated(resolved_scenarios) -> bool:
    """True iff scenarios differ by neither EV drivers nor equity-bridge fields.

    Operates on scenarios AFTER resolve_drivers() so that active_drivers
    contributing to growth_adj_pct/market_sentiment_pct are accounted for.

    Two legitimate SOTP differentiation patterns:
      EV-driver:     segment_multiples / segment_ebitda / segment_revenue /
                     segment_method_override / growth_adj_pct / market_sentiment_pct
      Equity-bridge: irr / cps_irr / rcps_irr / dlom /
                     cps_repay / rcps_repay / buyback / shares
    """
    if len(resolved_scenarios) <= 1:
        return False

    undiff_ev = all(
        not sc.segment_ebitda
        and not sc.segment_multiples
        and not sc.segment_revenue
        and not sc.segment_method_override
        and sc.growth_adj_pct == 0
        and sc.market_sentiment_pct == 0
        for sc in resolved_scenarios
    )
    if not undiff_ev:
        return False

    bridge_sigs = {
        (
            sc.irr,
            sc.cps_irr,
            sc.rcps_irr,
            sc.dlom,
            sc.cps_repay,
            sc.rcps_repay,
            sc.buyback,
            sc.shares,
        )
        for sc in resolved_scenarios
    }
    return len(bridge_sigs) == 1


def load_profile(path: str) -> ValuationInput:
    """Parse YAML profile into ValuationInput."""
    from pathlib import Path

    profile_text = Path(path).read_text(encoding="utf-8")
    raw = yaml.safe_load(profile_text)

    # Company
    co_raw = raw["company"]
    if isinstance(co_raw.get("analysis_date"), str):
        co_raw["analysis_date"] = date.fromisoformat(co_raw["analysis_date"])
    company = CompanyProfile(**co_raw)

    # Segments info
    segments = raw["segments"]

    # Segment data: year(int) → code → financials dict
    segment_data = {}
    for yr_str, segs in raw["segment_data"].items():
        yr = int(yr_str)
        segment_data[yr] = {code: data for code, data in segs.items()}

    # Consolidated: year(int) → financials dict
    consolidated = {}
    for yr_str, data in raw["consolidated"].items():
        yr = int(yr_str)
        consolidated[yr] = data

    base_year = int(raw.get("base_year", 2025))
    financial_anchor = raw.get("financial_anchor", "fy")
    ttm_anchor = raw.get("ttm_anchor")
    fy_base_financials = dict(consolidated.get(base_year, {}))
    anchor_fallback_reason = raw.get("financial_anchor_fallback_reason")
    if financial_anchor == "ttm":
        required_ttm = {"revenue", "op", "net_income", "dep", "amort", "capex"}
        if not isinstance(ttm_anchor, dict):
            raise ValueError("financial_anchor=ttm requires ttm_anchor")
        missing_ttm = sorted(required_ttm - set(ttm_anchor))
        if missing_ttm:
            raise ValueError(
                f"financial_anchor=ttm is incomplete: missing {missing_ttm}"
            )
        consolidated[base_year] = {
            **fy_base_financials,
            **ttm_anchor,
        }
        if len(segments) == 1 and base_year in segment_data:
            only_code = next(iter(segments))
            if only_code in segment_data[base_year]:
                segment_data[base_year][only_code] = {
                    **segment_data[base_year][only_code],
                    "revenue": ttm_anchor["revenue"],
                    "op": ttm_anchor["op"],
                }

    # WACC
    wacc_params = WACCParams(**raw["wacc_params"])

    # Multiples (from segments info)
    multiples = {code: info["multiple"] for code, info in segments.items()}

    # Scenarios
    scenarios = {}
    for code, sc_raw in raw.get("scenarios", {}).items():
        scenarios[code] = ScenarioParams(code=code, **sc_raw)

    # DCF (optional for equity-only methods like DDM/RIM/NAV)
    dcf_params = DCFParams(**raw["dcf_params"]) if "dcf_params" in raw else DCFParams()
    # Auto-generate from financial data when ebitda_growth_rates not specified
    if dcf_params.ebitda_growth_rates is None:
        from engine.growth import generate_growth_rates

        _industry = raw.get("industry", "") or co_raw.get("industry", "")
        dcf_params = dcf_params.model_copy(
            update={
                "ebitda_growth_rates": generate_growth_rates(
                    consolidated,
                    market=company.market,
                    industry=_industry,
                )
            }
        )

    # DDM (Optional)
    ddm_params = None
    if "ddm_params" in raw:
        ddm_params = DDMParams(**raw["ddm_params"])

    # RIM (Optional)
    rim_params = None
    if "rim_params" in raw:
        rim_params = RIMParams(**raw["rim_params"])

    # NAV (Optional)
    nav_params = None
    if "nav_params" in raw:
        nav_params = NAVParams(**raw["nav_params"])

    holding_structure = None
    if "holding_structure" in raw:
        holding_structure = HoldingStructure(**raw["holding_structure"])
        company = company.model_copy(update={"holding_structure": holding_structure})

    # rNPV (Optional — pharma pipeline)
    rnpv_params = None
    if "rnpv_params" in raw:
        pipeline_raw = raw["rnpv_params"].get("pipeline", [])
        pipeline_drugs = [PipelineDrug(**d) for d in pipeline_raw]
        rnpv_params = RNPVParams(
            pipeline=pipeline_drugs,
            r_and_d_cost=raw["rnpv_params"].get("r_and_d_cost", 0),
            discount_rate=raw["rnpv_params"].get("discount_rate"),
            decline_rate=raw["rnpv_params"].get("decline_rate", 20.0),
            default_margin=raw["rnpv_params"].get("default_margin", 0.35),
            tax_rate=raw["rnpv_params"].get("tax_rate", 0.22),
        )

    # Peers (skip entries with non-numeric ev_ebitda from AI output)
    peers = []
    for p in raw.get("peers", []):
        try:
            peers.append(PeerCompany(**p))
        except (ValueError, TypeError, KeyError) as e:
            logger.warning("Skipping invalid peer entry %s: %s", p, e)

    # News drivers (multi-variable scenario approach)
    news_drivers = []
    for nd_raw in raw.get("news_drivers", []):
        try:
            news_drivers.append(NewsDriver(**nd_raw))
        except (ValueError, TypeError, KeyError) as e:
            logger.warning("Skipping invalid news_driver entry %s: %s", nd_raw, e)
    news_key_issues = raw.get("news_key_issues")

    # Auto-detect unit_multiplier (when not specified in YAML)
    if "unit_multiplier" not in raw.get("company", {}):
        latest_yr = max(consolidated.keys())
        revenue = consolidated[latest_yr].get("revenue", 0)
        label, multiplier = detect_unit(revenue, company.market)
        company = company.model_copy(
            update={"currency_unit": label, "unit_multiplier": multiplier}
        )

    # Validate scenario override keys against known segment codes.
    # Build a name→code reverse map so AI-generated real names (e.g. "DS", "MEMORY")
    # are silently remapped to their SEG codes before the bad-key check.
    _valid_seg_codes = set(segments.keys())
    _name_to_code: dict[str, str] = {}
    for seg_code, seg_info in segments.items():
        seg_name = getattr(seg_info, "name", "") or ""
        # Index by full name and leading word (e.g. "반도체 (메모리/파운드리)" → "반도체")
        for variant in {
            seg_name.lower(),
            seg_name.split("(")[0].strip().lower(),
            seg_name.split(" ")[0].lower(),
        }:
            if variant:
                _name_to_code[variant] = seg_code

    for sc_code, sc in scenarios.items():
        for attr_name in ("segment_multiples", "segment_ebitda", "segment_revenue"):
            override_dict = getattr(sc, attr_name, None)
            if not override_dict:
                continue
            bad_keys = set(override_dict.keys()) - _valid_seg_codes
            if bad_keys:
                # Attempt name→code remapping before giving up
                remapped = {}
                still_bad = set()
                for k in bad_keys:
                    target = _name_to_code.get(k.lower())
                    if target:
                        remapped[k] = target
                    else:
                        still_bad.add(k)
                if remapped:
                    new_dict = {remapped.get(k, k): v for k, v in override_dict.items()}
                    setattr(sc, attr_name, new_dict)
                    logger.info(
                        "[%s] scenario '%s' %s: remapped keys %s → %s",
                        company.name,
                        sc_code,
                        attr_name,
                        list(remapped.keys()),
                        list(remapped.values()),
                    )
                if still_bad:
                    logger.warning(
                        "[%s] scenario '%s' %s has unrecognized keys %s "
                        "(valid: %s) — overrides will be ignored",
                        company.name,
                        sc_code,
                        attr_name,
                        still_bad,
                        _valid_seg_codes,
                    )

    # Clamp segment_multiples Bull/Bear ratio to ≤ 2.0x to prevent unrealistic EV spread.
    # Finds the per-segment minimum multiple across all scenarios (Bear reference), then
    # caps any multiple exceeding min × 2.0.
    _SOTP_MAX_RATIO = 2.0
    _allow_wide_spread = bool(
        raw.get("curated", False) and raw.get("allow_wide_scenario_spread", False)
    )
    _scenario_spread_warnings: list[str] = []
    _scenario_multiples_clamped = False
    _sc_mults_map: dict[str, dict[str, float]] = {
        code: dict(sc.segment_multiples)
        for code, sc in scenarios.items()
        if sc.segment_multiples
    }
    if len(_sc_mults_map) >= 2:
        # Per-segment minimum across all scenarios = effective Bear floor
        _seg_min: dict[str, float] = {}
        for mults in _sc_mults_map.values():
            for seg, val in mults.items():
                if val > 0:
                    _seg_min[seg] = min(_seg_min.get(seg, val), val)

        for sc_code, mults in _sc_mults_map.items():
            clamped = {}
            changed = False
            for seg, val in mults.items():
                floor = _seg_min.get(seg, 0)
                cap = floor * _SOTP_MAX_RATIO if floor > 0 else float("inf")
                if val > cap:
                    original_ratio = val / floor
                    if _allow_wide_spread:
                        clamped[seg] = val
                        warning = (
                            f"[{company.name}] curated wide spread 허용: 시나리오 "
                            f"'{sc_code}', 세그먼트 '{seg}' {val:.2f}x "
                            f"(최저 시나리오 대비 {original_ratio:.2f}x, "
                            f"기본 한도 {_SOTP_MAX_RATIO:.2f}x)"
                        )
                    else:
                        applied = round(cap, 2)
                        clamped[seg] = applied
                        changed = True
                        _scenario_multiples_clamped = True
                        warning = (
                            f"[{company.name}] 시나리오 클램프: '{sc_code}' / "
                            f"'{seg}' multiple {val:.2f}x → {applied:.2f}x "
                            f"(최저 시나리오 대비 {original_ratio:.2f}x → "
                            f"{_SOTP_MAX_RATIO:.2f}x)"
                        )
                    _scenario_spread_warnings.append(warning)
                    logger.warning(warning)
                else:
                    clamped[seg] = val
            if changed:
                scenarios[sc_code] = scenarios[sc_code].model_copy(
                    update={"segment_multiples": clamped}
                )

    _share_count_warnings: list[str] = []
    if scenarios:
        reference = max(scenarios.values(), key=lambda scenario: scenario.prob)
        outstanding = company.shares_outstanding
        if reference.shares > 0 and reference.shares != outstanding:
            difference = reference.shares - outstanding
            treasury_note = (
                f" (자기주식 {company.treasury_shares:,} 포함)"
                if difference == company.treasury_shares and difference > 0
                else ""
            )
            warning = (
                f"적용 주식수 {reference.shares:,} ≠ 유통주식수 {outstanding:,}"
                f"{treasury_note} — 시나리오 shares가 의도적 설정인지 확인"
            )
            _share_count_warnings.append(warning)
            logger.warning(warning)

    vi = ValuationInput(
        company=company,
        draft=raw.get("draft", False),
        generated=raw.get("generated", ""),
        curated=raw.get("curated", False),
        allow_wide_scenario_spread=raw.get("allow_wide_scenario_spread", False),
        profile_text=profile_text,
        scenario_spread_warnings=_scenario_spread_warnings,
        share_count_warnings=_share_count_warnings,
        scenario_multiples_clamped=_scenario_multiples_clamped,
        valuation_method=raw.get("valuation_method", "auto"),
        industry=raw.get("industry", "") or co_raw.get("industry", ""),
        segments=segments,
        segment_data=segment_data,
        consolidated=consolidated,
        wacc_params=wacc_params,
        beta_provenance=raw.get("beta_provenance"),
        erp_provenance=raw.get("erp_provenance"),
        tax_provenance=raw.get("tax_provenance"),
        multiples=multiples,
        scenarios=scenarios,
        dcf_params=dcf_params,
        ddm_params=ddm_params,
        rim_params=rim_params,
        nav_params=nav_params,
        rnpv_params=rnpv_params,
        cps_principal=raw.get("cps_principal", 0),
        cps_years=raw.get("cps_years", 0),
        cps_dividend_rate=raw.get("cps_dividend_rate", 0.0),
        rcps_principal=raw.get("rcps_principal", 0),
        rcps_years=raw.get("rcps_years", 0),
        rcps_dividend_rate=raw.get("rcps_dividend_rate", 0.0),
        net_debt=raw.get("net_debt", 0),
        net_debt_components=_parse_net_debt_components(raw),
        normalization_version=raw.get("normalization_version", LEGACY_VERSION),
        market_price=raw.get("market_price"),
        price_as_of=raw.get("price_as_of"),
        relative_inputs=RelativeInputs(**raw["relative_inputs"])
        if raw.get("relative_inputs")
        else None,
        segment_net_debt=raw.get("segment_net_debt", {}),
        eco_frontier=raw.get("eco_frontier", 0),
        peers=peers,
        base_year=base_year,
        financial_anchor=financial_anchor,
        ttm_anchor=ttm_anchor,
        ttm_provenance=raw.get("ttm_provenance"),
        fy_base_financials=fy_base_financials,
        financial_anchor_fallback_reason=anchor_fallback_reason,
        # Consensus and peer snapshots are audit/display metadata only. Deliberately
        # do not merge either block into consolidated, segment_data, or WACC inputs.
        forward_anchor=raw.get("forward_anchor"),
        peer_beta_snapshot=raw.get("peer_beta_snapshot"),
        ev_revenue_multiple=raw.get("ev_revenue_multiple", 0.0),
        pe_multiple=raw.get("pe_multiple", 0.0),
        pbv_multiple=raw.get("pbv_multiple", 0.0),
        ps_multiple=raw.get("ps_multiple", 0.0),
        pffo_multiple=raw.get("pffo_multiple", 0.0),
        ffo=raw.get("ffo", 0),
        mc_enabled=raw.get("mc_enabled", False),
        mc_sims=raw.get("mc_sims", 10_000),
        mc_multiple_std_pct=raw.get("mc_multiple_std_pct", 15.0),
        mc_dlom_mean=raw.get("mc_dlom_mean", 0.0),
        mc_dlom_std=raw.get("mc_dlom_std", 5.0),
        mc_revenue_std_pct=raw.get("mc_revenue_std_pct", 30.0),
        distress_max_discount=raw.get("distress_max_discount", 0.25),
        news_drivers=news_drivers,
        news_key_issues=news_key_issues,
        market_signals=raw.get("market_signals"),
        scenario_validation=ValidationReport(**raw["scenario_validation"])
        if raw.get("scenario_validation")
        else None,
    )

    return apply_net_debt_gate(vi)


def _parse_net_debt_components(raw: dict) -> NetDebtComponents | None:
    """YAML dict -> NetDebtComponents. `reconciled`는 computed라 payload로 위조되지 않는다."""
    payload = raw.get("net_debt_components")
    if not payload:
        return None
    if isinstance(payload, NetDebtComponents):
        return payload
    return NetDebtComponents.model_validate(payload)


def _already_gated(vi: ValuationInput, res: NetDebtResolution) -> bool:
    """이미 게이트를 통과한 입력인가? (멱등성 — CODEX 재작업 판정 1)

    두 번 적용하면 `net_debt_legacy`에 legacy가 아니라 **정규화 값**이 들어가 감사 축이 파괴된다.
    (`vi.net_debt`가 이미 교체돼 있으므로 두 번째 호출의 legacy_value는 정규화 값이다.)
    소비 상태의 표지는 세 가지가 동시에 참인 것이다:
      - normalization_version == NORMALIZATION_VERSION
      - net_debt_legacy is not None (교체 전 값이 보존돼 있다)
      - 지금 다시 대조해도 여전히 reconciled (components를 갈아끼운 입력은 재게이트 대상)
    """
    return (
        res.status == "consumed"
        and vi.normalization_version == NORMALIZATION_VERSION
        and vi.net_debt_legacy is not None
        and vi.net_debt == res.value
    )


def _demote_orphaned_normalization(vi: ValuationInput) -> ValuationInput:
    """원장(net_debt_components) 없이 정규화를 주장하는 입력을 legacy로 되돌린다.

    두 경로를 막는다 (CODEX 재작업 판정):
      1. 소비 후 원장만 제거된 입력 — 검증 축이 사라졌는데 정규화 값을 계속 소비하게 된다.
         `net_debt`를 `net_debt_legacy`로 롤백한다.
      2. 원장 없이 YAML이 `normalization_version`만 최신으로 적어 넣은 입력 — 대조할 원장이
         없으면 정규화를 주장할 수 없다. legacy로 강등한다.
    원장도 없고 소비 흔적도 없으면 P0 이전 프로필이다 — 손대지 않는다 (R10 무변화).
    """
    if vi.net_debt_legacy is None and vi.normalization_version == LEGACY_VERSION:
        return vi

    rollback: dict = {"normalization_version": LEGACY_VERSION}
    if vi.net_debt_legacy is not None:
        rollback["net_debt"] = vi.net_debt_legacy
        rollback["net_debt_legacy"] = None
    logger.warning(
        "[%s] 순차입금 원장(net_debt_components)이 없는데 정규화(%s)를 주장한다 — "
        "legacy로 강등. 검증 원장 없이는 정규화 값을 소비할 수 없다.",
        vi.company.name,
        vi.normalization_version,
    )
    return vi.model_copy(update=rollback)


def apply_net_debt_gate(vi: ValuationInput) -> ValuationInput:
    """§2.1 순차입금 게이트 (P0-1). reconciled is True일 때만 정규화 값을 소비한다.

    **멱등**이다 — `load_profile()`과 `run_valuation()` 양쪽에서 호출해도 안전하다.
    엔진·콘솔·Excel은 모두 `vi.net_debt`를 읽으므로, 소비 지점을 이 함수 하나로 모으면
    경로가 갈라지지 않는다.
    차단(False=불일치 / None=대조 불가) 시 legacy 스칼라를 그대로 두고
    normalization_version도 legacy로 남긴다 — 없는 정상화를 주장하지 않는다.
    """
    res: NetDebtResolution = resolve_net_debt(vi.net_debt_components, vi.net_debt)

    if res.status == "absent":
        return _demote_orphaned_normalization(vi)

    if _already_gated(vi, res):
        return vi  # 이미 소비됨 — 재적용하면 net_debt_legacy가 덮어써진다

    if res.blocked:
        logger.warning(
            "[%s] 순차입금 정규화 차단 (%s): %s — legacy 값 %s 유지",
            vi.company.name,
            res.status,
            res.reason,
            f"{res.legacy_value:,}",
        )
        if vi.normalization_version == LEGACY_VERSION:
            return vi
        # 한 번 소비된 뒤 원장이 교체돼 차단으로 뒤집힌 경우: 정규화 값을 되돌린다.
        # (그대로 두면 "차단"이라 말하면서 정규화 값을 계속 소비하게 된다.)
        rollback = {"normalization_version": LEGACY_VERSION}
        if vi.net_debt_legacy is not None:
            rollback["net_debt"] = vi.net_debt_legacy
            rollback["net_debt_legacy"] = None
        return vi.model_copy(update=rollback)

    logger.info(
        "[%s] 순차입금 정규화 소비: legacy %s -> normalized %s (독립 합계 %s, 차이 %s)",
        vi.company.name,
        f"{res.legacy_value:,}",
        f"{res.value:,}",
        f"{res.independent_total:,}",
        res.delta,
    )
    return vi.model_copy(
        update={
            "net_debt": res.value,
            "net_debt_legacy": res.legacy_value,
            "normalization_version": res.normalization_version,
        }
    )


def run_valuation(vi: ValuationInput) -> ValuationResult:
    """Execute full valuation pipeline -- dispatch by methodology."""
    # P0-1 §2.1: 엔진의 공개 진입점은 load_profile()을 거치지 않은 ValuationInput도 받는다
    # (app.py, 테스트, 스크립트). 게이트를 load_profile()에만 두면 그 경로로 우회된다.
    # 멱등이므로 load_profile()에서 이미 통과한 입력은 그대로 통과한다.
    vi = apply_net_debt_gate(vi)

    # Auto-detect financial sector -> skip Hamada (copy to avoid mutating input)
    if is_financial(vi.industry):
        vi = vi.model_copy(
            update={
                "wacc_params": vi.wacc_params.model_copy(update={"is_financial": True})
            }
        )

    # Common: WACC (needed before method selection -- Ke used for DDM/RIM decision)
    # NOTE: WACC uses 2-component capital structure (equity + debt). When CPS/RCPS exist,
    # their cost differs from kd_pre but is not separately weighted — WACC may be understated.
    if vi.cps_principal or vi.rcps_principal:
        logger.warning(
            "CPS/RCPS present but WACC uses 2-component structure (Ke/Kd only) "
            "— preferred equity cost is not separately weighted"
        )
    wacc_result = calc_wacc(vi.wacc_params)
    um = vi.company.unit_multiplier

    # Determine methodology
    method = vi.valuation_method
    if method == "auto":
        # Calculate ROE for financial DDM/RIM decision
        by = vi.base_year
        cons = vi.consolidated[by]
        equity_bv = cons.get("equity", 0)
        net_income = cons.get("net_income", 0)
        roe = (net_income / equity_bv * 100) if equity_bv > 0 else 0.0

        seg_names = [info["name"] for info in vi.segments.values()]
        # de_ratio is pre-computed (interest-bearing debt / equity) during profile generation
        # Do NOT recompute from liabilities (that would include trade payables, inflating D/E)
        de_ratio = cons.get("de_ratio", 0.0)
        method = suggest_method(
            n_segments=len(vi.segments),
            legal_status=vi.company.legal_status,
            industry=vi.industry,
            has_peers=len(vi.peers) >= 3,
            roe=roe,
            ke=wacc_result.ke,
            has_ddm_params=vi.ddm_params is not None,
            has_rim_params=vi.rim_params is not None,
            has_rnpv_params=vi.rnpv_params is not None,
            segment_names=seg_names,
            de_ratio=de_ratio,
        )

    dispatch = {
        "sotp": _run_sotp_valuation,
        "ddm": _run_ddm_valuation,
        "rim": _run_rim_valuation,
        "nav": _run_nav_valuation,
        "multiples": _run_multiples_valuation,
        "dcf_primary": _run_dcf_valuation,
        "rnpv": _run_rnpv_valuation,
    }
    runner = dispatch.get(method, _run_dcf_valuation)
    result = runner(vi, wacc_result, um)
    result.valuation_bucket = infer_valuation_bucket(
        primary_method=result.primary_method,
        industry=vi.industry,
        has_holding_structure=bool(
            vi.company.holding_structure and vi.company.holding_structure.enabled
        ),
        has_optionality_segments=any(
            info.get("optionality") for info in vi.segments.values()
        ),
    )
    result.scenario_multiples_clamped = vi.scenario_multiples_clamped
    result.wide_scenario_spread_allowed = bool(
        vi.curated and vi.allow_wide_scenario_spread
    )
    result.scenario_spread_warnings = list(vi.scenario_spread_warnings)

    # Quality scoring (pure function, zero IO)
    result.quality = calc_quality_score(vi, result)
    result.draft = vi.draft
    result = _apply_investability_gate(vi, result)

    # Diagnostic relative-valuation layer (P/E, P/B, PEG/PEGY, justified multiples).
    # Purely additive; never blocks a valuation if inputs are missing.
    try:
        result.relative_valuation = _build_relative_valuation(vi, result, wacc_result)
    except Exception as e:  # pragma: no cover - defensive
        logger.debug("relative valuation skipped: %s", e)

    return result


def _dcf_per_share(vi: ValuationInput, result: ValuationResult) -> float | None:
    if result.dcf is None or result.dcf.ev_dcf <= 0:
        return None
    equity_value = result.dcf.ev_dcf - vi.net_debt
    if vi.valuation_shares <= 0:
        return None
    return per_share(equity_value, vi.company.unit_multiplier, vi.valuation_shares)


def _peer_median_per_share(result: ValuationResult) -> float | None:
    values = sorted(
        float(item.per_share)
        for item in result.cross_validations
        if item.per_share and item.per_share > 0 and item.method.upper() != "DCF"
    )
    if not values:
        return None
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2.0


def _raw_profile_for_gate(vi: ValuationInput, result: ValuationResult) -> dict:
    segments = {
        code: {
            **info,
            "revenue": vi.segment_data.get(vi.base_year, {})
            .get(code, {})
            .get("revenue"),
            "multiple": vi.multiples.get(code),
        }
        for code, info in vi.segments.items()
    }
    return {
        "primary_method": result.primary_method,
        "draft": vi.draft,
        "generated": vi.generated,
        "curated": vi.curated,
        "segments": segments,
        "optionality_flag": any(
            info.get("optionality") for info in vi.segments.values()
        ),
        "peer_beta_snapshot": vi.peer_beta_snapshot.model_dump(mode="json")
        if vi.peer_beta_snapshot
        else None,
    }


def _apply_investability_gate(
    vi: ValuationInput,
    result: ValuationResult,
) -> ValuationResult:
    cons = vi.consolidated.get(vi.base_year, {})
    raw = _raw_profile_for_gate(vi, result)
    inputs = gate_inputs_from_profile(
        raw,
        dcf_value=_dcf_per_share(vi, result),
        peer_median_value=_peer_median_per_share(result),
        quality_grade=result.quality.grade if result.quality else None,
        consolidated_revenue=cons.get("revenue"),
        text=vi.profile_text,
    )
    report = evaluate_investability(inputs)
    result.investability_blockers = report.blockers
    # The gate is one-way: it may mark a result draft, but never clears vi.draft.
    if report.draft:
        result.draft = True
        if result.quality is not None and not result.quality.draft:
            draft_vi = vi.model_copy(update={"draft": True})
            result.quality = calc_quality_score(draft_vi, result)
        if report.blockers:
            logger.info(
                "investability gate: not investable — %s",
                "; ".join(report.blockers),
            )
    return result


def _check_financial_basis_alignment(vi: ValuationInput) -> tuple[bool, str]:
    """Check whether base-year earnings and the applied capital structure align."""
    cons = vi.consolidated.get(vi.base_year, {})
    ri = vi.relative_inputs
    explicit_alignment = ri.basis_aligned if ri else None
    basis_note = ri.basis_note if ri else ""
    if explicit_alignment is False:
        return False, basis_note or "실적과 현재 자본구조의 기준일이 일치하지 않음"

    if explicit_alignment is None and "net_borr" in cons:
        base_net_debt = cons.get("net_borr", 0)
        current_net_debt = vi.net_debt
        net_debt_gap = abs(current_net_debt - base_net_debt)
        scale = max(abs(current_net_debt), abs(base_net_debt), 1)
        equity_scale = max(abs(cons.get("equity", 0)) * 0.10, 1)
        if net_debt_gap >= scale * 0.25 and net_debt_gap >= equity_scale:
            return False, (
                f"base-year 순차입금 {base_net_debt:,}과 현재 적용 순차입금 "
                f"{current_net_debt:,}의 차이 {net_debt_gap:,}이 중요성 기준을 초과 — "
                "거래 전 실적과 거래 후 자본구조 혼용 가능성"
            )

    return True, ""


def attach_gap_diagnostic(vi: ValuationInput, result: ValuationResult) -> None:
    """Attach reverse-DCF diagnostics only when the engine produced a valid primary DCF."""
    from engine.gap_diagnostics import GAP_THRESHOLD, diagnose_gap

    mc = result.market_comparison
    if mc is None or mc.market_price <= 0 or abs(mc.gap_ratio) < GAP_THRESHOLD:
        return

    if result.dcf is None:
        logger.warning(
            "Reverse DCF diagnostic skipped: engine DCF result is unavailable"
        )
        return
    if any(info.get("method") in ("pbv", "pe") for info in vi.segments.values()):
        logger.warning("Reverse DCF diagnostic skipped: equity-based SOTP segment")
        return

    basis_aligned, basis_note = _check_financial_basis_alignment(vi)
    if not basis_aligned:
        logger.warning("Reverse DCF diagnostic skipped: %s", basis_note)
        return

    cons = vi.consolidated.get(vi.base_year, {})
    da_base = cons.get("dep", 0) + cons.get("amort", 0)
    ebitda_base = cons.get("op", 0) + da_base
    revenue_base = cons.get("revenue", 0)
    if ebitda_base <= 0:
        logger.warning("Reverse DCF diagnostic skipped: base EBITDA is not positive")
        return

    shares = vi.valuation_shares
    market_cap_display = mc.market_price * shares / vi.company.unit_multiplier
    market_ev = market_cap_display + max(vi.net_debt, 0)

    try:
        diag = diagnose_gap(
            gap_ratio=mc.gap_ratio,
            market_price=mc.market_price,
            intrinsic_per_share=mc.intrinsic_value,
            market_ev=market_ev,
            ebitda_base=int(ebitda_base),
            da_base=int(da_base),
            revenue_base=int(revenue_base),
            wacc_pct=result.wacc.wacc,
            params=vi.dcf_params,
            holding_discount_applied=bool(
                result.holding_discount and result.holding_discount.enabled
            ),
            de_ratio=cons.get("de_ratio", 0.0),
            industry=vi.industry,
        )
        if diag:
            result.gap_diagnostic = GapDiagnostic(**diag.__dict__)
    except Exception as exc:
        logger.debug("Gap diagnostics failed: %s", exc)


def _attach_reverse_rnpv(vi: ValuationInput, result: ValuationResult) -> None:
    """Attach reverse-rNPV diagnostics after a market price is available."""
    if result.primary_method != "rnpv" or not vi.rnpv_params:
        return

    market = result.market_comparison
    if market is None or market.market_price <= 0:
        return

    from engine.reverse_rnpv import reverse_rnpv
    from schemas.models import (
        ReverseRNPVDrugImplied,
        ReverseRNPVDrugSolo,
        ReverseRNPVResult,
    )

    market_cap = (
        market.market_price * vi.company.shares_outstanding / vi.company.unit_multiplier
    )
    market_ev = market_cap + max(vi.net_debt, 0)
    model_ev = float(result.rnpv.enterprise_value) if result.rnpv else 0

    try:
        raw = reverse_rnpv(
            target_ev=market_ev,
            model_ev=model_ev,
            pipeline=[drug.model_dump() for drug in vi.rnpv_params.pipeline],
            discount_rate=vi.rnpv_params.discount_rate or result.wacc.wacc,
            r_and_d_cost=vi.rnpv_params.r_and_d_cost,
            decline_rate=vi.rnpv_params.decline_rate,
            default_margin=vi.rnpv_params.default_margin,
            tax_rate=vi.rnpv_params.tax_rate,
        )
        result.reverse_rnpv = ReverseRNPVResult(
            target_ev=raw.target_ev,
            model_ev=raw.model_ev,
            gap_pct=raw.gap_pct,
            implied_pos_scale=raw.implied_pos_scale,
            implied_peak_scale=raw.implied_peak_scale,
            implied_discount_rate=raw.implied_discount_rate,
            implied_pos_per_drug=[
                ReverseRNPVDrugImplied(
                    name=item["name"],
                    base_value=item["base_pos"],
                    implied_value=item["implied_pos"],
                )
                for item in raw.implied_pos_per_drug
            ],
            implied_peak_per_drug=[
                ReverseRNPVDrugImplied(
                    name=item["name"],
                    base_value=item["base_peak"],
                    implied_value=item["implied_peak"],
                )
                for item in raw.implied_peak_per_drug
            ],
            implied_pos_solo=[
                ReverseRNPVDrugSolo(
                    name=item["name"],
                    phase=item["phase"],
                    base_pos=item["base_pos"],
                    implied_pos=item["implied_pos"],
                    solvable=item["solvable"],
                    max_ev_contribution=item["max_ev_contribution"],
                    skipped=item["skipped"],
                )
                for item in raw.implied_pos_solo
            ],
        )
    except Exception as exc:
        logger.debug("Reverse rNPV failed: %s", exc)


def enrich_market_dependent_result(
    vi: ValuationInput, result: ValuationResult
) -> ValuationResult:
    """Attach all diagnostics that require a selected market price."""
    market = result.market_comparison
    if market is None or market.market_price <= 0:
        return result

    if result.relative_valuation is None:
        try:
            vi_priced = vi.model_copy(update={"market_price": market.market_price})
            result.relative_valuation = _build_relative_valuation(
                vi_priced, result, result.wacc
            )
        except Exception as exc:
            logger.debug("Relative valuation enrichment skipped: %s", exc)
    attach_gap_diagnostic(vi, result)
    _attach_reverse_rnpv(vi, result)
    return result


def _build_relative_valuation(vi: ValuationInput, result: ValuationResult, wacc_result):
    """Assemble diagnostic relative-valuation ratios from live inputs.

    Returns None when market price or share count is unavailable (ratios are
    undefined without a current price). Sector guardrails suppress PEG for
    financials/cyclicals/low-growth names (see engine/relative_metrics.py).
    """
    from engine import relative_metrics as rm
    from engine.growth import calc_ebitda_growth
    from engine.distress import _CYCLICAL_KEYWORDS
    from schemas.models import RelativeValuation, RelMetric, RelVerdict

    diagnostics_enabled = any(
        multiple > 0
        for multiple in (
            vi.pe_multiple,
            vi.ev_revenue_multiple,
            vi.pbv_multiple,
            vi.ps_multiple,
            vi.pffo_multiple,
        )
    )
    if not diagnostics_enabled:
        return None

    price = vi.market_price
    company = vi.company
    shares = vi.valuation_shares
    if not price or price <= 0 or shares <= 0:
        return None

    um = company.unit_multiplier
    cons = vi.consolidated.get(vi.base_year, {})
    ri = vi.relative_inputs
    basis_aligned, basis_note = _check_financial_basis_alignment(vi)
    if not basis_aligned:
        return RelativeValuation(
            basis_aligned=False,
            basis_note=basis_note,
        )

    net_income = cons.get("net_income", 0)
    equity = cons.get("equity", 0)
    revenue = cons.get("revenue", 0)
    ebitda = cons.get("op", 0) + cons.get("dep", 0) + cons.get("amort", 0)
    net_debt = vi.net_debt
    ke = wacc_result.ke

    market_cap = price * shares / um
    # Trailing EPS: prefer fetched (diluted, continuing-ops) over model-derived.
    eps = (
        ri.trailing_eps
        if (ri and ri.trailing_eps is not None)
        else per_share(net_income, um, shares)
    )
    bvps = per_share(equity, um, shares)

    industry = vi.industry or company.industry or ""
    financial = result.primary_method in ("ddm", "rim") or is_financial(industry)
    cyclical = any(kw in industry.lower() for kw in _CYCLICAL_KEYWORDS)

    # Growth for PEG/PEGY/justified: prefer analyst consensus, fall back to model CAGR.
    if ri and ri.earnings_growth is not None:
        growth_pct = round(ri.earnings_growth, 2)
        growth_source = ri.growth_source or "analyst consensus"
    else:
        g_dec = calc_ebitda_growth(vi.consolidated)
        growth_pct = round(g_dec * 100, 2) if g_dec is not None else None
        growth_source = "model EBITDA CAGR"

    m_pe = rm.trailing_pe(price, eps)
    m_pb = rm.price_to_book(price, bvps)
    ratios = [
        m_pe,
        m_pb,
        rm.ev_ebitda(market_cap, net_debt, ebitda),
        rm.ev_sales(market_cap, net_debt, revenue),
    ]
    # Forward P/E when a forward EPS estimate is available.
    fwd_eps = ri.forward_eps if ri else None
    if fwd_eps is not None:
        ratios.insert(1, rm.forward_pe(price, fwd_eps))

    # Dividend yield: DPS-derived (reliable) preferred; else fetched yield.
    dps = vi.ddm_params.dps if vi.ddm_params else None
    m_dy = None
    if dps is not None:
        m_dy = rm.dividend_yield(dps, price)
    elif ri and ri.dividend_yield is not None:
        m_dy = rm.RelativeMetric(
            "Div Yield", round(ri.dividend_yield, 2), rm.OK, "시장 데이터"
        )
    if m_dy is not None:
        ratios.append(m_dy)

    div_y = m_dy.value if (m_dy and m_dy.value is not None) else 0.0
    ratios.append(
        rm.peg(
            m_pe.value,
            growth_pct,
            is_financial=financial,
            is_cyclical=cyclical,
            growth_source=growth_source,
        )
    )
    ratios.append(
        rm.pegy(
            m_pe.value,
            growth_pct,
            div_y,
            is_financial=financial,
            is_cyclical=cyclical,
            growth_source=growth_source,
        )
    )

    roe = (net_income / equity * 100) if equity > 0 else None
    payout = vi.rim_params.payout_ratio if vi.rim_params else None
    just_g = growth_pct if growth_pct is not None else 0.0
    verdicts = []
    if payout:
        jpe = rm.justified_pe(payout, just_g, ke)
        if jpe.is_meaningful and jpe.value > 0:
            v = rm.multiple_verdict("P/E", m_pe.value, jpe.value)
            verdicts.append(
                RelVerdict(
                    name=v.name,
                    actual=v.actual,
                    justified=v.justified,
                    gap_pct=v.gap_pct,
                    verdict=v.verdict,
                    note=v.note,
                )
            )
    if roe is not None:
        jpb = rm.justified_pb(roe, just_g, ke)
        if jpb.is_meaningful and jpb.value > 0:
            v = rm.multiple_verdict("P/B", m_pb.value, jpb.value)
            verdicts.append(
                RelVerdict(
                    name=v.name,
                    actual=v.actual,
                    justified=v.justified,
                    gap_pct=v.gap_pct,
                    verdict=v.verdict,
                    note=v.note,
                )
            )

    return RelativeValuation(
        ratios=[
            RelMetric(name=m.name, value=m.value, status=m.status, note=m.note)
            for m in ratios
        ],
        verdicts=verdicts,
        growth_pct=growth_pct,
        growth_source=growth_source,
    )


def _apply_holding_discount_to_scenario(
    scenario_result,
    net_equity_value: int,
    dlom_pct: float,
    prob_pct: float,
    unit_multiplier: int,
):
    """Replace scenario equity/per-share outputs with holding-discounted net equity."""
    pre_dlom = per_share(net_equity_value, unit_multiplier, scenario_result.shares)
    if net_equity_value > 0:
        post_dlom = round(pre_dlom * (1 - dlom_pct / 100))
    else:
        post_dlom = pre_dlom
    return scenario_result.model_copy(
        update={
            "equity_value": net_equity_value,
            "pre_dlom": pre_dlom,
            "post_dlom": post_dlom,
            "weighted": round(post_dlom * prob_pct / 100),
        }
    )


def _calc_effective_net_debt(vi: ValuationInput) -> int:
    """Calculate effective net debt for financial subsidiary split SOTP.

    Net debt of financial segments (method=pbv/pe) is already embedded in P/BV,
    so it is deducted from total net_debt. Returns net_debt as-is if segment_net_debt is empty.
    """
    has_pbv_pe = any(
        info.get("method") in ("pbv", "pe") for info in vi.segments.values()
    )
    if not vi.segment_net_debt:
        if has_pbv_pe:
            logger.warning(
                "PBV/PE segments present but segment_net_debt is empty — "
                "full net_debt will be deducted, risking double-counting"
            )
        return vi.net_debt
    financial_debt = sum(
        vi.segment_net_debt[c]
        for c, info in vi.segments.items()
        if info.get("method") in ("pbv", "pe") and c in vi.segment_net_debt
    )
    return vi.net_debt - financial_debt


def _has_mixed_sotp(vi: ValuationInput) -> bool:
    """Determine if this is a financial subsidiary split SOTP."""
    return bool(vi.segment_net_debt) and any(
        info.get("method") in ("pbv", "pe") for info in vi.segments.values()
    )


def _needs_method_dispatch(vi: ValuationInput) -> bool:
    """True if any segment uses a non-default method (ev_revenue, pbv, pe)."""
    return any(
        info.get("method") not in (None, "ev_ebitda") for info in vi.segments.values()
    )


def _run_sotp_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """SOTP-based valuation (multi-segment companies, Mixed Method support)."""
    by = vi.base_year
    cons = vi.consolidated[by]

    # Financial subsidiary split SOTP check
    has_equity_segments = any(
        info.get("method") in ("pbv", "pe") for info in vi.segments.values()
    )
    is_mixed = _has_mixed_sotp(vi)
    needs_dispatch = is_mixed or _needs_method_dispatch(vi)
    effective_net_debt = _calc_effective_net_debt(vi) if is_mixed else vi.net_debt

    # Extract segment method info
    seg_methods = {
        c: info.get("method", "ev_ebitda") for c, info in vi.segments.items()
    }

    # D&A allocation (all years) -- excluding financial segments
    da_allocations = {}
    for yr, segs in vi.segment_data.items():
        c = vi.consolidated[yr]
        total_da = c["dep"] + c["amort"]
        da_allocations[yr] = allocate_da(
            segs, total_da, seg_methods if needs_dispatch else None
        )

    # Financial distress discount on multiples
    distress = calc_distress_discount(
        vi.consolidated,
        by,
        market=vi.company.market,
        kd_pre=vi.wacc_params.kd_pre,
        industry=vi.industry,
        max_discount=vi.distress_max_discount,
    )
    # ev_revenue and distress_exempt segments keep original multiples
    exempt = {
        c
        for c, info in vi.segments.items()
        if info.get("method") == "ev_revenue" or info.get("distress_exempt")
    }
    # Healthy segments: profitable (op > 0) AND significant asset share (>= 20%)
    # in diversified companies get half discount.
    # Asset share criterion prevents tiny profitable segments from masking distress.
    healthy: set[str] = set()
    if len(vi.segments) >= 3 and distress.applied:
        base_seg_data = vi.segment_data.get(by, {})
        total_seg_assets = sum(
            base_seg_data.get(c, {}).get("assets", 0) for c in vi.segments
        )
        healthy = {
            c
            for c in vi.segments
            if c not in exempt
            and base_seg_data.get(c, {}).get("op", 0) > 0
            and (
                total_seg_assets == 0
                or base_seg_data.get(c, {}).get("assets", 0) / total_seg_assets * 100
                >= _HEALTHY_MIN_ASSET_SHARE_PCT
            )
        }
    effective_multiples = apply_distress_discount(
        vi.multiples,
        distress.discount,
        exempt,
        healthy,
    )
    if distress.applied:
        logger.info("[Distress] %s: %s", vi.company.name, distress.detail)

    # Build segment revenue map for ev_revenue segments
    seg_revenue = {
        c: vi.segment_data.get(by, {}).get(c, {}).get("revenue", 0) for c in vi.segments
    }

    # SOTP (base year) -- Mixed Method support
    if by not in da_allocations:
        raise ValueError(
            f"base_year({by})에 해당하는 segment_data가 없습니다. "
            f"사용 가능한 연도: {sorted(da_allocations.keys()) or list(vi.segment_data.keys())}"
        )
    base_alloc = da_allocations[by]
    sotp, total_ev = calc_sotp(
        base_alloc,
        effective_multiples,
        segments_info=vi.segments if needs_dispatch else None,
        revenue_by_seg=seg_revenue if needs_dispatch else None,
    )
    base_holding_bridge = None

    # Pre-resolve news drivers so the differentiation check sees
    # active_drivers contributions to growth_adj_pct / market_sentiment_pct.
    resolved_scenarios = {
        code: resolve_drivers(sc, vi.news_drivers) for code, sc in vi.scenarios.items()
    }
    if _sotp_scenarios_undifferentiated(list(resolved_scenarios.values())):
        logger.warning(
            "SOTP 시나리오에 EV 드라이버(segment_multiples/segment_ebitda/"
            "segment_method_override/growth_adj_pct/market_sentiment_pct) "
            "및 equity bridge(irr/cps_irr/rcps_irr/dlom/cps_repay/rcps_repay/"
            "buyback/shares) 모두 미차등 — 모든 시나리오 동일 가치. "
            "--auto로 재생성하거나 YAML 보강."
        )

    # Scenarios -- apply per-scenario SOTP overrides + market_sentiment_pct
    scenario_results = {}
    total_weighted = 0
    for code, sc in resolved_scenarios.items():
        # Per-scenario SOTP: recalculate if drivers are set
        needs_recalc = (
            sc.segment_ebitda
            or sc.segment_multiples
            or sc.segment_revenue
            or sc.segment_method_override
            or sc.growth_adj_pct != 0
        )
        if needs_recalc:
            # Apply growth_adj_pct to base EBITDA allocation
            adj_alloc = base_alloc
            if sc.growth_adj_pct != 0:
                mult = 1 + sc.growth_adj_pct / 100
                adj_alloc = {
                    c: alloc.model_copy(update={"ebitda": round(alloc.ebitda * mult)})
                    for c, alloc in base_alloc.items()
                }

            # Method transition: merge overrides into segments_info copy
            sc_segments = vi.segments if needs_dispatch else None
            if sc.segment_method_override:
                sc_segments = {
                    c: {
                        **info,
                        "method": sc.segment_method_override.get(
                            c, info.get("method", "ev_ebitda")
                        ),
                    }
                    for c, info in vi.segments.items()
                }
                # Re-allocate D&A for method transitions (ev_revenue→ev_ebitda gets D&A)
                sc_seg_methods = {
                    c: sc_segments[c].get("method", "ev_ebitda") for c in sc_segments
                }
                total_da = cons["dep"] + cons["amort"]
                adj_alloc = allocate_da(vi.segment_data[by], total_da, sc_seg_methods)
                if sc.growth_adj_pct != 0:
                    gm = 1 + sc.growth_adj_pct / 100
                    adj_alloc = {
                        c: alloc.model_copy(update={"ebitda": round(alloc.ebitda * gm)})
                        for c, alloc in adj_alloc.items()
                    }

            _, sc_ev = calc_sotp(
                adj_alloc,
                effective_multiples,
                segments_info=sc_segments,
                ebitda_override=sc.segment_ebitda,
                multiple_override=sc.segment_multiples,
                revenue_by_seg=seg_revenue if needs_dispatch else None,
                revenue_override=sc.segment_revenue,
            )
        else:
            sc_ev = total_ev

        # Market sentiment is cumulative
        if sc.market_sentiment_pct != 0:
            sc_ev = round(sc_ev * (1 + sc.market_sentiment_pct / 100))
        r = calc_scenario(
            sc,
            sc_ev,
            effective_net_debt,
            vi.eco_frontier,
            vi.cps_principal,
            vi.cps_years,
            vi.rcps_principal,
            vi.rcps_years,
            um,
            vi.cps_dividend_rate,
            vi.rcps_dividend_rate,
        )
        if vi.company.holding_structure and vi.company.holding_structure.enabled:
            bridge = build_holding_discount_bridge(
                gross_sotp_value=sc_ev,
                gross_equity_value=r.equity_value,
                holding_structure=vi.company.holding_structure,
            )
            if bridge is not None:
                r = _apply_holding_discount_to_scenario(
                    r,
                    bridge.net_equity_value,
                    sc.dlom,
                    sc.prob,
                    um,
                )
                if code == "Base" or base_holding_bridge is None:
                    base_holding_bridge = bridge
        scenario_results[code] = r
        total_weighted += r.weighted

    # DCF cross-validation -- for mixed SOTP, manufacturing segments only
    total_da_base = cons["dep"] + cons["amort"]
    if is_mixed:
        mfg_ebitda = sum(
            alloc.ebitda
            for c, alloc in base_alloc.items()
            if seg_methods.get(c, "ev_ebitda") == "ev_ebitda"
        )
        mfg_da = sum(
            alloc.da_allocated
            for c, alloc in base_alloc.items()
            if seg_methods.get(c, "ev_ebitda") == "ev_ebitda"
        )
        mfg_revenue = sum(
            vi.segment_data[by][c].get("revenue", 0)
            for c in vi.segment_data[by]
            if seg_methods.get(c, "ev_ebitda") == "ev_ebitda"
        )
        ebitda_base = mfg_ebitda
        dcf_da_base = mfg_da
        dcf_revenue = mfg_revenue
    else:
        ebitda_base = cons["op"] + total_da_base
        dcf_da_base = total_da_base
        dcf_revenue = cons["revenue"]

    dcf_result = None
    try:
        dcf_result = calc_dcf(
            ebitda_base,
            dcf_da_base,
            dcf_revenue,
            wacc_result.wacc,
            vi.dcf_params,
            vi.base_year,
        )
    except ValueError:
        logger.warning("SOTP DCF cross-validation skipped (ebitda<=0 or wacc<=tg)")

    # Sensitivity
    ref_sc = _get_reference_scenario(vi.scenarios)
    sens_mult, _, _ = sensitivity_multiples(
        base_alloc,
        effective_multiples,
        effective_net_debt,
        vi.eco_frontier,
        vi.valuation_shares,
        unit_multiplier=um,
        segments_info=vi.segments if needs_dispatch else None,
        revenue_by_seg=seg_revenue if needs_dispatch else None,
        cps_repay=round(
            vi.cps_principal
            * (
                1
                + max(
                    (
                        (ref_sc.cps_irr if ref_sc.cps_irr is not None else ref_sc.irr)
                        if ref_sc
                        else 0
                    )
                    - vi.cps_dividend_rate,
                    0,
                )
                / 100
            )
            ** vi.cps_years
        )
        if vi.cps_principal
        else 0,
        rcps_repay=_derive_rcps_repay(ref_sc, vi),
        buyback=ref_sc.buyback if ref_sc else 0,
    )
    if not sens_mult:
        logger.warning(
            "SOTP multiple sensitivity skipped: two segments with positive "
            "multiples and usable valuation metrics are required"
        )
    if vi.cps_principal > 0 or vi.rcps_principal > 0:
        sens_irr, _, _ = sensitivity_irr_dlom(
            total_ev,
            effective_net_debt,
            vi.eco_frontier,
            vi.cps_principal,
            vi.cps_years,
            _derive_rcps_repay(ref_sc, vi),
            ref_sc.buyback if ref_sc else 0,
            vi.valuation_shares,
            unit_multiplier=um,
            cps_dividend_rate=vi.cps_dividend_rate,
            rcps_principal=vi.rcps_principal,
            rcps_years=vi.rcps_years,
            rcps_dividend_rate=vi.rcps_dividend_rate,
        )
    else:
        sens_irr = []
    sens_dcf_rows = []
    if dcf_result is not None:
        try:
            sens_dcf_rows, _, _ = sensitivity_dcf(
                ebitda_base,
                dcf_da_base,
                dcf_revenue,
                vi.dcf_params,
                vi.base_year,
                wacc_base=wacc_result.wacc,
                shares=vi.valuation_shares,
                net_debt=vi.net_debt,
                unit_multiplier=um,
            )
        except (ValueError, ZeroDivisionError):
            logger.warning("SOTP DCF sensitivity skipped (invalid base DCF)")

    # Multiple cross-validation -- apply effective_net_debt
    # Exclude pbv/pe equity-based segments from implied EV/EBITDA (they inflate the multiple).
    sotp_ev_ev_only = sum(r.ev for r in sotp.values() if not r.is_equity_based)
    cv_items = _cross_validate_common(
        vi,
        cons,
        ebitda_base,
        total_ev,
        dcf_result.ev_dcf if dcf_result else 0,
        um,
        net_debt_override=effective_net_debt if has_equity_segments else None,
        sotp_ev_ebitda_only=sotp_ev_ev_only,
    )
    if any(method != "ev_ebitda" for method in seg_methods.values()):
        cv_items = [
            item.model_copy(
                update={"method": "SOTP (Mixed)", "metric_value": 0, "multiple": 0}
            )
            if item.method == "SOTP (EV/EBITDA)"
            else item
            for item in cv_items
        ]

    # Monte Carlo
    sotp_seg_ebitdas = {code: base_alloc[code].ebitda for code in vi.segments}
    mc_result = _run_monte_carlo(
        vi,
        wacc_result,
        sotp_seg_ebitdas,
        um,
        dcf_result=dcf_result if dcf_result else None,
        effective_multiples=effective_multiples,
        seg_revenues=seg_revenue,
        segment_methods=seg_methods,
        net_debt_override=effective_net_debt if has_equity_segments else None,
    )

    # Peer statistics
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(
        vi.peers,
        vi.multiples,
        seg_names,
        segment_methods=seg_methods,
    )

    return ValuationResult(
        primary_method="sotp",
        wacc=wacc_result,
        da_allocations={
            yr: {c: a for c, a in allocs.items()}
            for yr, allocs in da_allocations.items()
        },
        sotp=sotp,
        total_ev=total_ev,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        dcf=dcf_result,
        cross_validations=cv_items,
        peer_stats=peer_stats,
        monte_carlo=mc_result,
        sensitivity_multiples=sens_mult,
        sensitivity_irr_dlom=sens_irr,
        sensitivity_dcf=sens_dcf_rows,
        holding_discount=base_holding_bridge,
    )


def _make_scenario_dcf_params(
    base: DCFParams,
    sc: ScenarioParams,
    wacc: float,
) -> DCFParams | None:
    """Generate per-scenario DCF parameters. Returns None if no adjustments."""
    if sc.growth_adj_pct == 0 and sc.terminal_growth_adj == 0:
        return None
    adjusted_rates = [
        g * (1 + sc.growth_adj_pct / 100) for g in base.ebitda_growth_rates
    ]
    adjusted_tg = base.terminal_growth + sc.terminal_growth_adj
    # Safety: floor at 0% (negative TGR implies perpetual shrinkage), cap below WACC
    adjusted_tg = max(0.0, min(adjusted_tg, wacc - 0.5))
    return base.model_copy(
        update={
            "ebitda_growth_rates": adjusted_rates,
            "terminal_growth": adjusted_tg,
        }
    )


def _run_dcf_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """DCF-based valuation (single-segment or growth companies)."""
    by = vi.base_year
    cons = vi.consolidated[by]

    total_da_base = cons["dep"] + cons["amort"]
    ebitda_base = cons["op"] + total_da_base

    # DCF (primary)
    dcf_result = calc_dcf(
        ebitda_base,
        total_da_base,
        cons["revenue"],
        wacc_result.wacc,
        vi.dcf_params,
        vi.base_year,
    )
    total_ev = dcf_result.ev_dcf

    # Scenarios (DCF EV-based, per-scenario DCF driver + WACC adjustment applied)
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        sc = resolve_drivers(sc, vi.news_drivers)
        sc_ev = total_ev  # Default: base DCF EV

        # Per-scenario WACC adjustment
        sc_wacc = _adjust_wacc(wacc_result, sc.wacc_adj, vi.wacc_params.eq_w)
        effective_wacc = sc_wacc.wacc

        # Per-scenario DCF driver adjustment
        sc_dcf_params = _make_scenario_dcf_params(vi.dcf_params, sc, effective_wacc)
        if sc_dcf_params is not None:
            try:
                sc_dcf = calc_dcf(
                    ebitda_base,
                    total_da_base,
                    cons["revenue"],
                    effective_wacc,
                    sc_dcf_params,
                    vi.base_year,
                )
                sc_ev = sc_dcf.ev_dcf
            except (ValueError, ZeroDivisionError):
                logger.warning(
                    "DCF scenario '%s' recalc failed (wacc<=tg), using base EV", code
                )
        elif sc.wacc_adj != 0:
            # Recalculate DCF even without growth adjustment (WACC change alone)
            try:
                sc_dcf = calc_dcf(
                    ebitda_base,
                    total_da_base,
                    cons["revenue"],
                    effective_wacc,
                    vi.dcf_params,
                    vi.base_year,
                )
                sc_ev = sc_dcf.ev_dcf
            except (ValueError, ZeroDivisionError):
                logger.warning(
                    "DCF scenario '%s' WACC recalc failed, using base EV", code
                )

        # Market sentiment post-processing
        if sc.market_sentiment_pct != 0:
            sc_ev = round(sc_ev * (1 + sc.market_sentiment_pct / 100))

        r = calc_scenario(
            sc,
            sc_ev,
            vi.net_debt,
            vi.eco_frontier,
            vi.cps_principal,
            vi.cps_years,
            vi.rcps_principal,
            vi.rcps_years,
            um,
            vi.cps_dividend_rate,
            vi.rcps_dividend_rate,
        )
        scenario_results[code] = r
        total_weighted += r.weighted

    # DCF sensitivity
    sens_dcf_rows = []
    try:
        sens_dcf_rows, _, _ = sensitivity_dcf(
            ebitda_base,
            total_da_base,
            cons["revenue"],
            vi.dcf_params,
            vi.base_year,
            wacc_base=wacc_result.wacc,
            shares=vi.valuation_shares,
            net_debt=vi.net_debt,
            unit_multiplier=um,
        )
    except (ValueError, ZeroDivisionError):
        logger.warning("DCF sensitivity skipped (invalid wacc/tg range)")

    # SOTP cross-validation (calculate SOTP if multi-segment)
    sotp_ev = 0
    sotp_result = {}
    da_allocations = {}
    if len(vi.segments) > 1 and by in vi.segment_data:
        da_allocations[by] = allocate_da(vi.segment_data[by], total_da_base)
        _cv_seg_revenue = {
            c: vi.segment_data.get(by, {}).get(c, {}).get("revenue", 0)
            for c in vi.segments
        }
        sotp_result, sotp_ev = calc_sotp(
            da_allocations[by],
            vi.multiples,
            segments_info=vi.segments if len(vi.segments) > 1 else None,
            revenue_by_seg=_cv_seg_revenue,
        )

    sotp_ev_ev_only = sum(r.ev for r in sotp_result.values() if not r.is_equity_based)
    cv_items = _cross_validate_common(
        vi,
        cons,
        ebitda_base,
        sotp_ev,
        dcf_result.ev_dcf,
        um,
        sotp_ev_ebitda_only=sotp_ev_ev_only,
    )

    # Peer statistics
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    # Monte Carlo
    mc_result = _run_monte_carlo(
        vi,
        wacc_result,
        _build_seg_ebitdas_from_consolidated(vi, cons),
        um,
        dcf_result=dcf_result,
    )

    return ValuationResult(
        primary_method="dcf_primary",
        wacc=wacc_result,
        da_allocations={
            yr: {c: a for c, a in allocs.items()}
            for yr, allocs in da_allocations.items()
        },
        sotp=sotp_result,
        total_ev=total_ev,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        dcf=dcf_result,
        cross_validations=cv_items,
        peer_stats=peer_stats,
        sensitivity_dcf=sens_dcf_rows,
        monte_carlo=mc_result,
    )


def _run_ddm_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """DDM-based valuation (financial sector)."""
    if not vi.ddm_params:
        raise ValueError(
            "DDM 방법론이 선택되었으나 ddm_params가 없습니다. "
            "YAML에 ddm_params: {dps: ..., dividend_growth: ...}를 추가하세요."
        )

    ke = wacc_result.ke
    buyback_ps = vi.ddm_params.buyback_per_share
    base_growth = vi.ddm_params.dividend_growth

    if ke <= 0:
        raise ValueError(
            f"Ke({ke:.2f}%)가 0 이하입니다. DDM은 양의 자본비용이 필요합니다. "
            "WACC 파라미터(rf, erp, bu)를 확인하세요."
        )

    # Base DDM (default growth rate)
    ddm_raw = calc_ddm_engine(
        vi.ddm_params.dps,
        base_growth,
        ke,
        buyback_per_share=buyback_ps,
    )
    ddm_result = DDMValuationResult(
        dps=ddm_raw.dps,
        buyback_per_share=ddm_raw.buyback_per_share,
        total_payout=ddm_raw.total_payout,
        growth=ddm_raw.growth,
        ke=ddm_raw.ke,
        equity_per_share=ddm_raw.equity_per_share,
        warnings=ddm_raw.warnings,
    )

    # Per-scenario DDM: recalculate with ddm_growth + wacc_adj (Ke adjustment)
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        sc = resolve_drivers(sc, vi.news_drivers)
        sc_growth = sc.ddm_growth if sc.ddm_growth is not None else base_growth
        sc_wacc = _adjust_wacc(wacc_result, sc.wacc_adj, vi.wacc_params.eq_w)
        sc_ke = sc_wacc.ke
        try:
            if sc_ke <= 0:
                raise ValueError(f"sc_ke={sc_ke:.2f}% <= 0")
            sc_ddm = calc_ddm_engine(
                vi.ddm_params.dps,
                sc_growth,
                sc_ke,
                buyback_per_share=buyback_ps,
            )
            # DDM yields equity directly; add net_debt to get EV for calc_scenario bridge
            sc_eq = sc_ddm.equity_per_share * vi.valuation_shares // (um or 1)
        except ValueError:
            logger.warning(
                "DDM scenario '%s' failed (growth>=Ke or Ke<=0), using base DDM", code
            )
            sc_eq = ddm_raw.equity_per_share * vi.valuation_shares // (um or 1)

        # Apply sentiment to equity (not pseudo-EV) — avoids leverage amplification
        # for high-D/E financial companies where equity << net_debt.
        if sc.market_sentiment_pct != 0:
            sc_eq = round(sc_eq * (1 + sc.market_sentiment_pct / 100))
        sc_ev = sc_eq + vi.net_debt

        # DDM yields common equity directly (DPS/Ke-g); CPS/RCPS are already excluded
        # from common dividends — passing them to calc_scenario would double-deduct.
        # net_debt cancel-out (added to sc_ev above, subtracted here) is intentional.
        r = calc_scenario(
            sc, sc_ev, vi.net_debt, vi.eco_frontier, 0, 0, 0, 0, um, 0.0, 0.0
        )
        scenario_results[code] = r
        total_weighted += r.weighted

    # DDM base EV (for cross-validation): DDM equity + net_debt = EV
    total_ev = ddm_raw.equity_per_share * vi.valuation_shares // (um or 1) + vi.net_debt

    # Use DDM value directly when no scenarios are set
    if not scenario_results:
        total_weighted = ddm_raw.equity_per_share

    # EBITDA-based DCF is meaningless for financials -> P/E, P/BV cross-validation only
    by = vi.base_year
    cons = vi.consolidated[by]
    cv_items = _cross_validate_financial(vi, cons, um)

    # Peer statistics
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    # DDM sensitivity: Ke x dividend growth rate
    sens_ddm = sensitivity_ddm(
        vi.ddm_params.dps,
        ke,
        base_growth,
        buyback_per_share=buyback_ps,
    )

    # Monte Carlo (segment EBITDA-based -- auxiliary distribution)
    mc_result = _run_monte_carlo(
        vi, wacc_result, _build_seg_ebitdas_from_consolidated(vi, cons), um
    )

    return ValuationResult(
        primary_method="ddm",
        wacc=wacc_result,
        total_ev=total_ev,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        ddm=ddm_result,
        cross_validations=cv_items,
        peer_stats=peer_stats,
        monte_carlo=mc_result,
        sensitivity_primary=sens_ddm,
        sensitivity_primary_label=f"Ke × 배당성장률 → 주당가치 ({vi.company.currency_unit})",
    )


def _run_rim_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """RIM (Residual Income Model) valuation (financial sector -- BV-based)."""
    by = vi.base_year
    cons = vi.consolidated[by]
    equity_bv = cons.get("equity", 0)
    shares = vi.valuation_shares
    ke = wacc_result.ke

    # RIM parameters: explicit rim_params or auto-generated from financial statements
    if vi.rim_params:
        roe_forecasts = vi.rim_params.roe_forecasts
        tg = vi.rim_params.terminal_growth
        payout = vi.rim_params.payout_ratio
    else:
        # Back-calculate ROE from recent financials for 5-year forecast (gradual convergence)
        net_income = cons.get("net_income", 0)
        current_roe = (net_income / equity_bv * 100) if equity_bv > 0 else ke
        # ROE gradually converges toward Ke (5 years, fully reaching Ke at year 5)
        roe_forecasts = [
            round(current_roe + (ke - current_roe) * i / 5, 1) for i in range(1, 6)
        ]
        tg = 0.0
        payout = 30.0

    rim_raw = calc_rim_engine(
        book_value=equity_bv,
        roe_forecasts=roe_forecasts,
        ke=ke,
        terminal_growth=tg,
        shares=shares,
        unit_multiplier=um,
        payout_ratio=payout,
    )
    rim_result = RIMValuationResult(
        bv_current=rim_raw.bv_current,
        ke=rim_raw.ke,
        terminal_growth=rim_raw.terminal_growth,
        projections=[
            RIMProjectionResult(
                year=p.year,
                bv=p.bv,
                net_income=p.net_income,
                roe=p.roe,
                ri=p.ri,
                pv_ri=p.pv_ri,
            )
            for p in rim_raw.projections
        ],
        pv_ri_sum=rim_raw.pv_ri_sum,
        terminal_ri=rim_raw.terminal_ri,
        pv_terminal=rim_raw.pv_terminal,
        equity_value=rim_raw.equity_value,
        per_share=rim_raw.per_share,
    )

    # RIM directly yields Equity Value -> reverse-calculate EV
    total_ev = rim_raw.equity_value + vi.net_debt

    # Scenarios -- recalculate RIM with rim_roe_adj + wacc_adj (Ke adjustment)
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        sc = resolve_drivers(sc, vi.news_drivers)
        sc_eq = (
            rim_raw.equity_value
        )  # track equity separately to avoid leverage amplification
        sc_wacc = _adjust_wacc(wacc_result, sc.wacc_adj, vi.wacc_params.eq_w)
        sc_ke = sc_wacc.ke
        needs_recalc = (sc.rim_roe_adj != 0) or (sc.wacc_adj != 0)
        if needs_recalc:
            adj_roes = [r + sc.rim_roe_adj for r in roe_forecasts]
            try:
                sc_rim = calc_rim_engine(
                    book_value=equity_bv,
                    roe_forecasts=adj_roes,
                    ke=sc_ke,
                    terminal_growth=tg,
                    shares=shares,
                    unit_multiplier=um,
                    payout_ratio=payout,
                )
                sc_eq = sc_rim.equity_value
            except ValueError as e:
                logger.warning("RIM scenario '%s' failed: %s", code, e)

        # Apply sentiment to equity (not pseudo-EV) — avoids leverage amplification
        # for high-D/E financial companies where equity << net_debt.
        if sc.market_sentiment_pct != 0:
            sc_eq = round(sc_eq * (1 + sc.market_sentiment_pct / 100))
        sc_ev = sc_eq + vi.net_debt
        # RIM yields common equity value directly; CPS/RCPS are already excluded
        # from book-value-based residual income — passing them would double-deduct.
        r = calc_scenario(
            sc, sc_ev, vi.net_debt, vi.eco_frontier, 0, 0, 0, 0, um, 0.0, 0.0
        )
        scenario_results[code] = r
        total_weighted += r.weighted

    if not scenario_results:
        total_weighted = rim_raw.per_share

    # EBITDA-based DCF is meaningless for financials -> P/E, P/BV cross-validation only
    cv_items = _cross_validate_financial(vi, cons, um)

    # Peer statistics
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    # RIM sensitivity: Ke x Terminal Growth
    sens_rim = sensitivity_rim(
        equity_bv,
        roe_forecasts,
        ke,
        shares,
        terminal_growth_base=tg,
        payout_ratio=payout,
        unit_multiplier=um,
    )

    # Monte Carlo
    mc_result = _run_monte_carlo(
        vi, wacc_result, _build_seg_ebitdas_from_consolidated(vi, cons), um
    )

    return ValuationResult(
        primary_method="rim",
        wacc=wacc_result,
        total_ev=total_ev,
        rim=rim_result,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        cross_validations=cv_items,
        sensitivity_primary=sens_rim,
        sensitivity_primary_label=f"Ke × 영구성장률 → RIM 주당가치 ({vi.company.currency_unit})",
        peer_stats=peer_stats,
        monte_carlo=mc_result,
    )


def _run_multiples_valuation(
    vi: ValuationInput, wacc_result, um: int
) -> ValuationResult:
    """Multiples-based valuation (mature/stable companies with sufficient peers)."""
    by = vi.base_year
    cons = vi.consolidated[by]

    total_da_base = cons["dep"] + cons["amort"]
    ebitda_base = cons["op"] + total_da_base
    net_income = cons.get("net_income", 0)
    book_value = cons.get("equity", 0)
    shares = vi.valuation_shares

    # Primary method selection: EV/EBITDA -> P/E -> P/BV priority
    # Use peer-based multiples or multiples specified in YAML
    primary_mv = None

    # 1. EV/EBITDA (segment multiple average)
    seg_multiples = [m for m in vi.multiples.values() if m > 0]
    if seg_multiples and ebitda_base > 0:
        avg_multiple = sum(seg_multiples) / len(seg_multiples)
        ev = round(ebitda_base * avg_multiple)
        equity = ev - vi.net_debt
        ps = per_share(equity, um, shares)
        primary_mv = MultiplesResult(
            primary_multiple_method="EV/EBITDA",
            metric_value=ebitda_base,
            multiple=avg_multiple,
            enterprise_value=ev,
            equity_value=equity,
            per_share=ps,
        )
    # 2. P/E fallback
    elif vi.pe_multiple > 0 and net_income > 0:
        mv = calc_pe(net_income, vi.pe_multiple, shares, um)
        primary_mv = MultiplesResult(
            primary_multiple_method="P/E",
            metric_value=mv.metric_value,
            multiple=mv.multiple,
            enterprise_value=mv.enterprise_value,
            equity_value=mv.equity_value,
            per_share=mv.per_share,
        )
    # 3. P/BV fallback
    elif vi.pbv_multiple > 0 and book_value > 0:
        mv = calc_pbv(book_value, vi.pbv_multiple, shares, um)
        primary_mv = MultiplesResult(
            primary_multiple_method="P/BV",
            metric_value=mv.metric_value,
            multiple=mv.multiple,
            enterprise_value=mv.enterprise_value,
            equity_value=mv.equity_value,
            per_share=mv.per_share,
        )
    else:
        # Insufficient multiple data -> DCF fallback
        return _run_dcf_valuation(vi, wacc_result, um)

    total_ev = primary_mv.enterprise_value or round(
        primary_mv.equity_value + vi.net_debt
    )

    # Scenarios -- recalculate EV with modified multiple when ev_multiple is set
    # P/E and P/BV produce equity values directly; base total_ev already has net_debt
    # added back (equity + net_debt) so calc_scenario's net_debt deduction is correct.
    # But when ev_multiple recalculates, it yields equity directly — must add net_debt back.
    is_equity_direct = primary_mv.primary_multiple_method in ("P/E", "P/BV")

    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        sc = resolve_drivers(sc, vi.news_drivers)
        sc_ev = total_ev
        if sc.ev_multiple is not None and primary_mv.metric_value > 0:
            sc_val = round(primary_mv.metric_value * sc.ev_multiple)
            # For equity-direct methods, ev_multiple yields equity → add net_debt back
            # so calc_scenario's bridge deduction produces correct equity
            sc_ev = sc_val + vi.net_debt if is_equity_direct else sc_val
        if sc.market_sentiment_pct != 0:
            sc_ev = round(sc_ev * (1 + sc.market_sentiment_pct / 100))
        r = calc_scenario(
            sc,
            sc_ev,
            vi.net_debt,
            vi.eco_frontier,
            vi.cps_principal,
            vi.cps_years,
            vi.rcps_principal,
            vi.rcps_years,
            um,
            vi.cps_dividend_rate,
            vi.rcps_dividend_rate,
        )
        scenario_results[code] = r
        total_weighted += r.weighted

    if not scenario_results:
        total_weighted = primary_mv.per_share

    # DCF cross-validation (may fail for ebitda<=0 or wacc<=tg)
    dcf_result = None
    dcf_ev = 0
    try:
        dcf_result = calc_dcf(
            ebitda_base,
            total_da_base,
            cons["revenue"],
            wacc_result.wacc,
            vi.dcf_params,
            vi.base_year,
        )
        dcf_ev = dcf_result.ev_dcf
    except ValueError:
        pass

    cv_items = _cross_validate_common(vi, cons, ebitda_base, 0, dcf_ev, um)

    # Peer statistics
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    # Multiples sensitivity: applied multiple x discount rate
    sens_mult_primary = sensitivity_multiple_range(
        primary_mv.metric_value,
        vi.net_debt,
        shares,
        primary_mv.multiple,
        unit_multiplier=um,
    )

    # Monte Carlo
    mc_result = _run_monte_carlo(
        vi,
        wacc_result,
        _build_seg_ebitdas_from_consolidated(vi, cons),
        um,
        dcf_result=dcf_result if dcf_result else None,
    )

    return ValuationResult(
        primary_method="multiples",
        wacc=wacc_result,
        total_ev=total_ev,
        multiples_primary=primary_mv,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        dcf=dcf_result,
        cross_validations=cv_items,
        peer_stats=peer_stats,
        monte_carlo=mc_result,
        sensitivity_primary=sens_mult_primary,
        sensitivity_primary_label=f"적용 멀티플 × 할인율 → 주당가치 ({vi.company.currency_unit})",
    )


def _run_nav_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """NAV (Net Asset Value) valuation (holding companies/REITs/asset-heavy)."""
    by = vi.base_year
    cons = vi.consolidated[by]

    total_assets = cons.get("assets", 0)
    total_liabilities = cons.get("liabilities", 0)
    revaluation = vi.nav_params.revaluation if vi.nav_params else 0
    shares = vi.valuation_shares

    nav_raw = calc_nav(
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        shares=shares,
        revaluation=revaluation,
        unit_multiplier=um,
    )
    nav_result = NAVResult(
        total_assets=nav_raw.total_assets,
        revaluation=nav_raw.revaluation,
        adjusted_assets=nav_raw.adjusted_assets,
        total_liabilities=nav_raw.total_liabilities,
        nav=nav_raw.nav,
        per_share=nav_raw.per_share,
    )

    # NAV = Equity Value concept -> reverse-calculate EV (for cross-validation)
    total_ev = nav_raw.nav + vi.net_debt

    # Scenarios -- apply holding company discount via nav_discount
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        sc = resolve_drivers(sc, vi.news_drivers)
        sc_ev = total_ev
        if sc.nav_discount != 0:
            # Apply holding company discount to NAV then add net_debt back for EV
            discounted_nav = round(nav_raw.nav * (1 - sc.nav_discount / 100))
            sc_ev = discounted_nav + vi.net_debt
        if sc.market_sentiment_pct != 0:
            sc_ev = round(sc_ev * (1 + sc.market_sentiment_pct / 100))
        # NAV liabilities already include CPS/RCPS principal (K-IFRS) → skip to avoid double deduction
        r = calc_scenario(
            sc, sc_ev, vi.net_debt, vi.eco_frontier, 0, 0, 0, 0, um, 0.0, 0.0
        )
        scenario_results[code] = r
        total_weighted += r.weighted

    if not scenario_results:
        total_weighted = nav_raw.per_share

    # DCF cross-validation (may fail for ebitda<=0 or wacc<=tg)
    total_da_base = cons["dep"] + cons["amort"]
    ebitda_base = cons["op"] + total_da_base
    dcf_result = None
    dcf_ev = 0
    try:
        dcf_result = calc_dcf(
            ebitda_base,
            total_da_base,
            cons["revenue"],
            wacc_result.wacc,
            vi.dcf_params,
            vi.base_year,
        )
        dcf_ev = dcf_result.ev_dcf
    except ValueError:
        pass

    cv_items = _cross_validate_common(vi, cons, ebitda_base, 0, dcf_ev, um)

    # Peer statistics
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    # NAV sensitivity: revaluation x holding company discount
    sens_nav = sensitivity_nav(
        total_assets,
        total_liabilities,
        shares,
        base_revaluation=revaluation,
        unit_multiplier=um,
    )

    # Monte Carlo
    mc_result = _run_monte_carlo(
        vi,
        wacc_result,
        _build_seg_ebitdas_from_consolidated(vi, cons),
        um,
        dcf_result=dcf_result if dcf_result else None,
    )

    return ValuationResult(
        primary_method="nav",
        wacc=wacc_result,
        total_ev=total_ev,
        nav=nav_result,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        sensitivity_primary=sens_nav,
        sensitivity_primary_label=f"재평가 조정액 × 지주할인율 → 주당 NAV ({vi.company.currency_unit})",
        dcf=dcf_result,
        cross_validations=cv_items,
        peer_stats=peer_stats,
        monte_carlo=mc_result,
    )


def _get_reference_scenario(scenarios: dict) -> ScenarioParams | None:
    """Return the highest-probability scenario (for sensitivity analysis)."""
    if not scenarios:
        return None
    return max(scenarios.values(), key=lambda sc: sc.prob)


def _derive_rcps_repay(ref_sc: ScenarioParams | None, vi) -> int:
    """Derive RCPS repay amount using the same logic as calc_scenario.

    If rcps_repay is explicitly set in scenario, use it.
    Otherwise compute from IRR and rcps_principal/years/dividend_rate.
    Uses rcps_irr when set, else irr; defaults to 0 when both are None.
    """
    if ref_sc is None:
        return 0
    if ref_sc.rcps_repay is not None:
        return ref_sc.rcps_repay
    if vi.rcps_principal > 0:
        rcps_effective_irr = (
            ref_sc.rcps_irr if ref_sc.rcps_irr is not None else ref_sc.irr
        )
        effective_rate = max((rcps_effective_irr or 0) - vi.rcps_dividend_rate, 0.0)
        return round(vi.rcps_principal * (1 + effective_rate / 100) ** vi.rcps_years)
    return 0


def _cross_validate_financial(vi, cons, um):
    """Financial stock cross-validation -- P/E, P/BV only (EBITDA-based DCF/SOTP meaningless)."""
    items = []
    shares = vi.valuation_shares
    net_income = cons.get("net_income", 0)
    book_value = cons.get("equity", 0)

    if vi.pe_multiple > 0 and net_income > 0:
        mv = calc_pe(net_income, vi.pe_multiple, shares, um)
        items.append(
            CrossValidationItem(
                method="P/E",
                metric_value=net_income,
                multiple=vi.pe_multiple,
                enterprise_value=0,
                equity_value=mv.equity_value,
                per_share=mv.per_share,
            )
        )
    if vi.pbv_multiple > 0 and book_value > 0:
        mv = calc_pbv(book_value, vi.pbv_multiple, shares, um)
        items.append(
            CrossValidationItem(
                method="P/BV",
                metric_value=book_value,
                multiple=vi.pbv_multiple,
                enterprise_value=0,
                equity_value=mv.equity_value,
                per_share=mv.per_share,
            )
        )
    return items


def _cross_validate_common(
    vi,
    cons,
    ebitda_base,
    sotp_ev,
    dcf_ev,
    um,
    net_debt_override=None,
    sotp_ev_ebitda_only=None,
):
    """Common multiples cross-validation."""
    net_debt = net_debt_override if net_debt_override is not None else vi.net_debt
    cv_results = cross_validate(
        revenue=cons["revenue"],
        ebitda=ebitda_base,
        net_income=cons.get("net_income", 0),
        book_value=cons.get("equity", 0),
        net_debt=net_debt,
        shares=vi.valuation_shares,
        sotp_ev=sotp_ev,
        dcf_ev=dcf_ev,
        ev_revenue_multiple=vi.ev_revenue_multiple,
        pe_multiple=vi.pe_multiple,
        pbv_multiple=vi.pbv_multiple,
        ps_multiple=vi.ps_multiple,
        pffo_multiple=vi.pffo_multiple,
        ffo=vi.ffo,
        unit_multiplier=um,
        sotp_ev_ebitda_only=sotp_ev_ebitda_only,
    )
    return [
        CrossValidationItem(
            method=mv.method,
            metric_value=mv.metric_value,
            multiple=mv.multiple,
            enterprise_value=mv.enterprise_value,
            equity_value=mv.equity_value,
            per_share=mv.per_share,
        )
        for mv in cv_results
    ]


def _mc_raw_to_result(mc_raw, mc_input=None, include_dcf_tv: bool = False):
    """Convert MCResult to MonteCarloResult."""
    assumptions = {}
    if mc_input is not None:
        for seg in sorted(mc_input.multiple_params):
            m, s = mc_input.multiple_params[seg]
            distribution = "Lognormal" if m > 0 and s > 0 else "Normal (floored at 0)"
            mean_text = f"{m:.5f}".rstrip("0").rstrip(".")
            std_text = f"{s:.5f}".rstrip("0").rstrip(".")
            assumptions[f"Multiple({seg})"] = (
                f"{distribution}(mean={mean_text}x, std={std_text}x)"
            )
        if include_dcf_tv:
            assumptions["WACC"] = (
                f"Normal(mean={mc_input.wacc_mean:.1f}%, std={mc_input.wacc_std:.1f}%p)"
            )
        assumptions["DLOM"] = (
            f"Normal(mean={mc_input.dlom_mean:.0f}%, std={mc_input.dlom_std:.0f}%), clipped 0-50%"
        )
        if include_dcf_tv:
            assumptions["Terminal Growth"] = (
                f"Normal(mean={mc_input.tg_mean:.1f}%, "
                f"std={mc_input.tg_std:.1f}%p), clipped 0~WACC-0.5%"
            )
        for seg in sorted(mc_input.revenue_params):
            r, rs = mc_input.revenue_params[seg]
            assumptions[f"Revenue({seg})"] = f"Normal(mean={r:,.0f}, std={rs:,.0f})"
    return MonteCarloResult(
        n_sims=mc_raw.n_sims,
        mean=mc_raw.mean,
        median=mc_raw.median,
        std=mc_raw.std,
        p5=mc_raw.p5,
        p25=mc_raw.p25,
        p75=mc_raw.p75,
        p95=mc_raw.p95,
        min_val=mc_raw.min_val,
        max_val=mc_raw.max_val,
        histogram_bins=mc_raw.histogram_bins,
        histogram_counts=mc_raw.histogram_counts,
        pct_negative=mc_raw.pct_negative,
        input_assumptions=assumptions,
    )


def _run_monte_carlo(
    vi,
    wacc_result,
    seg_ebitdas: dict[str, int],
    um: int,
    dcf_result=None,
    effective_multiples: dict[str, float] | None = None,
    seg_revenues: dict[str, int] | None = None,
    segment_methods: dict[str, str] | None = None,
    net_debt_override: int | None = None,
) -> MonteCarloResult | None:
    """Run Monte Carlo -- common entry point for SOTP/non-SOTP.

    Args:
        seg_ebitdas: {seg_code: ebitda} -- allocate_da result for SOTP, or consolidated-based allocation.
        effective_multiples: Distress-adjusted multiples (falls back to vi.multiples if None).
        seg_revenues: {seg_code: revenue} for ev_revenue segments.
        segment_methods: {seg_code: method} for method dispatch in MC.
    """
    if not vi.mc_enabled:
        return None

    from engine.monte_carlo import MCInput, run_monte_carlo

    equity_codes = {
        code
        for code, method in (segment_methods or {}).items()
        if method in ("pbv", "pe")
    }
    if equity_codes:
        expected_net_debt = _calc_effective_net_debt(vi)
        if net_debt_override != expected_net_debt:
            raise AssertionError(
                "PBV/PE Monte Carlo requires effective_net_debt; "
                f"expected {expected_net_debt}, received {net_debt_override}"
            )

    ordered_equity_codes = sorted(equity_codes)
    seg_book_equity = {
        code: int(vi.segments.get(code, {}).get("book_equity", 0))
        for code in ordered_equity_codes
    }
    seg_net_income = {
        code: int(vi.segments.get(code, {}).get("net_income_segment", 0))
        for code in ordered_equity_codes
    }
    mults = effective_multiples or vi.multiples
    # Include non-EBITDA segments in MC even if their EBITDA is 0.
    mc_mult_codes = set(seg_ebitdas.keys())
    if segment_methods:
        mc_mult_codes |= {
            code
            for code, method in segment_methods.items()
            if method in ("ev_revenue", "pbv", "pe")
        }
    # Revenue uncertainty for ev_revenue segments (std = mc_revenue_std_pct of base revenue)
    rev_params: dict[str, tuple[float, float]] = {}
    ordered_methods = {
        code: method for code, method in sorted((segment_methods or {}).items())
    }
    if ordered_methods and seg_revenues:
        for c, m in ordered_methods.items():
            if m == "ev_revenue":
                rev = seg_revenues.get(c, 0)
                if rev > 0:
                    rev_params[c] = (float(rev), rev * vi.mc_revenue_std_pct / 100)
    mc_params = MCInput(
        multiple_params={
            c: (mults[c], mults[c] * vi.mc_multiple_std_pct / 100)
            for c in sorted(mc_mult_codes)
            if mults.get(c, 0) > 0
        },
        segment_methods=ordered_methods,
        revenue_params=rev_params,
        wacc_mean=wacc_result.wacc,
        wacc_std=1.0,
        dlom_mean=vi.mc_dlom_mean,
        dlom_std=vi.mc_dlom_std,
        tg_mean=vi.dcf_params.terminal_growth,
        tg_std=0.5,
        n_sims=vi.mc_sims,
    )
    ref_sc = _get_reference_scenario(vi.scenarios)

    dcf_kwargs = {}
    if dcf_result and dcf_result.projections:
        last_p = dcf_result.projections[-1]
        # Use normalized FCFF (consistent with actual DCF TV: NOPAT - delta_NWC).
        # Raw last_p.fcff perpetuates capex-fade artifacts and capex/DA deviations.
        normalized_last_fcff = (
            last_p.nopat - last_p.delta_nwc if last_p.nopat > 0 else last_p.fcff
        )
        dcf_kwargs = dict(
            wacc_for_dcf=wacc_result.wacc,
            dcf_last_fcff=normalized_last_fcff,
            dcf_pv_fcff_sum=dcf_result.pv_fcff_sum,
            dcf_n_periods=len(dcf_result.projections),
        )

    mc_net_debt = net_debt_override if net_debt_override is not None else vi.net_debt
    mc_raw = run_monte_carlo(
        mc_params,
        seg_ebitdas,
        mc_net_debt,
        vi.eco_frontier,
        vi.cps_principal,
        vi.cps_years,
        _derive_rcps_repay(ref_sc, vi),
        ref_sc.buyback if ref_sc else 0,
        ref_sc.shares if ref_sc else vi.valuation_shares,
        irr=(
            ref_sc.cps_irr
            if ref_sc and ref_sc.cps_irr is not None
            else (ref_sc.irr if ref_sc and ref_sc.irr else 5.0)
        ),
        unit_multiplier=um,
        seg_revenues=seg_revenues,
        seg_book_equity=seg_book_equity,
        seg_net_income=seg_net_income,
        cps_dividend_rate=vi.cps_dividend_rate,
        receivable_recovery_value=(
            ref_sc.receivable_recovery_value or 0 if ref_sc else 0
        ),
        **dcf_kwargs,
    )
    result = _mc_raw_to_result(
        mc_raw, mc_input=mc_params, include_dcf_tv=bool(dcf_kwargs)
    )

    # Per-scenario MC (lightweight: fewer sims, no histogram stored)
    from schemas.models import MCScenarioSummary

    sc_mc: dict[str, MCScenarioSummary] = {}
    for sc_code, sc in vi.scenarios.items():
        has_overrides = (
            sc.segment_multiples or sc.segment_revenue or sc.growth_adj_pct != 0
        )
        if not has_overrides:
            continue
        # Build scenario-specific multiples
        sc_mults = dict(mults)
        if sc.segment_multiples:
            sc_mults.update(sc.segment_multiples)
        # Build scenario-specific revenues
        sc_revs = dict(seg_revenues or {})
        if sc.segment_revenue:
            sc_revs.update(sc.segment_revenue)
        # Build scenario-specific EBITDAs (growth_adj_pct)
        sc_ebitdas = dict(seg_ebitdas)
        if sc.growth_adj_pct != 0:
            mult_g = 1 + sc.growth_adj_pct / 100
            sc_ebitdas = {c: round(e * mult_g) for c, e in seg_ebitdas.items()}
        if sc.segment_ebitda:
            sc_ebitdas.update(sc.segment_ebitda)

        sc_rev_params: dict[str, tuple[float, float]] = {}
        if ordered_methods and sc_revs:
            for c, m in ordered_methods.items():
                if m == "ev_revenue":
                    rev = sc_revs.get(c, 0)
                    if rev > 0:
                        sc_rev_params[c] = (
                            float(rev),
                            rev * vi.mc_revenue_std_pct / 100,
                        )

        sc_params = MCInput(
            multiple_params={
                c: (sc_mults[c], sc_mults[c] * vi.mc_multiple_std_pct / 100)
                for c in sorted(mc_mult_codes)
                if sc_mults.get(c, 0) > 0
            },
            segment_methods=ordered_methods,
            revenue_params=sc_rev_params,
            wacc_mean=wacc_result.wacc,
            wacc_std=1.0,
            dlom_mean=vi.mc_dlom_mean,
            dlom_std=vi.mc_dlom_std,
            tg_mean=vi.dcf_params.terminal_growth,
            tg_std=0.5,
            n_sims=min(2000, vi.mc_sims),
            seed=int(hashlib.md5(sc_code.encode()).hexdigest()[:8], 16) % (2**31),
        )
        sc_raw = run_monte_carlo(
            sc_params,
            sc_ebitdas,
            net_debt_override if net_debt_override is not None else vi.net_debt,
            vi.eco_frontier,
            vi.cps_principal,
            vi.cps_years,
            _derive_rcps_repay(sc, vi),
            sc.buyback,
            sc.shares,
            irr=(sc.cps_irr if sc.cps_irr is not None else (sc.irr if sc.irr else 5.0)),
            unit_multiplier=um,
            seg_revenues=sc_revs,
            seg_book_equity=seg_book_equity,
            seg_net_income=seg_net_income,
            cps_dividend_rate=vi.cps_dividend_rate,
            receivable_recovery_value=sc.receivable_recovery_value or 0,
            **dcf_kwargs,
        )
        sc_mc[sc_code] = MCScenarioSummary(
            mean=sc_raw.mean,
            median=sc_raw.median,
            p5=sc_raw.p5,
            p95=sc_raw.p95,
        )

    if sc_mc:
        result.scenario_mc = sc_mc
    return result


def _build_seg_ebitdas_from_consolidated(vi, cons) -> dict[str, int]:
    """For non-SOTP methods: allocate consolidated EBITDA to segments."""
    total_da = cons.get("dep", 0) + cons.get("amort", 0)
    ebitda = cons.get("op", 0) + total_da

    seg_codes = list(vi.segments.keys())
    if len(seg_codes) == 1:
        return {seg_codes[0]: ebitda}

    seg_data = vi.segment_data.get(vi.base_year, {})
    total_rev = sum(s.get("revenue", 0) for s in seg_data.values())
    if total_rev > 0:
        return {
            c: round(ebitda * seg_data.get(c, {}).get("revenue", 0) / total_rev)
            for c in seg_codes
        }
    # No revenue data — distribute equally across segments
    n = len(seg_codes)
    return {c: round(ebitda / n) for c in seg_codes}


def _run_rnpv_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """Risk-adjusted NPV (rNPV) valuation for pharma pipeline companies."""
    if not vi.rnpv_params:
        raise ValueError(
            "rNPV 방법론이 선택되었으나 rnpv_params가 없습니다. "
            "YAML에 rnpv_params: {pipeline: [...]}를 추가하세요."
        )

    # Use override discount rate or WACC
    discount_rate = vi.rnpv_params.discount_rate or wacc_result.wacc

    # Convert pipeline drugs to dicts for engine
    pipeline_dicts = [d.model_dump() for d in vi.rnpv_params.pipeline]

    rnpv_raw = calc_rnpv(
        pipeline=pipeline_dicts,
        discount_rate=discount_rate,
        r_and_d_cost=vi.rnpv_params.r_and_d_cost,
        decline_rate=vi.rnpv_params.decline_rate,
        default_margin=vi.rnpv_params.default_margin,
        tax_rate=vi.rnpv_params.tax_rate,
    )

    # Build Pydantic result (include revenue_curve for Excel charting)
    drug_results = [
        RNPVDrugResult(
            name=dr.name,
            phase=dr.phase,
            indication=dr.indication,
            peak_sales=dr.peak_sales,
            success_prob=dr.success_prob,
            npv_unadjusted=dr.npv,
            rnpv=dr.rnpv,
            revenue_curve=dr.revenue_curve,
        )
        for dr in rnpv_raw.drug_results
    ]

    shares = vi.valuation_shares
    ev = rnpv_raw.enterprise_value
    equity_value = ev - vi.net_debt
    per_share = round(equity_value * um / shares) if shares > 0 else 0

    rnpv_result = RNPVValuationResult(
        drug_results=drug_results,
        total_rnpv=rnpv_raw.total_rnpv,
        r_and_d_cost_pv=rnpv_raw.r_and_d_cost_pv,
        pipeline_value=rnpv_raw.pipeline_value,
        existing_revenue_value=rnpv_raw.existing_revenue_value,
        enterprise_value=ev,
        per_share=per_share,
        discount_rate=discount_rate,
    )

    # Scenarios: adjust success probabilities or peak sales
    total_ev = ev
    scenario_results = {}
    total_weighted = 0

    for sc_code, sc in vi.scenarios.items():
        # growth_adj_pct adjusts peak sales; wacc_adj adjusts discount rate; pos_override adjusts PoS
        adj_discount = discount_rate + sc.wacc_adj
        adj_pipeline = []
        for d in pipeline_dicts:
            adj_d = dict(d)
            if sc.growth_adj_pct != 0:
                adj_d["peak_sales"] = round(
                    d["peak_sales"] * (1 + sc.growth_adj_pct / 100)
                )
                if d.get("existing_revenue", 0) > 0:
                    adj_d["existing_revenue"] = round(
                        d["existing_revenue"] * (1 + sc.growth_adj_pct / 100)
                    )
            if sc.pos_override and d["name"] in sc.pos_override:
                adj_d["success_prob"] = sc.pos_override[d["name"]]
            adj_pipeline.append(adj_d)

        sc_rnpv = calc_rnpv(
            pipeline=adj_pipeline,
            discount_rate=adj_discount,
            r_and_d_cost=vi.rnpv_params.r_and_d_cost,
            decline_rate=vi.rnpv_params.decline_rate,
            default_margin=vi.rnpv_params.default_margin,
            tax_rate=vi.rnpv_params.tax_rate,
        )
        sc_ev = sc_rnpv.enterprise_value

        sc_result = calc_scenario(
            sc,
            sc_ev,
            vi.net_debt,
            vi.eco_frontier,
            vi.cps_principal,
            vi.cps_years,
            rcps_principal=vi.rcps_principal,
            rcps_years=vi.rcps_years,
            unit_multiplier=um,
            cps_dividend_rate=vi.cps_dividend_rate,
            rcps_dividend_rate=vi.rcps_dividend_rate,
        )
        scenario_results[sc_code] = sc_result
        total_weighted += sc_result.weighted

    if not scenario_results:
        total_weighted = per_share

    # Cross-validation (common multiples)
    cons = vi.consolidated[vi.base_year]
    total_da_base = cons.get("dep", 0) + cons.get("amort", 0)
    ebitda_base = cons.get("op", 0) + total_da_base
    dcf_result = None
    dcf_ev = 0
    try:
        dcf_result = calc_dcf(
            ebitda_base,
            total_da_base,
            cons.get("revenue", 0),
            wacc_result.wacc,
            vi.dcf_params,
            vi.base_year,
        )
        dcf_ev = dcf_result.ev_dcf
    except ValueError:
        pass

    cv_items = _cross_validate_common(vi, cons, ebitda_base, total_ev, dcf_ev, um)

    # Peer stats
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    # rNPV-specific sensitivity: discount rate × PoS scale
    sens_kwargs = dict(
        pipeline=pipeline_dicts,
        discount_rate=discount_rate,
        net_debt=vi.net_debt,
        shares=shares,
        unit_multiplier=um,
        r_and_d_cost=vi.rnpv_params.r_and_d_cost,
        decline_rate=vi.rnpv_params.decline_rate,
        default_margin=vi.rnpv_params.default_margin,
        tax_rate=vi.rnpv_params.tax_rate,
    )
    sens_rnpv = sensitivity_rnpv(**sens_kwargs)

    # Tornado: per-drug ±20% peak sales impact
    from schemas.models import RNPVTornadoItem

    tornado_raw = sensitivity_rnpv_tornado(**sens_kwargs)
    tornado_items = [
        RNPVTornadoItem(
            name=t["name"],
            base_value=t["base_value"],
            low_value=t["low_value"],
            high_value=t["high_value"],
            low_peak=t["low_peak"],
            high_peak=t["high_peak"],
        )
        for t in tornado_raw
    ]

    return ValuationResult(
        primary_method="rnpv",
        wacc=wacc_result,
        total_ev=total_ev,
        rnpv=rnpv_result,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        dcf=dcf_result,
        cross_validations=cv_items,
        peer_stats=peer_stats,
        sensitivity_primary=sens_rnpv,
        sensitivity_primary_label=f"할인율 × PoS 배수 → 주당가치 ({vi.company.currency_unit})",
        rnpv_tornado=tornado_items,
    )
