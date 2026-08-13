"use client";
import { useEffect, useState } from "react";
import { Check, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Button, Card, Tabs } from "@/components/ui";
import { Topbar } from "@/components/studio/Shell";
import { AudioPanel, ProvidersPanel } from "@/components/studio/ProviderSettings";
import { cx } from "@/lib/utils";

const PLANS = [
  { id: "free", name: "Free", price: 0, credits: 100, renders: 5, maxRes: "720p", perks: ["1 collaborator", "Community assets", "720p exports"] },
  { id: "pro", name: "Pro", price: 29, credits: 1500, renders: 100, maxRes: "1080p", perks: ["3 collaborators", "Character locking", "SEO suite", "Priority queue"] },
  { id: "studio", name: "Studio", price: 89, credits: 6000, renders: 500, maxRes: "4K", perks: ["10 collaborators", "Voice cloning", "Brand kits", "API access"] },
  { id: "enterprise", name: "Enterprise", price: 499, credits: 50000, renders: 10000, maxRes: "8K", perks: ["Unlimited seats", "Self-hosted models", "SLA & SSO", "Dedicated render farm"] },
];

export default function SettingsPage() {
  const [tab, setTab] = useState("billing");
  const [plan, setPlan] = useState("free");
  const [limits, setLimits] = useState<any>({});
  const [usage, setUsage] = useState<any>({});
  const [upgrading, setUpgrading] = useState(false);
  const [teams, setTeams] = useState<any[]>([]);

  const load = async () => {
    try {
      const b = await api("/billing/plan");
      setPlan(b.plan);
      setLimits(b.limits || {});
      setUsage(b.usage || {});
      const t = await api("/teams");
      setTeams(t);
    } catch {
      /* noop */
    }
  };

  useEffect(() => {
    load();
  }, []);

  const upgrade = async (p: string) => {
    setUpgrading(true);
    try {
      const r = await api("/billing/upgrade", { method: "POST", body: { plan: p } });
      setPlan(r.plan);
      load();
    } finally {
      setUpgrading(false);
    }
  };

  return (
    <div>
      <Topbar />
      <div className="mx-auto max-w-6xl px-6 py-8">
        <div className="mb-6">
          <h1 className="font-display text-2xl font-bold tracking-tight text-zinc-50">Settings</h1>
          <p className="mt-1 text-sm text-zinc-500">Billing, teams, API keys and studio preferences.</p>
        </div>

        <div className="mb-6 overflow-x-auto">
          <Tabs
            tabs={[
              { id: "billing", label: "Billing" },
              { id: "team", label: "Team" },
              { id: "providers", label: "AI providers" },
              { id: "audio", label: "Audio" },
              { id: "keys", label: "API keys" },
            ]}
            active={tab}
            onChange={setTab}
          />
        </div>

        {tab === "billing" && (
          <>
            <div className="mb-6 grid gap-4 sm:grid-cols-3">
              <Card className="p-5">
                <div className="label">Current plan</div>
                <div className="mt-1.5 font-display text-xl font-bold capitalize text-gold-400">{plan}</div>
              </Card>
              <Card className="p-5">
                <div className="label">AI credits used</div>
                <div className="mt-1.5 font-display text-xl font-bold text-zinc-100">{usage.ai_credits ?? 0} / {limits.credits ?? "—"}</div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/8">
                  <div className="h-full rounded-full bg-violet-500" style={{ width: `${Math.min(100, ((usage.ai_credits ?? 0) / Math.max(1, limits.credits ?? 1)) * 100)}%` }} />
                </div>
              </Card>
              <Card className="p-5">
                <div className="label">Renders</div>
                <div className="mt-1.5 font-display text-xl font-bold text-zinc-100">{usage.renders ?? 0} / {limits.renders ?? "—"}</div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/8">
                  <div className="h-full rounded-full bg-gold-400" style={{ width: `${Math.min(100, ((usage.renders ?? 0) / Math.max(1, limits.renders ?? 1)) * 100)}%` }} />
                </div>
              </Card>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {PLANS.map((p) => {
                const current = plan === p.id;
                return (
                  <Card key={p.id} className={cx("flex flex-col p-5", current && "border-gold-400/50 shadow-[0_0_30px_-12px_rgba(245,179,1,0.5)]")}>
                    <div className="flex items-center justify-between">
                      <span className="font-display text-base font-semibold text-zinc-100">{p.name}</span>
                      {current && <Badge tone="gold">current</Badge>}
                    </div>
                    <div className="mt-2">
                      <span className="font-display text-3xl font-bold text-zinc-50">${p.price}</span>
                      <span className="text-sm text-zinc-600">/mo</span>
                    </div>
                    <div className="mt-3 space-y-1.5 text-xs text-zinc-500">
                      <div>{p.credits.toLocaleString()} AI credits</div>
                      <div>{p.renders} renders</div>
                      <div>Up to {p.maxRes}</div>
                    </div>
                    <ul className="mt-3 flex-1 space-y-1.5 text-xs text-zinc-400">
                      {p.perks.map((perk) => (
                        <li key={perk} className="flex items-center gap-1.5">
                          <Check className="h-3.5 w-3.5 text-emerald-400" /> {perk}
                        </li>
                      ))}
                    </ul>
                    <Button variant={current ? "ghost" : "primary"} className="mt-4" disabled={current} onClick={() => upgrade(p.id)}>
                      {upgrading ? "Upgrading…" : current ? "Active" : `Upgrade to ${p.name}`}
                    </Button>
                  </Card>
                );
              })}
            </div>
          </>
        )}

        {tab === "team" && (
          <div className="grid gap-4 lg:grid-cols-2">
            {teams.map((t) => (
              <Card key={t.id} className="p-5">
                <div className="mb-3 flex items-center justify-between">
                  <span className="font-display text-base font-semibold text-zinc-100">{t.name}</span>
                  <Badge tone="violet">{t.members?.length || 1} members</Badge>
                </div>
                <div className="space-y-2">
                  {(t.members || []).map((m: any, i: number) => (
                    <div key={i} className="flex items-center justify-between rounded-xl bg-ink-850 px-3 py-2.5 text-xs">
                      <span className="font-medium text-zinc-300">member {m.user_id?.slice(0, 8)}</span>
                      <span className="chip capitalize">{m.role}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-4 flex items-center gap-2">
                  <input className="input !py-2 text-xs" placeholder="collaborator@studio.com" />
                  <Button variant="ghost" className="!py-2 text-xs"><Zap className="h-3.5 w-3.5" /> Invite</Button>
                </div>
              </Card>
            ))}
            {teams.length === 0 && (
              <Button onClick={async () => { await api("/teams", { method: "POST", body: { name: "My Studio Team" } }); load(); }} className="h-fit">
                Create a team
              </Button>
            )}
          </div>
        )}

        {tab === "providers" && <ProvidersPanel />}
        {tab === "audio" && <AudioPanel />}

        {tab === "keys" && (
          <Card className="max-w-xl p-5">
            <div className="label mb-1.5">Service API key</div>
            <p className="mb-3 text-xs text-zinc-500">Use for server-to-server pipeline calls. Keys are hashed at rest and scoped per role.</p>
            <code className="block rounded-xl border border-white/10 bg-ink-850 px-4 py-3 font-mono text-xs text-zinc-400">
              cf_live_demo_service_key
            </code>
            <div className="mt-4 rounded-xl border border-violet-400/20 bg-violet-400/5 p-3.5 text-xs text-violet-300">
              Phase 2: full API-key manager with scopes, quotas, rotation and audit.
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
