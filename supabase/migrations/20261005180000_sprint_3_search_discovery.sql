-- Migration: 20261005180000_sprint_3_search_discovery.sql
-- Description: Create searches and search_results tables, indexes, and RLS policies

-- 1. SEARCHES TABLE
CREATE TABLE IF NOT EXISTS public.searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    icp_id UUID NOT NULL REFERENCES public.icps(id) ON DELETE RESTRICT,
    created_by UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    status VARCHAR(50) NOT NULL DEFAULT 'CREATED',
    idempotency_key VARCHAR(255) NULL,
    specification JSONB NOT NULL,
    total_candidates INTEGER NOT NULL DEFAULT 0,
    new_candidates INTEGER NOT NULL DEFAULT 0,
    error_code VARCHAR(100) NULL,
    error_message TEXT NULL,
    queued_at TIMESTAMPTZ NULL,
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_search_status CHECK (
        status IN ('CREATED', 'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED')
    ),
    CONSTRAINT uq_workspace_idempotency UNIQUE (workspace_id, idempotency_key)
);

-- Indexes for searches
CREATE INDEX IF NOT EXISTS idx_searches_workspace_id ON public.searches(workspace_id);
CREATE INDEX IF NOT EXISTS idx_searches_icp_id ON public.searches(icp_id);
CREATE INDEX IF NOT EXISTS idx_searches_status ON public.searches(workspace_id, status);

-- Trigger for searches updated_at
DROP TRIGGER IF EXISTS trg_searches_updated_at ON public.searches;
CREATE TRIGGER trg_searches_updated_at
    BEFORE UPDATE ON public.searches
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- RLS for searches
ALTER TABLE public.searches ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Workspace members can view searches" ON public.searches;
CREATE POLICY "Workspace members can view searches"
    ON public.searches FOR SELECT
    USING (public.is_workspace_member(workspace_id, auth.uid()));

DROP POLICY IF EXISTS "Workspace members can insert searches" ON public.searches;
CREATE POLICY "Workspace members can insert searches"
    ON public.searches FOR INSERT
    WITH CHECK (
        public.is_workspace_member(workspace_id, auth.uid())
        AND auth.uid() = created_by
    );

DROP POLICY IF EXISTS "Workspace members can update searches" ON public.searches;
CREATE POLICY "Workspace members can update searches"
    ON public.searches FOR UPDATE
    USING (public.is_workspace_member(workspace_id, auth.uid()))
    WITH CHECK (public.is_workspace_member(workspace_id, auth.uid()));

DROP POLICY IF EXISTS "Disallow physical delete on searches" ON public.searches;
CREATE POLICY "Disallow physical delete on searches"
    ON public.searches FOR DELETE
    USING (false);

-- 2. SEARCH RESULTS TABLE
CREATE TABLE IF NOT EXISTS public.search_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_id UUID NOT NULL REFERENCES public.searches(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    external_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL DEFAULT 'overture',
    name VARCHAR(255) NOT NULL,
    canonical_category VARCHAR(100) NOT NULL,
    raw_category VARCHAR(100) NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    address TEXT NULL,
    city VARCHAR(100) NULL,
    postal_code VARCHAR(50) NULL,
    phone VARCHAR(100) NULL,
    website TEXT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    raw_metadata JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_search_external_id UNIQUE (search_id, external_id)
);

-- Indexes for search_results
CREATE INDEX IF NOT EXISTS idx_search_results_search_id ON public.search_results(search_id);
CREATE INDEX IF NOT EXISTS idx_search_results_workspace_id ON public.search_results(workspace_id);
CREATE INDEX IF NOT EXISTS idx_search_results_category ON public.search_results(workspace_id, canonical_category);

-- RLS for search_results
ALTER TABLE public.search_results ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Workspace members can view search results" ON public.search_results;
CREATE POLICY "Workspace members can view search results"
    ON public.search_results FOR SELECT
    USING (public.is_workspace_member(workspace_id, auth.uid()));

DROP POLICY IF EXISTS "Workspace members can insert search results" ON public.search_results;
CREATE POLICY "Workspace members can insert search results"
    ON public.search_results FOR INSERT
    WITH CHECK (public.is_workspace_member(workspace_id, auth.uid()));

DROP POLICY IF EXISTS "Workspace members can update search results" ON public.search_results;
CREATE POLICY "Workspace members can update search results"
    ON public.search_results FOR UPDATE
    USING (public.is_workspace_member(workspace_id, auth.uid()))
    WITH CHECK (public.is_workspace_member(workspace_id, auth.uid()));

DROP POLICY IF EXISTS "Disallow physical delete on search results" ON public.search_results;
CREATE POLICY "Disallow physical delete on search results"
    ON public.search_results FOR DELETE
    USING (false);
