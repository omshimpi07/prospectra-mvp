import "./globals.css";
import React from "react";
import { Providers } from "@/lib/providers";

export const metadata = {
  title: "Prospectra — Prospect Intelligence & Workspace",
  description: "B2B Prospect Intelligence and Qualification Platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
