"use client";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, getToken } from "@/lib/api";
import { useAuth } from "@/lib/store";
import { Spinner } from "@/components/ui";

export function StudioShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const user = useAuth((s) => s.user);
  const setUser = useAuth((s) => s.setUser);
  const [loading, setLoading] = useState(!user);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    if (!user) {
      api("/auth/me")
        .then((u) => setUser(u))
        .catch(() => router.replace("/login"))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [user, router, setUser]);

  if (loading) {
    return (
      <div className="grid h-screen place-items-center">
        <div className="flex flex-col items-center gap-3">
          <Spinner className="h-7 w-7 text-gold-400" />
          <div className="text-sm text-zinc-500">Entering the studio…</div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

export function Topbar({
  project,
  onRun,
  running,
  right,
}: {
  project?: { title: string; status: string; progress: number } | null;
  onRun?: () => void;
  running?: boolean;
  right?: React.ReactNode;
}) {
  const pathname = usePathname();
  const crumbs =
    pathname.startsWith("/app/projects/")
      ? ["Projects", project?.title || "Project"]
      : pathname === "/app"
        ? ["Dashboard"]
        : pathname.split("/").filter(Boolean).slice(1).map((s) => s.charAt(0).toUpperCase() + s.slice(1));

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-4 border-b border-white/8 bg-ink-950/70 px-5 backdrop-blur-xl">
      <nav className="flex items-center gap-1.5 text-sm">
        {crumbs.map((c, i) => (
          <span key={i} className="flex items-center gap-1.5">
            {i > 0 && <span className="text-zinc-700">/</span>}
            <span className={i === crumbs.length - 1 ? "font-semibold text-zinc-100" : "text-zinc-500"}>{c}</span>
          </span>
        ))}
      </nav>

      <div className="flex items-center gap-3">
        {project && (
          <div className="hidden items-center gap-2.5 md:flex">
            <div className="h-1.5 w-24 overflow-hidden rounded-full bg-white/8">
              <div className="h-full rounded-full bg-gold-400 transition-all" style={{ width: `${project.progress}%` }} />
            </div>
            <span className="text-xs font-semibold text-zinc-500">{project.progress}%</span>
          </div>
        )}
        {onRun && (
          <button
            onClick={onRun}
            disabled={running}
            className="btn-primary !px-3.5 !py-1.5 text-xs"
            title="Run the AI production pipeline"
          >
            {running ? (
              <>
                <Spinner className="h-3.5 w-3.5" /> Producing…
              </>
            ) : (
              <>▶ Run pipeline</>
            )}
          </button>
        )}
        {right}
      </div>
    </header>
  );
}
