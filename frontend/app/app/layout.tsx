"use client";
import { StudioSidebar, ChatFAB } from "@/components/studio/Sidebar";
import { ChatPanel } from "@/components/studio/ChatPanel";
import { StudioShell } from "@/components/studio/Shell";

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  return (
    <StudioShell>
      <div className="flex min-h-screen">
        <StudioSidebar />
        <div className="min-w-0 flex-1">{children}</div>
      </div>
      <ChatFAB />
      <ChatPanel />
    </StudioShell>
  );
}
