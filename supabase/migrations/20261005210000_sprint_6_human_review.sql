-- ==============================================================================
-- Prospectra — Sprint 6: Prospect Workspace & Human Review Foundation
-- Migration: 20261005210000_sprint_6_human_review.sql
-- ==============================================================================

-- 1. Add human review columns to public.prospects
ALTER TABLE public.prospects
    ADD COLUMN IF NOT EXISTS review_status VARCHAR(50) NOT NULL DEFAULT 'UNREVIEWED',
    ADD COLUMN IF NOT EXISTS rejection_reason VARCHAR(100) NULL,
    ADD COLUMN IF NOT EXISTS seller_note TEXT NULL,
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS reviewed_by UUID NULL REFERENCES public.profiles(id) ON DELETE SET NULL;

-- 2. Add check constraint for review_status
ALTER TABLE public.prospects
    DROP CONSTRAINT IF EXISTS chk_prospect_review_status;

ALTER TABLE public.prospects
    ADD CONSTRAINT chk_prospect_review_status
    CHECK (review_status IN ('UNREVIEWED', 'APPROVED', 'REJECTED'));

-- 3. Composite performance index for workspace review queue filtering and sorting
CREATE INDEX IF NOT EXISTS idx_prospects_workspace_review
    ON public.prospects (workspace_id, review_status, priority_score DESC NULLS LAST);
