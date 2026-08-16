# REVIEW — NVIDIA application plan (Codex)

## §2 seam 확인

확인됨 — `net_profit × 1e6 / eps_diluted` 재계산 시 `2019Q3–2020Q1 ≈ 0.62B`, `2020Q2–2023Q1 ≈ 2.49–2.54B`, `2023Q2 이후 ≈ 24.4–25.0B`로 동일한 두 seam이 재현되며, 실제 split 시행일이 아닌 데이터 조립 경계에서 기준이 바뀐 혼합-basis 시계열이다.

## §4 질문별 답변

1. **NVDA-1 schema**

   `split_history: [{date, ratio}]`를 `GenericProfile`에 명시하고 정규화 계층에서 적용하는 방식을 권장한다. `extra="forbid"` 및 명시적 가정 원칙에 맞고, 조정값만 YAML에 넣는 것보다 감사 가능성이 높다. 다만 canonical actual은 고정 `weighted_avg_diluted=24.49B`로 과거 EPS를 다시 계산하면 안 된다. 각 분기의 `WeightedAverageNumberOfDilutedSharesOutstanding`를 수집해 오늘 기준으로 split-adjust한 뒤 `eps_diluted = net_profit × unit_scale / adjusted_diluted_shares`로 파생해야 한다. 원본 EPS와 accession은 provenance로 남긴다.

   SEC companyfacts를 단순히 “as-filed라서 미조정”이라고 규정하는 것은 부정확하다. 동일 기간에 최초 as-filed fact와 후속 공시의 소급 비교치가 함께 존재한다. 예를 들어 2020-10-25 종료 분기 diluted EPS는 최초 10-Q의 `2.12`와 4:1 split 반영 후속 10-Q의 `0.53`이 모두 있고, 2024-04-28 종료 분기는 최초 `5.98`과 10:1 반영 후속 비교치 `0.60`이 함께 있다. 따라서 “first/last fact” 선택만으로 전 기간을 현재 기준으로 통일할 수 없으며, accession·period·split history를 함께 사용해야 한다.

2. **`pipeline/edgar_fetcher.py` 캐시와 HTTP 구조**

   CIK별 companyfacts 전체 blob을 원본 캐시로 저장하는 방식을 권장한다. 요청 한 번으로 모든 concept와 후속 비교치를 보존하므로 오프라인 재현과 accession 감사에 유리하며, concept slice는 필요하면 파생 캐시로 생성하면 된다. DART와 SEC는 인증·응답 구조·rate 특성이 달라 fetcher 본문을 공유할 이유는 없다. User-Agent, timeout, 제한된 retry/backoff, atomic cache write 정도의 작은 HTTP helper만 실제 중복이 확인될 때 공유한다.

   추출기는 `start/end/fy/fp/form/filed/accn/frame`을 보존하고, 같은 standalone quarter를 구성하는 revenue·NI·COGS·shares가 가능한 한 같은 accession 기준인지 검증해야 한다. YTD fact로 Q2/Q3/Q4를 차감할 때도 서로 다른 공시 vintage를 섞지 않아야 한다.

3. **NVDA-2와 `engine/skill_metrics.py` 재사용**

   재사용 가능하다. `backtest_generic` row의 `actual_rev/model_rev/rw_rev` 및 EPS 필드는 `SkillRow`에 직접 변환되며, 현재 의존 방향상 memory-path import cycle도 생기지 않는다. 기존 MAPE/bias는 호환성을 위해 유지하고 `compute_skill` 결과를 추가하는 최소 변경이 적절하다.

   다만 metrics 연결 전에 actual label을 다시 만들어야 한다. 현재 프로필은 일부 accession의 실제 종료연도와 `quarter_label`이 맞지 않고, actuals가 `Q1–Q3` 위주로 이어지며 **Q4가 전부 빠져 있다**. 정렬된 인접 row를 직전 분기로 간주하는 현재 backtest는 Q3 다음 Q1을 1-step으로 취급하므로 RW, seasonal slot, MAPE/MASE/Theil 모두 왜곡된다. Q4 standalone actual을 annual minus 9M으로 복원하고, 연속 분기 검증을 추가한 뒤 metrics를 계산해야 한다.

4. **NVDA consensus vintage와 quality gate**

   `to_consensus_record`를 as-is로 재사용하면 안 된다. 현재 `0q/+1q`를 `as_of`의 캘린더 분기에 붙이고 `0y/+1y`를 `as_of.year`에 붙이므로 1월 결산 NVIDIA fiscal quarter/year와 silent mis-join이 발생한다. `.KS`가 박힌 quality message와 `implied net margin >60%` 규칙도 issuer-neutral하지 않으며, NVIDIA의 높은 실제 순이익률에서는 오탐 위험이 있다.

   raw Yahoo 파싱은 재사용하되, profile의 fiscal calendar에 따라 period end·fiscal label·model label을 명시적으로 매핑하는 별도 normalization을 두고 테스트해야 한다. `quality_notes` 계약은 유지하되 메시지와 threshold는 통화/시장 suffix가 아니라 회사의 실제 margin 범위와 데이터 단위 정합성에 기반해야 한다.

5. **NVDA-1/2/3 우선순위와 범위**

   우선순위 `NVDA-1 ≫ NVDA-2 > NVDA-3`에 동의한다. 다만 NVDA-1은 (a) companyfacts accession/standalone-quarter 정규화, (b) Q4 복원 및 fiscal/calendar label 계약, (c) historical diluted shares split normalization과 derived EPS 순으로 쪼개는 것이 안전하다. 이 세 항목이 통과하기 전의 backtest 개선 수치는 유효하지 않다.

   NVDA-2에서는 skill metrics와 fiscal consensus alignment를 함께 진행하되 attribution은 후순위로 둔다. Generic 모델은 GP를 예측하지 않으므로 기존 5-lever 함수를 lever-count parameter로 복잡하게 만들기보다 `revenue / OP margin / OP→NI conversion / shares`의 별도 4-lever generic attribution이 모델 의미에 맞다. NVDA-3는 포트폴리오 가시성은 높지만 잘못된 지표를 시각적으로 강화할 위험이 있으므로 데이터·metrics 계약이 안정될 때까지 연기해도 방어 가능하다.

6. **누락된 정확도 위험과 fixed forward shares의 정합성**

   Forward window에서 현재 희석주식수 `24.49B`를 고정해 EPS를 계산하는 것은 명시적 forecast assumption으로는 일관된다. 그러나 historical backtest actual에도 같은 고정값을 적용하는 것은 split만 고칠 뿐 실제 dilution·buyback 변화를 제거하므로 부적절하다. 과거 actual은 분기별 split-adjusted diluted weighted-average shares를 사용해야 한다.

   추가 정확도 위험은 다음 두 가지가 가장 크다. 첫째, companyfacts에는 as-filed와 후속 공시 비교치가 공존하므로 period별 “최신 fact”가 언제나 오늘 기준 완전 조정치라는 보장이 없다. 오래된 분기는 최근 10-Q의 비교기간에 포함되지 않아 2024년 10:1 조정치가 존재하지 않을 수 있다. 둘째, actuals의 Q4 전부 누락과 잘못된 연도 라벨 때문에 현재 backtest가 비연속 분기를 1-step으로 연결한다. 따라서 split normalization만으로 EPS bias가 single digits로 내려갈 것이라는 acceptance criterion은 보장할 수 없다. 먼저 공식 standalone quarters, 연속 라벨, 분기별 shares를 확정한 뒤 bias 변화를 측정해야 한다.
