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

import math
import re
import statistics
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
    "Damodaran",  # 산업 beta 연간 테이블 (정적 스냅샷). yfinance로 위장 금지
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


# ── 베타 정책 (PLAN §2.3 / §2.5) — P0-2a 계약 ──
#
# 금칙 (§2.3): "범위 이탈은 차단 사유도, 자동 대체 사유도 아니다. 자동 클램프/대체 금지."
# 아래 상수는 **경고·차단 판정에만** 쓴다. 값을 깎거나 갈아끼우는 데 쓰지 않는다.
#
# 단, **유효하지 않은 숫자(NaN/Inf)나 경제적 정의역 밖의 자본구조를 차단하는 것은 클램프가 아니다.**
# 클램프는 유효한 관측치를 몰래 왜곡하는 행위이고, 이쪽은 애초에 관측치가 아닌 것을 걸러내는 행위다.

BETA_PLAUSIBLE_RANGE: tuple[float, float] = (0.3, 2.0)

# raw beta가 peer median의 이 배수를 넘으면 중대 불일치 (§2.3). **같은 basis끼리 비교한다.**
BETA_REFERENCE_CONFLICT_MULTIPLE = 1.5

# §2.5 peer 최소 수. beta만 별도 기준을 두지 않는다.
BETA_MIN_PEER_COUNT = 4

# beta 관측/peer 스냅샷 허용 시차 (§2.5). 시장 데이터이므로 짧다.
# 대상 회사 beta에도 동일하게 적용한다 — peer만 검사하면 target의 look-ahead가 열린다.
BETA_OBSERVATION_MAX_AGE_DAYS = 7
BETA_PEER_SNAPSHOT_MAX_AGE_DAYS = 7

# 산업 beta 테이블(연 1회) 허용 시차.
INDUSTRY_BETA_MAX_AGE_DAYS = 400

BetaFrequency = Literal["daily", "weekly", "monthly"]

# 베타의 기준(basis). 일반 기업은 unlevered, 금융업은 equity beta를 그대로 쓴다
# (engine/wacc.py: is_financial이면 Hamada를 건너뛰고 bu를 βL로 사용).
BetaBasis = Literal["unlevered", "equity"]

Freshness = Literal["fresh", "stale", "future", "unknown_as_of"]

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def require_finite(value: Optional[float], field: str) -> Optional[float]:
    """NaN/Inf 차단. None은 통과시킨다 (결측은 별도로 판정한다)."""
    if value is None:
        return None
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(f"{field}: 유효하지 않은 숫자입니다 ({value!r}). NaN/Inf는 관측치가 아닙니다.")
    return v


def require_sha256(value: str, field: str) -> str:
    """재현성 해시는 형식이 맞아야 의미가 있다 — 'x'는 해시가 아니다."""
    v = value.strip().lower()
    if not _SHA256_RE.match(v):
        raise ValueError(f"{field}: SHA-256 형식이 아닙니다 (64자리 hex): {value!r}")
    return v


def _numeric_source_value(src: Optional[Source], field: str) -> Optional[float]:
    """Source가 숫자 관측치를 담고 있으면 그 값을, 아니면 None."""
    if src is None:
        return None
    v = src.value
    if not isinstance(v, (int, float)):
        return None
    return require_finite(float(v), field)


def _freshness(as_of: Optional[date], evaluation_date: date, max_age_days: int) -> Freshness:
    """공통 신선도 판정. 미래 기준일은 look-ahead이므로 fresh가 아니다."""
    if as_of is None:
        return "unknown_as_of"
    if as_of > evaluation_date:
        return "future"
    if (evaluation_date - as_of).days > max_age_days:
        return "stale"
    return "fresh"


def hamada_unlever(levered_beta: float, de_ratio_pct: float, tax_rate_pct: float) -> Optional[float]:
    """Hamada 언레버. 경제적 정의역 밖이면 None (클램프하지 않는다).

    - D/E는 gross debt 기반이므로 음수일 수 없다.
    - 세율은 [0, 100] 밖일 수 없다.
    - 분모 <= 0이면 언레버가 정의되지 않는다.
    """
    for v in (levered_beta, de_ratio_pct, tax_rate_pct):
        if not math.isfinite(v):
            return None
    if de_ratio_pct < 0 or not (0.0 <= tax_rate_pct <= 100.0):
        return None
    denom = 1 + (1 - tax_rate_pct / 100) * de_ratio_pct / 100
    if denom <= 0:
        return None
    return levered_beta / denom


class BetaObservation(BaseModel):
    """상장사의 raw equity beta 관측 (§2.3).

    관측창·빈도·벤치마크는 beta 전용 의미라 범용 `Source`에 넣지 않는다.
    **관측창과 빈도를 알 수 없는 값은 §2.3 관측치가 아니다** — yfinance `info["beta"]`는
    이 타입을 만들 수 없고, 게이트가 `blocked_no_provenance`로 차단한다.
    """

    equity_beta: Source
    window_start: date
    window_end: date
    frequency: BetaFrequency
    benchmark: str
    observation_count: int
    calculation_method: str

    @field_validator("benchmark", "calculation_method")
    @classmethod
    def non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "BetaObservation.benchmark / calculation_method는 필수입니다. "
                "관측창·빈도·벤치마크 없는 beta는 §2.3의 관측치가 아닙니다."
            )
        return v

    @field_validator("observation_count")
    @classmethod
    def observation_count_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"BetaObservation.observation_count는 양수여야 합니다: {v}")
        return v

    @model_validator(mode="after")
    def validate_observation(self):
        if self.window_end <= self.window_start:
            raise ValueError(
                f"BetaObservation 관측창이 뒤집혔습니다: {self.window_start} ~ {self.window_end}"
            )
        if self.equity_beta.method not in OBSERVED_METHODS:
            raise ValueError(
                f"BetaObservation.equity_beta.method='{self.equity_beta.method}'는 관측치가 아닙니다."
            )
        v = self.equity_beta.value
        if not isinstance(v, (int, float)):
            raise ValueError(f"BetaObservation.equity_beta.value는 숫자여야 합니다: {v!r}")
        require_finite(float(v), "BetaObservation.equity_beta.value")

        # 관측 기준일은 관측창의 끝이다. 2020년에 끝난 관측창을 오늘 날짜로 포장할 수 없다.
        if self.equity_beta.as_of != self.window_end:
            raise ValueError(
                f"BetaObservation: equity_beta.as_of({self.equity_beta.as_of})가 "
                f"window_end({self.window_end})와 다릅니다. 관측 기준일은 관측창의 끝이어야 합니다 — "
                "오래된 관측창을 최신 기준일로 포장할 수 없습니다."
            )
        return self

    def freshness(self, evaluation_date: date) -> Freshness:
        """대상 회사 beta에도 시간축을 강제한다 (§2.5 허용 시차 7일, 미래는 look-ahead)."""
        if self.window_end > evaluation_date:
            return "future"
        return _freshness(self.equity_beta.as_of, evaluation_date, BETA_OBSERVATION_MAX_AGE_DAYS)

    @property
    def raw_levered_beta(self) -> float:
        return float(self.equity_beta.value)  # type: ignore[arg-type]

    @property
    def as_of(self) -> Optional[date]:
        return self.equity_beta.as_of

    def blume(self) -> float:
        """Approved Blume shrinkage of an observed raw levered beta."""
        return round(0.67 * self.raw_levered_beta + 0.33, 4)

    def dataset_mismatches(self, other: "BetaObservation") -> list[str]:
        """동일 시점·동일 방법 데이터셋인가 (§2.3 '멀티플과 분리된 동일 시점 데이터셋').

        다른 벤치마크·관측창·빈도·계산법·기준일에서 나온 beta는 서로를 반증할 수 없다.
        """
        return [
            name
            for name, a, b in (
                ("window_start", self.window_start, other.window_start),
                ("window_end", self.window_end, other.window_end),
                ("frequency", self.frequency, other.frequency),
                ("benchmark", self.benchmark, other.benchmark),
                ("calculation_method", self.calculation_method, other.calculation_method),
                ("as_of", self.as_of, other.as_of),
            )
            if a != b
        ]

    def matches_dataset(self, other: "BetaObservation") -> bool:
        return not self.dataset_mismatches(other)


class IndustryBetaEntry(BaseModel):
    """산업 beta 테이블 항목. **FallbackConstant가 아니라 버전 고정 관측 데이터다.**

    `source.value`가 단일 진실 원천이고, 출처는 Damodaran으로 강제된다 (yfinance 위장 금지).
    테이블은 unlevered basis다.
    """

    source: Source
    table_version: str
    table_sha256: str
    industry_key: str
    mapping_version: str
    collected_at: date
    basis: Literal["unlevered"] = "unlevered"

    @field_validator("table_version", "industry_key", "mapping_version")
    @classmethod
    def non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("IndustryBetaEntry의 버전/키 필드는 필수입니다 (재현성).")
        return v

    @field_validator("table_sha256")
    @classmethod
    def sha_format(cls, v: str) -> str:
        return require_sha256(v, "IndustryBetaEntry.table_sha256")

    @model_validator(mode="after")
    def validate_entry(self):
        if self.source.source != "Damodaran":
            raise ValueError(
                f"IndustryBetaEntry.source.source='{self.source.source}' — 산업 beta 테이블의 "
                "출처는 'Damodaran'이어야 합니다. 다른 출처로 위장할 수 없습니다."
            )
        if self.source.method not in OBSERVED_METHODS:
            raise ValueError(
                f"IndustryBetaEntry.source.method='{self.source.method}'는 관측치가 아닙니다 "
                f"(허용: {sorted(OBSERVED_METHODS)}). 산업 beta는 버전 고정 '관측 데이터'이며, "
                "가정(DeclaredAssumption)을 Damodaran 출처로 포장해 소비할 수 없습니다."
            )
        v = self.source.value
        if not isinstance(v, (int, float)):
            raise ValueError(f"IndustryBetaEntry.source.value는 숫자여야 합니다: {v!r}")
        require_finite(float(v), "IndustryBetaEntry.source.value")

        if self.source.as_of is not None and self.source.as_of > self.collected_at:
            raise ValueError(
                f"IndustryBetaEntry: 데이터 기준일({self.source.as_of})이 수집일"
                f"({self.collected_at})보다 미래입니다 — 존재하지 않는 자료를 수집할 수는 없습니다."
            )
        return self

    @property
    def unlevered_beta(self) -> float:
        """단일 진실 원천은 source.value다 — 별도 필드로 중복 저장하지 않는다."""
        return float(self.source.value)  # type: ignore[arg-type]

    def freshness(self, evaluation_date: date) -> Freshness:
        """수집일도 평가일 이전이어야 한다 — 미래에 수집한 테이블은 look-ahead다."""
        if self.collected_at > evaluation_date:
            return "future"
        return _freshness(self.source.as_of, evaluation_date, INDUSTRY_BETA_MAX_AGE_DAYS)


class BetaPeerMember(BaseModel):
    """peer beta 스냅샷의 구성원. **멀티플 필드는 없다** (§2.3 순환 의존 구조적 차단).

    파생 unlevered beta는 **저장하지 않는다.** raw 관측 + 숫자형 D/E·세율 Source에서
    결정론적으로 계산한다 — 저장형 필드였다면 `unlevered_beta=99.0`을 그냥 써넣을 수 있다.
    """

    model_config = {"extra": "forbid"}

    legal_entity_id: str  # 법인 식별자 (티커 리네이밍/중복 상장으로 같은 법인을 두 번 세지 않도록)
    ticker: str
    observation: Optional[BetaObservation] = None  # 조회 실패로 제외된 후보는 None
    de_ratio_pct: Optional[Source] = None  # 언레버 입력도 관측치다
    tax_rate_pct: Optional[Source] = None
    derived_from: list[str] = []
    included: bool = True
    exclusion_reason: str = ""

    @field_validator("legal_entity_id", "ticker")
    @classmethod
    def non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("BetaPeerMember.legal_entity_id / ticker는 필수입니다.")
        return v

    @model_validator(mode="after")
    def validate_member(self):
        if not self.included:
            if not self.exclusion_reason.strip():
                raise ValueError(
                    f"BetaPeerMember[{self.ticker}]: 제외한 peer는 사유가 필요합니다 (감사)."
                )
            return self
        if self.observation is None:
            raise ValueError(
                f"BetaPeerMember[{self.ticker}]: 유효(included) peer에는 beta 관측이 필요합니다. "
                "관측이 없으면 included=False + exclusion_reason으로 남기십시오."
            )
        # 언레버 입력도 관측치다 — 가정을 Source로 위장해 넣을 수 없다.
        for name, src in (("de_ratio_pct", self.de_ratio_pct), ("tax_rate_pct", self.tax_rate_pct)):
            if src is not None and src.method not in OBSERVED_METHODS:
                raise ValueError(
                    f"BetaPeerMember[{self.ticker}].{name}.method='{src.method}'는 관측치가 아닙니다. "
                    "가정은 DeclaredAssumption으로 표현하고, peer 파생값의 입력으로 쓰지 마십시오."
                )
        return self

    @property
    def unlevered_beta(self) -> Optional[float]:
        """raw βL + D/E + 세율에서 **결정론적으로 계산**한다. 임의 입력 불가."""
        if self.observation is None:
            return None
        de = _numeric_source_value(self.de_ratio_pct, f"BetaPeerMember[{self.ticker}].de_ratio_pct")
        tax = _numeric_source_value(self.tax_rate_pct, f"BetaPeerMember[{self.ticker}].tax_rate_pct")
        if de is None or tax is None:
            return None
        return hamada_unlever(self.observation.raw_levered_beta, de, tax)


class BetaPeerSnapshot(BaseModel):
    """§2.3 순환 의존 차단 — **멀티플 선정과 분리된** 동일 시점 beta 데이터셋.

    - 멀티플 필드를 아예 두지 않는다 (`extra="forbid"`).
    - 구성원 관측은 스냅샷의 관측창·빈도·벤치마크·계산법·기준일과 **전부 일치해야** 한다.
      서로 다른 시장·관측창의 beta를 섞어 하나의 median으로 인정하지 않는다.
    - median/peer_count는 유효 구성원에서 결정론적으로 계산되는 **일반 property**다.
      computed_field로 두면 model_dump -> model_validate 왕복이 extra="forbid"와 충돌한다.
    """

    model_config = {"extra": "forbid"}

    snapshot_id: str
    snapshot_version: str
    as_of: date
    content_sha256: str
    window_start: date
    window_end: date
    frequency: BetaFrequency
    benchmark: str
    calculation_method: str
    beta_basis: BetaBasis
    members: list[BetaPeerMember] = []

    @field_validator("snapshot_id", "snapshot_version", "benchmark", "calculation_method")
    @classmethod
    def non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("BetaPeerSnapshot의 식별/벤치마크/계산법 필드는 필수입니다.")
        return v

    @field_validator("content_sha256")
    @classmethod
    def sha_format(cls, v: str) -> str:
        return require_sha256(v, "BetaPeerSnapshot.content_sha256")

    @model_validator(mode="after")
    def validate_dataset_is_homogeneous(self):
        if self.window_end <= self.window_start:
            raise ValueError("BetaPeerSnapshot 관측창이 뒤집혔습니다.")
        if self.window_end != self.as_of:
            raise ValueError(
                f"BetaPeerSnapshot: as_of({self.as_of})가 window_end({self.window_end})와 "
                "다릅니다. 스냅샷 기준일은 관측창의 끝이어야 합니다."
            )

        # 같은 법인을 복제해 N을 채울 수 없다 (peer_count는 '고유 법인 수'여야 의미가 있다).
        seen_entities: set[str] = set()
        seen_tickers: set[str] = set()
        for m in self.members:
            if not m.included:
                continue
            entity = m.legal_entity_id.strip().lower()
            ticker = m.ticker.strip().lower()
            if entity in seen_entities or ticker in seen_tickers:
                raise ValueError(
                    f"BetaPeerSnapshot: peer가 중복됩니다 (legal_entity_id={m.legal_entity_id!r}, "
                    f"ticker={m.ticker!r}). 같은 법인을 여러 번 세어 최소 peer 수를 채울 수 없습니다."
                )
            seen_entities.add(entity)
            seen_tickers.add(ticker)

        for m in self.members:
            if not m.included or m.observation is None:
                continue
            obs = m.observation
            mismatched = [
                name
                for name, a, b in (
                    ("window_start", obs.window_start, self.window_start),
                    ("window_end", obs.window_end, self.window_end),
                    ("frequency", obs.frequency, self.frequency),
                    ("benchmark", obs.benchmark, self.benchmark),
                    ("calculation_method", obs.calculation_method, self.calculation_method),
                    ("as_of", obs.as_of, self.as_of),
                )
                if a != b
            ]
            if mismatched:
                raise ValueError(
                    f"BetaPeerSnapshot[{m.ticker}]: 스냅샷과 {mismatched}가 다릅니다. "
                    "서로 다른 시장·관측창의 beta를 하나의 median으로 섞을 수 없습니다 (§2.3 동일 시점 데이터셋)."
                )
            if self.beta_basis == "unlevered":
                if m.de_ratio_pct is None or m.tax_rate_pct is None:
                    raise ValueError(
                        f"BetaPeerSnapshot[{m.ticker}]: unlevered basis의 유효 peer에는 "
                        "D/E·세율 Source가 **둘 다** 필요합니다 (파생 unlevered beta의 입력)."
                    )
                for name, src in (
                    ("de_ratio_pct", m.de_ratio_pct),
                    ("tax_rate_pct", m.tax_rate_pct),
                ):
                    if src.as_of != self.as_of:
                        raise ValueError(
                            f"BetaPeerSnapshot[{m.ticker}].{name}.as_of({src.as_of})가 스냅샷 "
                            f"기준일({self.as_of})과 다릅니다 — 동일 시점 데이터셋이 아닙니다."
                        )
                if m.unlevered_beta is None:
                    raise ValueError(
                        f"BetaPeerSnapshot[{m.ticker}]: D/E·세율이 경제적 정의역 밖이라 파생 "
                        "unlevered beta를 계산할 수 없습니다. included=False + 사유로 남기십시오."
                    )
        return self

    def _member_beta(self, m: BetaPeerMember) -> Optional[float]:
        if self.beta_basis == "unlevered":
            return m.unlevered_beta
        return m.observation.raw_levered_beta if m.observation else None

    @property
    def valid_betas(self) -> list[float]:
        out = []
        for m in self.members:
            if not m.included:
                continue
            b = self._member_beta(m)
            if b is not None and math.isfinite(b):
                out.append(float(b))
        return sorted(out)  # 정렬 = 결정론

    @property
    def peer_count(self) -> int:
        return len(self.valid_betas)

    @property
    def median_beta(self) -> Optional[float]:
        betas = self.valid_betas
        if not betas:
            return None
        return float(statistics.median(betas))

    def freshness(self, evaluation_date: date) -> Freshness:
        """시장 데이터이므로 허용 시차가 짧다 (§2.5: 7일). 미래 기준일은 look-ahead."""
        return _freshness(self.as_of, evaluation_date, BETA_PEER_SNAPSHOT_MAX_AGE_DAYS)


# ── 순차입금 taxonomy (PLAN §2.1) ──

_CASH_FIELDS = ("cash", "marketable_debt_securities", "short_term_investments")

# 대조 허용오차 (display unit). 반올림 노이즈만 흡수한다 — 정의 오류는 흡수하지 않는다.
#
# 유도 (CODEX 재작업 판정 2 반영. 실제 태그 구조 기준):
#   Path A 현금성   : cash + (시장성 채무증권 | 단기투자)        -> 최대 2회 반올림
#   Path A 차입     : 개별 차입 태그 5종의 합                    -> 최대 5회
#   Path B 독립 합계: 결합 차입 태그 + 결합 현금 태그            -> 최대 2회
#   합 9회 x 0.5단위 = 4.5 -> 보수적으로 **5단위**.
# (P0-0의 엄격 등호는 원장부(raw)에서 정의가 일치해도 단위 반올림만으로 False를 내서
#  게이트가 전 종목을 오차단한다 — 그건 대조가 아니라 잡음이다.)
# 5단위 = NVDA 순현금 $41,865M의 0.012%. 이보다 큰 차이는 반올림으로 설명되지 않는다.
NET_DEBT_RECONCILE_TOLERANCE = 5


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
    def reconciliation_delta(self) -> Optional[int]:
        """독립 합계 − 구성요소 정의값. None이면 대조 불가. 감사용 — 차이를 숨기지 않는다."""
        expected = self.expected_net_debt()
        if expected is None or self.net_debt is None:
            return None
        return self.net_debt - expected

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reconciled(self) -> Optional[bool]:
        """3-state. Computed, never stored — so it cannot be round-tripped into a lie.

        허용오차는 단위 반올림 노이즈 폭(NET_DEBT_RECONCILE_TOLERANCE = 5단위)뿐이다.
        그보다 큰 차이는 반올림으로 설명되지 않는다 = 정의 오류이므로 False다.
        """
        delta = self.reconciliation_delta
        if delta is None:
            return None
        return abs(delta) <= NET_DEBT_RECONCILE_TOLERANCE
