import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { ScoreBadge } from "@/components/ScoreBadge";

describe("ScoreBadge", () => {
  it("renders high priority score with emerald styling and percentage", () => {
    render(<ScoreBadge score={0.92} />);
    expect(screen.getByText("92%")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
  });

  it("renders medium priority score with amber styling", () => {
    render(<ScoreBadge score={0.68} />);
    expect(screen.getByText("68%")).toBeInTheDocument();
    expect(screen.getByText("Med")).toBeInTheDocument();
  });

  it("renders low priority score with slate styling", () => {
    render(<ScoreBadge score={0.35} />);
    expect(screen.getByText("35%")).toBeInTheDocument();
    expect(screen.getByText("Low")).toBeInTheDocument();
  });
});
