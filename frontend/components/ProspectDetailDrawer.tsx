"use client";

import React, { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchEvidence, updateProspectReview } from "@/lib/api";
import { Prospect, ReviewStatus } from "@/lib/types";
import { ScoreBadge } from "./ScoreBadge";
import {
  X,
  Mail,
  Phone,
  Globe,
  MessageSquare,
  CheckCircle2,
  XCircle,
  Clock,
  ExternalLink,
  ShieldCheck,
  Check,
  AlertTriangle,
  Loader2,
  Copy,
} from "lucide-react";

interface ProspectDetailDrawerProps {
  workspaceId: string;
  prospect: Prospect | null;
  onClose: () => void;
}

const REJECTION_REASONS = [
  { value: "NOT_A_FIT_NICHE", label: "Not a fit for our niche/offering" },
  { value: "OUTDATED_OR_CLOSED", label: "Business appears closed or inactive" },
  { value: "BAD_CONTACT_DATA", label: "Inaccurate or missing contact channels" },
  { value: "ALREADY_CUSTOMER_OR_CONTACTED", label: "Already existing client or in progress" },
  { value: "POOR_OPPORTUNITY", label: "Poor gap opportunity / unviable prospect" },
  { value: "OTHER", label: "Other / custom reason" },
];

const SIGNAL_LABELS: Record<string, string> = {
  web_reachability: "Website Reachability & HTTP Status",
  ssl_certificate: "SSL / HTTPS Security Certificate",
  mobile_viewport: "Mobile Optimization & Viewport",
  cms_platform: "Content Management & Tech Stack",
  domain_presence: "Domain & Web Presence",
};

export function ProspectDetailDrawer({
  workspaceId,
  prospect,
  onClose,
}: ProspectDetailDrawerProps) {
  const queryClient = useQueryClient();

  // Local state for human review
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus>(prospect?.review_status || "UNREVIEWED");
  const [rejectionReason, setRejectionReason] = useState<string>(prospect?.rejection_reason || "");
  const [sellerNote, setSellerNote] = useState<string>(prospect?.seller_note || "");
  const [noteSaveStatus, setNoteSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [copiedContact, setCopiedContact] = useState(false);

  const debounceTimeout = useRef<NodeJS.Timeout | null>(null);

  // Sync state when selected prospect changes
  useEffect(() => {
    if (prospect) {
      setReviewStatus(prospect.review_status);
      setRejectionReason(prospect.rejection_reason || "");
      setSellerNote(prospect.seller_note || "");
      setNoteSaveStatus("idle");
    }
  }, [prospect]);

  // Lazy-load detailed audit evidence only when drawer is opened
  const { data: evidenceList = [], isLoading: isLoadingEvidence } = useQuery({
    queryKey: ["prospect-evidence", workspaceId, prospect?.id],
    queryFn: () => (prospect ? fetchEvidence(workspaceId, prospect.id) : Promise.resolve([])),
    enabled: Boolean(prospect),
  });

  // Mutation for updating review status and notes
  const reviewMutation = useMutation({
    mutationFn: (payload: { review_status: ReviewStatus; rejection_reason?: string | null; seller_note?: string | null }) => {
      if (!prospect) throw new Error("No prospect selected");
      return updateProspectReview(workspaceId, prospect.id, payload);
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(["prospects", workspaceId], (old: Prospect[] | undefined) => {
        if (!old) return old;
        return old.map((p) => (p.id === updated.id ? updated : p));
      });
      queryClient.invalidateQueries({ queryKey: ["prospects", workspaceId] });
      setNoteSaveStatus("saved");
      setTimeout(() => setNoteSaveStatus("idle"), 2500);
    },
    onError: () => {
      setNoteSaveStatus("error");
    },
  });

  // Debounced autosave for seller note (600ms)
  const handleNoteChange = (newNote: string) => {
    setSellerNote(newNote);
    setNoteSaveStatus("saving");

    if (debounceTimeout.current) {
      clearTimeout(debounceTimeout.current);
    }

    debounceTimeout.current = setTimeout(() => {
      reviewMutation.mutate({
        review_status: reviewStatus,
        rejection_reason: reviewStatus === "REJECTED" ? rejectionReason : null,
        seller_note: newNote,
      });
    }, 600);
  };

  const handleStatusChange = (newStatus: ReviewStatus) => {
    setReviewStatus(newStatus);
    const reasonToSend = newStatus === "REJECTED" ? (rejectionReason || "POOR_OPPORTUNITY") : null;
    if (newStatus === "REJECTED" && !rejectionReason) {
      setRejectionReason("POOR_OPPORTUNITY");
    }

    reviewMutation.mutate({
      review_status: newStatus,
      rejection_reason: reasonToSend,
      seller_note: sellerNote,
    });
  };

  const handleRejectionReasonChange = (reason: string) => {
    setRejectionReason(reason);
    if (reviewStatus === "REJECTED") {
      reviewMutation.mutate({
        review_status: "REJECTED",
        rejection_reason: reason,
        seller_note: sellerNote,
      });
    }
  };

  if (!prospect) return null;

  const emails = prospect.raw_signals?.public_emails || [];
  const phones = prospect.raw_signals?.public_phones || (prospect.phone ? [prospect.phone] : []);
  const primaryEmail = emails.length > 0 ? emails[0] : null;
  const primaryPhone = phones.length > 0 ? phones[0] : null;
  const whatsappPhone = primaryPhone ? primaryPhone.replace(/[^0-9]/g, "") : null;

  const copyContactSummary = () => {
    const lines = [
      `Business: ${prospect.name}`,
      prospect.website_url ? `Website: ${prospect.website_url}` : null,
      primaryEmail ? `Email: ${primaryEmail}` : null,
      primaryPhone ? `Phone: ${primaryPhone}` : null,
      `Opportunity: ${prospect.qualification_reason || "None specified"}`,
    ].filter(Boolean).join("\n");

    navigator.clipboard.writeText(lines);
    setCopiedContact(true);
    setTimeout(() => setCopiedContact(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/40 backdrop-blur-sm flex justify-end transition-opacity">
      <div className="w-full max-w-2xl bg-white h-full shadow-2xl flex flex-col overflow-y-auto border-l border-slate-200">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-slate-200 p-5 flex items-start justify-between z-10">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <ScoreBadge score={prospect.priority_score} size="md" />
              <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium">
                {prospect.canonical_category}
              </span>
              {prospect.city && (
                <span className="text-xs text-slate-500">• {prospect.city}</span>
              )}
            </div>
            <h2 className="text-xl font-bold text-slate-900 leading-tight">{prospect.name}</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-8 flex-1">
          {/* Outreach Action Bar */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                Direct Human Outreach
              </span>
              <button
                onClick={copyContactSummary}
                className="text-xs flex items-center gap-1 text-slate-500 hover:text-slate-800 transition"
              >
                {copiedContact ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                <span>{copiedContact ? "Copied" : "Copy Info"}</span>
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {primaryEmail ? (
                <a
                  href={`mailto:${primaryEmail}?subject=Website modernization for ${encodeURIComponent(prospect.name)}`}
                  className="flex items-center justify-center gap-1.5 p-2.5 rounded-lg bg-white border border-slate-200 hover:border-blue-300 hover:bg-blue-50/50 text-blue-700 text-xs font-semibold shadow-sm transition"
                >
                  <Mail className="h-4 w-4" />
                  <span>Email</span>
                </a>
              ) : (
                <span className="flex items-center justify-center gap-1.5 p-2.5 rounded-lg bg-slate-100 text-slate-400 text-xs font-medium cursor-not-allowed">
                  <Mail className="h-4 w-4" />
                  <span>No Email</span>
                </span>
              )}

              {primaryPhone ? (
                <a
                  href={`tel:${primaryPhone}`}
                  className="flex items-center justify-center gap-1.5 p-2.5 rounded-lg bg-white border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50/50 text-emerald-700 text-xs font-semibold shadow-sm transition"
                >
                  <Phone className="h-4 w-4" />
                  <span>Call</span>
                </a>
              ) : (
                <span className="flex items-center justify-center gap-1.5 p-2.5 rounded-lg bg-slate-100 text-slate-400 text-xs font-medium cursor-not-allowed">
                  <Phone className="h-4 w-4" />
                  <span>No Phone</span>
                </span>
              )}

              {whatsappPhone ? (
                <a
                  href={`https://wa.me/${whatsappPhone}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-1.5 p-2.5 rounded-lg bg-white border border-slate-200 hover:border-green-300 hover:bg-green-50/50 text-green-700 text-xs font-semibold shadow-sm transition"
                >
                  <MessageSquare className="h-4 w-4" />
                  <span>WhatsApp</span>
                </a>
              ) : (
                <span className="flex items-center justify-center gap-1.5 p-2.5 rounded-lg bg-slate-100 text-slate-400 text-xs font-medium cursor-not-allowed">
                  <MessageSquare className="h-4 w-4" />
                  <span>No WhatsApp</span>
                </span>
              )}

              {prospect.website_url ? (
                <a
                  href={prospect.website_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-1.5 p-2.5 rounded-lg bg-white border border-slate-200 hover:border-slate-400 text-slate-700 text-xs font-semibold shadow-sm transition"
                >
                  <Globe className="h-4 w-4" />
                  <span>Website</span>
                  <ExternalLink className="h-3 w-3 opacity-60" />
                </a>
              ) : (
                <span className="flex items-center justify-center gap-1.5 p-2.5 rounded-lg bg-slate-100 text-slate-400 text-xs font-medium cursor-not-allowed">
                  <Globe className="h-4 w-4" />
                  <span>No Website</span>
                </span>
              )}
            </div>
          </div>

          {/* ============================================================= */}
          {/* SECTION 1: HUMAN SELLER DECISION                              */}
          {/* ============================================================= */}
          <div className="border border-indigo-100 bg-indigo-50/30 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-indigo-600"></span>
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                  Human Seller Decision
                </h3>
              </div>
              {/* Last Review Metadata */}
              {prospect.reviewed_at && (
                <span className="text-[11px] text-slate-500 flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  Last reviewed: {new Date(prospect.reviewed_at).toLocaleDateString()}
                </span>
              )}
            </div>

            {/* Decision Tabs */}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => handleStatusChange("APPROVED")}
                className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 border transition ${
                  reviewStatus === "APPROVED"
                    ? "bg-emerald-600 text-white border-emerald-600 shadow-sm"
                    : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                }`}
              >
                <CheckCircle2 className="h-4 w-4" />
                <span>Approve for Outreach</span>
              </button>

              <button
                type="button"
                onClick={() => handleStatusChange("REJECTED")}
                className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 border transition ${
                  reviewStatus === "REJECTED"
                    ? "bg-rose-600 text-white border-rose-600 shadow-sm"
                    : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                }`}
              >
                <XCircle className="h-4 w-4" />
                <span>Reject</span>
              </button>

              <button
                type="button"
                onClick={() => handleStatusChange("UNREVIEWED")}
                className={`py-2 px-3 rounded-lg text-xs font-medium border transition ${
                  reviewStatus === "UNREVIEWED"
                    ? "bg-slate-800 text-white border-slate-800 shadow-sm"
                    : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                }`}
              >
                Reset
              </button>
            </div>

            {/* Rejection Reason Dropdown (Mandatory when rejected) */}
            {reviewStatus === "REJECTED" && (
              <div className="pt-2">
                <label className="block text-xs font-semibold text-rose-900 mb-1">
                  Rejection Reason (Required)
                </label>
                <select
                  value={rejectionReason}
                  onChange={(e) => handleRejectionReasonChange(e.target.value)}
                  className="w-full text-xs p-2 rounded-lg border border-rose-300 bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-rose-500"
                >
                  {REJECTION_REASONS.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Seller Note Textarea with Debounced Autosave */}
            <div className="pt-2">
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-semibold text-slate-700">Seller Note (Private)</label>
                <span className="text-[11px] font-medium">
                  {noteSaveStatus === "saving" && (
                    <span className="text-amber-600 flex items-center gap-1">
                      <Loader2 className="h-3 w-3 animate-spin" /> Saving...
                    </span>
                  )}
                  {noteSaveStatus === "saved" && (
                    <span className="text-emerald-600 flex items-center gap-1">
                      <Check className="h-3 w-3" /> Saved
                    </span>
                  )}
                  {noteSaveStatus === "error" && (
                    <span className="text-rose-600">Failed to save note</span>
                  )}
                </span>
              </div>
              <textarea
                value={sellerNote}
                maxLength={1000}
                onChange={(e) => handleNoteChange(e.target.value)}
                placeholder="Log qualitative context e.g., 'Owner Anita visits Tuesdays, proposal sent to manager'..."
                className="w-full text-xs p-2.5 rounded-lg border border-slate-200 focus:ring-2 focus:ring-indigo-500 focus:outline-none min-h-[70px]"
              />
              <div className="text-[10px] text-slate-400 text-right">{sellerNote.length} / 1000</div>
            </div>
          </div>

          {/* ============================================================= */}
          {/* SECTION 2: SYSTEM INTELLIGENCE & EXPLAINABILITY               */}
          {/* ============================================================= */}
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-blue-600" />
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                  Algorithmic Qualification & Opportunity
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-xs px-2.5 py-0.5 rounded-full font-bold uppercase tracking-wider ${
                  prospect.qualification_status === "QUALIFIED"
                    ? "bg-emerald-100 text-emerald-800"
                    : prospect.qualification_status === "REVIEW_NEEDED"
                    ? "bg-amber-100 text-amber-800"
                    : "bg-slate-100 text-slate-700"
                }`}>
                  {prospect.qualification_status}
                </span>
                <span className="text-xs font-medium text-slate-500">
                  {prospect.qualification_status === "QUALIFIED"
                    ? "• Qualified Fit"
                    : prospect.qualification_status === "REVIEW_NEEDED"
                    ? "• Needs Human Review"
                    : "• Not a Match"}
                </span>
              </div>
            </div>

            {/* Core Rationale */}
            {prospect.qualification_reason && (
              <div className="p-3.5 bg-blue-50/60 border border-blue-100 rounded-xl">
                <div className="text-xs font-bold text-blue-900 mb-1">Qualification Rationale</div>
                <p className="text-xs text-blue-800 leading-relaxed">{prospect.qualification_reason}</p>
              </div>
            )}

            {/* Mathematical Factor Decomposition */}
            {prospect.score_breakdown?.factors && prospect.score_breakdown.factors.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-semibold text-slate-700">
                  <span>Factor Decomposition</span>
                  <span className="text-[11px] text-slate-500 font-normal">
                    Profile: {prospect.score_breakdown.scoring_profile}
                  </span>
                </div>

                <div className="border border-slate-200 rounded-xl overflow-hidden divide-y divide-slate-100">
                  {prospect.score_breakdown.factors.map((factor, idx) => (
                    <div key={idx} className="p-3 bg-white flex items-start justify-between gap-4">
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-slate-900">{factor.label}</span>
                          <span
                            className={`text-[10px] px-1.5 py-0.2 rounded font-semibold uppercase ${
                              factor.status === "matched"
                                ? "bg-emerald-50 text-emerald-700"
                                : factor.status === "unknown"
                                ? "bg-amber-50 text-amber-700"
                                : "bg-slate-100 text-slate-500"
                            }`}
                          >
                            {factor.status}
                          </span>
                        </div>
                        {factor.evidence_snippet && (
                          <p className="text-[11px] text-slate-500">{factor.evidence_snippet}</p>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        <span className="text-xs font-bold text-slate-900">
                          +{factor.impact.toFixed(2)}
                        </span>
                        <span className="text-[10px] text-slate-400 ml-1">
                          / {factor.max_impact.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Technical Crawler Evidence */}
            <div className="space-y-2 pt-2">
              <div className="text-xs font-semibold text-slate-700">Audit Trail (Technical Evidence)</div>
              {isLoadingEvidence ? (
                <div className="p-4 flex items-center justify-center gap-2 text-xs text-slate-400">
                  <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                  <span>Loading crawler probe logs...</span>
                </div>
              ) : evidenceList.length > 0 ? (
                <div className="space-y-2.5">
                  {evidenceList.map((ev) => (
                    <div key={ev.id} className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/70 text-xs space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-900">
                          {SIGNAL_LABELS[ev.signal_key] || ev.signal_key}
                        </span>
                        <span className="text-[10px] text-slate-400">
                          {new Date(ev.observed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </div>
                      {ev.snippet && (
                        <div className="p-2 rounded-lg bg-white border border-slate-100 text-slate-700 font-medium text-[11px]">
                          {ev.snippet}
                        </div>
                      )}
                      <details className="pt-1">
                        <summary className="text-[10px] text-blue-600 hover:text-blue-800 cursor-pointer font-medium select-none">
                          View Raw Probe JSON
                        </summary>
                        <pre className="mt-1.5 text-[10px] bg-white p-2.5 rounded-lg border border-slate-200 text-slate-600 overflow-x-auto font-mono">
                          {JSON.stringify(ev.signal_value, null, 2)}
                        </pre>
                      </details>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-3 text-center text-xs text-slate-400 bg-slate-50 rounded-lg">
                  No technical evidence probes recorded for this prospect.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
