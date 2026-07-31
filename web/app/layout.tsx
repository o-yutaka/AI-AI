import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import "./demo.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://o-yutaka.github.io/AI-AI/"),
  title: "AI Agent Control Plane | BLACK",
  description:
    "Interactive AI agent control-plane demo with OpenAI-compatible planning, tool allow-lists, approvals, and audit traces.",
  openGraph: {
    title: "AI Agent Control Plane",
    description:
      "OpenAI-compatible candidate planning, allow-listed tools, human approval, and auditable execution.",
    type: "website",
    url: "https://o-yutaka.github.io/AI-AI/",
  },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
