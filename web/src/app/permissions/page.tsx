"use client";

import React, { useEffect, useState } from "react";
import { supabaseService } from "@/lib/supabase";
import { Permission } from "@/lib/types";
import {
  Check,
  CheckCircle2,
  Clock,
  History,
  Lock,
  RefreshCw,
  Shield,
  Sliders,
  UserCheck,
  X,
} from "lucide-react";

export default function PermissionsPage() {
  const [permissions, setPermissions] = useState<Permission[]>([
    { id: "p1", org_id: "demo", resource_type: "audit_reports", can_view: true, can_edit: false, can_approve: true, can_export: true },
    { id: "p2", org_id: "demo", resource_type: "transactions", can_view: true, can_edit: false, can_approve: false, can_export: true },
    { id: "p3", org_id: "demo", resource_type: "findings", can_view: true, can_edit: true, can_approve: true, can_export: true },
    { id: "p4", org_id: "demo", resource_type: "evidence_pbc", can_view: true, can_edit: true, can_approve: false, can_export: false },
    { id: "p5", org_id: "demo", resource_type: "investigations", can_view: true, can_edit: true, can_approve: true, can_export: true },
    { id: "p6", org_id: "demo", resource_type: "powerbi_exports", can_view: true, can_edit: false, can_approve: false, can_export: true },
  ]);

  const [auditLog, setAuditLog] = useState<any[]>([
    { id: "l1", action: "GRANT", resource_type: "findings", target_role: "engagement_partner", performed_by: "adm.kiran", performed_at: "2026-10-10 14:30:00" },
    { id: "l2", action: "RESTRICT", resource_type: "transactions", target_role: "sales", performed_by: "adm.kiran", performed_at: "2026-10-10 12:15:00" },
    { id: "l3", action: "ENABLE_EXPORT", resource_type: "audit_reports", target_role: "audit_staff", performed_by: "ptn.mehta", performed_at: "2026-10-10 11:00:00" },
  ]);

  const togglePerm = (id: string, field: "can_view" | "can_edit" | "can_approve" | "can_export") => {
    setPermissions((prev) =>
      prev.map((p) => {
        if (p.id === id) {
          const updated = { ...p, [field]: !p[field] };
          // Append audit log
          setAuditLog((logs) => [
            {
              id: "l_" + Date.now(),
              action: updated[field] ? "GRANT" : "REVOKE",
              resource_type: p.resource_type,
              target_role: "custom_rule",
              performed_by: "CA S. Mehta",
              performed_at: new Date().toISOString().replace("T", " ").slice(0, 19),
            },
            ...logs,
          ]);
          return updated;
        }
        return p;
      })
    );
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-medium text-slate-50 tracking-tight flex items-center gap-3">
            Access Control
          </h1>
        </div>
      </div>

      {/* Permissions Matrix */}
      <div className="panel p-5 rounded-lg border border-slate-800 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 className="text-sm font-semibold text-slate-50 flex items-center gap-2">
            <Sliders className="h-4 w-4 text-indigo-400" />
            Resource Access Control Matrix
          </h2>
          <span className="text-xs text-slate-400">Click any switch to toggle permission</span>
        </div>

        <div className="border border-slate-800 rounded-lg overflow-hidden bg-slate-900/60">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950 text-[11px] text-slate-400 uppercase font-mono border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Protected Resource</th>
                <th className="py-3 px-4 text-center">Can View</th>
                <th className="py-3 px-4 text-center">Can Edit / Modify</th>
                <th className="py-3 px-4 text-center">Can Sign-Off / Approve</th>
                <th className="py-3 px-4 text-center">Can Export Data</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {permissions.map((p) => (
                <tr key={p.id} className="hover:bg-slate-800/30 transition">
                  <td className="py-3 px-4 font-mono font-semibold text-slate-200">
                    {p.resource_type}
                  </td>
                  <td className="py-3 px-4 text-center">
                    <button
                      onClick={() => togglePerm(p.id, "can_view")}
                      className={`p-1.5 rounded-md border transition ${
                        p.can_view
                          ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300"
                          : "bg-slate-800 border-slate-700 text-slate-500"
                      }`}
                    >
                      {p.can_view ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
                    </button>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <button
                      onClick={() => togglePerm(p.id, "can_edit")}
                      className={`p-1.5 rounded-md border transition ${
                        p.can_edit
                          ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300"
                          : "bg-slate-800 border-slate-700 text-slate-500"
                      }`}
                    >
                      {p.can_edit ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
                    </button>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <button
                      onClick={() => togglePerm(p.id, "can_approve")}
                      className={`p-1.5 rounded-md border transition ${
                        p.can_approve
                          ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300"
                          : "bg-slate-800 border-slate-700 text-slate-500"
                      }`}
                    >
                      {p.can_approve ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
                    </button>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <button
                      onClick={() => togglePerm(p.id, "can_export")}
                      className={`p-1.5 rounded-md border transition ${
                        p.can_export
                          ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300"
                          : "bg-slate-800 border-slate-700 text-slate-500"
                      }`}
                    >
                      {p.can_export ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Immutable Permission Audit Log */}
      <div className="panel p-5 rounded-lg border border-slate-800 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 className="text-sm font-semibold text-slate-50 flex items-center gap-2">
            <History className="h-4 w-4 text-amber-400" />
            Immutable Permission Audit Log
          </h2>
          <span className="text-xs text-slate-400 font-mono">permission_audit_log (Append-Only)</span>
        </div>

        <div className="space-y-2">
          {auditLog.map((log) => (
            <div
              key={log.id}
              className="p-3 rounded-lg bg-slate-900/40 border border-slate-800 flex items-center justify-between text-xs"
            >
              <div className="flex items-center space-x-3">
                <span
                  className={`text-[11px] font-mono px-2 py-0.5 rounded font-bold ${
                    log.action.includes("GRANT") || log.action.includes("ENABLE")
                      ? "text-emerald-300"
                      : "text-rose-300"
                  }`}
                >
                  {log.action}
                </span>
                <span className="font-mono text-slate-50 font-medium">{log.resource_type}</span>
                <span className="text-slate-400">for {log.target_role}</span>
              </div>
              <div className="flex items-center space-x-3 text-xs text-slate-400">
                <span>By: <code className="text-indigo-400">{log.performed_by}</code></span>
                <span className="font-mono text-slate-500">{log.performed_at}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
