"use client";
// SVG chart components — zero dependencies, theme-aware.
import { cx } from "@/lib/utils";

export function LineChart({
  data,
  height = 160,
  color = "#f5b301",
  label,
  format = (v: number) => String(Math.round(v)),
}: {
  data: number[];
  height?: number;
  color?: string;
  label?: string;
  format?: (v: number) => string;
}) {
  const w = 600;
  const h = height;
  const pad = 6;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const span = max - min || 1;
  const pts = data.map((v, i) => {
    const x = pad + (i / Math.max(1, data.length - 1)) * (w - pad * 2);
    const y = h - pad - ((v - min) / span) * (h - pad * 2);
    return [x, y] as const;
  });
  const path = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${path} L${pts[pts.length - 1]?.[0] ?? w - pad},${h - pad} L${pts[0]?.[0] ?? pad},${h - pad} Z`;
  const last = pts[pts.length - 1];
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height }} preserveAspectRatio="none">
        <defs>
          <linearGradient id={`grad-${label || "line"}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.35" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((f) => (
          <line key={f} x1={pad} x2={w - pad} y1={h * f} y2={h * f} stroke="rgba(255,255,255,0.05)" strokeDasharray="3 4" />
        ))}
        <path d={area} fill={`url(#grad-${label || "line"})`} />
        <path d={path} fill="none" stroke={color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
        {last && <circle cx={last[0]} cy={last[1]} r="4" fill={color} />}
      </svg>
      {last && (
        <div
          className="pointer-events-none absolute -top-1 -translate-x-1/2 rounded-lg border border-white/10 bg-ink-850 px-2 py-1 text-[11px] font-semibold text-zinc-200 shadow-lg"
          style={{ left: `${(last[0] / w) * 100}%` }}
        >
          {format(data[data.length - 1])}
        </div>
      )}
    </div>
  );
}

export function BarChart({
  data,
  height = 140,
  color = "#8b5cf6",
}: {
  data: { label: string; value: number }[];
  height?: number;
  color?: string;
}) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="flex items-end gap-1.5" style={{ height }}>
      {data.map((d, i) => (
        <div key={i} className="group flex flex-1 flex-col items-center justify-end gap-1.5">
          <div className="text-[10px] font-semibold text-zinc-500 opacity-0 transition group-hover:opacity-100">
            {d.value.toLocaleString()}
          </div>
          <div
            className={cx("w-full rounded-t-md transition-all", i === data.length - 1 ? "opacity-100" : "opacity-50 group-hover:opacity-90")}
            style={{ height: `${Math.max(4, (d.value / max) * (height - 28))}px`, background: color }}
          />
        </div>
      ))}
    </div>
  );
}

export function Donut({ pct, size = 72, color = "#f5b301", label }: { pct: number; size?: number; color?: string; label?: string }) {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative inline-grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="6" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={`${(pct / 100) * c} ${c}`}
        />
      </svg>
      <div className="absolute text-center">
        <div className="text-sm font-bold text-zinc-100">{label ?? `${Math.round(pct)}%`}</div>
      </div>
    </div>
  );
}

export function MiniSpark({ data, color = "#34d399", width = 90, height = 28 }: { data: number[]; color?: string; width?: number; height?: number }) {
  const max = Math.max(...data, 1);
  const pts = data.map((v, i) => `${(i / Math.max(1, data.length - 1)) * width},${height - (v / max) * height}`).join(" ");
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
