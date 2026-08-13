"use client";
import { motion, AnimatePresence } from "framer-motion";
import { Copy, Check, X } from "lucide-react";
import React, { useEffect, useState } from "react";
import { cx } from "@/lib/utils";

/* ------------------------------------------------ primitives ---------- */
export function Button({
  variant = "primary",
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" }) {
  return (
    <button
      className={cx(
        variant === "primary" && "btn-primary",
        variant === "ghost" && "btn-ghost",
        variant === "danger" && "btn-danger",
        className
      )}
      {...props}
    />
  );
}

export function Card({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx("card", className)} {...props}>
      {children}
    </div>
  );
}

export function Badge({
  children,
  tone = "zinc",
  className,
}: {
  children: React.ReactNode;
  tone?: "zinc" | "gold" | "green" | "red" | "violet" | "blue";
  className?: string;
}) {
  const tones: Record<string, string> = {
    zinc: "border-white/10 bg-white/5 text-zinc-300",
    gold: "border-gold-400/30 bg-gold-400/10 text-gold-400",
    green: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    red: "border-red-400/30 bg-red-400/10 text-red-300",
    violet: "border-violet-400/30 bg-violet-400/10 text-violet-300",
    blue: "border-sky-400/30 bg-sky-400/10 text-sky-300",
  };
  return <span className={cx("chip", tones[tone], className)}>{children}</span>;
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx("input", props.className)} />;
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cx("input min-h-[90px] resize-y", props.className)} />;
}

export function Select({
  options,
  value,
  onChange,
  className,
  placeholder,
}: {
  options: { id: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
  className?: string;
  placeholder?: string;
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={cx("input appearance-none", className)}>
      {placeholder ? <option value="">{placeholder}</option> : null}
      {options.map((o) => (
        <option key={o.id} value={o.id} className="bg-ink-850">
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function Progress({ value, tone = "gold", className }: { value: number; tone?: "gold" | "violet" | "green" | "red"; className?: string }) {
  const color = { gold: "bg-gold-400", violet: "bg-violet-500", green: "bg-emerald-400", red: "bg-red-500" }[tone];
  return (
    <div className={cx("h-1.5 w-full overflow-hidden rounded-full bg-white/8", className)}>
      <motion.div
        className={cx("h-full rounded-full", color)}
        initial={{ width: 0 }}
        animate={{ width: `${Math.min(100, Math.max(0, value))}%` }}
        transition={{ duration: 0.4, ease: "easeOut" }}
      />
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={cx("animate-spin", className || "h-4 w-4")} viewBox="0 0 24 24" fill="none">
      <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton", className)} />;
}

export function EmptyState({
  icon,
  title,
  body,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="grid-noise flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 px-8 py-16 text-center">
      <div className="mb-4 text-4xl opacity-70">{icon}</div>
      <h3 className="font-display text-lg font-semibold text-zinc-200">{title}</h3>
      <p className="mt-1.5 max-w-sm text-sm text-zinc-500">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function StatCard({
  label,
  value,
  delta,
  icon,
  accent = "gold",
}: {
  label: string;
  value: string;
  delta?: string;
  icon?: React.ReactNode;
  accent?: "gold" | "violet" | "green" | "blue";
}) {
  const accents = {
    gold: "text-gold-400 bg-gold-400/10 border-gold-400/20",
    violet: "text-violet-400 bg-violet-400/10 border-violet-400/20",
    green: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
    blue: "text-sky-400 bg-sky-400/10 border-sky-400/20",
  };
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <div className="label">{label}</div>
          <div className="mt-2 font-display text-2xl font-bold tracking-tight text-zinc-100">{value}</div>
          {delta && <div className="mt-1 text-xs font-medium text-emerald-400">{delta}</div>}
        </div>
        {icon && <div className={cx("grid h-10 w-10 place-items-center rounded-xl border", accents[accent])}>{icon}</div>}
      </div>
    </Card>
  );
}

export function CopyButton({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="btn-ghost !rounded-lg !px-2 !py-1 text-xs"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1400);
        } catch {
          /* noop */
        }
      }}
      title="Copy to clipboard"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
      {label ?? (copied ? "Copied" : "Copy")}
    </button>
  );
}

export function Modal({
  open,
  onClose,
  title,
  children,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onMouseDown={(e) => e.target === e.currentTarget && onClose()}
        >
          <motion.div
            className={cx("card max-h-[88vh] w-full overflow-y-auto bg-ink-900 p-6", wide ? "max-w-3xl" : "max-w-lg")}
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.18 }}
          >
            <div className="mb-5 flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold text-zinc-100">{title}</h2>
              <button onClick={onClose} className="rounded-lg p-1.5 text-zinc-500 hover:bg-white/10 hover:text-zinc-200">
                <X className="h-4 w-4" />
              </button>
            </div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: string; label: string }[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="flex w-fit flex-wrap gap-1 rounded-xl border border-white/8 bg-ink-850 p-1">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={cx(
            "rounded-lg px-3.5 py-1.5 text-sm font-medium transition",
            active === t.id ? "bg-white/10 text-zinc-100 shadow-sm" : "text-zinc-500 hover:text-zinc-300"
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded border border-white/15 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">{children}</kbd>
  );
}
