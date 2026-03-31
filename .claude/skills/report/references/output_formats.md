# 출력 형식 상세

## 1. 리서치 노트 (마크다운)

`orchestrator.format_summary(vi, result)` → `str`

### 포함 섹션 (방법론에 따라 자동 분기)
- 기업명, 분석일, 방법론
- WACC (βL, Ke, Kd)
- DDM 결과 (금융업종)
- 상대가치평가 (Multiples Primary)
- NAV (지주사/리츠)
- SOTP EV (다부문)
- DCF EV + SOTP 대비 괴리
- 시나리오별 주당 가치 + 확률가중 결론
- 시장가격 비교 + 괴리율
- 교차검증 결과

### AI 리서치 노트
```python
from ai.analyst import AIAnalyst
analyst = AIAnalyst()
note = analyst.research_note(vi, result)  # Claude API 호출
```
- 투자 의견, 리스크 요인, 촉매 등 정성적 분석 포함
- AI 분석 결과는 DB에 자동 저장 (step="research_note")

## 2. Excel 7시트

`output.excel_builder.export(vi, result, output_dir)` → `str` (파일 경로)

| 시트 | 내용 | 사용 방법론 |
|------|------|-----------|
| 가정 | 기업 정보, WACC, Peers | 공통 |
| D&A 배분 | 자산 비중 → D&A 배분 → 부문별 EBITDA | SOTP |
| SOTP | 부문별 EV/EBITDA → 합산 EV | SOTP |
| 시나리오 | 시나리오별 주당 가치 + 확률가중 | 공통 |
| DCF | FCFF 추정 + 터미널밸류 | DCF |
| 민감도 | 멀티플/WACC/성장률 격자 | 공통 |
| 교차검증 | EV/Revenue, P/E, P/BV 등 | 공통 |

## 3. 콘솔 리포트

`output.console_report.print_report(vi, result)` → stdout

- 터미널 60자 폭 포맷
- 디버깅/빠른 확인용
