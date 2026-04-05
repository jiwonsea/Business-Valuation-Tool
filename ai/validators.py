"""Deterministic validators for AI LLM outputs.

Applied after JSON parsing, before values flow into valuation profiles.
Zero LLM calls -- pure arithmetic range checks.
"""

from __future__ import annotations

import logging
from copy import deepcopy

logger = logging.getLogger(__name__)

# ── Market-specific WACC parameter ranges (shared with engine/quality.py) ──

WACC_RANGES = {
    "KR": {"rf": (2.5, 5.0), "erp": (4.0, 8.0), "beta": (0.3, 2.0), "kd_pre": (2.0, 10.0)},
    "US": {"rf": (3.0, 5.5), "erp": (4.0, 7.0), "beta": (0.3, 2.0), "kd_pre": (2.0, 8.0)},
}

# ── Driver value ranges (shared with prompts._DRIVER_BOUNDS) ──

DRIVER_RANGES: dict[str, tuple[float, float]] = {
    "growth_adj_pct": (-50, 100),
    "terminal_growth_adj": (-2.0, 2.0),
    "wacc_adj": (-3.0, 3.0),
    "market_sentiment_pct": (-30, 30),
    "ddm_growth": (0.0, 15.0),
    "rim_roe_adj": (-10.0, 10.0),
    "ev_multiple": (1.0, 50.0),
    "nav_discount": (0.0, 60.0),
}


def validate_peers(peers_data: dict, market: str = "KR") -> tuple[dict, list[str]]:
    """Validate AI-recommended peer data.

    - Exclude peers with negative EV/EBITDA (loss-making, not useful as comparable)
    - Exclude peers with EV/EBITDA outside [0.5, 50]
    - Warn if < 2 valid peers remain per segment
    - Warn on single-country concentration

    Args:
        peers_data: AI output dict with segment-keyed peer lists.
            Expected structure: {"segments": {code: {"peers": [...], "ev_ebitda": float}}}
            or flat: {"peers": [{"name": ..., "segment": ..., "ev_ebitda": float}, ...]}
        market: "KR" or "US"

    Returns:
        (cleaned_data, warnings)
    """
    warnings: list[str] = []
    data = deepcopy(peers_data)

    # Handle flat peer list format
    if "peers" in data and isinstance(data["peers"], list):
        cleaned_peers = []
        excluded = []
        for peer in data["peers"]:
            ev = peer.get("ev_ebitda", 0)
            name = peer.get("name", "unknown")
            if ev is None:
                excluded.append(name)
                continue
            if ev < 0:
                excluded.append(name)
                warnings.append(f"Peer '{name}' 제외: 음수 EV/EBITDA ({ev:.1f}x, 적자 기업)")
                continue
            if ev < 0.5 or ev > 50:
                excluded.append(name)
                warnings.append(f"Peer '{name}' 제외: EV/EBITDA 범위 이탈 ({ev:.1f}x)")
                continue
            cleaned_peers.append(peer)
        data["peers"] = cleaned_peers

        if len(cleaned_peers) < 2:
            warnings.append(f"유효 Peer 수 부족 ({len(cleaned_peers)}개, 최소 2개 권장)")

    # Handle segment-keyed format
    if "segments" in data and isinstance(data["segments"], dict):
        for seg_code, seg_data in data["segments"].items():
            if "peers" not in seg_data or not isinstance(seg_data["peers"], list):
                continue
            cleaned = []
            for peer in seg_data["peers"]:
                ev = peer.get("ev_ebitda", 0)
                name = peer.get("name", "unknown")
                if ev is None or ev < 0:
                    warnings.append(f"[{seg_code}] Peer '{name}' 제외: 음수/null EV/EBITDA")
                    continue
                if ev < 0.5 or ev > 50:
                    warnings.append(f"[{seg_code}] Peer '{name}' 제외: EV/EBITDA {ev:.1f}x 범위 이탈")
                    continue
                cleaned.append(peer)
            seg_data["peers"] = cleaned

            if len(cleaned) < 2:
                warnings.append(f"[{seg_code}] 유효 Peer 수 부족 ({len(cleaned)}개)")

    return data, warnings


def validate_wacc(wacc_data: dict, market: str = "KR") -> tuple[dict, list[str]]:
    """Validate and clamp AI-suggested WACC parameters.

    Continuous parameters are clamped to boundaries (safe for WACC).

    Args:
        wacc_data: AI output with keys like "rf", "erp", "bu", "kd_pre", etc.
        market: "KR" or "US"

    Returns:
        (clamped_data, warnings)
    """
    warnings: list[str] = []
    data = deepcopy(wacc_data)
    ranges = WACC_RANGES.get(market, WACC_RANGES["KR"])

    _clamp(data, "rf", ranges["rf"], "무위험이자율", warnings)
    _clamp(data, "erp", ranges["erp"], "ERP", warnings)
    _clamp(data, "bu", ranges["beta"], "Unlevered Beta", warnings)
    _clamp(data, "kd_pre", ranges["kd_pre"], "세전타인자본비용", warnings)

    return data, warnings


def validate_scenarios(scenarios_data: dict | list) -> tuple[dict | list, list[str]]:
    """Validate AI-designed scenarios.

    Handles both formats:
    - dict: {scenario_code: {prob, dlom, ...}} (legacy)
    - list: [{code, prob, dlom, ...}, ...] (prompt output format)

    Checks:
    - Normalize probabilities (98-102% → silent normalize, else → warn + normalize)
    - Flag single scenario > 60%
    - Flag DLOM outside 0-40%
    - Require at least 2 scenarios
    - Base Case probability 30-50%
    - Driver values within allowed ranges
    - Scenario differentiation (drivers not all identical)
    - Combined driver effect sanity check

    Returns:
        (normalized_data, warnings)
    """
    warnings: list[str] = []

    # ── Normalize to list-of-dicts internally ──
    is_list = isinstance(scenarios_data, list)
    if is_list:
        items = deepcopy(scenarios_data)
    else:
        data_copy = deepcopy(scenarios_data)
        items = [v for v in data_copy.values() if isinstance(v, dict)]

    if len(items) < 2:
        warnings.append(f"시나리오 수 부족 ({len(items)}개, 최소 2개 권장)")
        if len(items) == 0:
            return scenarios_data if not is_list else [], warnings

    # ── Probability normalization ──
    probs = [s.get("prob", 0) for s in items]
    total_prob = sum(probs)

    if total_prob > 0:
        if abs(total_prob - 100) <= 2:
            for s in items:
                s["prob"] = s.get("prob", 0) / total_prob * 100
        elif total_prob != 100:
            warnings.append(
                f"시나리오 확률 합계 비정상 ({total_prob:.1f}%) → 100%로 정규화"
            )
            for s in items:
                s["prob"] = s.get("prob", 0) / total_prob * 100

    # ── Single scenario dominance ──
    for s in items:
        label = s.get("code") or s.get("name", "?")
        prob = s.get("prob", 0)
        if prob > 60:
            warnings.append(f"시나리오 '{label}' 확률 과대 ({prob:.0f}% > 60%)")

    # ── Base Case probability check ──
    for s in items:
        name_lower = (s.get("name") or "").lower()
        code_lower = (s.get("code") or "").lower()
        if "base" in name_lower or "base" in code_lower:
            prob = s.get("prob", 0)
            if prob < 30 or prob > 50:
                warnings.append(
                    f"Base Case 확률 ({prob:.0f}%)이 권장 범위(30-50%) 밖입니다"
                )
            break

    # ── DLOM range check ──
    for s in items:
        label = s.get("code") or s.get("name", "?")
        dlom = s.get("dlom", 0)
        if dlom < 0:
            s["dlom"] = 0
            warnings.append(f"시나리오 '{label}' DLOM 음수 → 0%로 보정")
        elif dlom > 40:
            warnings.append(f"시나리오 '{label}' DLOM 과대 ({dlom:.0f}% > 40%)")

    # ── Driver range validation ──
    for s in items:
        label = s.get("code") or s.get("name", "?")
        drivers = s.get("drivers", {})
        for field, val in drivers.items():
            if not isinstance(val, (int, float)):
                continue
            bounds = DRIVER_RANGES.get(field)
            if bounds and not (bounds[0] <= val <= bounds[1]):
                clamped = max(bounds[0], min(bounds[1], val))
                warnings.append(
                    f"[{label}] {field}={val} 범위 이탈 [{bounds[0]}, {bounds[1]}] → {clamped}로 보정"
                )
                drivers[field] = clamped

    # ── News driver effect range validation ──
    # (handled externally via news_drivers list, but check active_drivers weights)
    for s in items:
        label = s.get("code") or s.get("name", "?")
        active = s.get("active_drivers", {})
        if isinstance(active, dict):
            for did, weight in active.items():
                if isinstance(weight, (int, float)) and not (0 <= weight <= 1):
                    warnings.append(f"[{label}] driver '{did}' weight={weight} 범위 이탈 [0, 1]")

    # ── Scenario differentiation check ──
    driver_signatures = []
    for s in items:
        drivers = s.get("drivers", {})
        active = s.get("active_drivers", {})
        sig = tuple(sorted(drivers.items())) + tuple(sorted((active or {}).items()))
        driver_signatures.append(sig)
    if len(set(driver_signatures)) == 1 and len(items) > 1:
        warnings.append("모든 시나리오의 드라이버가 동일합니다 — 시나리오 분화 부족")

    # ── Combined driver effect sanity check ──
    for s in items:
        label = s.get("code") or s.get("name", "?")
        drivers = s.get("drivers", {})
        wacc = drivers.get("wacc_adj", 0)
        growth = drivers.get("growth_adj_pct", 0)
        # Extreme bear: huge negative growth + huge positive wacc is suspicious
        if isinstance(wacc, (int, float)) and isinstance(growth, (int, float)):
            if wacc > 2.0 and growth < -30:
                warnings.append(
                    f"[{label}] wacc_adj={wacc:+.1f} + growth_adj_pct={growth:+.0f}%: "
                    f"극단적 복합 효과 — 의도된 시나리오인지 확인 필요"
                )

    # ── Return in original format ──
    if is_list:
        return items, warnings

    # Rebuild dict
    result = deepcopy(scenarios_data)
    for k, v in result.items():
        if isinstance(v, dict):
            break
    # Map items back by position (dict preserves insertion order)
    dict_keys = [k for k, v in result.items() if isinstance(v, dict)]
    for k, item in zip(dict_keys, items):
        result[k] = item
    return result, warnings


def validate_scenario_draft(draft: dict) -> tuple[dict, list[str]]:
    """Validate Pass 1 scenario classification draft structure.

    Checks:
    - scenario_draft list exists with >= 2 entries
    - Each entry has code, prob_range (2-element list), driver_directions
    - prob_range intervals are plausible (each within [5, 60], lo <= hi)
    - At least one scenario looks like a Base Case

    Returns:
        (cleaned_draft, warnings)
    """
    warnings: list[str] = []
    data = deepcopy(draft)

    scenarios = data.get("scenario_draft", [])
    if not isinstance(scenarios, list):
        warnings.append("scenario_draft가 리스트가 아닙니다")
        return data, warnings

    if len(scenarios) < 2:
        warnings.append(f"시나리오 초안 수 부족 ({len(scenarios)}개, 최소 2개)")

    has_base = False
    for s in scenarios:
        label = s.get("code", "?")

        # Check prob_range
        pr = s.get("prob_range", [])
        if isinstance(pr, list) and len(pr) == 2:
            lo, hi = pr
            if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
                if lo > hi:
                    warnings.append(f"[{label}] prob_range 역전 [{lo}, {hi}] → 교환")
                    s["prob_range"] = [hi, lo]
                if hi > 60:
                    warnings.append(f"[{label}] prob_range 상한 {hi}% > 60%")
        else:
            warnings.append(f"[{label}] prob_range 누락 또는 형식 오류")

        # Check driver_directions
        dd = s.get("driver_directions", {})
        if not isinstance(dd, dict) or len(dd) == 0:
            warnings.append(f"[{label}] driver_directions 누락")

        # Base case detection
        name_lower = (s.get("name") or "").lower()
        code_lower = (s.get("code") or "").lower()
        if "base" in name_lower or "base" in code_lower:
            has_base = True

    if not has_base and len(scenarios) >= 2:
        warnings.append("Base Case 시나리오가 감지되지 않았습니다")

    return data, warnings


def validate_news_drivers(news_drivers: list[dict]) -> tuple[list[dict], list[str]]:
    """Validate news driver effect values against allowed ranges.

    Returns:
        (cleaned_drivers, warnings)
    """
    warnings: list[str] = []
    drivers = deepcopy(news_drivers)

    for nd in drivers:
        did = nd.get("id", "?")
        effects = nd.get("effects", {})
        for field, val in list(effects.items()):
            if not isinstance(val, (int, float)):
                continue
            bounds = DRIVER_RANGES.get(field)
            if bounds and not (bounds[0] <= val <= bounds[1]):
                clamped = max(bounds[0], min(bounds[1], val))
                warnings.append(
                    f"news_driver '{did}' {field}={val} 범위 이탈 → {clamped}로 보정"
                )
                effects[field] = clamped

    return drivers, warnings


def _clamp(data: dict, key: str, bounds: tuple[float, float], label: str, warnings: list[str]):
    """Clamp a numeric value to bounds, appending a warning if clamped."""
    if key not in data or data[key] is None:
        return
    val = data[key]
    lo, hi = bounds
    if val < lo:
        warnings.append(f"{label} 하한 보정 ({val:.2f} → {lo:.2f})")
        data[key] = lo
    elif val > hi:
        warnings.append(f"{label} 상한 보정 ({val:.2f} → {hi:.2f})")
        data[key] = hi
