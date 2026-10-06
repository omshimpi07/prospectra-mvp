"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { Loader2, AlertCircle } from "lucide-react";
import Link from "next/link";

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let resolved = false;

    const handleSuccess = () => {
      if (resolved) return;
      resolved = true;
      router.replace("/");
    };

    const handleError = (description: string) => {
      if (resolved) return;
      resolved = true;
      setErrorMsg(description);
      setTimeout(() => {
        router.replace(`/login?error=${encodeURIComponent(description)}`);
      }, 2000);
    };

    async function processAuth() {
      // 1. Check query parameters for errors
      const queryError = searchParams.get("error");
      const queryErrorDescription = searchParams.get("error_description");
      const queryErrorCode = searchParams.get("error_code");
      if (queryError || queryErrorDescription || queryErrorCode) {
        const desc =
          queryErrorCode === "otp_expired"
            ? "Email confirmation link is invalid or has expired. Please request a new confirmation email."
            : queryErrorDescription || queryError || "Authentication error occurred";
        handleError(desc);
        return;
      }

      // 2. Check hash fragments for errors or tokens
      if (typeof window !== "undefined" && window.location.hash) {
        const hash = window.location.hash.startsWith("#")
          ? window.location.hash.substring(1)
          : window.location.hash;
        const params = new URLSearchParams(hash);
        const hashError = params.get("error");
        const hashErrorDescription = params.get("error_description");
        const hashErrorCode = params.get("error_code");

        if (hashError || hashErrorDescription || hashErrorCode) {
          const desc =
            hashErrorCode === "otp_expired"
              ? "Email confirmation link is invalid or has expired. Please request a new confirmation email."
              : hashErrorDescription || hashError || "Authentication error occurred";
          handleError(desc);
          return;
        }

        const accessToken = params.get("access_token");
        const refreshToken = params.get("refresh_token");
        if (accessToken && refreshToken) {
          try {
            const { error: setSessionErr } = await supabase.auth.setSession({
              access_token: accessToken,
              refresh_token: refreshToken,
            });
            if (setSessionErr) {
              handleError(setSessionErr.message);
              return;
            }
            handleSuccess();
            return;
          } catch (e: any) {
            handleError(e?.message || "Failed to persist authentication session");
            return;
          }
        }
      }

      // 3. Check PKCE authorization code
      const code = searchParams.get("code");
      if (code) {
        try {
          const { error: exchangeErr } = await supabase.auth.exchangeCodeForSession(code);
          if (exchangeErr) {
            handleError(exchangeErr.message);
            return;
          }
          handleSuccess();
          return;
        } catch (e: any) {
          handleError(e?.message || "Failed to exchange authorization code");
          return;
        }
      }

      // 4. Check if session is already active
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (session) {
        handleSuccess();
        return;
      }

      // 5. Fallback timeout if no event or session occurs
      const timer = setTimeout(() => {
        if (!resolved) {
          handleError("Authentication verification timed out. Please try logging in again.");
        }
      }, 5000);

      return () => clearTimeout(timer);
    }

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (
        (event === "SIGNED_IN" || event === "TOKEN_REFRESHED" || event === "INITIAL_SESSION") &&
        session
      ) {
        handleSuccess();
      }
    });

    processAuth();

    return () => {
      subscription.unsubscribe();
    };
  }, [router, searchParams]);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-sm bg-white rounded-xl shadow-sm border border-slate-200 p-8 text-center">
        {errorMsg ? (
          <div className="space-y-4">
            <div className="h-12 w-12 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mx-auto">
              <AlertCircle className="h-6 w-6" />
            </div>
            <h2 className="text-base font-semibold text-slate-900">Verification Failed</h2>
            <p className="text-xs text-rose-600 bg-rose-50 p-3 rounded-lg border border-rose-200 text-left">
              {errorMsg}
            </p>
            <Link
              href="/login"
              className="inline-block w-full py-2 px-4 text-xs font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition"
            >
              Return to Login
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto" />
            <h2 className="text-base font-semibold text-slate-900">Verifying Confirmation</h2>
            <p className="text-xs text-slate-500">
              Confirming your email and establishing your secure session...
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-slate-50 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      }
    >
      <AuthCallbackContent />
    </Suspense>
  );
}
