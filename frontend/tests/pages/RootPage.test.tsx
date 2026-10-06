import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import RootPage from "@/app/page";
import { supabase } from "@/lib/supabase";
import { fetchWorkspaces } from "@/lib/api";

const mockPush = vi.fn();
const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
  }),
}));

vi.mock("@/lib/supabase", () => {
  return {
    supabase: {
      auth: {
        getSession: vi.fn(),
      },
    },
  };
});

vi.mock("@/lib/api", () => ({
  fetchWorkspaces: vi.fn(),
  createWorkspace: vi.fn(),
}));

describe("RootPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    delete (window as any).location;
    (window as any).location = { hash: "", search: "", origin: "http://localhost:3000" };
  });

  it("performs normal authenticated root redirect to workspace prospects", async () => {
    (supabase.auth.getSession as any).mockResolvedValue({
      data: { session: { user: { id: "u-1" } } },
    });
    (fetchWorkspaces as any).mockResolvedValue([
      { id: "ws-1", name: "Default Workspace", slug: "default" },
    ]);

    render(<RootPage />);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/workspaces/ws-1/prospects");
    });
  });

  it("redirects unauthenticated user without tokens to /login", async () => {
    (supabase.auth.getSession as any).mockResolvedValue({
      data: { session: null },
    });

    render(<RootPage />);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/login");
    });
  });

  it("guards against premature redirect and forwards auth hash tokens to /auth/callback", async () => {
    window.location.hash = "#access_token=token123&refresh_token=refresh123&type=signup";
    (supabase.auth.getSession as any).mockResolvedValue({
      data: { session: null },
    });

    render(<RootPage />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith(
        "/auth/callback#access_token=token123&refresh_token=refresh123&type=signup"
      );
      // Ensure it NEVER called push('/login')
      expect(mockPush).not.toHaveBeenCalledWith("/login");
    });
  });
});
