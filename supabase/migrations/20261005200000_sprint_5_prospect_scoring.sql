-- ==============================================================================
-- Prospectra — Sprint 5: Prospect Scoring & Prioritization
-- Migration: 20261005200000_sprint_5_prospect_scoring.sql
-- ==============================================================================

-- 1. Add scoring columns to public.prospects
ALTER TABLE public.prospects
    ADD COLUMN IF NOT EXISTS priority_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    ADD COLUMN IF NOT EXISTS score_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS scoring_version VARCHAR(50) NOT NULL DEFAULT 'v1.0',
    ADD COLUMN IF NOT EXISTS scored_at TIMESTAMPTZ;

-- 2. Add check constraint for priority_score bounds [0.0, 1.0]
ALTER TABLE public.prospects
    DROP CONSTRAINT IF EXISTS chk_prospect_priority_score;

ALTER TABLE public.prospects
    ADD CONSTRAINT chk_prospect_priority_score
    CHECK (priority_score >= 0.0 AND priority_score <= 1.0);

-- 3. Composite performance index for deterministic workspace ranking queries
CREATE INDEX IF NOT EXISTS idx_prospects_workspace_ranking
    ON public.prospects (workspace_id, priority_score DESC, qualification_status, created_at DESC, id ASC);
