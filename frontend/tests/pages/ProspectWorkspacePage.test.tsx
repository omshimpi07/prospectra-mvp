import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ProspectWorkspacePage from "@/app/workspaces/[workspaceId]/prospects/page";
import { Prospect } from "@/lib/types";

// Mock Next.js navigation hooks
vi.mock("next/navigation", () => ({
  useParams: () => ({ workspaceId: "ws-1" }),
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const { mockProspects } = vi.hoisted(() => {
  const mockProspects = [
    {
      id: "p-1",
      workspace_id: "ws-1",
      icp_id: "icp-1",
      name: "Blue Tokai Coffee Roasters",
      canonical_category: "cafe",
      city: "Pune",
      website_url: "https://bluetokai.example.com",
      phone: "+919876543210",
      status: "COMPLETED",
      qualification_status: "QUALIFIED",
      fit_score: 1.0,
      priority_score: 0.92,
      score_breakdown: {
        raw_score: 0.92,
        status_multiplier: 1.0,
        priority_score: 0.92,
        scoring_profile: "WEB_REDESIGN_MODERNIZATION",
        scoring_version: "v1.0",
        scored_at: new Date().toISOString(),
        factors: [],
      },
      scoring_version: "v1.0",
      qualification_reason: "High opportunity: active cafe missing mobile viewport.",
      raw_signals: {
        public_emails: ["hello@bluetokai.example.com"],
        public_phones: ["+919876543210"],
      },
      review_status: "UNREVIEWED",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ];
  return { mockProspects };
});

vi.mock("@/lib/api", () => ({
  fetchProspects: vi.fn().mockImplementation(() => Promise.resolve(mockProspects)),
  downloadProspectsCsv: vi.fn().mockResolvedValue(undefined),
  updateProspectReview: vi.fn().mockImplementation(() => Promise.resolve({ ...mockProspects[0], review_status: "APPROVED" })),
  fetchEvidence: vi.fn().mockResolvedValue([]),
}));

describe("ProspectWorkspacePage", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    vi.clearAllMocks();
  });

  it("renders workspace title, export button, and ranked prospect rows", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <ProspectWorkspacePage />
      </QueryClientProvider>
    );

    // Title & Export
    expect(screen.getByText("Prospect Intelligence Workspace")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Export Approved CSV/i })).toBeInTheDocument();

    // Row content (awaits React Query resolution)
    expect(await screen.findByText("Blue Tokai Coffee Roasters")).toBeInTheDocument();
    expect(screen.getByText("Priority")).toBeInTheDocument();
    expect(screen.getByText("Business & Category")).toBeInTheDocument();
    expect(screen.getByText("Core Opportunity (Why Ranked)")).toBeInTheDocument();
    expect(screen.getByText("92%")).toBeInTheDocument();
    expect(screen.getByText(/High opportunity: active cafe missing mobile viewport./i)).toBeInTheDocument();
    expect(screen.getByText("UNREVIEWED")).toBeInTheDocument();
  });
});
