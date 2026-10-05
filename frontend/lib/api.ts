import { supabase } from "./supabase";
import { Prospect, QualificationEvidence, ReviewProspectPayload, Workspace } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function getAuthHeaders(): Promise<HeadersInit> {
  const { data: { session } } = await supabase.auth.getSession();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (session?.access_token) {
    headers["Authorization"] = `Bearer ${session.access_token}`;
  }
  return headers;
}

export async function fetchWorkspaces(): Promise<Workspace[]> {
  const headers = await getAuthHeaders();
  const resp = await fetch(`${API_BASE_URL}/workspaces`, { headers });
  if (!resp.ok) {
    throw new Error(`Failed to load workspaces: ${resp.status}`);
  }
  return resp.json();
}

export interface FetchProspectsParams {
  review_status?: string;
  qualification_status?: string;
  min_score?: number;
  limit?: number;
  offset?: number;
}

export async function fetchProspects(
  workspaceId: string,
  params: FetchProspectsParams = {}
): Promise<Prospect[]> {
  const headers = await getAuthHeaders();
  const query = new URLSearchParams();
  if (params.review_status && params.review_status !== "ALL") {
    query.set("review_status", params.review_status);
  }
  if (params.qualification_status) {
    query.set("qualification_status", params.qualification_status);
  }
  if (params.min_score !== undefined && params.min_score !== null) {
    query.set("min_score", params.min_score.toString());
  }
  if (params.limit) query.set("limit", params.limit.toString());
  if (params.offset) query.set("offset", params.offset.toString());

  const url = `${API_BASE_URL}/workspaces/${workspaceId}/prospects?${query.toString()}`;
  const resp = await fetch(url, { headers });
  if (!resp.ok) {
    throw new Error(`Failed to fetch prospects: ${resp.status}`);
  }
  return resp.json();
}

export async function fetchProspect(
  workspaceId: string,
  prospectId: string
): Promise<Prospect> {
  const headers = await getAuthHeaders();
  const resp = await fetch(`${API_BASE_URL}/workspaces/${workspaceId}/prospects/${prospectId}`, {
    headers,
  });
  if (!resp.ok) {
    throw new Error(`Failed to fetch prospect: ${resp.status}`);
  }
  return resp.json();
}

export async function fetchEvidence(
  workspaceId: string,
  prospectId: string
): Promise<QualificationEvidence[]> {
  const headers = await getAuthHeaders();
  const resp = await fetch(
    `${API_BASE_URL}/workspaces/${workspaceId}/prospects/${prospectId}/evidence`,
    { headers }
  );
  if (!resp.ok) {
    throw new Error(`Failed to fetch evidence: ${resp.status}`);
  }
  return resp.json();
}

export async function updateProspectReview(
  workspaceId: string,
  prospectId: string,
  payload: ReviewProspectPayload
): Promise<Prospect> {
  const headers = await getAuthHeaders();
  const resp = await fetch(
    `${API_BASE_URL}/workspaces/${workspaceId}/prospects/${prospectId}/review`,
    {
      method: "PATCH",
      headers,
      body: JSON.stringify(payload),
    }
  );
  if (!resp.ok) {
    const errorData = await resp.json().catch(() => ({}));
    throw new Error(
      errorData?.error?.message ||
        errorData?.detail?.[0]?.msg ||
        `Review update failed (${resp.status})`
    );
  }
  return resp.json();
}

export async function downloadProspectsCsv(
  workspaceId: string,
  params: { review_status?: string; qualification_status?: string; min_score?: number } = {}
): Promise<void> {
  const headers = await getAuthHeaders();
  const query = new URLSearchParams();
  query.set("review_status", params.review_status || "APPROVED");
  if (params.qualification_status) {
    query.set("qualification_status", params.qualification_status);
  }
  if (params.min_score !== undefined && params.min_score !== null) {
    query.set("min_score", params.min_score.toString());
  }

  const url = `${API_BASE_URL}/workspaces/${workspaceId}/prospects/export?${query.toString()}`;
  const resp = await fetch(url, { headers });
  if (!resp.ok) {
    throw new Error(`Export failed: ${resp.status}`);
  }

  const blob = await resp.blob();
  const disposition = resp.headers.get("Content-Disposition");
  let filename = "prospects.csv";
  if (disposition && disposition.includes("filename=")) {
    const match = disposition.match(/filename="?([^"]+)"?/);
    if (match && match[1]) filename = match[1];
  }

  const downloadUrl = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(downloadUrl);
}

export async function createWorkspace(name: string): Promise<Workspace> {
  const headers = await getAuthHeaders();
  const resp = await fetch(`${API_BASE_URL}/workspaces`, {
    method: "POST",
    headers,
    body: JSON.stringify({ name }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err?.error?.message || err?.detail?.[0]?.msg || "Failed to create workspace");
  }
  return resp.json();
}

export async function createICP(
  workspaceId: string,
  name: string,
  rawPrompt: string
): Promise<{ id: string; name: string; status: string }> {
  const headers = await getAuthHeaders();
  const resp = await fetch(`${API_BASE_URL}/workspaces/${workspaceId}/icps`, {
    method: "POST",
    headers,
    body: JSON.stringify({ name, raw_prompt: rawPrompt }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err?.error?.message || err?.detail?.[0]?.msg || "Failed to create targeting criteria");
  }
  return resp.json();
}

export async function compileICP(
  workspaceId: string,
  icpId: string
): Promise<{ id: string; status: string; compiled_criteria: any }> {
  const headers = await getAuthHeaders();
  const resp = await fetch(`${API_BASE_URL}/workspaces/${workspaceId}/icps/${icpId}/compile`, {
    method: "POST",
    headers,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err?.error?.message || err?.detail?.[0]?.msg || "Failed to compile targeting criteria");
  }
  return resp.json();
}

export async function approveICP(
  workspaceId: string,
  icpId: string
): Promise<{ id: string; status: string }> {
  const headers = await getAuthHeaders();
  const resp = await fetch(`${API_BASE_URL}/workspaces/${workspaceId}/icps/${icpId}`, {
    method: "PATCH",
    headers,
    body: JSON.stringify({ status: "APPROVED" }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err?.error?.message || err?.detail?.[0]?.msg || "Failed to approve targeting criteria");
  }
  return resp.json();
}

export async function createSearch(
  workspaceId: string,
  icpId: string,
  limit: number = 25
): Promise<{ id: string; status: string }> {
  const headers = await getAuthHeaders();
  const resp = await fetch(`${API_BASE_URL}/workspaces/${workspaceId}/searches`, {
    method: "POST",
    headers,
    body: JSON.stringify({ icp_id: icpId, limit }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err?.error?.message || err?.detail?.[0]?.msg || "Failed to create search specification");
  }
  return resp.json();
}

export async function runSearch(
  workspaceId: string,
  searchId: string
): Promise<{ id: string; status: string }> {
  const headers = await getAuthHeaders();
  const resp = await fetch(`${API_BASE_URL}/workspaces/${workspaceId}/searches/${searchId}/run`, {
    method: "POST",
    headers,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err?.error?.message || err?.detail?.[0]?.msg || "Failed to start search");
  }
  return resp.json();
}

export async function getSearch(
  workspaceId: string,
  searchId: string
): Promise<{ id: string; status: string; total_candidates: number; error_message?: string }> {
  const headers = await getAuthHeaders();
  const resp = await fetch(`${API_BASE_URL}/workspaces/${workspaceId}/searches/${searchId}`, {
    headers,
  });
  if (!resp.ok) {
    throw new Error(`Failed to check search status (${resp.status})`);
  }
  return resp.json();
}

export async function getSearchResults(
  workspaceId: string,
  searchId: string,
  limit: number = 50
): Promise<Array<{ id: string; name: string; canonical_category: string; website?: string }>> {
  const headers = await getAuthHeaders();
  const resp = await fetch(
    `${API_BASE_URL}/workspaces/${workspaceId}/searches/${searchId}/results?limit=${limit}`,
    { headers }
  );
  if (!resp.ok) {
    throw new Error(`Failed to fetch search results (${resp.status})`);
  }
  return resp.json();
}

export async function qualifyCandidates(
  workspaceId: string,
  searchResultIds: string[]
): Promise<{ queued_count: number; message: string }> {
  const headers = await getAuthHeaders();
  const resp = await fetch(
    `${API_BASE_URL}/workspaces/${workspaceId}/prospects/qualify-candidates`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({ search_result_ids: searchResultIds }),
    }
  );
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err?.error?.message || err?.detail?.[0]?.msg || "Failed to enqueue prospects for research");
  }
  return resp.json();
}
