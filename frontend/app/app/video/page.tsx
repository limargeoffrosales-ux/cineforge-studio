"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Clapperboard, Download, Film, Gauge, ImagePlus, Layers, Play, RefreshCw, Route, Scissors, Sparkles, Trophy, Wand2, Upload,
} from "lucide-react";
import { api, apiUpload } from "@/lib/api";
import { Project, RenderJob } from "@/lib/types";
import { Badge, Button, Card, EmptyState, Progress, Select, Skeleton, Spinner, StatCard } from "@/components/ui";
import { Topbar } from "@/components/studio/Shell";
import { cx } from "@/lib/utils";

interface ProviderInfo {
  id: string; name: string; vendor: string; api: string; strengths: string[]; weaknesses: string[];
  max_duration_s: number; max_res: string; native_audio: boolean; image_to_video: boolean;
  character_consistency: string; camera_control: string; price_per_sec: number; quality: Record<string, number>;
  director_note: string; configured: boolean;
}

const QUALITY_LABELS: [string, keyof ProviderInfo["quality"]][] = [
  ["Physics", "physics"], ["Motion", "motion"], ["Consistency", "consistency"], ["Aesthetic", "aesthetic"], ["Adherence", "adherence"],
];

const PROVIDER_EMOJI: Record<string, string> = {
  "veo-3.1": "🌊", "runway-gen-4.5": "🎨", "kling-3.0": "🥋", "seedance-2.0": "⚡",
};

export default function VideoLabPage() {
  const [providers, setProviders] = useState<ProviderInfo[] | null>(null);
  const [benchmark, setBenchmark] = useState<any>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [project, setProject] = useState<Project | null>(null);
  const [jobs, setJobs] = useState<RenderJob[]>([]);
  const [providerOverride, setProviderOverride] = useState("auto");
  const [resolution, setResolution] = useState("480p");
  const [compareScene, setCompareScene] = useState("0");
  const [busy, setBusy] = useState<string | null>(null);
  const [tab, setTab] = useState("compare");

  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [i2vPrompt, setI2vPrompt] = useState("");
  const [i2vDuration, setI2vDuration] = useState("8");
  const [i2vStyle, setI2vStyle] = useState("auto");
  const [i2vMovement, setI2vMovement] = useState("auto");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const load = async () => {
    try {
      const [pv, bm, pr, jb] = await Promise.all([
        api<{ providers: ProviderInfo[]; benchmark: any }>("/video/providers"),
        api("/video/benchmark"),
        api<Project[]>("/projects"),
        api<RenderJob[]>("/render/jobs"),
      ]);
      setProviders(pv.providers);
      setBenchmark(bm.ensemble || pv.benchmark?.ensemble);
      setProjects(pr);
      setJobs(jb);
      if (!projectId && pr.length) setProjectId(pr[0].id);
    } catch {
      /* offline */
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (projectId) api<Project>(`/projects/${projectId}`).then(setProject).catch(() => {});
  }, [projectId]);

  const plan = project?.outputs?.video_generation;
  const planScenes = plan?.scenes || [];
  const routedProviders = new Set(planScenes.flatMap((s: any) => s.clips.map((c: any) => c.provider)));
  const completedJobs = jobs.filter((j) => j.status === "completed");
  const runningJobs = jobs.filter((j) => j.status === "rendering");
  const assembledJobs = jobs.filter((j) => j.final_url);
  const latestFilm = assembledJobs[0] || null;

  const enqueue = async (model: string, sceneLabel = "Full timeline") => {
    if (!projectId) return;
    setBusy(model === "compare" ? "compare" : "render");
    try {
      await api("/render/jobs", {
        method: "POST",
        body: {
          project_id: projectId,
          scene_label: model === "compare" ? compareScene : sceneLabel,
          model: model === "compare" ? "compare" : providerOverride,
          resolution,
        },
      });
    } finally {
      setBusy(null);
      load();
    }
  };

  const assemble = async (jid: string) => {
    await api(`/render/jobs/${jid}/assemble`, { method: "POST" });
    load();
  };

  const onPickImage = (f: File | null) => {
    setUploadError(null);
    setImageFile(f);
    if (!f) {
      setImagePreview(null);
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setImagePreview(String(reader.result));
    reader.readAsDataURL(f);
  };

  const startImageVideo = async () => {
    if (!imageFile) return;
    setUploading(true);
    setUploadError(null);
    try {
      const form = new FormData();
      form.append("file", imageFile);
      form.append("prompt", i2vPrompt);
      form.append("duration_s", i2vDuration);
      form.append("style", i2vStyle);
      form.append("movement", i2vMovement);
      await apiUpload("/video/image2video", form);
      load();
    } catch (e: any) {
      setUploadError(e?.message || "Upload failed — is the backend running?");
    } finally {
      setUploading(false);
    }
  };

  const reshoot = async (jid: string, clipId: string) => {
    await api(`/render/jobs/${jid}/clips/${clipId}/reshoot`, { method: "POST", body: { provider: "kling-3.0" } });
    load();
  };

  const avg = (q: Record<string, number>) => Math.round((Object.values(q).reduce((a, b) => a + b, 0) / Object.keys(q).length) * 100);

  const latestFilmPanel = latestFilm && (
    <Card className="border-emerald-400/25 bg-emerald-400/5 p-5">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Clapperboard className="h-4 w-4 text-emerald-400" />
        <span className="text-sm font-semibold text-zinc-100">Latest film — {latestFilm.scene_label}</span>
        <Badge tone="green">
          {latestFilm.clips.length} clips · {latestFilm.duration_s}s ·{" "}
          {latestFilm.audio_report?.mixed ? "🔊 with soundtrack" : "no audio track"}
        </Badge>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <video
          key={latestFilm.final_url}
          src={`/api/backend${latestFilm.final_url}`}
          controls
          autoPlay
          muted
          playsInline
          preload="metadata"
          className="mx-auto max-h-96 w-full rounded-lg bg-black"
        />
        <div className="flex flex-col justify-center gap-3">
          <a
            href={`/api/backend${latestFilm.final_url}`}
            download={`cineforge-${(project?.title || latestFilm.id).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "film"}-${latestFilm.id.slice(0, 8)}.mp4`}
            className="btn-ghost w-full justify-center !py-2.5 text-sm"
          >
            <Download className="h-4 w-4" /> Download MP4
          </a>
          {latestFilm.audio_report?.narration_lines > 0 && (
            <div className="text-center text-xs text-zinc-500">
              🎙 {latestFilm.audio_report.narration_lines} narration lines · {latestFilm.audio_report.narration_provider || "edge"} voices
            </div>
          )}
          <div className="text-center text-[11px] text-zinc-600">Auto-assembled — crossfades, subtitles, mixed soundtrack.</div>
        </div>
      </div>
    </Card>
  );

  return (
    <div>
      <Topbar />
      <div className="mx-auto max-w-[1400px] px-6 py-8">
        {/* header */}
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight text-zinc-50">Video Lab</h1>
            <p className="mt-1 max-w-2xl text-sm text-zinc-500">
              The generation engine routes every scene to the frontier model built for it — <b className="text-gold-400">Veo 3.1</b>,{" "}
              <b className="text-gold-400">Runway Gen-4.5</b>, <b className="text-gold-400">Kling 3.0</b>, <b className="text-gold-400">Seedance 2.0</b> —
              then quality-gates, re-shoots and assembles the director's cut. Cloud keys go in env vars; without them, the built-in
              procedural renderer produces real playable footage.
            </p>
          </div>
          {benchmark && (
            <div className="flex items-center gap-2 rounded-2xl border border-emerald-400/25 bg-emerald-400/8 px-4 py-2.5">
              <Trophy className="h-4 w-4 text-emerald-400" />
              <div className="text-xs">
                <div className="font-bold text-emerald-300">Routed ensemble: {benchmark.ensemble_score}%</div>
                <div className="text-emerald-500/80">
                  vs best single model {benchmark.best_single_model} ({benchmark.best_single_score}%) — +{benchmark.uplift_pts} pts
                </div>
              </div>
            </div>
          )}
        </div>

        {/* tabs */}
        <div className="mb-6 flex w-fit gap-1 rounded-xl border border-white/8 bg-ink-850 p-1">
          {[
            { id: "compare", label: "Model showdown", icon: Trophy },
            { id: "route", label: "Smart routing", icon: Route },
            { id: "generate", label: "Render & compare", icon: Film },
            { id: "image", label: "Image → Video", icon: ImagePlus },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cx(
                "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition",
                tab === t.id ? "bg-white/10 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"
              )}
            >
              <t.icon className="h-4 w-4" /> {t.label}
            </button>
          ))}
        </div>

        {/* ================= MODEL SHOWDOWN ================= */}
        {tab === "compare" && (
          <div className="space-y-6">
            {!providers && <Skeleton className="h-72 w-full rounded-2xl" />}
            {providers && (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {providers.map((p, i) => (
                  <motion.div key={p.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }}>
                    <Card className="flex h-full flex-col p-5">
                      <div className="mb-3 flex items-start justify-between">
                        <div className="flex items-center gap-2.5">
                          <span className="text-2xl">{PROVIDER_EMOJI[p.id]}</span>
                          <div>
                            <div className="font-display text-sm font-bold text-zinc-100">{p.name}</div>
                            <div className="text-[11px] text-zinc-600">{p.vendor}</div>
                          </div>
                        </div>
                        <Badge tone={p.configured ? "green" : "zinc"}>{p.configured ? "key ready" : "mock mode"}</Badge>
                      </div>
                      <div className="mb-3 space-y-1.5 text-xs">
                        {p.strengths.map((s) => (
                          <div key={s} className="flex items-center gap-1.5 text-emerald-400/90">
                            <span className="h-1 w-1 rounded-full bg-emerald-400" /> {s}
                          </div>
                        ))}
                        {p.weaknesses.map((w) => (
                          <div key={w} className="flex items-center gap-1.5 text-zinc-600">
                            <span className="h-1 w-1 rounded-full bg-zinc-600" /> {w}
                          </div>
                        ))}
                      </div>
                      <div className="mb-3 space-y-1.5">
                        {QUALITY_LABELS.map(([label, key]) => (
                          <div key={key} className="flex items-center gap-2">
                            <span className="w-20 text-[10px] text-zinc-600">{label}</span>
                            <Progress value={p.quality[key] * 100} tone={p.quality[key] >= 0.93 ? "green" : p.quality[key] >= 0.9 ? "gold" : "violet"} className="h-1" />
                            <span className="w-7 text-right font-mono text-[10px] text-zinc-500">{Math.round(p.quality[key] * 100)}</span>
                          </div>
                        ))}
                      </div>
                      <div className="mt-auto grid grid-cols-2 gap-2 border-t border-white/8 pt-3 text-[11px] text-zinc-500">
                        <div>${p.price_per_sec}/s</div>
                        <div>up to {p.max_duration_s}s · {p.max_res}</div>
                        <div>{p.native_audio ? "🔊 native audio" : "🔇 audio add-on"}</div>
                        <div>camera: {p.camera_control}</div>
                      </div>
                      <p className="mt-3 rounded-xl bg-ink-850 px-3 py-2 text-[11px] italic leading-relaxed text-zinc-500">
                        🎬 {p.director_note}
                      </p>
                    </Card>
                  </motion.div>
                ))}
              </div>
            )}

            {/* CineForge edge */}
            <Card className="relative overflow-hidden p-6">
              <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-gold-400/10 blur-[90px]" />
              <div className="relative flex flex-wrap items-center gap-6">
                <div className="grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-gold-400 to-amber-600 text-ink-950 shadow-[0_0_30px_-6px_rgba(245,179,1,0.7)]">
                  <Clapperboard className="h-7 w-7" />
                </div>
                <div className="min-w-[280px] flex-1">
                  <h3 className="font-display text-base font-semibold text-zinc-50">
                    Why CineForge beats using any of them raw
                  </h3>
                  <p className="mt-1 max-w-2xl text-sm leading-relaxed text-zinc-500">
                    Frontier labs compete on the model. CineForge competes on the <i>production</i>: every scene is routed to the
                    model whose strengths match its requirements, continuity is chained across shots (last-frame → first-frame),
                    every clip passes a quality gate with automated re-shoots, and the final cut is assembled with transitions,
                    subtitles and sound. The ensemble scores higher than any single model can on a mixed film.
                  </p>
                </div>
                <div className="grid gap-3 text-center">
                  <div>
                    <div className="font-display text-3xl font-bold text-gold-400">{benchmark?.uplift_pts ?? "—"}</div>
                    <div className="text-[11px] text-zinc-600">pts uplift vs best single model</div>
                  </div>
                  <div>
                    <div className="font-display text-3xl font-bold text-emerald-400">18</div>
                    <div className="text-[11px] text-zinc-600">stages of production direction</div>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* ================= SMART ROUTING ================= */}
        {tab === "route" && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <div className="w-72">
                <Select options={projects.map((p) => ({ id: p.id, label: p.title }))} value={projectId} onChange={setProjectId} placeholder="Select project…" />
              </div>
              {!project && <Skeleton className="h-8 w-40 rounded-xl" />}
              {project && (
                <div className="flex flex-wrap gap-1.5">
                  {[...routedProviders].map((pid) => (
                    <Badge key={String(pid)} tone="violet">{PROVIDER_EMOJI[String(pid)] || "🎬"} {String(pid)}</Badge>
                  ))}
                  <Badge tone="gold">{planScenes.length} scenes · {planScenes.flatMap((s: any) => s.clips).length} clips</Badge>
                </div>
              )}
            </div>

            {project && !plan && (
              <EmptyState
                icon="🎥"
                title="No video plan yet"
                body="Run the pipeline through the Video Generation stage to build the routed shot plan."
                action={
                  <Button onClick={() => api(`/pipeline/projects/${project.id}/run`, { method: "POST", body: { start_stage: "video_generation" } }).then(load)}>
                    <Sparkles className="h-4 w-4" /> Generate plan
                  </Button>
                }
              />
            )}

            {plan && (
              <div className="space-y-3">
                {planScenes.map((scene: any, si: number) => (
                  <Card key={scene.scene_id} className="p-4">
                    <div className="mb-3 flex items-center gap-2.5">
                      <span className="chip text-gold-400">Scene {si + 1}</span>
                      <span className="text-sm font-semibold text-zinc-100">{scene.title || scene.scene_id}</span>
                      <span className="ml-auto text-xs text-zinc-600">{scene.clips.length} clips · {scene.clips[0]?.aspect_ratio}</span>
                    </div>
                    <div className="space-y-2">
                      {scene.clips.map((clip: any, ci: number) => (
                        <div key={clip.clip_id} className="grid gap-3 rounded-xl border border-white/8 bg-ink-850 p-3.5 md:grid-cols-[220px_1fr_auto]">
                          <div>
                            <Badge tone="violet">{PROVIDER_EMOJI[clip.provider]} {clip.provider}</Badge>
                            <div className="mt-1.5 text-[11px] text-zinc-600">
                              {clip.shot?.shot_type} · {clip.shot?.camera_type} · {clip.shot?.lens} · {clip.shot?.movement}
                            </div>
                          </div>
                          <div>
                            <div className="text-[11px] font-semibold text-zinc-400">Prompt → {clip.provider}</div>
                            <div className="mt-0.5 line-clamp-2 font-mono text-[11px] leading-relaxed text-zinc-500">{clip.prompt}</div>
                          </div>
                          <div className="flex flex-col items-end gap-1 md:w-48">
                            {clip.routing?.reasons?.map((r: string) => (
                              <span key={r} className="chip text-emerald-400/90">✓ {r}</span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                ))}
              </div>
            )}

            {benchmark && (
              <Card className="p-5">
                <div className="label mb-3">Ensemble math — this project</div>
                <div className="grid gap-4 sm:grid-cols-3">
                  <div>
                    <div className="text-[11px] text-zinc-600">Best single model</div>
                    <div className="font-display text-xl font-bold text-zinc-200">{benchmark.best_single_model} · {benchmark.best_single_score}%</div>
                  </div>
                  <div>
                    <div className="text-[11px] text-zinc-600">Routed ensemble</div>
                    <div className="font-display text-xl font-bold text-gold-400">{benchmark.ensemble_score}%</div>
                  </div>
                  <div>
                    <div className="text-[11px] text-zinc-600">Uplift</div>
                    <div className="font-display text-xl font-bold text-emerald-400">+{benchmark.uplift_pts} pts</div>
                  </div>
                </div>
              </Card>
            )}
          </div>
        )}

        {/* ================= RENDER & COMPARE ================= */}
        {tab === "generate" && (
          <div className="space-y-6">
            {/* controls */}
            <Card className="p-5">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <label className="label mb-1.5 block">Project</label>
                  <Select options={projects.map((p) => ({ id: p.id, label: p.title }))} value={projectId} onChange={setProjectId} placeholder="Select…" />
                </div>
                <div>
                  <label className="label mb-1.5 block">Provider (auto = routed)</label>
                  <Select
                    options={[
                      { id: "auto", label: "Auto — smart routing" },
                      { id: "veo-3.1", label: "Veo 3.1" },
                      { id: "runway-gen-4.5", label: "Runway Gen-4.5" },
                      { id: "kling-3.0", label: "Kling 3.0" },
                      { id: "seedance-2.0", label: "Seedance 2.0" },
                    ]}
                    value={providerOverride}
                    onChange={setProviderOverride}
                  />
                </div>
                <div>
                  <label className="label mb-1.5 block">Resolution</label>
                  <Select options={[{ id: "480p", label: "480p (fast)" }, { id: "720p", label: "720p" }, { id: "1080p", label: "1080p" }]} value={resolution} onChange={setResolution} />
                </div>
                <div className="flex items-end gap-2">
                  <Button onClick={() => enqueue("render")} disabled={!projectId || busy === "render"} className="flex-1">
                    {busy === "render" ? <Spinner className="h-4 w-4" /> : <Play className="h-4 w-4" />} Render scenes
                  </Button>
                </div>
              </div>
              <div className="mt-4 border-t border-white/8 pt-4">
                <div className="label mb-2">4-way provider comparison — same scene, four grades</div>
                <div className="flex flex-wrap items-end gap-3">
                  <div className="w-56">
                    <Select
                      options={(planScenes.length ? planScenes : [{ scene_id: "0", title: "Demo scene (Banaue Terraces)" }]).map((s: any, i: number) => ({ id: String(i), label: `Scene ${i + 1}: ${s.title || s.scene_id}` }))}
                      value={compareScene}
                      onChange={setCompareScene}
                    />
                  </div>
                  <Button variant="ghost" onClick={() => enqueue("compare")} disabled={busy === "compare" || !projectId}>
                    {busy === "compare" ? <Spinner className="h-4 w-4" /> : <Wand2 className="h-4 w-4" />} Render comparison
                  </Button>
                  <span className="text-[11px] text-zinc-600">One clip per provider, side by side — pick the look you want.</span>
                </div>
              </div>
            </Card>

            {/* latest film — appears right here the moment a render finishes */}
            {latestFilmPanel}

            {/* running */}
            {runningJobs.length > 0 && (
              <Card className="p-5">
                <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-gold-400">
                  <Spinner className="h-4 w-4" /> Rendering in progress…
                </div>
                {runningJobs.map((j) => (
                  <div key={j.id} className="mb-2 flex items-center gap-3 text-xs">
                    <span className="text-zinc-500">{j.model === "compare" ? "Comparison job" : j.scene_label}</span>
                    <Progress value={j.progress} className="flex-1" />
                    <span className="font-mono text-zinc-400">{j.progress}%</span>
                  </div>
                ))}
              </Card>
            )}

            {/* jobs */}
            {jobs.length === 0 && !runningJobs.length && (
              <EmptyState icon="🖥️" title="Nothing rendered yet" body="Render the routed plan or fire a 4-way comparison — every clip is a real playable file." />
            )}

            {jobs.map((job) => (
              <Card key={job.id} className="p-5">
                <div className="mb-4 flex flex-wrap items-center gap-2.5">
                  <div className="grid h-9 w-9 place-items-center rounded-lg border border-white/8 bg-ink-850">
                    {job.model === "compare" ? <Layers className="h-4 w-4 text-violet-400" /> : <Film className="h-4 w-4 text-gold-400" />}
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-zinc-100">
                      {job.model === "compare" ? "Provider comparison" : job.scene_label}
                    </div>
                    <div className="text-[11px] text-zinc-600">
                      {job.model} · {job.resolution} · {job.clips.length} clips
                    </div>
                  </div>
                  <Badge tone={job.status === "completed" ? "green" : job.status === "rendering" ? "gold" : job.status === "failed" ? "red" : "zinc"}>{job.status}</Badge>
                  {job.final_url && <Badge tone="green">🎬 assembled</Badge>}
                  <div className="ml-auto flex items-center gap-2">
                    {job.status === "completed" && !job.final_url && (
                      <Button variant="ghost" onClick={() => assemble(job.id)} className="!py-1.5 text-xs">
                        <Scissors className="h-3.5 w-3.5" /> Assemble director's cut
                      </Button>
                    )}
                  </div>
                </div>

                {/* clips */}
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {job.clips.map((clip) => (
                    <div key={clip.id} className="rounded-xl border border-white/8 bg-ink-850 p-2.5">
                      <div className="relative mb-2 overflow-hidden rounded-lg bg-black">
                        {clip.file_url ? (
                          <video src={`/api/backend${clip.file_url}`} controls muted playsInline preload="metadata" className="aspect-video w-full" />
                        ) : (
                          <div className="grid aspect-video w-full place-items-center text-3xl opacity-40">{PROVIDER_EMOJI[clip.provider] || "🎬"}</div>
                        )}
                        <span className="absolute left-2 top-2 rounded-md bg-black/60 px-1.5 py-0.5 text-[10px] font-bold text-white backdrop-blur">
                          {PROVIDER_EMOJI[clip.provider]} {clip.provider}
                        </span>
                        {clip.score ? (
                          <span
                            className={cx(
                              "absolute right-2 top-2 rounded-md px-1.5 py-0.5 text-[10px] font-bold backdrop-blur",
                              clip.score >= 78 ? "bg-emerald-500/80 text-white" : clip.score >= 64 ? "bg-gold-400/90 text-ink-950" : "bg-red-500/80 text-white"
                            )}
                          >
                            {clip.score}
                          </span>
                        ) : null}
                      </div>
                      <div className="flex items-center justify-between px-1">
                        <span className="truncate font-mono text-[10px] text-zinc-600">{clip.clip_ref}</span>
                        <span className="text-[10px] text-zinc-600">{clip.duration_s}s</span>
                      </div>
                      <p className="mt-1 line-clamp-2 px-1 font-mono text-[10px] leading-relaxed text-zinc-500">{clip.prompt}</p>
                      <div className="mt-1.5 flex items-center justify-between px-1">
                        <div className="flex gap-1">
                          {clip.quality?.dims && (
                            <span className="chip" title={`motion ${clip.quality.dims.motion_quality} · physics ${clip.quality.dims.physics_plausibility} · consistency ${clip.quality.dims.temporal_consistency}`}>
                              <Gauge className="h-3 w-3" /> {clip.quality.verdict}
                            </span>
                          )}
                        </div>
                        <button onClick={() => reshoot(job.id, clip.id)} className="text-[10px] font-semibold text-violet-400 hover:text-violet-300" title="Re-shoot with the director's notes">
                          <RefreshCw className="mr-1 inline h-3 w-3" /> re-shoot
                        </button>
                        {clip.file_url && (
                          <a
                            href={`/api/backend${clip.file_url}`}
                            download={`cineforge-${clip.clip_ref}.mp4`}
                            className="text-[10px] font-semibold text-gold-400 hover:text-gold-300"
                            title="Download this clip"
                          >
                            <Download className="mr-1 inline h-3 w-3" /> clip
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* final film */}
                {job.final_url && (
                  <div className="mt-4 rounded-xl border border-gold-400/25 bg-gold-400/5 p-4">
                    <div className="mb-2.5 flex flex-wrap items-center gap-2">
                      <Clapperboard className="h-4 w-4 text-gold-400" />
                      <span className="text-sm font-semibold text-zinc-100">Director's cut</span>
                      <Badge tone="gold">{job.clips.length} clips · crossfades</Badge>
                      {job.audio_report?.mixed && (
                        <Badge tone="green">
                          🔊 soundtrack — {job.audio_report.music_scenes} music scenes · {job.audio_report.sfx_count} SFX
                          {job.audio_report.narration_lines > 0 ? ` · ${job.audio_report.narration_lines} narration lines` : " · narration unavailable (no network)"}
                        </Badge>
                      )}
                      <a
                        href={`/api/backend${job.final_url}`}
                        download={`cineforge-${(project?.title || job.id).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "film"}-${job.id.slice(0, 8)}.mp4`}
                        className="btn-ghost ml-auto !py-1.5 text-xs"
                      >
                        <Download className="h-3.5 w-3.5" /> Download MP4
                      </a>
                    </div>
                    <div className="grid gap-4 lg:grid-cols-[1fr_260px]">
                      <video src={`/api/backend${job.final_url}`} controls playsInline preload="metadata" className="mx-auto max-h-96 w-full rounded-lg bg-black" />
                      {job.audio_report?.tracks && (
                        <div className="max-h-96 space-y-1 overflow-y-auto rounded-xl border border-white/8 bg-black/25 p-3">
                          <div className="label mb-2">Soundtrack layers</div>
                          {job.audio_report.tracks.map((t: any, i: number) => (
                            <div key={i} className="flex items-center gap-2 rounded-lg bg-ink-850 px-2.5 py-1.5 text-[11px]">
                              <span className="text-base">
                                {t.kind === "music" ? "🎼" : t.kind === "sfx" ? "💥" : t.kind === "ambience" ? "🌫" : "🎙"}
                              </span>
                              <span className="w-14 shrink-0 font-mono text-zinc-600">{t.scene}</span>
                              <span className="truncate text-zinc-400">
                                {t.kind === "music" ? `${t.genre} · ${t.mood} · ${t.bpm} BPM` : t.kind === "narration" ? `${t.speaker}: ${t.text}` : t.cue || t.bed}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </Card>
            ))}

          </div>
        )}

          {/* ================= IMAGE → VIDEO ================= */}
        {tab === "image" && (
          <div className="space-y-6">
            <Card className="p-6">
              <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
                {/* uploader */}
                <div>
                  <label className="label mb-1.5 block">Your still image</label>
                  <label
                    className={cx(
                      "group flex h-56 cursor-pointer flex-col items-center justify-center gap-2 overflow-hidden rounded-2xl border-2 border-dashed transition",
                      imagePreview ? "border-emerald-400/40 bg-black/30" : "border-white/12 bg-ink-850 hover:border-gold-400/40"
                    )}
                  >
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => onPickImage(e.target.files?.[0] || null)}
                    />
                    {imagePreview ? (
                      <img src={imagePreview} alt="preview" className="max-h-56 w-full object-contain" />
                    ) : (
                      <>
                        <Upload className="h-8 w-8 text-zinc-600 transition group-hover:text-gold-400" />
                        <span className="text-sm text-zinc-500">Click to upload — JPG, PNG, WebP</span>
                        <span className="text-[11px] text-zinc-700">up to 25 MB · auto-cropped to 16:9</span>
                      </>
                    )}
                  </label>
                  {imageFile && (
                    <button onClick={() => onPickImage(null)} className="mt-1.5 text-[11px] font-semibold text-zinc-600 hover:text-red-400">
                      ✕ remove image
                    </button>
                  )}
                </div>

                {/* controls */}
                <div>
                  <label className="label mb-1.5 block">Prompt — describe the motion, mood and look</label>
                  <textarea
                    value={i2vPrompt}
                    onChange={(e) => setI2vPrompt(e.target.value)}
                    placeholder="e.g. slow cinematic push-in over the scene, golden hour light sweeping across, gentle film grain…"
                    rows={3}
                    className="w-full resize-none rounded-xl border border-white/10 bg-ink-850 px-3.5 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-gold-400/50"
                  />
                  <div className="mt-3 grid gap-3 sm:grid-cols-3">
                    <div>
                      <label className="label mb-1.5 block">Duration</label>
                      <Select
                        options={["4", "6", "8", "10", "12"].map((d) => ({ id: d, label: `${d}s` }))}
                        value={i2vDuration}
                        onChange={setI2vDuration}
                      />
                    </div>
                    <div>
                      <label className="label mb-1.5 block">Style (grade)</label>
                      <Select
                        options={[
                          { id: "auto", label: "Auto — routed" },
                          { id: "veo-3.1", label: "🌊 Veo 3.1 grade" },
                          { id: "runway-gen-4.5", label: "🎨 Runway grade" },
                          { id: "kling-3.0", label: "🥋 Kling 3.0 grade" },
                          { id: "seedance-2.0", label: "⚡ Seedance grade" },
                        ]}
                        value={i2vStyle}
                        onChange={setI2vStyle}
                      />
                    </div>
                    <div>
                      <label className="label mb-1.5 block">Camera move</label>
                      <Select
                        options={[
                          { id: "auto", label: "Auto — from prompt" },
                          { id: "push in", label: "Push in (Ken Burns)" },
                          { id: "pull back", label: "Pull back" },
                          { id: "pan", label: "Pan across" },
                          { id: "orbit", label: "Orbit" },
                          { id: "crane up", label: "Crane up (soar)" },
                          { id: "handheld", label: "Handheld" },
                          { id: "static", label: "Static lock-off" },
                        ]}
                        value={i2vMovement}
                        onChange={setI2vMovement}
                      />
                    </div>
                  </div>
                  {uploadError && <div className="mt-3 text-xs font-semibold text-red-400">⚠ {uploadError}</div>}
                  <div className="mt-4 flex items-center gap-3">
                    <Button onClick={startImageVideo} disabled={!imageFile || uploading} className="!py-2.5">
                      {uploading ? <Spinner className="h-4 w-4" /> : <ImagePlus className="h-4 w-4" />} {uploading ? "Animating…" : "Generate video"}
                    </Button>
                    <span className="text-[11px] text-zinc-600">
                      Fully offline — animated with camera moves, lighting grade & film grain. Cloud keys upgrade the look.
                    </span>
                  </div>
                </div>
              </div>
            </Card>

            {latestFilmPanel}

            {/* image jobs */}
            {jobs.filter((j) => j.model === "image").map((job) => (
              <Card key={job.id} className="p-5">
                <div className="mb-3 flex flex-wrap items-center gap-2.5">
                  <div className="grid h-9 w-9 place-items-center rounded-lg border border-white/8 bg-ink-850">
                    <ImagePlus className="h-4 w-4 text-gold-400" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-zinc-100">{job.scene_label || "Image film"}</div>
                    <div className="text-[11px] text-zinc-600">{job.model} · {job.duration_s}s · {job.clips.length} clips</div>
                  </div>
                  <Badge tone={job.status === "completed" ? "green" : job.status === "rendering" ? "gold" : job.status === "failed" ? "red" : "zinc"}>{job.status}</Badge>
                  {job.final_url && <Badge tone="green">🎬 assembled</Badge>}
                </div>
                {job.status === "rendering" && (
                  <Progress value={job.progress} tone="gold" className="h-1.5" />
                )}
                {job.status === "failed" && <div className="text-xs text-red-400">⚠ {job.error}</div>}
                <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {job.clips.map((clip) => (
                    <div key={clip.id} className="rounded-xl border border-white/8 bg-ink-850 p-2.5">
                      {clip.file_url ? (
                        <video src={`/api/backend${clip.file_url}`} controls muted playsInline preload="metadata" className="aspect-video w-full rounded-lg bg-black" />
                      ) : (
                        <div className="grid aspect-video w-full place-items-center rounded-lg bg-black/40 text-xs text-zinc-600">rendering…</div>
                      )}
                      <div className="mt-1.5 flex items-center justify-between px-1 text-[10px] text-zinc-600">
                        <span>{clip.duration_s}s · {clip.provider}</span>
                        {clip.score ? <span className="font-bold text-gold-400">Q{clip.score}</span> : null}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            ))}
            {jobs.filter((j) => j.model === "image").length === 0 && !uploading && (
              <EmptyState icon="🖼️" title="No image films yet" body="Upload a still and bring it to life — the result lands here as a playable, downloadable MP4." />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
