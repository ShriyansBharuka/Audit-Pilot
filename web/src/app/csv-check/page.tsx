"use client";

import React, { useRef, useState } from "react";
import { api } from "@/lib/api";
import { CsvCheckResult } from "@/lib/types";
import { AlertOctagon, FileUp, RefreshCw } from "lucide-react";

const rupees = (p?: number) =>
  p === undefined ? "—" : `${p < 0 ? "-" : ""}₹${(Math.abs(p) / 100).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const STATUS: Record<string, { label: string; color: string }> = {
  MATCHED: { label: "Matched", color: "text-slate-300" },
  AMOUNT_MISMATCH: { label: "Amount differs", color: "text-rose-300" },
  DATE_MISMATCH: { label: "Date differs", color: "text-amber-300" },
  NOT_IN_BOOKS: { label: "Not in books", color: "text-rose-300" },
  NO_KEY: { label: "No document no.", color: "text-amber-300" },
  UNPARSED_AMOUNT: { label: "Unreadable amount", color: "text-amber-300" },
};

const REASON: Record<string, string> = {
  EMPTY_FILE: "The file is empty.",
  NOT_TEXT: "The file is not a text CSV.",
  HEADER_ONLY: "Header row only, no data rows.",
  BLANK_ROWS: "Every row is blank.",
};

export default function CsvCheckPage() {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [useAi, setUseAi] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<CsvCheckResult | null>(null);

  const run = () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    api
      .verifyCsv(file, useAi)
      .then(setRes)
      .catch((e) => setError(e.message || "Check failed"))
      .finally(() => setBusy(false));
  };

  const c = res?.verification.counts || {};
  const total = Object.values(c).reduce((a, b) => a + b, 0);
  const issues = total - (c.MATCHED || 0);
  const stats = res
    ? [
        { label: "Data", value: res.profile.has_data ? "Yes" : "No", sub: res.profile.has_data ? `${res.profile.columns.length} columns` : REASON[res.profile.reason || ""] },
        { label: "Data rows", value: res.profile.data_rows.toLocaleString("en-IN"), sub: `${res.profile.blank_rows} blank` },
        { label: "Matched", value: (c.MATCHED || 0).toLocaleString("en-IN"), sub: res.verification.key_column ? `by ${res.verification.key_column}` : "no document column" },
        { label: "Issues", value: issues.toLocaleString("en-IN"), sub: res.verification.amount_column ? `amounts from ${res.verification.amount_column}` : "" },
      ]
    : [];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-medium text-slate-50 tracking-tight">CSV check</h1>
      </div>

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-5 flex flex-wrap items-center gap-3">
        <input
          ref={input}
          type="file"
          accept=".csv,text/csv,text/plain"
          className="hidden"
          onChange={(e) => {
            setFile(e.target.files?.[0] || null);
            setRes(null);
          }}
        />
        <button
          onClick={() => input.current?.click()}
          className="h-8 px-3 rounded-md text-slate-300 text-xs border border-slate-700 hover:bg-slate-800 flex items-center gap-1.5 transition"
        >
          <FileUp className="h-3.5 w-3.5" />
          {file ? "Change file" : "Choose CSV"}
        </button>
        <span className="text-xs text-slate-400 truncate max-w-[18rem]">{file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB` : "No file chosen"}</span>
        <label className="flex items-center gap-2 text-xs text-slate-400 ml-auto">
          <input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} className="accent-indigo-500" />
          AI summary
        </label>
        <button
          onClick={run}
          disabled={!file || busy}
          className="h-8 px-3 rounded-md bg-indigo-600 hover:bg-indigo-700 border border-indigo-500/40 text-white text-xs font-medium flex items-center gap-1.5 transition disabled:opacity-50"
        >
          {busy && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
          Verify
        </button>
      </section>

      {error && (
        <div className="p-3 rounded-md border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <AlertOctagon className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {res && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 rounded-lg border border-slate-800 bg-slate-900 divide-x divide-slate-800">
            {stats.map((st) => (
              <div key={st.label} className="p-5">
                <div className="text-xs text-slate-500">{st.label}</div>
                <div
                  className={`mt-2 text-2xl font-medium tabular-nums ${
                    st.label === "Data" && !res.profile.has_data ? "text-rose-300" : st.label === "Issues" && issues ? "text-amber-300" : "text-slate-50"
                  }`}
                >
                  {st.value}
                </div>
                <div className="mt-1 text-xs text-slate-500 truncate">{st.sub}</div>
              </div>
            ))}
          </div>

          <section className="rounded-lg border border-slate-800 bg-slate-900">
            <div className="flex items-center justify-between px-5 h-12 border-b border-slate-800">
              <h2 className="text-sm font-medium text-slate-50">Agent summary</h2>
              <span className="text-xs text-slate-500">
                {res.framework} · {res.path.join(" → ")} · {res.summary.by === "deterministic" ? "rule-based" : res.summary.by.replace("llm:", "")} · proposed
              </span>
            </div>
            <p className="px-5 py-4 text-sm text-slate-200 whitespace-pre-line">{res.summary.text}</p>
            {res.summary.llm && <p className="px-5 pb-4 text-xs text-slate-500">AI summary {res.summary.llm}.</p>}
          </section>

          {res.verification.rows.length > 0 && (
            <section className="rounded-lg border border-slate-800 bg-slate-900 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-slate-500 border-b border-slate-800">
                    <th className="text-left font-normal pl-5 py-3">Row</th>
                    <th className="text-left font-normal py-3">In file</th>
                    <th className="text-left font-normal py-3">Result</th>
                    <th className="text-left font-normal py-3">In books</th>
                    <th className="text-right font-normal pr-5 py-3">Difference</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {res.verification.rows.map((r) => (
                    <tr key={r.row} className="hover:bg-slate-800/40">
                      <td className="pl-5 py-2.5 text-xs text-slate-500 tabular-nums">{r.row}</td>
                      <td className="py-2.5 text-xs text-slate-300 font-mono">
                        {r.client_data.key || "—"}
                        {r.client_data.amount ? <span className="text-slate-500"> · {r.client_data.amount}</span> : null}
                      </td>
                      <td className={`py-2.5 text-xs ${STATUS[r.status]?.color || "text-slate-400"}`}>{STATUS[r.status]?.label || r.status}</td>
                      <td className="py-2.5 text-xs text-slate-400 font-mono">
                        {r.doc_id || "—"}
                        {r.books_paise !== undefined && <span className="text-slate-500"> · {rupees(r.books_paise)}</span>}
                        {r.books_date && <span className="text-slate-500"> · {r.books_date}</span>}
                      </td>
                      <td className="pr-5 py-2.5 text-right text-xs tabular-nums text-slate-300">
                        {r.difference_paise !== undefined ? rupees(r.difference_paise) : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          <div className="text-xs text-slate-500 font-mono">sha256 {res.sha256}</div>
        </>
      )}
    </div>
  );
}
