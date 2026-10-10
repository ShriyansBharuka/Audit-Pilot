"use client";

import React, { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { ShapExplanation, ShapSummary } from "@/lib/types";
import { BarChart2, CheckCircle2, Globe2, Info, RefreshCw, Search, XCircle } from "lucide-react";

function Waterfall({ data }: { data: ShapExplanation }) {
  // exact Shapley values from the real AuditGraph formula: 0 (clean baseline) + sum(phi) = risk score
  let running = data.base_value;
  return (
    <div className="space-y-2 pt-2">
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_4.5rem] gap-3 items-center text-xs text-slate-500 font-mono">
        <span>feature (player)</span>
        <span>0 ────────────── score 100</span>
        <span className="text-right">φ (pts)</span>
      </div>
      <Row label="Baseline: a clean invoice of a clean customer" from={0} to={data.base_value} value={data.base_value} muted />
      {data.contributions.map((c) => {
        const from = running;
        running += c.value;
        return (
          <React.Fragment key={c.feature}>
            <Row label={c.feature} from={from} to={running} value={c.value} />
            {c.kind === "entity" &&
              data.entity_terms.map((t) => (
                <Row key={t.term} label={`↳ ${t.feature}${t.term_value !== undefined ? ` = ${t.term_value}` : ""}`} sub value={t.value} />
              ))}
          </React.Fragment>
        );
      })}
      <div className="flex items-center justify-between text-xs p-3 rounded-lg bg-indigo-950/40 border border-indigo-500/30 font-bold mt-3">
        <span className="text-white">Risk score R = max(0.7·A + 0.3·E, hard-evidence floor 60)</span>
        <span className="font-mono text-indigo-300 text-sm">{data.risk_score.toFixed(1)} pts</span>
      </div>
    </div>
  );
}

function Row({ label, from = 0, to = 0, value, muted = false, sub = false }: {
  label: string; from?: number; to?: number; value: number; muted?: boolean; sub?: boolean;
}) {
  const lo = Math.max(0, Math.min(from, to));
  const width = Math.max(0.6, Math.abs(to - from));
  return (
    <div className={`grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_4.5rem] gap-3 items-center text-xs ${sub ? "opacity-75" : ""}`}>
      <span className={`truncate ${sub ? "pl-4 text-slate-400 text-xs" : "text-slate-200"}`} title={label}>
        {label}
      </span>
      <div className="h-2.5 w-full bg-slate-900 rounded-full relative overflow-hidden">
        {!sub && (
          <div
            className={`absolute h-full rounded-full ${muted ? "bg-slate-600" : value >= 0 ? "bg-rose-500" : "bg-emerald-500"}`}
            style={{ left: `${lo}%`, width: `${width}%` }}
          />
        )}
      </div>
      <span className={`font-mono text-right ${value >= 0 ? "text-rose-300" : "text-emerald-300"} ${sub ? "text-xs" : "font-bold"}`}>
        {value >= 0 ? "+" : ""}
        {value.toFixed(1)}
      </span>
    </div>
  );
}

function ShapContent() {
  const searchParams = useSearchParams();
  const [invoiceNo, setInvoiceNo] = useState(searchParams.get("invoice") || "");
  const [data, setData] = useState<ShapExplanation | null>(null);
  const [summary, setSummary] = useState<ShapSummary | null>(null);
  const [picks, setPicks] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadShap = (inv: string) => {
    setLoading(true);
    setError(null);
    api
      .getShapExplanation(inv)
      .then(setData)
      .catch((err) => {
        setError(err.message || "Failed to compute SHAP values");
        setData(null);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    api.getShapSummary(30).then(setSummary).catch(() => setSummary(null));
    api
      .getTransactions({ band: "HIGH", limit: 50 })
      .then((res) => {
        const top = [...res.items].sort((a: any, b: any) => (b.risk_score || 0) - (a.risk_score || 0)).slice(0, 4);
        const nos = top.map((t: any) => t.invoice_no);
        setPicks(nos);
        if (!invoiceNo && nos.length) {
          setInvoiceNo(nos[0]);
          loadShap(nos[0]);
        }
      })
      .catch(() => setPicks([]));
    if (invoiceNo) loadShap(invoiceNo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const maxImp = summary?.features.length ? summary.features[0].mean_abs : 1;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
          SHAP Explainability
          <span className="text-xs px-2 py-0.5 rounded-full bg-sky-500/20 text-sky-300 font-mono font-normal">exact Shapley values</span>
        </h1>
        <p className="text-xs text-slate-400 mt-1 max-w-3xl">
          Why does an invoice score what it scores? Each risk hit and the customer&apos;s entity risk are players of the real
          AuditGraph formula; their Shapley values are computed exactly (every coalition enumerated, nothing sampled or
          trained) and add up to the score.
        </p>
      </div>

      <div className="glass-panel p-4 rounded-xl border border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (invoiceNo.trim()) loadShap(invoiceNo.trim());
          }}
          className="flex-1 min-w-[260px] max-w-lg flex items-center gap-2"
        >
          <div className="relative flex-1">
            <Search className="h-4 w-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Invoice no or id (e.g. G2/4066/25, INV-005983)"
              value={invoiceNo}
              onChange={(e) => setInvoiceNo(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-mono"
            />
          </div>
          <button type="submit" className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium">
            Explain
          </button>
        </form>
        {picks.length > 0 && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-500 text-xs">Highest risk:</span>
            {picks.map((pick) => (
              <button
                key={pick}
                onClick={() => {
                  setInvoiceNo(pick);
                  loadShap(pick);
                }}
                className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono border border-slate-700"
              >
                {pick}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] gap-6">
        <div className="space-y-4">
          {loading ? (
            <div className="py-20 text-center text-slate-400">
              <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-indigo-400" />
              Computing exact Shapley values…
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">{error}</div>
          ) : !data ? (
            <div className="p-6 text-xs text-slate-400">Pick an invoice to explain.</div>
          ) : (
            <>
              <div className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
                <div className="text-xs font-mono text-indigo-400">
                  {data.invoice_no} · {data.invoice_date} · {data.party_id} {data.party_name ? `(${data.party_name})` : ""}
                </div>
                <div className="text-lg font-bold text-white">
                  Risk score{" "}
                  <span className={data.risk_band === "HIGH" ? "text-rose-400" : data.risk_band === "REVIEW" ? "text-amber-300" : "text-emerald-400"}>
                    {data.risk_score.toFixed(1)} / 100
                  </span>
                  <span className="text-xs font-normal text-slate-400 ml-2">
                    {data.risk_band} · A {data.A} · E {data.E}
                  </span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">{data.explanation_text}</p>
                <div
                  className={`inline-flex items-center gap-1.5 text-xs font-mono px-2 py-1 rounded ${
                    data.check.exact ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/30" : "bg-rose-500/10 text-rose-300 border border-rose-500/30"
                  }`}
                  title={data.check.note}
                >
                  {data.check.exact ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                  Σφ = {data.check.sum_of_attributions.toFixed(2)} = model output {data.check.model_output.toFixed(2)}
                  {Math.abs(data.stored_risk_score - data.risk_score) >= 0.05 && ` (stored, rounded: ${data.stored_risk_score})`}
                </div>
              </div>

              <div className="glass-panel p-5 rounded-xl border border-slate-800 space-y-3">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                    <BarChart2 className="h-4 w-4 text-indigo-400" />
                    Attribution waterfall
                  </h2>
                  <span className="text-xs text-slate-400 font-mono">R = φ₀ + Σ φᵢ</span>
                </div>
                {data.contributions.length ? (
                  <Waterfall data={data} />
                ) : (
                  <div className="text-xs text-slate-400">No risk hits and no customer risk: this invoice scores 0.</div>
                )}
                <div className="text-xs text-slate-500 flex gap-1.5 pt-2">
                  <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                  <span>
                    {data.method}. The baseline is a clean invoice, so every attribution is ≥ 0: in this model evidence of a
                    problem can only add risk; a clean check simply adds nothing.
                  </span>
                </div>
              </div>
            </>
          )}
        </div>

        <div className="glass-panel p-5 rounded-xl border border-slate-800 space-y-3 h-fit">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2 border-b border-slate-800 pb-3">
            <Globe2 className="h-4 w-4 text-sky-400" />
            What drives risk across the audit
          </h2>
          {!summary ? (
            <div className="text-xs text-slate-400">Loading…</div>
          ) : summary.invoices === 0 ? (
            <div className="text-xs text-slate-400">No invoice scores ≥ {summary.min_risk} yet.</div>
          ) : (
            <>
              <div className="text-xs text-slate-400">
                Mean |φ| per risk code over the {summary.invoices} invoices scored ≥ {summary.min_risk}.
              </div>
              <div className="space-y-2">
                {summary.features.slice(0, 12).map((f) => (
                  <div key={f.feature} className="space-y-0.5">
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-200 font-mono truncate">
                        {f.feature === "ENTITY_RISK_E" ? "customer entity risk E" : f.feature}
                        {f.detector && <span className="text-slate-500"> · {f.detector}</span>}
                      </span>
                      <span className="text-slate-400 font-mono">
                        {f.mean_abs.toFixed(1)} · {f.invoices} inv
                      </span>
                    </div>
                    <div className="h-1.5 bg-slate-900 rounded-full overflow-hidden">
                      <div className="h-full bg-sky-500 rounded-full" style={{ width: `${(100 * f.mean_abs) / maxImp}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ShapPage() {
  return (
    <React.Suspense fallback={<div className="py-20 text-center text-slate-400">Loading…</div>}>
      <ShapContent />
    </React.Suspense>
  );
}
