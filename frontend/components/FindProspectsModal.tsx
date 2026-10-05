"use client";

import React, { useState } from "react";
import {
  createICP,
  compileICP,
  approveICP,
  createSearch,
  runSearch,
  getSearch,
  getSearchResults,
  qualifyCandidates,
} from "@/lib/api";
import {
  Sparkles,
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Building,
  MapPin,
  Briefcase,
  Globe,
} from "lucide-react";

interface FindProspectsModalProps {
  isOpen: boolean;
  onClose: () => void;
  workspaceId: string;
  onSuccess?: () => void;
  onProspectsCreated?: () => void;
}

type StepStatus = "idle" | "structuring" | "discovering" | "qualifying" | "done" | "error";

export function FindProspectsModal({
  isOpen,
  onClose,
  workspaceId,
  onSuccess,
  onProspectsCreated,
}: FindProspectsModalProps) {
  const [serviceOffering, setServiceOffering] = useState("Modern Website Development & Online Ordering");
  const [businessType, setBusinessType] = useState("Restaurants & Cafes");
  const [city, setCity] = useState("Pune");
  const [websiteFilter, setWebsiteFilter] = useState<"no_website" | "has_website" | "any">("any");
  const [candidateLimit, setCandidateLimit] = useState(20);

  const [status, setStatus] = useState<StepStatus>("idle");
  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [discoveredCount, setDiscoveredCount] = useState(0);

  if (!isOpen) return null;

  const handleStartDiscovery = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setStatus("structuring");
    setStatusMessage("Structuring your targeting criteria with AI...");

    try {
      // 1. Build seller intent prompt
      let webRequirement = "";
      if (websiteFilter === "no_website") {
        webRequirement = "Target businesses that currently do NOT have a website.";
      } else if (websiteFilter === "has_website") {
        webRequirement = "Target businesses that already have a website.";
      }

      const promptText = `I offer ${serviceOffering}. I target ${businessType} located in ${city}. ${webRequirement}`.trim();
      const icpName = `${city} ${businessType} - ${serviceOffering.slice(0, 30)}`;

      // 2. Create ICP draft
      const icp = await createICP(workspaceId, icpName, promptText);

      // 3. Compile ICP
      setStatusMessage("Validating geographic boundaries and business categories...");
      await compileICP(workspaceId, icp.id);

      // 4. Approve ICP
      setStatusMessage("Approving targeting specification...");
      await approveICP(workspaceId, icp.id);

      // 5. Create and run discovery search
      setStatus("discovering");
      setStatusMessage(`Scanning open business registry for ${businessType} in ${city}...`);
      const search = await createSearch(workspaceId, icp.id, candidateLimit);
      await runSearch(workspaceId, search.id);

      // 6. Poll search completion
      let pollAttempts = 0;
      let isCompleted = false;
      while (pollAttempts < 25 && !isCompleted) {
        await new Promise((r) => setTimeout(r, 1200));
        pollAttempts++;
        const currentSearch = await getSearch(workspaceId, search.id);
        if (currentSearch.status === "COMPLETED") {
          isCompleted = true;
          setDiscoveredCount(currentSearch.total_candidates);
        } else if (currentSearch.status === "FAILED") {
          throw new Error(currentSearch.error_message || "Discovery query failed");
        }
      }

      // 7. Qualify candidates into prospects & trigger background research
      setStatus("qualifying");
      setStatusMessage("Extracting public signals and calculating opportunity scores...");
      const searchResults = await getSearchResults(workspaceId, search.id, candidateLimit);

      if (searchResults.length > 0) {
        const candidateIds = searchResults.map((r) => r.id);
        await qualifyCandidates(workspaceId, candidateIds);
      }

      setStatus("done");
      setStatusMessage(`Found ${searchResults.length} business prospects! Initial scores computed.`);

      setTimeout(() => {
        onSuccess?.();
        onProspectsCreated?.();
        onClose();
        setStatus("idle");
      }, 1800);
    } catch (err: any) {
      setStatus("error");
      setErrorMessage(err.message || "An unexpected error occurred during discovery");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs">
      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-100 bg-slate-50/75">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-blue-100/70 text-blue-700">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Find New Prospects</h2>
              <p className="text-xs text-slate-500">Discover and score qualified businesses in your target market</p>
            </div>
          </div>
          {status !== "structuring" && status !== "discovering" && status !== "qualifying" && (
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Form / Progress Content */}
        <div className="p-6">
          {status === "idle" && (
            <form onSubmit={handleStartDiscovery} className="space-y-4">
              {/* Service Offering */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1.5">
                  <Briefcase className="h-3.5 w-3.5 text-slate-400" />
                  <span>What service do you offer?</span>
                </label>
                <input
                  type="text"
                  value={serviceOffering}
                  onChange={(e) => setServiceOffering(e.target.value)}
                  placeholder="e.g. Modern Website Redesign & Online Ordering"
                  required
                  className="w-full text-xs p-2.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Target Business Type & Category */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1.5">
                  <Building className="h-3.5 w-3.5 text-slate-400" />
                  <span>Target Business Category</span>
                </label>
                <input
                  type="text"
                  value={businessType}
                  onChange={(e) => setBusinessType(e.target.value)}
                  placeholder="e.g. Restaurants, Cafes, Bakeries, Salons"
                  required
                  className="w-full text-xs p-2.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <div className="flex gap-1.5 mt-1.5">
                  {["Restaurants & Cafes", "Salons & Spas", "Bakeries", "Dentists"].map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setBusinessType(preset)}
                      className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 hover:bg-blue-50 hover:text-blue-700 transition"
                    >
                      {preset}
                    </button>
                  ))}
                </div>
              </div>

              {/* Target City */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1.5">
                  <MapPin className="h-3.5 w-3.5 text-slate-400" />
                  <span>Target City</span>
                </label>
                <select
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  className="w-full text-xs p-2.5 rounded-lg border border-slate-200 bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="Pune">Pune, Maharashtra</option>
                  <option value="Mumbai">Mumbai, Maharashtra</option>
                  <option value="Bengaluru">Bengaluru, Karnataka</option>
                  <option value="Delhi">Delhi, NCR</option>
                  <option value="Hyderabad">Hyderabad, Telangana</option>
                  <option value="Chennai">Chennai, Tamil Nadu</option>
                </select>
              </div>

              {/* Website Presence Filter */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1.5">
                  <Globe className="h-3.5 w-3.5 text-slate-400" />
                  <span>Website Targeting Preference</span>
                </label>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  {[
                    { id: "any", label: "All Businesses" },
                    { id: "no_website", label: "No Website Only" },
                    { id: "has_website", label: "Has Website" },
                  ].map((opt) => (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => setWebsiteFilter(opt.id as any)}
                      className={`py-2 px-2.5 rounded-lg border text-center font-medium transition ${
                        websiteFilter === opt.id
                          ? "bg-blue-50 border-blue-500 text-blue-700 font-bold"
                          : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Discovery Limit */}
              <div className="flex items-center justify-between text-xs text-slate-500 pt-1">
                <span>Maximum prospects to discover:</span>
                <select
                  value={candidateLimit}
                  onChange={(e) => setCandidateLimit(Number(e.target.value))}
                  className="text-xs p-1.5 rounded-md border border-slate-200 bg-white"
                >
                  <option value={15}>15 prospects</option>
                  <option value={25}>25 prospects</option>
                  <option value={50}>50 prospects</option>
                </select>
              </div>

              {/* Submit Button */}
              <div className="pt-2">
                <button
                  type="submit"
                  className="w-full py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-sm flex items-center justify-center gap-2 transition"
                >
                  <Sparkles className="h-4 w-4" />
                  <span>Start Discovery & Qualification</span>
                </button>
              </div>
            </form>
          )}

          {/* In-Flight Status & Progress */}
          {(status === "structuring" || status === "discovering" || status === "qualifying") && (
            <div className="py-8 px-4 flex flex-col items-center justify-center text-center space-y-4">
              <div className="relative">
                <Loader2 className="h-10 w-10 animate-spin text-blue-600" />
                <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-blue-700">
                  {status === "structuring" ? "1/3" : status === "discovering" ? "2/3" : "3/3"}
                </span>
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-slate-900">
                  {status === "structuring" && "Preparing Targeting Criteria"}
                  {status === "discovering" && "Searching Business Registry"}
                  {status === "qualifying" && "Evaluating Technical Qualification"}
                </h3>
                <p className="text-xs text-slate-500 max-w-sm">{statusMessage}</p>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden max-w-xs mt-2">
                <div
                  className={`h-full bg-blue-600 transition-all duration-500 ${
                    status === "structuring" ? "w-1/3" : status === "discovering" ? "w-2/3" : "w-11/12"
                  }`}
                />
              </div>
            </div>
          )}

          {/* Success State */}
          {status === "done" && (
            <div className="py-8 px-4 flex flex-col items-center justify-center text-center space-y-3">
              <div className="h-12 w-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center">
                <CheckCircle2 className="h-7 w-7" />
              </div>
              <h3 className="text-sm font-bold text-slate-900">Prospects Ready!</h3>
              <p className="text-xs text-slate-600">{statusMessage}</p>
            </div>
          )}

          {/* Error State */}
          {status === "error" && (
            <div className="py-6 px-4 flex flex-col items-center justify-center text-center space-y-3">
              <div className="h-10 w-10 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center">
                <AlertCircle className="h-6 w-6" />
              </div>
              <h3 className="text-sm font-bold text-slate-900">Discovery Encountered an Issue</h3>
              <p className="text-xs text-rose-600 max-w-md">{errorMessage}</p>
              <button
                type="button"
                onClick={() => setStatus("idle")}
                className="mt-2 px-4 py-2 bg-slate-900 text-white rounded-lg text-xs font-semibold hover:bg-slate-800 transition"
              >
                Modify Targeting & Try Again
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
