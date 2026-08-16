# Methodology

蹂?臾몄꽌??`earnings-forecast-engine` ???쒕씪?대쾭 遺꾪빐 ?쇰━쨌?쒕굹由ъ삤 ?ㅺ퀎쨌寃利??덉감瑜??뺣━?⑸땲?? 肄붾뱶? 1:1 ??묓븯誘濡? 紐⑤뱢 ?섏젙 ??蹂?臾몄꽌瑜??숈떆 ?낅뜲?댄듃?⑸땲??

## 짠1. ?ъ슜 ?⑥쐞쨌?쒓린

- ?듯솕: KRW (湲곕낯). USD 醫낅ぉ? profile YAML??紐낆떆.
- 蹂닿퀬 ?⑥쐞: KRW ??뼲 ??(KRW_billion) ??紐⑤뱺 P&L ?쇱씤.
- 遺꾧린 ?쇰꺼: `2026Q1` ?뺤떇. fiscal year ?쇰꺼: `FY26`.
- ?좊ː援ш컙: 90% ?먮뒗 25-75% (?쒕굹由ъ삤 諛대뱶).

## 짠2. ?곗씠???낅젰

| ?낅젰 | 異쒖쿂 | 紐⑤뱢 |
|------|------|------|
| 遺꾧린 ?ㅼ쟻 (留ㅼ텧쨌OP쨌NI쨌capex) | DART OpenAPI | `pipeline/dart_fetcher.py` |
| 諛쒗뻾二쇱떇??(蹂댄넻쨌?곗꽑) | DART ?ъ뾽蹂닿퀬??| `pipeline/dart_fetcher.py` |
| Yahoo 而⑥꽱?쒖뒪 (EPS쨌留ㅼ텧) | yfinance | `pipeline/yahoo_fetcher.py` |
| 遺꾧린蹂?媛??(bit growth쨌ASP쨌margin쨌?몄쑉) | 蹂몄씤 ?섎룞 ?낅젰 | `profiles/{company}.yaml` |

?섎룞 媛?뺤? 紐⑤몢 YAML??紐낆떆. **肄붾뱶 ???섎뱶肄붾뵫 湲덉?**.

## 짠3. ?쒓퀎??踰좎씠?ㅻ씪??
媛?遺꾧린 forecast ?쒖젏 T?먯꽌 ?ㅼ쓬 4遺꾧린 ?됯퇏(T-4 .. T-1)??踰좎씠?ㅻ씪?몄쑝濡??ъ슜:
- ASP baseline (DRAM blended, NAND blended)
- Margin baseline (GP, OP, NP)
- capex baseline (D&A ?ъ씠??異붿젙??

backtest?먯꽌???숈씪 洹쒖튃?쇰줈 look-ahead bias ?뚰뵾.

## 짠4. 留ㅼ텧 遺꾪빐

```
Revenue_total = Revenue_DRAM + Revenue_NAND + Revenue_Other
```

### 짠4-1. DRAM

```
Revenue_DRAM[t] = Bit_volume_DRAM[t] 횞 ASP_blended_DRAM[t]

Bit_volume_DRAM[t]    = Bit_volume_DRAM[t-1] 횞 (1 + bit_growth_qoq[t])
ASP_blended_DRAM[t]   = HBM_share[t] 횞 ASP_HBM[t] + (1 - HBM_share[t]) 횞 ASP_DDR[t]

ASP_HBM[t]  = ASP_HBM[t-4] 횞 (1 + hbm_asp_yoy / 4)    # ?⑥닚?? YoY瑜?遺꾧린蹂?遺꾪븷
ASP_DDR[t]  = ASP_DDR[t-1] 횞 (1 + ddr_asp_qoq[t])
```

`HBM_share` ? `bit_growth_qoq` ??YAML 遺꾧린蹂?紐낆떆. HBM ASP??YoY ??媛믪쑝濡?simplification ??Codex媛 P1?먯꽌 遺꾧린蹂?遺꾨━ 媛??

### 짠4-2. NAND

```
Revenue_NAND[t] = Bit_volume_NAND[t] 횞 ASP_NAND[t]

Bit_volume_NAND[t] = Bit_volume_NAND[t-1] 횞 (1 + nand_bit_growth_qoq[t])
ASP_NAND[t]        = ASP_NAND[t-1] 횞 (1 + nand_asp_qoq[t])
```

### 짠4-3. Other

CIS쨌?뚯슫?쒕━쨌湲고? ?⑹궛. ?⑥닚 ?깆옣瑜??곸슜:
```
Revenue_Other[t] = Revenue_Other[t-1] 횞 (1 + other_revenue_growth_qoq[t])
```


Defect 13 sync for backtest revenue:
- Forward revenue keeps scenario ASP assumptions because future realized prices do not exist.
- Backtest revenue uses assumed bit growth from the base scenario but realized ASP and HBM share from `historical_drivers[target_quarter]`.
- This is non-circular: actual company revenue and realized company bit volume are never inserted into the projection formula.

## 짠5. 留덉쭊 紐⑤뜽

### 짠5-1. GP margin (cost-per-bit ASP leverage)

```
asp_factor_s[t]  = product(1 + asp_change_s[k]) from anchor a+1 through t
cost_factor_s[t] = (1 - cost_decline_qoq_s) ** periods_since_anchor
GP_margin_s[t]   = 1 - (1 - GM_s) * cost_factor_s[t] / asp_factor_s[t]

R_HBM[t] = HBM_share[t] * R_DRAM[t]
R_DDR[t] = (1 - HBM_share[t]) * R_DRAM[t]
GP_KRW[t] = R_HBM[t] * GP_margin_HBM[t]
          + R_DDR[t] * GP_margin_DDR[t]
          + R_NAND[t] * GP_margin_NAND[t]
          + R_other[t] * GM_other
GP_margin[t] = GP_KRW[t] / R_total[t]
```

Defect 12 sync:
- `GM_HBM`, `GM_DDR`, `GM_NAND`, `GM_other`, and `cost_decline_qoq_*` live in top-level `anchor_margins`, not in scenario `margins`.
- The anchor is the first `historical_drivers` quarter, currently 2024Q1. Forward and backtest both accumulate realized historical ASP factors from that quarter through the seed or target quarter.
- Forward margin ASP factors carry over from anchor through the seed quarter, currently 2025Q4, then diverge by scenario ASP assumptions from 2026Q1.
- Scenario `margins` contain only `sga_pct_of_revenue` and `rnd_pct_of_revenue`; scenario margin divergence comes through ASP and HBM share.

- `GM_HBM`, `GM_DDR`, `GM_NAND`, `GM_other`??YAML `assumptions.*.margins`???듭빱 遺꾧린 ?멸렇癒쇳듃 珥앹씠?듬쪧?대떎. ?곸닔 留덉쭊???꾨땲??ASP/cost 紐⑤뜽???쒖옉?먯씠??
- Forward `asp_factor`??`engine.segment_revenue`媛 怨꾩궛?섎뒗 `asp_hbm`, `asp_ddr`, `asp_nand` ?몃뜳?ㅻ떎. ?듭빱(seed) = 1.0.
- Backtest `asp_factor`??top-level `historical_drivers[quarter].*_asp_qoq` ?쒖옣 price-index 蹂?숈쓣 諛깊뀒?ㅽ듃 ?덈룄 ?쒖옉 ?듭빱遺???꾩쟻?쒕떎. ?뚯궗 actual 留덉쭊/留ㅼ텧??driver濡??ｌ? ?딅뒗??
- `cost_decline_qoq_hbm`, `cost_decline_qoq_ddr`, `cost_decline_qoq_nand`??bit???먭???遺꾧린 ?섎씫瑜좎씠?? 媛寃⑷낵 臾닿???怨듭젙 migration ?④낵濡??붾떎.
- `GM_other`??ASP driver媛 ?녿뒗 湲고? 留ㅼ텧???듭빱 珥앹씠?듬쪧濡??좎??쒕떎.
- ?섎떒 GP floor???녿떎. ASP媛 cost蹂대떎 ?쏀븯硫??뚯닔 GP margin???덉슜?쒕떎. ?곷떒 cap 90%留?sanity guard濡??붾떎.

### 짠5-2. OP margin

```
OP_margin[t] = GP_margin[t] - sga_pct - rnd_pct
```

- `sga_pct`, `rnd_pct` ??YAML ?쒕굹由ъ삤蹂? 留ㅼ텧 ?鍮?鍮꾩쑉, 遺꾧린蹂??숈씪.
- R&D??capex ?ъ씠?닿낵 5Y lag ?곕룞???댁긽?곸씠??MVP??stable.

### 짠5-3. NP margin

```
NI[t] = OP[t] 횞 (1 - effective_tax_rate) + Revenue[t] 횞 net_interest_pct
NP_margin[t] = NI[t] / Revenue[t]
```

- `effective_tax_rate`, `net_interest_pct` 紐⑤몢 YAML ?쒕굹由ъ삤蹂?

## 짠6. EPS

```
EPS_basic[t]   = NI[t] / weighted_avg_basic_shares
EPS_diluted[t] = NI[t] / weighted_avg_diluted_shares
```

?먯궗二?留ㅼ엯쨌?곗꽑二?蹂?숈? MVP?먯꽌 stable. 遺꾧린蹂?蹂?숈? P1.

## 짠7. ?쒕굹由ъ삤 ?몃━

3-case 援ъ“: Bear (25%) / Base (50%) / Bull (25%) ???뺣쪧 ??= 1 (Pydantic validator 媛뺤젣).

```
Weighted_metric[t] = p_bear 횞 bear[t] + p_base 횞 base[t] + p_bull 횞 bull[t]
```

媛?case???숈씪??quarter set?쇰줈 ?뺣젹?쇱빞 ??(Codex: ?쇰꺼 mismatch ??ValueError).

?뺣쪧 ?ㅼ젙 洹쇨굅??[sk_hynix_thesis.md](sk_hynix_thesis.md) ??蹂몄씤??吏곸젒 湲곕줉.

## 짠8. Backtest

吏곸쟾 N遺꾧린 (湲곕낯 8) ?????

1. 媛?遺꾧린 T留덈떎 T-4..T-1 ?곗씠?곕쭔 ?ъ슜??踰좎씠?ㅻ씪?맞룹떆??援ъ꽦 (look-ahead bias ?뚰뵾).
2. ?숈씪??forward 硫붿냼?쒕? retroactive ?곸슜 ??projected T.

Defect 13 backtest rule:
- For each target quarter, construct a one-quarter revenue assumption where bit growth remains the methodology/base assumption.
- Override only `hbm_share`, `hbm_asp_qoq`, `ddr_asp_qoq`, and `nand_asp_qoq` from `historical_drivers[target_quarter]`.
- The same realized ASP driver then feeds the margin ASP factor, keeping revenue and margin internally consistent.

3. ?ㅼ젣 T? 鍮꾧탳:
   - `revenue_error_pct = (model - actual) / actual`
   - `direction_match = sign(model_qoq) == sign(actual_qoq)`
4. 吏묎퀎:
   - `revenue_mape = mean(|revenue_error_pct|)`
   - `eps_mape   = mean(|eps_error_pct|)`
   - `hit_ratio  = mean(direction_match)`
   - `bias_revenue = mean(revenue_error_pct)`   # 遺???좎?, 泥닿퀎??over/under ?뺤씤

## 짠9. Consensus Gap

媛?forecast period (遺꾧린쨌?곌컙) 蹂꾨줈:
```
gap_abs = model_value - consensus_value
gap_pct = gap_abs / consensus_value
direction = "above" if gap_pct > 0.02 else "below" if gap_pct < -0.02 else "in_line"
```

consensus ?꾨씫 ??`direction="n_a"`, `gap_*=None`.

`interpretation` ?꾨뱶??**?붿쭊?먯꽌 ?먮룞 梨꾩슦吏 ?딆쓬** ??蹂몄씤??1-2臾몄옣 thesis ?묒꽦.

## 짠10. Valuation Bridge

```
eps_delta_pct        = (model_weighted_FY1_EPS - consensus_FY1_EPS) / consensus_FY1_EPS
fair_value_delta_pct = fair_value_elasticity 횞 eps_delta_pct
```

`fair_value_elasticity` ??YAML profile??紐낆떆 (湲곕낯 1.2). ??踰?BVT濡?誘쇨컧??遺꾩꽍???뚮┛ ??醫낅ぉ蹂?elasticity瑜??뺥븳?ㅻ뒗 媛??

## 짠11. 寃利?湲곗?

| Check | ?듦낵 湲곗? |
|-------|-----------|
| 留ㅼ텧 backtest MAPE | < 10% |
| EPS backtest MAPE | < 25% |
| Direction hit ratio | > 60% |
| Bias revenue | |媛? < 5% (泥닿퀎??怨쇰?/怨쇱냼 異붿젙 ?뚰뵾) |
| Consensus gap range | 理쒖냼 1媛?period?먯꽌 |gap_pct| > 5% (李⑤퀎?붾맂 view ?쒓렇?? |

誘몃떖 ??媛???섏튂 ?ш?????YAML ?섏젙 ???ъ떎??
## §12. 컨센서스 시그널 레이어 (Phase B)

> **STATUS: DORMANT (2026-07-31).** 코드는 온전하나 **활성 프로파일 0개** — `signal_layer` 섹션을 가진 프로파일이 `4ebeb7c`(2026-07-10) 이후 없어 `--signal-backtest`/`--call-brief`는 진입 즉시 `return 2`. 삭제가 의도적 은퇴였는지 롤포워드 중 부수 유실이었는지는 미판정. 재활성화는 프로파일 복원 + 실제 deck/DART fixture + 추출 완전성 계약을 **한 작업**으로 묶어 진행한다. 근거: `HANDOFF_CODEX_doc_ingest_2026-07-31.md`.

공시·IR 텍스트를 구조화 신호로 바꿔 (a) forward 콜 사전 브리핑과 (b) 신호의 주가반응 예측력 backtest를 산출한다.
공식·검증 상세는 `HANDOFF_phase_b.md`와 코드(`engine/signal_*`)에 1:1로 유지한다.

### §12-1. 신호 추출
- 입력: IR 실적 deck(pymupdf 텍스트) + DART MD&A(공개뷰어, 키 불요). LLM = Claude Haiku 4.5, temperature 0 + 캐시.
- 출력 `ExtractedSignal`: 토픽 강조(salience·polarity), 가이던스 톤(up/flat/down), surprise 후보. 해석 필드 없음.
- 검증은 결정론(`engine/signal_extractor.py`): enum·범위·dedup·정렬. LLM/IO는 `ai/`에 격리.

### §12-2. CAR event study (backtest 타깃)
- 라벨 = 시장조정 누적초과수익률. `r_t = close_t/close_{t-1} − 1`, `AR_t = r_t(000660.KS) − r_t(^KS11)`, `CAR[T0→T+k] = Σ_{i=1..k} AR_{T0+i}`.
- T0 = yfinance `earnings_dates` 발표일 이상 첫 거래일. 1차 k=1d, 부 k=5d. 섹터(`229200.KS`) 조정은 robustness.
- 지표: directional hit ratio, IC(Spearman rank corr), calibration.
- **비순환**: 신호는 텍스트, CAR은 가격 — 독립. 실현 재무 미투입.
- **look-ahead 회피**: 각 T0 신호는 그 시점 공개 텍스트(IR deck=콜 당일)만. DART MD&A(T0+2~4주)는 같은 분기 CAR에 미사용, forward 브리핑 전용.

### §12-3. 콜 사전 브리핑 (forward)
- 최신 MD&A 신호 + 라이브 컨센 분산(low/high/numberOfAnalysts, `eps_revisions`) → 주목 토픽·예상 Q&A·분산 플래그·리비전 방향 예측.
- yfinance `.KS` 컨센 신뢰불가 경고(결함 6)를 항상 노출. `interpretation`은 빈 채 — 사용자 작성.

### §12-4. 정직성
- 표본 8~12로 작아 통계적 유의를 주장하지 않는다. 면접 방어용 **정성 신호 + 방법론 규율** 증빙으로 프레이밍한다.
