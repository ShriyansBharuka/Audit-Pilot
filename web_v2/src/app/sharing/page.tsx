"use client";

import React, { useState } from "react";
import { downloadWithToken } from "@/lib/api";
import {
  Check,
  CheckCircle2,
  Clock,
  Download,
  Eye,
  FileSpreadsheet,
  FileText,
  Lock,
  Share2,
  Shield,
  Sliders,
  UserCheck,
  Users,
} from "lucide-react";

export default function SharingPage() {
  const [reports, setReports] = useState([
    {
      id: "rep-01",
      title: "Statutory Revenue 4-Sheet Workpaper (FY 2025-26)",
      type: "workpaper",
      published_at: "2026-10-10 13:45",
      shared_with: ["Forensic Audit Team", "Partner Office"],
      format: ".XLSX",
    },
    {
      id: "rep-02",
      title: "Engagement Findings & AJE Technical Memo",
      type: "memo",
      published_at: "2026-10-10 14:10",
      shared_with: ["All Audit Staff"],
      format: ".MD",
    },
    {
      id: "rep-03",
      title: "Cryptographic Hash-Chained Audit Trail",
      type: "trail",
      published_at: "2026-10-10 14:30",
      shared_with: ["ICAI Peer Reviewer"],
      format: ".JSONL",
    },
  ]);

  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [selectedReport, setSelectedReport] = useState<any | null>(null);
  const [shareTarget, setShareTarget] = useState("Corporate Accounts Department");
  const [isFullAccess, setIsFullAccess] = useState(false);
  const [allowedFields, setAllowedFields] = useState<Record<string, boolean>>({
    invoice_no: true,
    invoice_date: true,
    party_name: true,
    taxable_amount: true,
    total_amount: true,
    risk_score: false,
    detector_hits: false,
    finding_id: false,
    aje_impact: false,
  });

  const [shareSuccess, setShareSuccess] = useState(false);

  const [accessLogs, setAccessLogs] = useState([
    { id: "al-1", report: "Statutory Revenue 4-Sheet Workpaper", accessed_by: "aud.judge", accessed_at: "2026-10-10 15:10:22", fields_viewed: "Summary (5 fields)" },
    { id: "al-2", report: "Engagement Findings Memo", accessed_by: "ptn.mehta", accessed_at: "2026-10-10 14:55:04", fields_viewed: "Full Workpaper (14 fields)" },
    { id: "al-3", report: "Cryptographic Hash-Chained Audit Trail", accessed_by: "orc.n8n", accessed_at: "2026-10-10 14:32:11", fields_viewed: "Full Trail" },
  ]);

  const handleOpenShare = (rep: any) => {
    setSelectedReport(rep);
    setShareSuccess(false);
    setShareModalOpen(true);
  };

  const handleSaveShare = (e: React.FormEvent) => {
    e.preventDefault();
    setShareSuccess(true);
    setReports((prev) =>
      prev.map((r) =>
        r.id === selectedReport?.id
          ? { ...r, shared_with: [...r.shared_with, shareTarget] }
          : r
      )
    );
    setAccessLogs((logs) => [
      {
        id: "al-" + Date.now(),
        report: selectedReport.title,
        accessed_by: "Current Auditor",
        accessed_at: new Date().toISOString().replace("T", " ").slice(0, 19),
        fields_viewed: isFullAccess ? "Full Workpaper" : "Restricted Field Mask",
      },
      ...logs,
    ]);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-medium text-slate-50 tracking-tight flex items-center gap-3">
            Report Sharing
          </h1>
        </div>
      </div>

      {/* Reports Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {reports.map((rep) => (
          <div key={rep.id} className="panel p-5 rounded-lg border border-slate-800 space-y-3 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-bold">
                  {rep.format}
                </span>
                <span className="text-[11px] text-slate-500 font-mono">{rep.published_at}</span>
              </div>
              <h3 className="font-bold text-slate-50 text-sm leading-snug">{rep.title}</h3>
              <div className="mt-3 space-y-1 text-xs">
                <div className="text-xs text-slate-400">Shared with:</div>
                <div className="flex flex-wrap gap-1">
                  {rep.shared_with.map((sw, i) => (
                    <span key={i} className="text-[11px] px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-300">
                      {sw}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="pt-2 flex items-center justify-between border-t border-slate-800 text-xs">
              <button
                onClick={() =>
                  rep.type === "workpaper"
                    ? downloadWithToken("/api/audit/deliverables/workpaper", "workpaper.xlsx").catch((e: Error) => alert(e.message))
                    : rep.type === "memo"
                    ? downloadWithToken("/api/audit/deliverables/memo", "memo.json").catch((e: Error) => alert(e.message))
                    : undefined
                }
                className="text-slate-400 hover:text-slate-50 flex items-center gap-1 transition"
              >
                <Download className="h-3.5 w-3.5" />
                <span>Download</span>
              </button>

              <button
                onClick={() => handleOpenShare(rep)}
                className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 border border-indigo-500/60 text-white font-medium flex items-center gap-1.5 transition"
              >
                <Share2 className="h-3.5 w-3.5" />
                <span>Configure Share</span>
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Immutable Access Log */}
      <div className="panel p-5 rounded-lg border border-slate-800 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 className="text-sm font-semibold text-slate-50 flex items-center gap-2">
            <Clock className="h-4 w-4 text-emerald-400" />
            Report Access Verification Log
          </h2>
          <span className="text-xs text-slate-400 font-mono">report_access_log (Supabase RLS)</span>
        </div>

        <div className="space-y-2">
          {accessLogs.map((log) => (
            <div
              key={log.id}
              className="p-3 rounded-lg bg-slate-900/40 border border-slate-800 flex items-center justify-between text-xs"
            >
              <div>
                <span className="font-semibold text-slate-50">{log.report}</span>
                <span className="text-slate-400 ml-2">by <code className="text-indigo-400">{log.accessed_by}</code></span>
              </div>
              <div className="flex items-center space-x-3 text-xs">
                <span className="font-mono text-emerald-400">{log.fields_viewed}</span>
                <span className="font-mono text-slate-500">{log.accessed_at}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Share Modal */}
      {shareModalOpen && selectedReport && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <form onSubmit={handleSaveShare} className="bg-slate-900 border border-slate-700 rounded-lg max-w-lg w-full p-6 space-y-4 text-xs">
            <h3 className="font-bold text-slate-50 text-sm flex items-center gap-2">
              <Share2 className="h-4 w-4 text-indigo-400" />
              Configure Sharing for "{selectedReport.title}"
            </h3>

            {shareSuccess ? (
              <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 space-y-2">
                <div className="font-bold flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4" />
                  Access Rules Configured & Enforced!
                </div>
                <p>The selected entity will only receive fields permitted by the active manifest.</p>
                <button
                  type="button"
                  onClick={() => setShareModalOpen(false)}
                  className="w-full mt-2 py-1.5 rounded bg-indigo-600 border border-indigo-500/40 text-white font-medium"
                >
                  Done
                </button>
              </div>
            ) : (
              <>
                <div className="space-y-1">
                  <label className="text-slate-300 font-semibold">Share With (User / Group)</label>
                  <input
                    type="text"
                    required
                    value={shareTarget}
                    onChange={(e) => setShareTarget(e.target.value)}
                    className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-slate-50"
                  />
                </div>

                <div className="space-y-2 pt-1">
                  <div className="flex items-center justify-between">
                    <label className="text-slate-300 font-semibold">Access Permissions</label>
                    <label className="flex items-center gap-2 cursor-pointer text-slate-400">
                      <input
                        type="checkbox"
                        checked={isFullAccess}
                        onChange={(e) => setIsFullAccess(e.target.checked)}
                        className="rounded border-slate-700 bg-slate-950 text-indigo-600"
                      />
                      <span>Grant Full Access (All 14 Fields)</span>
                    </label>
                  </div>

                  {!isFullAccess && (
                    <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
                      <div className="text-xs text-slate-400">Selective Field Visibility:</div>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        {Object.entries(allowedFields).map(([fKey, enabled]) => (
                          <label key={fKey} className="flex items-center space-x-2 text-slate-300 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={enabled}
                              onChange={(e) =>
                                setAllowedFields({ ...allowedFields, [fKey]: e.target.checked })
                              }
                              className="rounded border-slate-700 bg-slate-900 text-indigo-600"
                            />
                            <span className="font-mono text-xs">{fKey}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div className="flex justify-end space-x-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShareModalOpen(false)}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-400 text-xs"
                  >
                    Cancel
                  </button>
                  <button type="submit" className="px-4 py-1.5 rounded-lg bg-indigo-600 text-white font-medium">
                    Save Share Policy
                  </button>
                </div>
              </>
            )}
          </form>
        </div>
      )}
    </div>
  );
}
