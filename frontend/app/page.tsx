"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { fetchWorkspaces, createWorkspace } from "@/lib/api";
import { Workspace } from "@/lib/types";
import { Building2, Loader2, ArrowRight, PlusCircle } from "lucide-react";
import Link from "next/link";

export default function RootPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [newWsName, setNewWsName] = useState("");
  const [creatingWs, setCreatingWs] = useState(false);

  useEffect(() => {
    // 1. Guard against destroying auth hash or query tokens:
    // If arriving with auth callback parameters (hash or query), forward immediately to /auth/callback
    if (typeof window !== "undefined") {
      const hash = window.location.hash || "";
      const search = window.location.search || "";
      if (
        hash.includes("access_token") ||
        hash.includes("error") ||
        search.includes("code=") ||
        search.includes("error=")
      ) {
        router.replace(`/auth/callback${search}${hash}`);
        return;
      }
    }

    let isMounted = true;

    async function init() {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!isMounted) return;

      if (!session) {
        router.push("/login");
        return;
      }

      try {
        const wsList = await fetchWorkspaces();
        if (!isMounted) return;
        setWorkspaces(wsList);
        if (wsList.length > 0) {
          // Minimal entry: automatically redirect to the first workspace's prospects queue
          router.push(`/workspaces/${wsList[0].id}/prospects`);
        } else {
          setLoading(false);
        }
      } catch (err: any) {
        if (!isMounted) return;
        setError(err.message || "Failed to load workspaces");
        setLoading(false);
      }
    }

    init();

    return () => {
      isMounted = false;
    };
  }, [router]);

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWsName.trim()) return;
    setCreatingWs(true);
    setError(null);
    try {
      const created = await createWorkspace(newWsName.trim());
      router.push(`/workspaces/${created.id}/prospects`);
    } catch (err: any) {
      setError(err.message || "Failed to create workspace");
      setCreatingWs(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen w-full items-center justify-center flex-col gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        <p className="text-sm text-slate-500 font-medium">Entering Prospectra Workspace...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-md bg-white rounded-xl shadow-sm border border-slate-200 p-8 text-center">
        <div className="h-12 w-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-4">
          <Building2 className="h-6 w-6" />
        </div>
        <h1 className="text-xl font-bold text-slate-900 mb-2">Welcome to Prospectra</h1>
        <p className="text-sm text-slate-600 mb-6">
          {workspaces.length > 0
            ? "Select a workspace to enter your prospecting queue."
            : "Name your prospecting workspace to start discovering verified leads."}
        </p>

        {error && (
          <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 text-left">
            {error}
          </div>
        )}

        {workspaces.length > 0 ? (
          <div className="space-y-2">
            {workspaces.map((ws) => (
              <Link
                key={ws.id}
                href={`/workspaces/${ws.id}/prospects`}
                className="flex items-center justify-between p-3 rounded-lg border border-slate-200 hover:bg-slate-50 transition text-left"
              >
                <div>
                  <div className="font-medium text-slate-900">{ws.name}</div>
                  <div className="text-xs text-slate-500">{ws.slug}</div>
                </div>
                <ArrowRight className="h-4 w-4 text-slate-400" />
              </Link>
            ))}
          </div>
        ) : (
          <form onSubmit={handleCreateWorkspace} className="space-y-3 text-left">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Workspace Name
              </label>
              <input
                type="text"
                value={newWsName}
                onChange={(e) => setNewWsName(e.target.value)}
                placeholder="e.g. Growth Marketers, Apex Agency"
                required
                className="w-full text-xs p-2.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              type="submit"
              disabled={creatingWs || !newWsName.trim()}
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 text-xs font-bold text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
            >
              {creatingWs ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <PlusCircle className="h-4 w-4" />
              )}
              <span>Create Workspace & Start</span>
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
