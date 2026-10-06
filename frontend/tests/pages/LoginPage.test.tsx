import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import LoginPage from "@/app/login/page";
import { supabase } from "@/lib/supabase";

const mockPush = vi.fn();
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useSearchParams: () => mockSearchParams,
}));

vi.mock("@/lib/supabase", () => {
  return {
    supabase: {
      auth: {
        signUp: vi.fn(),
        signInWithPassword: vi.fn(),
        resend: vi.fn(),
      },
    },
  };
});

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams = new URLSearchParams();
  });

  it("sets emailRedirectTo on signUp", async () => {
    (supabase.auth.signUp as any).mockResolvedValue({
      data: { user: { id: "u-1" } },
      error: null,
    });

    render(<LoginPage />);

    // Switch to Sign Up
    fireEvent.click(screen.getByText("Need an account? Sign Up"));

    // Fill form
    fireEvent.change(screen.getByPlaceholderText("seller@example.com"), {
      target: { value: "newuser@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("********"), {
      target: { value: "SecurePass123!" },
    });

    // Submit
    fireEvent.click(screen.getByRole("button", { name: "Sign Up" }));

    await waitFor(() => {
      expect(supabase.auth.signUp).toHaveBeenCalledWith({
        email: "newuser@example.com",
        password: "SecurePass123!",
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback`,
        },
      });
    });

    expect(
      await screen.findByText(/Please check your email to confirm your account/)
    ).toBeInTheDocument();
  });

  it("displays confirmation errors from search params", async () => {
    mockSearchParams = new URLSearchParams(
      "error=Email confirmation link is invalid or has expired."
    );

    render(<LoginPage />);

    expect(
      await screen.findByText("Email confirmation link is invalid or has expired.")
    ).toBeInTheDocument();
    expect(screen.getByText("Resend confirmation email")).toBeInTheDocument();
  });

  it("handles resend confirmation flow when sign-in fails with unconfirmed email", async () => {
    (supabase.auth.signInWithPassword as any).mockResolvedValue({
      data: { session: null },
      error: new Error("Email not confirmed"),
    });
    (supabase.auth.resend as any).mockResolvedValue({
      data: {},
      error: null,
    });

    render(<LoginPage />);

    fireEvent.change(screen.getByPlaceholderText("seller@example.com"), {
      target: { value: "unconfirmed@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("********"), {
      target: { value: "MyPassword123" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Sign In" }));

    const resendBtn = await screen.findByText("Resend confirmation email");
    expect(resendBtn).toBeInTheDocument();

    fireEvent.click(resendBtn);

    await waitFor(() => {
      expect(supabase.auth.resend).toHaveBeenCalledWith({
        type: "signup",
        email: "unconfirmed@example.com",
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback`,
        },
      });
    });

    expect(
      await screen.findByText(/Confirmation email resent/)
    ).toBeInTheDocument();
  });
});
