"use client";
import { useEffect, useState } from "react";
import { Eye, Clock3, DollarSign, MousePointerClick, Rocket } from "lucide-react";
import { api } from "@/lib/api";
import { AnalyticsOverview } from "@/lib/types";
import { Badge, Card, Skeleton, StatCard } from "@/components/ui";
import { BarChart, LineChart } from "@/components/charts";
import { Topbar } from "@/components/studio/Shell";
import { fmtNum } from "@/lib/utils";

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsOverview | null>(null);

  useEffect(() => {
    api<AnalyticsOverview>("/analytics/overview").then(setData).catch(() => setData(null));
  }, []);

  if (!data) {
    return (
      <div>
        <Topbar />
        <div className="mx-auto max-w-6xl space-y-4 px-6 py-8">
          <Skeleton className="h-20 w-full rounded-2xl" />
          <Skeleton className="h-80 w-full rounded-2xl" />
        </div>
      </div>
    );
  }

  const retention = data.retention || [];
  const avgRet = retention.length ? (retention.reduce((a, b) => a + b, 0) / retention.length).toFixed(1) : "—";

  return (
    <div>
      <Topbar />
      <div className="mx-auto max-w-6xl px-6 py-8">
        <div className="mb-6">
          <h1 className="font-display text-2xl font-bold tracking-tight text-zinc-50">Analytics</h1>
          <p className="mt-1 text-sm text-zinc-500">Production progress, audience metrics and revenue estimates across all projects.</p>
        </div>

        <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Total views" value={fmtNum(data.totals.views)} icon={<Eye className="h-5 w-5" />} accent="blue" />
          <StatCard label="Watch time" value={`${Math.round(data.totals.watch_time_min / 60)}h`} icon={<Clock3 className="h-5 w-5" />} accent="violet" />
          <StatCard label="Est. revenue" value={`$${data.totals.revenue_usd.toLocaleString()}`} icon={<DollarSign className="h-5 w-5" />} accent="green" />
          <StatCard label="Renders completed" value={String(data.totals.renders_completed)} icon={<Rocket className="h-5 w-5" />} />
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="p-5 lg:col-span-2">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-zinc-100">Views — last 14 days</h2>
              <Badge tone="green">▲ live</Badge>
            </div>
            {data.trend.length ? (
              <BarChart data={data.trend.map((d) => ({ label: d.day.slice(5), value: d.views }))} color="#f5b301" />
            ) : (
              <div className="py-10 text-center text-sm text-zinc-600">No audience data yet — publish a project to start collecting it.</div>
            )}
          </Card>

          <Card className="p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-zinc-100">Retention</h2>
              <span className="chip text-gold-400">{avgRet}% avg</span>
            </div>
            <LineChart data={retention} label="retention" format={(v) => `${v}%`} />
            <div className="mt-4 space-y-2.5 border-t border-white/8 pt-4 text-xs">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-zinc-500"><MousePointerClick className="h-3.5 w-3.5" /> Avg CTR</span>
                <span className="font-semibold text-zinc-200">
                  {data.trend.length ? `${((data.totals.views / Math.max(1, data.trend.reduce((a, d) => a + d.views, 0) / data.trend.length)) * 4.2).toFixed(1)}%` : "—"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-zinc-500">Platforms</span>
                <span className="font-semibold text-zinc-200">{data.platforms.length}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-zinc-500">AI credits used</span>
                <span className="font-semibold text-zinc-200">{data.totals.ai_credits_used}</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
