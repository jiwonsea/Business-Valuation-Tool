"""P0-2a 베타 정상화 계약 (PLAN_deep_research.md §2.3 / §2.5).

CODEX 판정 (P0-2 설계 + 재작업):
  Q1. R10 재기준 없음 — 차단 시 진단 계산은 legacy로 계속하되 publish는 막는다.
      단 `normalized_value`는 성공 시에만 존재하고, 진단값은 `value_for("diagnostic")`으로
      **명시적으로** 골라야 한다 (차단 결과의 우회 소비 차단).
  Q2. 임시 peer 데이터셋 금지 — 계약(P0-2a) 먼저, 소비 배선은 P0-4 이후(P0-2b).
  Q3. 산업 beta = 버전 고정 관측 데이터. 400일 초과 stale, 미래 기준일은 차단.
  Q4. Source 확장 금지 -> BetaObservation. 관측창/빈도를 모르는 값(yfinance info["beta"])은
      §2.3 관측치가 아니다.
  + basis 분리(unlevered/equity), 같은 basis끼리 교차검증, NaN/Inf·Hamada 분모 차단,
    evaluation_date 필수(engine 순수성), peer 최소 4명(§2.5).

이 파일이 지키는 회귀: 자동 클램프·상수 대체의 부활, NaN/Inf 소비, basis 혼합 비교,
미래 기준일 테이블 소비, 차단 결과의 우회 소비.
"""

import math
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from engine.normalize import (
    BetaResolution,
    hamada_denominator,
    resolve_beta,
    unlever_beta,
    valid_capital_structure,
)
from schemas.provenance import (
    BETA_MIN_PEER_COUNT,
    BETA_OBSERVATION_MAX_AGE_DAYS,
    BETA_PEER_SNAPSHOT_MAX_AGE_DAYS,
    BETA_PLAUSIBLE_RANGE,
    BETA_REFERENCE_CONFLICT_MULTIPLE,
    INDUSTRY_BETA_MAX_AGE_DAYS,
    BetaObservation,
    BetaPeerMember,
    BetaPeerSnapshot,
    IndustryBetaEntry,
    Source,
)

TODAY = date(2026, 7, 13)


SNAP_AS_OF = date(2026, 7, 10)  # 평가일(2026-07-13) - 3일 -> 허용 시차(7일) 이내
WINDOW_START = date(2024, 7, 12)
BENCHMARK = "KOSPI"
METHOD = "OLS on weekly log returns"


def beta_obs(value: float = 1.20, as_of: date = SNAP_AS_OF, **over) -> BetaObservation:
    """관측 기준일 == 관측창의 끝 (계약). as_of를 옮기면 window_end도 같이 옮긴다."""
    kw = dict(
        equity_beta=Source(
            value=value,
            source="yfinance",
            url="https://finance.yahoo.com/quote/X",
            as_of=as_of,
            method="derived",
            derived_from=["yfinance:X:adj_close"],
        ),
        window_start=WINDOW_START,
        window_end=as_of,
        frequency="weekly",
        benchmark=BENCHMARK,
        observation_count=104,
        calculation_method=METHOD,
    )
    kw.update(over)
    return BetaObservation(**kw)


def num_source(v: float, name: str, as_of: date = SNAP_AS_OF) -> Source:
    return Source(
        value=v,
        source="yfinance",
        url=f"https://x/{name}",
        as_of=as_of,
        method="derived",
        derived_from=[name],
    )


def peer_member(
    ticker: str,
    levered: float,
    de: float = 30.0,
    tax: float = 25.0,
    as_of: date = SNAP_AS_OF,
    **over,
) -> BetaPeerMember:
    kw = dict(
        legal_entity_id=f"LEI-{ticker}",
        ticker=ticker,
        observation=beta_obs(levered, as_of=as_of),
        de_ratio_pct=num_source(de, f"{ticker}:de", as_of),
        tax_rate_pct=num_source(tax, f"{ticker}:tax", as_of),
        derived_from=[f"{ticker}:beta", f"{ticker}:de", f"{ticker}:tax"],
    )
    kw.update(over)
    return BetaPeerMember(**kw)


def peer_snapshot(
    unlevered_targets: list[float],
    basis: str = "unlevered",
    as_of: date = SNAP_AS_OF,
    **over,
) -> BetaPeerSnapshot:
    """원하는 파생 unlevered(또는 equity) beta가 나오도록 관측 βL을 역산해 구성한다.

    파생값은 저장하지 않는다 — raw βL + D/E + 세율에서 결정론적으로 계산된다.
    """
    de, tax = 30.0, 25.0
    factor = 1 + (1 - tax / 100) * de / 100  # 1.225
    members = [
        peer_member(
            f"PEER{i}",
            levered=(b if basis == "equity" else b * factor),
            de=de,
            tax=tax,
            as_of=as_of,
        )
        for i, b in enumerate(unlevered_targets)
    ]
    kw = dict(
        snapshot_id="beta-peers-sk-ecoplant",
        snapshot_version="v1",
        as_of=as_of,
        content_sha256="ab12" + "0" * 60,
        window_start=WINDOW_START,
        window_end=as_of,
        frequency="weekly",
        benchmark=BENCHMARK,
        calculation_method=METHOD,
        beta_basis=basis,
        members=members,
    )
    kw.update(over)
    return BetaPeerSnapshot(**kw)


def industry_entry(unlevered: float = 1.05, as_of: date = date(2026, 1, 5), **over) -> IndustryBetaEntry:
    kw = dict(
        source=Source(
            value=unlevered,
            source="Damodaran",
            url="https://pages.stern.nyu.edu/~adamodar/betas.html",
            as_of=as_of,
            method="observed",
        ),
        table_version="damodaran-2026-01",
        table_sha256="9f2b" + "0" * 60,
        industry_key="Engineering/Construction",
        mapping_version="kr-industry-map-v1",
        collected_at=date(2026, 1, 20),
    )
    kw.update(over)
    return IndustryBetaEntry(**kw)


# ── 유효하지 않은 숫자 (CODEX 블로커 1) ──


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_beta_cannot_even_be_observed(bad):
    """NaN/Inf beta는 BetaObservation 생성 단계에서 죽는다."""
    with pytest.raises(ValidationError):
        beta_obs(bad)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_capital_structure_is_blocked_not_consumed(bad):
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        observation=beta_obs(1.2),
        de_ratio_pct=bad,
        tax_rate_pct=25.0,
        legacy_unlevered_beta=0.75,
    )
    assert res.status == "blocked_invalid_number"
    assert res.publishable is False
    assert res.normalized_value is None


def test_zero_hamada_denominator_is_blocked_not_a_zero_division():
    """D/E = -100%, tax = 0% -> 분모 0. 예외가 아니라 판정으로 나와야 한다."""
    assert hamada_denominator(-100.0, 0.0) == 0
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        observation=beta_obs(1.2),
        de_ratio_pct=-100.0,
        tax_rate_pct=0.0,
        legacy_unlevered_beta=0.75,
    )
    assert res.status == "blocked_invalid_capital_structure"
    assert res.normalized_value is None


@pytest.mark.parametrize(
    "de,tax",
    [
        (-30.0, 25.0),  # D/E는 gross debt 기반 -> 음수 불가
        (30.0, -5.0),  # 세율 정의역 [0, 100] 밖
        (30.0, 120.0),
    ],
)
def test_capital_structure_outside_its_domain_is_blocked_not_clamped(de, tax):
    assert valid_capital_structure(de, tax) is False
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        observation=beta_obs(1.2),
        de_ratio_pct=de,
        tax_rate_pct=tax,
        legacy_unlevered_beta=0.75,
    )
    assert res.status == "blocked_invalid_capital_structure"
    assert res.normalized_value is None  # 클램프해서 통과시키지 않는다


def test_unlever_refuses_non_finite_and_non_positive_denominator():
    with pytest.raises(ValueError):
        unlever_beta(float("nan"), 50.0, 25.0)
    with pytest.raises(ValueError):
        unlever_beta(1.2, -200.0, 0.0)  # 분모 = -1


def test_non_finite_peer_beta_never_enters_the_median():
    snap = peer_snapshot([0.8, 0.9, 1.0, 1.1])
    poisoned = snap.model_copy(
        update={
            "members": snap.members
            + [
                BetaPeerMember.model_construct(
                    legal_entity_id="LEI-NAN",
                    ticker="NAN", observation=beta_obs(1.0), unlevered_beta=float("nan")
                )
            ]
        }
    )
    assert poisoned.peer_count == 4  # NaN 구성원은 유효 집합에서 빠진다
    assert math.isfinite(poisoned.median_beta)


# ── BetaObservation / 관측치 자격 (Q4) ──


def test_yfinance_info_beta_cannot_be_expressed_as_an_observation():
    with pytest.raises(ValidationError):
        BetaObservation(  # type: ignore[call-arg]
            equity_beta=Source(value=1.66, source="yfinance", url="https://x", as_of=TODAY)
        )


@pytest.mark.parametrize("blank", ["", "   "])
def test_benchmark_and_method_must_be_named(blank):
    with pytest.raises(ValidationError):
        beta_obs(benchmark=blank)
    with pytest.raises(ValidationError):
        beta_obs(calculation_method=blank)


def test_window_must_be_ordered():
    with pytest.raises(ValidationError):
        beta_obs(window_start=date(2026, 7, 10), window_end=date(2024, 7, 12))


def test_declared_assumption_cannot_masquerade_as_a_beta_observation():
    with pytest.raises(ValidationError):
        beta_obs(
            equity_beta=Source(value=1.2, source="yfinance", method="declared_assumption")
        )


def test_blume_is_carried_for_cross_check_not_for_consumption():
    obs = beta_obs(1.50)
    assert obs.blume() == pytest.approx(0.67 * 1.50 + 0.33)

    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        observation=obs,
        de_ratio_pct=0.0,
        tax_rate_pct=25.0,
    )
    assert res.normalized_value == pytest.approx(1.50)  # 소비된 건 raw (Blume이 아니다)
    assert res.blume_adjusted == pytest.approx(1.335)


# ── 상장사 · unlevered basis ──


def test_listed_consumes_verified_raw_beta_via_hamada():
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        observation=beta_obs(1.20),
        de_ratio_pct=50.0,
        tax_rate_pct=25.0,
    )
    assert res.status == "consumed_raw"
    assert res.publishable is True
    assert res.normalized_value == pytest.approx(1.20 / (1 + 0.75 * 0.5))
    assert res.unlevered_from_raw == pytest.approx(res.normalized_value)


def test_listed_without_provenance_is_blocked_and_never_substituted():
    """default_bu 상수 대체 금지. 차단 결과에는 소비 가능한 값이 아예 없다."""
    res = resolve_beta(
        evaluation_date=TODAY, is_listed=True, observation=None, legacy_unlevered_beta=0.75
    )
    assert res.status == "blocked_no_provenance"
    assert res.publishable is False
    assert res.normalized_value is None
    assert res.diagnostic_value == 0.75


def test_listed_without_capital_structure_is_blocked():
    res = resolve_beta(
        evaluation_date=TODAY, is_listed=True, observation=beta_obs(), de_ratio_pct=None
    )
    assert res.status == "blocked_no_capital_structure"
    assert res.normalized_value is None


# ── 교차검증은 같은 basis끼리 (CODEX 블로커 3) ──


def test_conflict_is_judged_on_unlevered_basis_not_levered_vs_unlevered():
    """레버리지 높은 회사: raw βL(1.60)만 보면 충돌처럼 보이지만 언레버하면 정상(0.94)이다."""
    snap = peer_snapshot([0.85, 0.90, 0.95, 1.00])  # median 0.925
    assert snap.median_beta == pytest.approx(0.925)

    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        observation=beta_obs(1.60),  # 1.60 > 0.925 × 1.5 = 1.3875 (levered 기준이면 충돌)
        de_ratio_pct=100.0,
        tax_rate_pct=25.0,
        peer_snapshot=snap,
    )
    assert res.status == "consumed_raw"  # 언레버 1.60/1.75 = 0.914 < 1.3875 -> 정상
    assert res.normalized_value == pytest.approx(1.60 / 1.75)


def test_genuine_conflict_on_the_same_basis_is_blocked():
    snap = peer_snapshot([0.85, 0.90, 0.95, 1.00])  # median 0.925 -> 임계 1.3875
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        observation=beta_obs(1.60),
        de_ratio_pct=0.0,  # 무차입 -> 언레버 = 1.60 > 1.3875
        tax_rate_pct=25.0,
        peer_snapshot=snap,
        legacy_unlevered_beta=0.9,
    )
    assert res.status == "blocked_reference_conflict"
    assert res.normalized_value is None
    assert res.diagnostic_value == 0.9


def test_conflict_check_needs_enough_peers_to_be_credible():
    """peer가 §2.5 최소 수(4)에 못 미치면 그 median으로 raw beta를 반증할 수 없다."""
    snap = peer_snapshot([0.5, 0.5, 0.5])  # 3명
    assert snap.peer_count == BETA_MIN_PEER_COUNT - 1
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        observation=beta_obs(2.00),
        de_ratio_pct=0.0,
        tax_rate_pct=25.0,
        peer_snapshot=snap,
    )
    assert res.status == "consumed_raw"


def test_basis_mismatch_between_target_and_peer_snapshot_is_blocked():
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        target_basis="unlevered",
        observation=beta_obs(1.2),
        de_ratio_pct=30.0,
        tax_rate_pct=25.0,
        peer_snapshot=peer_snapshot([0.9, 1.0, 1.1, 1.2], basis="equity"),
    )
    assert res.status == "blocked_basis_mismatch"
    assert res.normalized_value is None


# ── 금융업: equity basis (CODEX 판정 2) ──


def test_financial_listed_consumes_equity_beta_without_unlevering():
    """wacc.py는 is_financial이면 bu를 βL로 직접 쓴다 — 언레버하면 이중 조정이 된다."""
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        target_basis="equity",
        observation=beta_obs(1.10),
        # D/E·세율을 주지 않아도 된다 — equity basis는 언레버하지 않는다
    )
    assert res.status == "consumed_raw_equity"
    assert res.basis == "equity"
    assert res.normalized_value == pytest.approx(1.10)


def test_financial_conflict_is_judged_against_equity_basis_peers():
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        target_basis="equity",
        observation=beta_obs(2.00),
        peer_snapshot=peer_snapshot([0.9, 1.0, 1.1, 1.2], basis="equity"),  # median 1.05
    )
    assert res.status == "blocked_reference_conflict"  # 2.00 > 1.05 x 1.5


def test_industry_table_cannot_substitute_for_an_equity_basis_target():
    """산업 테이블은 unlevered basis다 — 금융업 equity beta 대체로 쓸 수 없다."""
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=False,
        target_basis="equity",
        industry_entry=industry_entry(1.05),
        legacy_unlevered_beta=0.8,
    )
    assert res.status == "blocked_no_reference"
    assert res.normalized_value is None


# ── 비상장사 ──


def test_unlisted_prefers_peer_median_over_the_industry_table():
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=False,
        peer_snapshot=peer_snapshot([0.78, 0.80, 0.84, 0.90]),  # median 0.82
        industry_entry=industry_entry(1.05),
    )
    assert res.status == "consumed_peer_median"
    assert res.normalized_value == pytest.approx(0.82)


def test_unlisted_falls_back_to_the_versioned_industry_table():
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=False,
        peer_snapshot=peer_snapshot([0.8, 0.9]),  # peer 부족 (2 < 4)
        industry_entry=industry_entry(1.05),
    )
    assert res.status == "consumed_industry_table"
    assert res.normalized_value == 1.05
    assert any("산업 테이블" in w for w in res.warnings)


def test_stale_industry_table_is_not_consumed():
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=False,
        industry_entry=industry_entry(
            as_of=TODAY - timedelta(days=INDUSTRY_BETA_MAX_AGE_DAYS + 1)
        ),
        legacy_unlevered_beta=0.75,
    )
    assert res.status == "blocked_stale_industry_table"
    assert res.normalized_value is None


def test_industry_table_at_the_age_limit_is_still_fresh():
    entry = industry_entry(as_of=TODAY - timedelta(days=INDUSTRY_BETA_MAX_AGE_DAYS))
    assert entry.freshness(TODAY) == "fresh"


def test_future_dated_industry_table_is_blocked():
    """평가일보다 미래 기준일 = look-ahead. fresh로 통과시키면 안 된다 (CODEX 블로커 6)."""
    entry = industry_entry(as_of=date(2027, 1, 1), collected_at=date(2027, 1, 20))
    assert entry.freshness(TODAY) == "future"

    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=False,
        industry_entry=entry,
        legacy_unlevered_beta=0.75,
    )
    assert res.status == "blocked_invalid_industry_table"
    assert res.normalized_value is None


def test_industry_table_without_a_reference_date_is_unusable():
    forged = Source.model_construct(
        value=1.05, source="Damodaran", url="https://x", as_of=None, method="observed"
    )
    entry = industry_entry().model_copy(update={"source": forged})
    assert entry.freshness(TODAY) == "unknown_as_of"

    res = resolve_beta(evaluation_date=TODAY, is_listed=False, industry_entry=entry)
    assert res.status == "blocked_invalid_industry_table"


def test_unlisted_with_no_peers_and_no_table_is_blocked_not_defaulted():
    """SK에코플랜트의 현재 상태 — 상수 0.75로 채우지 않는다."""
    res = resolve_beta(evaluation_date=TODAY, is_listed=False, legacy_unlevered_beta=0.75)
    assert res.status == "blocked_no_reference"
    assert res.normalized_value is None
    assert res.diagnostic_value == 0.75


# ── 산업 테이블 계약 (CODEX 블로커 5) ──


def test_industry_table_value_has_a_single_source_of_truth():
    entry = industry_entry(1.05)
    assert entry.unlevered_beta == 1.05  # source.value에서만 나온다
    assert entry.source.source == "Damodaran"

    with pytest.raises(ValidationError):
        industry_entry(
            source=Source(value="1.05", source="Damodaran", url="https://x", as_of=TODAY)
        )


def test_damodaran_is_a_first_class_source_kind():
    src = Source(value=1.0, source="Damodaran", url="https://x", as_of=TODAY)
    assert src.source == "Damodaran"


# ── peer 스냅샷 계약 (CODEX 판정 3) ──


def test_peer_snapshot_median_is_deterministic_and_derived_not_stored():
    snap = peer_snapshot([1.1, 0.8, 0.9, 1.0])  # 입력 순서 무관
    assert snap.valid_betas == pytest.approx([0.8, 0.9, 1.0, 1.1])
    assert snap.median_beta == pytest.approx(0.95)
    assert snap.peer_count == 4


def test_excluded_peers_need_a_reason_and_leave_the_median():
    with pytest.raises(ValidationError):
        BetaPeerMember(legal_entity_id="LEI-X", ticker="X", observation=beta_obs(), included=False)

    snap = peer_snapshot([0.8, 0.9, 1.0, 1.1])
    excluded = snap.model_copy(
        update={
            "members": [
                snap.members[0].model_copy(
                    update={"included": False, "exclusion_reason": "관측창 불일치"}
                )
            ]
            + snap.members[1:]
        }
    )
    assert excluded.peer_count == 3
    assert excluded.median_beta == pytest.approx(1.0)


def test_peer_snapshot_cannot_carry_multiples():
    """멀티플 필드를 못 넣게 해야 §2.3 순환 의존이 구조적으로 차단된다."""
    with pytest.raises(ValidationError):
        peer_snapshot([0.9, 1.0, 1.1, 1.2], ev_ebitda=10.0)


# ── 자동 클램프 금지 (§2.3) ──


def test_out_of_range_beta_is_warned_and_flagged_never_clamped():
    lo, hi = BETA_PLAUSIBLE_RANGE
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=False,
        peer_snapshot=peer_snapshot([hi + 0.4, hi + 0.5, hi + 0.5, hi + 0.6]),
    )
    assert res.status == "consumed_peer_median"
    assert res.normalized_value == pytest.approx(hi + 0.5)  # 깎이지 않았다
    assert res.sensitivity_required is True
    assert res.publishable is True  # 범위 이탈은 차단 사유가 아니다
    assert any("민감도" in w for w in res.warnings)
    assert lo == 0.3


def test_unlever_does_not_clamp_the_result():
    """max(bu, 0.1) 부활 방지."""
    bu = unlever_beta(0.05, 400.0, 25.0)
    assert bu == pytest.approx(0.05 / (1 + 0.75 * 4.0))
    assert bu < 0.1


def test_unlever_does_not_cap_de_ratio():
    """engine/wacc.py의 리레버 D/E 200% cap은 별도 정책 — 언레버는 관측 D/E를 그대로 쓴다."""
    assert unlever_beta(1.5, 400.0, 25.0) != unlever_beta(1.5, 200.0, 25.0)


# ── 판정 결과의 계약 (CODEX 판정 1) ──


@pytest.mark.parametrize(
    "res",
    [
        resolve_beta(
            evaluation_date=TODAY,
            is_listed=True,
            observation=None,
            legacy_unlevered_beta=0.7,
        ),
        resolve_beta(evaluation_date=TODAY, is_listed=False, legacy_unlevered_beta=0.7),
    ],
)
def test_blocked_resolutions_expose_no_publishable_value(res: BetaResolution):
    assert res.blocked is True
    assert res.publishable is False
    assert res.normalized_value is None
    assert res.value_for("publish") is None  # publish 경계에서는 값이 나오지 않는다
    assert res.value_for("diagnostic") == 0.7  # 진단 경계에서만 명시적으로 legacy를 고른다
    assert res.reason


def test_consumed_resolution_serves_the_same_value_to_both_modes():
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        observation=beta_obs(1.2),
        de_ratio_pct=50.0,
        tax_rate_pct=25.0,
        legacy_unlevered_beta=0.75,
    )
    assert res.value_for("publish") == res.value_for("diagnostic") == res.normalized_value


def test_engine_gate_is_pure_no_wall_clock():
    """evaluation_date가 필수다 — 같은 입력이 실행일에 따라 달라지면 pure가 아니다."""
    with pytest.raises(TypeError):
        resolve_beta(is_listed=False)  # type: ignore[call-arg]

    entry = industry_entry(as_of=date(2025, 1, 5), collected_at=date(2025, 1, 20))
    fresh = resolve_beta(
        evaluation_date=date(2025, 6, 1), is_listed=False, industry_entry=entry
    )
    aged = resolve_beta(
        evaluation_date=date(2026, 7, 13), is_listed=False, industry_entry=entry
    )
    assert fresh.status == "consumed_industry_table"
    assert aged.status == "blocked_stale_industry_table"  # 평가일이 결과를 결정한다


def test_policy_constants_match_the_plan():
    assert BETA_PLAUSIBLE_RANGE == (0.3, 2.0)
    assert BETA_REFERENCE_CONFLICT_MULTIPLE == 1.5
    assert BETA_MIN_PEER_COUNT == 4  # §2.5 — beta만 별도 기준을 두지 않는다
    assert INDUSTRY_BETA_MAX_AGE_DAYS == 400


# ── peer 스냅샷 계약 재작업 (CODEX 2차 블로커) ──


def test_future_dated_peer_snapshot_is_blocked():
    """블로커 1: 평가일보다 미래의 스냅샷 = look-ahead."""
    snap = peer_snapshot([0.8, 0.9, 1.0, 1.1], as_of=date(2027, 1, 1))
    assert snap.freshness(TODAY) == "future"
    res = resolve_beta(
        evaluation_date=TODAY, is_listed=False, peer_snapshot=snap, legacy_unlevered_beta=0.75
    )
    assert res.status == "blocked_invalid_peer_snapshot"
    assert res.normalized_value is None


def test_stale_peer_snapshot_is_blocked():
    """블로커 1: 시장 데이터의 허용 시차는 §2.5 기준(7일)."""
    snap = peer_snapshot(
        [0.8, 0.9, 1.0, 1.1],
        as_of=TODAY - timedelta(days=BETA_PEER_SNAPSHOT_MAX_AGE_DAYS + 1),
    )
    assert snap.freshness(TODAY) == "stale"
    res = resolve_beta(evaluation_date=TODAY, is_listed=False, peer_snapshot=snap)
    assert res.status == "blocked_stale_peer_snapshot"
    assert res.normalized_value is None


def test_peer_snapshot_at_the_age_limit_is_still_fresh():
    snap = peer_snapshot(
        [0.8, 0.9, 1.0, 1.1], as_of=TODAY - timedelta(days=BETA_PEER_SNAPSHOT_MAX_AGE_DAYS)
    )
    assert snap.freshness(TODAY) == "fresh"
    assert resolve_beta(evaluation_date=TODAY, is_listed=False, peer_snapshot=snap).status == (
        "consumed_peer_median"
    )


def test_derived_unlevered_beta_cannot_be_fabricated():
    """블로커 2: unlevered_beta는 저장 필드가 아니다 — 99.0을 써넣을 자리가 없다."""
    assert "unlevered_beta" not in BetaPeerMember.model_fields
    with pytest.raises(ValidationError):
        BetaPeerMember(legal_entity_id="LEI-X", ticker="X", observation=beta_obs(1.0), unlevered_beta=99.0)

    # D/E·세율 Source 없이 unlevered basis 스냅샷을 만들 수 없다
    with pytest.raises(ValidationError):
        peer_snapshot(
            [0.9] * 4,
            members=[
                BetaPeerMember(legal_entity_id=f"LEI-P{i}", ticker=f"P{i}", observation=beta_obs(1.0)) for i in range(4)
            ],
        )


def test_derived_unlevered_beta_is_computed_from_raw_and_capital_structure():
    m = peer_member("P", levered=1.225, de=30.0, tax=25.0)
    assert m.unlevered_beta == pytest.approx(1.225 / 1.225)  # = 1.0


def test_members_must_share_the_snapshot_dataset():
    """블로커 3: 서로 다른 시장·관측창의 beta를 하나의 median으로 섞을 수 없다."""
    with pytest.raises(ValidationError):
        peer_snapshot(
            [0.9] * 4,
            members=[peer_member("US", levered=1.2, **{"observation": beta_obs(1.2, benchmark="S&P 500")})]
            + [peer_member(f"KR{i}", levered=1.1) for i in range(3)],
        )

    with pytest.raises(ValidationError):  # 관측창 불일치
        peer_snapshot(
            [0.9] * 4,
            members=[
                peer_member(
                    "OLD",
                    levered=1.2,
                    **{"observation": beta_obs(1.2, window_start=date(2020, 1, 1))},
                )
            ]
            + [peer_member(f"P{i}", levered=1.1) for i in range(3)],
        )


def test_peer_snapshot_survives_a_serialization_round_trip():
    """블로커 4: 파생값이 dump에 섞여 extra='forbid'와 충돌하면 안 된다."""
    snap = peer_snapshot([0.8, 0.9, 1.0, 1.1])
    payload = snap.model_dump()
    assert "median_beta" not in payload and "peer_count" not in payload
    restored = BetaPeerSnapshot.model_validate(payload)
    assert restored.median_beta == pytest.approx(snap.median_beta)
    assert restored.peer_count == snap.peer_count


def test_a_candidate_without_an_observation_can_still_be_recorded_as_excluded():
    """블로커 5: 'beta 조회 실패로 제외'된 후보도 스냅샷에 남아야 감사가 된다."""
    dropped = BetaPeerMember(
        legal_entity_id="LEI-NOBETA",
        ticker="NOBETA",
        included=False,
        exclusion_reason="yfinance beta 조회 실패",
    )
    snap = peer_snapshot([0.8, 0.9, 1.0, 1.1])
    with_dropped = BetaPeerSnapshot.model_validate(
        {**snap.model_dump(), "members": snap.model_dump()["members"] + [dropped.model_dump()]}
    )
    assert with_dropped.peer_count == 4  # 제외 후보는 median에 들어가지 않는다

    with pytest.raises(ValidationError):  # included인데 관측이 없으면 거부
        BetaPeerMember(legal_entity_id="LEI-X", ticker="X", included=True)


def test_industry_table_source_must_be_damodaran():
    """블로커 6: 문서가 아니라 타입이 강제해야 한다."""
    with pytest.raises(ValidationError):
        industry_entry(
            source=Source(value=1.05, source="yfinance", url="https://x", as_of=date(2026, 1, 5))
        )


def test_sha256_fields_must_look_like_sha256():
    with pytest.raises(ValidationError):
        industry_entry(table_sha256="x")
    with pytest.raises(ValidationError):
        peer_snapshot([0.8, 0.9, 1.0, 1.1], content_sha256="x")


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(status="consumed_raw", basis="unlevered", normalized_value=None),  # 소비인데 값 없음
        dict(status="consumed_raw", basis="unlevered", normalized_value=float("nan")),
        dict(status="blocked_no_reference", basis="unlevered", normalized_value=0.9),  # 차단인데 값 있음
        dict(status="blocked_no_reference", basis="unlevered", diagnostic_value=float("inf")),
        dict(status="blocked_no_reference", basis="unlevered", peer_count=-1),
    ],
)
def test_beta_resolution_invariants_cannot_be_forged(kwargs):
    """블로커 7: 불변식을 깨는 판정 객체는 생성 자체가 실패해야 한다."""
    with pytest.raises(ValueError):
        BetaResolution(reason="forged", **kwargs)


# ── 시간축 · peer 고유성 (CODEX 3차 블로커) ──


def test_target_beta_window_cannot_end_in_the_future():
    """블로커 1: 대상 회사 beta도 look-ahead를 막아야 한다."""
    future = beta_obs(1.2, as_of=date(2027, 1, 1))
    assert future.freshness(TODAY) == "future"
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        target_basis="equity",
        observation=future,
        legacy_unlevered_beta=0.75,
    )
    assert res.status == "blocked_invalid_observation"
    assert res.normalized_value is None


def test_stale_target_beta_is_blocked():
    stale = beta_obs(1.2, as_of=TODAY - timedelta(days=BETA_OBSERVATION_MAX_AGE_DAYS + 1))
    assert stale.freshness(TODAY) == "stale"
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        observation=stale,
        de_ratio_pct=30.0,
        tax_rate_pct=25.0,
    )
    assert res.status == "blocked_stale_observation"


def test_an_old_window_cannot_be_repackaged_with_a_fresh_as_of():
    """2020년에 끝난 관측창을 오늘 날짜로 포장할 수 없다 — as_of == window_end."""
    with pytest.raises(ValidationError):
        BetaObservation(
            equity_beta=Source(
                value=1.2,
                source="yfinance",
                url="https://x",
                as_of=TODAY,  # 최신인 척
                method="derived",
                derived_from=["x"],
            ),
            window_start=date(2018, 1, 1),
            window_end=date(2020, 12, 31),  # 실제로는 2020년에 끝난 관측
            frequency="weekly",
            benchmark=BENCHMARK,
            observation_count=104,
            calculation_method=METHOD,
        )


def test_stale_peers_do_not_block_a_valid_industry_fallback():
    """블로커 2: stale peer는 peer 근거에서 빠질 뿐, 유효한 산업 테이블까지 막지 않는다."""
    stale_snap = peer_snapshot(
        [0.8, 0.9, 1.0, 1.1],
        as_of=TODAY - timedelta(days=BETA_PEER_SNAPSHOT_MAX_AGE_DAYS + 1),
    )
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=False,
        peer_snapshot=stale_snap,
        industry_entry=industry_entry(1.05),
    )
    assert res.status == "consumed_industry_table"  # §2.3 우선순위 유지
    assert res.normalized_value == 1.05
    assert any("stale" in w for w in res.warnings)


def test_stale_peers_do_not_block_a_listed_raw_beta_but_warn():
    stale_snap = peer_snapshot(
        [0.8, 0.9, 1.0, 1.1],
        as_of=TODAY - timedelta(days=BETA_PEER_SNAPSHOT_MAX_AGE_DAYS + 1),
    )
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        observation=beta_obs(1.2),
        de_ratio_pct=30.0,
        tax_rate_pct=25.0,
        peer_snapshot=stale_snap,
    )
    assert res.status == "consumed_raw"  # 교차검증만 못 할 뿐 raw는 유효하다
    assert any("교차검증" in w for w in res.warnings)


def test_stale_peers_block_only_when_nothing_else_remains():
    stale_snap = peer_snapshot(
        [0.8, 0.9, 1.0, 1.1],
        as_of=TODAY - timedelta(days=BETA_PEER_SNAPSHOT_MAX_AGE_DAYS + 1),
    )
    res = resolve_beta(evaluation_date=TODAY, is_listed=False, peer_snapshot=stale_snap)
    assert res.status == "blocked_stale_peer_snapshot"


def test_the_same_entity_cannot_be_counted_four_times():
    """블로커 3: 같은 법인을 복제해 최소 peer 수를 채울 수 없다."""
    with pytest.raises(ValidationError):
        peer_snapshot(
            [0.9] * 4,
            members=[peer_member("SAME", levered=1.1) for _ in range(4)],
        )

    with pytest.raises(ValidationError):  # 대소문자만 다른 티커도 중복이다
        peer_snapshot(
            [0.9] * 2,
            members=[
                peer_member("abc", levered=1.1),
                peer_member("ABC", levered=1.2, **{"legal_entity_id": "LEI-OTHER"}),
            ],
        )


def test_de_and_tax_sources_must_be_observations():
    """블로커 4: 가정을 Source로 위장해 파생 unlevered beta의 입력으로 쓸 수 없다."""
    assumed_de = Source.model_construct(
        value=30.0, source="yfinance", url="https://x", as_of=SNAP_AS_OF,
        method="declared_assumption",
    )
    with pytest.raises(ValidationError):
        peer_member("P", levered=1.2, **{"de_ratio_pct": assumed_de})


def test_unlevered_members_need_both_capital_structure_sources():
    with pytest.raises(ValidationError):
        peer_snapshot(
            [0.9] * 4,
            members=[peer_member(f"P{i}", levered=1.1) for i in range(3)]
            + [peer_member("NOTAX", levered=1.1, **{"tax_rate_pct": None})],
        )


def test_industry_table_collected_before_its_own_reference_date_is_rejected():
    """블로커 5: 존재하지 않는 자료를 수집할 수는 없다."""
    with pytest.raises(ValidationError):
        industry_entry(as_of=date(2026, 6, 1), collected_at=date(2026, 1, 20))


def test_industry_table_collected_in_the_future_is_not_consumed():
    entry = industry_entry(as_of=date(2026, 1, 5), collected_at=date(2027, 1, 20))
    assert entry.freshness(TODAY) == "future"
    res = resolve_beta(evaluation_date=TODAY, is_listed=False, industry_entry=entry)
    assert res.status == "blocked_invalid_industry_table"


# ── 최종 provenance 우회 (CODEX 4차) ──


def test_declared_assumption_industry_beta_is_rejected():
    """블로커 1: Damodaran 출처를 달아도 가정은 관측치가 아니다."""
    assumed = Source.model_construct(
        value=1.05,
        source="Damodaran",
        url="https://x",
        as_of=date(2026, 1, 5),
        method="declared_assumption",
    )
    with pytest.raises(ValidationError):
        industry_entry(source=assumed)


def test_peers_from_a_different_dataset_are_excluded_from_the_cross_check():
    """블로커 2: S&P 500 기준 target을 KOSPI peer median으로 반증할 수 없다."""
    kospi_peers = peer_snapshot([0.5, 0.5, 0.5, 0.5])  # median 0.5 -> 임계 0.75
    sp500_target = beta_obs(2.00, benchmark="S&P 500")  # 언레버 1.63 > 0.75 (같은 데이터셋이면 충돌)

    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        observation=sp500_target,
        de_ratio_pct=30.0,
        tax_rate_pct=25.0,
        peer_snapshot=kospi_peers,
    )
    assert res.status == "consumed_raw"  # 다른 데이터셋 peer로 차단하지 않는다
    assert res.peer_median is None  # 교차검증에서 제외
    assert res.peer_count == 0
    assert any("데이터셋" in w for w in res.warnings)


def test_same_dataset_peers_still_gate_the_cross_check():
    """데이터셋이 같으면 교차검증은 정상 작동한다 (위 예외가 구멍이 되면 안 된다)."""
    peers = peer_snapshot([0.5, 0.5, 0.5, 0.5])
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        observation=beta_obs(2.00),  # 같은 KOSPI 데이터셋
        de_ratio_pct=30.0,
        tax_rate_pct=25.0,
        peer_snapshot=peers,
        legacy_unlevered_beta=0.75,
    )
    assert res.status == "blocked_reference_conflict"


@pytest.mark.parametrize("field,value", [("frequency", "monthly"), ("calculation_method", "OLS on daily returns")])
def test_dataset_mismatch_covers_frequency_and_method(field, value):
    peers = peer_snapshot([0.5, 0.5, 0.5, 0.5])
    res = resolve_beta(
        evaluation_date=TODAY,
        is_listed=True,
        observation=beta_obs(2.00, **{field: value}),
        de_ratio_pct=30.0,
        tax_rate_pct=25.0,
        peer_snapshot=peers,
    )
    assert res.status == "consumed_raw"
    assert res.peer_count == 0
