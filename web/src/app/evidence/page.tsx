"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { EvidenceRequestItem } from "@/lib/types";
import { CheckCircle2, FileUp, FolderOpen, RefreshCw } from "lucide-react";

const STATUS_STYLE: Record<string, string> = {
  OPEN: "bg-amber-500/15 text-amber-300",
  OVERDUE: "bg-rose-500/15 text-rose-300",
  RECEIVED: "bg-emerald-500/15 text-emerald-300",
  WAIVED: "bg-slate-700 text-slate-300",
};

export default function EvidencePage() {
  const { user } = useAuth();
  const isClient = !!user && ["sales", "warehouse", "accounts", "client_admin"].includes(user.role);
  const [items, setItems] = useState<EvidenceRequestItem[]>([]);
  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    api
      .getEvidenceRequests(status || undefined)
      .then((r) => {
        setItems(r);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [status]);

  const upload = async (req: EvidenceRequestItem, file: File) => {
    setBusy(req.id);
    setNote(null);
    try {
      await api.submitEvidence(req.id, file);
      setNote(`${file.name} received for ${req.sample_ref} (${req.doc_kind}). The server stored it byte-for-byte with its SHA-256.`);
      load();
    } catch (e: unknown) {
      setNote(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(null);
    }
  };

  const counts = items.reduce<Record<string, number>>((m, r) => ({ ...m, [r.status]: (m[r.status] || 0) + 1 }), {});

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <FolderOpen className="h-5 w-5 text-indigo-400" />
            {isClient ? "Evidence requests from your auditor" : "Evidence & PBC requests"}
          </h1>
          <p className="text-xs text-slate-400 mt-1 max-w-3xl">
            {isClient
              ? "Upload the requested document for each item. Files are stored exactly as sent and fingerprinted (SHA-256) by the server; a later change to the underlying records is detected automatically."
              : "Requests sent to the client for the selected samples. The client sees only the sample reference and document type, never why it was selected."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="text-xs bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-slate-200"
          >
            <option value="">All statuses</option>
            {["OPEN", "OVERDUE", "RECEIVED", "WAIVED"].map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <button onClick={load} className="p-1.5 rounded bg-slate-800 border border-slate-700 text-slate-300">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      <div className="flex gap-2 text-xs font-mono">
        {Object.entries(counts).map(([k, v]) => (
          <span key={k} className={`px-2 py-0.5 rounded ${STATUS_STYLE[k] || "bg-slate-800 text-slate-300"}`}>
            {k} {v}
          </span>
        ))}
      </div>

      {note && <div className="p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-xs text-indigo-200">{note}</div>}
      {error && <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300">{error}</div>}

      <div className="glass-panel rounded-xl border border-slate-800 overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-slate-900/80 text-slate-400 text-xs">
            <tr>
              <th className="text-left p-2.5">Sample</th>
              <th className="text-left p-2.5">Document</th>
              <th className="text-left p-2.5">For</th>
              <th className="text-left p-2.5">Due</th>
              <th className="text-left p-2.5">Status</th>
              <th className="text-left p-2.5">Files received</th>
              {isClient && <th className="text-left p-2.5">Upload</th>}
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id} className="border-t border-slate-800/80 align-top">
                <td className="p-2.5 font-mono text-slate-200">{r.sample_ref}</td>
                <td className="p-2.5 text-slate-300">{r.doc_kind.replace("_", " ")}</td>
                <td className="p-2.5 font-mono text-slate-400">{r.about_doc_no || "—"}</td>
                <td className="p-2.5 font-mono text-slate-400">{r.due_on}</td>
                <td className="p-2.5">
                  <span className={`px-1.5 py-0.5 rounded text-[11px] font-mono ${STATUS_STYLE[r.status] || ""}`}>{r.status}</span>
                </td>
                <td className="p-2.5 space-y-1">
                  {r.submissions.length === 0 && <span className="text-slate-600">—</span>}
                  {r.submissions.map((s) => (
                    <div key={s.id} className="flex items-center gap-1.5 text-xs">
                      <CheckCircle2 className="h-3 w-3 text-emerald-400 shrink-0" />
                      <span className="text-slate-300 truncate max-w-[12rem]" title={s.filename}>
                        {s.filename}
                      </span>
                      <span className="font-mono text-slate-500" title={s.sha256}>
                        {s.sha256.slice(0, 10)}…
                      </span>
                    </div>
                  ))}
                </td>
                {isClient && (
                  <td className="p-2.5">
                    <label className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white text-xs cursor-pointer">
                      <FileUp className="h-3 w-3" />
                      {busy === r.id ? "Uploading…" : "Choose file"}
                      <input
                        type="file"
                        className="hidden"
                        disabled={busy === r.id}
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          if (f) upload(r, f);
                          e.target.value = "";
                        }}
                      />
                    </label>
                  </td>
                )}
              </tr>
            ))}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={7} className="p-6 text-center text-slate-500">
                  No evidence requests yet. They appear once the auditor selects samples.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
