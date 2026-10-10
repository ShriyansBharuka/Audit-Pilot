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
      .catch((err) => console.error("Error loading risk graph:", err))
      .finally(() => setLoading(false));
  }, []);

  const activeCycle: CycleItem | undefined = data?.cycles[selectedCycleIndex];

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            AuditGraph & Circular Trading Explorer
            <span className="text-xs px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 font-mono font-normal">
              {data ? `${data.cycles.length} minimum-span cycles flagged` : "minimum-span cycles"}
            </span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Detects artificial revenue circularity, round-trip transactions, and related-party accommodation trading (Companies Act s.143(12)).
          </p>
        </div>
      </div>

      {loading ? (
        <div className="py-20 text-center text-slate-400">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-indigo-400" />
          Analyzing entity graph and minimum-span cycles...
        </div>
      ) : !data ? (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
          Risk graph could not be loaded.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column (1 col): Cycles Selector */}
          <div className="glass-panel p-5 rounded-xl border border-slate-800 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                <Repeat className="h-4 w-4 text-rose-400" />
                Detected Circular Loops
              </h2>
              <span className="text-xs font-mono text-rose-400 font-bold">{data.cycles.length} Found</span>
            </div>

            <div className="space-y-2.5">
              {data.cycles.map((c, idx) => (
                <div
                  key={idx}
                  onClick={() => setSelectedCycleIndex(idx)}
                  className={`p-3.5 rounded-xl border cursor-pointer transition ${
                    selectedCycleIndex === idx
                      ? "border-rose-500/80 bg-rose-500/10 shadow-lg shadow-rose-500/5"
                      : "border-slate-800 bg-slate-900/60 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-slate-200">Loop #{idx + 1}</span>
                    <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300">
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

            <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 leading-relaxed">
              <strong>Statutory Warning:</strong> Circular trading without underlying transfer of control fails Ind AS 115 para 9(d) and constitutes fictitious turnover under SA 240.
            </div>
          </div>

          {/* Right Column (2 cols): Interactive Loop Inspector & Visual Breakdown */}
          <div className="lg:col-span-2 glass-panel p-5 rounded-xl border border-slate-800 space-y-5">
            {activeCycle && (
              <>
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div>
                    <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                      <span>Inspection of Loop #{selectedCycleIndex + 1}</span>
                      <span className="text-xs font-mono text-rose-400">({activeCycle.amount_formatted})</span>
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Closed cyclic graph of invoicing and settlement across {activeCycle.nodes.length} parties
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

                {/* Flow Diagram (Horizontal step graph) */}
                <div className="p-6 rounded-xl bg-slate-950 border border-slate-800/80 space-y-4">
                  <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-2">
                    Round-Trip Flow Architecture
                  </div>
                  <div className="flex flex-wrap items-center justify-center gap-3">
                    {activeCycle.nodes.map((node, i) => (
                      <React.Fragment key={i}>
                        <div className="p-3 rounded-xl bg-slate-900 border border-slate-700 min-w-[140px] text-center shadow-lg">
                          <div className="text-[11px] text-indigo-400 font-mono">Entity #{i + 1}</div>
                          <div className="text-xs font-bold text-white mt-1">{node}</div>
                          <div className="text-[11px] text-slate-400 mt-0.5">
                            {node === "SELF" ? "Audited Entity" : "Accommodation Party"}
                          </div>
                        </div>
                        {i < activeCycle.nodes.length - 1 && (
                          <div className="flex flex-col items-center text-rose-400">
                            <span className="text-[11px] font-mono text-slate-400">Goods / Inv</span>
                            <span className="text-base font-bold">→</span>
                          </div>
                        )}
                      </React.Fragment>
                    ))}
                    {/* Closing Arrow */}
                    <div className="flex flex-col items-center text-rose-400">
                      <span className="text-[11px] font-mono text-rose-400">Return to Origin</span>
                      <span className="text-base font-bold">↻</span>
                    </div>
                  </div>
                </div>

                {/* Associated Invoices in this Loop */}
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-white uppercase tracking-wider">
                    Invoices Constituting this Loop ({activeCycle.invoices.length})
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
                  <h4 className="text-xs font-semibold text-white uppercase tracking-wider">
                    Network Node Entities in AuditGraph
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
                        {data.graph.nodes.slice(0, 8).map((node) => (
                          <tr key={node.id} className="hover:bg-slate-800/30">
                            <td className="p-2.5 font-mono text-indigo-400">{node.id}</td>
                            <td className="p-2.5 font-medium text-slate-200">{node.name}</td>
                            <td className="p-2.5">
                              {node.is_rp ? (
                                <span className="text-[11px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 font-bold">
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
