"use client";

import React, { useState } from "react";
import { api, downloadWithToken } from "@/lib/api";
import { Download } from "lucide-react";

type Dl = { label: string; run: () => Promise<void> };
type Item = { title: string; sub: string; files: Dl[] };

const ITEMS: Item[] = [
  {
    title: "Statutory audit memorandum",
    sub: "Draft memo with observations and the AJE summary",
    files: [
      { label: "PDF", run: () => api.downloadStatutoryMemo("pdf") },
      { label: "Markdown", run: () => api.downloadStatutoryMemo("md") },
    ],
  },
  {
    title: "Workpaper",
    sub: "Four-sheet revenue workpaper",
    files: [{ label: "Excel", run: () => downloadWithToken("/api/audit/deliverables/workpaper", "workpaper.xlsx") }],
  },
  {
    title: "Findings memo",
    sub: "Findings and proposed AJEs",
    files: [{ label: "JSON", run: () => downloadWithToken("/api/audit/deliverables/memo", "memo.json") }],
  },
  {
    title: "Report A: continuous",
    sub: "Running view of hits and cases",
    files: [
      { label: "HTML", run: () => downloadWithToken("/api/reports/continuous?format=html", "report_continuous.html") },
      { label: "Markdown", run: () => downloadWithToken("/api/reports/continuous?format=md", "report_continuous.md") },
    ],
  },
  {
    title: "Report B: year-end",
    sub: "Year-end cut-off and period-end view",
    files: [
      { label: "HTML", run: () => downloadWithToken("/api/reports/year-end?format=html", "report_year_end.html") },
      { label: "Markdown", run: () => downloadWithToken("/api/reports/year-end?format=md", "report_year_end.md") },
    ],
  },
  {
    title: "Power BI dataset",
    sub: "Star-schema CSVs and DAX measures",
    files: [{ label: "ZIP", run: () => api.downloadPowerBiPackage() }],
  },
];

export default function DownloadsPage() {
  const [busy, setBusy] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const go = async (title: string, f: Dl) => {
    const key = `${title}:${f.label}`;
    setBusy(key);
    setErrors((e) => ({ ...e, [title]: "" }));
    try {
      await f.run();
    } catch (ex) {
      const msg = ex instanceof Error ? ex.message : "Download failed";
      setErrors((e) => ({ ...e, [title]: /404|not found|NOT_FOUND/i.test(msg) ? "Nothing generated yet for this engagement." : msg }));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-medium text-slate-50 tracking-tight">Downloads</h1>
      <div className="rounded-lg border border-slate-800 bg-slate-900 divide-y divide-slate-800">
        {ITEMS.map((it) => (
          <div key={it.title} className="flex items-center justify-between gap-4 px-5 py-4">
            <div className="min-w-0">
              <div className="text-sm text-slate-50">{it.title}</div>
              <div className="text-xs text-slate-500 mt-0.5">{it.sub}</div>
              {errors[it.title] && <div className="text-xs text-rose-300 mt-1.5">{errors[it.title]}</div>}
            </div>
            <div className="flex gap-2 shrink-0">
              {it.files.map((f) => (
                <button
                  key={f.label}
                  onClick={() => go(it.title, f)}
                  disabled={busy !== null}
                  className="h-8 px-3 rounded-md border border-slate-700 hover:bg-slate-800 disabled:opacity-50 text-xs text-slate-300 flex items-center gap-1.5 transition"
                >
                  <Download className="h-3.5 w-3.5 text-slate-500" />
                  {busy === `${it.title}:${f.label}` ? "…" : f.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
