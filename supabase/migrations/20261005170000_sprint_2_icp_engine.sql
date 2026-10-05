-- Migration: 20261005170000_sprint_2_icp_engine.sql
-- Description: Create icps table, audit trigger, and RLS policies

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS public.icps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    name VARCHAR(255) NOT NULL,
    raw_prompt TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
    version INTEGER NOT NULL DEFAULT 1,
    compiled_criteria JSONB,
    compilation_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_icp_status CHECK (
        status IN ('DRAFT', 'COMPILED', 'APPROVED', 'ARCHIVED')
    ),
    CONSTRAINT chk_icp_name_not_empty CHECK (
        char_length(trim(name)) > 0
    ),
    CONSTRAINT chk_icp_raw_prompt_not_empty CHECK (
        char_length(trim(raw_prompt)) > 0
    )
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_icps_workspace_id ON public.icps(workspace_id);
CREATE INDEX IF NOT EXISTS idx_icps_status ON public.icps(workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_icps_created_by ON public.icps(created_by);

-- Updated_at Trigger
DROP TRIGGER IF EXISTS trg_icps_updated_at ON public.icps;
CREATE TRIGGER trg_icps_updated_at
    BEFORE UPDATE ON public.icps
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Row Level Security
ALTER TABLE public.icps ENABLE ROW LEVEL SECURITY;

-- Select Policy: Workspace members can view icps
DROP POLICY IF EXISTS "Workspace members can view icps" ON public.icps;
CREATE POLICY "Workspace members can view icps"
    ON public.icps
    FOR SELECT
    USING (public.is_workspace_member(workspace_id, auth.uid()));

-- Insert Policy: Workspace members can create icps
DROP POLICY IF EXISTS "Workspace members can insert icps" ON public.icps;
CREATE POLICY "Workspace members can insert icps"
    ON public.icps
    FOR INSERT
    WITH CHECK (
        public.is_workspace_member(workspace_id, auth.uid())
        AND auth.uid() = created_by
    );

-- Update Policy: Workspace members can update icps
DROP POLICY IF EXISTS "Workspace members can update icps" ON public.icps;
CREATE POLICY "Workspace members can update icps"
    ON public.icps
    FOR UPDATE
    USING (public.is_workspace_member(workspace_id, auth.uid()))
    WITH CHECK (public.is_workspace_member(workspace_id, auth.uid()));

-- Delete Policy: Disallow physical delete on icps
DROP POLICY IF EXISTS "Disallow physical delete on icps" ON public.icps;
CREATE POLICY "Disallow physical delete on icps"
    ON public.icps
    FOR DELETE
    USING (false);
