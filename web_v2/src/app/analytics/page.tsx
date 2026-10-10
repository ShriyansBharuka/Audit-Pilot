"use client";

import React, { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { ChartsData } from "@/lib/types";
import { AlertOctagon, RefreshCw } from "lucide-react";

const rupees = (paise: number) => {
  const r = paise / 100;
  if (r >= 1e7) return `₹${(r / 1e7).toFixed(2)} Cr`;
  if (r >= 1e5) return `₹${(r / 1e5).toFixed(2)} L`;
  return `₹${Math.round(r).toLocaleString("en-IN")}`;
};

function Panel({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900">
      <div className="flex items-center justify-between px-5 h-12 border-b border-slate-800">
        <h2 className="text-sm font-medium text-slate-50">{title}</h2>
        {right && <div className="text-xs text-slate-500">{right}</div>}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function VolumeChart({ v }: { v: ChartsData["volume"] }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 900, H = 240, L = 56, R = 12, T = 12, B = 24;
  const days = v.days;
  if (!days.length) return <div className="text-xs text-slate-500">No invoices in the period.</div>;
  const hi = v.mean_paise + 3 * v.stdev_paise;
  const lo = Math.max(0, v.mean_paise - 3 * v.stdev_paise);
  const yMax = Math.max(hi, ...days.map((d) => d.total_paise)) * 1.05 || 1;
  const x = (i: number) => L + (i * (W - L - R)) / Math.max(1, days.length - 1);
  const y = (p: number) => T + (H - T - B) * (1 - p / yMax);
  const path = days.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(d.total_paise).toFixed(1)}`).join(" ");
  const win = days.map((d, i) => (d.period_end_window ? i : -1)).filter((i) => i >= 0);
  const months = days
    .map((d, i) => ({ i, m: d.date.slice(0, 7) }))
    .filter((d, k, arr) => k === 0 || arr[k - 1].m !== d.m);
  const h = hover !== null ? days[hover] : null;

  return (
    <div className="space-y-3">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto"
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          const px = ((e.clientX - r.left) / r.width) * W;
          const i = Math.round(((px - L) / (W - L - R)) * (days.length - 1));
          setHover(Math.min(days.length - 1, Math.max(0, i)));
        }}
      >
        {win.length > 0 && (
          <rect x={x(win[0]) - 3} y={T} width={x(win[win.length - 1]) - x(win[0]) + 6} height={H - T - B} className="fill-amber-500/10" />
        )}
        <rect x={L} y={y(hi)} width={W - L - R} height={Math.max(0, y(lo) - y(hi))} className="fill-slate-700/25" />
        <line x1={L} x2={W - R} y1={y(v.mean_paise)} y2={y(v.mean_paise)} className="stroke-slate-600" strokeDasharray="3 3" />
        {[0, 0.5, 1].map((f) => (
          <text key={f} x={L - 6} y={y(yMax * f) + 3} textAnchor="end" className="fill-slate-500 text-[10px]">
            {rupees(yMax * f)}
          </text>
        ))}
        {months.map((m) => (
          <text key={m.m} x={x(m.i)} y={H - 6} className="fill-slate-500 text-[10px]">
            {new Date(m.m + "-01").toLocaleString("en-IN", { month: "short" })}
          </text>
        ))}
        <path d={path} fill="none" className="stroke-indigo-400" strokeWidth={1.2} />
        {days.map((d, i) =>
          d.flagged ? <circle key={d.date} cx={x(i)} cy={y(d.total_paise)} r={3.5} className="fill-rose-500" /> : null,
        )}
        {h && hover !== null && (
          <>
            <line x1={x(hover)} x2={x(hover)} y1={T} y2={H - B} className="stroke-slate-500" />
            <circle cx={x(hover)} cy={y(h.total_paise)} r={3} className="fill-slate-50" />
          </>
        )}
      </svg>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5"><span className="h-2 w-3 bg-slate-700/60 rounded-sm" /> ±3σ</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-3 bg-amber-500/30 rounded-sm" /> Period end</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-rose-500 rounded-full" /> Spike</span>
        </div>
        <div className="tabular-nums text-slate-400">
          {h ? `${h.date} · ${h.count} invoices · ${rupees(h.total_paise)} · z ${h.z.toFixed(1)}` : `Daily mean ${rupees(v.mean_paise)}`}
        </div>
      </div>
    </div>
  );
}

function BenfordChart({ b }: { b: ChartsData["benford"] }) {
  const W = 420, H = 200, L = 30, B = 22, T = 8;
  const max = Math.max(...b.digits.map((d) => Math.max(d.actual, d.expected)), 0.01) * 1.1;
  const bw = (W - L) / 9;
  const y = (p: number) => T + (H - T - B) * (1 - p / max);
  return (
    <div className="space-y-3">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
        {[0, 0.1, 0.2, 0.3].filter((t) => t <= max).map((t) => (
          <text key={t} x={L - 4} y={y(t) + 3} textAnchor="end" className="fill-slate-500 text-[10px]">
            {Math.round(t * 100)}%
          </text>
        ))}
        {b.digits.map((d, i) => {
          const x0 = L + i * bw + bw * 0.15;
          const w = bw * 0.33;
          return (
            <g key={d.digit}>
              <rect x={x0} y={y(d.actual)} width={w} height={H - B - y(d.actual)} className="fill-indigo-500" rx={1}>
                <title>{`Digit ${d.digit}: ${(d.actual * 100).toFixed(1)}% actual (${d.count})`}</title>
              </rect>
              <rect x={x0 + w + 2} y={y(d.expected)} width={w} height={H - B - y(d.expected)} className="fill-slate-600" rx={1}>
                <title>{`Digit ${d.digit}: ${(d.expected * 100).toFixed(1)}% expected`}</title>
              </rect>
              <text x={x0 + w} y={H - 6} textAnchor="middle" className="fill-slate-500 text-[10px]">
                {d.digit}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-4 text-slate-500">
          <span className="flex items-center gap-1.5"><span className="h-2 w-3 bg-indigo-500 rounded-sm" /> Actual</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-3 bg-slate-600 rounded-sm" /> Expected</span>
        </div>
        <span className={b.flagged ? "text-rose-300" : "text-slate-300"}>
          {b.flagged ? `Deviates: χ² ${b.chi2.toFixed(1)}` : "Consistent with Benford"}
        </span>
      </div>
    </div>
  );
}

function RiskHistogram({ h }: { h: ChartsData["risk"]["histogram"] }) {
  const max = Math.max(...h.map((b) => b.count), 1);
  const color = (band: string) => (band === ">=70" ? "bg-rose-500" : band === "30-69" ? "bg-amber-500" : "bg-slate-600");
  const label = (band: string) => (band === ">=70" ? "70+" : band === "30-69" ? "30–69" : "Under 30");
  return (
    <div className="space-y-3">
      {h.map((b) => (
        <div key={b.band} className="grid grid-cols-[4.5rem_minmax(0,1fr)_4rem] items-center gap-3 text-xs">
          <span className="text-slate-400">{label(b.band)}</span>
          <div className="h-2.5 bg-slate-800 rounded-sm overflow-hidden">
            <div className={`h-full ${color(b.band)}`} style={{ width: `${Math.max(0.5, (100 * b.count) / max)}%` }} />
          </div>
          <span className="text-right tabular-nums text-slate-200">{b.count.toLocaleString("en-IN")}</span>
        </div>
      ))}
    </div>
  );
}

function RiskScatter({ pts }: { pts: ChartsData["risk"]["scatter"] }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 600, H = 240, L = 34, B = 24, T = 8, R = 8;
  const vals = pts.filter((p) => p.total_paise > 0);
  const lmin = Math.log10(Math.max(100, Math.min(...vals.map((p) => p.total_paise))));
  const lmax = Math.log10(Math.max(...vals.map((p) => p.total_paise), 1000));
  const x = (paise: number) => L + ((Math.log10(Math.max(paise, 1)) - lmin) / Math.max(0.001, lmax - lmin)) * (W - L - R);
  const y = (r: number) => T + (H - T - B) * (1 - r / 100);
  const ticks = [];
  for (let e = Math.ceil(lmin); e <= Math.floor(lmax); e++) ticks.push(e);
  const h = hover !== null ? vals[hover] : null;
  return (
    <div className="space-y-3">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
        {[30, 70].map((r) => (
          <line key={r} x1={L} x2={W - R} y1={y(r)} y2={y(r)} className="stroke-slate-700" strokeDasharray="3 3" />
        ))}
        {[0, 30, 70, 100].map((r) => (
          <text key={r} x={L - 4} y={y(r) + 3} textAnchor="end" className="fill-slate-500 text-[10px]">
            {r}
          </text>
        ))}
        {ticks.map((e) => (
          <text key={e} x={x(10 ** e)} y={H - 6} textAnchor="middle" className="fill-slate-500 text-[10px]">
            {rupees(10 ** e)}
          </text>
        ))}
        {vals.map((p, i) => (
          <circle
            key={p.invoice_no}
            cx={x(p.total_paise)}
            cy={y(p.risk_score)}
            r={p.risk_score >= 70 ? 3.5 : 2}
            className={p.risk_score >= 70 ? "fill-rose-500" : p.risk_score >= 30 ? "fill-amber-400" : "fill-slate-500/50"}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
          />
        ))}
      </svg>
      <div className="text-xs text-slate-400 tabular-nums h-4">
        {h ? `${h.invoice_no} · ${rupees(h.total_paise)} · risk ${h.risk_score} · ${h.category}` : "Hover a point"}
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const [data, setData] = useState<ChartsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    api
      .getAnalyticsCharts()
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(e.message || "Failed to load charts"))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const spikes = useMemo(() => data?.volume.days.filter((d) => d.flagged).length ?? 0, [data]);
  const high = data?.risk.histogram.find((b) => b.band === ">=70")?.count ?? 0;
  const stats = [
    { label: "Invoices", value: data ? data.benford.n.toLocaleString("en-IN") : "—", sub: data ? `${data.period.start} → ${data.period.end}` : "" },
    { label: "Spike days", value: data ? String(spikes) : "—", sub: "z ≥ 3" },
    { label: "Benford", value: data ? (data.benford.flagged ? "Deviates" : "Consistent") : "—", sub: data ? `χ² ${data.benford.chi2.toFixed(1)}` : "" },
    { label: "High risk", value: data ? String(high) : "—", sub: "score 70+" },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-medium text-slate-50 tracking-tight">Analytics</h1>
        <button
          onClick={load}
          disabled={loading}
          className="h-8 px-3 rounded-md text-slate-300 text-xs border border-slate-700 hover:bg-slate-800 flex items-center gap-1.5 transition"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-md border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <AlertOctagon className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 rounded-lg border border-slate-800 bg-slate-900 divide-x divide-slate-800">
        {stats.map((st) => (
          <div key={st.label} className="p-5">
            <div className="text-xs text-slate-500">{st.label}</div>
            <div className="mt-2 text-2xl font-medium text-slate-50 tabular-nums">{st.value}</div>
            <div className="mt-1 text-xs text-slate-500">{st.sub}</div>
          </div>
        ))}
      </div>

      {data && (
        <>
          <Panel title="Daily volume" right={`${data.volume.days.length} trading days`}>
            <VolumeChart v={data.volume} />
          </Panel>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <Panel title="Benford first digit" right={`${data.benford.n.toLocaleString("en-IN")} invoices`}>
              <BenfordChart b={data.benford} />
            </Panel>
            <Panel title="Risk distribution">
              <RiskHistogram h={data.risk.histogram} />
            </Panel>
          </div>
          <Panel
            title="Amount vs risk"
            right={`${data.risk.scatter_shown.toLocaleString("en-IN")} of ${data.risk.scatter_total.toLocaleString("en-IN")} invoices`}
          >
            <RiskScatter pts={data.risk.scatter} />
          </Panel>
        </>
      )}
    </div>
  );
}
