"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { EvidenceRequestItem } from "@/lib/types";
import { AlertOctagon, CheckCircle2, FileUp, RefreshCw } from "lucide-react";

const STATUS_COLOR: Record<string, string> = {
  OPEN: "text-amber-300",
  OVERDUE: "text-rose-300",
  RECEIVED: "text-indigo-400",
  WAIVED: "text-slate-500",
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
      .catch((e) => setError(e.message || "Failed to load requests"))
      .finally(() => setLoading(false));
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [status]);

  const upload = async (req: EvidenceRequestItem, file: File) => {
    setBusy(req.id);
    setNote(null);
    try {
      await api.submitEvidence(req.id, file);
      setNote(`${file.name} received for ${req.sample_ref}.`);
      load();
    } catch (e: unknown) {
      setNote(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(null);
    }
  };

  const count = (s: string) => items.filter((r) => r.status === s).length;
  const stats = [
    { label: "Requests", value: items.length },
    { label: "Open", value: count("OPEN") },
    { label: "Overdue", value: count("OVERDUE") },
    { label: "Received", value: count("RECEIVED") },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-medium text-slate-50 tracking-tight">{isClient ? "Evidence requests" : "Evidence"}</h1>
        <div className="flex items-center gap-2">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="h-8 text-xs bg-slate-900 border border-slate-700 rounded-md px-2 text-slate-200"
          >
            <option value="">All statuses</option>
            {["OPEN", "OVERDUE", "RECEIVED", "WAIVED"].map((s) => (
              <option key={s} value={s}>
                {s.charAt(0) + s.slice(1).toLowerCase()}
              </option>
            ))}
          </select>
          <button
            onClick={load}
            disabled={loading}
            className="h-8 px-3 rounded-md text-slate-300 text-xs border border-slate-700 hover:bg-slate-800 flex items-center gap-1.5 transition"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-md border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <AlertOctagon className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {note && <div className="p-3 rounded-md border border-slate-700 text-slate-300 text-xs">{note}</div>}

      <div className="grid grid-cols-2 lg:grid-cols-4 rounded-lg border border-slate-800 bg-slate-900 divide-x divide-slate-800">
        {stats.map((st) => (
          <div key={st.label} className="p-5">
            <div className="text-xs text-slate-500">{st.label}</div>
            <div className="mt-2 text-2xl font-medium text-slate-50 tabular-nums">{st.value}</div>
          </div>
        ))}
      </div>

      <section className="rounded-lg border border-slate-800 bg-slate-900 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-slate-500 border-b border-slate-800">
              <th className="text-left font-normal pl-5 py-3">Ref</th>
              <th className="text-left font-normal py-3">Document</th>
              <th className="text-left font-normal py-3">For</th>
              <th className="text-left font-normal py-3">Due</th>
              <th className="text-left font-normal py-3">Status</th>
              <th className="text-left font-normal py-3">Files</th>
              {isClient && <th className="pr-5 py-3"></th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {items.map((r) => (
              <tr key={r.id} className="align-top hover:bg-slate-800/40">
                <td className="pl-5 py-3 font-mono text-xs text-slate-300">{r.sample_ref}</td>
                <td className="py-3 text-slate-200">{r.doc_kind.replace("_", " ").toLowerCase()}</td>
                <td className="py-3 font-mono text-xs text-slate-400">{r.about_doc_no || "—"}</td>
                <td className="py-3 text-xs text-slate-400 tabular-nums">{r.due_on}</td>
                <td className={`py-3 text-xs ${STATUS_COLOR[r.status] || "text-slate-400"}`}>
                  {r.status.charAt(0) + r.status.slice(1).toLowerCase()}
                </td>
                <td className="py-3 space-y-1">
                  {r.submissions.length === 0 && <span className="text-slate-600 text-xs">—</span>}
                  {r.submissions.map((s) => (
                    <div key={s.id} className="flex items-center gap-1.5 text-xs">
                      <CheckCircle2 className="h-3 w-3 text-indigo-400 shrink-0" />
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
                  <td className="pr-5 py-3 text-right">
                    <label className="inline-flex h-7 items-center gap-1.5 px-2.5 rounded-md bg-indigo-600 hover:bg-indigo-700 text-white text-xs cursor-pointer">
                      <FileUp className="h-3 w-3" />
                      {busy === r.id ? "Uploading…" : "Upload"}
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
                <td colSpan={7} className="px-5 py-10 text-center text-xs text-slate-500">
                  No evidence requests yet. They appear once samples are selected.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
