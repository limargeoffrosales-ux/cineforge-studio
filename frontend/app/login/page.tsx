"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { Clapperboard, Loader2 } from "lucide-react";
import { api, setToken } from "@/lib/api";
import { useAuth } from "@/lib/store";

function AuthInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [tab, setTab] = useState<"login" | "register">(params.get("tab") === "register" ? "register" : "login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [seedInfo, setSeedInfo] = useState<{ email?: string; password?: string; demo_available?: boolean }>({});
  const setUser = useAuth((s) => s.setUser);

  useEffect(() => {
    api("/auth/seed-info").then(setSeedInfo).catch(() => {});
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await api("/auth/" + (tab === "login" ? "login" : "register"), {
        method: "POST",
        body:
          tab === "login"
            ? { email, password }
            : { email, password, name: name || email.split("@")[0] },
      });
      setToken(res.access_token);
      setUser(res.user);
      router.push("/app");
    } catch (err: any) {
      setError(err.message || "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  const fillDemo = () => {
    setTab("login");
    setEmail(seedInfo.email || "demo@cineforge.ai");
    setPassword(seedInfo.password || "cineforge123");
  };

  return (
    <main className="grid-noise relative grid min-h-screen place-items-center overflow-hidden px-4">
      <div className="pointer-events-none absolute -top-32 left-1/2 h-[420px] w-[820px] -translate-x-1/2 rounded-full bg-gold-400/10 blur-[130px]" />
      <div className="relative z-10 grid w-full max-w-4xl gap-10 md:grid-cols-2 md:items-center">
        <div className="hidden md:block">
          <div className="mb-6 flex items-center gap-2.5">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-gold-400 to-amber-600 shadow-[0_0_28px_-4px_rgba(245,179,1,0.7)]">
              <Clapperboard className="h-5 w-5 text-ink-950" />
            </div>
            <div className="font-display text-xl font-bold text-zinc-100">
              CineForge <span className="text-gradient-gold">AI Studio</span>
            </div>
          </div>
          <h1 className="font-display text-4xl font-bold leading-tight text-zinc-50">
            The production pipeline for the AI era.
          </h1>
          <p className="mt-4 max-w-sm text-zinc-500">
            One studio that researches, writes, storyboards, directs, renders, edits and publishes cinematic video.
          </p>
          <div className="mt-8 space-y-2 text-sm text-zinc-400">
            {["18-stage autonomous pipeline", "Character & environment consistency", "Cinematography-level shot control", "SEO, thumbnails & publishing"].map((f) => (
              <div key={f} className="flex items-center gap-2.5">
                <span className="h-1.5 w-1.5 rounded-full bg-gold-400" /> {f}
              </div>
            ))}
          </div>
        </div>

        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
          <div className="card bg-ink-900/90 p-7 shadow-2xl">
            <div className="mb-6 flex rounded-xl border border-white/8 bg-ink-850 p-1">
              {(["login", "register"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`flex-1 rounded-lg py-2 text-sm font-semibold capitalize transition ${
                    tab === t ? "bg-white/10 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"
                  }`}
                >
                  {t === "login" ? "Sign in" : "Create account"}
                </button>
              ))}
            </div>

            <form onSubmit={submit} className="space-y-4">
              {tab === "register" && (
                <div>
                  <label className="label mb-1.5 block">Name</label>
                  <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Alex Rivera" required />
                </div>
              )}
              <div>
                <label className="label mb-1.5 block">Email</label>
                <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@studio.com" required />
              </div>
              <div>
                <label className="label mb-1.5 block">Password</label>
                <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required minLength={8} />
              </div>
              {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">{error}</div>}
              <button type="submit" disabled={busy} className="btn-primary w-full !py-3">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : tab === "login" ? "Enter the studio" : "Create my studio"}
              </button>
            </form>

            {seedInfo.demo_available && tab === "login" && (
              <button onClick={fillDemo} className="mt-4 w-full rounded-xl border border-dashed border-gold-400/30 bg-gold-400/5 px-3.5 py-3 text-xs text-zinc-400 transition hover:bg-gold-400/10">
                <span className="font-semibold text-gold-400">Try the demo:</span> {seedInfo.email} · {seedInfo.password}
              </button>
            )}
            <div className="mt-5 text-center text-xs text-zinc-600">
              <Link href="/" className="hover:text-zinc-400">
                ← Back to home
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    </main>
  );
}

export default function AuthPage() {
  return (
    <Suspense>
      <AuthInner />
    </Suspense>
  );
}
