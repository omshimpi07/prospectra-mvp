"use client";

import React, { useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchProspects, downloadProspectsCsv, updateProspectReview } from "@/lib/api";
import { Prospect, ReviewStatus, QualificationStatus } from "@/lib/types";
import { ScoreBadge } from "@/components/ScoreBadge";
import { ContactChannels } from "@/components/ContactChannels";
import { ProspectDetailDrawer } from "@/components/ProspectDetailDrawer";
import {
  Download,
  Filter,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Search,
  Building2,
  Loader2,
  AlertCircle,
  SlidersHorizontal,
} from "lucide-react";

export default function ProspectWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const workspaceId = params.workspaceId as string;

  // URL search params as source of truth for filters
  const reviewFilter = searchParams.get("review") || "ALL";
  const qualFilter = searchParams.get("qual") || "";
  const minScoreParam = searchParams.get("min_score");
  const minScore = minScoreParam ? parseFloat(minScoreParam) : undefined;
  const selectedProspectId = searchParams.get("prospectId");

  const [searchQuery, setSearchQuery] = useState("");
  const [exporting, setExporting] = useState(false);

  // TanStack Query for server data fetching
  const {
    data: prospects = [],
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["prospects", workspaceId, reviewFilter, qualFilter, minScore],
    queryFn: () =>
      fetchProspects(workspaceId, {
        review_status: reviewFilter,
        qualification_status: qualFilter || undefined,
        min_score: minScore,
        limit: 100,
      }),
    enabled: Boolean(workspaceId),
  });

  // Quick review mutation for inline Approve / Reject
  const quickReviewMutation = useMutation({
    mutationFn: ({ prospectId, status }: { prospectId: string; status: ReviewStatus }) => {
      const reason = status === "REJECTED" ? "POOR_OPPORTUNITY" : null;
      return updateProspectReview(workspaceId, prospectId, {
        review_status: status,
        rejection_reason: reason,
      });
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(
        ["prospects", workspaceId, reviewFilter, qualFilter, minScore],
        (old: Prospect[] | undefined) => {
          if (!old) return old;
          return old.map((p) => (p.id === updated.id ? updated : p));
        }
      );
      queryClient.invalidateQueries({ queryKey: ["prospects", workspaceId] });
    },
  });

  // Filter update helper
  const updateUrlFilters = (updates: Record<string, string | null>) => {
    const nextParams = new URLSearchParams(searchParams.toString());
    Object.entries(updates).forEach(([key, val]) => {
      if (val === null || val === "" || val === "ALL") {
        nextParams.delete(key);
      } else {
        nextParams.set(key, val);
      }
    });
    router.push(`?${nextParams.toString()}`);
  };

  // CSV Export handler (defaults to APPROVED per Instruction 6)
  const handleExportCsv = async () => {
    setExporting(true);
    try {
      await downloadProspectsCsv(workspaceId, {
        review_status: reviewFilter === "ALL" ? "APPROVED" : reviewFilter,
        qualification_status: qualFilter || undefined,
        min_score: minScore,
      });
    } catch (err: any) {
      alert(`Export failed: ${err.message}`);
    } finally {
      setExporting(false);
    }
  };

  // Filtered by local search query
  const filteredProspects = prospects.filter((p) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      p.name.toLowerCase().includes(q) ||
      p.canonical_category.toLowerCase().includes(q) ||
      (p.city && p.city.toLowerCase().includes(q))
    );
  });

  // Find currently selected prospect for the detail drawer
  const selectedProspect = selectedProspectId
    ? prospects.find((p) => p.id === selectedProspectId) || null
    : null;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Top Navbar */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-blue-600 text-white flex items-center justify-center font-bold">
            <Building2 className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-900 leading-tight">Prospect Intelligence Workspace</h1>
            <p className="text-xs text-slate-500">Deterministic Opportunity Queue & Human Review</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition"
            title="Refresh prospects queue"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin text-blue-600" : ""}`} />
          </button>

          <button
            onClick={handleExportCsv}
            disabled={exporting}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-sm transition disabled:opacity-50"
          >
            {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
            <span>Export Approved CSV</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-5">
        {/* Filter & Control Bar */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            {/* Review Status Tabs */}
            <div className="flex bg-slate-100 p-1 rounded-lg text-xs font-medium self-start">
              {[
                { key: "ALL", label: "All Queue" },
                { key: "UNREVIEWED", label: "Unreviewed" },
                { key: "APPROVED", label: "Approved" },
                { key: "REJECTED", label: "Rejected" },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => updateUrlFilters({ review: tab.key })}
                  className={`px-3 py-1.5 rounded-md transition ${
                    reviewFilter === tab.key
                      ? "bg-white text-slate-900 font-bold shadow-xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Search Input */}
            <div className="relative w-full sm:w-64">
              <Search className="h-3.5 w-3.5 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter by name or niche..."
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Secondary Filters: Qualification and Minimum Score */}
          <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-slate-100 text-xs">
            <div className="flex items-center gap-1.5 text-slate-500">
              <SlidersHorizontal className="h-3.5 w-3.5" />
              <span>Filters:</span>
            </div>

            {/* Min Score Filter */}
            <select
              value={minScore !== undefined ? minScore.toString() : ""}
              onChange={(e) => updateUrlFilters({ min_score: e.target.value || null })}
              className="text-xs p-1.5 rounded-lg border border-slate-200 bg-white text-slate-700"
            >
              <option value="">All Opportunity Scores</option>
              <option value="0.80">Priority ≥ 80% (High)</option>
              <option value="0.65">Priority ≥ 65% (Med+)</option>
              <option value="0.50">Priority ≥ 50%</option>
            </select>

            {/* Qualification Status Filter */}
            <select
              value={qualFilter}
              onChange={(e) => updateUrlFilters({ qual: e.target.value || null })}
              className="text-xs p-1.5 rounded-lg border border-slate-200 bg-white text-slate-700"
            >
              <option value="">All Qualification Tiers</option>
              <option value="QUALIFIED">QUALIFIED Only</option>
              <option value="REVIEW_NEEDED">REVIEW_NEEDED Only</option>
              <option value="UNQUALIFIED">UNQUALIFIED Only</option>
            </select>

            {(reviewFilter !== "ALL" || qualFilter || minScore !== undefined) && (
              <button
                onClick={() => router.push(window.location.pathname)}
                className="text-xs text-blue-600 hover:underline ml-auto"
              >
                Reset filters
              </button>
            )}
          </div>
        </div>

        {/* Prospect List / Table */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
          {isLoading ? (
            <div className="p-16 flex flex-col items-center justify-center gap-3 text-slate-400">
              <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
              <p className="text-sm font-medium">Loading ranked prospects...</p>
            </div>
          ) : isError ? (
            <div className="p-12 text-center space-y-3">
              <AlertCircle className="h-8 w-8 text-rose-500 mx-auto" />
              <p className="text-sm font-semibold text-slate-800">Failed to load prospects</p>
              <p className="text-xs text-slate-500">{(error as any)?.message}</p>
              <button
                onClick={() => refetch()}
                className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-semibold"
              >
                Retry
              </button>
            </div>
          ) : filteredProspects.length === 0 ? (
            <div className="p-16 text-center space-y-2">
              <Building2 className="h-10 w-10 text-slate-300 mx-auto" />
              <p className="text-sm font-bold text-slate-800">No prospects match your current criteria</p>
              <p className="text-xs text-slate-500">
                Try switching review status tabs or lowering the minimum opportunity score.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/75 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                    <th className="py-3 px-4">Priority</th>
                    <th className="py-3 px-4">Business & Category</th>
                    <th className="py-3 px-4">Core Opportunity (Why Ranked)</th>
                    <th className="py-3 px-4">Channels</th>
                    <th className="py-3 px-4">Review Status</th>
                    <th className="py-3 px-4 text-right">Quick Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs">
                  {filteredProspects.map((prospect) => (
                    <tr
                      key={prospect.id}
                      onClick={() => updateUrlFilters({ prospectId: prospect.id })}
                      className="hover:bg-blue-50/40 cursor-pointer transition"
                    >
                      {/* Priority Score */}
                      <td className="py-3 px-4 shrink-0">
                        <ScoreBadge score={prospect.priority_score} size="md" />
                      </td>

                      {/* Business Name & Category */}
                      <td className="py-3 px-4">
                        <div className="font-bold text-slate-900 hover:text-blue-600 transition">
                          {prospect.name}
                        </div>
                        <div className="text-[11px] text-slate-500 flex items-center gap-1.5 mt-0.5">
                          <span className="capitalize">{prospect.canonical_category}</span>
                          {prospect.city && <span>• {prospect.city}</span>}
                        </div>
                      </td>

                      {/* Opportunity Summary (Qualification Reason) */}
                      <td className="py-3 px-4 max-w-sm">
                        <p className="line-clamp-2 text-slate-700 text-[11px] leading-relaxed">
                          {prospect.qualification_reason || "Deterministic signal qualification complete."}
                        </p>
                      </td>

                      {/* Contact Availability */}
                      <td className="py-3 px-4 shrink-0">
                        <ContactChannels
                          websiteUrl={prospect.website_url}
                          phone={prospect.phone}
                          emails={prospect.raw_signals?.public_emails || []}
                          phones={prospect.raw_signals?.public_phones || []}
                        />
                      </td>

                      {/* Human Review Status Badge */}
                      <td className="py-3 px-4 shrink-0">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                            prospect.review_status === "APPROVED"
                              ? "bg-emerald-100 text-emerald-800"
                              : prospect.review_status === "REJECTED"
                              ? "bg-rose-100 text-rose-800"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {prospect.review_status}
                        </span>
                      </td>

                      {/* Quick Actions */}
                      <td
                        className="py-3 px-4 text-right shrink-0"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() =>
                              quickReviewMutation.mutate({
                                prospectId: prospect.id,
                                status: "APPROVED",
                              })
                            }
                            title="Approve prospect"
                            className={`p-1.5 rounded-md border transition ${
                              prospect.review_status === "APPROVED"
                                ? "bg-emerald-600 text-white border-emerald-600"
                                : "bg-white text-slate-600 border-slate-200 hover:border-emerald-300 hover:text-emerald-700"
                            }`}
                          >
                            <CheckCircle2 className="h-4 w-4" />
                          </button>

                          <button
                            type="button"
                            onClick={() =>
                              quickReviewMutation.mutate({
                                prospectId: prospect.id,
                                status: "REJECTED",
                              })
                            }
                            title="Reject prospect"
                            className={`p-1.5 rounded-md border transition ${
                              prospect.review_status === "REJECTED"
                                ? "bg-rose-600 text-white border-rose-600"
                                : "bg-white text-slate-600 border-slate-200 hover:border-rose-300 hover:text-rose-700"
                            }`}
                          >
                            <XCircle className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {/* Prospect Detail Drawer */}
      <ProspectDetailDrawer
        workspaceId={workspaceId}
        prospect={selectedProspect}
        onClose={() => updateUrlFilters({ prospectId: null })}
      />
    </div>
  );
}
