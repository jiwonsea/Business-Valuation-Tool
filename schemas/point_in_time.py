"""Point-in-time contract for reported financial values (§7.2-4 / §7.2-5).

Gate contract (HANDOFF_CODEX_c_gate_research_2026-07-18 §7.2, no relaxation):

- Original filing values and later restated comparatives are stored SEPARATELY.
  Point-in-time computation consumes ONLY basis="original" — the value that was
  actually available at the filing's receipt date. Restated comparatives are an
  audit record; they never overwrite or substitute for the original.
- available_at = DART receipt date (first 8 digits of rcept_no). Only material
  with available_at <= evaluation_date may be used; anything later is
  look-ahead.
- No current-snapshot backfill, no interpolation of missing values: a missing
  observation stays missing (excluded), it is never imputed.
- First-scope multiples are LTM P/B and P/S only. "12M Forward" (or any
  forward-estimate label) is forbidden in this scope.

This module MUST NOT import schemas.models (one-way dependency, same rule as
schemas.provenance).
"""

from __future__ import annotations

import re
from datetime import date
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, field_validator, model_validator

# ── Multiple scope (§7.2-5) ──

# First-scope observable multiples: trailing (LTM) book / sales only.
ALLOWED_LTM_MULTIPLES: tuple[str, ...] = ("P/B", "P/S")

# Any label matching this is a forward estimate and is forbidden in this scope.
_FORWARD_LABEL_RE = re.compile(
    r"forward|fwd|estimate|(?:^|[^A-Za-z0-9])E(?:$|[^A-Za-z0-9])", re.IGNORECASE
)


def require_allowed_multiple_label(label: str) -> str:
    """Reject forward-looking multiple labels ('12M Forward' 금지, §7.2-5).

    Fail-closed: only the explicit LTM P/B·P/S labels pass. This is a contract
    guard, not a parser — call it wherever a multiple label enters the
    point-in-time path.
    """
    stripped = label.strip()
    if _FORWARD_LABEL_RE.search(stripped):
        raise ValueError(
            f"multiple label {label!r}: forward-looking labels are forbidden in "
            "the point-in-time scope (§7.2-5 — LTM P/B·P/S only)."
        )
    if stripped not in ALLOWED_LTM_MULTIPLES:
        raise ValueError(
            f"multiple label {label!r}: first scope allows only "
            f"{ALLOWED_LTM_MULTIPLES} (LTM). (§7.2-5)"
        )
    return stripped


# ── available_at (§7.2-5) ──

_RCEPT_NO_RE = re.compile(r"^\d{14}$")


def available_at_from_rcept_no(rcept_no: str) -> date:
    """DART rcept_no -> receipt date (= available_at).

    The first 8 digits of a 14-digit rcept_no are YYYYMMDD. Fail-closed: a
    malformed rcept_no raises instead of yielding a fabricated date.
    """
    cleaned = rcept_no.strip()
    if not _RCEPT_NO_RE.match(cleaned):
        raise ValueError(
            f"rcept_no {rcept_no!r}: expected 14 digits (YYYYMMDD + serial); "
            "cannot derive available_at from a malformed receipt number."
        )
    return date(int(cleaned[0:4]), int(cleaned[4:6]), int(cleaned[6:8]))


# ── Reported value with basis separation (§7.2-4) ──

Basis = Literal["original", "restated_comparative"]

# Statement codes fnlttSinglAcntAll uses (SCE listed for completeness — the
# parser's STATEMENT_CONTRACT never selects from it).
StatementCode = Literal["BS", "IS", "CIS", "CF", "SCE"]


class ReportedFinancialValue(BaseModel):
    """One reported number with filing provenance and basis separation.

    basis="original": thstrm value of the FY report — available at
    `available_at`, the only basis point-in-time computation may consume.
    basis="restated_comparative": a later report's comparative for a prior
    year — audit record, never a point-in-time input.

    Frozen: a reported value is an observation; mutate via model_copy only
    (project Pydantic rule).
    """

    model_config = {"frozen": True, "extra": "forbid"}

    account: str  # internal key (revenue / op / ... / capex)
    fiscal_year: int
    value_mkrw: int
    basis: Basis
    statement: StatementCode
    account_nm: str  # DART spelling actually matched (alias registry audit)
    rcept_no: str
    available_at: date

    @field_validator("account", "account_nm")
    @classmethod
    def non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "ReportedFinancialValue: account / account_nm는 필수입니다."
            )
        return v

    @model_validator(mode="after")
    def available_at_matches_rcept_no(self):
        derived = available_at_from_rcept_no(self.rcept_no)
        if self.available_at != derived:
            raise ValueError(
                f"ReportedFinancialValue: available_at({self.available_at})가 "
                f"rcept_no 접수일({derived})과 다릅니다 — available_at은 접수일 "
                "그 자체여야 합니다 (§7.2-5, 소급/위장 금지)."
            )
        return self


def select_point_in_time(
    values: list[ReportedFinancialValue],
    account: str,
    fiscal_year: int,
    evaluation_date: date,
) -> Optional[ReportedFinancialValue]:
    """The value for (account, FY) as it was knowable at evaluation_date.

    Rules (§7.2-5, fail-closed):
      - basis="original" only — restated comparatives are never consumed;
      - available_at <= evaluation_date only — later filings are look-ahead;
      - nothing qualifies -> None. The caller must treat it as missing
        (관측 제외); interpolation/backfill is forbidden.

    If multiple qualifying originals exist (e.g. a re-filed annual report), the
    EARLIEST available_at wins: point-in-time uses the first disclosure.
    """
    qualifying = [
        v
        for v in values
        if v.account == account
        and v.fiscal_year == fiscal_year
        and v.basis == "original"
        and v.available_at <= evaluation_date
    ]
    if not qualifying:
        return None
    return min(qualifying, key=lambda v: (v.available_at, v.rcept_no))


# ── Phase 2: multi-year observations + historical band ──
# Contract: HANDOFF_CODEX_phase2_impl_scope_2026-07-18 §7/§7.1 (no relaxation).
# These models are observations for a REPORTING-ONLY band. They must never
# become valuation inputs (engine wiring of P1/P2 was REJECTED in the Phase 1
# debate); engine/multiple_band.py enforces the same rule on the compute side.

# Maximum backward search window for a filing-date price (§7-4): the price used
# for t must satisfy  t - PRICE_SEARCH_WINDOW_DAYS <= price_date <= t.
PRICE_SEARCH_WINDOW_DAYS: int = 7


class PriceExclusionReason(str, Enum):
    """Mechanical (testable) reasons a fiscal year is excluded from the band.

    Subjective "corporate action 복원 불확실" judgments are forbidden (§7-4);
    every exclusion must cite one of these machine-checkable conditions.
    """

    # No raw close available in [t-7d, t] (post-t prices are look-ahead).
    NO_PRICE_WITHIN_WINDOW = "no_price_within_window"
    # A split/corporate action falls between price_date and t, so the raw
    # close and the share count are on different bases.
    SPLIT_ADJUSTMENT_DETECTED = "split_adjustment_detected"
    # No share-count record for the fiscal year (발행-자기 미확보).
    SHARES_BASIS_MISSING = "shares_basis_missing"
    # Share basis cannot be tied to the price basis mechanically (e.g. the
    # price source cannot report corporate actions for the window at all).
    SHARES_BASIS_MISMATCH = "shares_basis_mismatch"


# Fixed note strings for non-price exclusions (mechanical, grep-able).
EXCLUSION_NOTE_DENOMINATOR_NON_POSITIVE = "denominator_non_positive"


class ExcludedYear(BaseModel):
    """One fiscal year excluded from the band, with its mechanical reason.

    Exactly the audit trail §7-4 requires: either a PriceExclusionReason, or
    the account keys that had no qualifying point-in-time value
    (select_point_in_time -> None; missing stays missing, no interpolation),
    or a fixed mechanical note string.
    """

    model_config = {"frozen": True, "extra": "forbid"}

    fiscal_year: int
    price_reason: Optional[PriceExclusionReason] = None
    missing_accounts: tuple[str, ...] = ()
    note: str = ""

    @model_validator(mode="after")
    def some_reason_required(self):
        if self.price_reason is None and not self.missing_accounts and not self.note:
            raise ValueError(
                "ExcludedYear: 제외에는 기계적 사유가 필수입니다 — price_reason, "
                "missing_accounts, note 중 하나 이상 (§7-4, 주관 판단 금지)."
            )
        return self


class MultipleObservation(BaseModel):
    """One point-in-time LTM multiple observation (annual filing date basis).

    t = the annual report's DART receipt date (available_at): the first day
    the FY financials were public. price = raw close (auto_adjust=False) on
    the latest trading day <= t within PRICE_SEARCH_WINDOW_DAYS. shares =
    발행보통주 - 자기보통주 from the same filing. denominator = the
    basis="original" FY value chosen by select_point_in_time at t.
    """

    model_config = {"frozen": True, "extra": "forbid"}

    label: str  # validated: LTM P/B·P/S only (§7.2-5)
    company: str
    fiscal_year: int
    t: date  # evaluation date = filing receipt date
    price_date: date  # trading day actually used, <= t
    price_close_raw_krw: float
    shares_outstanding: int  # 발행보통주 - 자기보통주 (당시 보고서)
    market_cap_mkrw: float
    denominator_mkrw: int  # equity (P/B) / revenue (P/S), original basis
    multiple: float
    rcept_no: str

    @field_validator("label")
    @classmethod
    def label_in_scope(cls, v: str) -> str:
        return require_allowed_multiple_label(v)

    @model_validator(mode="after")
    def price_within_window(self):
        if self.price_date > self.t:
            raise ValueError(
                f"MultipleObservation FY{self.fiscal_year}: price_date"
                f"({self.price_date}) > t({self.t}) — 접수일 이후 가격은 "
                "look-ahead입니다 (§7-4)."
            )
        if (self.t - self.price_date).days > PRICE_SEARCH_WINDOW_DAYS:
            raise ValueError(
                f"MultipleObservation FY{self.fiscal_year}: price_date"
                f"({self.price_date})가 t({self.t})로부터 "
                f"{PRICE_SEARCH_WINDOW_DAYS} calendar days를 초과합니다 — "
                "관측 제외 대상입니다 (§7-4)."
            )
        if self.shares_outstanding <= 0:
            raise ValueError(
                f"MultipleObservation FY{self.fiscal_year}: "
                "shares_outstanding <= 0 — shares_basis_missing으로 제외해야 "
                "합니다."
            )
        if self.denominator_mkrw <= 0:
            raise ValueError(
                f"MultipleObservation FY{self.fiscal_year}: 분모 <= 0 — "
                f"'{EXCLUSION_NOTE_DENOMINATOR_NON_POSITIVE}'로 제외해야 합니다."
            )
        return self


class HistoricalBand(BaseModel):
    """Reporting-only percentile band over point-in-time multiple observations.

    NOT a valuation input: run_valuation/method selection must never consume
    this model (Phase 1 debate — engine wiring REJECTED). Statistics are
    None when n_obs == 0; renderers must show "이력 부족(N=x)" for small n
    instead of fabricating a band.
    """

    model_config = {"frozen": True, "extra": "forbid"}

    label: str  # validated: LTM P/B·P/S only
    company: str
    n_obs: int
    band_min: Optional[float] = None
    p25: Optional[float] = None
    median: Optional[float] = None
    p75: Optional[float] = None
    band_max: Optional[float] = None
    observations: tuple[MultipleObservation, ...] = ()
    excluded: tuple[ExcludedYear, ...] = ()

    @field_validator("label")
    @classmethod
    def label_in_scope(cls, v: str) -> str:
        return require_allowed_multiple_label(v)

    @model_validator(mode="after")
    def stats_match_observations(self):
        if self.n_obs != len(self.observations):
            raise ValueError(
                f"HistoricalBand: n_obs({self.n_obs}) != 관측 수"
                f"({len(self.observations)})."
            )
        stats = (self.band_min, self.p25, self.median, self.p75, self.band_max)
        if self.n_obs == 0 and any(s is not None for s in stats):
            raise ValueError(
                "HistoricalBand: n_obs=0인데 통계가 존재합니다 — 관측 없는 "
                "밴드 날조 금지."
            )
        if self.n_obs > 0 and any(s is None for s in stats):
            raise ValueError("HistoricalBand: n_obs>0이면 5개 통계가 전부 필요합니다.")
        return self
