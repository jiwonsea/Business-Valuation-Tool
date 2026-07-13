"""Net debt normalization gate (PLAN_deep_research.md §2.1 — P0-1).

Pure functions only (no IO, no state) — see CLAUDE.md 'engine/ functions must be pure'.

계약 (CODEX 5차 확정, HANDOFF_CODEX_p0-0_commit.md §8):

  1. 파서는 `net_debt`(독립 합계)와 구성요소를 **서로 다른 원천**에서 수집한다.
     구성요소를 더해서 `net_debt`에 넣으면 `reconciled`는 항상 True가 되고 대조는 공허해진다.
  2. 엔진은 **`reconciled is True`일 때만** 정규화 값을 소비한다.
  3. `False`(불일치)와 `None`(대조 불가)은 **둘 다 차단**이며, 차단 시 legacy 스칼라
     (`ValuationInput.net_debt`, 즉 파서의 `net_borr`)로 되돌아간다. 임의 생성 금지.

소비되는 "정규화 값"은 **taxonomy 정의값**(`expected_net_debt()`)이다:
    gross_borrowings − (cash + marketable_debt_securities + short_term_investments)
독립 합계(`net_debt`)는 그 정의값을 **검증**하는 대조 축이지, 소비 대상이 아니다.
둘의 차이는 게이트를 통과한 시점에 이미 반올림 허용오차 이내임이 보장된다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import math
from datetime import date

from schemas.provenance import (
    BETA_MIN_PEER_COUNT,
    BETA_PLAUSIBLE_RANGE,
    BETA_REFERENCE_CONFLICT_MULTIPLE,
    LEGACY_VERSION,
    NORMALIZATION_VERSION,
    BetaBasis,
    BetaObservation,
    BetaPeerSnapshot,
    IndustryBetaEntry,
    NetDebtComponents,
    hamada_unlever,
)

# consumed               : reconciled is True  -> 정규화 값 소비
# blocked_mismatch       : reconciled is False -> 정의 불일치. legacy 유지
# blocked_unreconcilable : reconciled is None  -> 독립 합계 또는 구성요소 결측. legacy 유지
# absent                 : 구성요소 자체가 없음 (P0 이전 프로필) -> legacy 유지
NetDebtStatus = Literal[
    "consumed", "blocked_mismatch", "blocked_unreconcilable", "absent"
]

BLOCKED_STATUSES: frozenset[str] = frozenset(
    {"blocked_mismatch", "blocked_unreconcilable"}
)


@dataclass(frozen=True)
class NetDebtResolution:
    """게이트 판정 결과. `value`가 엔진이 실제로 쓰는 순차입금이다."""

    value: int  # 엔진 소비값 (display unit)
    status: NetDebtStatus
    normalization_version: str
    legacy_value: int  # 파서 net_borr (gross − cash). 감사용으로 항상 보존
    normalized_value: Optional[int] = None  # taxonomy 정의값. 차단 시에도 기록
    independent_total: Optional[int] = None  # 독립 원천 합계 (대조 축)
    delta: Optional[int] = None  # 독립 합계 − taxonomy 정의값
    reason: str = ""

    @property
    def consumed(self) -> bool:
        return self.status == "consumed"

    @property
    def blocked(self) -> bool:
        return self.status in BLOCKED_STATUSES

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "status": self.status,
            "normalization_version": self.normalization_version,
            "legacy_value": self.legacy_value,
            "normalized_value": self.normalized_value,
            "independent_total": self.independent_total,
            "delta": self.delta,
            "reason": self.reason,
        }


def resolve_net_debt(
    components: Optional[NetDebtComponents],
    legacy_net_debt: int,
) -> NetDebtResolution:
    """§2.1 게이트. reconciled is True일 때만 정규화 값을, 아니면 legacy 값을 돌려준다.

    Args:
        components: 파서가 수집한 구성요소 + 독립 합계. None이면 P0 이전 프로필.
        legacy_net_debt: 기존 스칼라 (`net_borr` = gross_borr − cash). 폴백 축.

    Returns:
        NetDebtResolution — `value`는 항상 채워진다 (차단 시 legacy_net_debt).
    """
    if components is None:
        return NetDebtResolution(
            value=legacy_net_debt,
            status="absent",
            normalization_version=LEGACY_VERSION,
            legacy_value=legacy_net_debt,
            reason="net_debt_components 없음 (P0 이전 프로필) — legacy 정의 유지",
        )

    expected = components.expected_net_debt()
    reconciled = components.reconciled

    if reconciled is None:
        if not components.has_components:
            reason = (
                "구성요소 결측 (차입 또는 현금 한쪽 미공시) — 대조 불가. "
                "결측 측을 0으로 채우는 것은 정상화가 아니라 날조다."
            )
        else:
            reason = (
                "독립 합계(net_debt) 미수집 — 대조 불가. "
                "구성요소 합으로 채우면 대조가 정의로 퇴화한다."
            )
        return NetDebtResolution(
            value=legacy_net_debt,
            status="blocked_unreconcilable",
            normalization_version=LEGACY_VERSION,
            legacy_value=legacy_net_debt,
            normalized_value=expected,
            independent_total=components.net_debt,
            delta=components.reconciliation_delta,
            reason=reason,
        )

    if reconciled is False:
        return NetDebtResolution(
            value=legacy_net_debt,
            status="blocked_mismatch",
            normalization_version=LEGACY_VERSION,
            legacy_value=legacy_net_debt,
            normalized_value=expected,
            independent_total=components.net_debt,
            delta=components.reconciliation_delta,
            reason=(
                f"독립 합계 {components.net_debt:,} vs 구성요소 정의값 {expected:,} "
                f"(차이 {components.reconciliation_delta:,}) — 반올림으로 설명 불가한 "
                "정의 불일치. 정규화 값을 소비하지 않는다."
            ),
        )

    # reconciled is True — 유일한 소비 경로
    assert expected is not None  # reconciled True면 항상 참
    return NetDebtResolution(
        value=expected,
        status="consumed",
        normalization_version=NORMALIZATION_VERSION,
        legacy_value=legacy_net_debt,
        normalized_value=expected,
        independent_total=components.net_debt,
        delta=components.reconciliation_delta,
        reason="독립 합계와 대조 일치 — §2.1 정의값 소비",
    )


# ══════════════════════════════════════════════════════════════════════════════
# 베타 정상화 (PLAN §2.3 / §2.5) — P0-2a 계약
#
# 계약 (CODEX P0-2 판정 + 재작업 판정):
#   1. 상장/비상장을 분리한다. "raw beta 없으면 차단"은 비상장을 전부 막는다.
#   2. **basis를 분리한다.** 일반 기업은 unlevered, 금융업은 equity beta를 그대로 쓴다
#      (engine/wacc.py: is_financial이면 Hamada를 건너뛰고 bu를 βL로 사용).
#      basis가 다른 값끼리 비교·대체하지 않는다 — 배선층에서 몰래 우회하면 provenance가 거짓이 된다.
#   3. 교차검증은 **같은 basis끼리** 한다. raw βL을 먼저 언레버한 뒤 peer median unlevered와 비교한다
#      (레버리지 높은 회사가 정상 값으로도 충돌 판정되던 오류 — CODEX 블로커 3).
#   4. 자동 클램프·자동 상수 대체 금지. 범위 이탈([0.3, 2.0])은 경고 + 민감도 표시일 뿐이다.
#      단 **NaN/Inf 차단은 클램프가 아니다** — 애초에 관측치가 아닌 것을 걸러내는 일이다.
#   5. 차단 시 `normalized_value`는 None이고 `diagnostic_value`(legacy)만 남는다.
#      진단 실행 경계에서 diagnostic_value를 **명시적으로** 선택해야 쓸 수 있다 (우회 소비 차단).
#   6. `evaluation_date`는 필수 인자다. engine/은 순수해야 하므로 date.today()를 읽지 않는다.
#
# 소비 배선(profile_generator / valuation_runner / ai.validators)은 P0-2b이며 P0-4 이후에 붙인다.
# ══════════════════════════════════════════════════════════════════════════════

BetaStatus = Literal[
    "consumed_raw",  # 상장 · unlevered basis: 검증된 raw βL -> Hamada 언레버
    "consumed_raw_equity",  # 상장 · equity basis(금융업): raw βL 그대로
    "consumed_peer_median",  # 비상장: peer median (target basis와 동일 basis)
    "consumed_industry_table",  # 비상장 · unlevered basis: 버전 고정 산업 테이블
    "blocked_invalid_number",  # NaN/Inf
    "blocked_invalid_capital_structure",  # D/E < 0, 세율 정의역 밖, Hamada 분모 <= 0
    "blocked_no_provenance",  # 관측창/빈도/출처 없는 beta
    "blocked_invalid_observation",  # 대상 beta 관측창이 평가일보다 미래 (look-ahead)
    "blocked_stale_observation",  # 대상 beta 관측이 허용 시차(7일) 초과
    "blocked_no_capital_structure",  # D/E·세율 결측
    "blocked_reference_conflict",  # 같은 basis 대조에서 중대 불일치 (× 1.5 초과)
    "blocked_basis_mismatch",  # peer 스냅샷 basis != target basis
    "blocked_stale_peer_snapshot",  # peer 스냅샷 허용 시차(7일) 초과
    "blocked_invalid_peer_snapshot",  # peer 스냅샷 기준일이 미래 (look-ahead)
    "blocked_no_reference",  # 비상장: peer 부족 + 산업 테이블 없음/사용 불가
    "blocked_stale_industry_table",  # 산업 테이블 400일 초과
    "blocked_invalid_industry_table",  # 산업 테이블 기준일이 미래/부재
]

_CONSUMED_BETA_STATUSES: frozenset[str] = frozenset(
    s for s in BetaStatus.__args__ if s.startswith("consumed_")
)


@dataclass(frozen=True)
class BetaResolution:
    """베타 게이트 판정. 불변식을 생성 시점에 강제한다 — 위조 불가.

    - consumed 상태 -> normalized_value는 유한한 실수여야 한다
    - blocked 상태  -> normalized_value는 None이어야 한다
    - diagnostic_value가 있으면 유한해야 한다
    - peer_count >= 0
    """

    status: BetaStatus
    basis: BetaBasis
    normalized_value: Optional[float] = None
    diagnostic_value: Optional[float] = None
    raw_levered_beta: Optional[float] = None
    unlevered_from_raw: Optional[float] = None
    blume_adjusted: Optional[float] = None
    peer_median: Optional[float] = None
    peer_count: int = 0
    sensitivity_required: bool = False
    warnings: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        if self.status not in BetaStatus.__args__:
            raise ValueError(f"BetaResolution.status가 계약에 없는 값입니다: {self.status!r}")
        if self.consumed:
            if self.normalized_value is None or not math.isfinite(self.normalized_value):
                raise ValueError(
                    f"BetaResolution(status={self.status!r}): 소비 상태에는 유한한 "
                    f"normalized_value가 필요합니다 (받은 값: {self.normalized_value!r})."
                )
        elif self.normalized_value is not None:
            raise ValueError(
                f"BetaResolution(status={self.status!r}): 차단 상태에는 소비 가능한 값이 "
                "존재할 수 없습니다. normalized_value는 None이어야 합니다."
            )
        if self.diagnostic_value is not None and not math.isfinite(self.diagnostic_value):
            raise ValueError(
                f"BetaResolution.diagnostic_value가 유효한 숫자가 아닙니다: {self.diagnostic_value!r}"
            )
        if self.peer_count < 0:
            raise ValueError(f"BetaResolution.peer_count는 음수일 수 없습니다: {self.peer_count}")
        if not self.reason.strip():
            raise ValueError("BetaResolution.reason은 필수입니다 (판정 근거 없는 판정은 감사 불가).")

    @property
    def consumed(self) -> bool:
        return self.status in _CONSUMED_BETA_STATUSES

    @property
    def publishable(self) -> bool:
        """저장 필드가 아니라 status에서 계산된다 — 위조할 수 없다."""
        return self.consumed

    @property
    def blocked(self) -> bool:
        return not self.consumed

    def value_for(self, mode: Literal["publish", "diagnostic"]) -> Optional[float]:
        """소비 경계에서 **명시적으로** 값을 고른다.

        publish 모드는 차단된 판정에서 값을 내주지 않는다 — 우회 소비가 구조적으로 불가능하다.
        """
        if mode == "publish":
            return self.normalized_value
        return self.normalized_value if self.consumed else self.diagnostic_value


def hamada_denominator(de_ratio_pct: float, tax_rate_pct: float) -> float:
    """1 + (1 - t) × D/E. 0 이하면 언레버가 정의되지 않는다."""
    return 1 + (1 - tax_rate_pct / 100) * de_ratio_pct / 100


def valid_capital_structure(de_ratio_pct: float, tax_rate_pct: float) -> bool:
    """경제적 정의역: D/E >= 0 (gross debt 기반), 세율 [0, 100], Hamada 분모 > 0.

    정의역 밖의 값은 **클램프하지 않고 차단한다** — 관측치가 아니라 오류다.
    """
    if not (math.isfinite(de_ratio_pct) and math.isfinite(tax_rate_pct)):
        return False
    if de_ratio_pct < 0 or not (0.0 <= tax_rate_pct <= 100.0):
        return False
    return hamada_denominator(de_ratio_pct, tax_rate_pct) > 0


def unlever_beta(levered_beta: float, de_ratio_pct: float, tax_rate_pct: float) -> float:
    """Hamada 언레버. **클램프하지 않는다** (§2.3).

    engine/wacc.py의 리레버 D/E 200% cap은 별도 방법론 정책이며 여기서 건드리지 않는다.
    정의역 밖이면 ValueError — 조용히 기본값으로 넘어가지 않는다.
    """
    result = hamada_unlever(levered_beta, de_ratio_pct, tax_rate_pct)
    if result is None:
        raise ValueError(
            f"unlever_beta: 언레버가 정의되지 않습니다 "
            f"(beta={levered_beta!r}, D/E={de_ratio_pct!r}%, tax={tax_rate_pct!r}%)."
        )
    return result


def _range_warnings(beta: Optional[float]) -> tuple[bool, tuple[str, ...]]:
    """범위 이탈 판정. 경고 + 민감도 표시일 뿐, 값을 깎지 않는다."""
    lo, hi = BETA_PLAUSIBLE_RANGE
    if beta is None or lo <= beta <= hi:
        return False, ()
    return True, (
        f"beta {beta:.3f}가 타당성 범위 [{lo}, {hi}] 밖입니다 — 값을 대체하지 않습니다. "
        "WACC 민감도에 반드시 표시하십시오 (§2.3).",
    )


def resolve_beta(
    *,
    evaluation_date: date,
    is_listed: bool,
    target_basis: BetaBasis = "unlevered",
    observation: Optional[BetaObservation] = None,
    de_ratio_pct: Optional[float] = None,
    tax_rate_pct: Optional[float] = None,
    peer_snapshot: Optional[BetaPeerSnapshot] = None,
    industry_entry: Optional[IndustryBetaEntry] = None,
    legacy_unlevered_beta: Optional[float] = None,
) -> BetaResolution:
    """§2.3 베타 게이트 (P0-2a). 순수 함수 — IO 없음, 현재 시각을 읽지 않음."""
    peer_median = peer_snapshot.median_beta if peer_snapshot else None
    peer_count = peer_snapshot.peer_count if peer_snapshot else 0
    raw_bl = observation.raw_levered_beta if observation else None

    def blocked(status: BetaStatus, reason: str) -> BetaResolution:
        diag = legacy_unlevered_beta
        if diag is not None and not math.isfinite(diag):
            diag = None  # 진단값조차 유효하지 않으면 들고 다니지 않는다
        return BetaResolution(
            status=status,
            basis=target_basis,
            normalized_value=None,
            diagnostic_value=diag,
            raw_levered_beta=raw_bl,
            peer_median=peer_median,
            peer_count=max(peer_count, 0),
            warnings=(f"베타 정상화 차단 ({status}) — publish 불가.",),
            reason=reason,
        )

    def consumed(
        status: BetaStatus,
        value: float,
        reason: str,
        *,
        unlevered_from_raw: Optional[float] = None,
        extra_warnings: tuple[str, ...] = (),
    ) -> BetaResolution:
        needs_sens, warns = _range_warnings(value)
        diag = legacy_unlevered_beta
        if diag is not None and not math.isfinite(diag):
            diag = None
        return BetaResolution(
            status=status,
            basis=target_basis,
            normalized_value=value,
            diagnostic_value=diag,
            raw_levered_beta=raw_bl,
            unlevered_from_raw=unlevered_from_raw,
            blume_adjusted=observation.blume() if observation else None,
            peer_median=peer_median,
            peer_count=peer_count,
            sensitivity_required=needs_sens,
            warnings=warns + extra_warnings,
            reason=reason,
        )

    # ── 0. 유효하지 않은 숫자 (클램프가 아니다 — 관측치가 아닌 것을 거른다) ──
    for name, v in (
        ("de_ratio_pct", de_ratio_pct),
        ("tax_rate_pct", tax_rate_pct),
        ("peer_median", peer_median),
        ("raw_levered_beta", raw_bl),
    ):
        if v is not None and not math.isfinite(float(v)):
            return blocked(
                "blocked_invalid_number",
                f"{name}가 유효한 숫자가 아닙니다 ({v!r}). NaN/Inf는 관측치가 아닙니다.",
            )

    # ── 0b. 대상 회사 beta의 시간축 (peer만 검사하면 target의 look-ahead가 열린다) ──
    if observation is not None:
        obs_freshness = observation.freshness(evaluation_date)
        if obs_freshness == "future":
            return blocked(
                "blocked_invalid_observation",
                f"대상 beta 관측창이 평가일보다 미래입니다 "
                f"(window_end={observation.window_end}, 평가일={evaluation_date}) — look-ahead.",
            )
        if obs_freshness in ("stale", "unknown_as_of"):
            return blocked(
                "blocked_stale_observation",
                f"대상 beta 관측이 stale입니다 (as_of={observation.as_of}, "
                f"평가일={evaluation_date}, §2.5 허용 시차 초과).",
            )

    # ── 0c. peer 스냅샷: basis 정합성 + 신선도 ──
    # 미래 스냅샷은 look-ahead이므로 즉시 차단한다.
    # stale 스냅샷은 **peer 근거에서 제외**할 뿐, 유효한 다른 근거(raw beta / 산업 테이블)까지
    # 막지 않는다 (§2.3 우선순위). 다른 근거가 없을 때만 blocked_stale_peer_snapshot이 된다.
    peer_stale = False
    if peer_snapshot is not None:
        if peer_snapshot.beta_basis != target_basis:
            return blocked(
                "blocked_basis_mismatch",
                f"peer 스냅샷 basis='{peer_snapshot.beta_basis}' != target basis='{target_basis}'. "
                "basis가 다른 beta끼리는 비교도 대체도 할 수 없습니다.",
            )
        snap_freshness = peer_snapshot.freshness(evaluation_date)
        if snap_freshness == "future":
            return blocked(
                "blocked_invalid_peer_snapshot",
                f"peer 스냅샷 기준일이 미래입니다 (as_of={peer_snapshot.as_of}, "
                f"평가일={evaluation_date}) — look-ahead.",
            )
        if snap_freshness in ("stale", "unknown_as_of"):
            peer_stale = True
            peer_median = None  # 오래된 시장 데이터로 대체도, 교차검증도 하지 않는다
            peer_count = 0

    # ── 0d. target vs peer 데이터셋 동일성 ──
    # S&P 500 기준 target beta를 KOSPI 기준 peer median으로 반증할 수는 없다.
    # 미래 데이터가 아니라 '비교 불가'이므로, stale peer와 동일하게 **peer 근거에서 제외**하고
    # 경고한다 (상장사의 primary는 raw beta다).
    peer_dataset_mismatch: list[str] = []
    if (
        peer_snapshot is not None
        and not peer_stale
        and observation is not None
        and peer_snapshot.members
    ):
        reference = next(
            (m.observation for m in peer_snapshot.members if m.included and m.observation),
            None,
        )
        if reference is not None:
            peer_dataset_mismatch = observation.dataset_mismatches(reference)
        if peer_dataset_mismatch:
            peer_median = None
            peer_count = 0

    peer_excluded_warning: tuple[str, ...] = ()
    if peer_stale:
        peer_excluded_warning = (
            f"peer 스냅샷이 stale이라(as_of={peer_snapshot.as_of}) peer 교차검증을 수행하지 "
            "못했습니다 — beta 대조 없이 소비합니다.",
        )
    elif peer_dataset_mismatch:
        peer_excluded_warning = (
            f"peer 스냅샷이 대상 beta와 다른 데이터셋입니다 ({peer_dataset_mismatch}) — "
            "교차검증에서 제외했습니다. 서로 다른 벤치마크·관측창의 beta는 서로를 반증할 수 없습니다.",
        )

    credible_peers = peer_median is not None and peer_count >= BETA_MIN_PEER_COUNT

    # ── 1. 상장사 ──
    if is_listed:
        if observation is None or raw_bl is None:
            return blocked(
                "blocked_no_provenance",
                "관측창·빈도·벤치마크가 기록된 raw equity beta가 없습니다. "
                "yfinance info['beta']처럼 관측창을 알 수 없는 값은 §2.3 관측치가 아닙니다. "
                "상수(default_bu) 대체는 금지입니다.",
            )

        # 금융업(equity basis): 언레버하지 않는다. wacc.py가 bu를 βL로 직접 쓴다.
        if target_basis == "equity":
            if credible_peers and raw_bl > peer_median * BETA_REFERENCE_CONFLICT_MULTIPLE:
                return blocked(
                    "blocked_reference_conflict",
                    f"raw βL {raw_bl:.3f} > peer median equity beta {peer_median:.3f} × "
                    f"{BETA_REFERENCE_CONFLICT_MULTIPLE} — 중대 불일치가 해소되지 않았습니다.",
                )
            return consumed(
                "consumed_raw_equity",
                raw_bl,
                f"금융업(equity basis): 검증된 raw βL {raw_bl:.3f} "
                f"({observation.window_start}~{observation.window_end}, {observation.frequency}, "
                f"{observation.benchmark}) — Hamada 언레버를 적용하지 않습니다.",
                extra_warnings=peer_excluded_warning,
            )

        # 일반 기업(unlevered basis): Hamada 언레버 필요
        if de_ratio_pct is None or tax_rate_pct is None:
            return blocked(
                "blocked_no_capital_structure",
                "D/E 또는 세율이 없어 Hamada 언레버를 계산할 수 없습니다. "
                "빠진 값을 기본값으로 채우지 않습니다.",
            )
        if not valid_capital_structure(de_ratio_pct, tax_rate_pct):
            return blocked(
                "blocked_invalid_capital_structure",
                f"자본구조가 경제적 정의역 밖입니다 (D/E={de_ratio_pct}%, tax={tax_rate_pct}%). "
                "D/E는 gross debt 기반이라 음수일 수 없고, 세율은 [0, 100]이며, "
                "Hamada 분모는 양수여야 합니다. 클램프하지 않고 차단합니다.",
            )

        target_bu = unlever_beta(raw_bl, de_ratio_pct, tax_rate_pct)

        # §2.3 중대 불일치 — **같은 basis끼리** 비교한다 (언레버 후 vs peer median unlevered).
        if credible_peers and target_bu > peer_median * BETA_REFERENCE_CONFLICT_MULTIPLE:
            return blocked(
                "blocked_reference_conflict",
                f"언레버 beta {target_bu:.3f} > peer median unlevered {peer_median:.3f} × "
                f"{BETA_REFERENCE_CONFLICT_MULTIPLE} — 중대 불일치가 해소되지 않았습니다. "
                "사람이 override하고 {원값, 대체값, 사유, WACC 민감도}를 남겨야 합니다.",
            )

        return consumed(
            "consumed_raw",
            target_bu,
            f"검증된 raw βL {raw_bl:.3f} ({observation.window_start}~{observation.window_end}, "
            f"{observation.frequency}, {observation.benchmark}) -> Hamada 언레버 {target_bu:.3f}",
            unlevered_from_raw=target_bu,
            extra_warnings=peer_excluded_warning,
        )

    # ── 2. 비상장사 ──
    if credible_peers:
        return consumed(
            "consumed_peer_median",
            float(peer_median),
            f"peer median {target_basis} beta (유효 peer {peer_count}개 >= {BETA_MIN_PEER_COUNT}, "
            f"스냅샷 {peer_snapshot.snapshot_id}@{peer_snapshot.snapshot_version}, "
            f"as_of {peer_snapshot.as_of})",
        )

    if industry_entry is not None:
        if target_basis != "unlevered":
            return blocked(
                "blocked_no_reference",
                "산업 beta 테이블은 unlevered basis입니다 — equity basis(금융업) 대체로 쓸 수 없습니다. "
                "금융업 peer 통계는 equity basis로 별도 산출해야 합니다.",
            )
        freshness = industry_entry.freshness(evaluation_date)
        if freshness == "stale":
            return blocked(
                "blocked_stale_industry_table",
                f"산업 beta 테이블({industry_entry.table_version})이 stale입니다 "
                f"(기준일 {industry_entry.source.as_of}, 평가일 {evaluation_date}). "
                "stale 자료가 비상장사의 유일한 beta 근거라면 소비하지 않습니다.",
            )
        if freshness in ("future", "unknown_as_of"):
            return blocked(
                "blocked_invalid_industry_table",
                f"산업 beta 테이블의 기준일이 {'미래' if freshness == 'future' else '없음'}입니다 "
                f"(as_of={industry_entry.source.as_of}, 평가일={evaluation_date}). "
                "look-ahead이거나 신선도를 계산할 수 없으므로 소비하지 않습니다.",
            )
        return consumed(
            "consumed_industry_table",
            industry_entry.unlevered_beta,
            f"산업 beta 테이블 {industry_entry.industry_key} ({industry_entry.table_version}, "
            f"sha {industry_entry.table_sha256[:8]}, 매핑 {industry_entry.mapping_version})",
            extra_warnings=peer_excluded_warning
            + (
                f"유효 peer {peer_count}개 < {BETA_MIN_PEER_COUNT} — 산업 테이블로 대체했습니다.",
            ),
        )

    if peer_stale:
        return blocked(
            "blocked_stale_peer_snapshot",
            f"peer 스냅샷이 stale이고(as_of={peer_snapshot.as_of}, 평가일={evaluation_date}) "
            "대체할 산업 테이블도 없습니다. 오래된 시장 데이터로 beta를 대체하지 않습니다.",
        )

    return blocked(
        "blocked_no_reference",
        f"유효 peer {peer_count}개 < {BETA_MIN_PEER_COUNT}이고 산업 테이블도 없습니다. "
        "상수 대체 없이 차단합니다 (§2.3).",
    )
