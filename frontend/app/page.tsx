"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { fetchWorkspaces } from "@/lib/api";
import { Workspace } from "@/lib/types";
import { Building2, Loader2, ArrowRight } from "lucide-react";
import Link from "next/link";

export default function RootPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function init() {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push("/login");
        return;
      }

      try {
        const wsList = await fetchWorkspaces();
        setWorkspaces(wsList);
        if (wsList.length > 0) {
          // Minimal entry: automatically redirect to the first workspace's prospects queue
          router.push(`/workspaces/${wsList[0].id}/prospects`);
        } else {
          setLoading(false);
        }
      } catch (err: any) {
        setError(err.message || "Failed to load workspaces");
        setLoading(false);
      }
    }
    init();
  }, [router]);

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
          {error ? error : "No workspaces found for your account. Please create one to begin."}
        </p>

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
          <Link
            href="/login"
            className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition"
          >
            Sign in with another account
          </Link>
        )}
      </div>
    </div>
  );
}
