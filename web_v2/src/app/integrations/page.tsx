"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { N8nEvents } from "@/lib/types";
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
  const [feed, setFeed] = useState<N8nEvents | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const powerBiUrl = api.getPowerBiDatasetUrl();
  const mcpUrl = process.env.NEXT_PUBLIC_MCP_URL || "http://localhost:8000/mcp";

  const load = () => {
    setRefreshing(true);
    api.getN8nEvents(20).then(setFeed).catch(() => setFeed(null)).finally(() => setRefreshing(false));
  };
  useEffect(load, []);

  const copyPowerBi = () => {
    navigator.clipboard.writeText(powerBiUrl);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-medium text-slate-50 tracking-tight flex items-center gap-3">
            Integrations
          </h1>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Power BI Connector Card */}
        <div className="panel p-5 rounded-lg border border-slate-800 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-lg bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400 font-bold">
                <BarChart3 className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-slate-50">Microsoft Power BI Direct Connector</h2>
                <div className="text-xs text-slate-400">Live JSON Web Data Connector Endpoint</div>
              </div>
            </div>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded text-emerald-300 font-bold">
              Ready
            </span>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed">Population, findings and flags for Power BI.</p>

          <div className="space-y-1 text-xs">
            <label className="text-slate-400 font-mono text-xs">Power BI Web Data Feed URL:</label>
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

          <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-400 space-y-1">
            <div className="font-semibold text-slate-300">How to connect in Power BI:</div>
            <div>1. In Power BI Desktop, click <strong>Get Data</strong> → <strong>Web</strong></div>
            <div>2. Paste the URL above and click <strong>OK</strong></div>
            <div>3. Under <strong>Advanced</strong>, add the header <code>Authorization: Bearer &lt;auditor token&gt;</code>.</div>
            <div>4. Load the <code>invoices</code> and <code>findings</code> tables into your model.</div>
          </div>
        </div>

        {/* MCP Agent Gateway Card */}
        <div className="panel p-5 rounded-lg border border-slate-800 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 font-bold">
                <Server className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-slate-50">Model Context Protocol (MCP) Server</h2>
                <div className="text-xs text-slate-400">Streamable HTTP gateway, role-filtered tools</div>
              </div>
            </div>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded text-indigo-300 font-bold">
              Port 8000
            </span>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed">Connect an AI agent over MCP with your token.</p>

          <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 space-y-2">
            <div className="text-slate-500 font-sans text-[11px] uppercase font-semibold">Connect via CLI:</div>
            <code className="text-indigo-300 block select-all break-all">
              {`claude mcp add --transport http auditpilot ${mcpUrl} --header "Authorization: Bearer aud_…"`}
            </code>
          </div>

          <div className="text-xs text-slate-400 flex items-center justify-between pt-1">
            <span>Audit Trail Transport: <code className="text-emerald-400">HTTP / Stdio</code></span>
            <span className="text-slate-500">Hash-Chained</span>
          </div>
        </div>
      </div>

      {/* n8n: real events this app emits; the workflows themselves run in n8n (n8n/README.md) */}
      <div className="panel p-5 rounded-lg border border-slate-800 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-emerald-400" />
            <h2 className="text-sm font-semibold text-slate-50">n8n event feed</h2>
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`text-[11px] font-mono px-2 py-0.5 rounded font-bold ${
                feed?.webhook_configured ? "text-emerald-300" : "text-amber-300"
              }`}
            >
              {feed?.webhook_configured ? "webhook configured" : "N8N_WEBHOOK_URL not set: events recorded only"}
            </span>
            <button onClick={load} className="text-slate-400 hover:text-slate-50">
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
          {(feed?.workflows || []).map((w) => (
            <div key={w} className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300">
              {w}
            </div>
          ))}
        </div>
        <div className="space-y-1.5">
          <div className="text-xs font-semibold text-slate-300 ">Recent events (signed HMAC-SHA256 webhooks)</div>
          {(feed?.events || []).length === 0 && <div className="text-xs text-slate-500">No events yet.</div>}
          {(feed?.events || []).map((ev) => (
            <div key={ev.id} className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between text-xs">
              <span className="font-mono text-slate-50">
                #{ev.id} {ev.kind}
              </span>
              <span className="flex items-center gap-3">
                <span className="text-[11px] text-slate-500 font-mono">{ev.at}</span>
                <span
                  className={`text-[11px] font-mono px-2 py-0.5 rounded ${
                    ev.notified_at ? "text-emerald-300" : "bg-slate-800 text-slate-400"
                  }`}
                >
                  {ev.notified_at ? "delivered" : "recorded"}
                </span>
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
