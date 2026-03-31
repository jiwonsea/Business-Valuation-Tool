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

    # D/E ratio — 상장사는 시장가 기준, 비상장은 장부가
    equity_bv = cons.get("equity", 0)
    liabilities = cons.get("liabilities", 0)
    net_debt = cons.get("net_borr", 0)
    market_price = shares_info.get("price", 0)

    if market_price > 0 and shares_total > 0:
        # 시장가 기반 D/E (상장사)
        market_cap = market_price * shares_total
        if is_us:
            market_cap /= 1_000_000  # $M 단위로 변환
        de_ratio = round(net_debt / market_cap * 100, 1) if market_cap > 0 and net_debt > 0 else 0.0
        eq_w = round(market_cap / (market_cap + max(net_debt, 0)) * 100, 1) if market_cap > 0 else 50.0
    else:
        # 비상장: 장부가 기반
        de_ratio = round(liabilities / equity_bv * 100, 1) if equity_bv > 0 else 100.0
        eq_w = round(100 / (1 + de_ratio / 100), 1)

    # WACC defaults by market
    if is_us:
        rf, erp, bu, tax, kd_pre = 4.25, 5.50, 1.0, 21.0, 5.50
    else:
        rf, erp, bu, tax, kd_pre = 3.50, 7.00, 0.75, 22.0, 5.50

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
    from pipeline.macro_data import get_terminal_growth, calc_effective_tax_rate, get_diluted_shares
    terminal_growth = get_terminal_growth(identity.market)
    effective_tax = calc_effective_tax_rate(financials)
    if effective_tax is not None:
        tax = effective_tax

    # 희석주식수 (SBC/스톡옵션 반영)
    if identity.ticker:
        diluted = get_diluted_shares(identity.ticker, identity.market)
        if diluted and diluted > shares_total:
            shares_total = diluted
            shares_ordinary = diluted

    # 교차검증 멀티플 자동 계산 (수집된 재무 + 시장 데이터 기반)
    pe_multiple = 0.0
    ev_revenue_multiple = 0.0
    pbv_multiple = 0.0
    if market_price > 0 and shares_total > 0:
        mcap = market_price * shares_total
        if is_us:
            mcap /= 1_000_000  # $M 단위
        net_inc = cons.get("net_income", 0)
        revenue = cons.get("revenue", 0)
        if net_inc > 0:
            pe_multiple = round(mcap / net_inc, 1)
        if revenue > 0:
            ev = mcap + max(net_debt, 0)
            ev_revenue_multiple = round(ev / revenue, 1)
        if equity_bv > 0:
            pbv_multiple = round(mcap / equity_bv, 1)

    content = f"""# {identity.name} — Auto-generated draft profile
# Source: {'SEC EDGAR' if is_us else 'DART'} | Generated by valuation-tool
# TODO: Add segment data, multiples, and scenario parameters

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
  shares_preferred: 0
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
    shares: {shares_total}
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
    shares: {shares_total}
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
    shares: {shares_total}
    desc: "Downside scenario"

dcf_params:
  ebitda_growth_rates: [0.10, 0.08, 0.06, 0.05, 0.04]
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

    # AI Step 5b: 시나리오 설계 (뉴스 기반 key_issues 전달)
    print("[AI 6/6] 시나리오 설계 중...")
    legal = "상장" if identity.market == "US" else "비상장"
    try:
        sc_result = analyst.design_scenarios(identity.name, legal, key_issues)
        ai_scenarios = sc_result.get("scenarios", [])
        print(f"  → {len(ai_scenarios)}개 시나리오")
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

    # 시나리오 업데이트
    if ai_scenarios:
        shares = raw["company"]["shares_total"]
        raw["scenarios"] = {}
        for sc in ai_scenarios:
            code = sc.get("code", "A")
            raw["scenarios"][code] = {
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
