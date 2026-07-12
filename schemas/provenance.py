"""Provenance contract — every material number carries where it came from.

P1 (PLAN_deep_research.md §1):
  ① 관측치        -> Source                        : 공시/시장데이터. LLM 생성 금지
  ② 명시적 가정   -> DeclaredAssumption            : 허용하되 ①과 분리 + 민감도 필수
  ③ 근거 없는 창작 -> 표현 불가 (타입 자체가 없다)

관측 실패 시의 상수 폴백(§2.4)은 ①도 ②도 아니다 -> FallbackConstant.

P0-0 scope: types + constants only. No parser/engine/DB write path consumes these yet —
new fields stay at their defaults until P0-1. That is intentional.

This module MUST NOT import schemas.models (one-way dependency: models -> provenance).
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional, Union

from pydantic import BaseModel, computed_field, field_validator, model_validator

# ── Version constants ──

# Net debt definition v1 (PLAN §2.1). Bump when the normalization contract changes.
NORMALIZATION_VERSION = "2026.07-nd1"

# Every profile / snapshot produced before P0. Never backfill: the default value
# itself is the information ("computed under the pre-P0 definition").
LEGACY_VERSION = "legacy"


# Only real observation channels. "manual" and "fallback constant" are NOT here —
# a human-entered number is a DeclaredAssumption; a failed fetch is a FallbackConstant.
SourceKind = Literal[
    "SEC EDGAR",
    "DART",
    "EDINET",
    "yfinance",
    "FRED",
    "ECOS",
]

Method = Literal["observed", "derived", "declared_assumption"]

# Only these may appear in an observation ledger (P1 범주 ①).
OBSERVED_METHODS: frozenset[str] = frozenset({"observed", "derived"})

SegmentDisclosureLevel = Literal["L1", "L2", "L3", "none"]

# Only a human can approve a declared assumption (PLAN §1). The identifier after the
# prefix must be non-blank — "human:" alone is unauditable.
_HUMAN_PREFIX = "human:"


# ── P1 범주 ① — 관측치 ──


class Source(BaseModel):
    """An observed (or mechanically derived) number, with its lineage.

    P5 is enforced by the type, not by convention:
      - method="observed"  -> as_of 필수 + (accession 또는 url) 필수
      - method="derived"   -> as_of 필수 + (accession | url | derived_from) 필수
    An "observed" number with no date and no document reference is not an observation;
    it is a claim. `as_of` is also what §2.4 staleness (rf <= 7d / ERP <= 45d) is computed
    from, so allowing it to be None would make the staleness contract uncomputable.

    Never use this to carry an assumption. `method="declared_assumption"` remains in the
    Literal only so foreign/legacy payloads can be *parsed and rejected* instead of
    crashing — `assert_observed_only()` blocks it from every observation ledger.
    """

    value: Union[float, int, str, None] = None
    source: SourceKind
    accession: Optional[str] = None  # SEC accession / DART rcept_no
    url: Optional[str] = None
    as_of: Optional[date] = None
    method: Method = "observed"
    derived_from: list[str] = []  # upstream refs for method="derived"
    stale: bool = False  # 허용 시차 초과 (PLAN §2.4)

    @model_validator(mode="after")
    def require_minimum_provenance(self):
        if self.method not in OBSERVED_METHODS:
            # Not an observation; assert_observed_only() rejects it from any ledger.
            return self

        if self.as_of is None:
            raise ValueError(
                f"Source(method='{self.method}', source='{self.source}'): "
                "as_of는 필수입니다. 기준일 없는 관측치는 §2.4 staleness를 계산할 수 없습니다."
            )

        has_doc_ref = bool(self.accession) or bool(self.url)
        if self.method == "observed" and not has_doc_ref:
            raise ValueError(
                f"Source(method='observed', source='{self.source}'): "
                "accession 또는 url 중 하나는 필수입니다 (P5)."
            )
        if self.method == "derived" and not (has_doc_ref or self.derived_from):
            raise ValueError(
                f"Source(method='derived', source='{self.source}'): "
                "accession · url · derived_from 중 하나는 필수입니다 (P5). "
                "파생값은 무엇에서 파생됐는지 가리켜야 합니다."
            )
        return self


# ── P1 범주 ② — 명시적 가정 ──


class DeclaredAssumption(BaseModel):
    """P1 범주 ②. 관측치가 아니다 — 절대 Source로 표현하지 말 것.

    PLAN §1: "LLM은 *제안*만 하고 근거를 남긴다. 사람이 승인한다."
    그래서 제안자와 승인자를 분리한다. LLM은 approved_by에 들어갈 수 없다.
    민감도는 옵션이 아니다 (§2.6) — sensitivity_required는 Literal[True]다.
    """

    value: float
    rationale: str  # 필수. 빈 문자열 금지
    proposed_by: str = ""  # "llm:claude-sonnet-4" | "human:<user>" | ""
    approved_by: str  # 필수. "human:<user>" — 접두사 + 식별자 둘 다 필요
    at: date  # 필수. 언제 선언됐는지 없으면 감사 불가
    sensitivity_required: Literal[True] = True  # §2.6: 민감도 면제 불가

    @field_validator("rationale")
    @classmethod
    def rationale_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "DeclaredAssumption.rationale은 필수입니다 (빈 문자열 금지). "
                "근거 없는 숫자는 P1 범주 ③이며 표현할 수 없습니다."
            )
        return v

    @field_validator("approved_by")
    @classmethod
    def approved_by_is_an_identified_human(cls, v: str) -> str:
        """'human:' 접두사만으로는 부족하다 — 뒤에 실제 식별자가 있어야 감사가 가능하다."""
        if not v.strip():
            raise ValueError(
                "DeclaredAssumption.approved_by는 필수입니다. "
                "가정은 사람이 승인해야 합니다 (PLAN §1)."
            )
        if not v.startswith(_HUMAN_PREFIX):
            raise ValueError(
                f"DeclaredAssumption.approved_by는 'human:<user>' 형식이어야 합니다: {v!r}. "
                "LLM은 제안(proposed_by)만 할 수 있고 자기 가정을 승인할 수 없습니다."
            )
        if not v[len(_HUMAN_PREFIX) :].strip():
            raise ValueError(
                f"DeclaredAssumption.approved_by에 승인자 식별자가 없습니다: {v!r}. "
                "'human:' 접두사만으로는 누가 승인했는지 감사할 수 없습니다."
            )
        return v


# ── 관측 실패 폴백 (PLAN §2.4) — ①도 ②도 아니다 ──


class FallbackConstant(BaseModel):
    """관측에 실패했을 때 쓰는 상수. 관측치인 척하면 안 된다.

    §2.4: "실패 시 상수 폴백하되 rf_source: 'fallback constant' + 기준일 + stale TTL을
    반드시 기록한다." 폴백은 기본적으로 stale이며, 그 사실이 산출물에 드러나야 한다.
    """

    value: float
    reason: str  # 필수: 왜 관측이 실패했는가 (예: "FRED DGS10 timeout x3")
    as_of: date  # 필수: 이 상수가 대표하는 기준일
    ttl_days: int  # 필수: 허용 시차 (rf=7, ERP=45)
    stale: bool = True  # 폴백은 반증되기 전까지 stale로 취급한다

    @field_validator("reason")
    @classmethod
    def reason_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("FallbackConstant.reason은 필수입니다 (관측 실패 사유).")
        return v

    @field_validator("ttl_days")
    @classmethod
    def ttl_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"FallbackConstant.ttl_days는 양수여야 합니다: {v}")
        return v


def assert_observed_only(
    mapping: dict[str, Source], field_name: str = "assumption_sources"
) -> dict[str, Source]:
    """Guard: an observation ledger may only hold observed/derived Sources.

    Blocks the back door of smuggling an assumption in as a Source with
    method="declared_assumption". Use DeclaredAssumption instead.
    """
    for key, src in mapping.items():
        if src.method not in OBSERVED_METHODS:
            raise ValueError(
                f"{field_name}['{key}']: method='{src.method}'는 관측치가 아닙니다. "
                f"허용: {sorted(OBSERVED_METHODS)}. "
                "가정은 declared_assumptions(DeclaredAssumption)에 저장하십시오."
            )
    return mapping


# ── 순차입금 taxonomy (PLAN §2.1) ──

_CASH_FIELDS = ("cash", "marketable_debt_securities", "short_term_investments")


class NetDebtComponents(BaseModel):
    """§2.1. 합계만 저장하면 정의 오류를 영원히 못 잡는다.

    expected_net_debt() = gross_borrowings
                          - (cash + marketable_debt_securities + short_term_investments)

    `net_debt`는 **독립적으로 관측/보고된 합계**다. 구성요소에서 유도하지 않는다 —
    유도해 버리면 대조가 정의로 퇴화하고 `reconciled`는 공허한 참이 된다.

    `reconciled`는 3-상태다:
      True  : 독립 합계와 구성요소 합이 일치
      False : 불일치 (예외를 던지지 않는다 — 차단은 게이트의 책임, PLAN §2.8)
      None  : 대조 불가 (합계 미제공 또는 구성요소 결측). 빈 객체는 통과가 아니라 None이다.

    P0-1은 `reconciled is True`일 때만 정상화 값을 소비해야 한다.

    `*_excluded` 필드는 의도적으로 **차감하지 않은** 금액이다 (제한현금 / 시장성 지분증권 —
    후자는 별도 상방 브리지로 간다). 기록용이며 합계에 들어가지 않는다.

    모든 금액은 프로필의 display unit ($M / 백만원) 기준.
    """

    cash: Optional[int] = None
    marketable_debt_securities: Optional[int] = None
    short_term_investments: Optional[int] = None
    restricted_cash_excluded: Optional[int] = None  # 차감하지 '않은' 금액 (기록용)
    equity_securities_excluded: Optional[int] = None  # 차감하지 '않은' 금액 (상방 브리지)
    gross_borrowings: Optional[int] = None
    net_debt: Optional[int] = None  # 독립 관측/보고된 합계. 유도하지 않는다.

    @property
    def deductible_cash(self) -> Optional[int]:
        """Cash deducted from gross borrowings. None when nothing was disclosed."""
        if all(getattr(self, f) is None for f in _CASH_FIELDS):
            return None
        return sum(getattr(self, f) or 0 for f in _CASH_FIELDS)

    @property
    def has_components(self) -> bool:
        """Both sides present? Imputing a missing side would be fabrication."""
        return self.gross_borrowings is not None and self.deductible_cash is not None

    def expected_net_debt(self) -> Optional[int]:
        """Net debt implied by the components. None when they cannot support it."""
        if not self.has_components:
            return None
        return self.gross_borrowings - self.deductible_cash

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reconciled(self) -> Optional[bool]:
        """3-state. Computed, never stored — so it cannot be round-tripped into a lie."""
        expected = self.expected_net_debt()
        if expected is None or self.net_debt is None:
            return None
        return self.net_debt == expected
