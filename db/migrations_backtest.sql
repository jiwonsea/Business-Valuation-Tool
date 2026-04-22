-- ============================================================
-- Backtest / Calibration 테이블 (SQL Editor에서 실행)
-- ============================================================

-- 1. prediction_snapshots — Append-only 예측 스냅샷 (밸류에이션 실행 시점에 캡처)
CREATE TABLE IF NOT EXISTS prediction_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    valuation_id UUID REFERENCES valuations(id) ON DELETE CASCADE,

    company_name TEXT NOT NULL,
    ticker TEXT NOT NULL,
    market TEXT NOT NULL,
    currency TEXT NOT NULL,              -- "KRW" | "USD"
    unit_multiplier INT NOT NULL,        -- 1_000_000 (백만원) etc.
    legal_status TEXT NOT NULL,          -- "상장" | "비상장"
    analysis_date DATE NOT NULL,

    -- 예측값 (display unit 기준)
    predicted_weighted_value BIGINT NOT NULL,
    predicted_gap_ratio DOUBLE PRECISION,
    price_at_prediction DOUBLE PRECISION,  -- T0 시장가 (밸류에이션 시점)
    wacc_pct DOUBLE PRECISION,

    -- 시나리오별 예측 (JSON)
    -- {code: {name, prob, pre_dlom, post_dlom, growth_adj_pct, wacc_adj, ...}}
    scenario_values JSONB NOT NULL DEFAULT '{}',

    -- 메타데이터
    model_version TEXT DEFAULT '',
    code_version TEXT DEFAULT '',

    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshot_valuation
    ON prediction_snapshots(valuation_id);

-- 2. backtest_outcomes — 백테스트 결과 (주가 수집 후 저장)
CREATE TABLE IF NOT EXISTS backtest_outcomes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    snapshot_id UUID REFERENCES prediction_snapshots(id) ON DELETE CASCADE UNIQUE,

    ticker TEXT NOT NULL,
    market TEXT NOT NULL,
    analysis_date DATE NOT NULL,

    -- 실제 주가 (원화/달러 원본 그대로)
    price_t0 DOUBLE PRECISION,
    price_t3m DOUBLE PRECISION,
    price_t6m DOUBLE PRECISION,
    price_t12m DOUBLE PRECISION,
    date_t3m DATE,
    date_t6m DATE,
    date_t12m DATE,

    -- 주가 수집 상태
    price_fetched_at TIMESTAMPTZ,        -- NULL = 아직 미수집
    fetch_errors JSONB DEFAULT '{}',     -- {horizon: "error message"}

    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_backtest_ticker
    ON backtest_outcomes(ticker);

-- ============================================================
-- Schema updates (run if tables already exist)
-- ============================================================

-- Add market_signals_version to prediction_snapshots (added in Phase 4)
ALTER TABLE prediction_snapshots
    ADD COLUMN IF NOT EXISTS market_signals_version INT DEFAULT 0;

-- Add primary_method to prediction_snapshots (added in Phase 5)
ALTER TABLE prediction_snapshots
    ADD COLUMN IF NOT EXISTS primary_method TEXT DEFAULT '';

-- Add valuation_bucket to prediction_snapshots (Phase 1 bucketed backtest)
ALTER TABLE prediction_snapshots
    ADD COLUMN IF NOT EXISTS valuation_bucket TEXT DEFAULT 'plain_operating';

-- Add unique constraints for upsert support
CREATE UNIQUE INDEX IF NOT EXISTS uq_valuations_company_date
    ON valuations(company_name, analysis_date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_profiles_company_file
    ON profiles(company_name, file_name);

-- ============================================================
-- Row Level Security (RLS)
-- ============================================================
-- Pattern matches migrations.sql: enable RLS, grant full access to service_role.
-- service_role bypasses RLS automatically; anon/public access is blocked.

ALTER TABLE prediction_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_outcomes    ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_prediction_snapshots" ON prediction_snapshots
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_backtest_outcomes" ON backtest_outcomes
    FOR ALL TO service_role USING (true) WITH CHECK (true);
