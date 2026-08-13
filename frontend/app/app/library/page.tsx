"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Plus, Globe, Users, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { CharacterItem, EnvironmentItem } from "@/lib/types";
import { Badge, Button, Card, Input, Modal, Select, Tabs, Textarea } from "@/components/ui";
import { Topbar } from "@/components/studio/Shell";
import { cx } from "@/lib/utils";

function LibraryInner() {
  const params = useSearchParams();
  const [tab, setTab] = useState(params.get("tab") || "characters");
  const [characters, setCharacters] = useState<CharacterItem[] | null>(null);
  const [environments, setEnvironments] = useState<EnvironmentItem[] | null>(null);
  const [modal, setModal] = useState<null | "character" | "environment">(null);

  const load = async () => {
    const [c, e] = await Promise.all([api<CharacterItem[]>("/library/characters"), api<EnvironmentItem[]>("/library/environments")]);
    setCharacters(c);
    setEnvironments(e);
  };
  useEffect(() => {
    load().catch(() => {});
  }, []);
  useEffect(() => {
    if (params.get("tab")) setTab(params.get("tab") as string);
  }, [params]);

  return (
    <div>
      <Topbar />
      <div className="mx-auto max-w-6xl px-6 py-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight text-zinc-50">Library</h1>
            <p className="mt-1 text-sm text-zinc-500">Reusable characters, environments and brand assets across every project.</p>
          </div>
          <div className="flex gap-2">
            <Tabs
              tabs={[{ id: "characters", label: "Characters" }, { id: "environments", label: "Environments" }, { id: "assets", label: "Brand assets" }]}
              active={tab}
              onChange={setTab}
            />
          </div>
        </div>

        {tab === "characters" && (
          <>
            <div className="mb-4 flex justify-end">
              <Button onClick={() => setModal("character")}><Plus className="h-4 w-4" /> New character</Button>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {(characters || []).map((c) => (
                <Card key={c.id} className="p-5">
                  <div className="mb-3 flex items-center gap-3">
                    <div className="grid h-12 w-12 place-items-center rounded-2xl text-base font-bold text-ink-950" style={{ background: c.palette?.[0] || "#f5b301" }}>
                      {c.name.slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <div className="font-display text-sm font-semibold text-zinc-100">{c.name}</div>
                      <div className="text-xs text-zinc-500">{c.archetype}</div>
                    </div>
                    {c.is_shared ? <Users className="ml-auto h-4 w-4 text-violet-400" /> : <span className="ml-auto chip">yours</span>}
                  </div>
                  <p className="mb-3 line-clamp-2 text-xs text-zinc-500">{c.description}</p>
                  <div className="mb-2 flex flex-wrap gap-1">
                    {(c.traits || []).map((t) => <span key={t} className="chip">{t}</span>)}
                  </div>
                  <div className="flex items-center justify-between text-xs text-zinc-500">
                    <span>🎙 {c.voice?.style}</span>
                    <div className="flex items-center gap-1.5">
                      {(c.palette || []).slice(0, 3).map((p) => (
                        <span key={p} className="h-3.5 w-3.5 rounded-full border border-white/15" style={{ background: p }} />
                      ))}
                    </div>
                  </div>
                </Card>
              ))}
              {characters && characters.length === 0 && <div className="col-span-full text-center text-sm text-zinc-600 py-12">No characters yet.</div>}
            </div>
          </>
        )}

        {tab === "environments" && (
          <>
            <div className="mb-4 flex justify-end">
              <Button onClick={() => setModal("environment")}><Plus className="h-4 w-4" /> New environment</Button>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {(environments || []).map((e) => (
                <Card key={e.id} className="overflow-hidden">
                  <div className="relative h-28" style={{ background: `linear-gradient(135deg, ${e.palette?.[1] || "#222"}, ${e.palette?.[0] || "#333"})` }}>
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_25%,rgba(255,255,255,0.18),transparent_55%)]" />
                    <div className="absolute bottom-3 left-4">
                      <div className="text-sm font-semibold text-white drop-shadow">{e.name}</div>
                      <div className="text-[11px] text-white/70">{e.category.replace(/_/g, " ")}</div>
                    </div>
                    {e.is_shared ? <Globe className="absolute right-3 top-3 h-4 w-4 text-white/70" /> : null}
                  </div>
                  <div className="space-y-2 p-4 text-xs">
                    <p className="line-clamp-2 text-zinc-500">{e.description}</p>
                    <div className="flex flex-wrap gap-1">
                      {(e.weather || []).map((w) => <span key={w} className="chip">☁️ {w}</span>)}
                    </div>
                  </div>
                </Card>
              ))}
              {environments && environments.length === 0 && <div className="col-span-full text-center text-sm text-zinc-600 py-12">No environments yet.</div>}
            </div>
          </>
        )}

        {tab === "assets" && <AssetsTab />}
      </div>

      <CharacterModal open={modal === "character"} onClose={() => setModal(null)} onSaved={load} />
      <EnvironmentModal open={modal === "environment"} onClose={() => setModal(null)} onSaved={load} />
    </div>
  );
}

/* ----------------------------------------------------------------- assets */
const ASSETS = [
  { kind: "logo", name: "CineForge mark", meta: { type: "svg", colors: 2 } },
  { kind: "font", name: "Sora / Inter pair", meta: { weights: "400–800" } },
  { kind: "music", name: "Cinematic bed 01", meta: { bpm: 84, genre: "orchestral" } },
  { kind: "watermark", name: "Studio watermark", meta: { opacity: 18 } },
];

function AssetsTab() {
  const [assets, setAssets] = useState<any[] | null>(null);
  useEffect(() => {
    api("/library/assets").then(setAssets).catch(() => setAssets(ASSETS));
  }, []);
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {(assets || ASSETS).map((a, i) => (
        <Card key={i} className="p-5">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-xl">{a.kind === "logo" ? "🔤" : a.kind === "font" ? "🅰️" : a.kind === "music" ? "🎼" : "💧"}</span>
            <div>
              <div className="text-sm font-semibold text-zinc-100">{a.name}</div>
              <div className="text-[11px] text-zinc-600">{a.kind}</div>
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(a.meta || {}).map(([k, v]) => (
              <span key={k} className="chip">{k}: {String(v)}</span>
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
}

/* ----------------------------------------------------------------- modals */
function CharacterModal({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState("");
  const [archetype, setArchetype] = useState("host");
  const [desc, setDesc] = useState("");
  const save = async () => {
    await api("/library/characters", { method: "POST", body: { name, archetype, description: desc, traits: ["custom"], expressions: [], wardrobe: [], palette: ["#f5b301", "#222", "#fff"], voice: { pitch: "medium", rate: "medium", style: "conversational" } } });
    setName(""); setDesc(""); onSaved(); onClose();
  };
  return (
    <Modal open={open} onClose={onClose} title="New character">
      <div className="space-y-4">
        <div><label className="label mb-1.5 block">Name</label><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Maya Santos" /></div>
        <div>
          <label className="label mb-1.5 block">Archetype</label>
          <Select options={[{ id: "host", label: "Host" }, { id: "documentary_narrator", label: "Documentary Narrator" }, { id: "expert", label: "Expert" }, { id: "storyteller", label: "Storyteller" }, { id: "reviewer", label: "Reviewer" }]} value={archetype} onChange={setArchetype} />
        </div>
        <div><label className="label mb-1.5 block">Description</label><Textarea value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Role, personality, look…" /></div>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={save} disabled={!name.trim()}>Create</Button></div>
      </div>
    </Modal>
  );
}

function EnvironmentModal({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("nature");
  const [desc, setDesc] = useState("");
  const save = async () => {
    await api("/library/environments", { method: "POST", body: { name, category, description: desc, lighting: { key: "ambient", contrast: "medium" }, weather: ["clear"], palette: ["#222", "#444"] } });
    setName(""); setDesc(""); onSaved(); onClose();
  };
  return (
    <Modal open={open} onClose={onClose} title="New environment">
      <div className="space-y-4">
        <div><label className="label mb-1.5 block">Name</label><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Taal Volcano — Misty Dawn" /></div>
        <div>
          <label className="label mb-1.5 block">Category</label>
          <Select options={[{ id: "nature", label: "Nature" }, { id: "urban", label: "Urban" }, { id: "interior", label: "Interior" }, { id: "philippine_landmark", label: "Philippine landmark" }, { id: "historical", label: "Historical" }, { id: "scifi", label: "Sci-fi" }, { id: "studio", label: "Studio" }]} value={category} onChange={setCategory} />
        </div>
        <div><label className="label mb-1.5 block">Description</label><Textarea value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Location, atmosphere, key features…" /></div>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={save} disabled={!name.trim()}>Create</Button></div>
      </div>
    </Modal>
  );
}

export default function LibraryPage() {
  return (
    <Suspense fallback={null}>
      <LibraryInner />
    </Suspense>
  );
}
