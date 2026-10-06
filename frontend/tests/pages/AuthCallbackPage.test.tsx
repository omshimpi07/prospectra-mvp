import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import AuthCallbackPage from "@/app/auth/callback/page";
import { supabase } from "@/lib/supabase";

const mockPush = vi.fn();
const mockReplace = vi.fn();
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
  }),
  useSearchParams: () => mockSearchParams,
}));

vi.mock("@/lib/supabase", () => {
  return {
    supabase: {
      auth: {
        getSession: vi.fn(),
        setSession: vi.fn(),
        exchangeCodeForSession: vi.fn(),
        onAuthStateChange: vi.fn(),
      },
    },
  };
});

describe("AuthCallbackPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams = new URLSearchParams();
    delete (window as any).location;
    (window as any).location = { hash: "", search: "", origin: "http://localhost:3000" };
    (supabase.auth.onAuthStateChange as any).mockReturnValue({
      data: { subscription: { unsubscribe: vi.fn() } },
    });
    (supabase.auth.getSession as any).mockResolvedValue({ data: { session: null } });
  });

  it("handles successful callback/session hydration via hash tokens", async () => {
    window.location.hash = "#access_token=valid_access&refresh_token=valid_refresh&type=signup";
    (supabase.auth.setSession as any).mockResolvedValue({
      data: { session: { user: { id: "u-1" } } },
      error: null,
    });

    render(<AuthCallbackPage />);

    await waitFor(() => {
      expect(supabase.auth.setSession).toHaveBeenCalledWith({
        access_token: "valid_access",
        refresh_token: "valid_refresh",
      });
      expect(mockReplace).toHaveBeenCalledWith("/");
    });
  });

  it("handles successful callback via PKCE code exchange", async () => {
    mockSearchParams = new URLSearchParams("code=valid_pkce_code");
    (supabase.auth.exchangeCodeForSession as any).mockResolvedValue({
      data: { session: { user: { id: "u-1" } } },
      error: null,
    });

    render(<AuthCallbackPage />);

    await waitFor(() => {
      expect(supabase.auth.exchangeCodeForSession).toHaveBeenCalledWith("valid_pkce_code");
      expect(mockReplace).toHaveBeenCalledWith("/");
    });
  });

  it("handles expired confirmation link in hash and displays error", async () => {
    window.location.hash =
      "#error=access_denied&error_code=otp_expired&error_description=Email+link+is+invalid+or+has+expired";

    render(<AuthCallbackPage />);

    expect(await screen.findByText("Verification Failed")).toBeInTheDocument();
    expect(
      screen.getByText("Email confirmation link is invalid or has expired. Please request a new confirmation email.")
    ).toBeInTheDocument();

    await waitFor(
      () => {
        expect(mockReplace).toHaveBeenCalledWith(
          expect.stringContaining("/login?error=")
        );
      },
      { timeout: 3000 }
    );
  });
});
