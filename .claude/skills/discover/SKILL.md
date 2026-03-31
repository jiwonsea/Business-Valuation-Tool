# Discovery Skill

## Description
TRIGGER when: 사용자가 "뉴스 분석", "기업 추천", "시장 동향", "어떤 기업을 분석할까", "--discover" 언급 시.
DO NOT TRIGGER when: 특정 기업 밸류에이션 실행 (→ /valuation), 프로필 생성 (→ /profile), 결과 비교 (→ /compare).

## Overview
최근 1개월 KR/US 시장 뉴스를 수집하고 AI로 분석하여, 분석 대상 기업과 시나리오를 제안한다.
시나리오와 확률 배분은 AI가 제안하되, 최종 결정은 사용자가 한다.

## Workflow
1. 뉴스 수집: KR=네이버 뉴스 API, US=Google News RSS
2. AI 분석: Claude API로 이슈 분류 + 기업 추천
3. 시나리오 제안: 기업별 시나리오 + 확률 배분 초안
4. 사용자 확인/수정 후 YAML 프로필 생성
5. 밸류에이션 실행

## File References
- [references/news_sources.md](references/news_sources.md) — 뉴스 소스별 API 호출 방법과 제한사항

## Gotchas
- 네이버 API는 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 환경변수 필요
- Google News RSS는 API Key 불필요
- AI 제안은 참고용. 사용자 확인 없이 자동 실행하지 말 것
