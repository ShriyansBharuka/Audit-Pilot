"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Lookups } from "@/lib/types";
import { CheckCircle2, Plus, Trash2 } from "lucide-react";

type Kind = "party" | "item" | "invoice" | "credit-note" | "journal";
// same role rules as the client MCP tools (app/tools_client.py)
const TABS: { kind: Kind; label: string; roles: string[] }[] = [
  { kind: "party", label: "Party", roles: ["sales", "client_admin"] },
  { kind: "item", label: "Item", roles: ["client_admin"] },
  { kind: "invoice", label: "Invoice", roles: ["accounts", "client_admin"] },
  { kind: "credit-note", label: "Credit note", roles: ["accounts", "client_admin"] },
  { kind: "journal", label: "Journal", roles: ["accounts", "client_admin"] },
];
const today = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
const input = "w-full h-9 px-2.5 rounded-md bg-slate-950 border border-slate-800 focus:border-indigo-500/60 text-sm text-slate-100 outline-none";
const label = "block space-y-1.5 text-xs text-slate-400";
const rupee = /^\d+(\.\d{1,2})?$/;

function Submit({ busy }: { busy: boolean }) {
  return (
    <button type="submit" disabled={busy} className="h-9 px-4 rounded-md bg-indigo-600 hover:bg-indigo-700 border border-indigo-500/40 disabled:opacity-50 text-sm font-medium text-white">
      {busy ? "Saving…" : "Save"}
    </button>
  );
}

export default function RecordsPage() {
  const { user } = useAuth();
  const tabs = TABS.filter((t) => user?.role && t.roles.includes(user.role));
  const [kind, setKind] = useState<Kind | null>(null);
  const [lk, setLk] = useState<Lookups | null>(null);
  const [busy, setBusy] = useState(false);
  const [ok, setOk] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const active = kind ?? tabs[0]?.kind ?? null;

  const loadLookups = () => api.getLookups().then(setLk).catch(() => setLk(null));
  useEffect(() => {
    loadLookups();
  }, []);

  const save = async (k: Kind, body: Record<string, unknown>, describe: (r: Record<string, unknown>) => string) => {
    setBusy(true);
    setOk(null);
    setError(null);
    try {
      const r = await api.createRecord(k, body);
      setOk(describe(r.result));
      loadLookups();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  };

  // ---- forms
  const [party, setParty] = useState({ name: "", tags: "CUSTOMER", gstin: "", pan: "", state_code: "", email: "", phone: "" });
  const [item, setItem] = useState({ name: "", hsn: "", uom: "NOS", gst: "18", list_rate: "" });
  const [inv, setInv] = useState({ party_id: "", series: "G2", invoice_date: today(), lines: [{ item_id: "", qty: "1", rate: "" }] });
  const [cn, setCn] = useState({ invoice_no: "", cn_date: today(), reason: "RATE_DIFF", taxable: "" });
  const [jv, setJv] = useState({ voucher_date: today(), narration: "", lines: [{ account_code: "", side: "debit", amount: "" }, { account_code: "", side: "credit", amount: "" }] });
  const dr = jv.lines.filter((l) => l.side === "debit").reduce((a, l) => a + Math.round(Number(l.amount || 0) * 100), 0);
  const cr = jv.lines.filter((l) => l.side === "credit").reduce((a, l) => a + Math.round(Number(l.amount || 0) * 100), 0);

  if (!tabs.length) return <p className="text-sm text-slate-400">Your role cannot enter records.</p>;

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-2xl font-medium text-slate-50 tracking-tight">Enter records</h1>
      <nav className="flex gap-6 border-b border-slate-800" aria-label="Record type">
        {tabs.map((t) => (
          <button
            key={t.kind}
            onClick={() => {
              setKind(t.kind);
              setOk(null);
              setError(null);
            }}
            aria-current={active === t.kind ? "page" : undefined}
            className={`pb-2.5 -mb-px text-[13px] border-b-2 ${active === t.kind ? "border-indigo-400 text-slate-50" : "border-transparent text-slate-400 hover:text-slate-50"}`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {ok && (
        <div className="flex items-center gap-2 rounded-md border border-indigo-500/30 px-3 py-2 text-xs text-indigo-300">
          <CheckCircle2 className="h-3.5 w-3.5" /> {ok}
        </div>
      )}
      {error && <div role="alert" className="rounded-md border border-rose-500/30 px-3 py-2 text-xs text-rose-300">{error}</div>}

      <div className="rounded-lg border border-slate-800 bg-slate-900 p-5">
        {active === "party" && (
          <form
            className="grid gap-4 sm:grid-cols-2"
            onSubmit={(e) => {
              e.preventDefault();
              save("party", { ...party, pan: party.pan.toUpperCase() || undefined, gstin: party.gstin.toUpperCase() || undefined }, (r) => `Saved ${r.id} · ${party.name}`);
            }}
          >
            <label className={`${label} sm:col-span-2`}>Name<input required className={input} value={party.name} onChange={(e) => setParty({ ...party, name: e.target.value })} /></label>
            <label className={label}>Type
              <select className={input} value={party.tags} onChange={(e) => setParty({ ...party, tags: e.target.value })}>
                {["CUSTOMER", "VENDOR", "TRANSPORTER", "DIRECTOR", "KMP", "RELATIVE"].map((t) => <option key={t}>{t}</option>)}
              </select>
            </label>
            <label className={label}>GSTIN<input className={`${input} uppercase`} maxLength={15} value={party.gstin} onChange={(e) => setParty({ ...party, gstin: e.target.value })} /></label>
            <label className={label}>PAN<input className={`${input} uppercase`} maxLength={10} value={party.pan} onChange={(e) => setParty({ ...party, pan: e.target.value })} /></label>
            <label className={label}>State code<input className={input} maxLength={2} placeholder="27" value={party.state_code} onChange={(e) => setParty({ ...party, state_code: e.target.value })} /></label>
            <label className={label}>Email<input type="email" className={input} value={party.email} onChange={(e) => setParty({ ...party, email: e.target.value })} /></label>
            <label className={label}>Phone<input className={input} value={party.phone} onChange={(e) => setParty({ ...party, phone: e.target.value })} /></label>
            <div className="sm:col-span-2"><Submit busy={busy} /></div>
          </form>
        )}

        {active === "item" && (
          <form
            className="grid gap-4 sm:grid-cols-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (item.list_rate && !rupee.test(item.list_rate)) return setError("Enter the list rate like 4500.00");
              save("item", { name: item.name, hsn: item.hsn, uom: item.uom, gst_rate_bp: Math.round(Number(item.gst) * 100), list_rate: item.list_rate || "0" }, (r) => `Saved ${r.id} · ${item.name}`);
            }}
          >
            <label className={`${label} sm:col-span-2`}>Name<input required className={input} placeholder="Ball valve DN25" value={item.name} onChange={(e) => setItem({ ...item, name: e.target.value })} /></label>
            <label className={label}>HSN / SAC<input required className={input} placeholder="8481" value={item.hsn} onChange={(e) => setItem({ ...item, hsn: e.target.value })} /></label>
            <label className={label}>Unit<input className={input} value={item.uom} onChange={(e) => setItem({ ...item, uom: e.target.value })} /></label>
            <label className={label}>GST rate (%)
              <select className={input} value={item.gst} onChange={(e) => setItem({ ...item, gst: e.target.value })}>
                {["0", "5", "12", "18", "28"].map((g) => <option key={g} value={g}>{g}%</option>)}
              </select>
            </label>
            <label className={label}>List rate (₹)<input className={input} inputMode="decimal" placeholder="4500.00" value={item.list_rate} onChange={(e) => setItem({ ...item, list_rate: e.target.value })} /></label>
            <div className="sm:col-span-2"><Submit busy={busy} /></div>
          </form>
        )}

        {active === "invoice" && (
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (inv.lines.some((l) => !l.item_id || !rupee.test(l.rate) || !(Number(l.qty) > 0))) return setError("Each line needs an item, a quantity and a rate like 45000.00");
              save("invoice", { party_id: inv.party_id, series: inv.series, invoice_date: inv.invoice_date, lines: inv.lines.map((l) => ({ item_id: l.item_id, qty: Number(l.qty), rate: l.rate })) }, (r) => `Issued ${r.invoice_no ?? r.id}`);
            }}
          >
            <div className="grid gap-4 sm:grid-cols-3">
              <label className={`${label} sm:col-span-3`}>Customer
                <select required className={input} value={inv.party_id} onChange={(e) => setInv({ ...inv, party_id: e.target.value })}>
                  <option value="">Choose…</option>
                  {lk?.parties.filter((p) => p.tags.includes("CUSTOMER")).map((p) => <option key={p.id} value={p.id}>{p.name} ({p.id})</option>)}
                </select>
              </label>
              <label className={label}>Series
                <select className={input} value={inv.series} onChange={(e) => setInv({ ...inv, series: e.target.value })}><option>G2</option><option>G11</option></select>
              </label>
              <label className={label}>Invoice date<input type="date" required className={input} value={inv.invoice_date} onChange={(e) => setInv({ ...inv, invoice_date: e.target.value })} /></label>
            </div>
            {inv.lines.map((l, i) => (
              <div key={i} className="grid grid-cols-[1fr_5rem_8rem_2rem] gap-2 items-end">
                <label className={label}>Item
                  <select required className={input} value={l.item_id} onChange={(e) => setInv({ ...inv, lines: inv.lines.map((x, j) => (j === i ? { ...x, item_id: e.target.value } : x)) })}>
                    <option value="">Choose…</option>
                    {lk?.items.map((it) => <option key={it.id} value={it.id}>{it.name}</option>)}
                  </select>
                </label>
                <label className={label}>Qty<input className={input} inputMode="numeric" value={l.qty} onChange={(e) => setInv({ ...inv, lines: inv.lines.map((x, j) => (j === i ? { ...x, qty: e.target.value } : x)) })} /></label>
                <label className={label}>Rate (₹)<input className={input} inputMode="decimal" placeholder="45000.00" value={l.rate} onChange={(e) => setInv({ ...inv, lines: inv.lines.map((x, j) => (j === i ? { ...x, rate: e.target.value } : x)) })} /></label>
                <button type="button" aria-label="Remove line" disabled={inv.lines.length === 1} onClick={() => setInv({ ...inv, lines: inv.lines.filter((_, j) => j !== i) })} className="h-9 flex items-center justify-center text-slate-500 hover:text-rose-300 disabled:opacity-30"><Trash2 className="h-4 w-4" /></button>
              </div>
            ))}
            <div className="flex items-center gap-3">
              <button type="button" onClick={() => setInv({ ...inv, lines: [...inv.lines, { item_id: "", qty: "1", rate: "" }] })} className="h-9 px-3 rounded-md border border-slate-700 hover:bg-slate-800 text-xs text-slate-300 flex items-center gap-1.5"><Plus className="h-3.5 w-3.5" /> Line</button>
              <Submit busy={busy} />
            </div>
          </form>
        )}

        {active === "credit-note" && (
          <form
            className="grid gap-4 sm:grid-cols-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (!rupee.test(cn.taxable)) return setError("Enter the taxable value like 25000.00");
              save("credit-note", { cn_date: cn.cn_date, reason: cn.reason, lines: [{ invoice_no: cn.invoice_no, taxable: cn.taxable }] }, (r) => `Issued ${r.cn_no ?? r.id}`);
            }}
          >
            <label className={`${label} sm:col-span-2`}>Against invoice
              <select required className={input} value={cn.invoice_no} onChange={(e) => setCn({ ...cn, invoice_no: e.target.value })}>
                <option value="">Choose…</option>
                {lk?.invoices.map((iv) => <option key={iv.invoice_no} value={iv.invoice_no}>{iv.invoice_no} · {iv.invoice_date}</option>)}
              </select>
            </label>
            <label className={label}>Date<input type="date" required className={input} value={cn.cn_date} onChange={(e) => setCn({ ...cn, cn_date: e.target.value })} /></label>
            <label className={label}>Reason
              <select className={input} value={cn.reason} onChange={(e) => setCn({ ...cn, reason: e.target.value })}>
                {["SALES_RETURN", "RATE_DIFF", "SCHEME_REBATE", "QUALITY", "OTHER"].map((r) => <option key={r}>{r}</option>)}
              </select>
            </label>
            <label className={label}>Taxable value (₹)<input required className={input} inputMode="decimal" placeholder="25000.00" value={cn.taxable} onChange={(e) => setCn({ ...cn, taxable: e.target.value })} /></label>
            <div className="sm:col-span-2"><Submit busy={busy} /></div>
          </form>
        )}

        {active === "journal" && (
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (jv.lines.some((l) => !l.account_code || !rupee.test(l.amount))) return setError("Each line needs an account and an amount like 250000.00");
              if (dr !== cr || dr === 0) return setError("Debits and credits must be equal and not zero.");
              save("journal", { voucher_date: jv.voucher_date, narration: jv.narration, lines: jv.lines.map((l) => ({ account_code: l.account_code, [l.side]: l.amount })) }, (r) => `Posted journal ${r.no ?? r.id ?? ""}`);
            }}
          >
            <div className="grid gap-4 sm:grid-cols-3">
              <label className={label}>Date<input type="date" required className={input} value={jv.voucher_date} onChange={(e) => setJv({ ...jv, voucher_date: e.target.value })} /></label>
              <label className={`${label} sm:col-span-2`}>Narration<input required className={input} value={jv.narration} onChange={(e) => setJv({ ...jv, narration: e.target.value })} /></label>
            </div>
            {jv.lines.map((l, i) => (
              <div key={i} className="grid grid-cols-[1fr_6rem_8rem_2rem] gap-2 items-end">
                <label className={label}>Account
                  <select required className={input} value={l.account_code} onChange={(e) => setJv({ ...jv, lines: jv.lines.map((x, j) => (j === i ? { ...x, account_code: e.target.value } : x)) })}>
                    <option value="">Choose…</option>
                    {lk?.accounts.map((a) => <option key={a.code} value={a.code}>{a.code} · {a.name}</option>)}
                  </select>
                </label>
                <label className={label}>Side
                  <select className={input} value={l.side} onChange={(e) => setJv({ ...jv, lines: jv.lines.map((x, j) => (j === i ? { ...x, side: e.target.value } : x)) })}><option value="debit">Debit</option><option value="credit">Credit</option></select>
                </label>
                <label className={label}>Amount (₹)<input className={input} inputMode="decimal" value={l.amount} onChange={(e) => setJv({ ...jv, lines: jv.lines.map((x, j) => (j === i ? { ...x, amount: e.target.value } : x)) })} /></label>
                <button type="button" aria-label="Remove line" disabled={jv.lines.length <= 2} onClick={() => setJv({ ...jv, lines: jv.lines.filter((_, j) => j !== i) })} className="h-9 flex items-center justify-center text-slate-500 hover:text-rose-300 disabled:opacity-30"><Trash2 className="h-4 w-4" /></button>
              </div>
            ))}
            <div className="flex items-center gap-3">
              <button type="button" onClick={() => setJv({ ...jv, lines: [...jv.lines, { account_code: "", side: "debit", amount: "" }] })} className="h-9 px-3 rounded-md border border-slate-700 hover:bg-slate-800 text-xs text-slate-300 flex items-center gap-1.5"><Plus className="h-3.5 w-3.5" /> Line</button>
              <span className={`text-xs tabular-nums ${dr === cr && dr > 0 ? "text-slate-400" : "text-amber-300"}`}>
                Dr ₹{(dr / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })} · Cr ₹{(cr / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </span>
              <Submit busy={busy} />
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
