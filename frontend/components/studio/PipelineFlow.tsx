"use client";
import { motion } from "framer-motion";
import { Check, CircleDashed, Loader2, AlertTriangle } from "lucide-react";
import { StageDef, StageState } from "@/lib/types";
import { cx, STAGE_ICONS } from "@/lib/utils";

export const PHASE_COLORS: Record<string, { text: string; dot: string; bar: string }> = {
  "Pre-Production": { text: "text-sky-400", dot: "bg-sky-400", bar: "from-sky-500/30 to-sky-400" },
  Design: { text: "text-violet-400", dot: "bg-violet-400", bar: "from-violet-500/30 to-violet-400" },
  Production: { text: "text-gold-400", dot: "bg-gold-400", bar: "from-gold-500/30 to-gold-400" },
  "Post-Production": { text: "text-emerald-400", dot: "bg-emerald-400", bar: "from-emerald-500/30 to-emerald-400" },
  Distribution: { text: "text-rose-400", dot: "bg-rose-400", bar: "from-rose-500/30 to-rose-400" },
};

export function StageBadge({ state }: { state: StageState }) {
  if (state.status === "completed")
    return (
      <span className="grid h-6 w-6 place-items-center rounded-full bg-emerald-400/15 text-emerald-400">
        <Check className="h-3.5 w-3.5" />
      </span>
    );
  if (state.status === "running")
    return (
      <span className="grid h-6 w-6 place-items-center rounded-full bg-gold-400/15 text-gold-400">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      </span>
    );
  if (state.status === "failed")
    return (
      <span className="grid h-6 w-6 place-items-center rounded-full bg-red-400/15 text-red-400">
        <AlertTriangle className="h-3.5 w-3.5" />
      </span>
    );
  return (
    <span className="grid h-6 w-6 place-items-center rounded-full bg-white/5 text-zinc-600">
      <CircleDashed className="h-3.5 w-3.5" />
    </span>
  );
}

export function PipelineFlow({
  stages,
  states,
  selected,
  onSelect,
  running,
}: {
  stages: StageDef[];
  states: Record<string, StageState>;
  selected: string;
  onSelect: (id: string) => void;
  running: boolean;
}) {
  const phases = [...new Set(stages.map((s) => s.phase))];
  let counter = 0;

  return (
    <div className="space-y-6">
      {phases.map((phase) => {
        const phaseStages = stages.filter((s) => s.phase === phase);
        const colors = PHASE_COLORS[phase];
        return (
          <div key={phase}>
            <div className="mb-2.5 flex items-center gap-2">
              <span className={cx("h-1.5 w-1.5 rounded-full", colors.dot)} />
              <span className={cx("text-[11px] font-bold uppercase tracking-widest", colors.text)}>{phase}</span>
              <div className={cx("h-px flex-1 bg-gradient-to-r to-transparent", colors.bar)} />
            </div>
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {phaseStages.map((s) => {
                counter += 1;
                const state = states[s.id] || { status: "pending", progress: 0 };
                const active = selected === s.id;
                const isRunning = state.status === "running";
                return (
                  <motion.button
                    key={s.id}
                    onClick={() => onSelect(s.id)}
                    whileHover={{ y: -2 }}
                    className={cx(
                      "relative overflow-hidden rounded-2xl border p-3.5 text-left transition",
                      active
                        ? "border-gold-400/50 bg-ink-800 shadow-[0_0_28px_-8px_rgba(245,179,1,0.4)]"
                        : isRunning
                          ? "border-gold-400/30 bg-ink-850"
                          : state.status === "completed"
                            ? "border-emerald-400/15 bg-ink-900 hover:border-emerald-400/30"
                            : state.status === "failed"
                              ? "border-red-400/30 bg-ink-850"
                              : "border-white/8 bg-ink-900/60 hover:border-white/20"
                    )}
                  >
                    {isRunning && (
                      <div className="absolute inset-x-0 bottom-0 h-0.5 overflow-hidden bg-white/5">
                        <motion.div
                          className="h-full bg-gold-400"
                          animate={{ width: `${state.progress}%` }}
                          transition={{ duration: 0.5 }}
                        />
                      </div>
                    )}
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-[10px] font-bold text-zinc-600">{String(counter).padStart(2, "0")}</span>
                      <StageBadge state={state} />
                    </div>
                    <div className="text-xl">{STAGE_ICONS[s.id]}</div>
                    <div className="mt-2 text-[13px] font-semibold leading-tight text-zinc-100">{s.name}</div>
                    <div className="mt-1 line-clamp-2 text-[10.5px] leading-snug text-zinc-600">{s.desc}</div>
                    {state.status === "completed" && state.completed_at && (
                      <div className="mt-2 text-[10px] text-emerald-400/80">{state.notes}</div>
                    )}
                    {state.status === "failed" && <div className="mt-2 text-[10px] text-red-400">{state.notes}</div>}
                  </motion.button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
