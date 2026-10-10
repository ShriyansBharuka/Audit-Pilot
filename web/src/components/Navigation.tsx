"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { AuditOverview } from "@/lib/types";
import {
  AlertTriangle,
  Award,
  BarChart3,
  Building,
  CheckCircle2,
  ChevronDown,
  FileSearch,
  FileText,
  FolderOpen,
  GitCommit,
  KeyRound,
  LineChart,
  Layers,
  LogOut,
  Network,
  Share2,
  Shield,
  Sliders,
  Sparkles,
  UserCheck,
  Zap,
} from "lucide-react";

const AUDIT_ROLES = ["audit_staff", "engagement_partner"];
const MCP_URL = process.env.NEXT_PUBLIC_MCP_URL || "http://localhost:8000/mcp";

function LoginScreen() {
  const { loginWithToken, identities } = useAuth();
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const quick = identities.filter((i) => i.token && i.role !== "orchestrator"); // orchestrator = n8n over MCP only

  const submit = async (t: string) => {
    setBusy(true);
    setError(null);
    try {
      await loginWithToken(t.trim());
    } catch (e: any) {
      setError(e.message || "Unknown token");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--background)] p-4">
      <div className="w-full max-w-md glass-panel rounded-lg border border-slate-800 p-6 space-y-5">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-lg bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center">
            <Shield className="h-4 w-4 text-indigo-400" />
          </div>
          <div>
            <div className="font-semibold text-slate-50">AuditPilot AI</div>
            <div className="text-xs text-slate-400">Statutory revenue audit · sign in with your token</div>
          </div>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (token.trim()) submit(token);
          }}
          className="space-y-2"
        >
          <label className="text-xs text-slate-400 font-mono">Token (from the judge card)</label>
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="aud_… / adm_… / ptn_…"
            className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-sm font-mono text-slate-200"
          />
          <button
            type="submit"
            disabled={busy || !token.trim()}
            className="w-full py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 border border-indigo-500/60 disabled:opacity-50 text-white text-sm font-medium flex items-center justify-center gap-2"
          >
            <KeyRound className="h-4 w-4" />
            {busy ? "Checking…" : "Sign in"}
          </button>
          {error && <div className="text-xs text-rose-400">{error}</div>}
        </form>
        {quick.length > 0 && (
          <div className="space-y-2 border-t border-slate-800 pt-4">
            <div className="text-[11px]  text-slate-500 font-semibold">Demo personas (local only)</div>
            <div className="grid grid-cols-2 gap-2">
              {quick.map((i) => (
                <button
                  key={i.principal}
                  onClick={() => submit(i.token)}
                  className="p-2 rounded-lg border border-slate-800 bg-slate-900 hover:border-slate-600 text-left text-xs"
                >
                  <div className="text-slate-200">{i.name}</div>
                  <div className="text-[11px] text-slate-500 font-mono">{i.role.replace("_", " ")}</div>
                </button>
              ))}
            </div>
            <div className="text-[11px] text-slate-500">The engagement partner always signs in with their own token.</div>
          </div>
        )}
        <div className="text-xs text-slate-500 border-t border-slate-800 pt-3">
          AI agents connect over MCP instead: <code className="text-indigo-400">{MCP_URL}</code> with{" "}
          <code className="text-indigo-400">Authorization: Bearer &lt;token&gt;</code>.
        </div>
      </div>
    </div>
  );
}

export function Navigation({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, loading, logout, identities, loginWithToken } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [cardOpen, setCardOpen] = useState(false);
  const [ov, setOv] = useState<AuditOverview | null>(null);
  const isAudit = !!user && AUDIT_ROLES.includes(user.role);

  useEffect(() => {
    if (isAudit) api.getOverview().then(setOv).catch(() => setOv(null));
  }, [isAudit, pathname]);

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-slate-400 text-sm">Loading…</div>;
  }
  if (!user) return <LoginScreen />;

  const n = (v?: number) => (v === undefined || v === null ? undefined : v.toLocaleString("en-IN"));
  // demo personas carry a token only when the API runs with DEMO_ROLE_SWITCHER=1; the partner's never does
  const personas = identities.filter(
    (i: any) => i.token && i.role !== "engagement_partner" && i.role !== "orchestrator" && i.principal !== user.principal,
  );
  const findingsTotal = ov?.findings_counts ? Object.values(ov.findings_counts).reduce((a, b) => a + b, 0) : undefined;
  const requestsTotal = ov?.evidence_requests ? Object.values(ov.evidence_requests).reduce((a, b) => a + b, 0) : undefined;
  const auditItems = [
    { href: "/", label: "Overview", icon: BarChart3, badge: ov?.company_risk?.band },
    { href: "/transactions", label: "Population", icon: Layers, badge: n(ov?.invoices_count) },
    { href: "/analytics", label: "Analytics", icon: LineChart },
    { href: "/network", label: "Circular Trading", icon: Network },
    { href: "/shap", label: "SHAP", icon: Sparkles },
    { href: "/findings", label: "Findings", icon: Award, badge: n(findingsTotal) },
    { href: "/report", label: "Memo", icon: FileText },
    { href: "/csv-check", label: "CSV check", icon: FileSearch },
    { href: "/evidence", label: "Evidence", icon: FolderOpen, badge: n(requestsTotal) },
    { href: "/orgs", label: "Organizations", icon: Building },
    { href: "/permissions", label: "Access Control", icon: Sliders },
    { href: "/sharing", label: "Report Sharing", icon: Share2 },
    { href: "/investigations", label: "Fraud Hub", icon: AlertTriangle },
    { href: "/integrations", label: "Integrations", icon: Zap },
    { href: "/trail", label: "Audit Trail", icon: GitCommit },
  ];
  // the client only ever sees its evidence requests, never the audit's reasons (vault 05 sampling)
  const navItems = isAudit ? auditItems : auditItems.filter((i) => i.href === "/evidence");
  const allowed = navItems.some((i) => i.href === pathname);

  return (
    <div className="flex h-screen bg-[var(--background)] text-slate-100 antialiased overflow-hidden">
      <aside className="w-64 flex flex-col border-r border-slate-800/80 bg-[var(--sidebar)] shrink-0 z-20">
        <div className="p-4 border-b border-slate-800/80 flex items-center justify-between">
          <Link href={isAudit ? "/" : "/evidence"} className="flex items-center space-x-2.5">
            <div className="h-7 w-7 rounded-md bg-slate-800 flex items-center justify-center">
              <Shield className="h-4 w-4 text-indigo-400" />
            </div>
            <div>
              <div className="font-medium text-sm text-slate-50">
                AuditPilot
              </div>
            </div>
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
          <div className="text-xs text-slate-500 px-3 mb-2">
            {isAudit ? "Audit Workspace" : "Client Portal"}
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center justify-between px-3 py-1.5 rounded-md text-[13px] transition-colors ${
                  isActive
                    ? "bg-slate-800 text-slate-50"
                    : "text-slate-400 hover:text-slate-50 hover:bg-slate-800/50"
                }`}
              >
                <div className="flex items-center space-x-2.5">
                  <Icon className={`h-4 w-4 ${isActive ? "text-slate-50" : "text-slate-500"}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span
                    className="text-xs text-slate-500 tabular-nums"
                  >
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        <div className="px-4 py-3 border-t border-slate-800">
          <div className="text-xs font-medium text-slate-300 truncate">{ov?.entity_name || "Konkan Marine Controls Ltd"}</div>
          <div className="flex items-center justify-between text-[11px] text-slate-400 mt-1">
            <span className="flex items-center gap-1">
                            {ov ? `${ov.period_start} → ${ov.period_end}` : "FY 2025-26"}
            </span>
            <span className="font-mono">{ov?.engagement_id || "ENG-2025-26"}</span>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-14 border-b border-slate-800/80 bg-[var(--sidebar)]/90 backdrop-blur px-8 flex items-center justify-between shrink-0 z-10">
          <div className="flex items-center space-x-3 text-xs">
            {isAudit && ov?.has_engagement && (
              <>
                <span className="text-slate-400 flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-indigo-500" />
                  {n(ov.invoices_count)} of {n(ov.invoices_count)} invoices tested
                </span>
                {!!ov.materiality_paise && (
                  <span className="text-slate-500">
                    Materiality {ov.materiality_formatted}
                  </span>
                )}
              </>
            )}
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={() => setCardOpen(true)}
              className="h-8 text-xs px-3 rounded-md hover:bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1.5 transition"
            >
              <UserCheck className="h-3.5 w-3.5 text-slate-400" />
              <span>Connect an agent</span>
            </button>
            <div className="relative">
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="h-8 flex items-center space-x-2 hover:bg-slate-800 px-2 rounded-md text-xs text-slate-200 transition"
              >
                <div className="h-6 w-6 rounded-full bg-slate-700 text-slate-200 flex items-center justify-center font-medium text-[11px]">
                  {user.role === "engagement_partner" ? "EP" : user.role.slice(0, 2).toUpperCase()}
                </div>
                <div className="text-left">
                  <div className="leading-tight font-medium">{user.name || user.principal}</div>
                  <div className="text-[11px] text-slate-400 leading-tight">{user.role.replace("_", " ")}</div>
                </div>
                <ChevronDown className="h-3 w-3 text-slate-400 ml-1" />
              </button>
              {menuOpen && (
                <div className="absolute right-0 mt-2 w-56 rounded-md bg-slate-900 border border-slate-700 py-1 z-50 text-xs">
                  {/* Switch user = sign in with another persona's token (demo mode only; never the partner) */}
                  {personas.length > 0 && (
                    <>
                      <div className="px-3 pt-1.5 pb-1 text-[11px] text-slate-500">Switch user</div>
                      {personas.map((p) => (
                        <button
                          key={p.principal}
                          onClick={async () => {
                            setMenuOpen(false);
                            await loginWithToken(p.token);
                            window.location.href = AUDIT_ROLES.includes(p.role) ? "/" : "/evidence";
                          }}
                          className="w-full text-left px-3 py-1.5 flex items-center justify-between text-slate-300 hover:bg-slate-800"
                        >
                          <span className="truncate">{p.name}</span>
                          <span className="text-[11px] text-slate-500">{p.role.replace("_", " ")}</span>
                        </button>
                      ))}
                      <div className="my-1 border-t border-slate-800" />
                    </>
                  )}
                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      logout();
                    }}
                    className="w-full text-left px-3 py-2 flex items-center gap-2 text-slate-300 hover:bg-slate-800"
                  >
                    <LogOut className="h-3.5 w-3.5" /> Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto bg-[var(--background)]">
          {allowed ? (
            <div className="mx-auto w-full max-w-[1600px] px-8 py-7">{children}</div>
          ) : (
            <div className="max-w-lg mx-auto mt-20 text-center space-y-3">
              <div className="text-sm text-slate-300">This page is for the audit team.</div>
              <Link href="/evidence" className="text-xs text-indigo-400 underline">
                Go to your evidence requests
              </Link>
            </div>
          )}
        </main>
      </div>

      {cardOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-lg max-w-2xl w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-indigo-400" />
                <h3 className="font-semibold text-slate-50 text-sm">Connect your own AI agent (MCP)</h3>
              </div>
              <button onClick={() => setCardOpen(false)} className="text-slate-400 hover:text-slate-50 text-xs px-2 py-1 rounded bg-slate-800">
                ✕ Close
              </button>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">Your agent gets your role&apos;s tools. Every call is logged.</p>
            <code className="block p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-indigo-300 break-all select-all">
              {`claude mcp add --transport http auditpilot ${MCP_URL} --header "Authorization: Bearer ${
                user.role === "engagement_partner" ? "<an auditor token>" : user.token
              }"`}
            </code>
          </div>
        </div>
      )}
    </div>
  );
}
