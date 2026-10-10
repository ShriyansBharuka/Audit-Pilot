"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { FindingItem } from "@/lib/types";
import {
  AlertOctagon,
  AlertTriangle,
  Award,
  CheckCircle2,
  FileCheck,
  FileText,
  Lock,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";

export default function FindingsPage() {
  const { user } = useAuth();
  const [findings, setFindings] = useState<FindingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [selectedFinding, setSelectedFinding] = useState<FindingItem | null>(null);

  // Partner Decision Modal
  const [decisionModalOpen, setDecisionModalOpen] = useState(false);
  const [decisionType, setDecisionType] = useState<"CONFIRM" | "REJECT" | "MODIFY">("CONFIRM");
  const [decisionNote, setDecisionNote] = useState("");
  const [submittingDecision, setSubmittingDecision] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);

  // Sign-off Modal
  const [signoffModalOpen, setSignoffModalOpen] = useState(false);
  const [blockers, setBlockers] = useState<string[]>([]);
  const [signoffStatement, setSignoffStatement] = useState(
    "I confirm that I have reviewed 100% of the substantive testing findings, evaluated uncorrected misstatements against overall materiality, and sign off on the statutory revenue audit for FY 2025-26."
  );
  const [signoffPassword, setSignoffPassword] = useState("partner-pass");
  const [signingOff, setSigningOff] = useState(false);
  const [signoffResult, setSignoffResult] = useState<any | null>(null);

  const loadFindings = () => {
    setLoading(true);
    api
      .getFindings(statusFilter || undefined)
      .then((res) => {
        setFindings(res);
        if (res.length > 0 && !selectedFinding) {
          setSelectedFinding(res[0]);
        }
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadFindings();
  }, [statusFilter]);

  const handleOpenDecision = (type: "CONFIRM" | "REJECT" | "MODIFY") => {
    setDecisionType(type);
    setDecisionNote("");
    setDecisionError(null);
    setDecisionModalOpen(true);
  };

  const submitDecision = async () => {
    if (!selectedFinding) return;
    if (!decisionNote.trim()) {
      setDecisionError("Mandatory partner comment is required under ICAI standards.");
      return;
    }
    setSubmittingDecision(true);
    setDecisionError(null);
    try {
      await api.decideFinding(selectedFinding.id, decisionType, decisionNote.trim());
      setDecisionModalOpen(false);
      loadFindings();
    } catch (err: any) {
      setDecisionError(err.message || "Failed to record partner decision");
    } finally {
      setSubmittingDecision(false);
    }
  };

  const handleOpenSignoff = () => {
    api.getSignoffBlockers().then((b) => setBlockers(b || []));
    setSignoffModalOpen(true);
  };

  const submitSignoff = async () => {
    setSigningOff(true);
    try {
      const res = await api.signOff(signoffStatement, signoffPassword);
      setSignoffResult(res);
    } catch (err: any) {
      alert(err.message || "Sign-off refused");
    } finally {
      setSigningOff(false);
    }
  };

  const isPartner = user?.role === "engagement_partner";

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            Findings & Engagement Partner Sign-Off
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-mono font-normal">
              {findings.length} Total AJEs
            </span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Review proposed adjusting journal entries, confirm factual misstatements, and execute final audit sign-off.
          </p>
        </div>

        {/* Sign-off Trigger Button */}
        <button
          onClick={handleOpenSignoff}
          className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-2 shadow-lg shadow-emerald-600/20 transition"
        >
          <Lock className="h-4 w-4" />
          <span>Execute Partner Sign-Off</span>
        </button>
      </div>

      {/* Role Alert if not partner */}
      {!isPartner && (
        <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
            <span>
              You are currently viewing as <strong>{user?.name} ({user?.role})</strong>. Only the Engagement Partner may confirm/reject findings or sign off. Use the persona switcher above to switch to CA S. Mehta.
            </span>
          </div>
        </div>
      )}

      {/* Filter and Status Bar */}
      <div className="flex items-center space-x-2 text-xs">
        {["", "PROPOSED", "CONFIRMED", "REJECTED", "MODIFIED"].map((st) => (
          <button
            key={st}
            onClick={() => setStatusFilter(st)}
            className={`px-3 py-1.5 rounded-lg border transition ${
              statusFilter === st
                ? "bg-indigo-600 border-indigo-500 text-white font-medium"
                : "border-slate-800 bg-slate-900/60 text-slate-400 hover:text-white"
            }`}
          >
            {st || "All Findings"}
          </button>
        ))}
      </div>

      {/* Main 2-column split layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left list (1 col) */}
        <div className="glass-panel p-3 rounded-xl border border-slate-800 space-y-2 overflow-y-auto max-h-[750px]">
          {loading ? (
            <div className="py-12 text-center text-slate-400">
              <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2 text-indigo-400" />
              Loading findings...
            </div>
          ) : findings.length === 0 ? (
            <div className="py-8 text-center text-slate-400 text-xs">No findings match this filter.</div>
          ) : (
            findings.map((f) => (
              <div
                key={f.id}
                onClick={() => setSelectedFinding(f)}
                className={`p-3.5 rounded-xl border cursor-pointer transition ${
                  selectedFinding?.id === f.id
                    ? "border-indigo-500 bg-indigo-500/10"
                    : "border-slate-800 bg-slate-900/60 hover:border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-mono font-bold text-indigo-400">{f.id}</span>
                  <span
                    className={`text-[9px] font-mono px-1.5 py-0.2 rounded ${
                      f.status === "CONFIRMED"
                        ? "bg-emerald-500/20 text-emerald-300"
                        : f.status === "REJECTED"
                        ? "bg-rose-500/20 text-rose-300"
                        : "bg-amber-500/20 text-amber-300"
                    }`}
                  >
                    {f.status}
                  </span>
                </div>
                <div className="font-semibold text-xs text-white truncate">{f.title}</div>
                <div className="flex items-center justify-between mt-2 text-[11px]">
                  <span className="text-slate-400">{f.category}</span>
                  <span className="font-mono font-bold text-amber-400">{f.gross_impact_formatted}</span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Right detail view (2 cols) */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-xl border border-slate-800 space-y-5">
          {selectedFinding ? (
            <>
              {/* Header */}
              <div className="flex items-start justify-between border-b border-slate-800 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold text-indigo-400">{selectedFinding.id}</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                      Detector {selectedFinding.detector} ({selectedFinding.code})
                    </span>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
                        selectedFinding.status === "CONFIRMED"
                          ? "bg-emerald-500/20 text-emerald-300"
                          : selectedFinding.status === "REJECTED"
                          ? "bg-rose-500/20 text-rose-300"
                          : "bg-amber-500/20 text-amber-300"
                      }`}
                    >
                      {selectedFinding.status}
                    </span>
                  </div>
                  <h2 className="text-base font-bold text-white mt-1">{selectedFinding.title}</h2>
                </div>

                {/* Partner Action Buttons */}
                {isPartner && selectedFinding.status === "PROPOSED" && (
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => handleOpenDecision("CONFIRM")}
                      className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition"
                    >
                      Confirm
                    </button>
                    <button
                      onClick={() => handleOpenDecision("REJECT")}
                      className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-medium transition"
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>

              {/* Impact Banner */}
              <div className="grid grid-cols-3 gap-3 p-3.5 rounded-xl bg-slate-900 border border-slate-800 text-xs">
                <div>
                  <div className="text-[10px] text-slate-500 uppercase font-mono">Gross Impact</div>
                  <div className="text-base font-bold font-mono text-amber-400 mt-0.5">
                    {selectedFinding.gross_impact_formatted}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500 uppercase font-mono">Taxable Value</div>
                  <div className="text-base font-bold font-mono text-slate-200 mt-0.5">
                    {selectedFinding.taxable_impact_formatted}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500 uppercase font-mono">Confidence Level</div>
                  <div className="text-base font-bold font-mono text-indigo-400 mt-0.5">
                    {selectedFinding.confidence}
                  </div>
                </div>
              </div>

              {/* Explanation & Technical Basis */}
              <div className="space-y-2 text-xs">
                <h3 className="font-semibold text-white uppercase tracking-wider text-[11px]">
                  Auditor Substantive Explanation
                </h3>
                <p className="text-slate-300 leading-relaxed bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                  {selectedFinding.explanation}
                </p>
                <div className="text-[11px] text-indigo-400 font-mono">
                  Standards Cited: {selectedFinding.standards}
                </div>
              </div>

              {/* Proposed Adjusting Journal Entry (AJE) Table */}
              <div className="space-y-2">
                <h3 className="font-semibold text-white uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                  <FileCheck className="h-3.5 w-3.5 text-emerald-400" />
                  Proposed Adjusting Journal Entry (AJE)
                </h3>
                {!selectedFinding.proposed_aje || selectedFinding.proposed_aje.length === 0 ? (
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 text-xs">
                    Disclosure-only matter. No balance sheet reclassification proposed.
                  </div>
                ) : (
                  <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950">
                    <table className="w-full text-left text-xs text-slate-300">
                      <thead className="bg-slate-900 text-[10px] text-slate-400 uppercase font-mono">
                        <tr>
                          <th className="p-2.5">Account Code</th>
                          <th className="p-2.5">Party</th>
                          <th className="p-2.5 text-right">Debit (₹)</th>
                          <th className="p-2.5 text-right">Credit (₹)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800">
                        {selectedFinding.proposed_aje.map((line, idx) => (
                          <tr key={idx}>
                            <td className="p-2.5 font-mono text-indigo-300 font-medium">{line.account_code}</td>
                            <td className="p-2.5 text-slate-400">{line.party_id || "—"}</td>
                            <td className="p-2.5 text-right font-mono text-slate-200">
                              {line.dr_paise ? (line.dr_paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 }) : "—"}
                            </td>
                            <td className="p-2.5 text-right font-mono text-slate-200">
                              {line.cr_paise ? (line.cr_paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 }) : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="py-20 text-center text-slate-400 text-xs">Select a finding to inspect its workpaper.</div>
          )}
        </div>
      </div>

      {/* Partner Decision Modal */}
      {decisionModalOpen && selectedFinding && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <h3 className="font-bold text-white text-sm">
              Record Partner Decision: {decisionType} Finding {selectedFinding.id}
            </h3>
            <p className="text-xs text-slate-400">
              Under SA 230 and SA 450, partner review actions require an explicit, professional rationale recorded permanently in the tamper-evident audit trail.
            </p>

            {decisionError && (
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
                {decisionError}
              </div>
            )}

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-300">Mandatory Partner Note / Comment</label>
              <textarea
                rows={3}
                placeholder="State your audit conclusion, corroboration examined, or basis for rejection..."
                value={decisionNote}
                onChange={(e) => setDecisionNote(e.target.value)}
                className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="flex justify-end space-x-2 pt-2">
              <button
                onClick={() => setDecisionModalOpen(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-400 text-xs hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={submitDecision}
                disabled={submittingDecision}
                className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition"
              >
                {submittingDecision ? "Recording..." : `Confirm ${decisionType}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sign-off Modal */}
      {signoffModalOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-xl w-full p-6 shadow-2xl space-y-4">
            <h3 className="font-bold text-white text-sm flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-emerald-400" />
              Final Engagement Partner Sign-Off
            </h3>

            {signoffResult ? (
              <div className="space-y-3 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300">
                <div className="font-bold text-emerald-400 flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4" />
                  Audit Successfully Signed Off!
                </div>
                <div>Deliverables locked with cryptographic hash:</div>
                <div className="font-mono text-[10px] break-all bg-slate-950 p-2 rounded text-slate-300">
                  {signoffResult.signoff_hash}
                </div>
                <button
                  onClick={() => setSignoffModalOpen(false)}
                  className="w-full mt-2 py-1.5 rounded bg-emerald-600 text-white font-medium"
                >
                  Close
                </button>
              </div>
            ) : (
              <>
                {blockers.length > 0 && (
                  <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs space-y-1">
                    <div className="font-bold text-rose-400 flex items-center gap-1">
                      <AlertOctagon className="h-3.5 w-3.5" />
                      Sign-off Blocked by Preconditions:
                    </div>
                    {blockers.map((b, i) => (
                      <div key={i}>• {b}</div>
                    ))}
                  </div>
                )}

                <div className="space-y-1 text-xs">
                  <label className="text-slate-300 font-semibold">ICAI Engagement Partner Statement</label>
                  <textarea
                    rows={3}
                    value={signoffStatement}
                    onChange={(e) => setSignoffStatement(e.target.value)}
                    className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-white"
                  />
                </div>

                <div className="space-y-1 text-xs">
                  <label className="text-slate-300 font-semibold">Partner Sign-off Password / Token Key</label>
                  <input
                    type="password"
                    value={signoffPassword}
                    onChange={(e) => setSignoffPassword(e.target.value)}
                    className="w-full p-2 rounded-lg bg-slate-950 border border-slate-700 text-xs text-white"
                  />
                </div>

                <div className="flex justify-end space-x-2 pt-2">
                  <button
                    onClick={() => setSignoffModalOpen(false)}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-400 text-xs"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={submitSignoff}
                    disabled={signingOff || blockers.length > 0}
                    className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-xs font-semibold"
                  >
                    {signingOff ? "Signing..." : "Lock & Sign Off Audit"}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
