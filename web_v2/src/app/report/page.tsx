"use client";

import React, { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { StatutoryMemo } from "@/lib/types";
import { AlertOctagon, Download, FileText, RefreshCw } from "lucide-react";

const rupees = (paise: number) => `₹${(paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function ReportPage() {
  const [memo, setMemo] = useState<StatutoryMemo | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  const draft = () => {
    setBusy(true);
    setError(null);
    api
      .draftStatutoryMemo()
      .then(setMemo)
      .catch((e) => setError(e.message || "Could not draft the memo"))
      .finally(() => setBusy(false));
  };

  const download = (format: "md" | "pdf") => {
    setDownloading(format);
    api
      .downloadStatutoryMemo(format)
      .catch((e) => setError(e.message || "Download failed"))
      .finally(() => setDownloading(null));
  };

  const stats = memo
    ? [
        { label: "Status", value: "Draft", sub: "Proposed" },
        { label: "Findings", value: String(memo.finding_ids.length), sub: memo.finding_ids.slice(0, 3).join(", ") },
        { label: "AJE debits", value: rupees(memo.aje_totals.dr_paise), sub: "" },
        { label: "AJE credits", value: rupees(memo.aje_totals.cr_paise), sub: memo.aje_totals.dr_paise === memo.aje_totals.cr_paise ? "Balanced" : "Unbalanced" },
      ]
    : [];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-medium text-slate-50 tracking-tight">Audit memo</h1>
        <div className="flex items-center gap-2">
          {memo && (
            <>
              <button
                onClick={() => download("md")}
                disabled={!!downloading}
                className="h-8 px-3 rounded-md text-slate-300 text-xs border border-slate-700 hover:bg-slate-800 flex items-center gap-1.5 transition"
              >
                <Download className="h-3.5 w-3.5" />
                {downloading === "md" ? "Preparing…" : "Download .md"}
              </button>
              <button
                onClick={() => download("pdf")}
                disabled={!!downloading}
                className="h-8 px-3 rounded-md text-slate-300 text-xs border border-slate-700 hover:bg-slate-800 flex items-center gap-1.5 transition"
              >
                <Download className="h-3.5 w-3.5" />
                {downloading === "pdf" ? "Preparing…" : "Download .pdf"}
              </button>
            </>
          )}
          <button
            onClick={draft}
            disabled={busy}
            className="h-8 px-3 rounded-md bg-indigo-600 hover:bg-indigo-700 border border-indigo-500/40 text-white text-xs font-medium flex items-center gap-1.5 transition disabled:opacity-60"
          >
            {busy ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <FileText className="h-3.5 w-3.5" />}
            {memo ? "Redraft" : "Draft memo"}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-md border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <AlertOctagon className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!memo && !busy && (
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-8 text-center text-sm text-slate-400">
          Draft the statutory revenue audit memo from the current findings.
        </div>
      )}

      {memo && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 rounded-lg border border-slate-800 bg-slate-900 divide-x divide-slate-800">
            {stats.map((st) => (
              <div key={st.label} className="p-5">
                <div className="text-xs text-slate-500">{st.label}</div>
                <div className="mt-2 text-2xl font-medium text-slate-50 tabular-nums">{st.value}</div>
                <div className="mt-1 text-xs text-slate-500 truncate">{st.sub}</div>
              </div>
            ))}
          </div>

          <section className="rounded-lg border border-slate-800 bg-slate-900">
            <div className="flex items-center justify-between px-5 h-12 border-b border-slate-800">
              <h2 className="text-sm font-medium text-slate-50">Preview</h2>
              <Link href="/findings" className="text-xs text-slate-400 hover:text-slate-50 transition">
                Partner decides in Findings
              </Link>
            </div>
            {/* sandboxed: no scripts, no same-origin access; the server escapes every client string anyway */}
            <iframe title="Statutory memo preview" sandbox="" srcDoc={memo.html} className="w-full h-[75vh] rounded-b-lg bg-white" />
          </section>
        </>
      )}
    </div>
  );
}
