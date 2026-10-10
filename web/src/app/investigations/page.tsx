"use client";

import React, { useEffect, useState } from "react";
import { supabaseService } from "@/lib/supabase";
import { Investigation } from "@/lib/types";
import {
  AlertOctagon,
  AlertTriangle,
  Award,
  CheckCircle2,
  Clock,
  FileCheck,
  FileText,
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  ShieldAlert,
  User,
  Users,
} from "lucide-react";

export default function InvestigationsPage() {
  const [investigations, setInvestigations] = useState<Investigation[]>([
    {
      id: "inv-001",
      org_id: "demo-org",
      title: "Circular Trading Accommodation Network (Ratnagiri - Verna Axis)",
      description: "Detected multi-entity round-trip invoices with no physical logistics delivery (D10 / Companies Act s.143(12)).",
      severity: "CRITICAL",
      status: "OPEN",
      created_at: "2026-10-10 13:15:00",
      resolution_summary: "Awaiting final confirmation from lead engagement partner.",
    },
    {
      id: "inv-002",
      org_id: "demo-org",
      title: "Premature Revenue Cut-Off via Post-Period Credit Reversals",
      description: "Invoices issued in final 5 days of March reversed via credit notes in April with zero return movements (D3 / D9).",
      severity: "HIGH",
      status: "IN_REVIEW",
      created_at: "2026-10-10 14:00:00",
    },
  ]);

  const [selectedCase, setSelectedCase] = useState<Investigation | null>(investigations[0]);
  const [comments, setComments] = useState<any[]>([
    { id: "c1", author: "aud.judge", role: "Audit Staff", text: "Traced LR-000492: transporter log shows no vehicle registration in Goa RTO. Consignment appears fictitious.", at: "14:15" },
    { id: "c2", author: "ptn.mehta", role: "Engagement Partner", text: "Agreed. This matches circular pattern Plant C. Draft proposed AJE to reverse revenue and derecognize debtors.", at: "14:28" },
  ]);

  const [newComment, setNewComment] = useState("");
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newSeverity, setNewSeverity] = useState<"CRITICAL" | "HIGH" | "MEDIUM">("HIGH");

  const handleAddComment = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    setComments([
      ...comments,
      {
        id: "c_" + Date.now(),
        author: "Current User",
        role: "Auditor",
        text: newComment.trim(),
        at: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);
    setNewComment("");
  };

  const handleCreateCase = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    const item: Investigation = {
      id: "inv-00" + (investigations.length + 1),
      org_id: "demo-org",
      title: newTitle.trim(),
      description: newDesc.trim(),
      severity: newSeverity,
      status: "OPEN",
      created_at: new Date().toISOString().replace("T", " ").slice(0, 19),
    };
    setInvestigations([item, ...investigations]);
    setSelectedCase(item);
    setCreateModalOpen(false);
    setNewTitle("");
    setNewDesc("");
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            Fraud Investigation & Collaboration Hub
            <span className="text-xs px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 font-mono font-normal">
              Cross-Entity Fraud Docket
            </span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Collaborative case management for revenue fraud investigations, evidence threads, and traceable conclusions.
          </p>
        </div>

        <button
          onClick={() => setCreateModalOpen(true)}
          className="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold flex items-center gap-1.5 transition shadow-lg shadow-rose-600/20"
        >
          <Plus className="h-4 w-4" />
          <span>New Investigation Docket</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Docket List */}
        <div className="glass-panel p-4 rounded-xl border border-slate-800 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
            <h2 className="text-sm font-semibold text-white flex items-center gap-1.5">
              <ShieldAlert className="h-4 w-4 text-rose-400" />
              Active Cases
            </h2>
            <span className="text-xs font-mono text-slate-400">{investigations.length}</span>
          </div>

          <div className="space-y-2">
            {investigations.map((item) => (
              <div
                key={item.id}
                onClick={() => setSelectedCase(item)}
                className={`p-3.5 rounded-xl border cursor-pointer transition ${
                  selectedCase?.id === item.id
                    ? "border-rose-500/80 bg-rose-500/10 shadow-lg"
                    : "border-slate-800 bg-slate-900/60 hover:border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span
                    className={`text-[9px] font-mono px-2 py-0.5 rounded font-bold ${
                      item.severity === "CRITICAL"
                        ? "bg-rose-500/20 text-rose-300"
                        : "bg-amber-500/20 text-amber-300"
                    }`}
                  >
                    {item.severity}
                  </span>
                  <span className="text-[10px] text-slate-400 font-mono">{item.status}</span>
                </div>
                <div className="font-semibold text-xs text-white leading-snug">{item.title}</div>
                <div className="text-[10px] text-slate-400 mt-2 truncate">{item.created_at}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Right 2 Columns: Selected Case Workspace */}
        <div className="lg:col-span-2 space-y-5">
          {selectedCase ? (
            <>
              {/* Case Header Banner */}
              <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-rose-400 font-bold uppercase">{selectedCase.id}</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                    Status: {selectedCase.status}
                  </span>
                </div>
                <h2 className="text-base font-bold text-white leading-snug">{selectedCase.title}</h2>
                <p className="text-xs text-slate-300 leading-relaxed">{selectedCase.description}</p>
              </div>

              {/* Thread Discussion */}
              <div className="glass-panel p-5 rounded-xl border border-slate-800 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    <MessageSquare className="h-4 w-4 text-indigo-400" />
                    Investigation Discussion & Evidence Log
                  </h3>
                  <span className="text-xs text-slate-400 font-mono">{comments.length} comments</span>
                </div>

                {/* Comment Feed */}
                <div className="space-y-3 max-h-[350px] overflow-y-auto pr-1">
                  {comments.map((c) => (
                    <div key={c.id} className="p-3.5 rounded-xl bg-slate-950 border border-slate-800/80 space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-indigo-300">{c.author}</span>
                          <span className="text-[10px] text-slate-400 font-mono px-1.5 py-0.2 rounded bg-slate-900">
                            {c.role}
                          </span>
                        </div>
                        <span className="text-[10px] text-slate-500 font-mono">{c.at}</span>
                      </div>
                      <p className="text-xs text-slate-200 leading-relaxed">{c.text}</p>
                    </div>
                  ))}
                </div>

                {/* Comment Input */}
                <form onSubmit={handleAddComment} className="pt-2 flex items-center gap-2">
                  <input
                    type="text"
                    placeholder="Contribute forensic findings or reference evidence IDs..."
                    value={newComment}
                    onChange={(e) => setNewComment(e.target.value)}
                    className="flex-1 p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-white focus:outline-none focus:border-indigo-500"
                  />
                  <button
                    type="submit"
                    className="px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition"
                  >
                    <Send className="h-3.5 w-3.5" />
                    <span>Post</span>
                  </button>
                </form>
              </div>
            </>
          ) : (
            <div className="py-20 text-center text-slate-400 text-xs">Select an investigation docket.</div>
          )}
        </div>
      </div>

      {/* New Case Modal */}
      {createModalOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <form onSubmit={handleCreateCase} className="bg-slate-900 border border-slate-700 rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4 text-xs">
            <h3 className="font-bold text-white text-sm">Open New Fraud Investigation</h3>
            <div className="space-y-1">
              <label className="text-slate-300 font-semibold">Case Title</label>
              <input
                type="text"
                required
                placeholder="e.g. Circular Invoicing with Accommodation Vendor"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-white"
              />
            </div>
            <div className="space-y-1">
              <label className="text-slate-300 font-semibold">Severity</label>
              <select
                value={newSeverity}
                onChange={(e: any) => setNewSeverity(e.target.value)}
                className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-white"
              >
                <option value="CRITICAL">CRITICAL</option>
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-slate-300 font-semibold">Forensic Description & Hypotheses</label>
              <textarea
                rows={3}
                required
                placeholder="State anomalies, detector flags, and initial observations..."
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-white"
              />
            </div>
            <div className="flex justify-end space-x-2 pt-2">
              <button
                type="button"
                onClick={() => setCreateModalOpen(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-400 text-xs"
              >
                Cancel
              </button>
              <button type="submit" className="px-4 py-1.5 rounded-lg bg-rose-600 text-white font-medium">
                Create Docket
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
