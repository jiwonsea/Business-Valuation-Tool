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

from schemas.provenance import (
    LEGACY_VERSION,
    NORMALIZATION_VERSION,
    NetDebtComponents,
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
