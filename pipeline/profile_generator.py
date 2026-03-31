"""자동 데이터 수집 → YAML 프로필 생성 + AI 자동 분석."""

import re
from datetime import date
from pathlib import Path

import yaml


# 프로젝트 루트 (cli.py가 아니라 이 파일 기준으로 상위 디렉토리)
_PROJECT_ROOT = Path(__file__).parent.parent


def auto_fetch(company_query: str) -> dict:
    """기업명/ticker 입력 → 자동 판별 → 재무 데이터 수집 → raw dict 반환."""
    from pipeline.data_fetcher import DataFetcher

    fetcher = DataFetcher()

    # Step 1: 기업 식별
    print(f"\n[1/3] 기업 식별 중: '{company_query}'")
    identity = fetcher.identify(company_query)
    if not identity:
        print(f"  [ERROR] 기업을 찾을 수 없습니다: {company_query}")
        return {}

    market_label = "한국 (DART)" if identity.market == "KR" else "미국 (SEC EDGAR)"
    print(f"  → {identity.name} | {market_label}")
    if identity.ticker:
        print(f"    Ticker: {identity.ticker}")
    if identity.cik:
        print(f"    CIK: {identity.cik}")
    if identity.corp_code:
        print(f"    DART corp_code: {identity.corp_code}")

    # Step 2: 재무제표 수집
    print(f"\n[2/3] 재무제표 수집 중...")
    financials = fetcher.fetch_financials(identity)
    if not financials:
        print("  [ERROR] 재무제표를 수집할 수 없습니다.")
        return {}

    for year, data in sorted(financials.items(), reverse=True):
        rev = data.get("revenue", 0)
        op = data.get("op", 0)
        unit = "$M" if identity.market == "US" else "백만원"
        print(f"  {year}: 매출 {rev:,}{unit}, 영업이익 {op:,}{unit}")

    # Step 3: 주식수 / 시장 데이터
    print(f"\n[3/3] 시장 데이터 수집 중...")
    shares_info = fetcher.fetch_shares(identity)
    if shares_info.get("shares_total"):
        print(f"  총 주식수: {shares_info['shares_total']:,}")
    if shares_info.get("price"):
        currency = shares_info.get("currency", "")
        print(f"  현재가: {shares_info['price']:,.2f} {currency}")

    # Step 4: YAML 프로필 자동 생성
    yaml_path = _generate_draft_profile(identity, financials, shares_info)

    print(f"\n{'='*60}")
    print(f"데이터 수집 완료: {identity.name}")
    print(f"시장: {identity.market} | 연도: {sorted(financials.keys())}")
    print(f"{'='*60}")
    if yaml_path:
        print(f"\n[Draft YAML 생성됨] {yaml_path}")
        print(f"  → 부문 데이터, 멀티플, 시나리오를 편집한 후:")
        print(f"    python cli.py --profile {yaml_path} --excel")

    return {
        "identity": identity,
        "financials": financials,
        "shares": shares_info,
        "yaml_path": yaml_path,
    }


def _estimate_wacc_params(
    cons: dict, shares_info: dict, market: str, identity
) -> dict:
    """데이터 기반 WACC 파라미터 자동 추정.

    핵심 원칙:
    - D/E: 이자발생부채(gross_borr) / 시장자본(market_cap) (총부채/장부자본 아님)
    - Tax: min(max(effective_tax, 0), statutory_max)
    - Beta: yfinance → Hamada unlever
    - Kd: |interest_expense| / gross_borr
    - Equity weight: market_cap / (market_cap + gross_borr)
    """
    is_us = market == "US"
    # 시장별 기본값
    rf = 4.25 if is_us else 3.50
    erp = 5.50 if is_us else 7.00
    statutory_tax = 21.0 if is_us else 25.0
    default_bu = 1.0 if is_us else 0.75
    default_kd = rf + 2.0

    market_price = shares_info.get("price", 0)
    shares_total = shares_info.get("shares_total", 0)
    gross_borr = cons.get("gross_borr", 0)
    interest_expense = cons.get("interest_expense", 0)

    # yfinance beta 수집
    levered_beta = shares_info.get("beta")  # fetch_shares에서 전달
    if levered_beta is None:
        # yfinance_fetcher에서 직접 시도
        try:
            from pipeline.yfinance_fetcher import fetch_market_data
            if identity.ticker:
                md = fetch_market_data(identity.ticker, market)
                if md:
                    levered_beta = md.get("beta")
        except Exception:
            pass

    # 시장자본 계산 (재무제표와 동일 단위: 백만원/$M)
    # price * shares = raw currency → ÷ 1,000,000 → 재무제표 단위
    market_cap = 0.0
    if market_price > 0 and shares_total > 0:
        market_cap = market_price * shares_total / 1_000_000

    # --- Tax rate: 실효세율 클램핑 ---
    from pipeline.macro_data import calc_effective_tax_rate
    effective_tax = calc_effective_tax_rate({0: cons})  # dummy year key
    if effective_tax is not None:
        tax = min(max(effective_tax, 0.0), statutory_tax)
    else:
        tax = statutory_tax * 0.85  # 보수적 기본값

    # --- D/E: gross_borr / market_cap ---
    if market_cap > 0 and gross_borr > 0:
        de_ratio = round(gross_borr / market_cap * 100, 1)
    elif market_cap > 0:
        de_ratio = 0.0
    else:
        # 비상장: 장부가 기반 fallback
        equity_bv = cons.get("equity", 0)
        liabilities = cons.get("liabilities", 0)
        de_ratio = round(liabilities / equity_bv * 100, 1) if equity_bv > 0 else 100.0

    # --- Equity weight ---
    if market_cap > 0:
        eq_w = round(market_cap / (market_cap + max(gross_borr, 0)) * 100, 1)
    else:
        eq_w = round(100 / (1 + de_ratio / 100), 1)

    # --- Unlevered beta (Hamada) ---
    if levered_beta and levered_beta > 0 and market_cap > 0:
        hamada_de = gross_borr / market_cap if market_cap > 0 else 0
        bu = round(levered_beta / (1 + (1 - tax / 100) * hamada_de), 3)
        bu = max(bu, 0.1)  # 비현실적 값 방지
    else:
        bu = default_bu

    # --- Kd_pre: |interest_expense| / gross_borr ---
    if gross_borr > 0 and interest_expense != 0:
        kd_pre = round(abs(interest_expense) / gross_borr * 100, 2)
        # 범위 제한: [rf, rf + 5%]
        kd_pre = max(rf, min(kd_pre, rf + 5.0))
    else:
        kd_pre = default_kd

    return {
        "rf": rf, "erp": erp, "bu": bu,
        "de": de_ratio, "tax": round(tax, 1),
        "kd_pre": kd_pre, "eq_w": eq_w,
    }


def _generate_draft_profile(identity, financials: dict, shares_info: dict) -> str | None:
    """수집된 데이터로 draft YAML 프로필 자동 생성."""
    years = sorted(financials.keys())
    if not years:
        return None

    latest = years[-1]
    cons = financials[latest]

    is_us = identity.market == "US"
    currency = "USD" if is_us else "KRW"
    unit = "$M" if is_us else "백만원"

    shares_total = shares_info.get("shares_total", 0)
    shares_ordinary = shares_info.get("shares_ordinary", shares_total)
    shares_preferred = shares_info.get("shares_preferred", 0)
    treasury_shares = shares_info.get("treasury_shares", 0)

    equity_bv = cons.get("equity", 0)
    liabilities = cons.get("liabilities", 0)
    net_debt = cons.get("net_borr", 0)
    market_price = shares_info.get("price", 0)

    # WACC 자동 추정
    wacc_est = _estimate_wacc_params(cons, shares_info, identity.market, identity)
    rf = wacc_est["rf"]
    erp = wacc_est["erp"]
    bu = wacc_est["bu"]
    tax = wacc_est["tax"]
    kd_pre = wacc_est["kd_pre"]
    de_ratio = wacc_est["de"]
    eq_w = wacc_est["eq_w"]

    # 파일명 생성
    safe_name = re.sub(r"[^\w\-]", "_", identity.name.lower().replace(" ", "_"))
    if identity.ticker:
        safe_name = identity.ticker.lower()
    yaml_filename = f"profiles/{safe_name}.yaml"
    yaml_path = str(_PROJECT_ROOT / yaml_filename)

    # consolidated YAML 블록
    cons_blocks = []
    for yr in years:
        d = financials[yr]
        cons_blocks.append(f"""  {yr}:
    revenue: {d.get('revenue', 0)}
    op: {d.get('op', 0)}
    net_income: {d.get('net_income', 0)}
    assets: {d.get('assets', 0)}
    liabilities: {d.get('liabilities', 0)}
    equity: {d.get('equity', 0)}
    dep: {d.get('dep', 0)}
    amort: {d.get('amort', 0)}
    gross_borr: {d.get('gross_borr', 0)}
    net_borr: {d.get('net_borr', 0)}
    de_ratio: {d.get('de_ratio', 0)}""")

    net_debt = cons.get("net_borr", 0)

    # 매크로 데이터 자동 수집
    from pipeline.macro_data import get_terminal_growth, get_diluted_shares
    from engine.growth import generate_growth_rates
    terminal_growth = get_terminal_growth(identity.market)

    # EBITDA 성장률 동적 생성 (최근 CAGR → 시장 수렴치로 선형 감쇠)
    growth_rates = generate_growth_rates(financials, market=identity.market)
    growth_rates_str = "[" + ", ".join(f"{r:.2f}" for r in growth_rates) + "]"
    # Note: tax rate는 _estimate_wacc_params()에서 클램핑 적용 완료

    # 희석주식수 (SBC/스톡옵션 반영) — DART 주식총수를 못 가져온 경우만
    if identity.ticker and shares_preferred == 0 and treasury_shares == 0:
        diluted = get_diluted_shares(identity.ticker, identity.market)
        if diluted and diluted > shares_total:
            shares_total = diluted
            shares_ordinary = diluted

    # 유통보통주식수 (per-share 계산 기준)
    shares_outstanding = shares_ordinary - treasury_shares
    if shares_outstanding <= 0:
        shares_outstanding = shares_ordinary or shares_total

    # 교차검증 멀티플 자동 계산 (수집된 재무 + 시장 데이터 기반)
    pe_multiple = 0.0
    ev_revenue_multiple = 0.0
    pbv_multiple = 0.0
    if market_price > 0 and shares_outstanding > 0:
        mcap = market_price * shares_outstanding / 1_000_000  # 백만원/$M 단위
        net_inc = cons.get("net_income", 0)
        revenue = cons.get("revenue", 0)
        if net_inc > 0:
            pe_multiple = round(mcap / net_inc, 1)
        if revenue > 0:
            ev = mcap + max(net_debt, 0)
            ev_revenue_multiple = round(ev / revenue, 1)
        if equity_bv > 0:
            pbv_multiple = round(mcap / equity_bv, 1)

    # 금융자회사 보유 가능성 경고
    fin_subsidiary_warn = ""
    if not is_us and de_ratio > 150:
        industry = getattr(identity, "industry", "") or ""
        warn_keywords = ["자동차", "건설", "지주", "종합상사", "금융"]
        if any(kw in identity.name or kw in industry for kw in warn_keywords):
            fin_subsidiary_warn = (
                "\n# ⚠ WARNING: D/E > 150% + 금융자회사 보유 가능 업종."
                "\n#   부문 분리 SOTP(Mixed Method) 검토 필요."
                "\n#   segments에 method: pbv, segment_net_debt 추가 고려."
            )

    content = f"""# {identity.name} — Auto-generated draft profile
# Source: {'SEC EDGAR' if is_us else 'DART'} | Generated by valuation-tool
# TODO: Add segment data, multiples, and scenario parameters{fin_subsidiary_warn}

company:
  name: "{identity.name}"
  legal_status: "{'상장' if is_us or identity.legal_status == '상장' else '비상장'}"
  market: "{identity.market}"
  currency: "{currency}"
  currency_unit: "{unit}"
  ticker: {f'"{identity.ticker}"' if identity.ticker else 'null'}
  cik: {f'"{identity.cik}"' if identity.cik else 'null'}
  corp_code: {f'"{identity.corp_code}"' if identity.corp_code else 'null'}
  shares_total: {shares_total}
  shares_ordinary: {shares_ordinary}
  shares_preferred: {shares_preferred}
  treasury_shares: {treasury_shares}
  analysis_date: "{date.today().isoformat()}"

# TODO: Define business segments (REQUIRED for SOTP)
segments:
  MAIN:
    name: "Main Business"
    multiple: 10.0   # TODO: Set appropriate EV/EBITDA multiple

# TODO: Add segment-level financials (revenue, op, assets per segment)
segment_data:
  {latest}:
    MAIN: {{revenue: {cons.get('revenue', 0)}, gross_profit: 0, op: {cons.get('op', 0)}, assets: {cons.get('assets', 0)}}}

consolidated:
{chr(10).join(cons_blocks)}

wacc_params:
  rf: {rf}
  erp: {erp}
  bu: {bu}
  de: {de_ratio}
  tax: {tax}
  kd_pre: {kd_pre}
  eq_w: {eq_w}

# TODO: Design scenarios appropriate for this company
scenarios:
  Base:
    name: "Base Case"
    prob: 50
    ipo: "N/A"
    irr: null
    dlom: 0
    cps_repay: 0
    rcps_repay: 0
    buyback: 0
    shares: {shares_outstanding}
    growth_adj_pct: 0
    terminal_growth_adj: 0
    desc: "Base case with consensus estimates"
  Bull:
    name: "Bull Case"
    prob: 25
    ipo: "N/A"
    irr: null
    dlom: 0
    cps_repay: 0
    rcps_repay: 0
    buyback: 0
    shares: {shares_outstanding}
    growth_adj_pct: 20
    terminal_growth_adj: 0.3
    desc: "Upside scenario"
  Bear:
    name: "Bear Case"
    prob: 25
    ipo: "N/A"
    irr: null
    dlom: {'20' if not is_us else '0'}
    cps_repay: 0
    rcps_repay: 0
    buyback: 0
    shares: {shares_outstanding}
    growth_adj_pct: -25
    terminal_growth_adj: -0.3
    desc: "Downside scenario"

dcf_params:
  ebitda_growth_rates: {growth_rates_str}
  tax_rate: {tax}
  capex_to_da: 1.10
  nwc_to_rev_delta: 0.05
  terminal_growth: {terminal_growth}

# 교차검증 멀티플 (Trading Multiple — 현재 시장가 기반 역산)
# Peer 기반 독립 멀티플로 교체 권장
pe_multiple: {pe_multiple}
ev_revenue_multiple: {ev_revenue_multiple}
pbv_multiple: {pbv_multiple}

cps_principal: 0
cps_years: 0
net_debt: {net_debt}
eco_frontier: 0
base_year: {latest}

peers: []
  # TODO: Add peer companies
  # - {{name: "Peer Co", segment_code: "MAIN", ev_ebitda: 10.0, notes: ""}}
"""
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(content)

    return yaml_filename


def auto_analyze(company_query: str, output_dir: str | None = None):
    """AI 기반 end-to-end 자동 분석.

    1. 데이터 수집 (auto_fetch)
    2. AI가 부문/멀티플/시나리오 설계
    3. YAML 프로필 보강
    4. 밸류에이션 실행 + Excel 출력
    """
    from valuation_runner import load_profile, run_valuation
    from output.console_report import print_report

    # Step 1: 데이터 수집
    fetch_result = auto_fetch(company_query)
    if not fetch_result or not fetch_result.get("yaml_path"):
        print("[ERROR] 데이터 수집 실패. --auto 중단.")
        return None

    yaml_path = str(_PROJECT_ROOT / fetch_result["yaml_path"])
    identity = fetch_result["identity"]
    financials = fetch_result["financials"]

    # Step 2: AI 분석
    print(f"\n{'='*60}")
    print(f"[AI 분석 시작] {identity.name}")
    print(f"{'='*60}")

    try:
        from ai.analyst import AIAnalyst
        analyst = AIAnalyst()
    except Exception as e:
        print(f"[WARN] AI 모듈 로드 실패 ({e}). Draft YAML로 진행합니다.")
        vi = load_profile(yaml_path)
        result = run_valuation(vi)
        print_report(vi, result)
        from output.excel_builder import export
        path = export(vi, result, output_dir)
        print(f"\n[Excel] 저장 완료: {path}")
        return result

    latest = max(financials.keys())
    cons = financials[latest]

    # 매출 구성 텍스트
    revenue_text = f"총 매출: {cons.get('revenue', 0):,}, 영업이익: {cons.get('op', 0):,}"

    # AI Step 2: 부문 분류
    print("[AI 2/6] 부문 분류 중...")
    try:
        seg_result = analyst.classify_segments(identity.name, revenue_text)
        segments = seg_result.get("segments", [])
        print(f"  → {len(segments)}개 부문 식별")
    except Exception as e:
        print(f"  [WARN] 부문 분류 실패: {e}")
        segments = []

    # AI Step 3: Peer/멀티플 추천
    peers_all = []
    multiples_ai = {}
    if segments:
        print("[AI 3/6] Peer 기업 추천 중...")
        for seg in segments:
            code = seg.get("code", "MAIN")
            name = seg.get("name", "Main")
            try:
                peer_result = analyst.recommend_peers(
                    identity.name, code, name,
                    seg.get("peer_group", ""),
                )
                for p in peer_result.get("peers", []):
                    peers_all.append({
                        "name": p["name"],
                        "segment_code": code,
                        "ev_ebitda": p.get("ev_ebitda", 10.0),
                        "notes": p.get("notes", ""),
                    })
                multiples_ai[code] = peer_result.get("recommended_multiple", 10.0)
                print(f"  → {code}: {peer_result.get('recommended_multiple', '?')}x "
                      f"({len(peer_result.get('peers', []))} peers)")
            except Exception as e:
                print(f"  [WARN] {code} Peer 추천 실패: {e}")
                multiples_ai[code] = 10.0

    # AI Step 4: WACC 추천
    print("[AI 4/6] WACC 추정 중...")
    equity = cons.get("equity", 0)
    liabilities = cons.get("liabilities", 0)
    de_ratio = round(liabilities / equity * 100, 1) if equity > 0 else 100.0
    try:
        wacc_result = analyst.suggest_wacc(identity.name, de_ratio, "")
        print(f"  → WACC ≈ {wacc_result.get('wacc_estimate', '?')}%")
    except Exception as e:
        print(f"  [WARN] WACC 추정 실패: {e}")
        wacc_result = {}

    # AI Step 5a: 뉴스 수집 → 핵심 이슈 요약
    print("[AI 5/6] 관련 뉴스 수집 중...")
    key_issues = ""
    try:
        from discovery.news_collector import NewsCollector
        from discovery.discovery_engine import summarize_key_issues
        collector = NewsCollector()
        news = collector.collect_for_company(identity.name, identity.market)
        if news:
            print(f"  → {len(news)}건 수집")
            key_issues = summarize_key_issues(news, identity.name, identity.market)
            if key_issues:
                print(f"  → 핵심 이슈 요약 완료")
        else:
            print(f"  → 관련 뉴스 없음 (범용 시나리오로 진행)")
    except Exception as e:
        print(f"  [WARN] 뉴스 수집 실패: {e}. 범용 시나리오로 진행합니다.")

    # AI Step 5b: 시나리오 설계 (뉴스 기반 key_issues + 멀티 드라이버)
    print("[AI 6/6] 시나리오 설계 중...")
    legal = "상장" if identity.market == "US" else "비상장"

    # 방법론 결정 → AI에게 전달하여 method-aware 드라이버 생성
    try:
        from engine.method_selector import suggest_method
        val_method = suggest_method(
            n_segments=len(segments) if segments else 1,
            legal_status=legal,
            industry=getattr(identity, "industry", "") or "",
        )
    except Exception:
        val_method = "dcf_primary"

    try:
        sc_result = analyst.design_scenarios(
            identity.name, legal, key_issues, valuation_method=val_method,
        )
        ai_scenarios = sc_result.get("scenarios", [])
        print(f"  → {len(ai_scenarios)}개 시나리오 (멀티 드라이버, {val_method})")
    except Exception as e:
        print(f"  [WARN] 시나리오 설계 실패: {e}")
        ai_scenarios = []

    # Step 3: YAML 보강
    print(f"\n[YAML 보강 중] {yaml_path}")
    with open(yaml_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # 부문 정보 업데이트
    if segments:
        raw["segments"] = {}
        seg_data_update = {}
        for seg in segments:
            code = seg.get("code", "MAIN")
            raw["segments"][code] = {
                "name": seg.get("name", code),
                "multiple": multiples_ai.get(code, 10.0),
            }
            share = seg.get("revenue_share_pct", 100.0 / len(segments)) / 100
            seg_data_update[code] = {
                "revenue": round(cons.get("revenue", 0) * share),
                "gross_profit": 0,
                "op": round(cons.get("op", 0) * share),
                "assets": round(cons.get("assets", 0) * share),
            }
        raw["segment_data"] = {latest: seg_data_update}

    # WACC 업데이트
    if wacc_result:
        for key in ["rf", "erp", "bu", "kd_pre", "tax"]:
            if key in wacc_result:
                raw["wacc_params"][key] = wacc_result[key]

    # 뉴스 핵심 이슈 저장 (감사 추적용)
    if key_issues:
        raw["news_key_issues"] = key_issues

    # 시나리오 업데이트 (멀티 드라이버 매핑)
    if ai_scenarios:
        # 유통보통주식수 (보통주 - 자사주) 기준
        _ord = raw["company"].get("shares_ordinary", raw["company"]["shares_total"])
        _trs = raw["company"].get("treasury_shares", 0)
        shares = _ord - _trs if _trs > 0 else _ord
        raw["scenarios"] = {}
        for sc in ai_scenarios:
            code = sc.get("code", "A")
            sc_dict = {
                "name": sc.get("name", f"Scenario {code}"),
                "prob": sc.get("prob", 33),
                "ipo": "N/A",
                "irr": None,
                "dlom": sc.get("dlom", 0),
                "cps_repay": 0,
                "rcps_repay": 0,
                "buyback": 0,
                "shares": shares,
                "desc": sc.get("description", ""),
                "probability_rationale": sc.get("probability_rationale", ""),
            }
            # AI가 생성한 정량적 드라이버 매핑
            drivers = sc.get("drivers", {})
            for field in (
                "growth_adj_pct", "terminal_growth_adj", "market_sentiment_pct",
                "wacc_adj", "ddm_growth", "ev_multiple", "rim_roe_adj", "nav_discount",
            ):
                if field in drivers:
                    val = drivers[field]
                    # ddm_growth/ev_multiple: 0은 "미설정"을 의미 → None으로 변환
                    if field in ("ddm_growth", "ev_multiple") and val == 0:
                        val = None
                    sc_dict[field] = val
            # 드라이버별 근거
            dr = sc.get("driver_rationale", {})
            if dr:
                sc_dict["driver_rationale"] = dr
            raw["scenarios"][code] = sc_dict

    # Peers 업데이트
    if peers_all:
        raw["peers"] = peers_all

    # MC 활성화
    raw["mc_enabled"] = True

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"  → YAML 저장 완료")

    # Step 4: 밸류에이션 실행
    print(f"\n{'='*60}")
    print(f"[밸류에이션 실행]")
    print(f"{'='*60}")

    vi = load_profile(yaml_path)
    result = run_valuation(vi)

    # 상장사 괴리율 자동 비교
    from cli import _fetch_and_compare_market_price
    result = _fetch_and_compare_market_price(vi, result)

    print_report(vi, result)

    from output.excel_builder import export
    path = export(vi, result, output_dir)
    print(f"\n[Excel] 저장 완료: {path}")

    return result
