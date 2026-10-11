import {
  AuditOverview,
  ChartsData,
  CsvCheckResult,
  Lookups,
  Membership,
  NewTenantInput,
  UploadResult,
  TenantItem,
  TrailResponse,
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

// EX-4: the organisation (tenant) this browser is working on; the server checks the token may see it.
const TENANT_KEY = "auditpilot_tenant";
export const getActiveTenant = () => (typeof window !== "undefined" ? localStorage.getItem(TENANT_KEY) : null);
export const setActiveTenant = (slug: string | null) => {
  if (typeof window === "undefined") return;
  if (slug) localStorage.setItem(TENANT_KEY, slug);
  else localStorage.removeItem(TENANT_KEY);
};

/** Bearer token + X-Tenant (when one is picked). */
export function authHeaders(): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("auditpilot_token") : null;
  const tenant = getActiveTenant();
  return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(tenant ? { "X-Tenant": tenant } : {}) };
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...authHeaders(),
    ...(options.headers as Record<string, string>),
  };

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    // network failure, or a server crash: an unhandled 500 carries no CORS headers, so the browser
    // reports both as "Failed to fetch"
    throw reportApiError(`Can't reach the AuditPilot API at ${API_BASE} (or it hit an internal error on ${path.split("?")[0]}).`);
  }

  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const data = await res.json();
      if (data.detail) errorDetail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      // fallback
    }
    if (res.status >= 500) throw reportApiError(`Server error ${res.status} on ${path.split("?")[0]}: ${errorDetail}`);
    throw new Error(errorDetail);
  }

  return res.json() as Promise<T>;
}

/** Network and 5xx failures are shown once, app-wide (Navigation listens); 4xx stay with the page that asked. */
export const API_ERROR_EVENT = "auditpilot:api-error";
function reportApiError(message: string) {
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(API_ERROR_EVENT, { detail: message }));
  return new Error(message);
}

/** Download an authenticated file (the token goes in the header, never in a URL). */
export async function downloadWithToken(path: string, filename: string) {
  const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail || `Download failed (${res.status})`);
  }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export interface AssistantStatus {
  enabled: boolean;
  supported: boolean;
  mode: "tools" | "page_data" | null;
  reason: string;
}

export type AssistantEvent =
  | { type: "status"; mode: string; model: string }
  | { type: "delta"; text: string }
  | { type: "tool"; name: string; status: "running" | "done" }
  | { type: "proposal"; tool: string; args: Record<string, unknown>; why: string }
  | { type: "done"; tool_calls: number; usd: number }
  | { type: "error"; message: string };

/** ASSIST: stream one assistant turn (SSE over POST); onEvent gets each parsed event. */
export async function streamAssistant(
  body: { messages: { role: string; content: string }[]; page?: string; context?: unknown },
  onEvent: (e: AssistantEvent) => void,
  signal?: AbortSignal,
) {
  const res = await fetch(`${API_BASE}/api/assistant/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail || `Assistant unavailable (${res.status})`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i).trim();
      buf = buf.slice(i + 2);
      if (chunk.startsWith("data: ")) {
        try {
          onEvent(JSON.parse(chunk.slice(6)) as AssistantEvent);
        } catch {
          // ignore a malformed line
        }
      }
    }
  }
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
    const form = new FormData();
    form.append("request_id", requestId);
    form.append("file", file);
    const res = await fetch(`${API_BASE}/api/audit/evidence/submit`, {
      method: "POST",
      body: form,
      headers: authHeaders(),
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

  // Organisations (EX-4): each is its own data directory + engagement
  getTenants: () => request<{ items: TenantItem[] }>("/api/tenants"),
  createTenant: (body: NewTenantInput) => request<TenantItem>("/api/tenants", { method: "POST", body: JSON.stringify(body) }),

  // Web accounts (Supabase) + onboarding
  getMemberships: () => request<{ email: string; items: Membership[] }>("/api/auth/memberships"),
  createOrganisation: (body: NewTenantInput & { membership_no?: string }) =>
    request<TenantItem & { role: string }>("/api/onboarding/organization", { method: "POST", body: JSON.stringify(body) }),
  getMembers: (slug: string) =>
    request<{ members: { email: string; role: string }[]; invites: { email: string; role: string }[] }>(
      `/api/tenants/${encodeURIComponent(slug)}/members`,
    ),
  invite: (slug: string, email: string, role: string) =>
    request<{ email: string; role: string; status: string }>(`/api/tenants/${encodeURIComponent(slug)}/invites`, {
      method: "POST",
      body: JSON.stringify({ email, role }),
    }),

  // Agent tokens (MCP) for web accounts: shown once, stored hashed on the server
  getAgentTokens: () =>
    request<{ organisation: string; items: { id: string; role: string; label: string; hint: string; created_at: string }[] }>(
      "/api/agent-tokens",
    ),
  createAgentToken: (label: string) =>
    request<{ id: string; role: string; label: string; hint: string; token: string; organisation: string }>("/api/agent-tokens", {
      method: "POST",
      body: JSON.stringify({ label }),
    }),
  revokeAgentToken: (id: string) => request<{ id: string }>(`/api/agent-tokens/${encodeURIComponent(id)}`, { method: "DELETE" }),

  // Client input: register / related-party uploads (stored byte-for-byte, server SHA-256) and manual ERP entry
  uploadClientFile: async (kind: "sales-register" | "related-parties", file: File) => {
    const form = new FormData();
    form.append("file", file);
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/client/${kind}`, { method: "POST", body: form, headers: authHeaders() });
    } catch {
      throw reportApiError(`Can't reach the AuditPilot API at ${API_BASE} (or it hit an internal error on the upload).`);
    }
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      throw new Error(d.detail || `Upload failed (${res.status})`);
    }
    return (await res.json()) as UploadResult;
  },
  getLookups: () => request<Lookups>("/api/client/lookups"),
  createRecord: (kind: "party" | "item" | "invoice" | "credit-note" | "journal", body: Record<string, unknown>) =>
    request<{ result: Record<string, unknown>; next_steps: unknown[] }>(`/api/client/records/${kind}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // ASSIST: in-app assistant (Agents SDK over MCP with the caller's own token)
  getAssistantStatus: () => request<AssistantStatus>("/api/assistant/status"),
  runAssistantAction: (tool: string, args: Record<string, unknown>) =>
    request<{ ok: boolean; text: string }>("/api/assistant/execute", { method: "POST", body: JSON.stringify({ tool, args }) }),

  // CSV verification agent (LangGraph): does the file hold data, and does it match the books?
  verifyCsv: async (file: File, ai = false) => {
    const form = new FormData();
    form.append("file", file);
    form.append("ai", String(ai));
    const res = await fetch(`${API_BASE}/api/agents/csv-verify`, { method: "POST", body: form, headers: authHeaders() });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      throw new Error(d.detail || `Check failed (${res.status})`);
    }
    return (await res.json()) as CsvCheckResult;
  },

  // Analytics charts (EX-2)
  getAnalyticsCharts: () => request<ChartsData>("/api/audit/analytics/charts"),

  // Statutory memo (EX-3): PROPOSED / DRAFT; the partner decides in the findings flow
  draftStatutoryMemo: (polish = false) =>
    request<StatutoryMemo>("/api/audit/deliverables/statutory-memo", { method: "POST", body: JSON.stringify({ polish }) }),
  downloadStatutoryMemo: (format: "md" | "pdf") =>
    downloadWithToken(`/api/audit/deliverables/statutory-memo?format=${format}`, `statutory_memo.${format}`),

  // Audit Trail
  getAuditTrail: (limit = 50, offset = 0) => request<TrailResponse>(`/api/audit/trail?limit=${limit}&offset=${offset}`),

  // Power BI: JSON "Web" feed URL + the zip package (4 CSVs in paise + measures.dax)
  getPowerBiDatasetUrl: () => `${API_BASE}/api/v1/powerbi/feed`,
  downloadPowerBiPackage: () => downloadWithToken("/api/integrations/powerbi/package", "AuditPilot_PowerBI.zip"),

  // n8n: the real event feed this app emits (workflows themselves run in n8n)
  getN8nEvents: (limit = 20) => request<N8nEvents>(`/api/integrations/n8n/events?limit=${limit}`),
};
