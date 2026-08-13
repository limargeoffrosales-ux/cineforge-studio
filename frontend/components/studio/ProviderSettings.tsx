"use client";
import { useEffect, useState } from "react";
import { KeyRound, Music4, Plug2, Save, Trash2, Zap, CheckCircle2, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { ProviderSetting } from "@/lib/types";
import { Badge, Button, Card, Input, Select, Tabs } from "@/components/ui";
import { cx } from "@/lib/utils";

const KIND_LABEL: Record<string, string> = { video: "Video", llm: "LLM + TTS", tts: "TTS" };
const KIND_TONE: Record<string, "violet" | "gold" | "blue"> = { video: "violet", llm: "gold", tts: "blue" };

function ProviderRow({ p, onSaved }: { p: ProviderSetting; onSaved: () => void }) {
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [testResult, setTestResult] = useState<null | { ok: boolean; detail: string; latency_ms?: number }>(null);

  const save = async () => {
    if (!key.trim()) return;
    setBusy(true);
    try {
      await api(`/settings/providers/${p.id}`, { method: "PUT", body: { key: key.trim() } });
      setKey("");
      onSaved();
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    await api(`/settings/providers/${p.id}`, { method: "DELETE" });
    onSaved();
  };

  const test = async () => {
    setBusy(true);
    setTestResult(null);
    try {
      setTestResult(await api(`/settings/providers/${p.id}/test`, { method: "POST" }));
    } catch (e: any) {
      setTestResult({ ok: false, detail: e.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-5">
      <div className="mb-3 flex flex-wrap items-center gap-2.5">
        <div className="grid h-9 w-9 place-items-center rounded-lg border border-white/8 bg-ink-850">
          <Plug2 className="h-4 w-4 text-zinc-400" />
        </div>
        <div className="font-display text-sm font-semibold text-zinc-100">{p.name}</div>
        <Badge tone={KIND_TONE[p.kind] || "zinc"}>{KIND_LABEL[p.kind]}</Badge>
        <Badge tone={p.configured ? "green" : "zinc"}>
          {p.configured ? `configured (${p.source})` : "not configured"}
        </Badge>
        {p.last4 && <span className="font-mono text-[11px] text-zinc-600">{p.last4}</span>}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="password"
          className="input max-w-sm !py-2 font-mono text-xs"
          placeholder={p.configured ? "•••••••• (leave empty to keep)" : "Paste API key…"}
          value={key}
          onChange={(e) => setKey(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && save()}
        />
        <Button onClick={save} disabled={busy || !key.trim()} className="!py-2 text-xs">
          <Save className="h-3.5 w-3.5" /> Save
        </Button>
        <Button variant="ghost" onClick={test} disabled={busy || !p.configured} className="!py-2 text-xs">
          <Zap className="h-3.5 w-3.5" /> Test
        </Button>
        {p.configured && (
          <button onClick={remove} className="rounded-lg p-2 text-zinc-600 transition hover:bg-red-500/10 hover:text-red-400" title="Remove key">
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>
      {testResult && (
        <div
          className={cx(
            "mt-3 flex items-start gap-2 rounded-xl border px-3.5 py-2.5 text-xs",
            testResult.ok ? "border-emerald-400/25 bg-emerald-400/8 text-emerald-300" : "border-red-400/25 bg-red-400/8 text-red-300"
          )}
        >
          {testResult.ok ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
          <span>
            {testResult.detail}
            {testResult.latency_ms ? <span className="ml-2 text-zinc-500">{testResult.latency_ms} ms</span> : null}
          </span>
        </div>
      )}
      {p.kind === "video" && !p.configured && (
        <p className="mt-2.5 text-[11px] text-zinc-600">
          No key → scenes routed to this model render with the built-in procedural cinematographer (still playable, still graded).
        </p>
      )}
    </Card>
  );
}

export function ProvidersPanel() {
  const [providers, setProviders] = useState<ProviderSetting[] | null>(null);
  const load = () => api<{ providers: ProviderSetting[] }>("/settings/providers").then((d) => setProviders(d.providers)).catch(() => {});
  useEffect(() => {
    load();
  }, []);
  if (!providers) return <Card className="p-6 text-sm text-zinc-500">Loading providers…</Card>;
  return (
    <div className="space-y-3">
      {providers.map((p) => (
        <ProviderRow key={p.id} p={p} onSaved={load} />
      ))}
      <div className="rounded-xl border border-white/8 bg-ink-850 p-4 text-xs leading-relaxed text-zinc-500">
        <KeyRound className="mr-1.5 inline h-3.5 w-3.5 text-gold-400" />
        Keys are <b className="text-zinc-300">encrypted at rest</b> (Fernet, key derived from the server secret) and only ever
        sent to the provider's own API. Env vars still work as a fallback: <code className="font-mono text-zinc-400">VEO_API_KEY</code>,{" "}
        <code className="font-mono text-zinc-400">RUNWAY_API_KEY</code>, <code className="font-mono text-zinc-400">KLING_API_KEY</code>,{" "}
        <code className="font-mono text-zinc-400">SEEDANCE_API_KEY</code>, <code className="font-mono text-zinc-400">OPENAI_API_KEY</code>,{" "}
        <code className="font-mono text-zinc-400">ELEVENLABS_API_KEY</code>.
      </div>
    </div>
  );
}

export function AudioPanel() {
  const [audio, setAudio] = useState<any>(null);
  const [voices, setVoices] = useState<any>({});
  const [busy, setBusy] = useState(false);
  const load = () =>
    api("/settings/audio")
      .then((d) => {
        setAudio(d.audio);
        setVoices(d.voices);
      })
      .catch(() => {});
  useEffect(() => {
    load();
  }, []);

  const set = (k: string, v: any) => setAudio((a: any) => ({ ...a, [k]: v }));
  const save = async () => {
    setBusy(true);
    try {
      await api("/settings/audio", { method: "PUT", body: audio });
    } finally {
      setBusy(false);
    }
  };

  if (!audio) return <Card className="p-6 text-sm text-zinc-500">Loading audio defaults…</Card>;
  return (
    <div className="max-w-2xl space-y-5">
      <Card className="p-5">
        <div className="mb-4 flex items-center gap-2">
          <Music4 className="h-4 w-4 text-gold-400" />
          <h3 className="text-sm font-semibold text-zinc-100">Soundtrack defaults</h3>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label mb-1.5 block">Music style</label>
            <Select
              options={[
                { id: "cinematic orchestral", label: "Cinematic orchestral" },
                { id: "ambient electronic", label: "Ambient electronic" },
                { id: "neon synthwave", label: "Neon synthwave" },
                { id: "acoustic folk", label: "Acoustic folk" },
                { id: "uplifting", label: "Uplifting" },
                { id: "tense", label: "Tense" },
              ]}
              value={audio.music_style}
              onChange={(v) => set("music_style", v)}
            />
          </div>
          <div>
            <label className="label mb-1.5 block">Narration provider</label>
            <Select
              options={[
                { id: "edge", label: "Microsoft Edge neural (free — no key)" },
                { id: "openai", label: "OpenAI TTS (tts-1-hd)" },
                { id: "elevenlabs", label: "ElevenLabs" },
              ]}
              value={audio.tts_provider}
              onChange={(v) => set("tts_provider", v)}
            />
          </div>
          <div>
            <label className="label mb-1.5 block">Narration voice</label>
            <Select
              options={(voices[audio.tts_provider]?.voices || []).map((v: any) => ({ id: v.id, label: `${v.id} — ${v.tone}` }))}
              value={audio.narration_voice}
              onChange={(v) => set("narration_voice", v)}
            />
          </div>
          <div>
            <label className="label mb-1.5 block">Sound effects</label>
            <button
              onClick={() => set("sfx_enabled", !audio.sfx_enabled)}
              className={cx(
                "w-full rounded-xl border px-3.5 py-2.5 text-sm font-medium transition",
                audio.sfx_enabled ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300" : "border-white/10 bg-ink-850 text-zinc-500"
              )}
            >
              {audio.sfx_enabled ? "● On — risers, impacts, whooshes" : "○ Off"}
            </button>
          </div>
        </div>
        <div className="mt-5 flex items-center justify-between border-t border-white/8 pt-4">
          <p className="text-[11px] text-zinc-600">
            Works fully keyless — narration uses free Microsoft Edge neural voices; music/SFX/ambience are synthesized locally.
            Add a paid TTS key anytime for premium voices.
          </p>
          <Button onClick={save} disabled={busy}>
            <Save className="h-4 w-4" /> Save defaults
          </Button>
        </div>
      </Card>
      <Card className="p-5">
        <h3 className="mb-3 text-sm font-semibold text-zinc-100">Voice catalog</h3>
        <div className="space-y-3">
          {Object.entries(voices).map(([pid, cat]: any) => (
            <div key={pid}>
              <div className="label mb-1.5">{cat.name}</div>
              <div className="flex flex-wrap gap-1.5">
                {cat.voices.map((v: any) => (
                  <span key={v.id} className="chip">
                    🎙 {v.id} — {v.tone}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
