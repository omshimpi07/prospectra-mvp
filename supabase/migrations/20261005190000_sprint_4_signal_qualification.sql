-- ==============================================================================
-- Prospectra — Sprint 4: Deep Signal Qualification & Business Intelligence
-- Migration: 20261005190000_sprint_4_signal_qualification.sql
-- ==============================================================================

-- 1. Create prospects table
CREATE TABLE IF NOT EXISTS public.prospects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    icp_id UUID NOT NULL REFERENCES public.icps(id) ON DELETE RESTRICT,
    search_result_id UUID REFERENCES public.search_results(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    canonical_category VARCHAR(100) NOT NULL,
    city VARCHAR(100),
    website_url TEXT,
    phone VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'QUEUED',
    qualification_status VARCHAR(50) NOT NULL DEFAULT 'UNQUALIFIED',
    fit_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    qualification_reason TEXT,
    raw_signals JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_code VARCHAR(100),
    error_message TEXT,
    queued_at TIMESTAMPTZ DEFAULT now(),
    started_at TIMESTAMPTZ,
    qualified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_prospect_status CHECK (
        status IN ('QUEUED', 'RESEARCHING', 'COMPLETED', 'FAILED')
    ),
    CONSTRAINT chk_qualification_status CHECK (
        qualification_status IN ('UNQUALIFIED', 'QUALIFIED', 'DISQUALIFIED', 'REVIEW_NEEDED')
    )
);

-- Partial unique constraint: cannot promote the same search result twice in the same workspace
CREATE UNIQUE INDEX IF NOT EXISTS uq_prospect_workspace_search_result
    ON public.prospects(workspace_id, search_result_id)
    WHERE search_result_id IS NOT NULL;

-- 2. Create qualification_evidence table
CREATE TABLE IF NOT EXISTS public.qualification_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    prospect_id UUID NOT NULL REFERENCES public.prospects(id) ON DELETE CASCADE,
    signal_key VARCHAR(100) NOT NULL,
    signal_value JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    source_url TEXT,
    snippet VARCHAR(500),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Indexes for query and worker performance
CREATE INDEX IF NOT EXISTS idx_prospects_workspace_status ON public.prospects(workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_prospects_workspace_qual ON public.prospects(workspace_id, qualification_status);
CREATE INDEX IF NOT EXISTS idx_prospects_worker_claim ON public.prospects(status, queued_at) WHERE status = 'QUEUED';
CREATE INDEX IF NOT EXISTS idx_prospects_icp_id ON public.prospects(icp_id);
CREATE INDEX IF NOT EXISTS idx_evidence_prospect_id ON public.qualification_evidence(prospect_id);
CREATE INDEX IF NOT EXISTS idx_evidence_workspace_id ON public.qualification_evidence(workspace_id);

-- 4. Enable Row Level Security (RLS)
ALTER TABLE public.prospects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qualification_evidence ENABLE ROW LEVEL SECURITY;

-- 5. RLS Policies: Workspace-scoped via public.is_workspace_member
-- Physical DELETE is denied permanently (USING false) to preserve qualification and audit trail.
CREATE POLICY "prospects_select_member" ON public.prospects
    FOR SELECT TO authenticated
    USING (public.is_workspace_member(workspace_id, auth.uid()));

CREATE POLICY "prospects_insert_member" ON public.prospects
    FOR INSERT TO authenticated
    WITH CHECK (public.is_workspace_member(workspace_id, auth.uid()));

CREATE POLICY "prospects_update_member" ON public.prospects
    FOR UPDATE TO authenticated
    USING (public.is_workspace_member(workspace_id, auth.uid()));

CREATE POLICY "prospects_delete_deny" ON public.prospects
    FOR DELETE TO authenticated
    USING (false);

CREATE POLICY "evidence_select_member" ON public.qualification_evidence
    FOR SELECT TO authenticated
    USING (public.is_workspace_member(workspace_id, auth.uid()));

CREATE POLICY "evidence_insert_member" ON public.qualification_evidence
    FOR INSERT TO authenticated
    WITH CHECK (public.is_workspace_member(workspace_id, auth.uid()));

CREATE POLICY "evidence_delete_deny" ON public.qualification_evidence
    FOR DELETE TO authenticated
    USING (false);

-- 6. Trigger for updated_at
DROP TRIGGER IF EXISTS tr_prospects_updated_at ON public.prospects;
CREATE TRIGGER tr_prospects_updated_at
    BEFORE UPDATE ON public.prospects
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();
