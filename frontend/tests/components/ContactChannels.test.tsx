import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import React from "react";
import { ContactChannels } from "@/components/ContactChannels";

describe("ContactChannels", () => {
  it("renders active email and phone indicators when present", () => {
    const { container } = render(
      <ContactChannels
        websiteUrl="https://cafe.example.com"
        phone="+919876543210"
        emails={["owner@cafe.example.com"]}
      />
    );
    expect(container.querySelector("a[href='https://cafe.example.com']")).toBeInTheDocument();
    expect(container.querySelector(".text-blue-600")).toBeInTheDocument();
    expect(container.querySelector(".text-emerald-600")).toBeInTheDocument();
  });

  it("renders inactive indicators when channels are missing", () => {
    const { container } = render(
      <ContactChannels websiteUrl={null} phone={null} emails={[]} phones={[]} />
    );
    const disabledChannels = container.querySelectorAll(".text-slate-300");
    expect(disabledChannels.length).toBeGreaterThanOrEqual(3);
  });
});
