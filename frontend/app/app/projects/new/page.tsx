"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Sparkles, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button, Input, Select, Textarea, Badge } from "@/components/ui";
import { Topbar } from "@/components/studio/Shell";
import { CATEGORIES, LANGUAGES, TONES } from "@/lib/utils";

const SUGGESTIONS = [
  "Banaue Rice Terraces",
  "How AI Video Generation Works",
  "The History of Philippine Coffee",
  "Tropical Storm Science",
  "The Future of Electric Boats",
  "Inside the Chocolate Hills",
];

export default function NewProjectPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [category, setCategory] = useState("explainer");
  const [tone, setTone] = useState("cinematic");
  const [language, setLanguage] = useState("en");
  const [duration, setDuration] = useState(120);
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const p = await api("/projects", {
        method: "POST",
        body: { title, topic: topic || title, category, tone, language, target_duration: duration, description },
      });
      router.push(`/app/projects/${p.id}`);
    } catch (err: any) {
      setError(err.message || "Could not create project");
      setBusy(false);
    }
  };

  return (
    <div>
      <Topbar />
      <div className="mx-auto max-w-2xl px-6 py-8">
        <Link href="/app/projects" className="mb-6 inline-flex items-center gap-1.5 text-xs font-medium text-zinc-500 hover:text-zinc-300">
          <ArrowLeft className="h-3.5 w-3.5" /> Back to projects
        </Link>

        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
          <div className="mb-8 flex items-center gap-3">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-gold-400 to-amber-600 text-ink-950 shadow-[0_0_30px_-6px_rgba(245,179,1,0.6)]">
              <Sparkles className="h-6 w-6" />
            </div>
            <div>
              <h1 className="font-display text-2xl font-bold tracking-tight text-zinc-50">New production</h1>
              <p className="text-sm text-zinc-500">One idea in — a fully produced video out.</p>
            </div>
          </div>

          <form onSubmit={submit} className="card space-y-5 p-6">
            <div className="space-y-4">
              <div>
                <label className="label mb-1.5 block">Title</label>
                <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. The 2,000-Year Stairway to the Sky" required />
              </div>
              <div>
                <label className="label mb-1.5 block">Topic (what the AI researches)</label>
                <Input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. Banaue Rice Terraces" />
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} type="button" onClick={() => setTopic(s)} className="chip transition hover:border-gold-400/40 hover:text-gold-400">
                      {s}
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label className="label mb-1.5 block">Format</label>
                  <Select options={CATEGORIES} value={category} onChange={setCategory} />
                </div>
                <div>
                  <label className="label mb-1.5 block">Tone</label>
                  <Select options={TONES.map((t) => ({ id: t, label: t.charAt(0).toUpperCase() + t.slice(1) }))} value={tone} onChange={setTone} />
                </div>
                <div>
                  <label className="label mb-1.5 block">Language</label>
                  <Select options={LANGUAGES} value={language} onChange={setLanguage} />
                </div>
              </div>
              <div>
                <label className="label mb-1.5 block">Target duration — <span className="text-gold-400">{duration}s</span></label>
                <input
                  type="range"
                  min={30}
                  max={600}
                  step={10}
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                  className="w-full accent-[#f5b301]"
                />
              </div>
              <div>
                <label className="label mb-1.5 block">Description</label>
                <Textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What's this video about?" />
              </div>
            </div>

            {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">{error}</div>}

            <div className="flex items-center justify-between pt-1">
              <Badge tone="violet">18-stage pipeline ready</Badge>
              <Button type="submit" disabled={busy || !title.trim()}>
                <Sparkles className="h-4 w-4" /> {busy ? "Creating…" : "Create & open studio"}
              </Button>
            </div>
          </form>
        </motion.div>
      </div>
    </div>
  );
}
