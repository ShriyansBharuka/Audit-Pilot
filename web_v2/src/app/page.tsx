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

  const proposed = data?.findings_counts?.PROPOSED ?? 0;
  const band = data?.company_risk?.band || "—";
  const stats = [
    { label: "Revenue tested", value: data?.revenue_formatted ?? "—", sub: `${(data?.invoices_count ?? 0).toLocaleString("en-IN")} invoices · ${data?.customers_count ?? 0} customers` },
    { label: "Proposed findings", value: String(proposed), sub: data?.materiality_paise ? `Materiality ${data.materiality_formatted}` : "Materiality not set" },
    { label: "Circular loops", value: String(data?.company_risk?.cycles_count ?? 0), sub: `₹${((data?.company_risk?.circular_paise ?? 0) / 1e9).toFixed(2)} Cr turnover` },
    { label: "Company risk", value: band, sub: "AuditGraph" },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-medium text-slate-50 tracking-tight">Overview</h1>
        <button
          onClick={loadData}
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
            <div className="mt-2 text-2xl font-medium text-slate-50 tabular-nums flex items-center gap-2">
              {st.label === "Company risk" && (
                <span className={`h-2 w-2 rounded-full ${band === "HIGH" ? "bg-rose-500" : band === "REVIEW" ? "bg-amber-500" : "bg-indigo-500"}`} />
              )}
              {st.value}
            </div>
            <div className="mt-1 text-xs text-slate-500">{st.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="lg:col-span-2 rounded-lg border border-slate-800 bg-slate-900">
          <div className="flex items-center justify-between px-5 h-12 border-b border-slate-800">
            <h2 className="text-sm font-medium text-slate-50">Detectors</h2>
            <Link href="/transactions" className="text-xs text-slate-400 hover:text-slate-50 flex items-center gap-1 transition">
              View population <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-slate-800">
              {Object.entries(DETECTOR_NAMES).map(([key, meta]) => {
                const count = data?.detector_counts?.[key] || 0;
                return (
                  <tr key={key} className={count ? "hover:bg-slate-800/40" : "text-slate-500"}>
                    <td className="pl-5 py-2.5 w-14 font-mono text-xs text-slate-500">{key}</td>
                    <td className={`py-2.5 ${count ? "text-slate-200" : ""}`}>{meta.title}</td>
                    <td className="py-2.5 text-xs text-slate-500 hidden md:table-cell">{meta.standard}</td>
                    <td className={`pr-5 py-2.5 text-right tabular-nums ${count ? "text-slate-50" : ""}`}>{count}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900 p-5 space-y-4 h-fit">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-slate-50">Partner sign-off</h2>
            <span className="text-xs text-slate-500">{(data?.status || "IN_PROGRESS").replace("_", " ").toLowerCase()}</span>
          </div>
          <div>
            <div className="text-3xl font-medium text-slate-50 tabular-nums">{proposed}</div>
            <div className="text-xs text-slate-500 mt-1">findings awaiting a decision</div>
          </div>
          <Link
            href="/findings"
            className="inline-flex h-8 items-center px-3 rounded-md bg-indigo-600 hover:bg-indigo-700 border border-indigo-500/40 text-white text-xs font-medium transition"
          >
            Review findings
          </Link>
        </section>
      </div>
    </div>
  );
}
