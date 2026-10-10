"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { AuditOverview } from "@/lib/types";
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  Award,
  BarChart3,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileCheck,
  FileSpreadsheet,
  Layers,
  Network,
  RefreshCw,
  Shield,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";

export default function OverviewPage() {
  const [data, setData] = useState<AuditOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = () => {
    setLoading(true);
    api
      .getOverview()
      .then((res) => {
        setData(res);
        setError(null);
      })
      .catch((err) => {
        setError(err.message || "Failed to load audit overview");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  const DETECTOR_NAMES: Record<string, { title: string; standard: string; desc: string }> = {
    D0: { title: "Register vs SoR", standard: "SA 500 / SA 230", desc: "Reconciles uploaded register row-by-row against system of record" },
    D1: { title: "Related Parties", standard: "SA 550 / Ind AS 24", desc: "Undisclosed related entities, PAN/GSTIN match, common directors" },
    D2: { title: "RP Period Shift", standard: "SA 550 / s.188", desc: "Transactions during undisclosed or misstated appointment windows" },
    D3: { title: "Cut-off / Control", standard: "Ind AS 115 / SA 240", desc: "Premature or delayed revenue recognition vs logistics dispatch" },
    D4: { title: "Movement Void", standard: "CGST Rule 138", desc: "Invoices lacking valid e-way bill or physical movement proof" },
    D5: { title: "Period Concentration", standard: "SA 520 / SA 240", desc: "Unusual volume spikes in final 10 days of FY" },
    D6: { title: "Statutory Portal", standard: "CGST Rules 46/48", desc: "Missing IRN, e-way bill cancellations, GSTR-1 mismatches" },
    D7: { title: "Manual Journals", standard: "SA 240 para 32", desc: "Unusual contra entries, top-side post-closing entries" },
    D8: { title: "Evidence Reliability", standard: "SA 500 / SA 240", desc: "Client-submitted documents failing hash or date verification" },
    D9: { title: "Credit Notes", standard: "Ind AS 115 / CGST s.34", desc: "Post-period reversals without physical goods return" },
    D10: { title: "Circular Loops", standard: "Companies Act s.143(12)", desc: "Multi-party round-trip invoicing and cash flow loops" },
    D13: { title: "Sequence Breaks", standard: "CGST Rule 46(b)", desc: "Back-dated invoice insertions and broken numbering series" },
    D14: { title: "Client Data Injection", standard: "OWASP LLM01 / SA 240", desc: "Instruction injection attempts hidden in client data cells" },
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-50 tracking-tight flex items-center gap-2">
            Audit Overview
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            {data?.entity_name || "Konkan Marine Controls Ltd"} · {data?.period_start} → {data?.period_end} · {data?.framework === "IND_AS" ? "Ind AS" : data?.framework || "Ind AS"} framework
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs border border-slate-700 flex items-center gap-1.5 transition"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <AlertOctagon className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Card 1: Revenue Tested */}
        <div className="glass-card p-4 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span className="font-medium">Total Population Revenue</span>
            <FileSpreadsheet className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="text-xl font-bold text-slate-50 font-mono tracking-tight">
            {data?.revenue_formatted ?? "—"}
          </div>
          <div className="text-xs text-slate-400 mt-2 flex items-center gap-1">
            <span className="text-emerald-400 font-semibold">{(data?.invoices_count ?? 0).toLocaleString("en-IN")} invoices</span>
            <span>across {data?.customers_count ?? 0} customers</span>
          </div>
        </div>

        {/* Card 2: Exceptions & Proposed AJEs */}
        <div className="glass-card p-4 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span className="font-medium">Exceptions & AJEs</span>
            <Award className="h-4 w-4 text-amber-400" />
          </div>
          <div className="text-xl font-bold text-amber-400 font-mono tracking-tight flex items-baseline gap-2">
            <span>{data?.findings_counts?.PROPOSED ?? 0} proposed</span>
            <span className="text-xs text-slate-400 font-normal">SA 320</span>
          </div>
          <div className="text-xs text-slate-400 mt-2 flex items-center gap-1">
            <span className="text-amber-400">Materiality OM:</span>
            <span>{data?.materiality_paise ? data.materiality_formatted : "set when findings are generated"}</span>
          </div>
        </div>

        {/* Card 3: Circular Trading Loops */}
        <div className="glass-card p-4 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span className="font-medium">Circular Trading Loops</span>
            <Network className="h-4 w-4 text-rose-400" />
          </div>
          <div className="text-xl font-bold text-rose-400 font-mono tracking-tight flex items-baseline gap-2">
            <span>{data?.company_risk?.cycles_count ?? 0} flagged cycles</span>
          </div>
          <div className="text-xs text-slate-400 mt-2 flex items-center gap-1">
            <span className="text-rose-400 font-medium">₹{((data?.company_risk?.circular_paise ?? 0) / 1e9).toFixed(2)} Cr</span>
            <span>circular turnover flagged</span>
          </div>
        </div>

        {/* Card 4: Audit Readiness */}
        <div className="glass-card p-4 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span className="font-medium">Company Risk Band</span>
            <ShieldAlert className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="text-xl font-bold text-slate-50 font-mono tracking-tight flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-xs badge-high font-bold">
              {data?.company_risk?.band || "HIGH"}
            </span>
            <span className="text-xs text-slate-400 font-normal">AuditGraph</span>
          </div>
        </div>
      </div>

      {/* Main Grid: Detector Matrix & Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 cols): 15 Detectors Breakdown */}
        <div className="lg:col-span-2 glass-panel p-5 rounded-xl border border-slate-800 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-50">Detector results (D0–D14)</h2>
            </div>
            <Link
              href="/transactions"
              className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
            >
              <span>View all</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {Object.entries(DETECTOR_NAMES).map(([key, meta]) => {
              const count = data?.detector_counts?.[key] || 0;
              const hasHits = count > 0;
              return (
                <div
                  key={key}
                  className={`p-3 rounded-lg border transition ${
                    hasHits
                      ? "border-slate-800 bg-slate-900/60 hover:border-slate-700"
                      : "border-slate-800/40 bg-slate-950/40 opacity-70"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-mono font-bold px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300">
                        {key}
                      </span>
                      <span className="text-xs font-semibold text-slate-200">{meta.title}</span>
                    </div>
                    <span
                      className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                        hasHits ? "bg-amber-500/20 text-amber-300" : "bg-slate-800 text-slate-500"
                      }`}
                    >
                      {count} hits
                    </span>
                  </div>
                  <div className="text-[11px] text-indigo-400/80 font-mono mt-1">{meta.standard}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column (1 col): Quick Navigation & Partner Status */}
        <div className="space-y-4">
          {/* Partner Sign-off Card */}
          <div className="glass-panel p-5 rounded-xl border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-50 flex items-center gap-2">
                <Award className="h-4 w-4 text-indigo-400" />
                Partner sign-off
              </h3>
              <span className="text-[11px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono">
                {data?.status || "IN_PROGRESS"}
              </span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">Each finding needs a partner decision with a comment.</p>
            <div className="border-t border-slate-800 pt-3 space-y-2 text-xs">
              <div className="flex justify-between text-slate-300">
                <span>Proposed Findings:</span>
                <span className="font-mono font-bold text-amber-400">{data?.findings_counts?.PROPOSED ?? 0}</span>
              </div>
            </div>
            <Link
              href="/findings"
              className="mt-2 block text-center w-full py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs shadow-lg shadow-indigo-600/20 transition"
            >
              Open Partner Review Queue
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
