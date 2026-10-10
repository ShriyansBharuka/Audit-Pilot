"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { TrailResponse, TrailRow } from "@/lib/types";
import { AlertOctagon, RefreshCw } from "lucide-react";

const PAGE = 50;

const OUTCOME_COLOR: Record<string, string> = { OK: "text-slate-300", DENIED: "text-amber-300", ERROR: "text-rose-300" };

/** A short, plain summary of the call's arguments (values are already redacted server-side). */
function argsSummary(args: Record<string, unknown>) {
  const parts = Object.entries(args || {})
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .slice(0, 3)
    .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`);
  const s = parts.join(" · ");
  return s.length > 80 ? s.slice(0, 79) + "…" : s;
}

export default function TrailPage() {
  const [data, setData] = useState<TrailResponse | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = (off = offset) => {
    setLoading(true);
    api
      .getAuditTrail(PAGE, off)
      .then((r) => {
        setData(r);
        setError(null);
      })
      .catch((e) => setError(e.message || "Failed to load the audit trail"))
      .finally(() => setLoading(false));
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => load(offset), [offset]);

  const v = data?.verification;
  const stats = [
    { label: "Entries", value: data ? data.total.toLocaleString("en-IN") : "—", sub: "every MCP call and web decision" },
    {
      label: "Chain",
      value: !v ? "—" : v.valid ? "Intact" : "Broken",
      sub: !v ? "" : v.valid ? "hashes and links verified" : `first bad row #${v.broken_at_seq ?? v.anchor_mismatch_at}`,
    },
    { label: "Head", value: v ? `#${v.head_seq}` : "—", sub: v ? `${v.head_hash.slice(0, 16)}…` : "" },
    { label: "Anchors", value: v ? String(v.anchors) : "—", sub: "checkpoints held by the auditor" },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-medium text-slate-50 tracking-tight">Audit trail</h1>
        <button
          onClick={() => load(offset)}
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
            <div
              className={`mt-2 text-2xl font-medium tabular-nums ${
                st.label === "Chain" && v && !v.valid ? "text-rose-300" : "text-slate-50"
              }`}
            >
              {st.value}
            </div>
            <div className="mt-1 text-xs text-slate-500 truncate font-mono">{st.sub}</div>
          </div>
        ))}
      </div>

      <section className="rounded-lg border border-slate-800 bg-slate-900 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-slate-500 border-b border-slate-800">
              <th className="text-left font-normal pl-5 py-3">#</th>
              <th className="text-left font-normal py-3">Time</th>
              <th className="text-left font-normal py-3">Who</th>
              <th className="text-left font-normal py-3">Tool</th>
              <th className="text-left font-normal py-3 hidden xl:table-cell">Arguments</th>
              <th className="text-left font-normal py-3">Via</th>
              <th className="text-left font-normal py-3">Outcome</th>
              <th className="text-left font-normal pr-5 py-3 hidden md:table-cell">Hash</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {(data?.items || []).map((r: TrailRow) => (
              <tr key={r.seq} className="hover:bg-slate-800/40 align-top">
                <td className="pl-5 py-2.5 text-xs text-slate-500 tabular-nums">{r.seq}</td>
                <td className="py-2.5 text-xs text-slate-400 tabular-nums whitespace-nowrap">{r.at.replace("T", " ").slice(0, 19)}</td>
                <td className="py-2.5">
                  <div className="text-slate-200 text-xs">{r.principal}</div>
                  <div className="text-[11px] text-slate-500">{r.role.replace("_", " ")}</div>
                </td>
                <td className="py-2.5 font-mono text-xs text-slate-200">{r.tool}</td>
                <td className="py-2.5 text-xs text-slate-500 font-mono hidden xl:table-cell max-w-[22rem] truncate" title={JSON.stringify(r.args)}>
                  {argsSummary(r.args) || "—"}
                </td>
                <td className="py-2.5 text-xs text-slate-400">{r.transport.toLowerCase()}</td>
                <td className={`py-2.5 text-xs ${OUTCOME_COLOR[r.outcome] || "text-slate-400"}`}>
                  {r.outcome.charAt(0) + r.outcome.slice(1).toLowerCase()}
                </td>
                <td className="pr-5 py-2.5 text-xs text-slate-500 font-mono hidden md:table-cell" title={r.hash}>
                  {r.hash.slice(0, 12)}…
                </td>
              </tr>
            ))}
            {!loading && data && data.items.length === 0 && (
              <tr>
                <td colSpan={8} className="px-5 py-10 text-center text-xs text-slate-500">
                  No entries yet. Every MCP tool call and every web decision is recorded here.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {data && data.total > PAGE && (
          <div className="flex items-center justify-between px-5 h-11 border-t border-slate-800 text-xs text-slate-500">
            <span className="tabular-nums">
              {offset + 1}–{Math.min(offset + PAGE, data.total)} of {data.total.toLocaleString("en-IN")}
            </span>
            <div className="flex gap-2">
              <button
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE))}
                className="h-7 px-2.5 rounded-md border border-slate-700 text-slate-300 hover:bg-slate-800 disabled:opacity-40"
              >
                Newer
              </button>
              <button
                disabled={offset + PAGE >= data.total}
                onClick={() => setOffset(offset + PAGE)}
                className="h-7 px-2.5 rounded-md border border-slate-700 text-slate-300 hover:bg-slate-800 disabled:opacity-40"
              >
                Older
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
