# Plan: Weekly Email — 10-Company Target & News/Excel in Email

## Context

주간 파이프라인이 10개 목표 기업 중 4-5개만 분석 완료하고, 이메일에 뉴스 링크/엑셀 파일이 누락되고 있음.

**조사 결과:**
- 문제 1: `scheduler/weekly_run.py:411`의 `calls_per_company=6` 와 공유 일별 카운터(`.cache/api_usage.json`)로 인해, 인터랙티브 CLI 사용으로 당일 쿼터가 소진되면 주간 실행 시 남은 예산이 20-30콜 → 20//6=3-4개 기업만 처리. 주간 실행 전용 예산이 없음.
- 문제 2: `scheduler/delivery.py:build_gmail_html()`이 `top_news[].url`(이미 `_weekly_summary.json`에 저장됨)과 Excel `download_url`(Supabase 서명 URL, 이미 생성됨)을 이메일 HTML에 포함하지 않음.

---

## Fix 1: 10개 기업 보장 — 주간 전용 LLM 예산

**파일:** `scheduler/weekly_run.py` (lines ~395-419)

**원인:** `llm_budget = estimate["remaining_quota"].get("openrouter/anthropic")`는 하루 동안 대화형 사용으로 소진된 후의 잔여치를 읽음. 주간 작업 전용 예산 할당 없음.

**수정 방법:**

```python
# 현재 코드 (weekly_run.py ~L407-412)
calls_per_company = 6
max_affordable = max(llm_budget // calls_per_company, 1)

# 변경 후
WEEKLY_LLM_BUDGET = int(os.getenv("WEEKLY_LLM_BUDGET", "80"))  # 10개 × 6 + 20 여유
calls_per_company = 6
effective_budget = max(llm_budget, WEEKLY_LLM_BUDGET)  # 잔여치와 전용 예산 중 큰 값 사용
max_affordable = max(effective_budget // calls_per_company, 1)
```

`WEEKLY_LLM_BUDGET=80` 환경변수(기본값 80 → 최대 13개 기업)로 대화형 사용과 무관하게 주간 작업 실행 보장.

**추가 최적화:** `calls_per_company`를 실제 캐시 적중률에 맞게 조정
- `news_summary`는 7일 TTL 캐시 적용 → 재실행 시 실제 소비 5콜
- `profile_gen`이 항상 필요한지 확인, 불필요시 4-5로 낮춤

---

## Fix 2: SaveTicker.com으로 US 뉴스 교체 (디스커버리 LLM 1콜 절약)

**사전 조사 결과:**
- `https://api.saveticker.com/api/news/list` — 페이지 기반 JSON API (인증 불필요)
- `tag_names` 배열에 `$TSLA`, `$NVDA` 등 티커 직접 포함
- `extra.source_url`에 원본 기사 URL 포함
- **단점: US 전용, KR 주식 미지원** — Naver 파이프라인은 그대로 유지

**구현:**

1. **`discovery/saveticker_collector.py` 신규 파일**
   ```python
   BASE_URL = "https://api.saveticker.com/api/news/list"

   def fetch_saveticker_news(max_items=100) -> list[dict]:
       """페이지네이션으로 최근 뉴스 수집, tag_names에서 US 티커 추출"""
       # GET ?page=1&page_size=50 호출
       # tag_names에서 "$" 시작 항목 추출 → ticker
       # extra.source_url → url 필드로 매핑
       # view_count 기준 정렬

   def get_top_us_tickers(n=15) -> list[dict]:
       """mention count 기준 상위 N 티커 반환 (LLM 불필요)"""
   ```

2. **`discovery/discovery_engine.py` 수정**
   - US 마켓: Google RSS → SaveTicker 교체
   - 티커가 직접 오므로 US LLM 디스커버리 콜(1콜) 생략 가능
   - KR 마켓: Naver + LLM 기존 방식 유지

3. **`pipeline/api_guard.py` 수정**
   - `saveticker` 프로바이더 등록 (일일 한도 100콜, rate_limit_per_sec=2)

---

## Fix 3: 이메일에 뉴스 링크 + 엑셀 URL 포함

**파일:** `scheduler/delivery.py` (함수 `build_gmail_html()`, ~lines 235-344)

**현재:** 기업 카드에 `reason` 텍스트만 있음. `top_news` URL과 `download_url`이 이미 `_weekly_summary.json`에 저장되어 있으나 이메일 HTML에 미포함.

**수정:**

각 기업 카드에 두 블록 추가:

```html
<!-- 뉴스 링크 블록 (top_news[].url 존재 시) -->
<div style="margin-top:8px;">
  <strong>📰 관련 기사</strong>
  <ul style="margin:4px 0; padding-left:16px;">
    <li><a href="{url1}">{title1}</a></li>
    <li><a href="{url2}">{title2}</a></li>
  </ul>
</div>

<!-- 엑셀 다운로드 (download_url 존재 시) -->
<div style="margin-top:6px;">
  <a href="{download_url}" style="...button style...">📥 엑셀 다운로드</a>
</div>
```

**데이터 흐름 확인:**
- `summary["scored_companies"][i]["top_news"]` → `[{"title": str, "url": str}]` ✓ 이미 존재
- `summary["valuations"][i]["download_url"]` → Supabase 서명 URL ✓ 이미 생성됨
- `build_gmail_html()`에 두 필드를 기업 ID로 조인하는 로직 추가 필요

---

## 수정 파일 목록

| 파일 | 변경 내용 |
|------|----------|
| `scheduler/weekly_run.py` | `WEEKLY_LLM_BUDGET` 상수 추가, `effective_budget` 계산 수정 (L407-412) |
| `scheduler/delivery.py` | `build_gmail_html()` — 뉴스 링크 블록 + 엑셀 다운로드 버튼 추가 |
| `discovery/saveticker_collector.py` | 신규 파일 — SaveTicker JSON API 수집기 |
| `discovery/discovery_engine.py` | US 마켓: SaveTicker로 교체 + LLM 콜 제거 |
| `pipeline/api_guard.py` | `saveticker` 프로바이더 등록 |

---

## 구현 우선순위

**P0 (반드시):**
1. `weekly_run.py` — `WEEKLY_LLM_BUDGET` 전용 예산 (1-line fix, 즉시 효과)
2. `delivery.py` — 뉴스 링크 + 엑셀 URL 이메일 포함

**P1 (권장):**
3. `saveticker_collector.py` + `discovery_engine.py` 교체 (US 뉴스 품질↑, LLM 1콜 절약)
4. `api_guard.py` — saveticker 프로바이더 등록

---

## 검증 방법

```bash
# Fix 1: 쿼터 계산 확인
python -c "
import sys; sys.path.insert(0, '.')
from pipeline.api_guard import ApiGuard
g = ApiGuard()
est = g.estimate_remaining()
print(est)
"

# Fix 2: SaveTicker 수집기 단위 테스트
python -m discovery.saveticker_collector  # __main__ 블록에서 샘플 출력 확인

# Fix 3: 이메일 HTML 미리보기
python -c "
from scheduler.delivery import build_gmail_html
# mock summary with top_news + download_url 포함
print(build_gmail_html(mock_summary))
" > /tmp/preview.html

# 통합 테스트
python cli.py --weekly --dry-run --max-companies 2  # discovery까지 확인
```
