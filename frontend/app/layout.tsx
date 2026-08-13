import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CineForge AI Studio — Enterprise AI Video Production",
  description:
    "Research, script, storyboard, direct, render, edit and publish cinematic AI video — one integrated production pipeline.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-ink-950 font-sans text-zinc-200">{children}</body>
    </html>
  );
}
