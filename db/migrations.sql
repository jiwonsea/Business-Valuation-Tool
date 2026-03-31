-- ============================================================
-- Supabase 테이블 생성 (SQL Editor에서 실행)
-- ============================================================

-- 1. valuations — 밸류에이션 입력 + 결과
CREATE TABLE IF NOT EXISTS valuations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    -- 검색/필터용 핵심 컬럼
    company_name TEXT NOT NULL,
    ticker TEXT,
    market TEXT NOT NULL DEFAULT 'KR',
    legal_status TEXT NOT NULL DEFAULT '비상장',
    valuation_method TEXT NOT NULL,
    analysis_date DATE NOT NULL,
    base_year INT NOT NULL,

    -- 빠른 조회용 결과 요약
    total_ev BIGINT,
    weighted_value BIGINT,
    wacc_pct DOUBLE PRECISION,

    -- 시장가격 비교
    market_price DOUBLE PRECISION,
    gap_ratio DOUBLE PRECISION,

    -- 전체 데이터 (JSONB)
    input_data JSONB NOT NULL,
    result_data JSONB NOT NULL,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 2. ai_analyses — AI 분석 단계별 결과
CREATE TABLE IF NOT EXISTS ai_analyses (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    valuation_id UUID REFERENCES valuations(id) ON DELETE CASCADE,
    company_name TEXT NOT NULL,
    step TEXT NOT NULL,          -- identify, classify, peers, wacc, scenarios, research_note
    result_data JSONB NOT NULL,
    model TEXT DEFAULT 'claude-sonnet-4',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 3. profiles — YAML 프로필 저장
CREATE TABLE IF NOT EXISTS profiles (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    company_name TEXT NOT NULL,
    file_name TEXT,
    profile_yaml TEXT NOT NULL,
    profile_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_valuations_company ON valuations(company_name);
CREATE INDEX IF NOT EXISTS idx_valuations_ticker ON valuations(ticker);
CREATE INDEX IF NOT EXISTS idx_valuations_date ON valuations(analysis_date DESC);
CREATE INDEX IF NOT EXISTS idx_valuations_created_at ON valuations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_valuations_market ON valuations(market);
CREATE INDEX IF NOT EXISTS idx_ai_analyses_valuation ON ai_analyses(valuation_id);
CREATE INDEX IF NOT EXISTS idx_ai_analyses_company ON ai_analyses(company_name);
CREATE INDEX IF NOT EXISTS idx_ai_analyses_created_at ON ai_analyses(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_profiles_company ON profiles(company_name);
CREATE INDEX IF NOT EXISTS idx_profiles_created_at ON profiles(created_at DESC);

-- updated_at 자동 갱신 트리거
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER valuations_updated_at
    BEFORE UPDATE ON valuations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE OR REPLACE TRIGGER profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- Upsert용 UNIQUE 제약조건
-- ============================================================

-- 같은 기업 + 같은 분석일 → 최신 결과로 갱신
CREATE UNIQUE INDEX IF NOT EXISTS uq_valuations_company_date
    ON valuations(company_name, analysis_date);

-- 같은 기업 + 같은 파일명 → 최신 프로필로 갱신
CREATE UNIQUE INDEX IF NOT EXISTS uq_profiles_company_file
    ON profiles(company_name, file_name);

-- ============================================================
-- 4. discovery_runs — 주간 자동 분석 실행 기록
-- ============================================================

CREATE TABLE IF NOT EXISTS discovery_runs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    run_date TIMESTAMPTZ DEFAULT now(),
    markets TEXT[] NOT NULL,
    news_count INT DEFAULT 0,
    companies_discovered JSONB DEFAULT '[]',
    companies_analyzed TEXT[] DEFAULT '{}',
    valuation_ids TEXT[] DEFAULT '{}',
    errors JSONB DEFAULT '[]',
    status TEXT DEFAULT 'running',       -- running | completed | completed_with_errors | failed
    duration_seconds DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_discovery_runs_date
    ON discovery_runs(run_date DESC);
CREATE INDEX IF NOT EXISTS idx_discovery_runs_created_at
    ON discovery_runs(created_at DESC);

-- ============================================================
-- Row Level Security (RLS)
-- ============================================================
-- 모든 테이블에 RLS 활성화.
-- service_role 키는 RLS를 자동 우회하므로 백엔드 접근에 영향 없음.
-- anon/public 접근은 차단됨.

ALTER TABLE valuations ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE discovery_runs ENABLE ROW LEVEL SECURITY;

-- service_role 전용 정책 (anon 키 사용 시에도 백엔드 동작 보장)
CREATE POLICY "service_role_all_valuations" ON valuations
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_ai_analyses" ON ai_analyses
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_profiles" ON profiles
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_discovery_runs" ON discovery_runs
    FOR ALL TO service_role USING (true) WITH CHECK (true);
