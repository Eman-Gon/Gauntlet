import type { Metadata } from "next";
import "../index.css";

export const metadata: Metadata = {
  title: "Gauntlet - Autonomous burden of proof for the agentic web",
  description: "Vet agents, claims, and buyer flows before trusting them.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
