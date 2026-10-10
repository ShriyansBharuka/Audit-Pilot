"use client";

import React, { useState } from "react";
import { api } from "@/lib/api";
import {
  BarChart3,
  CheckCircle2,
  Copy,
  ExternalLink,
  Play,
  RefreshCw,
  Server,
  Share2,
  Terminal,
  Zap,
} from "lucide-react";

export default function IntegrationsPage() {
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [triggering, setTriggering] = useState<string | null>(null);
  const [workflowRuns, setWorkflowRuns] = useState<any[]>([
    {
      id: "exec_d819fa0b12",
      name: "Daily PBC Evidence Expiry Monitor",
      status: "COMPLETED",
      at: "2026-10-10 14:00:15",
      receipt: "Dispatched 12 reminder webhooks to client accounts team",
    },
    {
      id: "exec_4019ab921c",
      name: "High-Risk Transaction Alert to Teams/Slack",
      status: "COMPLETED",
      at: "2026-10-10 12:45:00",
      receipt: "Broadcasted 13 HIGH risk invoices to Forensic Channel",
    },
  ]);

  const powerBiUrl = "http://localhost:8000/api/integrations/powerbi";

  const copyPowerBi = () => {
    navigator.clipboard.writeText(powerBiUrl);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
  };

  const handleTrigger = async (workflowName: string, action: string) => {
    setTriggering(workflowName);
    try {
      const res = await api.triggerN8nWorkflow(workflowName, action);
      setWorkflowRuns([
        {
          id: res.execution_id,
          name: res.workflow_name,
          status: "SUCCESS",
          at: new Date().toLocaleTimeString(),
          receipt: res.message,
        },
        ...workflowRuns,
      ]);
    } catch (err: any) {
      alert("Failed to trigger workflow: " + err.message);
    } finally {
      setTriggering(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            Enterprise Integrations & Workflow Orchestration
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-mono font-normal">
              Power BI · n8n · MCP
            </span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Connect statutory audit deliverables to enterprise business intelligence, webhook workflows, and AI coding agents.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Power BI Connector Card */}
        <div className="glass-panel p-5 rounded-xl border border-slate-800 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-lg bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400 font-bold">
                <BarChart3 className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">Microsoft Power BI Direct Connector</h2>
                <div className="text-[11px] text-slate-400">Live JSON Web Data Connector Endpoint</div>
              </div>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold">
              Ready
            </span>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed">
            Consume cleaned population sales, tax breakdown, related-party flags, and detector findings directly in Microsoft Power BI Desktop or Service without exposing database credentials.
          </p>

          <div className="space-y-1 text-xs">
            <label className="text-slate-400 font-mono text-[11px]">Power BI Web Data Feed URL:</label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={powerBiUrl}
                className="flex-1 p-2 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-indigo-300 select-all"
              />
              <button
                onClick={copyPowerBi}
                className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition"
              >
                {copiedUrl ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                <span>{copiedUrl ? "Copied" : "Copy"}</span>
              </button>
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-400 space-y-1">
            <div className="font-semibold text-slate-300">How to connect in Power BI:</div>
            <div>1. In Power BI Desktop, click <strong>Get Data</strong> → <strong>Web</strong></div>
            <div>2. Paste the URL above and click <strong>OK</strong></div>
            <div>3. Transform or load <code>invoices</code> and <code>findings</code> tables into your DAX model.</div>
          </div>
        </div>

        {/* MCP Agent Gateway Card */}
        <div className="glass-panel p-5 rounded-xl border border-slate-800 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 font-bold">
                <Server className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">Model Context Protocol (MCP) Server</h2>
                <div className="text-[11px] text-slate-400">Streamable HTTP Gateway (46 Audit Tools)</div>
              </div>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-bold">
              Port 8000
            </span>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed">
            All 46 audit tools are exposed over standard MCP with cryptographic token-bound RBAC. External AI agents (Claude Code, Cursor, Windsurf) connect directly with token headers.
          </p>

          <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 space-y-2">
            <div className="text-slate-500 font-sans text-[10px] uppercase font-semibold">Connect via CLI:</div>
            <code className="text-indigo-300 block select-all break-all">
              claude mcp add --transport http auditpilot http://localhost:8000/mcp --header "Authorization: Bearer aud_pD_bL7H70P_42AypXzL44a7_qiCTEH5z"
            </code>
          </div>

          <div className="text-[11px] text-slate-400 flex items-center justify-between pt-1">
            <span>Audit Trail Transport: <code className="text-emerald-400">HTTP / Stdio</code></span>
            <span className="text-slate-500">Hash-Chained</span>
          </div>
        </div>
      </div>

      {/* n8n Webhook Orchestration */}
      <div className="glass-panel p-5 rounded-xl border border-slate-800 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-emerald-400" />
            <h2 className="text-sm font-semibold text-white">n8n Workflow Execution Orchestrator</h2>
          </div>
          <span className="text-xs text-slate-400 font-mono">Webhook Receiver Active</span>
        </div>

        {/* Action Triggers */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
            <div className="font-semibold text-xs text-white">Daily PBC Evidence Reminders</div>
            <p className="text-[11px] text-slate-400">Dispatches automated notifications for unanswered client requests.</p>
            <button
              onClick={() => handleTrigger("Daily PBC Evidence Reminders", "dispatch_reminders")}
              disabled={triggering === "Daily PBC Evidence Reminders"}
              className="w-full mt-1 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 flex items-center justify-center gap-1.5 transition"
            >
              <Play className="h-3 w-3 text-emerald-400" />
              <span>{triggering === "Daily PBC Evidence Reminders" ? "Triggering..." : "Run Workflow"}</span>
            </button>
          </div>

          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
            <div className="font-semibold text-xs text-white">High-Risk Exception Alerts</div>
            <p className="text-[11px] text-slate-400">Pushes circular trading and cut-off findings to audit partner channel.</p>
            <button
              onClick={() => handleTrigger("High-Risk Exception Alerts", "send_alerts")}
              disabled={triggering === "High-Risk Exception Alerts"}
              className="w-full mt-1 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 flex items-center justify-center gap-1.5 transition"
            >
              <Play className="h-3 w-3 text-emerald-400" />
              <span>{triggering === "High-Risk Exception Alerts" ? "Triggering..." : "Run Workflow"}</span>
            </button>
          </div>

          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
            <div className="font-semibold text-xs text-white">Workpaper Sync & Backup</div>
            <p className="text-[11px] text-slate-400">Archives current 4-sheet workpaper and findings memo to secure vault.</p>
            <button
              onClick={() => handleTrigger("Workpaper Sync & Backup", "sync_workpaper")}
              disabled={triggering === "Workpaper Sync & Backup"}
              className="w-full mt-1 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 flex items-center justify-center gap-1.5 transition"
            >
              <Play className="h-3 w-3 text-emerald-400" />
              <span>{triggering === "Workpaper Sync & Backup" ? "Triggering..." : "Run Workflow"}</span>
            </button>
          </div>
        </div>

        {/* Workflow Run History */}
        <div className="space-y-2 pt-2">
          <div className="text-xs font-semibold text-slate-300 uppercase tracking-wider text-[11px]">
            Recent n8n Execution Runs
          </div>
          <div className="space-y-1.5">
            {workflowRuns.map((run) => (
              <div
                key={run.id}
                className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between text-xs"
              >
                <div>
                  <span className="font-semibold text-white">{run.name}</span>
                  <div className="text-[11px] text-slate-400 mt-0.5">{run.receipt}</div>
                </div>
                <div className="text-right">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold">
                    {run.status}
                  </span>
                  <div className="text-[10px] text-slate-500 font-mono mt-0.5">{run.at}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
