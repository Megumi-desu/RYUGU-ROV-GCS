import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RYUGU ROV — Spectator Dashboard",
  description: "Live telemetry and camera feeds from the RYUGU ROV | KKI 2026",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="bg-bg">
      <body className="min-h-screen flex flex-col">{children}</body>
    </html>
  );
}
