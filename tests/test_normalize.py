"""P0-1 순차입금 정규화 게이트 (PLAN_deep_research.md §2.1).

계약 (HANDOFF_CODEX_p0-0_commit.md §8):
  1. 파서는 net_debt(독립 합계)와 구성요소를 서로 다른 원천에서 수집한다.
  2. 엔진은 reconciled is True일 때만 정규화 값을 소비한다.
  3. False(불일치) / None(대조 불가)은 둘 다 차단 -> legacy 정의 유지.
  4. 독립 합계를 구할 수 없으면 임의 생성하지 않는다.

이 파일이 지키는 회귀: "구성요소를 더해서 net_debt에 넣는" 퇴화(reconciled가 항상 True).
"""

from pathlib import Path

import pytest
import yaml

from engine.normalize import resolve_net_debt
from valuation_runner import apply_net_debt_gate, load_profile, run_valuation
from pipeline import dart_parser, edgar_parser
from schemas.provenance import (
    LEGACY_VERSION,
    NORMALIZATION_VERSION,
    NET_DEBT_RECONCILE_TOLERANCE,
    NetDebtComponents,
)

# NVDA Q1 FY27 (PLAN §0/§2.1): cash 13,237 + 시장성 채무증권 37,098, 차입 8,470 -> 순현금 41,865
NVDA = dict(
    cash=13_237,
    marketable_debt_securities=37_098,
    gross_borrowings=8_470,
)
NVDA_NET_DEBT = -41_865


# ── 게이트: 소비 조건 ──


def test_reconciled_true_is_the_only_path_that_consumes_the_normalized_value():
    nd = NetDebtComponents(**NVDA, net_debt=NVDA_NET_DEBT)
    assert nd.reconciled is True

    res = resolve_net_debt(nd, legacy_net_debt=-4_767)  # legacy = 8,470 - 13,237
    assert res.status == "consumed"
    assert res.value == NVDA_NET_DEBT  # taxonomy 정의값 (시장성 채무증권까지 차감)
    assert res.legacy_value == -4_767  # legacy는 파괴되지 않는다
    assert res.normalization_version == NORMALIZATION_VERSION
    assert res.delta == 0


def test_mismatch_is_blocked_and_falls_back_to_legacy():
    """불일치는 예외가 아니라 차단이다 — 그리고 legacy 값을 계속 쓴다."""
    nd = NetDebtComponents(**NVDA, net_debt=-30_000)  # 독립 합계가 어긋남
    assert nd.reconciled is False

    res = resolve_net_debt(nd, legacy_net_debt=-4_767)
    assert res.status == "blocked_mismatch"
    assert res.blocked is True
    assert res.value == -4_767  # legacy
    assert res.normalized_value == NVDA_NET_DEBT  # 계산은 했지만 소비하지 않는다
    assert res.delta == 11_865
    assert res.normalization_version == LEGACY_VERSION


def test_missing_independent_total_is_blocked_not_imputed():
    """독립 합계가 없으면 구성요소 합으로 채우지 않는다 — 대조가 정의로 퇴화한다."""
    nd = NetDebtComponents(**NVDA)  # net_debt=None
    assert nd.reconciled is None

    res = resolve_net_debt(nd, legacy_net_debt=-4_767)
    assert res.status == "blocked_unreconcilable"
    assert res.value == -4_767
    assert res.independent_total is None


def test_one_sided_components_are_blocked():
    """차입 측이 없는데 0으로 채우면 순현금이 날조된다."""
    nd = NetDebtComponents(cash=13_237, net_debt=-13_237)
    res = resolve_net_debt(nd, legacy_net_debt=0)
    assert res.status == "blocked_unreconcilable"
    assert res.value == 0


def test_absent_components_leave_legacy_untouched():
    """P0 이전 프로필: 동작 무변화 (R10 회귀 방지)."""
    res = resolve_net_debt(None, legacy_net_debt=1_234_567)
    assert res.status == "absent"
    assert res.value == 1_234_567
    assert res.normalization_version == LEGACY_VERSION


def test_rounding_noise_within_tolerance_still_reconciles():
    """단위 반올림($1M)만으로 전 종목을 차단하면 그건 대조가 아니라 잡음이다."""
    nd = NetDebtComponents(
        **NVDA, net_debt=NVDA_NET_DEBT + NET_DEBT_RECONCILE_TOLERANCE
    )
    assert nd.reconciled is True
    assert resolve_net_debt(nd, legacy_net_debt=0).status == "consumed"


def test_difference_beyond_rounding_is_a_definition_error():
    nd = NetDebtComponents(
        **NVDA, net_debt=NVDA_NET_DEBT + NET_DEBT_RECONCILE_TOLERANCE + 1
    )
    assert nd.reconciled is False
    assert resolve_net_debt(nd, legacy_net_debt=0).status == "blocked_mismatch"


def test_excluded_buckets_never_enter_the_deduction():
    """제한현금·시장성 지분증권은 기록만 하고 차감하지 않는다 (§2.1)."""
    nd = NetDebtComponents(
        **NVDA,
        net_debt=NVDA_NET_DEBT,
        restricted_cash_excluded=1_500,
        equity_securities_excluded=21_100,
    )
    res = resolve_net_debt(nd, legacy_net_debt=0)
    assert res.status == "consumed"
    assert res.value == NVDA_NET_DEBT  # 제외 버킷을 차감했다면 -64,465가 됐을 것


# ── EDGAR 파서: 독립 원천 ──


def _facts(**tags) -> dict:
    """{tag: raw USD} -> company facts JSON (FY2026 10-K)."""
    return {
        "facts": {
            "us-gaap": {
                tag: {
                    "units": {
                        "USD": [
                            {
                                "fy": 2026,
                                "fp": "FY",
                                "form": "10-K",
                                "end": "2026-01-25",
                                "val": val,
                            }
                        ]
                    }
                }
                for tag, val in tags.items()
            }
        }
    }


M = 1_000_000


def test_edgar_component_and_total_tags_are_disjoint():
    """계약의 뿌리: 두 경로가 같은 태그를 쓰면 reconciled는 항상 True가 된다."""
    assert not (edgar_parser._PATH_A_TAGS & edgar_parser._PATH_B_TAGS)


def test_edgar_collects_total_from_aggregate_tags_not_from_the_components():
    facts = _facts(
        # Path A — 개별 태그 (구성요소)
        CashAndCashEquivalentsAtCarryingValue=13_237 * M,
        MarketableSecuritiesCurrent=37_098 * M,
        LongTermDebtCurrent=1_000 * M,
        LongTermDebtNoncurrent=7_470 * M,
        # Path B — 결합 태그 (독립 합계). 구성요소 합과 무관하게 회사가 보고한 값.
        DebtLongtermAndShorttermCombinedAmount=8_470 * M,
        CashCashEquivalentsAndShortTermInvestments=50_335 * M,
    )
    nd = edgar_parser.extract_net_debt_components(facts, 2026)

    assert nd.gross_borrowings == 8_470  # 개별 태그의 합
    assert nd.net_debt == NVDA_NET_DEBT  # 결합 태그에서 온 독립 합계
    assert nd.expected_net_debt() == NVDA_NET_DEBT
    assert nd.reconciled is True

    res = resolve_net_debt(nd, legacy_net_debt=-4_767)
    assert res.status == "consumed"
    assert res.value == NVDA_NET_DEBT


def test_edgar_returns_no_total_when_the_company_never_reported_one():
    """결합 태그가 없으면 net_debt=None. 구성요소를 더해 채우지 않는다."""
    facts = _facts(
        CashAndCashEquivalentsAtCarryingValue=13_237 * M,
        MarketableSecuritiesCurrent=37_098 * M,
        LongTermDebtNoncurrent=8_470 * M,
    )
    nd = edgar_parser.extract_net_debt_components(facts, 2026)

    assert nd.expected_net_debt() == NVDA_NET_DEBT  # 정의값은 계산된다
    assert nd.net_debt is None  # 그러나 독립 합계를 날조하지는 않는다
    assert nd.reconciled is None
    assert (
        resolve_net_debt(nd, legacy_net_debt=-4_767).status == "blocked_unreconcilable"
    )


def test_edgar_double_counted_cash_pool_is_caught_by_the_gate():
    """단기투자 = 시장성 채무증권과 같은 풀. 둘 다 차감하면 순현금이 부풀려진다."""
    facts = _facts(
        CashAndCashEquivalentsAtCarryingValue=13_237 * M,
        MarketableSecuritiesCurrent=37_098 * M,
        ShortTermInvestments=37_098 * M,  # 같은 풀의 다른 태그
        LongTermDebtNoncurrent=8_470 * M,
        DebtLongtermAndShorttermCombinedAmount=8_470 * M,
        CashCashEquivalentsAndShortTermInvestments=50_335 * M,
    )
    nd = edgar_parser.extract_net_debt_components(facts, 2026)

    # 파서가 우선순위로 하나만 채택한다 -> 이중차감 없음
    assert nd.short_term_investments is None
    assert nd.deductible_cash == 50_335
    assert nd.reconciled is True


def test_edgar_missing_tag_family_gives_up_instead_of_guessing():
    facts = _facts(Revenues=130_497 * M)
    assert edgar_parser.extract_net_debt_components(facts, 2026) is None


def test_edgar_restricted_cash_is_removed_from_the_combined_cash_tag():
    """결합 태그밖에 없으면 제한현금을 빼고 쓴다 (§2.1)."""
    facts = _facts(
        CashAndCashEquivalentsAtCarryingValue=13_237 * M,
        MarketableSecuritiesCurrent=37_098 * M,
        LongTermDebtNoncurrent=8_470 * M,
        DebtLongtermAndShorttermCombinedAmount=8_470 * M,
        CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents=50_835 * M,
        RestrictedCashAndCashEquivalentsAtCarryingValue=500 * M,
    )
    nd = edgar_parser.extract_net_debt_components(facts, 2026)

    assert nd.restricted_cash_excluded == 500
    assert nd.net_debt == NVDA_NET_DEBT  # 50,835 - 500 = 50,335 차감
    assert nd.reconciled is True


def test_edgar_mismatch_between_paths_blocks_consumption():
    """결합 태그가 개별 태그와 어긋난다 = 우리 매핑이 뭔가 놓쳤다는 신호."""
    facts = _facts(
        CashAndCashEquivalentsAtCarryingValue=13_237 * M,
        MarketableSecuritiesCurrent=37_098 * M,
        LongTermDebtNoncurrent=8_470 * M,  # 개별: CP 1,200을 놓침
        DebtLongtermAndShorttermCombinedAmount=9_670 * M,  # 결합: CP 포함
        CashCashEquivalentsAndShortTermInvestments=50_335 * M,
    )
    nd = edgar_parser.extract_net_debt_components(facts, 2026)

    assert nd.reconciled is False
    assert nd.reconciliation_delta == 1_200
    res = resolve_net_debt(nd, legacy_net_debt=-4_767)
    assert res.status == "blocked_mismatch"
    assert res.value == -4_767


# ── DART 파서 ──


def _bs(name: str, won: int) -> dict:
    return {"sj_div": "BS", "account_nm": name, "thstrm_amount": f"{won:,}"}


def _cf(name: str, won: int) -> dict:
    return {"sj_div": "CF", "account_nm": name, "thstrm_amount": f"{won:,}"}


BILLION = 1_000_000_000


def test_dart_collects_components_but_never_fabricates_a_total():
    """DART 표준계정에는 순차입금 단일 사실이 없다 -> net_debt=None (대조 불가)."""
    items = [
        _bs("단기차입금", 1_000 * BILLION),
        _bs("장기차입금", 2_000 * BILLION),
        _bs("현금및현금성자산", 4_000 * BILLION),
        _bs("단기금융상품", 1_500 * BILLION),
    ]
    nd = dart_parser.extract_net_debt_components(items)

    assert nd.gross_borrowings == 3_000_000  # 백만원
    assert nd.cash == 4_000_000
    assert nd.short_term_investments == 1_500_000
    assert nd.expected_net_debt() == -2_500_000
    assert nd.net_debt is None
    assert nd.reconciled is None

    res = resolve_net_debt(nd, legacy_net_debt=-2_500_000)
    assert res.status == "blocked_unreconcilable"  # KR은 현재 항상 여기 — 의도된 동작
    assert res.value == -2_500_000  # legacy 유지


def test_dart_ignores_cash_flow_lines():
    """NAVER 순현금 5배 과대계상 회귀: CF 항목이 BS 계정으로 새면 안 된다."""
    items = [
        _bs("단기차입금", 1_000 * BILLION),
        _bs("현금및현금성자산", 4_000 * BILLION),
        _cf("사채의 발행", 9_000 * BILLION),
        _cf("단기금융상품의 감소", 8_000 * BILLION),
        _cf("기말현금및현금성자산", 4_000 * BILLION),
    ]
    nd = dart_parser.extract_net_debt_components(items)

    assert nd.gross_borrowings == 1_000_000
    assert nd.cash == 4_000_000
    assert nd.short_term_investments is None


def test_dart_restricted_cash_is_recorded_not_deducted():
    items = [
        _bs("단기차입금", 1_000 * BILLION),
        _bs("현금및현금성자산", 4_000 * BILLION),
        _bs("사용제한예금", 300 * BILLION),
    ]
    nd = dart_parser.extract_net_debt_components(items)

    assert nd.restricted_cash_excluded == 300_000
    assert nd.deductible_cash == 4_000_000  # 제한현금은 차감되지 않는다
    assert nd.expected_net_debt() == -3_000_000


def test_dart_returns_none_when_no_balance_sheet_items():
    assert (
        dart_parser.extract_net_debt_components([_cf("사채의 발행", 1 * BILLION)])
        is None
    )


# ── 직렬화: reconciled는 위조할 수 없다 ──


@pytest.mark.parametrize("forged", [True, False, None])
def test_gate_cannot_be_bypassed_by_writing_reconciled_into_the_payload(forged):
    payload = {**NVDA, "net_debt": -30_000, "reconciled": forged}
    nd = NetDebtComponents.model_validate(payload)
    assert nd.reconciled is False  # computed — payload는 무시된다
    assert resolve_net_debt(nd, legacy_net_debt=-4_767).status == "blocked_mismatch"


# ── E2E: YAML -> load_profile -> 엔진이 실제로 무엇을 소비하는가 ──


def _profile_with_components(tmp_path, components: dict | None) -> str:
    """프로즌 MSFT 프로필(legacy net_debt=30,346)에 §2.1 원장을 얹은 사본."""
    src = Path(__file__).parent / "fixtures" / "msft_frozen.yaml"
    raw = yaml.safe_load(src.read_text(encoding="utf-8"))
    if components is not None:
        raw["net_debt_components"] = components
    dst = tmp_path / "msft_p01.yaml"
    dst.write_text(
        yaml.dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return str(dst)


def test_e2e_legacy_profile_is_untouched(tmp_path):
    """R10 회귀: P0 이전 프로필은 동작이 바뀌지 않는다."""
    vi = load_profile(_profile_with_components(tmp_path, None))
    assert vi.net_debt == 30_346
    assert vi.normalization_version == LEGACY_VERSION
    assert vi.net_debt_legacy is None


def test_e2e_reconciled_components_replace_the_engine_input(tmp_path):
    """reconciled is True -> 엔진이 읽는 vi.net_debt가 정규화 값으로 교체된다."""
    path = _profile_with_components(
        tmp_path,
        # 독립 합계(-41,865)가 구성요소 정의값과 일치
        {**NVDA, "net_debt": NVDA_NET_DEBT},
    )
    vi = load_profile(path)

    assert vi.net_debt == NVDA_NET_DEBT  # 엔진 소비값
    assert vi.net_debt_legacy == 30_346  # 교체 전 legacy 스칼라 보존
    assert vi.normalization_version == NORMALIZATION_VERSION


def test_e2e_blocked_components_leave_the_engine_on_legacy(tmp_path):
    """reconciled is False -> 엔진은 legacy 값을 계속 쓴다 (정규화 미주장)."""
    path = _profile_with_components(
        tmp_path,
        {**NVDA, "net_debt": -30_000},  # 정의 불일치
    )
    vi = load_profile(path)

    assert vi.net_debt == 30_346  # legacy 그대로
    assert vi.normalization_version == LEGACY_VERSION


def test_e2e_unreconcilable_components_leave_the_engine_on_legacy(tmp_path):
    """독립 합계 없음(KR 전 종목의 현재 상태) -> legacy 유지."""
    path = _profile_with_components(tmp_path, dict(NVDA))  # net_debt 없음
    vi = load_profile(path)

    assert vi.net_debt == 30_346
    assert vi.normalization_version == LEGACY_VERSION


def test_e2e_forged_reconciled_in_yaml_does_not_open_the_gate(tmp_path):
    """YAML에 reconciled: true를 써넣어도 computed_field라 위조되지 않는다."""
    path = _profile_with_components(
        tmp_path, {**NVDA, "net_debt": -30_000, "reconciled": True}
    )
    vi = load_profile(path)

    assert vi.net_debt_components.reconciled is False
    assert vi.net_debt == 30_346  # 게이트는 열리지 않는다


# ── 우회 차단 + 멱등성 (CODEX 재작업 판정 1) ──


def _ungate(vi):
    """게이트를 거치지 않은 ValuationInput을 만든다 (load_profile 우회 경로 재현)."""
    return vi.model_copy(
        update={
            "net_debt": vi.net_debt_legacy,
            "net_debt_legacy": None,
            "normalization_version": LEGACY_VERSION,
        }
    )


def test_run_valuation_gates_an_input_that_never_passed_load_profile(tmp_path):
    """공개 진입점 run_valuation(vi)도 게이트를 통과해야 한다 — 우회 경로 차단."""
    gated = load_profile(
        _profile_with_components(tmp_path, {**NVDA, "net_debt": NVDA_NET_DEBT})
    )
    assert gated.net_debt == NVDA_NET_DEBT and gated.net_debt_legacy == 30_346

    ungated = _ungate(gated)  # 손으로 만든 vi: legacy 스칼라 + 미소비 상태
    assert ungated.net_debt == 30_346

    # 게이트가 run_valuation 안에서 다시 적용되므로 두 결과가 같아야 한다.
    assert run_valuation(ungated).weighted_value == run_valuation(gated).weighted_value

    # legacy(30,346)와 정규화(-41,865)는 실제로 다른 결과를 낸다 — 대조군.
    legacy_only = ungated.model_copy(update={"net_debt_components": None})
    assert (
        run_valuation(legacy_only).weighted_value != run_valuation(gated).weighted_value
    )


def test_run_valuation_does_not_consume_unreconciled_components(tmp_path):
    """reconciled=False인 vi를 직접 넘겨도 정규화 값이 소비되면 안 된다."""
    vi = load_profile(_profile_with_components(tmp_path, {**NVDA, "net_debt": -30_000}))
    assert vi.net_debt == 30_346  # legacy

    legacy_only = vi.model_copy(update={"net_debt_components": None})
    assert run_valuation(vi).weighted_value == run_valuation(legacy_only).weighted_value


def test_gate_is_idempotent(tmp_path):
    """두 번 적용해도 net_debt_legacy가 정규화 값으로 덮어써지지 않는다."""
    once = load_profile(
        _profile_with_components(tmp_path, {**NVDA, "net_debt": NVDA_NET_DEBT})
    )
    twice = apply_net_debt_gate(once)
    thrice = apply_net_debt_gate(twice)

    for vi in (twice, thrice):
        assert vi.net_debt == NVDA_NET_DEBT
        assert vi.net_debt_legacy == 30_346  # legacy가 보존된다 (핵심 회귀)
        assert vi.normalization_version == NORMALIZATION_VERSION
    assert twice is once  # 이미 통과한 입력은 복사조차 하지 않는다


def test_gate_is_idempotent_on_the_blocked_path(tmp_path):
    vi = load_profile(_profile_with_components(tmp_path, {**NVDA, "net_debt": -30_000}))
    again = apply_net_debt_gate(vi)
    assert again is vi
    assert again.net_debt == 30_346
    assert again.normalization_version == LEGACY_VERSION


def test_swapping_components_on_a_gated_input_is_re_gated(tmp_path):
    """멱등성이 '재대조 면제'로 퇴화하면 안 된다 — components가 바뀌면 다시 판정한다."""
    gated = load_profile(
        _profile_with_components(tmp_path, {**NVDA, "net_debt": NVDA_NET_DEBT})
    )
    # 소비 표지(normalization_version/net_debt_legacy)는 그대로 둔 채 원장만 불일치로 교체
    tampered = gated.model_copy(
        update={
            "net_debt_components": NetDebtComponents(**NVDA, net_debt=-30_000),
        }
    )
    regated = apply_net_debt_gate(tampered)
    assert regated.normalization_version == LEGACY_VERSION  # 차단으로 되돌아간다
    assert regated.net_debt == 30_346  # 소비했던 정규화 값을 롤백한다
    assert regated.net_debt_legacy is None


def test_removing_the_ledger_after_consumption_rolls_back_to_legacy(tmp_path):
    """소비 후 원장이 사라지면 정규화 값도 함께 내려놔야 한다 (검증 축 소멸)."""
    gated = load_profile(
        _profile_with_components(tmp_path, {**NVDA, "net_debt": NVDA_NET_DEBT})
    )
    assert (gated.net_debt, gated.net_debt_legacy) == (NVDA_NET_DEBT, 30_346)

    orphaned = gated.model_copy(update={"net_debt_components": None})
    regated = apply_net_debt_gate(orphaned)

    assert regated.net_debt == 30_346  # legacy로 롤백
    assert regated.net_debt_legacy is None
    assert regated.normalization_version == LEGACY_VERSION

    # run_valuation을 직접 태워도 마찬가지 (우회 불가)
    legacy_only = gated.model_copy(
        update={
            "net_debt": 30_346,
            "net_debt_legacy": None,
            "net_debt_components": None,
            "normalization_version": LEGACY_VERSION,
        }
    )
    assert (
        run_valuation(orphaned).weighted_value
        == run_valuation(legacy_only).weighted_value
    )


def test_version_claimed_without_a_ledger_is_demoted_to_legacy(tmp_path):
    """원장 없이 normalization_version만 최신으로 위조한 YAML -> legacy 강등."""
    src = Path(__file__).parent / "fixtures" / "msft_frozen.yaml"
    raw = yaml.safe_load(src.read_text(encoding="utf-8"))
    raw["normalization_version"] = NORMALIZATION_VERSION  # 원장은 없다
    dst = tmp_path / "msft_forged_version.yaml"
    dst.write_text(
        yaml.dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    vi = load_profile(str(dst))

    assert vi.net_debt_components is None
    assert vi.normalization_version == LEGACY_VERSION  # 주장은 기각된다
    assert vi.net_debt == 30_346
