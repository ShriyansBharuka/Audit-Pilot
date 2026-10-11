"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ArrowLeft, KeyRound, LogOut, Mail, RefreshCw, Shield } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api, setActiveTenant } from "@/lib/api";

const MCP_URL = process.env.NEXT_PUBLIC_MCP_URL || "http://localhost:8000/mcp";
const input =
  "w-full h-10 px-3 rounded-md bg-slate-950 border border-slate-800 focus:border-indigo-500/60 text-sm text-slate-100 placeholder:text-slate-600 outline-none";
const primary =
  "w-full h-10 rounded-md bg-indigo-600 hover:bg-indigo-700 border border-indigo-500/40 disabled:opacity-50 text-white text-sm font-medium flex items-center justify-center gap-2";

function Card({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--background)] p-4">
      <div className="w-full max-w-sm space-y-6">
        <Link href="/" className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300">
          <ArrowLeft className="h-3.5 w-3.5" /> Home
        </Link>
        <div className="flex items-center gap-2.5">
          <span className="h-8 w-8 rounded-md bg-slate-800 flex items-center justify-center">
            <Shield className="h-4 w-4 text-indigo-400" />
          </span>
          <span className="font-medium text-slate-50">AuditPilot</span>
        </div>
        <div>
          <h1 className="text-xl font-medium text-slate-50">{title}</h1>
          {sub && <p className="mt-1 text-sm text-slate-400">{sub}</p>}
        </div>
        {children}
      </div>
    </div>
  );
}

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs text-slate-400">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-slate-500">{hint}</span>}
    </label>
  );
}

export function SignInScreen() {
  const { signInWithEmail, loginWithToken, identities } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const quick = identities.filter((i) => i.token && i.role !== "orchestrator"); // orchestrator = n8n over MCP only

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Sign in" sub="Welcome back.">
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          run(() => signInWithEmail(email.trim(), password));
        }}
      >
        <Field label="Email">
          <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={input} placeholder="you@firm.in" />
        </Field>
        <Field label="Password">
          <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} className={input} />
        </Field>
        <button type="submit" disabled={busy} className={primary}>
          <Mail className="h-4 w-4" /> {busy && !showToken ? "Signing in…" : "Sign in"}
        </button>
      </form>
      {error && <div role="alert" className="text-xs text-rose-300">{error}</div>}
      <p className="text-sm text-slate-400">
        New here?{" "}
        <Link href="/signup" className="text-indigo-400 hover:text-indigo-300">
          Create an account
        </Link>
      </p>

      <div className="border-t border-slate-800 pt-4 space-y-3">
        <button onClick={() => setShowToken((v) => !v)} aria-expanded={showToken} className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1.5">
          <KeyRound className="h-3.5 w-3.5" /> {showToken ? "Hide access token sign-in" : "Sign in with an access token"}
        </button>
        {showToken && (
          <div className="space-y-3">
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (token.trim()) run(() => loginWithToken(token.trim()));
              }}
            >
              <input type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder="aud_… / adm_… / ptn_…" className={`${input} font-mono`} />
              <button type="submit" disabled={busy || !token.trim()} className="h-10 px-3 rounded-md border border-slate-700 hover:bg-slate-800 text-sm text-slate-200 disabled:opacity-50">
                Go
              </button>
            </form>
            {quick.length > 0 && (
              <div className="grid grid-cols-2 gap-2">
                {quick.map((i) => (
                  <button key={i.principal} onClick={() => run(() => loginWithToken(i.token))} className="p-2 rounded-md border border-slate-800 hover:border-slate-600 text-left text-xs">
                    <div className="text-slate-200 truncate">{i.name}</div>
                    <div className="text-[11px] text-slate-500">{i.role.replace("_", " ")}</div>
                  </button>
                ))}
              </div>
            )}
            <p className="text-[11px] leading-relaxed text-slate-500">
              AI agents connect over MCP at <code className="text-slate-400">{MCP_URL}</code> with the same token.
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}

export function SignUpScreen() {
  const { signUpWithEmail } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  if (sent) {
    return (
      <Card title="Check your inbox" sub={`We sent a confirmation link to ${email}. Open it on this device, then you are signed in.`}>
        <Link href="/signin" className="text-sm text-indigo-400 hover:text-indigo-300">Back to sign in</Link>
      </Card>
    );
  }

  return (
    <Card title="Create your account" sub="Set up your firm's workspace in a minute.">
      <form
        className="space-y-3"
        onSubmit={async (e) => {
          e.preventDefault();
          if (password.length < 8) return setError("Use at least 8 characters for the password.");
          setBusy(true);
          setError(null);
          try {
            const r = await signUpWithEmail(email.trim(), password);
            if (r.confirm) setSent(true);
          } catch (ex) {
            setError(ex instanceof Error ? ex.message : "Sign-up failed");
          } finally {
            setBusy(false);
          }
        }}
      >
        <Field label="Work email">
          <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={input} placeholder="you@firm.in" />
        </Field>
        <Field label="Password" hint="At least 8 characters.">
          <input type="password" autoComplete="new-password" required value={password} onChange={(e) => setPassword(e.target.value)} className={input} />
        </Field>
        <button type="submit" disabled={busy} className={primary}>
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>
      {error && <div role="alert" className="text-xs text-rose-300">{error}</div>}
      <p className="text-sm text-slate-400">
        Already have an account?{" "}
        <Link href="/signin" className="text-indigo-400 hover:text-indigo-300">Sign in</Link>
      </p>
    </Card>
  );
}

/** A web account that is on an organisation where it holds no role: pick one of its own. */
export function OrgPickerScreen() {
  const { user, refresh, logout } = useAuth();
  return (
    <Card title="Choose an organisation" sub={`Signed in as ${user?.email}.`}>
      <div className="rounded-md border border-slate-800 divide-y divide-slate-800">
        {user?.memberships?.map((m) => (
          <button
            key={m.slug}
            onClick={async () => {
              setActiveTenant(m.slug);
              await refresh();
            }}
            className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-slate-800/50"
          >
            <span className="text-sm text-slate-100">{m.name}</span>
            <span className="text-xs text-slate-500">{m.role.replace("_", " ")}</span>
          </button>
        ))}
      </div>
      <button onClick={logout} className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200">
        <LogOut className="h-3.5 w-3.5" /> Sign out
      </button>
    </Card>
  );
}

/** A signed-in web account with no organisation yet: create one (you become its partner) or wait for an invite. */
export function OnboardingScreen() {
  const { user, refresh, logout } = useAuth();
  const [form, setForm] = useState({ name: "", pan: "", gstin: "", fy: "2025-26", membership_no: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  return (
    <Card title="Set up your organisation" sub="The company you are auditing this year. You will be its engagement partner.">
      <form
        className="space-y-3"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            const t = await api.createOrganisation({
              name: form.name.trim(),
              pan: form.pan.trim().toUpperCase(),
              gstin: form.gstin.trim().toUpperCase(),
              fy: form.fy.trim(),
              membership_no: form.membership_no.trim() || undefined,
            });
            setActiveTenant(t.slug);
            await refresh();
          } catch (ex) {
            setError(ex instanceof Error ? ex.message : "Could not create the organisation");
          } finally {
            setBusy(false);
          }
        }}
      >
        <Field label="Company name">
          <input required value={form.name} onChange={set("name")} className={input} placeholder="Velas Marine Pvt Ltd" />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="PAN">
            <input required value={form.pan} onChange={set("pan")} className={`${input} uppercase`} placeholder="AAFCS6120R" maxLength={10} />
          </Field>
          <Field label="Financial year">
            <input required value={form.fy} onChange={set("fy")} className={input} placeholder="2025-26" />
          </Field>
        </div>
        <Field label="GSTIN" hint="Must contain the PAN (characters 3 to 12).">
          <input required value={form.gstin} onChange={set("gstin")} className={`${input} uppercase`} placeholder="27AAFCS6120R1ZV" maxLength={15} />
        </Field>
        <Field label="Your ICAI membership no. (optional)">
          <input value={form.membership_no} onChange={set("membership_no")} className={input} />
        </Field>
        <button type="submit" disabled={busy} className={primary}>
          {busy ? "Setting up…" : "Create organisation"}
        </button>
      </form>
      {error && <div role="alert" className="text-xs text-rose-300">{error}</div>}
      <div className="border-t border-slate-800 pt-4 space-y-2 text-xs text-slate-400">
        <p>
          Joining a client or a firm instead? Ask its engagement partner to invite <span className="text-slate-200">{user?.email}</span>, then refresh.
        </p>
        <div className="flex gap-4">
          <button onClick={() => refresh()} className="flex items-center gap-1.5 hover:text-slate-200">
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </button>
          <button onClick={logout} className="flex items-center gap-1.5 hover:text-slate-200">
            <LogOut className="h-3.5 w-3.5" /> Sign out
          </button>
        </div>
      </div>
    </Card>
  );
}
