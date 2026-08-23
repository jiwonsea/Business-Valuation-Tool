# SK Hynix Thesis (Working Draft)

> 본 문서는 본인이 직접 작성합니다. Codex 자동 생성 금지.
> 가정 수치 (`profiles/sk_hynix.yaml`) 와 1:1 대응.

## 1. 핵심 thesis

**한 줄**: HBM3E 12H ramp가 2026Q1~Q3 동안 DRAM 마진 사이클을 끌어올리고, NAND는 2026 후반 회복.

(여기에 1-2 문단 — 본인 작성)

## 2. 시나리오 확률 (25/50/25) 근거

### Bear 25%

(여기에 본인이 정한 근거 — 예: HBM 경쟁사 진입·중국 메모리 수요 둔화·미중 무역 마찰)

### Base 50%

(여기에 본인이 정한 근거 — 컨센 수준, AI capex 사이클 지속)

### Bull 25%

(여기에 본인이 정한 근거 — HBM ASP 상회, 선단공정 점유율 확대)

## 3. 컨센서스와 차별화 포인트

Consensus gap 표 (`reports/sk_hynix_*.md`) 를 참조하면서 각 period 별로 1-2 문장:

| Period | Gap % | 본인의 view |
|--------|-------|-------------|
| 2026Q1 | (채움) | (예: 컨센이 HBM share 35% 가정, 본 모델은 38% — 12H 12-layer 양산 일정 반영) |
| 2026Q2 | (채움) | (채움) |
| FY26   | (채움) | (채움) |
| FY27   | (채움) | (채움) |

## 4. 취약점 (면접 drill-down 대비)

- **HBM share 분기별 추정**: 회사 가이던스가 분기별로 명시되지 않음. TrendForce·Counterpoint 추정치를 본인 판단으로 보간 → 답변: "회사 가이던스 + 업계 트래커 + 분기 컨퍼런스콜 코멘트 종합".
- **시나리오 확률 주관성**: SK에코플랜트 패턴과 동일하게 본인 분포 가정. 답변: "확률 자체보다 시나리오 구조 분리가 목적 — sensitivity로 어느 가정이 결과를 좌우하는지 파악".
- **마진 모델 = cost-per-bit operating leverage** (구 `gp_cyclicality` 대체): `GP_margin_s = 1 − cost_per_bit_s / ASP_s`. 마진을 ASP에 연동해 가격→마진 증폭을 구조적으로 포착. 답변: "상품 ASP 사이클 자체는 예측하지 않음 — ASP는 입력(시장 트래커/내 view), 모델은 ASP를 EPS로 번역".
- **HBM/DDR 세그먼트 마진 split = under-identified**: 회사가 세그먼트 총이익률 비공시. 앵커(2024Q1)의 실측 aggregate GP(DART 38.6%)에 일치시키고, HBM 마진은 애널리스트 추정, DDR은 잔차. 답변: "관측 가능한 aggregate에 앵커를 고정하고 비관측 split은 보수적 추정 — 한계를 인정, sensitivity로 영향 확인".
- **historical_drivers ASP = 시장 트래커 추정**: TrendForce 분기 가격 변동의 근사. 답변: "독립 시장가격 인덱스 사용(회사 매출 아님) — 백테스트 비순환 보장".
- **컨센 출처 단일 (Yahoo)**: `.KS` 컨센은 신뢰도 제한(함의 순이익률 비현실). 답변: "한국 broker 컨센(FnGuide·네이버)은 P1 backlog — 현재는 신뢰불가 경고 표시 후 매출 gap 위주".

## 5. 입사 후 6개월 적용 시나리오

면접 8장 답변 "기존 커버리지 모델 가정 원문 검증·업데이트" 와 직접 연결:

1. 분기 실적 발표 직후 본 모델에 actual 입력 → 차이가 큰 라인 식별
2. IR 컨퍼런스콜 원문 (한국어·일본어) 읽고 분기별 가정 수치 갱신
3. 시나리오 확률 재설정 (예: HBM 가이던스 상회 시 Bull 25% → 35%)
4. 컨센 gap 변화 추적 → "내 view가 어디서 차별화되는지" 1-pager 작성
