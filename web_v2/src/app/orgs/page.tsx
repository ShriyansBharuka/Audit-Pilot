"use client";

import React, { useEffect, useState } from "react";
import { api, getActiveTenant, setActiveTenant } from "@/lib/api";
import { TenantItem } from "@/lib/types";
import { AlertOctagon, Plus, RefreshCw } from "lucide-react";

const EMPTY = { name: "", pan: "", gstin: "", fy: "2026-27" };

export default function OrgsPage() {
  const [orgs, setOrgs] = useState<TenantItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [active, setActive] = useState("konkan");

  const load = () => {
    setActive(getActiveTenant() || "konkan");
    setLoading(true);
    api
      .getTenants()
      .then((r) => {
        setOrgs(r.items);
        setError(null);
      })
      .catch((e) => setError(e.message || "Failed to load organisations"))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const openOrg = (slug: string) => {
    setActiveTenant(slug === "konkan" ? null : slug);
    window.location.href = "/"; // every page reloads against the chosen organisation
  };

  const create = (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFormError(null);
    api
      .createTenant({ ...form, pan: form.pan.toUpperCase(), gstin: form.gstin.toUpperCase() })
      .then(() => {
        setOpen(false);
        setForm(EMPTY);
        load();
      })
      .catch((err) => setFormError(err.message || "Could not create the organisation"))
      .finally(() => setSaving(false));
  };

  const field = (key: keyof typeof EMPTY, label: string, placeholder: string) => (
    <label className="block space-y-1">
      <span className="text-xs text-slate-400">{label}</span>
      <input
        required
        value={form[key]}
        placeholder={placeholder}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        className="w-full h-9 px-3 rounded-md bg-slate-950 border border-slate-700 text-sm text-slate-50 placeholder-slate-600 focus:outline-none focus:border-indigo-500"
      />
    </label>
  );

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-medium text-slate-50 tracking-tight">Organizations</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            disabled={loading}
            className="h-8 px-3 rounded-md text-slate-300 text-xs border border-slate-700 hover:bg-slate-800 flex items-center gap-1.5 transition"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button
            onClick={() => setOpen(true)}
            className="h-8 px-3 rounded-md bg-indigo-600 hover:bg-indigo-700 border border-indigo-500/40 text-white text-xs font-medium flex items-center gap-1.5 transition"
          >
            <Plus className="h-3.5 w-3.5" />
            New organization
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-md border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <AlertOctagon className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <section className="rounded-lg border border-slate-800 bg-slate-900">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-slate-500 border-b border-slate-800">
              <th className="text-left font-normal pl-5 py-3">Name</th>
              <th className="text-left font-normal py-3 hidden md:table-cell">PAN</th>
              <th className="text-left font-normal py-3 hidden lg:table-cell">GSTIN</th>
              <th className="text-left font-normal py-3">FY</th>
              <th className="text-right font-normal py-3">Invoices</th>
              <th className="pr-5 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {orgs.map((o) => {
              const isActive = o.slug === active;
              return (
                <tr key={o.slug} className="hover:bg-slate-800/40">
                  <td className="pl-5 py-3">
                    <div className="text-slate-100">{o.name}</div>
                    <div className="text-xs text-slate-500 font-mono">{o.engagement_id}</div>
                  </td>
                  <td className="py-3 text-xs text-slate-400 font-mono hidden md:table-cell">{o.pan}</td>
                  <td className="py-3 text-xs text-slate-400 font-mono hidden lg:table-cell">{o.gstin}</td>
                  <td className="py-3 text-xs text-slate-400">{o.fy_label}</td>
                  <td className="py-3 text-right tabular-nums text-slate-200">{o.invoices_count.toLocaleString("en-IN")}</td>
                  <td className="pr-5 py-3 text-right">
                    {isActive ? (
                      <span className="text-xs text-indigo-400">Active</span>
                    ) : (
                      <button
                        onClick={() => openOrg(o.slug)}
                        className="h-7 px-2.5 rounded-md text-xs text-slate-300 border border-slate-700 hover:bg-slate-800 transition"
                      >
                        Open
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
            {!loading && orgs.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-xs text-slate-500">
                  No organizations visible to you.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      {open && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
          <form onSubmit={create} className="bg-slate-900 border border-slate-700 rounded-lg max-w-md w-full p-6 space-y-4">
            <h3 className="text-sm font-medium text-slate-50">New organization</h3>
            {field("name", "Name", "Deccan Valves Pvt Ltd")}
            {field("pan", "PAN", "AAECD1234F")}
            {field("gstin", "GSTIN", "27AAECD1234F1Z…")}
            {field("fy", "Financial year", "2026-27")}
            {formError && <div className="text-xs text-rose-300">{formError}</div>}
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="h-8 px-3 rounded-md text-xs text-slate-300 border border-slate-700 hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="h-8 px-3 rounded-md bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium disabled:opacity-60"
              >
                {saving ? "Creating…" : "Create"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
