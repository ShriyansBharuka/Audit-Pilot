"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { UserPlus } from "lucide-react";

const ROLES = [
  { value: "client_admin", label: "Client admin (uploads, all records)" },
  { value: "accounts", label: "Client accounts (invoices, journals)" },
  { value: "sales", label: "Client sales (parties)" },
  { value: "audit_staff", label: "Audit staff" },
];

/** Members and invites of the active organisation; shown to its engagement partner (web accounts). */
export function MembersPanel({ slug }: { slug: string }) {
  const [data, setData] = useState<{ members: { email: string; role: string }[]; invites: { email: string; role: string }[] } | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("client_admin");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.getMembers(slug).then(setData).catch((e) => setError(e.message));
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900">
      <div className="flex items-center justify-between px-5 h-12 border-b border-slate-800">
        <h2 className="text-sm font-medium text-slate-50">Members</h2>
        <span className="text-xs text-slate-500">Invites apply when that person signs in with the same e-mail</span>
      </div>
      <form
        className="flex flex-wrap gap-2 px-5 py-4 border-b border-slate-800"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            await api.invite(slug, email.trim(), role);
            setEmail("");
            load();
          } catch (ex) {
            setError(ex instanceof Error ? ex.message : "Could not invite");
          } finally {
            setBusy(false);
          }
        }}
      >
        <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="cfo@client.in"
          className="flex-1 min-w-[200px] h-9 px-3 rounded-md bg-slate-950 border border-slate-700 text-sm text-slate-50 placeholder-slate-600 outline-none focus:border-indigo-500" />
        <select value={role} onChange={(e) => setRole(e.target.value)} className="h-9 px-2 rounded-md bg-slate-950 border border-slate-700 text-sm text-slate-200">
          {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
        <button type="submit" disabled={busy} className="h-9 px-3 rounded-md bg-indigo-600 hover:bg-indigo-700 border border-indigo-500/40 text-white text-xs font-medium flex items-center gap-1.5 disabled:opacity-50">
          <UserPlus className="h-3.5 w-3.5" /> {busy ? "Inviting…" : "Invite"}
        </button>
        {error && <p role="alert" className="w-full text-xs text-rose-300">{error}</p>}
      </form>
      <table className="w-full text-sm">
        <tbody className="divide-y divide-slate-800">
          {data?.members.map((m) => (
            <tr key={m.email}><td className="px-5 py-2.5 text-slate-200">{m.email}</td><td className="px-5 py-2.5 text-xs text-slate-400">{m.role.replace("_", " ")}</td><td className="px-5 py-2.5 text-right text-xs text-slate-500">member</td></tr>
          ))}
          {data?.invites.map((m) => (
            <tr key={m.email}><td className="px-5 py-2.5 text-slate-400">{m.email}</td><td className="px-5 py-2.5 text-xs text-slate-500">{m.role.replace("_", " ")}</td><td className="px-5 py-2.5 text-right text-xs text-amber-300">invited</td></tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
