"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Plus, XCircle, MonitorPlay, Layers, Cpu, Clock3, Download } from "lucide-react";
import { api } from "@/lib/api";
import { Project, RenderJob } from "@/lib/types";
import { Badge, Button, Card, EmptyState, Input, Modal, Select, Skeleton, StatCard } from "@/components/ui";
import { Topbar } from "@/components/studio/Shell";
import { cx, fmtDate } from "@/lib/utils";

const JOB_TONE: Record<string, "zinc" | "gold" | "green" | "red" | "violet"> = {
  queued: "zinc",
  rendering: "gold",
  completed: "green",
  failed: "red",
  cancelled: "zinc",
};

export default function RenderQueuePage() {
  const [jobs, setJobs] = useState<RenderJob[] | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [open, setOpen] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [sceneLabel, setSceneLabel] = useState("");
  const [resolution, setResolution] = useState("1080p");
  const [model, setModel] = useState("cineforge-1.0");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const [j, p] = await Promise.all([api<RenderJob[]>("/render/jobs"), api<Project[]>("/projects")]);
    setJobs(j);
    setProjects(p);
  };

  useEffect(() => {
    load().catch(() => {});
    const t = setInterval(load, 2500); // live-ish progress while rendering
    return () => clearInterval(t);
  }, []);

  const enqueue = async () => {
    if (!projectId) return;
    setBusy(true);
    try {
      await api("/render/jobs", {
        method: "POST",
        body: { project_id: projectId, scene_label: sceneLabel || "Full timeline", resolution, model },
      });
      setOpen(false);
      setSceneLabel("");
      load();
    } finally {
      setBusy(false);
    }
  };

  const cancel = async (jid: string) => {
    await api(`/render/jobs/${jid}/cancel`, { method: "POST" });
    load();
  };

  const running = (jobs || []).filter((j) => j.status === "rendering").length;
  const done = (jobs || []).filter((j) => j.status === "completed").length;

  return (
    <div>
      <Topbar />
      <div className="mx-auto max-w-6xl px-6 py-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight text-zinc-50">Render queue</h1>
            <p className="mt-1 text-sm text-zinc-500">Distributed rendering jobs — providers are swappable without touching the pipeline.</p>
          </div>
          <Button onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" /> Enqueue render
          </Button>
        </div>

        <div className="mb-6 grid gap-4 sm:grid-cols-3">
          <StatCard label="Queued / rendering" value={String(running)} icon={<Cpu className="h-5 w-5" />} />
          <StatCard label="Completed" value={String(done)} icon={<MonitorPlay className="h-5 w-5" />} accent="green" />
          <StatCard label="Active workers" value={String(Math.max(1, Math.ceil(running / 2)))} icon={<Layers className="h-5 w-5" />} accent="violet" />
        </div>

        {!jobs && <Skeleton className="h-64 w-full rounded-2xl" />}
        {jobs && jobs.length === 0 && (
          <EmptyState
            icon="🖥️"
            title="No render jobs yet"
            body="Enqueue a render to send scenes to the render farm. Progress streams live."
            action={<Button onClick={() => setOpen(true)}><Plus className="h-4 w-4" /> Enqueue render</Button>}
          />
        )}

        <div className="space-y-3">
          {jobs?.map((j) => (
            <motion.div key={j.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <Card className="flex flex-wrap items-center gap-4 p-4">
                <div className={cx("grid h-11 w-11 shrink-0 place-items-center rounded-xl border", j.status === "completed" ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-400" : j.status === "rendering" ? "border-gold-400/25 bg-gold-400/10 text-gold-400" : "border-white/8 bg-ink-850 text-zinc-500")}>
                  {j.status === "rendering" ? <Clock3 className="h-5 w-5 animate-pulse" /> : <MonitorPlay className="h-5 w-5" />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate font-display text-sm font-semibold text-zinc-100">{j.scene_label}</span>
                    <Badge tone={JOB_TONE[j.status] || "zinc"}>{j.status}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-zinc-500">
                    {j.model} · {j.resolution} · {j.fps} fps · priority {j.priority} · enqueued {fmtDate(j.created_at)}
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/8">
                    <div
                      className={cx("h-full rounded-full transition-all", j.status === "completed" ? "bg-emerald-400" : j.status === "failed" ? "bg-red-500" : "bg-gold-400")}
                      style={{ width: `${j.progress}%` }}
                    />
                  </div>
                  {(j.clips?.length || 0) > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {j.clips.map((c: any) => (
                        <span key={c.id} className={cx("chip", c.status === "completed" ? "text-emerald-400" : c.status === "failed" ? "text-red-400" : "text-zinc-500")}>
                          {c.status === "completed" ? "✅" : c.status === "failed" ? "❌" : "⏳"} {c.provider} · {c.score ?? "—"}
                        </span>
                      ))}
                    </div>
                  )}
                  {j.final_url && (
                    <div className="mt-3 flex max-w-md flex-col gap-2">
                      <video src={`/api/backend${j.final_url}`} controls muted playsInline preload="metadata" className="w-full rounded-lg bg-black" />
                      <a
                        href={`/api/backend${j.final_url}`}
                        download={`cineforge-${j.scene_label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "film"}-${j.id.slice(0, 8)}.mp4`}
                        className="btn-ghost w-fit !py-1.5 text-xs"
                      >
                        <Download className="h-3.5 w-3.5" /> Download MP4
                      </a>
                    </div>
                  )}
                </div>
                <div className="flex w-40 items-center justify-end gap-2">
                  <span className={cx("font-mono text-sm font-bold", j.status === "completed" ? "text-emerald-400" : j.status === "failed" ? "text-red-400" : "text-gold-400")}>
                    {Math.round(j.progress)}%
                  </span>
                  {j.status === "queued" || j.status === "rendering" ? (
                    <button onClick={() => cancel(j.id)} className="rounded-lg p-1.5 text-zinc-600 hover:bg-red-500/10 hover:text-red-400" title="Cancel job">
                      <XCircle className="h-4 w-4" />
                    </button>
                  ) : null}
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title="Enqueue render job">
        <div className="space-y-4">
          <div>
            <label className="label mb-1.5 block">Project</label>
            <Select options={projects.map((p) => ({ id: p.id, label: p.title }))} value={projectId} onChange={setProjectId} placeholder="Select project…" />
          </div>
          <div>
            <label className="label mb-1.5 block">Scene / label</label>
            <Input value={sceneLabel} onChange={(e) => setSceneLabel(e.target.value)} placeholder="Full timeline (default)" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label mb-1.5 block">Resolution</label>
              <Select options={[{ id: "720p", label: "720p" }, { id: "1080p", label: "1080p" }, { id: "2K", label: "2K" }, { id: "4K", label: "4K" }]} value={resolution} onChange={setResolution} />
            </div>
            <div>
              <label className="label mb-1.5 block">Model</label>
              <Select options={[{ id: "cineforge-1.0", label: "CineForge 1.0" }, { id: "cineforge-4k-pro", label: "CineForge 4K Pro" }, { id: "provider-default", label: "Provider default" }]} value={model} onChange={setModel} />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={enqueue} disabled={busy || !projectId}>{busy ? "Enqueuing…" : "Enqueue"}</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
