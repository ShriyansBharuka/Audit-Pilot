import {
  AuditOverview,
  ChartsData,
  StatutoryMemo,
  N8nEvents,
  ShapSummary,
  CycleItem,
  EvidenceRequestItem,
  FindingItem,
  RiskGraphData,
  ShapExplanation,
  TransactionDetail,
  TransactionItem,
} from "./types";

// REST API (app/api_server.py) runs on 8001; 8000 is the MCP server for agents.
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("auditpilot_token") : null;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const data = await res.json();
      if (data.detail) errorDetail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      // fallback
    }
    throw new Error(errorDetail);
  }

  return res.json() as Promise<T>;
}

/** Download an authenticated file (the token goes in the header, never in a URL). */
export async function downloadWithToken(path: string, filename: string) {
  const token = typeof window !== "undefined" ? localStorage.getItem("auditpilot_token") : null;
  const res = await fetch(`${API_BASE}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new Error(`Download failed (${res.status})`);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const api = {
  // Identities & Auth
  getIdentities: () => request<any[]>("/api/identities"),
  tokenLogin: (token: string) =>
    request<any>("/api/auth/token-login", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

  // Audit Overview
  getOverview: () => request<AuditOverview>("/api/audit/overview"),

  // Transactions
  getTransactions: (params?: { limit?: number; offset?: number; band?: string; detector?: string; search?: string }) => {
    const qs = new URLSearchParams();
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    if (params?.band) qs.set("band", params.band);
    if (params?.detector) qs.set("detector", params.detector);
    if (params?.search) qs.set("search", params.search);
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<{ total: number; offset: number; limit: number; items: TransactionItem[] }>(`/api/audit/transactions${query}`);
  },

  getTransactionDetail: (invoiceNo: string) =>
    request<TransactionDetail>(`/api/audit/transactions/${encodeURIComponent(invoiceNo)}`),

  // Risk Graph
  getRiskGraph: () => request<RiskGraphData>("/api/audit/risk-graph"),

  // Findings
  getFindings: (status?: string) => {
    const qs = status ? `?status=${status}` : "";
    return request<FindingItem[]>(`/api/audit/findings${qs}`);
  },

  decideFinding: (findingId: string, decision: "CONFIRM" | "REJECT" | "MODIFY", note: string, proposedAje?: any[]) =>
    request<any>(`/api/audit/findings/${findingId}/decide`, {
      method: "POST",
      body: JSON.stringify({
        decision,
        note,
        proposed_aje: proposedAje,
      }),
    }),

  getSignoffBlockers: () => request<string[]>("/api/audit/signoff-blockers"),

  signOff: (statement: string, password: string) =>
    request<any>("/api/audit/sign-off", {
      method: "POST",
      body: JSON.stringify({ statement, password }),
    }),

  // Evidence
  getEvidenceRequests: (status?: string) => {
    const qs = status ? `?status=${status}` : "";
    return request<EvidenceRequestItem[]>(`/api/audit/evidence/requests${qs}`);
  },

  /** Client uploads a file for a request (multipart; the server computes the SHA-256 and stores it verbatim). */
  submitEvidence: async (requestId: string, file: File) => {
    const token = typeof window !== "undefined" ? localStorage.getItem("auditpilot_token") : null;
    const form = new FormData();
    form.append("request_id", requestId);
    form.append("file", file);
    const res = await fetch(`${API_BASE}/api/audit/evidence/submit`, {
      method: "POST",
      body: form,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      throw new Error(d.detail || `Upload failed (${res.status})`);
    }
    return res.json();
  },

  // SHAP
  getShapExplanation: (invoiceNo: string) =>
    request<ShapExplanation>(`/api/audit/shap/${encodeURIComponent(invoiceNo)}`),
  getShapSummary: (minRisk = 30) => request<ShapSummary>(`/api/audit/shap-summary?min_risk=${minRisk}`),

  // Analytics charts (EX-2)
  getAnalyticsCharts: () => request<ChartsData>("/api/audit/analytics/charts"),

  // Statutory memo (EX-3): PROPOSED / DRAFT; the partner decides in the findings flow
  draftStatutoryMemo: (polish = false) =>
    request<StatutoryMemo>("/api/audit/deliverables/statutory-memo", { method: "POST", body: JSON.stringify({ polish }) }),
  downloadStatutoryMemo: (format: "md" | "pdf") =>
    downloadWithToken(`/api/audit/deliverables/statutory-memo?format=${format}`, `statutory_memo.${format}`),

  // Audit Trail
  getAuditTrail: (limit = 50, offset = 0) =>
    request<{ total: number; offset: number; limit: number; items: any[] }>(`/api/audit/trail?limit=${limit}&offset=${offset}`),

  // Power BI: JSON "Web" feed URL + the zip package (4 CSVs in paise + measures.dax)
  getPowerBiDatasetUrl: () => `${API_BASE}/api/v1/powerbi/feed`,
  downloadPowerBiPackage: () => downloadWithToken("/api/integrations/powerbi/package", "AuditPilot_PowerBI.zip"),

  // n8n: the real event feed this app emits (workflows themselves run in n8n)
  getN8nEvents: (limit = 20) => request<N8nEvents>(`/api/integrations/n8n/events?limit=${limit}`),
};
