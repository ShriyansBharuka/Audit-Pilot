"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { CycleItem, RiskGraphData } from "@/lib/types";
import {
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  GitFork,
  HelpCircle,
  Layers,
  Network,
  RefreshCw,
  Repeat,
  ShieldAlert,
} from "lucide-react";

export default function NetworkPage() {
  const [data, setData] = useState<RiskGraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedCycleIndex, setSelectedCycleIndex] = useState<number>(0);

  useEffect(() => {
    setLoading(true);
    api
      .getRiskGraph()
      .then((res) => setData(res))
      .catch((err) => console.warn("Error loading risk graph:", err))
      .finally(() => setLoading(false));
  }, []);

  const activeCycle: CycleItem | undefined = data?.cycles[selectedCycleIndex];

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-medium text-slate-50 tracking-tight flex items-center gap-3">
            Circular Trading
            <span className="text-sm text-slate-500 font-normal tabular-nums">{data ? `${data.cycles.length} cycles` : "…"}</span>
          </h1>
        </div>
      </div>

      {loading ? (
        <div className="py-20 text-center text-slate-400">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-indigo-400" />
          Loading…
        </div>
      ) : !data ? (
        <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
          Risk graph could not be loaded.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column (1 col): Cycles Selector */}
          <div className="panel p-5 rounded-lg border border-slate-800 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-sm font-semibold text-slate-50 flex items-center gap-2">
                <Repeat className="h-4 w-4 text-rose-400" />
                Loops
              </h2>
              <span className="text-xs font-mono text-rose-400 font-bold">{data.cycles.length} Found</span>
            </div>

            <div className="space-y-2.5">
              {data.cycles.map((c, idx) => (
                <div
                  key={idx}
                  onClick={() => setSelectedCycleIndex(idx)}
                  className={`p-3.5 rounded-lg border cursor-pointer transition ${
                    selectedCycleIndex === idx
                      ? "border-rose-500/80 bg-rose-500/10 "
                      : "border-slate-800 bg-slate-900/60 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-slate-200">Loop #{idx + 1}</span>
                    <span className="text-[11px] font-mono px-1.5 py-0.5 rounded text-rose-300">
                      {c.type}
                    </span>
                  </div>
                  <div className="text-base font-bold text-rose-400 font-mono mt-1">{c.amount_formatted}</div>
                  <div className="text-xs text-slate-400 mt-1 flex items-center justify-between">
                    <span>{c.nodes.length} Entities</span>
                    <span>{c.span_days} days turnover</span>
                  </div>
                </div>
              ))}
            </div>

          </div>

          {/* Right Column (2 cols): Interactive Loop Inspector & Visual Breakdown */}
          <div className="lg:col-span-2 panel p-5 rounded-lg border border-slate-800 space-y-5">
            {activeCycle && (
              <>
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-50 flex items-center gap-2">
                      <span>Loop #{selectedCycleIndex + 1}</span>
                      <span className="text-xs font-mono text-rose-400">({activeCycle.amount_formatted})</span>
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {activeCycle.nodes.length} parties
                    </p>
                  </div>
                  <Link
                    href={`/transactions?detector=D10`}
                    className="text-xs px-2.5 py-1.5 rounded bg-indigo-600/20 border border-indigo-500/40 text-indigo-300 hover:bg-indigo-600/30 flex items-center gap-1 transition"
                  >
                    <span>View D10 Invoices</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>

                <CycleRing
                  nodes={activeCycle.nodes}
                  names={Object.fromEntries(data.graph.nodes.map((n) => [n.id, n.name]))}
                  amount={activeCycle.amount_formatted}
                />

                {/* Associated Invoices in this Loop */}
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-slate-50 ">
                    Invoices ({activeCycle.invoices.length})
                  </h4>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {activeCycle.invoices.map((invNo, i) => (
                      <Link
                        key={i}
                        href={`/transactions?search=${encodeURIComponent(invNo)}`}
                        className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 hover:border-slate-700 flex items-center justify-between text-xs transition"
                      >
                        <span className="font-mono text-indigo-300 font-medium">{invNo}</span>
                        <ArrowRight className="h-3 w-3 text-slate-500" />
                      </Link>
                    ))}
                  </div>
                </div>

                {/* Node details table */}
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-slate-50 ">
                    Parties
                  </h4>
                  <div className="border border-slate-800 rounded-lg overflow-hidden bg-slate-900/40">
                    <table className="w-full text-left text-xs text-slate-300">
                      <thead className="bg-slate-950 text-[11px] text-slate-400 uppercase font-mono">
                        <tr>
                          <th className="p-2.5">Party Identifier</th>
                          <th className="p-2.5">Entity Name</th>
                          <th className="p-2.5">Relationship</th>
                          <th className="p-2.5">State Code</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800">
                        {data.graph.nodes.filter((nd, i, all) => all.findIndex((x) => x.id === nd.id) === i).slice(0, 8).map((node) => (
                          <tr key={node.id} className="hover:bg-slate-800/30">
                            <td className="p-2.5 font-mono text-indigo-400">{node.id}</td>
                            <td className="p-2.5 font-medium text-slate-200">{node.name}</td>
                            <td className="p-2.5">
                              {node.is_rp ? (
                                <span className="text-[11px] px-1.5 py-0.5 rounded text-purple-300 font-bold">
                                  Related Party
                                </span>
                              ) : (
                                <span className="text-[11px] text-slate-400">Commercial Third-Party</span>
                              )}
                            </td>
                            <td className="p-2.5 font-mono text-slate-400">{node.state || "27"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Entities on a ring, money/goods flowing clockwise back to the start.
function CycleRing({ nodes, names, amount }: { nodes: string[]; names: Record<string, string>; amount: string }) {
  const size = 560, c = size / 2, R = 150, r = 30;
  const n = nodes.length;
  const at = (i: number, rad = R) => {
    const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
    return [c + rad * Math.cos(a), c + rad * Math.sin(a)];
  };
  const gap = Math.asin(Math.min(1, (r + 8) / R)) * 2; // keep arcs clear of the node circles
  const arc = (i: number) => {
    const a0 = -Math.PI / 2 + (2 * Math.PI * i) / n + gap;
    const a1 = -Math.PI / 2 + (2 * Math.PI * (i + 1)) / n - gap;
    const [x0, y0] = [c + R * Math.cos(a0), c + R * Math.sin(a0)];
    const [x1, y1] = [c + R * Math.cos(a1), c + R * Math.sin(a1)];
    return `M ${x0} ${y0} A ${R} ${R} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${x1} ${y1}`;
  };
  return (
    <div className="rounded-lg bg-slate-950 border border-slate-800 flex justify-center py-4">
      <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-[560px] overflow-visible" role="img" aria-label={`Circular flow across ${n} parties`}>
        <defs>
          <marker id="ring-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 z" fill="var(--color-rose-400)" />
          </marker>
        </defs>
        <circle cx={c} cy={c} r={R} fill="none" stroke="var(--color-slate-800)" strokeWidth="1" strokeDasharray="2 6" />
        {nodes.map((_, i) => (
          <path key={`e${i}`} d={arc(i)} fill="none" stroke="var(--color-rose-400)" strokeWidth="2.5" strokeLinecap="round"
            markerEnd="url(#ring-arrow)" className="ring-flow" />
        ))}
        <text x={c} y={c - 4} textAnchor="middle" className="fill-slate-50" fontSize="22" fontWeight="600" fontFamily="var(--font-mono)">{amount}</text>
        <text x={c} y={c + 20} textAnchor="middle" className="fill-slate-500" fontSize="12">round trip</text>
        {nodes.map((id, i) => {
          const [x, y] = at(i);
          const self = id === "SELF";
          const label = (names[id] || id).replace(/ (Pvt|Private) Ltd\.?$| Ltd\.?$| LLP$/, "");
          const [lx, ly] = at(i, R + r + 18);
          return (
            <g key={`n${i}`}>
              <circle cx={x} cy={y} r={r} fill={self ? "var(--color-indigo-600)" : "var(--color-slate-900)"}
                stroke={self ? "var(--color-indigo-400)" : "var(--color-slate-600)"} strokeWidth="1.5" />
              <text x={x} y={y + 4} textAnchor="middle" fontSize="11" fontWeight="600" fontFamily="var(--font-mono)"
                className={self ? "fill-white" : "fill-slate-200"}>{id.length > 7 ? id.slice(0, 7) : id}</text>
              <text x={lx} y={ly + 4} textAnchor={Math.abs(lx - c) < 8 ? "middle" : lx > c ? "start" : "end"}
                fontSize="11" className="fill-slate-400">{label.length > 22 ? label.slice(0, 21) + "…" : label}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
