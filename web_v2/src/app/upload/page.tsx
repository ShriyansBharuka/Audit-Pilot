"use client";

import React, { useRef, useState } from "react";
import { api } from "@/lib/api";
import { UploadResult } from "@/lib/types";
import { CheckCircle2, FileSpreadsheet, Upload } from "lucide-react";

type Kind = "sales-register" | "related-parties";
const CARDS: { kind: Kind; title: string; sub: string; accept: string }[] = [
  {
    kind: "sales-register",
    title: "Sales register",
    sub: "Your invoice-level sales register for the year (.xlsx or .csv). The auditor reconciles every row to the books.",
    accept: ".xlsx,.csv",
  },
  {
    kind: "related-parties",
    title: "Related-party list",
    sub: "Directors, KMP, relatives and their companies, with PAN and the period they were related (.csv or .xlsx).",
    accept: ".csv,.xlsx",
  },
];

function UploadCard({ kind, title, sub, accept }: (typeof CARDS)[number]) {
  const ref = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const send = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      setDone(await api.uploadClientFile(kind, file));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-5 space-y-4">
      <div>
        <h2 className="text-sm font-medium text-slate-50 flex items-center gap-2">
          <FileSpreadsheet className="h-4 w-4 text-slate-400" /> {title}
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-slate-400">{sub}</p>
      </div>
      <div
        onClick={() => ref.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const f = e.dataTransfer.files?.[0];
          if (f) setFile(f);
        }}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && ref.current?.click()}
        className="cursor-pointer rounded-md border border-dashed border-slate-700 hover:border-slate-500 px-4 py-6 text-center text-xs text-slate-400"
      >
        {file ? (
          <span className="text-slate-200">{file.name} · {(file.size / 1024).toFixed(1)} KB</span>
        ) : (
          <span>Drop a file here or click to choose</span>
        )}
        <input ref={ref} type="file" accept={accept} className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </div>
      <button
        onClick={send}
        disabled={!file || busy}
        className="h-8 px-3 rounded-md bg-indigo-600 hover:bg-indigo-700 border border-indigo-500/40 disabled:opacity-50 text-xs font-medium text-white flex items-center gap-1.5"
      >
        <Upload className="h-3.5 w-3.5" /> {busy ? "Sending…" : "Send to auditor"}
      </button>
      {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}
      {done && (
        <div className="rounded-md border border-slate-800 bg-slate-950 p-3 text-xs space-y-1">
          <div className="flex items-center gap-1.5 text-indigo-400">
            <CheckCircle2 className="h-3.5 w-3.5" /> Received{done.rows_received != null ? ` · ${done.rows_received.toLocaleString("en-IN")} rows` : ""}
          </div>
          <div className="text-slate-500">
            Stored exactly as sent. Fingerprint <span className="font-mono text-slate-400">{done.sha256.slice(0, 16)}…</span>
          </div>
        </div>
      )}
    </section>
  );
}

export default function UploadPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-medium text-slate-50 tracking-tight">Upload data</h1>
      <div className="grid gap-5 lg:grid-cols-2">
        {CARDS.map((c) => (
          <UploadCard key={c.kind} {...c} />
        ))}
      </div>
    </div>
  );
}
