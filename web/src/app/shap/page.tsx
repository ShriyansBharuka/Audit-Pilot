"use client";

import React, { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { ShapExplanation } from "@/lib/types";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  BarChart2,
  CheckCircle2,
  HelpCircle,
  RefreshCw,
  Search,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

function ShapContent() {
  const searchParams = useSearchParams();
  const initialInvoice = searchParams.get("invoice") || "G2/0216/25";
  const [invoiceNo, setInvoiceNo] = useState(initialInvoice);
  const [data, setData] = useState<ShapExplanation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadShap = (inv: string) => {
    setLoading(true);
    setError(null);
    api
      .getShapExplanation(inv)
      .then((res) => setData(res))
      .catch((err) => {
        setError(err.message || "Failed to compute SHAP values");
        setData(null);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadShap(invoiceNo);
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (invoiceNo.trim()) {
      loadShap(invoiceNo.trim());
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            SHAP Explainability Studio
            <span className="text-xs px-2 py-0.5 rounded-full bg-sky-500/20 text-sky-300 font-mono font-normal">
              Feature Attribution (Shapley Values)
            </span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Mathematical decomposition of AuditGraph risk scores into exact positive and negative feature contributions.
          </p>
        </div>
      </div>

      {/* Invoice Selector */}
      <div className="glass-panel p-4 rounded-xl border border-slate-800 flex items-center justify-between gap-4">
        <form onSubmit={handleSearch} className="flex-1 max-w-lg flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="h-4 w-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Enter Invoice No (e.g. G2/0216/25, G2/0017/26)..."
              value={invoiceNo}
              onChange={(e) => setInvoiceNo(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-mono"
            />
          </div>
          <button
            type="submit"
            className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition"
          >
            Explain
          </button>
        </form>

        {/* Quick sample chips */}
        <div className="flex items-center space-x-2 text-xs">
          <span className="text-slate-500 text-[11px]">Quick Picks:</span>
          {["G2/0216/25", "G2/0017/26", "G11/0002/25"].map((pick) => (
            <button
              key={pick}
              onClick={() => {
                setInvoiceNo(pick);
                loadShap(pick);
              }}
              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-mono border border-slate-700"
            >
              {pick}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="py-20 text-center text-slate-400">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-indigo-400" />
          Computing exact Shapley additive feature attributions...
        </div>
      ) : error ? (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
          {error}
        </div>
      ) : !data ? null : (
        <div className="space-y-6">
          {/* Top Score Summary Banner */}
          <div className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 flex items-center justify-between">
            <div>
              <div className="text-[11px] font-mono text-indigo-400">
                {data.invoice_no} · {data.invoice_date} · {data.party_name}
              </div>
              <div className="text-lg font-bold text-white mt-1">
                AuditGraph Risk Score:{" "}
                <span className={data.risk_band === "HIGH" ? "text-rose-400" : "text-emerald-400"}>
                  {data.risk_score} / 100
                </span>
                <span className="text-xs font-normal text-slate-400 ml-2">({data.risk_band} BAND)</span>
              </div>
              <p className="text-xs text-slate-300 mt-1 max-w-2xl leading-relaxed">{data.explanation_text}</p>
            </div>
            <div className="text-right">
              <div className="text-[10px] text-slate-500 uppercase font-mono">Population Baseline</div>
              <div className="text-xl font-bold font-mono text-slate-400">{data.base_value.toFixed(1)} pts</div>
            </div>
          </div>

          {/* Waterfall Chart Representation */}
          <div className="glass-panel p-5 rounded-xl border border-slate-800 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                <BarChart2 className="h-4 w-4 text-indigo-400" />
                SHAP Feature Attribution Waterfall
              </h2>
              <span className="text-xs text-slate-400 font-mono">f(x) = E[f(x)] + ∑ φᵢ</span>
            </div>

            <div className="space-y-3 pt-2">
              {/* Baseline row */}
              <div className="flex items-center justify-between text-xs p-2 rounded bg-slate-900/40 border border-slate-800">
                <span className="font-mono text-slate-400">Base Expected Value (Population Mean)</span>
                <span className="font-mono text-slate-300 font-bold">{data.base_value.toFixed(1)} pts</span>
              </div>

              {/* Attribution Items */}
              {Object.entries(data.shap_values).map(([feature, val]) => {
                const isPositive = val > 0;
                const percentage = Math.min(Math.abs(val) * 2.5, 100);
                return (
                  <div key={feature} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-200 flex items-center gap-1.5">
                        {isPositive ? (
                          <ArrowUp className="h-3.5 w-3.5 text-rose-400 shrink-0" />
                        ) : (
                          <ArrowDown className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                        )}
                        <span>{feature}</span>
                      </span>
                      <span
                        className={`font-mono font-bold ${
                          isPositive ? "text-rose-400" : "text-emerald-400"
                        }`}
                      >
                        {isPositive ? `+${val.toFixed(1)}` : `${val.toFixed(1)}`} pts
                      </span>
                    </div>

                    {/* Attribution visual bar */}
                    <div className="h-2 w-full bg-slate-900 rounded-full overflow-hidden flex">
                      {isPositive ? (
                        <div
                          className="h-full bg-rose-500 rounded-full transition-all"
                          style={{ width: `${percentage}%` }}
                        />
                      ) : (
                        <div
                          className="h-full bg-emerald-500 rounded-full transition-all"
                          style={{ width: `${percentage}%` }}
                        />
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Final Result Row */}
              <div className="flex items-center justify-between text-xs p-3 rounded-lg bg-indigo-950/40 border border-indigo-500/30 font-bold">
                <span className="text-white">Final Calibrated Risk Score</span>
                <span className="font-mono text-indigo-300 text-sm">{data.risk_score} pts</span>
              </div>
            </div>
          </div>

          {/* Top positive vs negative drivers */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-rose-500/5 border border-rose-500/20 space-y-2">
              <h3 className="text-xs font-bold text-rose-400 uppercase tracking-wider flex items-center gap-1.5">
                <TrendingUp className="h-4 w-4" />
                Risk Escalation Factors (Positive Push)
              </h3>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Features that elevated this transaction's risk profile above the population baseline.
              </p>
              <div className="space-y-1 pt-1">
                {data.top_positive.map((p, i) => (
                  <div key={i} className="text-xs text-slate-300 flex justify-between">
                    <span>{p.feature}</span>
                    <span className="font-mono text-rose-400 font-bold">+{p.value.toFixed(1)}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20 space-y-2">
              <h3 className="text-xs font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                <TrendingDown className="h-4 w-4" />
                Risk Mitigating Factors (Negative Push)
              </h3>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Evidence and compliance signals that demonstrated authentic commercial reality.
              </p>
              <div className="space-y-1 pt-1">
                {data.top_negative.map((n, i) => (
                  <div key={i} className="text-xs text-slate-300 flex justify-between">
                    <span>{n.feature}</span>
                    <span className="font-mono text-emerald-400 font-bold">{n.value.toFixed(1)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ShapPage() {
  return (
    <React.Suspense fallback={<div className="py-20 text-center text-slate-400">Loading SHAP explainability studio...</div>}>
      <ShapContent />
    </React.Suspense>
  );
}
