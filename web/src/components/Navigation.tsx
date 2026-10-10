"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { API_ERROR_EVENT, api } from "@/lib/api";
import { AuditOverview } from "@/lib/types";
import { AlertTriangle, ChevronDown, ChevronRight, KeyRound, LogOut, Shield, UserCheck, X } from "lucide-react";
import { NAV, PRINTABLE, allHrefs, groupForPath, itemHrefs, type BadgeKey, type NavItem } from "@/lib/nav";
import { SectionTabs } from "@/components/SectionTabs";
import { ExportPdfButton } from "@/components/ExportPdfButton";

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
  // collapsible menu: group open state (Admin closed by default) and expanded items with sub-pages
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(NAV.map((g) => [g.key, g.defaultOpen])),
  );
  const [openItems, setOpenItems] = useState<Record<string, boolean>>({});
  const [apiError, setApiError] = useState<string | null>(null);

  // network / server failures from any page land in one banner (lib/api.ts reportApiError)
  useEffect(() => {
    const on = (e: Event) => setApiError((e as CustomEvent<string>).detail);
    window.addEventListener(API_ERROR_EVENT, on);
    return () => window.removeEventListener(API_ERROR_EVENT, on);
  }, []);
  useEffect(() => setApiError(null), [pathname]);
  const isAudit = !!user && AUDIT_ROLES.includes(user.role);

  // auto-open the group (and the item) that holds the current page
  useEffect(() => {
    const g = groupForPath(pathname);
    if (g) setOpenGroups((o) => (o[g.key] ? o : { ...o, [g.key]: true }));
    const it = g?.items.find((i) => i.tabs && itemHrefs(i).includes(pathname));
    if (it) setOpenItems((o) => (o[it.href] ? o : { ...o, [it.href]: true }));
  }, [pathname]);

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
  const requestsTotal = ov?.evidence_requests ? Object.values(ov.evidence_requests).reduce((a, b) => a + b, 0) : undefined;
  const badges: Record<BadgeKey, string | undefined> = {
    risk: ov?.company_risk?.band,
    invoices: n(ov?.invoices_count),
    requests: n(requestsTotal),
    proposed: n(ov?.findings_counts?.PROPOSED), // open findings: the partner signs off under Analytics > Findings
  };
  // the client only ever sees its evidence requests, never the audit's reasons (vault 05 sampling)
  const groups = isAudit
    ? NAV
    : [{ key: "client", label: "Client portal", defaultOpen: true, items: NAV[0].items.filter((i) => i.href === "/evidence") }];
  const allowed = isAudit ? allHrefs().includes(pathname) : pathname === "/evidence";

  const navLink = (item: NavItem) => {
    const Icon = item.icon;
    const active = itemHrefs(item).includes(pathname);
    const expanded = !!openItems[item.href];
    const badge = item.badge && badges[item.badge];
    return (
      <div key={item.href}>
        <div
          className={`flex items-center rounded-md text-[13px] transition-colors ${
            active ? "bg-slate-800 text-slate-50" : "text-slate-400 hover:text-slate-50 hover:bg-slate-800/50"
          }`}
        >
          <Link href={item.href} className="flex-1 flex items-center justify-between pl-3 pr-2 py-1.5 min-w-0">
            <span className="flex items-center gap-2.5 min-w-0">
              <Icon className={`h-4 w-4 shrink-0 ${active ? "text-slate-50" : "text-slate-500"}`} />
              <span className="truncate">{item.label}</span>
            </span>
            {badge && <span className="text-xs text-slate-500 tabular-nums">{badge}</span>}
          </Link>
          {item.tabs && (
            <button
              onClick={() => setOpenItems((o) => ({ ...o, [item.href]: !expanded }))}
              aria-label={`${expanded ? "Collapse" : "Expand"} ${item.label}`}
              aria-expanded={expanded}
              className="h-7 w-7 mr-1 flex items-center justify-center rounded text-slate-500 hover:text-slate-50"
            >
              <ChevronRight className={`h-3.5 w-3.5 transition-transform ${expanded ? "rotate-90" : ""}`} />
            </button>
          )}
        </div>
        {item.tabs && expanded && (
          <div className="ml-[22px] mt-0.5 mb-1 border-l border-slate-800 pl-2 space-y-0.5">
            {item.tabs.map((t) => (
              <Link
                key={t.href}
                href={t.href}
                className={`block px-2 py-1 rounded text-[12.5px] transition-colors ${
                  t.href === pathname ? "text-slate-50 bg-slate-800/60" : "text-slate-500 hover:text-slate-50"
                }`}
              >
                {t.label}
              </Link>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="app-shell flex h-screen bg-[var(--background)] text-slate-100 antialiased overflow-hidden">
      <aside className="no-print w-64 flex flex-col border-r border-slate-800/80 bg-[var(--sidebar)] shrink-0 z-20">
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

        <nav className="flex-1 overflow-y-auto px-3 py-4 flex flex-col gap-4">
          {groups.map((g) => {
            const open = isAudit ? !!openGroups[g.key] : true;
            return (
              <div key={g.key} className={g.key === "admin" ? "mt-auto" : ""}>
                <button
                  onClick={() => setOpenGroups((o) => ({ ...o, [g.key]: !open }))}
                  aria-expanded={open}
                  className="w-full flex items-center justify-between px-3 mb-1 text-[11px] text-slate-500 hover:text-slate-300 transition-colors"
                >
                  <span>{g.label}</span>
                  <ChevronDown className={`h-3 w-3 transition-transform ${open ? "" : "-rotate-90"}`} />
                </button>
                {open && <div className="space-y-0.5">{g.items.map(navLink)}</div>}
              </div>
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

      <div className="app-body flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="no-print h-14 border-b border-slate-800/80 bg-[var(--sidebar)]/90 backdrop-blur px-8 flex items-center justify-between shrink-0 z-10">
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
            {isAudit && PRINTABLE.includes(pathname) && <ExportPdfButton />}
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

        <main className="app-main flex-1 overflow-y-auto bg-[var(--background)]">
          {allowed ? (
            <div className="mx-auto w-full max-w-[1600px] px-8 py-7">
              <div className="print-only print-header">
                {ov?.entity_name || "Konkan Marine Controls Ltd"} · {ov?.engagement_id || "ENG-2025-26"} · printed{" "}
                {new Date().toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short", year: "numeric" })}
              </div>
              {isAudit && <SectionTabs />}
              {apiError && (
                <div role="alert" className="no-print mb-5 flex items-start gap-2.5 rounded-md border border-rose-500/30 px-3.5 py-2.5 text-xs text-rose-300">
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-px" />
                  <span className="flex-1">{apiError}</span>
                  <button onClick={() => setApiError(null)} aria-label="Dismiss" className="text-rose-300/70 hover:text-rose-200">
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              )}
              {children}
            </div>
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
