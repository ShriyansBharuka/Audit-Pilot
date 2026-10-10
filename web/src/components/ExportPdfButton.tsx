"use client";

import { Printer } from "lucide-react";

/** Browser print dialog ("Save as PDF"); globals.css @media print strips the app chrome. */
export function ExportPdfButton() {
  return (
    <button
      onClick={() => window.print()}
      className="no-print h-8 text-xs px-3 rounded-md hover:bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1.5 transition"
    >
      <Printer className="h-3.5 w-3.5 text-slate-400" />
      <span>Export PDF</span>
    </button>
  );
}
