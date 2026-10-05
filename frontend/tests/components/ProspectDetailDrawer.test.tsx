import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProspectDetailDrawer } from "@/components/ProspectDetailDrawer";
import { Prospect } from "@/lib/types";
import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({
  fetchEvidence: vi.fn().mockResolvedValue([
    {
      id: "ev-1",
      workspace_id: "ws-1",
      prospect_id: "p-1",
      signal_key: "web_reachability",
      signal_value: { reachable: true, status_code: 200 },
      confidence: 1.0,
      snippet: "HTTP Status 200, Reachable=True",
      observed_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
    },
  ]),
  updateProspectReview: vi.fn().mockResolvedValue({
    id: "p-1",
    review_status: "APPROVED",
  }),
}));

const mockProspect: Prospect = {
  id: "p-1",
  workspace_id: "ws-1",
  icp_id: "icp-1",
  name: "German Bakery",
  canonical_category: "bakery",
  city: "Pune",
  website_url: "https://germanbakery.example.com",
  phone: "+919876543210",
  status: "COMPLETED",
  qualification_status: "QUALIFIED",
  fit_score: 1.0,
  priority_score: 0.88,
  score_breakdown: {
    raw_score: 0.88,
    status_multiplier: 1.0,
    priority_score: 0.88,
    scoring_profile: "WEB_REDESIGN_MODERNIZATION",
    scoring_version: "v1.0",
    scored_at: new Date().toISOString(),
    factors: [
      {
        key: "mobile_viewport_gap",
        label: "Lacks Mobile Viewport",
        impact: 0.25,
        max_impact: 0.25,
        status: "matched",
        evidence_snippet: "Viewport meta tag absent",
      },
    ],
  },
  scoring_version: "v1.0",
  qualification_reason: "High opportunity: active bakery with non-responsive site.",
  raw_signals: {
    public_emails: ["info@germanbakery.example.com"],
    public_phones: ["+919876543210"],
  },
  review_status: "UNREVIEWED",
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

describe("ProspectDetailDrawer", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    vi.clearAllMocks();
  });

  it("renders SYSTEM section with qualification status, score breakdown, and rationale", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <ProspectDetailDrawer workspaceId="ws-1" prospect={mockProspect} onClose={vi.fn()} />
      </QueryClientProvider>
    );

    // Business & Category
    expect(screen.getByText("German Bakery")).toBeInTheDocument();
    expect(screen.getByText("bakery")).toBeInTheDocument();

    // System: Algorithmic Qualification & Factor Decomposition
    expect(screen.getByText("Algorithmic Qualification & Opportunity")).toBeInTheDocument();
    expect(screen.getByText("QUALIFIED")).toBeInTheDocument();
    expect(screen.getByText("Lacks Mobile Viewport")).toBeInTheDocument();
    expect(screen.getByText("+0.25")).toBeInTheDocument();
    expect(screen.getByText("High opportunity: active bakery with non-responsive site.")).toBeInTheDocument();
  });

  it("renders HUMAN section with review controls and updates review status", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <ProspectDetailDrawer workspaceId="ws-1" prospect={mockProspect} onClose={vi.fn()} />
      </QueryClientProvider>
    );

    expect(screen.getByText("Human Seller Decision")).toBeInTheDocument();
    const approveBtn = screen.getByRole("button", { name: /Approve for Outreach/i });
    expect(approveBtn).toBeInTheDocument();

    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(api.updateProspectReview).toHaveBeenCalledWith(
        "ws-1",
        "p-1",
        expect.objectContaining({
          review_status: "APPROVED",
        })
      );
    });
  });

  it("requires rejection reason when selecting Reject", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <ProspectDetailDrawer workspaceId="ws-1" prospect={mockProspect} onClose={vi.fn()} />
      </QueryClientProvider>
    );

    const rejectBtn = screen.getByRole("button", { name: /Reject/i });
    fireEvent.click(rejectBtn);

    // Rejection reason dropdown appears
    expect(screen.getByText(/Rejection Reason \(Required\)/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(api.updateProspectReview).toHaveBeenCalledWith(
        "ws-1",
        "p-1",
        expect.objectContaining({
          review_status: "REJECTED",
          rejection_reason: expect.any(String),
        })
      );
    });
  });
});
