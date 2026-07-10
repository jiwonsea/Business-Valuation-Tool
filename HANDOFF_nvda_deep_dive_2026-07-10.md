# HANDOFF — NVDA 심층 재밸류에이션 평가 요청 (CODEX)

세션: 2026-07-10 (Cowork). NVIDIA 3중 앵커 재밸류에이션 수행. **코드 변경 없음 — 프로파일(YAML)·문서만 변경.**
분석 본문: `valuation-results/2026-07-10-nvda-deep-dive/nvda_deep_dive_2026-07-10.md`
검증 데이터: 같은 폴더 `_verified_data.md` (SEC 원문 추출) · 실행 로그 `_run_{ttm,fy27e,fy26_baseline}.txt`

## 변경 파일

| 파일 | 변경 | 근거 |
|---|---|---|
| `profiles/nvda_ttm.yaml` | BS를 10-Q 원문으로 교정(equity 195,474·net_borr **−41,865**), NI 정상화(159,613→**143,224** 비GAAP TTM), rf 3.2→**4.56**·erp 5.5→4.6·tax 17.0, dep 3,586, 시나리오 축 재구성, dcf_params 갱신, trading 배수(pe 34.5/ev_rev 19.3/pbv 25.2), `market_price: 202.34` 추가 | Q1 FY27 10-Q, 10Y UST 4.56% |
| `profiles/nvda_fy27e.yaml` | FY27E를 컨센서스 앵커로 재구축(매출 391,300·op 256,300·NI 214,000), 포워드 시나리오 멀티플(22/17.5/12), dcf growth [.18,.13,.09,.06,.04] | 컨센서스 $391.3B·EPS $9.34 |
| `profiles/nvda.yaml` | `market_price` 194→202.34만 갱신 (FY26 확정실적 앵커 보존 — 역산 기준선) | 2026-07-09 종가 |

백업: `/tmp/bak_{ttm,fy27e,nvda}.yaml` (세션 한정). 스냅샷은 valuation-results 폴더에 동결.

## 결과 요약

| 앵커 | 확률가중 | vs $202.34 | MC mean (P5–P95) | 품질 |
|---|---:|---:|---|---:|
| FY26 확정 | $145 | −28.3% | — (내재 WACC 5.97% · 성장배수 4.94x) | 72 B |
| TTM | $175 | −13.5% | 118 (86–160) | 89 A |
| FY27E | $207 | +2.3% | 189 (137–257) | 100 A |

## 평가 요청 항목 (우선순위순)

(a) **net_debt 정의 변경의 엔진 영향**: `net_borr/net_debt = −41,865` (현금+시장성 채무증권−차입).
기존 관행은 현금만 차감(435). 음수 net_debt가 equity bridge·DDM/RIM add-back·distress 판정·MC에서
의도대로 전파되는지 점검. 특히 `de_ratio: 4.3`과 wacc `de: 0.2`의 정합성.

(b) **NI 정상화의 일관성**: consolidated `net_income`에 비GAAP TTM(143,224)을 넣어 P/E 교차검증을 정상화했으나,
같은 값이 ROE·quality·backtest snapshot에도 흘러간다. GAAP/정상화 이원 필드가 필요한지, 아니면 현 방식(주석 문서화)으로
충분한지 판단 요청.

(c) **시나리오 멀티플 캘리브레이션**: TTM Base SEG1 24x는 peer median 14.6x 대비 +64% 프리미엄(성장률 차이 근거),
Bull 30x는 현 시장 TTM 배수(29.4x)와 밀착. 스프레드 1.875x ≤ 2x 준수. 근거 타당성과 `_METHOD_DRIVERS` 레인지 대비 검토.

(d) **trading 배수 교차검증의 순환성**: pe/ev_revenue/pbv를 시장가 역산으로 넣으면 교차검증 3종이 정의상 주가를
재현하고, quality '시장가격 정합 25/25'·수렴도가 부풀 수 있음. [T]/[P] 구분이 quality 계산에 반영되는지 확인하고,
아니라면 peer-anchored 독립 배수로 되돌릴지 결정 요청. **본 분석의 최대 방법론 이슈.**

(e) **MC mean(118) ≪ 확률가중(175) 괴리 (TTM)**: 시나리오별 MC mean(220/171/109)의 확률가중은 ~165인데
통합 MC mean은 118. TV resampling 또는 멀티플 샘플링 분포의 하방 치우침 여부를 `engine/monte_carlo.py`에서 규명
(rules/monte-carlo.md 참조). FY27E도 동일 패턴(189 vs 207).

(f) **FY27E 추정 필드의 크로스밸리데이션 민감도**: equity 250,000·assets 320,000은 추정치. P/BV 크로스밸류가
이 값에 선형 의존 — 추정 오차 ±10%가 결론을 흔들지 않는지 확인.

(g) **DCF 1년차 성장 0.45 (TTM 프로파일)**: TTM 앵커에 FY27E 이행 성장을 얹은 값. TTM에 이미 Q1 FY27이 포함되어
있어 이중반영 소지 점검(순수하게는 FY27E/TTM − 1 ≈ +57% 연간, 4개 분기 중 1개 반영분 감안 시 ~45%로 산정).

## 재현

```bash
python cli.py --profile profiles/nvda_ttm.yaml          # $175, quality 89
python cli.py --profile profiles/nvda_fy27e.yaml        # $207, quality 100
python cli.py --profile profiles/nvda.yaml              # $145, reverse DCF 발동
```

pytest 미실행(엔진 코드 무변경). 기지 이슈: `TestScenarioDriverRoundTrip` 2건은 profiles/ 드리프트로 deselect 관례
(CLAUDE.md Testing 절).

## 후속 (호스트)

- CODEX 평가 반영 후 결과 확정 → 기업분석보고서(md+PDF, SK에코플랜트 형식) 작성 예정.
- 차기 분기부터 부문 보고 개편(Hyperscale/ACIE)에 따른 SEG 매핑 재설계 백로그 등록.
- 커밋 대상: `profiles/nvda*.yaml`, `valuation-results/2026-07-10-nvda-deep-dive/`, 본 파일.

---

## 개정 1 (2026-07-10 오후) — CODEX 평가 반영 완료

CODEX 판정: "FY27E $207 참고 가능한 중심값 / TTM $175 시나리오 가치 / quality 89·100은 신뢰도 지표 사용 불가((d) 순환성 확인)".

**적용 조치.**
1. **(d) 엔진 패치** `engine/quality.py`: `_TRADING_MULT_METHODS` + `_trading_anchored_methods()`(시장가 ±5% 밀착 감지,
   console_report [T] 태그와 동일 기준) 신설 → quality 수렴도에서 trading 배수 제외. trading 제외 시 DCF-vs-시장배수
   자동제외는 스킵(참조 클러스터 소멸). 폴백 계층: 독립방법(옵셔널리티 제외 완화) ≥2개면 trading만 제외 유지, 미만이면
   전체 폴백+경고. `market_price` 없는 프로파일은 완전 무변경(가드). 단위테스트 `tests/test_quality_trading_exclusion.py`
   8건 통과, `tests/test_engine.py` 279 pass(실패 3건은 httpx 미설치 환경 이슈, 코드 무관).
2. **(a) 자본구조 정합화**: ttm `de: 4.3`/`eq_w: 95.9`, fy27e `de: 3.4`/`eq_w: 96.7` (gross debt/equity 기준).
   WACC 11.23→11.16%(TTM). 헤드라인 불변.
3. **(e) 문서 교정**: 통합 MC를 "Base-input MC"로 재명명, 시나리오 확률혼합과 구분 명시(TTM 119≈기본 SOTP 119).
4. **(c) Base 24x 유지 결정(사용자)**: 선도기업 프리미엄 — 성장조정 배수 0.42 vs 피어 0.86, GM 75%, CUDA 락인/네트워크
   효과, 현 시장배수 대비 −18% 내장 압축. 계량 브릿지를 분석 문서 §3에 수록. Bear 16x가 프리미엄 회수 시나리오.

**패치 후 확정 수치** (가치·괴리 불변): FY26 $145 / 78(B) · TTM $175 / **95(A)** (수렴도 20/25, SOTP·DCF 독립 2종) ·
FY27E $207 / **89(A)** (수렴도 14/25). 위 "결과 요약" 표의 quality 열은 요청 시점 값(순환성 포함)으로 폐기.

**잔여 백로그(코드).** ① `normalized_net_income` Optional 필드 이원화((b), P/E·상대가치 진단만 우선 사용).
② 시나리오 mixture MC 분포 구현((e)). ③ TTM DCF stub-period → FY27E 명시 예측연도 방식((g)).
④ CrossValidationItem `source` 필드 정식화(현재는 ±5% 휴리스틱).

**커밋 주의(CODEX 지적).** `profiles/nvda.yaml` 등은 이번 세션 이전의 미커밋 변경이 누적된 상태 — 커밋 시
`git add -p`로 범위 분리할 것. 이번 세션 변경분: `engine/quality.py`, `tests/test_quality_trading_exclusion.py`,
`profiles/nvda_ttm.yaml`, `profiles/nvda_fy27e.yaml`, `profiles/nvda.yaml`(market_price),
`valuation-results/2026-07-10-nvda-deep-dive/*`, 본 파일.

**세션 중 기록: mount 동기화 이슈 재발 (2건).** ① `engine/quality.py` Windows-side Edit 후 mount에서 714줄
중간절단 관측 → `/tmp` 백업에서 재구성·`cp` 재동기화(md5 일치·ast·pytest 확인). ② 본 파일·분석 md가 Edit 직후
bash CRLF 변환과 레이스로 부분 클로버링 → bash-side 원자적 재작성으로 복구. **이 레포에서 md/py 대형 편집은
bash-side 전체 재작성 경로를 기본으로 할 것.**

