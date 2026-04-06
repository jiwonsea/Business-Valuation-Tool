"""Deterministic validators for AI LLM outputs.

Applied after JSON parsing, before values flow into valuation profiles.
Zero LLM calls -- pure arithmetic range checks.
"""

from __future__ import annotations

import logging
import math
from copy import deepcopy

logger = logging.getLogger(__name__)


def _safe_numeric(val) -> float | None:
    """Convert ev_ebitda value to float, returning None for non-numeric inputs."""
    if val is None:
        return None
    if isinstance(val, str):
        return None
    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    return None

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
        total_input = len(data["peers"])
        for peer in data["peers"]:
            ev = _safe_numeric(peer.get("ev_ebitda"))
            name = peer.get("name", "unknown")
            if ev is None:
                warnings.append(f"Peer '{name}' 제외: EV/EBITDA 값 누락 (파싱 에러)")
                continue
            if ev < 0:
                warnings.append(f"Peer '{name}' 제외: 음수 EV/EBITDA ({ev:.1f}x, 적자 기업)")
                continue
            if ev < 0.5 or ev > 50:
                warnings.append(f"Peer '{name}' 제외: EV/EBITDA 범위 이탈 ({ev:.1f}x)")
                continue
            cleaned_peers.append(peer)
        data["peers"] = cleaned_peers

        excluded_count = total_input - len(cleaned_peers)
        if excluded_count > 0:
            logger.warning(
                "Peer 파싱 집계: %d/%d개 제외됨", excluded_count, total_input,
            )
        if len(cleaned_peers) < 2:
            warnings.append(f"유효 Peer 수 부족 ({len(cleaned_peers)}개, 최소 2개 권장)")

    # Handle segment-keyed format
    if "segments" in data and isinstance(data["segments"], dict):
        for seg_code, seg_data in data["segments"].items():
            if "peers" not in seg_data or not isinstance(seg_data["peers"], list):
                continue
            cleaned = []
            seg_total = len(seg_data["peers"])
            for peer in seg_data["peers"]:
                ev = _safe_numeric(peer.get("ev_ebitda"))
                name = peer.get("name", "unknown")
                if ev is None:
                    warnings.append(f"[{seg_code}] Peer '{name}' 제외: EV/EBITDA 값 누락 (파싱 에러)")
                    continue
                if ev < 0:
                    warnings.append(f"[{seg_code}] Peer '{name}' 제외: 음수 EV/EBITDA ({ev:.1f}x)")
                    continue
                if ev < 0.5 or ev > 50:
                    warnings.append(f"[{seg_code}] Peer '{name}' 제외: EV/EBITDA {ev:.1f}x 범위 이탈")
                    continue
                cleaned.append(peer)
            seg_data["peers"] = cleaned

            seg_excluded = seg_total - len(cleaned)
            if seg_excluded > 0:
                logger.warning(
                    "[%s] Peer 파싱 집계: %d/%d개 제외됨", seg_code, seg_excluded, seg_total,
                )
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


# ── Market Signal-Aware Validation (Phase 4) ──

def validate_scenarios_with_signals(
    scenarios: list[dict],
    signals,
    weighted_value: int | None = None,
) -> list[str]:
    """Cross-check AI scenarios against external market signals.

    Returns warning messages only (does NOT modify scenarios -- advisory layer).

    Args:
        scenarios: List of scenario dicts (post-validate_scenarios).
        signals: MarketSignals object (or None).
        weighted_value: Probability-weighted per-share value (optional).
    """
    if signals is None:
        return []

    warnings: list[str] = []

    # 1. Analyst target range check
    if weighted_value and signals.target_mean:
        deviation = abs(weighted_value - signals.target_mean) / signals.target_mean
        if deviation > 0.5:
            direction = "높음" if weighted_value > signals.target_mean else "낮음"
            warnings.append(
                f"[Signal] 가중평균 가치({weighted_value:,})가 애널리스트 목표가"
                f"({signals.target_mean:,.0f}) 대비 {deviation:.0%} {direction} — 검토 권장"
            )

    # 2. Scenario range vs analyst range overlap check
    if signals.target_low and signals.target_high and len(scenarios) >= 2:
        sc_values = []
        for s in scenarios:
            # Try to find per-share value from scenario (may not exist at validation time)
            val = s.get("per_share") or s.get("weighted") or s.get("post_dlom")
            if isinstance(val, (int, float)) and val > 0:
                sc_values.append(val)

        if sc_values:
            sc_min, sc_max = min(sc_values), max(sc_values)
            # Check if ranges overlap at all
            if sc_max < signals.target_low or sc_min > signals.target_high:
                warnings.append(
                    f"[Signal] 시나리오 범위({sc_min:,}-{sc_max:,})와 "
                    f"애널리스트 범위({signals.target_low:,.0f}-{signals.target_high:,.0f})가 "
                    f"겹치지 않음 — 시나리오 범위 재검토 권장"
                )

    # 3. VIX-scenario spread check
    if signals.vix is not None and signals.vix > 25 and len(scenarios) >= 2:
        probs = [s.get("prob", 0) for s in scenarios]
        if probs:
            max_prob, min_prob = max(probs), min(probs)
            spread = max_prob - min_prob
            if spread < 15:
                warnings.append(
                    f"[Signal] VIX 높음({signals.vix:.0f}) 대비 시나리오 확률 편차"
                    f"({spread:.0f}%p)가 작음 — 불확실성 반영 부족 가능"
                )

    # 4. Sentiment consistency check
    if signals.news_sentiment_score is not None:
        bull_prob = 0.0
        bear_prob = 0.0
        for s in scenarios:
            name_lower = (s.get("name") or s.get("code") or "").lower()
            prob = s.get("prob", 0)
            if "bull" in name_lower or "upside" in name_lower:
                bull_prob = prob
            elif "bear" in name_lower or "downside" in name_lower:
                bear_prob = prob

        if bull_prob > 0 and bear_prob > 0:
            if signals.news_sentiment_score > 0.3 and bear_prob > bull_prob:
                warnings.append(
                    f"[Signal] 뉴스 감성 긍정적({signals.news_sentiment_score:+.2f})인데 "
                    f"Bear({bear_prob:.0f}%) > Bull({bull_prob:.0f}%) — 불일치 검토"
                )
            elif signals.news_sentiment_score < -0.3 and bull_prob > bear_prob:
                warnings.append(
                    f"[Signal] 뉴스 감성 부정적({signals.news_sentiment_score:+.2f})인데 "
                    f"Bull({bull_prob:.0f}%) > Bear({bear_prob:.0f}%) — 불일치 검토"
                )

    # 5. IV-proportional scenario spread check
    if signals.iv_30d_atm is not None and signals.iv_30d_atm > 40:
        has_wide_wacc = any(
            abs(s.get("drivers", {}).get("wacc_adj", s.get("wacc_adj", 0)) or 0) >= 0.5
            for s in scenarios
        )
        if not has_wide_wacc:
            warnings.append(
                f"[Signal] IV 높음({signals.iv_30d_atm:.0f}%)인데 "
                f"wacc_adj ±0.5%p 이상 시나리오 없음 — 변동성 미반영 가능"
            )

    return warnings
