import Link from "next/link";
import { Clapperboard, ArrowRight, Film, Sparkles, GitBranch, ShieldCheck, Gauge, Layers } from "lucide-react";

const FEATURES = [
  { icon: <GitBranch className="h-4 w-4" />, title: "18-Stage AI Pipeline", body: "Idea → Research → Script → Storyboard → Shot Planning → Render → Edit → Publish. Orchestrated end-to-end." },
  { icon: <Film className="h-4 w-4" />, title: "Cinematography Engine", body: "Camera types, lenses, movements and shot types for every scene — real filmmaking controls." },
  { icon: <Sparkles className="h-4 w-4" />, title: "Character & Environment Studio", body: "Consistent digital actors and reusable cinematic locations with lighting, weather and time presets." },
  { icon: <Layers className="h-4 w-4" />, title: "Post-Production Suite", body: "Auto-editing, motion graphics, subtitles, CTR-optimized thumbnails and full SEO metadata." },
  { icon: <Gauge className="h-4 w-4" />, title: "Render Queue & Analytics", body: "Distributed render jobs, live progress, audience retention, CTR and revenue estimates." },
  { icon: <ShieldCheck className="h-4 w-4" />, title: "Enterprise-Grade", body: "JWT auth, RBAC, audit logs, rate limiting, teams, billing — designed to scale horizontally." },
];

export default function LandingPage() {
  return (
    <main className="grid-noise relative min-h-screen overflow-hidden">
      {/* backdrop */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-40 left-1/2 h-[480px] w-[900px] -translate-x-1/2 rounded-full bg-gold-400/10 blur-[140px]" />
        <div className="absolute bottom-0 right-0 h-[380px] w-[600px] rounded-full bg-violet-600/10 blur-[140px]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,transparent_40%,#08080b_100%)]" />
      </div>

      <nav className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2.5">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-gold-400 to-amber-600 shadow-[0_0_28px_-4px_rgba(245,179,1,0.7)]">
            <Clapperboard className="h-5 w-5 text-ink-950" />
          </div>
          <div className="font-display text-lg font-bold tracking-tight text-zinc-100">
            CineForge <span className="text-gradient-gold">AI Studio</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/login" className="btn-ghost !py-2 text-sm">
            Sign in
          </Link>
          <Link href="/login?tab=register" className="btn-primary !py-2 text-sm">
            Start creating <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </nav>

      <header className="relative z-10 mx-auto max-w-4xl px-6 pb-16 pt-20 text-center">
        <div className="mx-auto mb-6 flex w-fit items-center gap-2 rounded-full border border-gold-400/25 bg-gold-400/8 px-4 py-1.5 text-xs font-medium text-gold-400">
          <Sparkles className="h-3.5 w-3.5" /> Full-stack AI production studio — pipeline v0.1
        </div>
        <h1 className="font-display text-5xl font-extrabold leading-[1.05] tracking-tight text-zinc-50 sm:text-6xl">
          Your idea in.
          <br />
          <span className="text-gradient-gold">A finished video out.</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-zinc-400">
          CineForge researches your topic, writes the script, storyboards every scene, plans the shots, generates the
          footage, voice, music and subtitles — then edits, optimizes and publishes it for you.
        </p>
        <div className="mt-9 flex items-center justify-center gap-3">
          <Link href="/login?tab=register" className="btn-primary !px-6 !py-3 text-base">
            Launch the studio <ArrowRight className="h-4 w-4" />
          </Link>
          <span className="text-xs text-zinc-600">Demo: demo@cineforge.ai · cineforge123</span>
        </div>
      </header>

      <section className="relative z-10 mx-auto grid max-w-6xl gap-4 px-6 pb-20 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f) => (
          <div key={f.title} className="card p-6 transition hover:border-white/15 hover:bg-ink-800/80">
            <div className="mb-3 grid h-9 w-9 place-items-center rounded-lg border border-gold-400/20 bg-gold-400/10 text-gold-400">
              {f.icon}
            </div>
            <h3 className="font-display text-base font-semibold text-zinc-100">{f.title}</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-zinc-500">{f.body}</p>
          </div>
        ))}
      </section>

      <footer className="relative z-10 border-t border-white/5 py-8 text-center text-xs text-zinc-600">
        CineForge AI Studio · Next.js + FastAPI · microservice-ready · mock AI mode with OpenAI-compatible provider support
      </footer>
    </main>
  );
}
