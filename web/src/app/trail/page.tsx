"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  CheckCircle2,
  Clock,
  GitCommit,
  Hash,
  Lock,
  RefreshCw,
  Shield,
  XCircle,
} from "lucide-react";

export default function TrailPage() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const loadTrail = () => {
    setLoading(true);
    api
      .getAuditTrail(50, 0)
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadTrail();
  }, []);

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-50 tracking-tight flex items-center gap-2">
            Audit Trail
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono font-normal">{total} entries</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">SHA-256 hash chain of every action.</p>
        </div>

        <button
          onClick={loadTrail}
          className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs border border-slate-700 flex items-center gap-1.5 transition"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh Trail</span>
        </button>
      </div>

      {/* Trail Table */}
      <div className="glass-panel rounded-xl border border-slate-800 overflow-hidden">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-900/80 text-[11px] text-slate-400 uppercase font-mono border-b border-slate-800">
            <tr>
              <th className="py-3 px-4">Seq #</th>
              <th className="py-3 px-4">Timestamp (IST)</th>
              <th className="py-3 px-4">Principal & Role</th>
              <th className="py-3 px-4">Tool / Action</th>
              <th className="py-3 px-4">Transport</th>
              <th className="py-3 px-4">Outcome</th>
              <th className="py-3 px-4">Chain Hash</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {loading ? (
              <tr>
                <td colSpan={7} className="py-12 text-center text-slate-400 font-sans">
                  <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2 text-indigo-400" />
                  Verifying hash chain integrity...
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-slate-400 font-sans">
                  No audit trail records found.
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.seq} className="hover:bg-slate-800/40 transition">
                  <td className="py-3 px-4 font-bold text-indigo-400">#{row.seq}</td>
                  <td className="py-3 px-4 text-slate-400 text-xs">{row.at}</td>
                  <td className="py-3 px-4">
                    <span className="text-slate-50 font-medium">{row.principal}</span>
                    <span className="text-slate-500 text-[11px] block font-sans">{row.role}</span>
                  </td>
                  <td className="py-3 px-4 font-semibold text-slate-200">{row.tool}</td>
                  <td className="py-3 px-4 text-[11px] text-slate-400">{row.transport}</td>
                  <td className="py-3 px-4">
                    <span
                      className={`text-[11px] px-2 py-0.5 rounded font-bold ${
                        row.outcome === "OK"
                          ? "bg-emerald-500/20 text-emerald-300"
                          : row.outcome === "DENIED"
                          ? "bg-amber-500/20 text-amber-300"
                          : "bg-rose-500/20 text-rose-300"
                      }`}
                    >
                      {row.outcome}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-[11px] text-slate-500">
                    <div className="flex items-center gap-1">
                      <Lock className="h-3 w-3 text-emerald-500" />
                      <span className="truncate max-w-[120px]">{row.chain_hash?.slice(0, 16)}...</span>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
