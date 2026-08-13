"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Search } from "lucide-react";
import { api } from "@/lib/api";
import { Project } from "@/lib/types";
import { Badge, Card, EmptyState, Input, Skeleton } from "@/components/ui";
import { Topbar } from "@/components/studio/Shell";
import { STAGE_ICONS, fmtDate } from "@/lib/utils";

const STATUS_TONE: Record<string, "zinc" | "gold" | "green" | "violet"> = {
  draft: "zinc",
  pre_production: "violet",
  in_production: "gold",
  post_production: "gold",
  review: "violet",
  published: "green",
};

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    api<Project[]>("/projects").then(setProjects).catch(() => setProjects([]));
  }, []);

  const filtered = (projects || []).filter(
    (p) => p.title.toLowerCase().includes(q.toLowerCase()) || p.topic.toLowerCase().includes(q.toLowerCase())
  );

  return (
    <div>
      <Topbar />
      <div className="mx-auto max-w-6xl px-6 py-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight text-zinc-50">Projects</h1>
            <p className="mt-1 text-sm text-zinc-500">Every production runs the full 18-stage AI pipeline.</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-600" />
              <Input className="!w-64 !pl-9" placeholder="Search projects…" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <Link href="/app/projects/new" className="btn-primary">
              <Plus className="h-4 w-4" /> New project
            </Link>
          </div>
        </div>

        {!projects && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-56 w-full rounded-2xl" />
            ))}
          </div>
        )}

        {projects && filtered.length === 0 && (
          <EmptyState
            icon="🎬"
            title={q ? "No matches" : "No projects yet"}
            body={q ? `Nothing matches "${q}".` : "Create a project and let the AI production pipeline build it from an idea."}
            action={
              !q ? (
                <Link href="/app/projects/new" className="btn-primary">
                  <Plus className="h-4 w-4" /> New project
                </Link>
              ) : undefined
            }
          />
        )}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((p) => (
            <Link key={p.id} href={`/app/projects/${p.id}`}>
              <Card className="group flex h-full flex-col p-5 transition hover:-translate-y-0.5 hover:border-gold-400/25 hover:shadow-[0_16px_40px_-16px_rgba(245,179,1,0.25)]">
                <div className="mb-4 flex items-start justify-between">
                  <div className="grid h-11 w-11 place-items-center rounded-xl border border-white/8 bg-ink-850 text-xl transition group-hover:scale-105">
                    {STAGE_ICONS[p.current_stage] || "🎬"}
                  </div>
                  <Badge tone={STATUS_TONE[p.status] || "zinc"}>{p.status.replace(/_/g, " ")}</Badge>
                </div>
                <h3 className="font-display text-[15px] font-semibold leading-snug text-zinc-100 group-hover:text-gold-400">
                  {p.title}
                </h3>
                <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-zinc-500">{p.description || p.topic}</p>
                <div className="mt-auto pt-4">
                  <div className="mb-1.5 flex justify-between text-[11px] text-zinc-600">
                    <span>
                      {p.category} · {p.language}
                    </span>
                    <span>{fmtDate(p.updated_at)}</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-white/8">
                    <div className="h-full rounded-full bg-gold-400 transition-all" style={{ width: `${p.progress}%` }} />
                  </div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
