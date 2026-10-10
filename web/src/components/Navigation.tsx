"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  Activity,
  AlertTriangle,
  Award,
  BarChart3,
  Building,
  CheckCircle2,
  ChevronDown,
  FileText,
  FolderOpen,
  GitCommit,
  Layers,
  LogOut,
  Network,
  Share2,
  Shield,
  Sliders,
  Sparkles,
  UserCheck,
  Users,
  Zap,
} from "lucide-react";

export function Navigation({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, switchRole, identities } = useAuth();
  const [roleDropdownOpen, setRoleDropdownOpen] = useState(false);
  const [judgeCardOpen, setJudgeCardOpen] = useState(false);

  const navItems = [
    { href: "/", label: "Audit Overview", icon: BarChart3, badge: "303 Invoices" },
    { href: "/transactions", label: "100% Population", icon: Layers, badge: "D0–D14" },
    { href: "/network", label: "Risk & Circular Loops", icon: Network, badge: "4 Cycles" },
    { href: "/shap", label: "SHAP Explainability", icon: Sparkles, badge: "Attribution" },
    { href: "/findings", label: "Findings & Sign-Off", icon: Award, badge: "31 AJEs" },
    { href: "/evidence", label: "Evidence & PBC Portal", icon: FolderOpen, badge: "118 Req" },
    { href: "/orgs", label: "Organizations & Depts", icon: Building },
    { href: "/permissions", label: "Granular RBAC", icon: Sliders },
    { href: "/sharing", label: "Report Sharing", icon: Share2 },
    { href: "/investigations", label: "Fraud Hub", icon: AlertTriangle, badge: "Cross-Org" },
    { href: "/integrations", label: "Integrations & Power BI", icon: Zap },
    { href: "/trail", label: "Hash-Chained Trail", icon: GitCommit },
  ];

  return (
    <div className="flex h-screen bg-[#070b14] text-slate-100 antialiased overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 flex flex-col border-r border-slate-800/80 bg-[#0b1120] shrink-0 z-20">
        {/* Brand */}
        <div className="p-4 border-b border-slate-800/80 flex items-center justify-between">
          <Link href="/" className="flex items-center space-x-2.5">
            <div className="h-8 w-8 rounded-lg bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400 font-bold shadow-lg shadow-indigo-500/10">
              <Shield className="h-4 w-4 text-indigo-400" />
            </div>
            <div>
              <div className="font-semibold text-sm tracking-tight text-white flex items-center gap-1.5">
                AuditPilot <span className="text-xs px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 font-mono">AI</span>
              </div>
              <div className="text-[10px] text-slate-400 font-mono">Statutory Revenue Audit</div>
            </div>
          </Link>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
          <div className="text-[10px] font-semibold tracking-wider text-slate-500 uppercase px-2 mb-2">
            Audit Workspace
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center justify-between px-2.5 py-2 rounded-md text-xs font-medium transition-colors ${
                  isActive
                    ? "bg-indigo-600/15 text-indigo-400 border border-indigo-500/30"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}
              >
                <div className="flex items-center space-x-2.5">
                  <Icon className={`h-4 w-4 ${isActive ? "text-indigo-400" : "text-slate-400"}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                      isActive ? "bg-indigo-500/30 text-indigo-200" : "bg-slate-800 text-slate-400"
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Entity status footer */}
        <div className="p-3 border-t border-slate-800/80 bg-slate-900/40">
          <div className="text-[11px] font-medium text-slate-300 truncate">Konkan Marine Controls Ltd</div>
          <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1">
            <span className="flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
              FY 2025-26 (Ind AS)
            </span>
            <span className="font-mono text-emerald-400">ENG-2025-26</span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Navbar */}
        <header className="h-14 border-b border-slate-800/80 bg-[#0b1120]/90 backdrop-blur px-6 flex items-center justify-between shrink-0 z-10">
          {/* Left status chips */}
          <div className="flex items-center space-x-3 text-xs">
            <span className="px-2.5 py-1 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-medium flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5" />
              100% Population Tested (303 Invoices)
            </span>
            <span className="px-2.5 py-1 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400 font-mono text-[11px]">
              OM: ₹42.50 L · PM: ₹31.87 L
            </span>
          </div>

          {/* Right controls */}
          <div className="flex items-center space-x-3">
            {/* Quick Judge Card Modal Trigger */}
            <button
              onClick={() => setJudgeCardOpen(true)}
              className="text-xs px-2.5 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 flex items-center gap-1.5 transition"
            >
              <UserCheck className="h-3.5 w-3.5 text-indigo-400" />
              <span>Judge Card Credentials</span>
            </button>

            {/* Role Switcher */}
            <div className="relative">
              <button
                onClick={() => setRoleDropdownOpen(!roleDropdownOpen)}
                className="flex items-center space-x-2 bg-slate-800/80 hover:bg-slate-800 border border-slate-700 px-3 py-1.5 rounded-md text-xs font-medium text-slate-200 transition"
              >
                <div className="h-5 w-5 rounded-full bg-indigo-500/20 text-indigo-300 flex items-center justify-center font-bold text-[10px]">
                  {user?.role === "engagement_partner" ? "EP" : user?.role?.slice(0, 2).toUpperCase() || "ID"}
                </div>
                <div className="text-left">
                  <div className="leading-tight font-medium">{user?.name || "User"}</div>
                  <div className="text-[10px] text-slate-400 leading-tight">
                    {user?.role?.replace("_", " ")}
                  </div>
                </div>
                <ChevronDown className="h-3 w-3 text-slate-400 ml-1" />
              </button>

              {roleDropdownOpen && (
                <div className="absolute right-0 mt-2 w-56 rounded-md bg-slate-900 border border-slate-700 shadow-xl py-1 z-50 text-xs">
                  <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500 border-b border-slate-800">
                    Switch Active Persona
                  </div>
                  {identities.map((id) => (
                    <button
                      key={id.token}
                      onClick={() => {
                        switchRole(id.role);
                        setRoleDropdownOpen(false);
                      }}
                      className={`w-full text-left px-3 py-2 flex items-center justify-between hover:bg-slate-800 transition ${
                        user?.token === id.token ? "bg-indigo-600/10 text-indigo-400 font-semibold" : "text-slate-300"
                      }`}
                    >
                      <div>
                        <div>{id.name}</div>
                        <div className="text-[10px] text-slate-400">{id.role.replace("_", " ")}</div>
                      </div>
                      {user?.token === id.token && <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400" />}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Scrollable Page Body */}
        <main className="flex-1 overflow-y-auto p-6 bg-[#070b14]">
          {children}
        </main>
      </div>

      {/* Judge Card Credential Modal */}
      {judgeCardOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-2xl w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-indigo-400" />
                <h3 className="font-semibold text-white text-sm">AuditPilot AI — Official Judge Card Tokens</h3>
              </div>
              <button
                onClick={() => setJudgeCardOpen(false)}
                className="text-slate-400 hover:text-white text-xs px-2 py-1 rounded bg-slate-800"
              >
                ✕ Close
              </button>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Every business and audit action in AuditPilot AI is cryptographic and token-bound. Click any identity below to immediately switch context and test granular permissions:
            </p>

            <div className="grid grid-cols-2 gap-2 text-xs">
              {identities.map((id) => (
                <div
                  key={id.token}
                  onClick={() => {
                    switchRole(id.role);
                    setJudgeCardOpen(false);
                  }}
                  className={`p-3 rounded-lg border cursor-pointer transition ${
                    user?.token === id.token
                      ? "border-indigo-500 bg-indigo-500/10"
                      : "border-slate-800 bg-slate-800/40 hover:border-slate-700 hover:bg-slate-800"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-200">{id.name}</span>
                    <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                      {id.role}
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-400 mt-1 font-mono truncate">{id.principal}</div>
                  <div className="text-[9px] text-slate-500 mt-1 font-mono truncate">{id.token}</div>
                </div>
              ))}
            </div>

            <div className="border-t border-slate-800 pt-3 text-[11px] text-slate-400 flex justify-between items-center">
              <span>MCP Protocol URL: <code className="text-indigo-400 font-mono">http://localhost:8000/mcp</code></span>
              <span className="text-emerald-400">Token-bound RBAC active</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
