"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { Pencil, Rocket, RefreshCw, ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import { PipelineStatus, Project, StageDef } from "@/lib/types";
import { Badge, Button, Card, Input, Kbd, Modal, Skeleton, Spinner, Tabs } from "@/components/ui";
import { Topbar } from "@/components/studio/Shell";
import { PipelineFlow } from "@/components/studio/PipelineFlow";
import { StageDetail } from "@/components/studio/StageDetail";
import { usePipelineSocket } from "@/lib/ws";
import {
  ScriptView,
  StoryboardView,
  ShotsView,
  CharactersView,
  EnvironmentsView,
  SeoView,
  PublishView,
  ProjectAnalyticsView,
} from "@/components/studio/ProjectViews";
import { fmtDate, STAGE_ICONS } from "@/lib/utils";

const TABS = [
  { id: "pipeline", label: "Pipeline" },
  { id: "script", label: "Script" },
  { id: "storyboard", label: "Storyboard" },
  { id: "shots", label: "Shots" },
  { id: "characters", label: "Characters" },
  { id: "environments", label: "Environments" },
  { id: "seo", label: "SEO" },
  { id: "publish", label: "Publish" },
  { id: "analytics", label: "Analytics" },
];

export default function ProjectStudioPage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [stages, setStages] = useState<StageDef[]>([]);
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [tab, setTab] = useState("pipeline");
  const [selectedStage, setSelectedStage] = useState("idea");
  const [starting, setStarting] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [analytics, setAnalytics] = useState<any>(null);

  const reload = useCallback(async () => {
    const [p, s, st] = await Promise.all([
      api<Project>(`/projects/${id}`),
      api<{ stages: StageDef[] }>("/pipeline/stages"),
      api<PipelineStatus>(`/pipeline/projects/${id}`),
    ]);
    setProject(p);
    setStages(s.stages);
    setStatus(st);
    setSelectedStage((cur) => cur || st.current_stage || "idea");
  }, [id]);

  useEffect(() => {
    reload().catch(() => {});
  }, [reload]);

  useEffect(() => {
    if (tab === "analytics" && project) {
      api(`/projects/${project.id}/analytics`).then(setAnalytics).catch(() => {});
    }
  }, [tab, project]);

  // live updates
  usePipelineSocket(id, (ev) => {
    if (ev.type === "stage_update") {
      setStatus((prev) => {
        if (!prev) return prev;
        const stages = { ...prev.stages };
        const st = stages[ev.stage_id!];
        if (st) {
          stages[ev.stage_id!] = {
            ...st,
            status: (ev.status as any) || st.status,
            progress: ev.progress ?? st.progress,
          };
        }
        return { ...prev, stages, current_stage: ev.stage_id || prev.current_stage, progress: ev.project_progress ?? prev.progress };
      });
    } else if (ev.type === "run_finished") {
      reload();
    } else if (ev.type === "poll") {
      setStatus((prev) => {
        if (!prev || !ev.stages) return prev;
        return { ...prev, stages: ev.stages, progress: ev.project_progress ?? prev.progress, running: ev.running ?? prev.running };
      });
    }
  });

  const runPipeline = async (startStage?: string) => {
    setStarting(startStage || "all");
    try {
      await api(`/pipeline/projects/${id}/run`, { method: "POST", body: startStage ? { start_stage: startStage } : {} });
      reload();
    } catch (e: any) {
      alert(e.message || "Could not start pipeline");
    } finally {
      setStarting(null);
    }
  };

  // keyboard shortcut: ⌘R / Ctrl+R runs the pipeline (not while typing)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "r") {
        const target = e.target as HTMLElement;
        if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
        e.preventDefault();
        runPipeline();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, status?.running]);

  const saveEdits = async () => {
    await api(`/projects/${id}`, { method: "PATCH", body: { title: editTitle, description: editDesc } });
    setEditOpen(false);
    reload();
  };

  if (!project) {
    return (
      <div>
        <Topbar />
        <div className="grid h-[70vh] place-items-center">
          <Spinner className="h-7 w-7 text-gold-400" />
        </div>
      </div>
    );
  }

  const running = status?.running || false;
  const outputs = project.outputs || {};
  const selectedOutput = outputs[selectedStage];

  return (
    <div>
      <Topbar
        project={{ title: project.title, status: project.status, progress: project.progress }}
        onRun={() => runPipeline()}
        running={running}
        right={
          <button onClick={() => { setEditTitle(project.title); setEditDesc(project.description); setEditOpen(true); }} className="btn-ghost !px-3 !py-1.5 text-xs" title="Edit project">
            <Pencil className="h-3.5 w-3.5" />
          </button>
        }
      />

      <div className="mx-auto max-w-[1500px] px-6 py-6">
        {/* project header */}
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <Link href="/app/projects" className="mb-2 inline-flex items-center gap-1.5 text-xs text-zinc-600 hover:text-zinc-400">
              <ArrowLeft className="h-3.5 w-3.5" /> Projects
            </Link>
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="font-display text-2xl font-bold tracking-tight text-zinc-50">{project.title}</h1>
              <Badge tone={project.status === "published" ? "green" : project.status === "draft" ? "zinc" : "gold"}>{project.status.replace(/_/g, " ")}</Badge>
              {project.current_stage && <Badge tone="violet">{STAGE_ICONS[project.current_stage]} {project.current_stage.replace(/_/g, " ")}</Badge>}
            </div>
            <p className="mt-1.5 max-w-2xl text-sm text-zinc-500">{project.description || project.topic}</p>
            <div className="mt-2.5 flex flex-wrap gap-1.5 text-xs">
              <span className="chip">🎯 {project.topic}</span>
              <span className="chip">📦 {project.category}</span>
              <span className="chip">🗣 {project.tone}</span>
              <span className="chip">🌐 {project.language}</span>
              <span className="chip">⏱ target {Math.round(project.target_duration / 60)}:{String(project.target_duration % 60).padStart(2, "0")}</span>
              <span className="chip">🕒 {fmtDate(project.updated_at)}</span>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <span>Pipeline progress</span>
              <span className="font-bold text-gold-400">{project.progress}%</span>
            </div>
            <div className="h-2 w-56 overflow-hidden rounded-full bg-white/8">
              <motion.div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-gold-400" animate={{ width: `${project.progress}%` }} />
            </div>
            <div className="mt-1 flex items-center gap-2">
              {running ? (
                <span className="flex items-center gap-2 text-xs font-semibold text-gold-400">
                  <Spinner className="h-3.5 w-3.5" /> AI director at work…
                </span>
              ) : (
                <button onClick={() => runPipeline()} disabled={!!starting} className="btn-ghost !px-3 !py-1.5 text-xs">
                  <RefreshCw className="h-3.5 w-3.5" /> Re-run full pipeline
                </button>
              )}
              <span className="hidden text-[10px] text-zinc-700 md:inline"><Kbd>⌘</Kbd> <Kbd>R</Kbd></span>
            </div>
          </div>
        </div>

        {/* tabs */}
        <div className="mb-6 overflow-x-auto">
          <Tabs tabs={TABS} active={tab} onChange={setTab} />
        </div>

        {/* PIPELINE TAB */}
        {tab === "pipeline" && (
          <div className="grid gap-6 xl:grid-cols-[1fr_420px]">
            <div>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-display text-sm font-semibold text-zinc-300">Production pipeline — 18 stages</h2>
                {running && <Badge tone="gold"><Spinner className="mr-1 h-3 w-3" /> {status?.current_stage}</Badge>}
              </div>
              <PipelineFlow
                stages={stages}
                states={status?.stages || {}}
                selected={selectedStage}
                onSelect={setSelectedStage}
                running={running}
              />
            </div>
            <div className="xl:sticky xl:top-16 xl:h-fit">
              <Card className="p-5">
                <StageDetail
                  stage={stages.find((s) => s.id === selectedStage) || { id: selectedStage, name: selectedStage, phase: "", desc: "" }}
                  state={status?.stages?.[selectedStage] || { status: "pending", progress: 0, started_at: null, completed_at: null, notes: "" }}
                  output={selectedOutput}
                />
                <div className="mt-5 flex items-center justify-between border-t border-white/8 pt-4">
                  <span className="text-xs text-zinc-600">Regenerate just this stage</span>
                  <Button variant="ghost" onClick={() => runPipeline(selectedStage)} disabled={running || !!starting} className="!py-1.5 text-xs">
                    {starting ? <Spinner className="h-3.5 w-3.5" /> : <Rocket className="h-3.5 w-3.5" />} Run from here
                  </Button>
                </div>
              </Card>
            </div>
          </div>
        )}

        {tab === "script" && <ScriptView project={project} />}
        {tab === "storyboard" && <StoryboardView project={project} />}
        {tab === "shots" && <ShotsView project={project} />}
        {tab === "characters" && <CharactersView project={project} />}
        {tab === "environments" && <EnvironmentsView project={project} />}
        {tab === "seo" && <SeoView project={project} />}
        {tab === "publish" && <PublishView project={project} onPublish={() => setTimeout(reload, 600)} />}
        {tab === "analytics" && <ProjectAnalyticsView analytics={analytics} />}
      </div>

      <Modal open={editOpen} onClose={() => setEditOpen(false)} title="Edit project">
        <div className="space-y-4">
          <div>
            <label className="label mb-1.5 block">Title</label>
            <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
          </div>
          <div>
            <label className="label mb-1.5 block">Description</label>
            <Input value={editDesc} onChange={(e) => setEditDesc(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setEditOpen(false)}>Cancel</Button>
            <Button onClick={saveEdits}>Save</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
