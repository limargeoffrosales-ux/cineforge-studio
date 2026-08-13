"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Clapperboard,
  LayoutDashboard,
  FolderKanban,
  MonitorPlay,
  UserSquare2,
  Globe2,
  BarChart3,
  Library,
  Settings,
  LogOut,
  MessageSquare,
  Film,
} from "lucide-react";
import { useAuth, useUi } from "@/lib/store";
import { clearToken } from "@/lib/api";
import { initials, paletteFor } from "@/lib/utils";

const NAV = [
  {
    section: "Studio",
    items: [
      { href: "/app", label: "Dashboard", icon: LayoutDashboard },
      { href: "/app/projects", label: "Projects", icon: FolderKanban },
    ],
  },
  {
    section: "Production",
    items: [
      { href: "/app/video", label: "Video Lab", icon: Film },
      { href: "/app/render", label: "Render Queue", icon: MonitorPlay },
    ],
  },
  {
    section: "Resources",
    items: [
      { href: "/app/library?tab=characters", label: "Character Studio", icon: UserSquare2 },
      { href: "/app/library?tab=environments", label: "Environment Builder", icon: Globe2 },
      { href: "/app/library?tab=assets", label: "Assets & Brand", icon: Library },
    ],
  },
  {
    section: "Insights",
    items: [
      { href: "/app/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/app/settings", label: "Settings & Billing", icon: Settings },
    ],
  },
];

export function StudioSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const collapsed = useUi((s) => s.sidebarCollapsed);
  const user = useAuth((s) => s.user);

  const logout = () => {
    clearToken();
    useAuth.getState().setUser(null);
    router.push("/login");
  };

  const isActive = (href: string) => {
    const base = href.split("?")[0];
    if (base === "/app") return pathname === "/app";
    if (base === "/app/projects") return pathname.startsWith("/app/projects");
    return pathname === base;
  };

  return (
    <aside
      className={`sticky top-0 z-30 flex h-screen shrink-0 flex-col border-r border-white/8 bg-ink-900/60 backdrop-blur-xl transition-all ${
        collapsed ? "w-[72px]" : "w-60"
      }`}
    >
      <div className={`flex items-center gap-2.5 px-4 py-5 ${collapsed ? "justify-center px-2" : ""}`}>
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-gold-400 to-amber-600 shadow-[0_0_22px_-4px_rgba(245,179,1,0.6)]">
          <Clapperboard className="h-5 w-5 text-ink-950" />
        </div>
        {!collapsed && (
          <div className="font-display text-[15px] font-bold tracking-tight text-zinc-100">
            CineForge <span className="text-gradient-gold">AI Studio</span>
          </div>
        )}
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto px-3 py-2">
        {NAV.map((section) => (
          <div key={section.section}>
            {!collapsed && <div className="label mb-2 px-3">{section.section}</div>}
            <div className="space-y-0.5">
              {section.items.map(({ href, label, icon: Icon }) => {
                const active = isActive(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    title={collapsed ? label : undefined}
                    className={`group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                      active ? "text-zinc-50" : "text-zinc-500 hover:bg-white/5 hover:text-zinc-200"
                    }`}
                  >
                    {active && (
                      <motion.div
                        layoutId="nav-pill"
                        className="absolute inset-0 rounded-xl border border-gold-400/25 bg-gold-400/10"
                        transition={{ type: "spring", stiffness: 400, damping: 32 }}
                      />
                    )}
                    <Icon className={`relative z-10 h-[18px] w-[18px] ${active ? "text-gold-400" : ""}`} />
                    {!collapsed && <span className="relative z-10">{label}</span>}
                    {!collapsed && active && <span className="relative z-10 ml-auto h-1.5 w-1.5 rounded-full bg-gold-400" />}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-white/8 p-3">
        {user && (
          <div className={`flex items-center gap-2.5 rounded-xl px-2 py-2 ${collapsed ? "justify-center" : ""}`}>
            <div
              className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-[11px] font-bold text-ink-950"
              style={{ background: paletteFor(user.avatar_seed || user.id)[0] }}
            >
              {initials(user.name || user.email)}
            </div>
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px] font-semibold text-zinc-200">{user.name}</div>
                <div className="truncate text-[11px] text-zinc-600">
                  {user.plan} · {user.role}
                </div>
              </div>
            )}
            {!collapsed && (
              <button onClick={logout} title="Sign out" className="rounded-lg p-1.5 text-zinc-500 hover:bg-white/10 hover:text-zinc-200">
                <LogOut className="h-4 w-4" />
              </button>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}

export function ChatFAB() {
  const setChatOpen = useUi((s) => s.setChatOpen);
  return (
    <button
      onClick={() => setChatOpen(true)}
      className="fixed bottom-5 right-5 z-40 grid h-12 w-12 place-items-center rounded-full bg-gradient-to-br from-gold-400 to-amber-600 text-ink-950 shadow-[0_8px_30px_-6px_rgba(245,179,1,0.6)] transition hover:scale-105 active:scale-95"
      title="AI Assistant"
    >
      <MessageSquare className="h-5 w-5" />
    </button>
  );
}
