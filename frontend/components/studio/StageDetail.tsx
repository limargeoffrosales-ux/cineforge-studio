"use client";
import { StageDef, StageState } from "@/lib/types";
import { Badge, Card, CopyButton } from "@/components/ui";
import { fmtDuration, STAGE_ICONS } from "@/lib/utils";

function KeyVal({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div>
      <div className="label mb-1">{k}</div>
      <div className="text-sm text-zinc-300">{v || "—"}</div>
    </div>
  );
}

function SceneLine({ d, i }: { d: any; i: number }) {
  return (
    <div className="rounded-xl border border-white/8 bg-ink-850 p-3.5">
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <span className="chip text-gold-400">Scene {i + 1}</span>
        <span className="text-sm font-semibold text-zinc-100">{d.title}</span>
        <span className="ml-auto text-xs text-zinc-500">{fmtDuration(d.duration || 0)}</span>
      </div>
      <div className="mb-2 text-xs italic text-zinc-500">{d.direction}</div>
      <div className="space-y-1">
        {(d.dialogue || []).map((l: any, j: number) => (
          <div key={j} className="flex gap-2 text-[13px]">
            <span className="w-20 shrink-0 font-semibold text-violet-400">{l.speaker}</span>
            <span className="text-zinc-300">{l.line}</span>
          </div>
        ))}
      </div>
      <div className="mt-2.5 flex flex-wrap gap-1.5">
        <span className="chip">➡ {d.transition}</span>
        <span className="chip">🔊 {d.audio_cue}</span>
      </div>
    </div>
  );
}

function StoryboardPanel({ p, i }: { p: any; i: number }) {
  return (
    <Card className="overflow-hidden">
      {/* panel visual: gradient + framing overlay */}
      <div
        className="relative grid h-32 place-items-center overflow-hidden"
        style={{
          background: `linear-gradient(135deg, ${["#2b2720", "#1c2433", "#2a1f14", "#14251c", "#221733"][i % 5]}, ${["#4a3d1e", "#2c3e5a", "#593a1e", "#23402f", "#3a2a55"][i % 5]})`,
        }}
      >
        <div className="absolute inset-0 opacity-30" style={{ backgroundImage: "radial-gradient(circle at 50% 45%, rgba(255,255,255,0.25) 0%, transparent 38%)" }} />
        {/* rule of thirds */}
        <div className="absolute inset-0 opacity-[0.16]">
          <div className="absolute left-1/3 top-0 h-full w-px bg-white" />
          <div className="absolute left-2/3 top-0 h-full w-px bg-white" />
          <div className="absolute top-1/3 left-0 w-full h-px bg-white" />
          <div className="absolute top-2/3 left-0 w-full h-px bg-white" />
        </div>
        <div className="relative rounded-lg border border-white/25 bg-black/40 px-2.5 py-1 text-[10px] font-semibold text-white backdrop-blur-sm">
          {p.composition}
        </div>
        <div className="absolute bottom-2 right-2 text-[10px] text-white/70">{fmtDuration(p.duration || 0)}</div>
      </div>
      <div className="space-y-2 p-3.5 text-xs">
        <div className="flex flex-wrap gap-1.5">
          <span className="chip">🎥 {p.camera}</span>
          <span className="chip">💡 {p.lighting}</span>
          <span className="chip">🎭 {p.mood}</span>
        </div>
        <div className="text-zinc-500">{p.dialogue}</div>
        <div className="flex flex-wrap gap-1.5">
          {(p.effects || []).map((e: string) => (
            <span key={e} className="chip">✦ {e}</span>
          ))}
        </div>
      </div>
    </Card>
  );
}

function ShotRow({ s }: { s: any }) {
  return (
    <tr className="border-b border-white/5 text-[12.5px] last:border-0 hover:bg-white/3">
      <td className="px-3 py-2.5 font-mono text-[11px] text-zinc-600">{s.id}</td>
      <td className="px-3 py-2.5">
        <span className="chip text-violet-400">{s.shot_type}</span>
      </td>
      <td className="px-3 py-2.5">{s.camera_type}</td>
      <td className="px-3 py-2.5">{s.lens}</td>
      <td className="px-3 py-2.5">{s.movement}</td>
      <td className="px-3 py-2.5 text-zinc-500">{s.background}</td>
      <td className="px-3 py-2.5 text-zinc-500">{s.time_of_day}</td>
    </tr>
  );
}

export function StageDetail({ stage, state, output }: { stage: StageDef; state: StageState; output?: any }) {
  const sid = stage.id;
  return (
    <div>
      <div className="mb-4 flex items-start gap-3">
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-gold-400/20 bg-gold-400/10 text-2xl">
          {STAGE_ICONS[sid]}
        </div>
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="font-display text-lg font-semibold text-zinc-50">{stage.name}</h2>
            <Badge tone={state.status === "completed" ? "green" : state.status === "running" ? "gold" : state.status === "failed" ? "red" : "zinc"}>
              {state.status}
            </Badge>
          </div>
          <p className="mt-0.5 text-sm text-zinc-500">{stage.desc}</p>
        </div>
      </div>

      {state.status === "pending" && (
        <div className="rounded-2xl border border-dashed border-white/10 p-8 text-center text-sm text-zinc-600">
          This stage hasn't run yet — hit <span className="font-semibold text-gold-400">Run pipeline</span> to produce it.
        </div>
      )}

      {state.status === "running" && (
        <div className="rounded-2xl border border-gold-400/25 bg-gold-400/5 p-8 text-center">
          <div className="mb-2 text-3xl">{STAGE_ICONS[sid]}</div>
          <div className="text-sm font-semibold text-gold-400">Producing {stage.name.toLowerCase()}…</div>
          <div className="mx-auto mt-3 h-1.5 w-56 overflow-hidden rounded-full bg-white/8">
            <div className="h-full rounded-full bg-gold-400 transition-all" style={{ width: `${state.progress}%` }} />
          </div>
        </div>
      )}

      {state.status === "failed" && (
        <div className="rounded-2xl border border-red-400/25 bg-red-400/5 p-8 text-center text-sm text-red-300">{state.notes}</div>
      )}

      {state.status === "completed" && output && (
        <div className="space-y-4">
          {/* RESEARCH */}
          {sid === "research" && (
            <>
              <Card className="p-5">
                <div className="label mb-2">Summary</div>
                <p className="text-sm leading-relaxed text-zinc-300">{output.summary}</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {(output.hooks || []).map((h: string, i: number) => (
                    <span key={i} className="chip text-gold-400">⚡ {h}</span>
                  ))}
                </div>
              </Card>
              <div className="grid gap-3 md:grid-cols-2">
                {(output.findings || []).map((f: any, i: number) => (
                  <Card key={i} className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-semibold text-zinc-100">{f.title}</div>
                      <Badge tone={f.confidence > 0.85 ? "green" : "gold"}>{(f.confidence * 100).toFixed(0)}%</Badge>
                    </div>
                    <p className="mt-1.5 text-xs leading-relaxed text-zinc-500">{f.summary}</p>
                  </Card>
                ))}
              </div>
              <Card className="p-5">
                <div className="label mb-3">Timeline</div>
                <div className="space-y-0">
                  {(output.timeline || []).map((t: any, i: number) => (
                    <div key={i} className="flex gap-3">
                      <div className="flex w-16 shrink-0 flex-col items-center">
                        <span className="font-mono text-xs font-bold text-gold-400">{t.year}</span>
                        {i < output.timeline.length - 1 && <div className="my-1 w-px flex-1 bg-white/10" />}
                      </div>
                      <div className="pb-4 text-xs text-zinc-400">{t.event}</div>
                    </div>
                  ))}
                </div>
              </Card>
            </>
          )}

          {/* SCRIPT */}
          {sid === "script" && (
            <>
              <Card className="p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-display text-lg font-semibold text-zinc-50">{output.title}</h3>
                  <CopyButton text={output.title} />
                  <span className="ml-auto flex gap-2">
                    <Badge tone="violet">{output.structure}</Badge>
                    <Badge tone="gold">{fmtDuration(output.total_duration || 0)}</Badge>
                  </span>
                </div>
                <p className="mt-3 rounded-xl border border-gold-400/15 bg-gold-400/5 px-4 py-3 text-sm italic text-zinc-300">
                  🪝 {output.hook}
                </p>
              </Card>
              <div className="space-y-2.5">
                {(output.scenes || []).map((s: any, i: number) => (
                  <SceneLine key={i} d={s} i={i} />
                ))}
              </div>
            </>
          )}

          {/* STORYBOARD */}
          {sid === "storyboard" && (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {(output.panels || []).map((p: any, i: number) => (
                <StoryboardPanel key={i} p={p} i={i} />
              ))}
            </div>
          )}

          {/* SCENE PLANNING */}
          {sid === "scene_planning" && (
            <div className="space-y-2.5">
              {(output.scenes || []).map((s: any, i: number) => (
                <Card key={i} className="grid gap-3 p-4 sm:grid-cols-3">
                  <div>
                    <div className="label mb-1">Scene</div>
                    <div className="text-sm font-semibold text-zinc-200">{s.title}</div>
                    <div className="text-xs text-zinc-500">{fmtDuration(s.duration)}</div>
                  </div>
                  <KeyVal k="Setting" v={s.setting} />
                  <KeyVal k="Environment family" v={s.environment_family} />
                  <KeyVal k="Time of day" v={s.time_of_day} />
                  <KeyVal k="Props" v={s.props} />
                  <KeyVal k="VFX wishlist" v={s.vfx_wishlist} />
                </Card>
              ))}
            </div>
          )}

          {/* CHARACTERS */}
          {sid === "character_design" && (
            <div className="grid gap-3 sm:grid-cols-2">
              {(output.characters || []).map((c: any, i: number) => (
                <Card key={i} className="p-4">
                  <div className="mb-3 flex items-center gap-3">
                    <div
                      className="grid h-11 w-11 place-items-center rounded-full text-sm font-bold text-ink-950"
                      style={{ background: c.palette?.[0] || "#f5b301" }}
                    >
                      {c.name?.slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-zinc-100">{c.name}</div>
                      <div className="text-xs text-zinc-500">{c.archetype} · {c.relationship}</div>
                    </div>
                  </div>
                  <div className="mb-2 flex flex-wrap gap-1.5">
                    {(c.traits || []).map((t: string) => (
                      <span key={t} className="chip">{t}</span>
                    ))}
                  </div>
                  <KeyVal k="Voice" v={`${c.voice?.pitch || "—"} · ${c.voice?.rate || "—"} · ${c.voice?.style || "—"}`} />
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {(c.expressions || []).map((e: string) => (
                      <span key={e} className="chip text-violet-400">😊 {e}</span>
                    ))}
                  </div>
                </Card>
              ))}
            </div>
          )}

          {/* ENVIRONMENTS */}
          {sid === "environment_design" && (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {(output.environments || []).map((e: any, i: number) => (
                <Card key={i} className="overflow-hidden">
                  <div
                    className="relative h-24"
                    style={{ background: `linear-gradient(135deg, ${e.palette?.[1] || "#222"}, ${e.palette?.[0] || "#333"})` }}
                  >
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_30%,rgba(255,255,255,0.18),transparent_50%)]" />
                    <div className="absolute bottom-2 left-3 text-xs font-semibold text-white/90 drop-shadow">{e.name}</div>
                  </div>
                  <div className="p-3.5 text-xs">
                    <div className="mb-2 flex gap-1.5">
                      <span className="chip">{e.category.replace(/_/g, " ")}</span>
                      {(e.weather || []).map((w: string) => (
                        <span key={w} className="chip">☁️ {w}</span>
                      ))}
                    </div>
                    <p className="line-clamp-2 text-zinc-500">{e.description}</p>
                  </div>
                </Card>
              ))}
            </div>
          )}

          {/* SHOTS */}
          {sid === "shot_planning" && (
            <Card className="overflow-x-auto">
              <table className="w-full min-w-[720px]">
                <thead>
                  <tr className="border-b border-white/8 text-left text-[11px] uppercase tracking-wider text-zinc-600">
                    <th className="px-3 py-2.5">Shot</th>
                    <th className="px-3 py-2.5">Type</th>
                    <th className="px-3 py-2.5">Camera</th>
                    <th className="px-3 py-2.5">Lens</th>
                    <th className="px-3 py-2.5">Movement</th>
                    <th className="px-3 py-2.5">Background</th>
                    <th className="px-3 py-2.5">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {(output.shots || []).map((s: any, i: number) => (
                    <ShotRow key={i} s={s} />
                  ))}
                </tbody>
              </table>
            </Card>
          )}

          {/* VIDEO / VOICE / SOUND / MUSIC / EDIT / MGFX — structured readouts */}
          {["video_generation", "voice_generation", "sound_design", "music", "editing", "motion_graphics"].includes(sid) && (
            <div className="space-y-3">
              {sid === "video_generation" && (
                <Card className="p-5">
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <Badge tone="violet">routing: {output.provider === "auto" ? "smart per-scene" : output.provider}</Badge>
                    <Badge tone="gold">{output.resolutions?.join(" · ")}</Badge>
                    <Badge tone="zinc">{output.fps} fps</Badge>
                    {output.ensemble && <Badge tone="green">ensemble +{output.ensemble.uplift_pts} pts</Badge>}
                  </div>
                  <div className="grid gap-2 sm:grid-cols-3">
                    <KeyVal k="Character consistency" v={output.consistency?.character_locked ? "locked ✔" : "—"} />
                    <KeyVal k="Temporal consistency" v={output.consistency?.temporal} />
                    <KeyVal k="Physics-aware motion" v={output.consistency?.physics} />
                  </div>
                  <div className="mt-4 space-y-2">
                    {(output.scenes || []).map((s: any, i: number) => (
                      <div key={i} className="rounded-xl border border-white/8 bg-ink-850 p-3">
                        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs font-semibold text-zinc-200">
                          <span className="text-gold-400">{s.scene_id}</span>
                          <span className="text-zinc-600">{s.clips?.length || 0} clips</span>
                          <span className="ml-auto flex gap-1.5">
                            {[...new Set((s.clips || []).map((c: any) => c.provider))].map((p) => (
                              <span key={p as string} className="chip text-violet-400">{p as string}</span>
                            ))}
                          </span>
                        </div>
                        {(s.clips || []).map((c: any, j: number) => (
                          <div key={j} className="mb-1.5 rounded-lg bg-black/25 px-2.5 py-1.5">
                            <div className="mb-0.5 flex items-center gap-2 text-[10px]">
                              <span className="font-bold text-violet-400">{c.provider}</span>
                              <span className="text-zinc-600">
                                {c.shot?.shot_type} · {c.shot?.camera_type} · {c.shot?.movement} · {c.aspect_ratio}
                              </span>
                              {(c.routing?.reasons || []).slice(0, 2).map((r: string) => (
                                <span key={r} className="chip text-emerald-400/80">✓ {r}</span>
                              ))}
                            </div>
                            <div className="font-mono text-[11px] leading-relaxed text-zinc-500">{c.prompt}</div>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                  <div className="mt-3 flex justify-end">
                    <a href="/app/video" className="btn-ghost !py-1.5 text-xs">🎬 Open Video Lab — render, compare & assemble</a>
                  </div>
                </Card>
              )}
              {sid === "voice_generation" && (
                <Card className="p-5">
                  <div className="mb-3 flex flex-wrap gap-2">
                    {(output.voices || []).map((v: any, i: number) => (
                      <Badge key={i} tone="violet">{v.character} · {v.profile?.style}</Badge>
                    ))}
                    <Badge tone="gold">lip-sync: {output.lip_sync?.enabled ? "on" : "off"}</Badge>
                  </div>
                  <div className="max-h-72 space-y-1.5 overflow-y-auto">
                    {(output.narration_tracks || []).map((l: any, i: number) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <span className="w-16 shrink-0 font-mono text-zinc-600">{l.start}s</span>
                        <span className="w-20 shrink-0 font-semibold text-violet-400">{l.speaker}</span>
                        <span className="truncate text-zinc-400">{l.text}</span>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
              {sid === "sound_design" && (
                <div className="grid gap-3 md:grid-cols-2">
                  <Card className="p-4">
                    <div className="label mb-2">SFX cues</div>
                    {(output.sfx || []).map((s: any, i: number) => (
                      <div key={i} className="mb-1.5 flex items-center justify-between rounded-lg bg-ink-850 px-3 py-2 text-xs">
                        <span className="font-mono text-zinc-500">{s.scene_id}</span>
                        <span className="text-zinc-300">{s.cue}</span>
                        <span className="text-zinc-600">{s.gain_db} dB</span>
                      </div>
                    ))}
                  </Card>
                  <Card className="p-4">
                    <div className="label mb-2">Ambience & foley</div>
                    {(output.ambience || []).map((a: any, i: number) => (
                      <div key={i} className="mb-1.5 flex items-center justify-between rounded-lg bg-ink-850 px-3 py-2 text-xs">
                        <span className="font-mono text-zinc-500">{a.scene_id}</span>
                        <span className="text-zinc-300">{a.bed}</span>
                        <span className="text-zinc-600">{a.level}</span>
                      </div>
                    ))}
                    <div className="mt-2 text-xs text-zinc-500">🦶 {(output.foley || []).map((f: any) => f.action).join(", ")}</div>
                  </Card>
                </div>
              )}
              {sid === "music" && (
                <Card className="p-5">
                  <div className="mb-3 flex gap-2">
                    <Badge tone="green">master: {output.master?.loudness}</Badge>
                    <Badge tone="zinc">{output.master?.true_peak}</Badge>
                    <Badge tone="violet">{output.license}</Badge>
                  </div>
                  <div className="space-y-2">
                    {(output.tracks || []).map((t: any, i: number) => (
                      <div key={i} className="flex flex-wrap items-center gap-2 rounded-xl bg-ink-850 px-3.5 py-2.5 text-xs">
                        <span className="font-mono text-zinc-500">{t.scene_id}</span>
                        <span className="font-semibold text-zinc-200">{t.title}</span>
                        <span className="text-zinc-500">{t.genre}</span>
                        <span className="ml-auto text-zinc-400">{t.mood} · {t.bpm} BPM · {t.key}</span>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
              {sid === "editing" && (
                <div className="grid gap-3 md:grid-cols-2">
                  <Card className="p-4">
                    <div className="label mb-2">Assembly</div>
                    {(output.assembly || []).map((a: any, i: number) => (
                      <div key={i} className="mb-1.5 flex items-center gap-2 rounded-lg bg-ink-850 px-3 py-2 text-xs">
                        <span className="font-mono text-zinc-600">#{a.order}</span>
                        <span className="font-mono text-zinc-500">{a.scene_id}</span>
                        <span className="ml-auto text-zinc-400">➡ {a.transition}</span>
                      </div>
                    ))}
                    <div className="mt-3 space-y-1 text-xs text-zinc-500">
                      {(output.smart_cuts || []).map((c: any, i: number) => (
                        <div key={i}>✂ {c.rule}</div>
                      ))}
                    </div>
                  </Card>
                  <Card className="p-4">
                    <div className="label mb-2">Color & motion</div>
                    <div className="mb-3 rounded-xl border border-violet-400/20 bg-violet-400/5 p-3 text-xs text-violet-300">
                      🎨 {output.color?.grade} — contrast {output.color?.contrast}, warmth {output.color?.warmth}
                    </div>
                    <div className="space-y-1.5 text-xs text-zinc-500">
                      {(output.b_roll || []).map((b: any, i: number) => (
                        <div key={i}>
                          <span className="font-mono text-zinc-600">{b.scene_id}</span> → {b.suggested?.join(", ")}
                        </div>
                      ))}
                      <div>🎯 Motion tracking: {(output.motion_tracking || []).map((m: any) => m.target).join(", ")}</div>
                      <div>⚡ Speed ramp: {(output.speed_ramps || []).map((r: any) => r.profile).join(", ")}</div>
                    </div>
                  </Card>
                </div>
              )}
              {sid === "motion_graphics" && (
                <div className="grid gap-3 md:grid-cols-2">
                  <Card className="p-4">
                    <div className="label mb-2">Titles & lower thirds</div>
                    {(output.titles || []).map((t: any, i: number) => (
                      <div key={i} className="mb-2 rounded-xl border border-gold-400/20 bg-gold-400/5 p-3 text-sm font-semibold text-gold-400">
                        {t.text} <span className="ml-1 text-[10px] font-normal text-zinc-500">{t.style}</span>
                      </div>
                    ))}
                    {(output.lower_thirds || []).map((l: any, i: number) => (
                      <div key={i} className="mb-1.5 rounded-lg bg-ink-850 px-3 py-2 text-xs">
                        <span className="font-mono text-zinc-600">{l.scene_id}</span> <span className="text-zinc-300">{l.text}</span>
                      </div>
                    ))}
                  </Card>
                  <Card className="p-4">
                    <div className="label mb-2">Infographics & callouts</div>
                    <div className="mb-2 flex flex-wrap gap-1.5">
                      {(output.infographics || []).map((g: string, i: number) => (
                        <span key={i} className="chip text-violet-400">📊 {g}</span>
                      ))}
                    </div>
                    {(output.callouts || []).map((c: any, i: number) => (
                      <div key={i} className="mb-1.5 rounded-lg bg-ink-850 px-3 py-2 text-xs">
                        <span className="font-mono text-zinc-600">{c.scene}</span> <span className="font-semibold text-zinc-200">{c.text}</span> · {c.position}
                      </div>
                    ))}
                  </Card>
                </div>
              )}
            </div>
          )}

          {/* SUBTITLES */}
          {sid === "subtitles" && (
            <Card className="p-5">
              <div className="mb-3 flex flex-wrap gap-2">
                <Badge tone="gold">word highlighting on</Badge>
                <Badge tone="zinc">{output.formats?.join(" · ")}</Badge>
                <CopyButton text={(output.entries || []).map((e: any) => `${e.start} → ${e.end}  ${e.text}`).join("\n")} label="Export SRT" />
              </div>
              <div className="max-h-80 space-y-1 overflow-y-auto">
                {(output.entries || []).map((e: any, i: number) => (
                  <div key={i} className="flex items-center gap-3 rounded-lg bg-ink-850 px-3 py-1.5 text-xs">
                    <span className="w-20 shrink-0 font-mono text-zinc-600">
                      {e.start}s–{e.end}s
                    </span>
                    <span className="font-semibold text-violet-400">{e.speaker}</span>
                    <span className="text-zinc-300">{e.text}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* THUMBNAILS */}
          {sid === "thumbnail" && (
            <div className="grid gap-3 md:grid-cols-3">
              {(output.concepts || []).map((t: any, i: number) => (
                <Card key={i} className="overflow-hidden">
                  <div
                    className="relative flex h-40 items-center justify-center"
                    style={{ background: `linear-gradient(140deg, ${t.palette?.[1] || "#111"}, ${t.palette?.[0] || "#222"})` }}
                  >
                    <div className="absolute inset-0 grid place-items-center opacity-25">
                      <div className="h-24 w-32 rounded-2xl border border-white/40" />
                    </div>
                    <div className="relative rounded-xl border border-white/20 bg-black/50 px-3 py-2 text-center backdrop-blur">
                      <div className="text-[11px] font-bold leading-tight text-white">{t.concept}</div>
                    </div>
                    <span className="absolute left-2.5 top-2.5 chip">CTR {t.ctr_rating}</span>
                  </div>
                  <div className="space-y-1.5 p-3.5 text-[11px]">
                    <div className="text-zinc-500">🎯 {t.ctr_rating.split("—")[1]}</div>
                    <div className="flex flex-wrap gap-1.5">
                      {(t.palette || []).map((c: string) => (
                        <span key={c} className="h-4 w-4 rounded-full border border-white/15" style={{ background: c }} title={c} />
                      ))}
                    </div>
                    <div className="text-zinc-500">🔤 {t.typography}</div>
                  </div>
                </Card>
              ))}
            </div>
          )}

          {/* SEO */}
          {sid === "seo" && (
            <div className="space-y-3">
              <Card className="p-5">
                <div className="label mb-2">Titles</div>
                <div className="space-y-2">
                  {(output.titles || []).map((t: string, i: number) => (
                    <div key={i} className="flex items-center justify-between gap-3 rounded-xl bg-ink-850 px-3.5 py-2.5 text-sm text-zinc-200">
                      <span className="truncate">{t}</span>
                      <CopyButton text={t} />
                    </div>
                  ))}
                </div>
              </Card>
              <Card className="p-5">
                <div className="label mb-2">Description</div>
                <pre className="whitespace-pre-wrap rounded-xl border border-white/8 bg-ink-850 p-4 font-sans text-[13px] leading-relaxed text-zinc-400">{output.description}</pre>
                <div className="mt-3 flex justify-end">
                  <CopyButton text={output.description || ""} />
                </div>
              </Card>
              <div className="grid gap-3 md:grid-cols-2">
                <Card className="p-4">
                  <div className="label mb-2">Tags</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(output.tags || []).map((t: string) => (
                      <span key={t} className="chip">#{t.replace(/\s+/g, "")}</span>
                    ))}
                  </div>
                </Card>
                <Card className="p-4">
                  <div className="label mb-2">Hashtags</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(output.hashtags || []).map((t: string) => (
                      <span key={t} className="chip text-violet-400">{t}</span>
                    ))}
                  </div>
                </Card>
              </div>
              <Card className="p-4">
                <div className="label mb-2">Chapters</div>
                <div className="space-y-1.5">
                  {(output.chapters || []).map((c: any, i: number) => (
                    <div key={i} className="flex items-center gap-3 text-xs">
                      <span className="font-mono text-gold-400">{Math.floor(c.start / 60)}:{String(c.start % 60).padStart(2, "0")}</span>
                      <span className="text-zinc-300">{c.label}</span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {/* PUBLISHING */}
          {sid === "publishing" && (
            <div className="grid gap-3 md:grid-cols-2">
              {(output.platforms || []).map((p: any, i: number) => (
                <Card key={i} className="p-4">
                  <div className="mb-1 flex items-center gap-2.5">
                    <span className="text-xl">{p.id === "youtube" ? "▶️" : p.id === "tiktok" ? "🎵" : p.id === "facebook" ? "📘" : p.id === "instagram" ? "📸" : "🎞️"}</span>
                    <span className="text-sm font-semibold text-zinc-100">{p.name}</span>
                    <Badge tone="violet" className="ml-auto">{p.api}</Badge>
                  </div>
                  <div className="text-xs text-zinc-500">{p.notes}</div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
