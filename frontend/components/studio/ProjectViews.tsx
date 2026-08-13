"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { Clapperboard, RefreshCw } from "lucide-react";
import { Badge, Button, Card, CopyButton, Select, Spinner, Textarea } from "@/components/ui";
import { LineChart, BarChart } from "@/components/charts";
import { fmtDate, fmtDuration, fmtNum, cx } from "@/lib/utils";
import { Project, RenderJob } from "@/lib/types";

/* ---------------------------------------------------------------- Script */
export function ScriptView({ project }: { project: Project }) {
  const script = project.outputs?.script;
  if (!script) return <EmptyOutput what="script" />;
  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-display text-lg font-semibold text-zinc-50">{script.title}</h3>
          <CopyButton text={script.title} />
          <span className="ml-auto flex gap-2">
            <Badge tone="violet">{script.structure}</Badge>
            <Badge tone="gold">{fmtDuration(script.total_duration)}</Badge>
            <Badge tone="zinc">rev {script.revision}</Badge>
          </span>
        </div>
        <p className="mt-3 rounded-xl border border-gold-400/15 bg-gold-400/5 px-4 py-3 text-sm italic text-zinc-300">🪝 {script.hook}</p>
      </Card>
      <div className="space-y-3">
        {(script.scenes || []).map((s: any, i: number) => (
          <Card key={i} className="p-5">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Badge tone="gold">Scene {i + 1}</Badge>
              <span className="font-display text-base font-semibold text-zinc-100">{s.title}</span>
              <span className="ml-auto text-xs text-zinc-500">{fmtDuration(s.duration)} · {s.tone}</span>
            </div>
            <div className="mb-3 text-xs italic text-zinc-500">🎬 {s.direction}</div>
            <div className="space-y-2">
              {(s.dialogue || []).map((l: any, j: number) => (
                <div key={j} className="flex items-start gap-3 rounded-xl bg-ink-850 p-3">
                  <span className="w-24 shrink-0 rounded-md bg-violet-400/10 px-2 py-0.5 text-center text-xs font-semibold text-violet-300">
                    {l.speaker}
                  </span>
                  <div className="text-sm text-zinc-300">
                    {l.line}
                    {l.emotion && <span className="ml-2 text-xs text-zinc-600">[{l.emotion}]</span>}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <span className="chip">➡ {s.transition}</span>
              <span className="chip">🔊 {s.audio_cue}</span>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ Storyboard */
export function StoryboardView({ project }: { project: Project }) {
  const panels = project.outputs?.storyboard?.panels || [];
  if (!panels.length) return <EmptyOutput what="storyboard" />;
  const GRADS = [
    ["#2b2720", "#4a3d1e"],
    ["#1c2433", "#2c3e5a"],
    ["#2a1f14", "#593a1e"],
    ["#14251c", "#23402f"],
    ["#221733", "#3a2a55"],
  ];
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-zinc-500">{panels.length} panels · {project.outputs?.storyboard?.style_notes}</div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {panels.map((p: any, i: number) => (
          <Card key={p.id} className="overflow-hidden">
            <div className="relative grid h-44 place-items-center overflow-hidden" style={{ background: `linear-gradient(135deg, ${GRADS[i % 5][0]}, ${GRADS[i % 5][1]})` }}>
              <div className="absolute inset-0 opacity-30" style={{ backgroundImage: "radial-gradient(circle at 50% 45%, rgba(255,255,255,0.22) 0%, transparent 40%)" }} />
              <div className="absolute inset-0 opacity-[0.15]">
                <div className="absolute left-1/3 top-0 h-full w-px bg-white" />
                <div className="absolute left-2/3 top-0 h-full w-px bg-white" />
                <div className="absolute left-0 top-1/3 h-px w-full bg-white" />
                <div className="absolute left-0 top-2/3 h-px w-full bg-white" />
              </div>
              <div className="relative rounded-lg border border-white/25 bg-black/45 px-3 py-1.5 text-center backdrop-blur-sm">
                <div className="text-[11px] font-semibold text-white">{p.composition}</div>
                <div className="text-[10px] text-white/70">{p.camera}</div>
              </div>
              <span className="absolute left-2.5 top-2.5 rounded-md bg-black/50 px-1.5 py-0.5 font-mono text-[10px] text-white/80">{p.id}</span>
              <span className="absolute bottom-2 right-2.5 rounded-md bg-black/50 px-1.5 py-0.5 text-[10px] text-white/80">{fmtDuration(p.duration)}</span>
            </div>
            <div className="space-y-2 p-4 text-xs">
              <div className="flex flex-wrap gap-1.5">
                <span className="chip">💡 {p.lighting}</span>
                <span className="chip">🎭 {p.mood}</span>
                <span className="chip">🎥 {p.placement}</span>
              </div>
              <div className="rounded-lg border border-white/8 bg-ink-850 px-3 py-2 text-zinc-400">“{p.dialogue}”</div>
              <div className="flex flex-wrap gap-1.5">
                {(p.effects || []).map((e: string) => (
                  <span key={e} className="chip">✦ {e}</span>
                ))}
                <span className="chip">➡ {p.transition}</span>
                <span className="chip">🔊 {p.audio_cue}</span>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- Shots */
const SHOT_TYPES = ["All", "Establishing", "Wide", "Medium", "Close-Up", "Hero Shot", "POV", "Dutch Angle"];

export function ShotsView({ project }: { project: Project }) {
  const shots = project.outputs?.shot_planning?.shots || [];
  const [filter, setFilter] = useState("All");
  if (!shots.length) return <EmptyOutput what="shot list" />;
  const rows = filter === "All" ? shots : shots.filter((s: any) => s.shot_type === filter);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1.5">
        {SHOT_TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            className={cx(
              "chip transition",
              filter === t ? "border-gold-400/40 bg-gold-400/10 text-gold-400" : "hover:border-white/25"
            )}
          >
            {t}
          </button>
        ))}
      </div>
      <Card className="overflow-x-auto">
        <table className="w-full min-w-[860px]">
          <thead>
            <tr className="border-b border-white/8 text-left text-[11px] uppercase tracking-wider text-zinc-600">
              <th className="px-3 py-2.5">Shot</th>
              <th className="px-3 py-2.5">Type</th>
              <th className="px-3 py-2.5">Camera rig</th>
              <th className="px-3 py-2.5">Lens</th>
              <th className="px-3 py-2.5">Movement</th>
              <th className="px-3 py-2.5">Framing</th>
              <th className="px-3 py-2.5">Action</th>
              <th className="px-3 py-2.5">Background</th>
              <th className="px-3 py-2.5">Time / weather</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s: any, i: number) => (
              <tr key={i} className="border-b border-white/5 text-[12.5px] last:border-0 hover:bg-white/3">
                <td className="px-3 py-2.5 font-mono text-[11px] text-zinc-600">{s.id}</td>
                <td className="px-3 py-2.5"><span className="chip text-violet-400">{s.shot_type}</span></td>
                <td className="px-3 py-2.5 text-zinc-200">{s.camera_type}</td>
                <td className="px-3 py-2.5">{s.lens}</td>
                <td className="px-3 py-2.5">{s.movement}</td>
                <td className="px-3 py-2.5 text-zinc-500">{s.framing}</td>
                <td className="px-3 py-2.5 text-zinc-500">{s.character_action}</td>
                <td className="px-3 py-2.5 text-zinc-500">{s.background}</td>
                <td className="px-3 py-2.5 text-zinc-500">{s.time_of_day} · {s.weather}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <p className="text-xs text-zinc-600">
        ℹ️ Each shot carries a ready-to-use generation prompt — the video provider consumes these at render time.
      </p>
    </div>
  );
}

/* ----------------------------------------------------------- Characters */
export function CharactersView({ project }: { project: Project }) {
  const chars = project.characters || [];
  if (!chars.length) return <EmptyOutput what="character designs" />;
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {chars.map((c: any, i: number) => (
        <Card key={i} className="p-5">
          <div className="mb-4 flex items-center gap-3">
            <div className="grid h-14 w-14 place-items-center rounded-2xl text-lg font-bold text-ink-950" style={{ background: c.palette?.[0] || "#f5b301" }}>
              {c.name?.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <div className="font-display text-base font-semibold text-zinc-100">{c.name}</div>
              <div className="text-xs text-zinc-500">{c.archetype} · {c.relationship}</div>
            </div>
            <span className="ml-auto chip text-emerald-400">🔒 consistent</span>
          </div>
          <div className="mb-3 flex flex-wrap gap-1.5">
            {(c.traits || []).map((t: string) => (
              <span key={t} className="chip">{t}</span>
            ))}
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between rounded-lg bg-ink-850 px-3 py-2">
              <span className="text-zinc-500">🎙 Voice</span>
              <span className="text-zinc-300">{c.voice?.pitch} · {c.voice?.rate} · {c.voice?.style}</span>
            </div>
            <div className="rounded-lg bg-ink-850 px-3 py-2">
              <div className="mb-1 text-zinc-500">😊 Expressions</div>
              <div className="flex flex-wrap gap-1">
                {(c.expressions || []).map((e: string) => (
                  <span key={e} className="chip text-violet-400">{e}</span>
                ))}
              </div>
            </div>
            <div className="rounded-lg bg-ink-850 px-3 py-2">
              <div className="mb-1 text-zinc-500">👔 Wardrobe</div>
              <div className="flex flex-wrap gap-1">
                {(c.wardrobe || []).map((w: string) => (
                  <span key={w} className="chip">{w}</span>
                ))}
              </div>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------- Environments */
export function EnvironmentsView({ project }: { project: Project }) {
  const envs = project.environments || [];
  if (!envs.length) return <EmptyOutput what="environment designs" />;
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {envs.map((e: any, i: number) => (
        <Card key={i} className="overflow-hidden">
          <div className="relative h-32" style={{ background: `linear-gradient(135deg, ${e.palette?.[1] || "#222"}, ${e.palette?.[0] || "#333"})` }}>
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_25%,rgba(255,255,255,0.2),transparent_55%)]" />
            <div className="absolute bottom-3 left-4">
              <div className="text-sm font-semibold text-white drop-shadow">{e.name}</div>
              <div className="text-[11px] text-white/70">{e.category.replace(/_/g, " ")}</div>
            </div>
            <span className="absolute right-3 top-3 chip bg-black/50 text-white/90">{e.time_presets?.[0] || "any time"}</span>
          </div>
          <div className="space-y-2.5 p-4 text-xs">
            <p className="text-zinc-500">{e.description}</p>
            <div className="flex flex-wrap gap-1.5">
              {(e.weather || []).map((w: string) => (
                <span key={w} className="chip">☁️ {w}</span>
              ))}
            </div>
            <div className="rounded-lg bg-ink-850 px-3 py-2">
              <div className="mb-1 text-zinc-500">💡 Lighting rig</div>
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-zinc-300">
                {Object.entries(e.lighting || {}).map(([k, v]) => (
                  <span key={k}><span className="text-zinc-600">{k}:</span> {String(v)}</span>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              {(e.palette || []).map((c: string) => (
                <span key={c} className="h-4 w-4 rounded-full border border-white/15" style={{ background: c }} />
              ))}
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------- SEO */
export function SeoView({ project }: { project: Project }) {
  const seo = project.outputs?.seo;
  if (!seo) return <EmptyOutput what="SEO metadata" />;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="p-5 lg:col-span-2">
        <div className="label mb-3">Titles (A/B/C)</div>
        <div className="space-y-2">
          {(seo.titles || []).map((t: string, i: number) => (
            <div key={i} className="flex items-center gap-3 rounded-xl bg-ink-850 px-4 py-3">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-gold-400/10 text-[11px] font-bold text-gold-400">
                {String.fromCharCode(65 + i)}
              </span>
              <span className="flex-1 truncate text-sm text-zinc-200">{t}</span>
              <CopyButton text={t} />
            </div>
          ))}
        </div>
      </Card>
      <Card className="p-5 lg:col-span-2">
        <div className="label mb-3">Description</div>
        <pre className="whitespace-pre-wrap rounded-xl border border-white/8 bg-ink-850 p-4 font-sans text-[13px] leading-relaxed text-zinc-400">{seo.description}</pre>
        <div className="mt-3 flex justify-end"><CopyButton text={seo.description || ""} /></div>
      </Card>
      <Card className="p-5">
        <div className="label mb-3">Tags</div>
        <div className="flex flex-wrap gap-1.5">
          {(seo.tags || []).map((t: string) => (
            <span key={t} className="chip">#{t.replace(/\s+/g, "")}</span>
          ))}
        </div>
      </Card>
      <Card className="p-5">
        <div className="label mb-3">Hashtags</div>
        <div className="flex flex-wrap gap-1.5">
          {(seo.hashtags || []).map((t: string) => (
            <span key={t} className="chip text-violet-400">{t}</span>
          ))}
        </div>
      </Card>
      <Card className="p-5 lg:col-span-2">
        <div className="label mb-3">Chapters</div>
        <div className="flex items-center gap-0">
          {(seo.chapters || []).map((c: any, i: number) => (
            <div key={i} className="flex flex-1 flex-col items-start">
              <div className="mb-1.5 font-mono text-[11px] text-gold-400">
                {Math.floor(c.start / 60)}:{String(c.start % 60).padStart(2, "0")}
              </div>
              <div className="h-1.5 w-full rounded-full bg-gradient-to-r from-violet-500 to-gold-400" style={{ opacity: 0.35 + i * 0.16 }} />
              <div className="mt-1.5 text-xs text-zinc-300">{c.label}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------- Analytics */
export function ProjectAnalyticsView({ analytics }: { analytics: any }) {
  if (!analytics || analytics.empty)
    return (
      <div className="rounded-2xl border border-dashed border-white/10 p-12 text-center text-sm text-zinc-600">
        Publish this project to start collecting audience analytics.
      </div>
    );
  const retention = analytics.retention || [];
  const daily = analytics.daily || [];
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Views", value: fmtNum(analytics.views) },
          { label: "Watch time", value: `${Math.round(analytics.watch_time_min / 60)}h ${Math.round(analytics.watch_time_min % 60)}m` },
          { label: "Avg retention", value: `${analytics.avg_retention}%` },
          { label: "CTR", value: `${analytics.ctr}%` },
        ].map((s) => (
          <Card key={s.label} className="p-4">
            <div className="label">{s.label}</div>
            <div className="mt-1.5 font-display text-xl font-bold text-zinc-100">{s.value}</div>
          </Card>
        ))}
      </div>
      <Card className="p-5">
        <div className="label mb-4">Retention curve</div>
        <LineChart data={retention} label="retention" format={(v) => `${v}%`} />
      </Card>
      <Card className="p-5">
        <div className="label mb-4">Daily views</div>
        <BarChart data={daily.map((d: any) => ({ label: d.day.slice(5), value: d.views }))} />
        <div className="mt-2 flex justify-between text-[10px] text-zinc-600">
          <span>{daily[0]?.day}</span>
          <span>{daily[daily.length - 1]?.day}</span>
        </div>
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------- Publish */
export function PublishView({ project, onPublish }: { project: Project; onPublish: (platform: string) => void }) {
  const platforms = project.outputs?.publishing?.platforms || [];
  const [selected, setSelected] = useState("youtube");
  const [busy, setBusy] = useState<string | null>(null);
  const [entries, setEntries] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);

  if (!platforms.length) return <EmptyOutput what="publishing plan" />;

  const publish = async () => {
    setBusy(selected);
    try {
      const { api } = await import("@/lib/api");
      await api(`/projects/${project.id}/publish`, { method: "POST", body: { platform: selected } });
      onPublish(selected);
    } catch {
      /* surfaced via reload */
    } finally {
      setBusy(null);
      if (!loaded) {
        const { api } = await import("@/lib/api");
        try {
          setEntries(await api(`/projects/${project.id}/publish`));
          setLoaded(true);
        } catch {
          /* noop */
        }
      }
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="space-y-3 lg:col-span-2">
        <div className="grid gap-3 sm:grid-cols-2">
          {platforms.map((p: any) => (
            <button
              key={p.id}
              onClick={() => setSelected(p.id)}
              className={cx(
                "card p-4 text-left transition",
                selected === p.id ? "border-gold-400/50 bg-ink-800 shadow-[0_0_24px_-10px_rgba(245,179,1,0.5)]" : "hover:border-white/20"
              )}
            >
              <div className="mb-1 flex items-center gap-2.5">
                <span className="text-2xl">{p.id === "youtube" ? "▶️" : p.id === "tiktok" ? "🎵" : p.id === "facebook" ? "📘" : p.id === "instagram" ? "📸" : "🎞️"}</span>
                <div>
                  <div className="text-sm font-semibold text-zinc-100">{p.name}</div>
                  <div className="text-[11px] text-zinc-600">{p.api} · up to {p.max_res}</div>
                </div>
              </div>
              <div className="text-xs leading-relaxed text-zinc-500">{p.notes}</div>
            </button>
          ))}
        </div>
        <Card className="p-5">
          <div className="label mb-2">Dispatch</div>
          <p className="text-sm text-zinc-400">
            Publishing pushes the final cut with the generated metadata through {selected === "youtube" ? "the YouTube Data API" : `${selected}'s official API`} adapter. Scheduled publishing is supported via <span className="font-mono text-xs">scheduled_at</span>.
          </p>
          <div className="mt-4 flex gap-2.5">
            <Button onClick={publish} disabled={busy === selected}>
              {busy === selected ? "Publishing…" : `🚀 Publish to ${platforms.find((p: any) => p.id === selected)?.name}`}
            </Button>
          </div>
        </Card>
      </div>
      <Card className="h-fit p-5">
        <div className="label mb-3">Publish history</div>
        <div className="space-y-2">
          {entries.length === 0 && <div className="text-xs text-zinc-600">No published entries yet.</div>}
          {entries.map((e: any) => (
            <div key={e.id} className="flex items-center justify-between rounded-xl bg-ink-850 px-3 py-2.5 text-xs">
              <span className="font-semibold capitalize text-zinc-200">{e.platform}</span>
              <Badge tone={e.status === "published" ? "green" : "gold"}>{e.status}</Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------- Final film */
export function FinalFilmView({
  project,
  jobs,
  onRender,
  busy,
}: {
  project: Project;
  jobs: RenderJob[];
  onRender: () => void;
  busy: boolean;
}) {
  const mine = (jobs || []).filter((j) => j.project_id === project.id);
  const latest = mine[0] || null;
  const films = mine.filter((j) => j.final_url);
  const running = latest && ["queued", "rendering"].includes(latest.status);
  const providers = new Set((latest?.clips || []).map((c: any) => c.provider).filter(Boolean));

  return (
    <div className="space-y-4">
      {running && (
        <Card className="p-6">
          <div className="flex items-center gap-3">
            <Spinner className="h-5 w-5 text-gold-400" />
            <div>
              <div className="font-display text-sm font-semibold text-zinc-100">Rendering the director's cut…</div>
              <div className="text-xs text-zinc-500">
                {latest?.scene_label || "Full timeline"} · {latest?.resolution} · {latest?.fps}fps
              </div>
            </div>
            <span className="ml-auto font-bold text-gold-400">{latest?.progress ?? 0}%</span>
          </div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/8">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-violet-500 to-gold-400"
              animate={{ width: `${latest?.progress ?? 0}%` }}
            />
          </div>
          <p className="mt-4 text-xs text-zinc-600">
            The film assembles automatically when rendering finishes — stay on this page and it appears here.
          </p>
        </Card>
      )}

      {!running && latest?.final_url && (
        <Card className="overflow-hidden">
          <div className="relative bg-black">
            <video
              key={latest.final_url}
              src={`/api/backend${latest.final_url}`}
              controls
              playsInline
              preload="metadata"
              className="aspect-video w-full"
            />
          </div>
          <div className="flex flex-wrap items-center gap-3 p-5">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="font-display text-base font-semibold text-zinc-50">Director's cut</h3>
                <Badge tone="green">🎬 assembled</Badge>
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1.5 text-xs">
                <span className="chip">⏱ {latest.duration_s ? `${latest.duration_s}s` : fmtDuration(latest.duration_s)}</span>
                <span className="chip">📐 {latest.resolution}</span>
                <span className="chip">🎞 {latest.fps}fps</span>
                {[...providers].slice(0, 4).map((p) => (
                  <span key={p} className="chip">{p}</span>
                ))}
              </div>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <a href={`/api/backend${latest.final_url}`} download={`cineforge-${project.id}.mp4`} className="btn-ghost !py-1.5 text-xs">
                ⬇ Download MP4
              </a>
              <Button onClick={onRender} disabled={busy} variant="ghost" className="!py-1.5 text-xs">
                {busy ? <Spinner className="h-3.5 w-3.5" /> : "⟳ Re-render"}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {!running && !latest?.final_url && (
        <Card className="p-10 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-400/10 text-2xl">🎬</div>
          <h3 className="font-display text-base font-semibold text-zinc-100">No final film yet</h3>
          <p className="mx-auto mt-2 max-w-md text-sm text-zinc-500">
            {latest?.status === "failed" ? `Last render failed: ${latest.error || "unknown error"}` : "Run the pipeline and the director's cut renders automatically onto this page — or kick it off right now."}
          </p>
          <div className="mt-5 flex justify-center gap-2">
            {latest?.status === "failed" && (
              <button onClick={onRender} disabled={busy} className="btn-ghost !py-2 text-sm">
                <RefreshCw className="mr-1.5 h-4 w-4" /> Retry render
              </button>
            )}
            <Button onClick={onRender} disabled={busy}>
              {busy ? <Spinner className="h-4 w-4" /> : <Clapperboard className="h-4 w-4" />} Render final film
            </Button>
          </div>
        </Card>
      )}

      {films.length > 1 && (
        <Card className="p-5">
          <h4 className="mb-3 font-display text-xs font-semibold uppercase tracking-wider text-zinc-500">Earlier films</h4>
          <div className="space-y-2">
            {films.slice(1).map((f) => (
              <div key={f.id} className="flex items-center gap-3 rounded-xl bg-ink-850 p-2.5">
                <video src={`/api/backend${f.final_url}`} className="h-14 w-24 rounded-lg bg-black object-cover" muted playsInline preload="metadata" />
                <div className="min-w-0 text-xs">
                  <div className="font-semibold text-zinc-300">{f.scene_label || "Full timeline"}</div>
                  <div className="text-zinc-600">{f.resolution} · {f.status}{f.finished_at ? ` · ${fmtDate(f.finished_at)}` : ""}</div>
                </div>
                <a href={`/api/backend${f.final_url}`} download className="ml-auto btn-ghost !py-1 text-xs">⬇</a>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function EmptyOutput({ what }: { what: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-white/10 p-12 text-center text-sm text-zinc-600">
      No {what} yet — run the pipeline to produce this stage.
    </div>
  );
}
