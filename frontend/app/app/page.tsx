"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Plus, FolderKanban, Eye, Clock3, DollarSign, MonitorPlay, ArrowRight, Activity } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/store";
import { Project, AnalyticsOverview } from "@/lib/types";
import { StatCard, Card, Skeleton, Badge, EmptyState } from "@/components/ui";
import { LineChart, MiniSpark } from "@/components/charts";
import { STAGE_ICONS, cx } from "@/lib/utils";
import { Topbar } from "@/components/studio/Shell";

const STATUS_TONE: Record<string, "zinc" | "gold" | "green" | "violet"> = {
  draft: "zinc",
  pre_production: "violet",
  in_production: "gold",
  post_production: "gold",
  review: "violet",
  published: "green",
};

export default function DashboardPage() {
  const user = useAuth((s) => s.user);
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);

  useEffect(() => {
    api<Project[]>("/projects").then(setProjects).catch(() => setProjects([]));
    api<AnalyticsOverview>("/analytics/overview").then(setAnalytics).catch(() => setAnalytics(null));
  }, []);

  return (
    <div>
      <Topbar />
      <div className="mx-auto max-w-6xl px-6 py-8">
        {/* hero */}
        <div className="grid-noise relative mb-8 overflow-hidden rounded-3xl border border-gold-400/15 bg-gradient-to-br from-ink-800 via-ink-900 to-ink-950 p-8">
          <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-gold-400/10 blur-[100px]" />
          <div className="relative">
            <div className="label mb-2 text-gold-400">Welcome back, {user?.name?.split(" ")[0]}</div>
            <h1 className="font-display text-3xl font-bold tracking-tight text-zinc-50">
              What are we <span className="text-gradient-gold">producing</span> today?
            </h1>
            <p className="mt-2 max-w-xl text-sm text-zinc-400">
              Start with an idea — CineForge handles research, script, storyboard, shots, rendering, edit, SEO and publishing.
            </p>
            <Link href="/app/projects/new" className="btn-primary mt-6">
              <Plus className="h-4 w-4" /> New project
            </Link>
          </div>
        </div>

        {/* stats */}
        <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Projects" value={analytics ? String(analytics.totals.projects) : "—"} icon={<FolderKanban className="h-5 w-5" />} />
          <StatCard label="Total views" value={analytics ? analytics.totals.views.toLocaleString() : "—"} delta={analytics && analytics.totals.views > 0 ? "▲ live audience data" : undefined} icon={<Eye className="h-5 w-5" />} accent="blue" />
          <StatCard label="Watch time" value={analytics ? `${Math.round(analytics.totals.watch_time_min / 60)}h` : "—"} icon={<Clock3 className="h-5 w-5" />} accent="violet" />
          <StatCard label="Est. revenue" value={analytics ? `$${analytics.totals.revenue_usd.toLocaleString()}` : "—"} icon={<DollarSign className="h-5 w-5" />} accent="green" />
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* projects */}
          <div className="lg:col-span-2">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-display text-base font-semibold text-zinc-100">Recent projects</h2>
              <Link href="/app/projects" className="flex items-center gap-1 text-xs font-medium text-gold-400 hover:text-gold-500">
                All projects <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
            <div className="space-y-3">
              {!projects &&
                [0, 1, 2].map((i) => <Skeleton key={i} className="h-[104px] w-full rounded-2xl" />)}
              {projects?.length === 0 && (
                <EmptyState
                  icon="🎬"
                  title="No projects yet"
                  body="Create your first production and let the AI pipeline do the heavy lifting."
                  action={
                    <Link href="/app/projects/new" className="btn-primary">
                      <Plus className="h-4 w-4" /> New project
                    </Link>
                  }
                />
              )}
              {projects?.map((p, i) => (
                <motion.div key={p.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                  <Link href={`/app/projects/${p.id}`}>
                    <Card className="group flex items-center gap-4 p-4 transition hover:border-gold-400/25 hover:bg-ink-800/80">
                      <div className="grid h-12 w-12 shrink-0 place-items-center rounded-xl border border-white/8 bg-ink-850 text-2xl">
                        {STAGE_ICONS[p.current_stage] || "🎬"}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="truncate font-display text-sm font-semibold text-zinc-100 group-hover:text-gold-400">
                            {p.title}
                          </span>
                          <Badge tone={STATUS_TONE[p.status] || "zinc"}>{p.status.replace(/_/g, " ")}</Badge>
                        </div>
                        <div className="mt-1.5 flex items-center gap-3 text-xs text-zinc-500">
                          <span className="truncate">{p.topic}</span>
                          <span className="hidden sm:inline">·</span>
                          <span className="hidden sm:inline">
                            {p.category} · {p.language}
                          </span>
                        </div>
                        <div className="mt-2 flex items-center gap-2.5">
                          <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/8">
                            <div className="h-full rounded-full bg-gold-400 transition-all" style={{ width: `${p.progress}%` }} />
                          </div>
                          <span className="w-10 text-right text-[11px] font-semibold text-zinc-500">{p.progress}%</span>
                        </div>
                      </div>
                      <div className="hidden items-center gap-2 text-xs text-zinc-500 md:flex">
                        <MonitorPlay className="h-3.5 w-3.5" />
                        <span>{Object.values(p.outputs || {}).length}/18 stages</span>
                      </div>
                    </Card>
                  </Link>
                </motion.div>
              ))}
            </div>
          </div>

          {/* right rail */}
          <div className="space-y-6">
            <Card className="p-5">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
                  <Activity className="h-4 w-4 text-gold-400" /> Retention curve
                </h3>
                <span className="chip text-emerald-400">live</span>
              </div>
              {analytics ? (
                <LineChart data={analytics.retention.slice(0, 30)} label="retention" format={(v) => `${v}%`} />
              ) : (
                <Skeleton className="h-36 w-full" />
              )}
              <div className="mt-3 flex items-center justify-between text-xs text-zinc-500">
                <span>Avg retention</span>
                <span className="font-semibold text-zinc-200">
                  {analytics ? `${(analytics.retention.reduce((a, b) => a + b, 0) / analytics.retention.length).toFixed(1)}%` : "—"}
                </span>
              </div>
            </Card>

            <Card className="p-5">
              <h3 className="mb-4 text-sm font-semibold text-zinc-100">Published platforms</h3>
              <div className="space-y-3">
                {analytics?.platforms.length === 0 && <div className="text-xs text-zinc-600">Nothing published yet — run a pipeline to the Publishing stage.</div>}
                {analytics?.platforms.map((pl) => (
                  <div key={pl.url + pl.platform} className="flex items-center justify-between rounded-xl border border-white/8 bg-ink-850 px-3 py-2.5">
                    <div className="flex items-center gap-2.5">
                      <span className="text-base">{pl.platform === "youtube" ? "▶️" : pl.platform === "tiktok" ? "🎵" : pl.platform === "facebook" ? "📘" : pl.platform === "instagram" ? "📸" : "🎞️"}</span>
                      <span className="text-sm font-medium capitalize text-zinc-200">{pl.platform}</span>
                    </div>
                    <Badge tone={pl.status === "published" ? "green" : "gold"}>{pl.status}</Badge>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-5">
              <h3 className="mb-4 text-sm font-semibold text-zinc-100">AI credits</h3>
              <div className="flex items-center gap-4">
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/8">
                  <motion.div
                    className="h-full rounded-full bg-gradient-to-r from-violet-500 to-gold-400"
                    initial={{ width: 0 }}
                    animate={{ width: "58%" }}
                    transition={{ duration: 0.8, delay: 0.2 }}
                  />
                </div>
                <span className="text-xs font-bold text-zinc-200">58%</span>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-zinc-500">
                Plan usage is tracked per project and render. Upgrade anytime from Settings → Billing.
              </p>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
