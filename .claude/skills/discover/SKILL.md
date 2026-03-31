# Discovery Skill

## Description
TRIGGER when: user mentions "뉴스 분석", "기업 추천", "시장 동향", "어떤 기업을 분석할까", "news analysis", "company recommendation", "--discover".
DO NOT TRIGGER when: specific company valuation (→ /valuation), profile creation (→ /profile), result comparison (→ /compare).

## Overview
Collects recent 1-month KR/US market news and uses AI to analyze them, proposing target companies and scenarios.
AI proposes scenarios and probability allocation, but user makes final decisions.

## Workflow
1. News collection: KR=Naver News API, US=Google News RSS
2. AI analysis: Claude API for issue classification + company recommendation
3. Scenario proposal: per-company scenarios + probability allocation draft
4. User review/modification → YAML profile creation
5. Run valuation

## File References
- [references/news_sources.md](references/news_sources.md) — API call methods and limitations per news source

## Gotchas
- Naver API requires `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` env vars
- Google News RSS requires no API key
- AI suggestions are for reference only. Never auto-execute without user confirmation
