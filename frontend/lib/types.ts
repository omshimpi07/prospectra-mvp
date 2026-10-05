export type ProspectStatus = "QUEUED" | "RESEARCHING" | "COMPLETED" | "FAILED";
export type QualificationStatus = "UNQUALIFIED" | "QUALIFIED" | "DISQUALIFIED" | "REVIEW_NEEDED";
export type ReviewStatus = "UNREVIEWED" | "APPROVED" | "REJECTED";
export type FactorStatus = "matched" | "unmatched" | "unknown";

export interface ScoreFactor {
  key: string;
  label: string;
  impact: float;
  max_impact: float;
  status: FactorStatus;
  evidence_snippet?: string | null;
}

export type float = number;

export interface ScoreBreakdown {
  raw_score: number;
  status_multiplier: number;
  priority_score: number;
  scoring_profile: string;
  scoring_version: string;
  scored_at: string;
  factors: ScoreFactor[];
}

export interface Prospect {
  id: string;
  workspace_id: string;
  icp_id: string;
  search_result_id?: string | null;
  name: string;
  canonical_category: string;
  city?: string | null;
  website_url?: string | null;
  phone?: string | null;
  status: ProspectStatus;
  qualification_status: QualificationStatus;
  fit_score: number;
  priority_score: number;
  score_breakdown: ScoreBreakdown;
  scoring_version: string;
  scored_at?: string | null;
  qualification_reason?: string | null;
  raw_signals: Record<string, any>;
  review_status: ReviewStatus;
  rejection_reason?: string | null;
  seller_note?: string | null;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  created_at: string;
  updated_at: string;
}

export interface QualificationEvidence {
  id: string;
  workspace_id: string;
  prospect_id: string;
  signal_key: string;
  signal_value: Record<string, any>;
  confidence: number;
  source_url?: string | null;
  snippet?: string | null;
  observed_at: string;
  created_at: string;
}

export interface ReviewProspectPayload {
  review_status: ReviewStatus;
  rejection_reason?: string | null;
  seller_note?: string | null;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  created_at: string;
}
