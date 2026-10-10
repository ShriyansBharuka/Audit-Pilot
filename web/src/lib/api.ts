import {
  AuditOverview,
  CycleItem,
  EvidenceRequestItem,
  FindingItem,
  RiskGraphData,
  ShapExplanation,
  TransactionDetail,
  TransactionItem,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

  // SHAP
  getShapExplanation: (invoiceNo: string) =>
    request<ShapExplanation>(`/api/audit/shap/${encodeURIComponent(invoiceNo)}`),

  // Audit Trail
  getAuditTrail: (limit = 50, offset = 0) =>
    request<{ total: number; offset: number; limit: number; items: any[] }>(`/api/audit/trail?limit=${limit}&offset=${offset}`),

  // Power BI Export
  getPowerBiDatasetUrl: () => `${API_BASE}/api/integrations/powerbi`,

  // n8n Trigger
  triggerN8nWorkflow: (workflowName: string, action: string, payload?: any) =>
    request<any>("/api/integrations/n8n/trigger", {
      method: "POST",
      body: JSON.stringify({
        workflow_name: workflowName,
        action,
        payload,
      }),
    }),
};
