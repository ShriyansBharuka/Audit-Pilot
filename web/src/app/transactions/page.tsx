"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { TransactionDetail, TransactionItem } from "@/lib/types";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Eye,
  FileCheck,
  FileText,
  Filter,
  Layers,
  RefreshCw,
  Search,
  Shield,
  Sparkles,
  Truck,
  X,
} from "lucide-react";

export default function TransactionsPage() {
  const [items, setItems] = useState<TransactionItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [band, setBand] = useState<string>("");
  const [detector, setDetector] = useState<string>("");
  const [page, setPage] = useState(0);
  const limit = 25;

  // Selected invoice for slide-over drawer
  const [selectedInvoice, setSelectedInvoice] = useState<string | null>(null);
  const [detail, setDetail] = useState<TransactionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadTransactions = () => {
    setLoading(true);
    api
      .getTransactions({
        limit,
        offset: page * limit,
        band: band || undefined,
        detector: detector || undefined,
        search: search || undefined,
      })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((err) => {
        console.error("Error loading transactions:", err);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadTransactions();
  }, [page, band, detector]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
    loadTransactions();
  };

  const openDrawer = (invoiceNo: string) => {
    setSelectedInvoice(invoiceNo);
    setDetailLoading(true);
    api
      .getTransactionDetail(invoiceNo)
      .then((res) => setDetail(res))
      .catch((err) => console.error(err))
      .finally(() => setDetailLoading(false));
  };

  const closeDrawer = () => {
    setSelectedInvoice(null);
    setDetail(null);
  };

  return (
    <div className="space-y-5">
      {/* Page Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            100% Population Explorer
            <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-mono font-normal">
              {total} Total Invoices
            </span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Browse, filter, and inspect every sales transaction against the system of record and statutory portals.
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="glass-panel p-4 rounded-xl border border-slate-800 flex flex-wrap items-center justify-between gap-3">
        <form onSubmit={handleSearchSubmit} className="flex-1 min-w-[260px] flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="h-4 w-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search by Invoice No (e.g. G2/0017/26), Customer, or GSTIN..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>
          <button
            type="submit"
            className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition"
          >
            Search
          </button>
        </form>

        <div className="flex items-center space-x-2 text-xs">
          {/* Risk Band Filter */}
          <div className="flex items-center space-x-1 bg-slate-900 border border-slate-700 rounded-lg p-1">
            <span className="text-[10px] text-slate-400 px-1 font-semibold uppercase">Band:</span>
            {["", "HIGH", "REVIEW", "LOW"].map((b) => (
              <button
                key={b}
                onClick={() => {
                  setBand(b);
                  setPage(0);
                }}
                className={`px-2 py-1 rounded text-xs transition ${
                  band === b
                    ? "bg-indigo-600 text-white font-medium"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {b || "All"}
              </button>
            ))}
          </div>

          {/* Detector Filter */}
          <select
            value={detector}
            onChange={(e) => {
              setDetector(e.target.value);
              setPage(0);
            }}
            className="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="">All Detectors</option>
            <option value="D0">D0: Register vs SoR</option>
            <option value="D1">D1: Related Parties</option>
            <option value="D3">D3: Cut-Off / Dispatch</option>
            <option value="D4">D4: Movement Void</option>
            <option value="D6">D6: Statutory IRN/EWB</option>
            <option value="D7">D7: Journal Entries</option>
            <option value="D9">D9: Credit Notes</option>
            <option value="D10">D10: Circular Loops</option>
            <option value="D13">D13: Sequence Breaks</option>
          </select>
        </div>
      </div>

      {/* Transactions Table */}
      <div className="glass-panel rounded-xl border border-slate-800 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/80 text-[11px] text-slate-400 uppercase font-mono border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Invoice No</th>
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4">Customer</th>
                <th className="py-3 px-4">Taxable Value</th>
                <th className="py-3 px-4">Total Amount</th>
                <th className="py-3 px-4">Risk Score</th>
                <th className="py-3 px-4">Exceptions</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-sans">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-400">
                    <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2 text-indigo-400" />
                    Loading population records...
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-400">
                    No transactions match the selected filters.
                  </td>
                </tr>
              ) : (
                items.map((row) => (
                  <tr
                    key={row.id}
                    className="hover:bg-slate-800/40 transition cursor-pointer"
                    onClick={() => openDrawer(row.invoice_no)}
                  >
                    <td className="py-3 px-4 font-mono font-medium text-white flex items-center gap-1.5">
                      <span>{row.invoice_no}</span>
                      {row.irn ? (
                        <span className="text-[9px] px-1 py-0.2 rounded bg-emerald-500/20 text-emerald-300 font-mono">
                          IRN
                        </span>
                      ) : (
                        <span className="text-[9px] px-1 py-0.2 rounded bg-rose-500/20 text-rose-300 font-mono">
                          NO IRN
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-400">{row.invoice_date}</td>
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-200 truncate max-w-[200px]">{row.party_name}</div>
                      <div className="text-[10px] text-slate-500 font-mono flex items-center gap-1">
                        <span>{row.buyer_gstin}</span>
                        {row.is_related_party && (
                          <span className="px-1 py-0.2 rounded bg-purple-500/20 text-purple-300 font-bold">
                            RP
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-200">{row.taxable_amount}</td>
                    <td className="py-3 px-4 font-mono font-semibold text-white">{row.total_amount}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold ${
                            row.risk_band === "HIGH"
                              ? "badge-high"
                              : row.risk_band === "REVIEW"
                              ? "badge-review"
                              : "badge-low"
                          }`}
                        >
                          {row.risk_score}/100
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex flex-wrap gap-1 max-w-[220px]">
                        {row.detector_hits.length === 0 ? (
                          <span className="text-[10px] text-slate-500">—</span>
                        ) : (
                          row.detector_hits.map((h, i) => (
                            <span
                              key={i}
                              className="text-[9px] px-1.5 py-0.2 rounded bg-amber-500/10 border border-amber-500/20 text-amber-300 font-mono"
                            >
                              {h.detector}:{h.code}
                            </span>
                          ))
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          openDrawer(row.invoice_no);
                        }}
                        className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs border border-slate-700 flex items-center gap-1 ml-auto"
                      >
                        <Eye className="h-3 w-3" />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination controls */}
        <div className="p-3 border-t border-slate-800 bg-slate-900/60 flex items-center justify-between text-xs text-slate-400">
          <div>
            Showing <span className="font-mono text-slate-200">{items.length}</span> of{" "}
            <span className="font-mono text-slate-200">{total}</span> records
          </div>
          <div className="flex items-center space-x-2">
            <button
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
              className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 text-xs border border-slate-700"
            >
              Previous
            </button>
            <span className="font-mono text-slate-300">Page {page + 1}</span>
            <button
              disabled={(page + 1) * limit >= total}
              onClick={() => setPage(page + 1)}
              className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 text-xs border border-slate-700"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* Slide-over Transaction Inspector Drawer */}
      {selectedInvoice && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex justify-end">
          <div className="w-full max-w-2xl bg-[#0b1120] border-l border-slate-800 h-full flex flex-col shadow-2xl animate-in slide-in-from-right duration-200">
            {/* Drawer Header */}
            <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-900/80">
              <div>
                <div className="text-xs font-mono text-indigo-400 flex items-center gap-2">
                  <span>TAX INVOICE DETAIL</span>
                  <span className="text-slate-500">·</span>
                  <span>{selectedInvoice}</span>
                </div>
                <h2 className="text-base font-bold text-white mt-1">
                  {detail?.party.name || "Loading counterparty..."}
                </h2>
              </div>
              <div className="flex items-center space-x-2">
                <Link
                  href={`/shap?invoice=${encodeURIComponent(selectedInvoice)}`}
                  className="px-2.5 py-1.5 rounded-lg bg-indigo-600/20 border border-indigo-500/40 text-indigo-300 text-xs font-medium flex items-center gap-1.5 hover:bg-indigo-600/30 transition"
                >
                  <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
                  <span>Explain with SHAP</span>
                </Link>
                <button
                  onClick={closeDrawer}
                  className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Drawer Body */}
            <div className="flex-1 overflow-y-auto p-5 space-y-5 text-xs text-slate-300">
              {detailLoading ? (
                <div className="py-12 text-center text-slate-400">
                  <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-indigo-400" />
                  Compiling complete documentary trail...
                </div>
              ) : !detail ? (
                <div className="py-8 text-center text-rose-400">Transaction details could not be loaded.</div>
              ) : (
                <>
                  {/* Top Metadata Box */}
                  <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-[10px] text-slate-500 uppercase font-mono">Invoice Date</div>
                      <div className="font-mono text-slate-200 mt-0.5">{detail.invoice.invoice_date}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-500 uppercase font-mono">Place of Supply</div>
                      <div className="font-mono text-slate-200 mt-0.5">{detail.invoice.place_of_supply}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-500 uppercase font-mono">Buyer GSTIN</div>
                      <div className="font-mono text-slate-200 mt-0.5">{detail.invoice.buyer_gstin}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-500 uppercase font-mono">Invoice Status</div>
                      <div className="font-mono text-emerald-400 mt-0.5">{detail.invoice.status}</div>
                    </div>
                    <div className="col-span-2">
                      <div className="text-[10px] text-slate-500 uppercase font-mono">Govt IRN (e-Invoice)</div>
                      <div className="font-mono text-[11px] text-indigo-300 mt-0.5 truncate bg-slate-950 p-1.5 rounded border border-slate-800">
                        {detail.invoice.irn || "IRN NOT GENERATED ON PORTAL"}
                      </div>
                    </div>
                  </div>

                  {/* Detector Exceptions */}
                  <div>
                    <h3 className="text-xs font-semibold text-white uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                      Detector Hits on this Document ({detail.risk_hits.length})
                    </h3>
                    {detail.risk_hits.length === 0 ? (
                      <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs">
                        No substantive exceptions detected. Valid commercial sale.
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {detail.risk_hits.map((h) => (
                          <div
                            key={h.id}
                            className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 space-y-1"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-mono font-bold text-amber-400 text-xs">
                                {h.detector}: {h.code}
                              </span>
                              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300">
                                Severity {h.severity}
                              </span>
                            </div>
                            <p className="text-xs text-slate-300 leading-relaxed">{h.reason}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Line Items Table */}
                  <div>
                    <h3 className="text-xs font-semibold text-white uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <FileText className="h-3.5 w-3.5 text-indigo-400" />
                      Invoice Line Items
                    </h3>
                    <div className="border border-slate-800 rounded-lg overflow-hidden bg-slate-900/60">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-950 text-[10px] text-slate-400 uppercase font-mono">
                          <tr>
                            <th className="p-2">Item</th>
                            <th className="p-2">HSN</th>
                            <th className="p-2 text-right">Qty</th>
                            <th className="p-2 text-right">Taxable</th>
                            <th className="p-2 text-right">Tax</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                          {detail.lines.map((l) => (
                            <tr key={l.line_no}>
                              <td className="p-2 font-medium text-slate-200">{l.item_name}</td>
                              <td className="p-2 font-mono text-slate-400">{l.hsn}</td>
                              <td className="p-2 text-right font-mono">{l.qty}</td>
                              <td className="p-2 text-right font-mono text-slate-200">{l.taxable_formatted}</td>
                              <td className="p-2 text-right font-mono text-slate-400">{l.total_tax_formatted}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Logistics: EWB and Lorry Receipts */}
                  <div>
                    <h3 className="text-xs font-semibold text-white uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <Truck className="h-3.5 w-3.5 text-emerald-400" />
                      Physical Movement Evidence (EWB & Lorry Receipt)
                    </h3>
                    <div className="grid grid-cols-2 gap-3">
                      {detail.ewaybills.length === 0 ? (
                        <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 col-span-2">
                          No e-way bill issued for this invoice.
                        </div>
                      ) : (
                        detail.ewaybills.map((ewb) => (
                          <div key={ewb.ewb_no} className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-1">
                            <div className="text-[10px] font-mono text-emerald-400">EWB: {ewb.ewb_no}</div>
                            <div className="text-slate-300 font-mono text-xs">Vehicle: {ewb.vehicle_no || "N/A"}</div>
                            <div className="text-slate-400 text-[10px]">Distance: {ewb.distance_km} km</div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
