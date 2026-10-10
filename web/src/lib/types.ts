// TypeScript type definitions for AuditPilot AI

export type UserRole =
  | "engagement_partner"
  | "audit_staff"
  | "client_admin"
  | "accounts"
  | "warehouse"
  | "sales"
  | "orchestrator";

export interface Membership {
  slug: string;
  name: string;
  role: UserRole;
}

export interface UserSession {
  token: string;
  principal: string;
  role: UserRole | null; // null: a web account with no role in the active organisation yet (onboarding)
  name: string;
  membership_no?: string;
  org_id?: string;
  account?: "token" | "supabase";
  email?: string;
  memberships?: Membership[];
}

export interface UploadResult {
  submission_id: string;
  sha256: string;
  rows_received?: number;
  status: string;
}

export interface Lookups {
  parties: { id: string; name: string; tags: string }[];
  items: { id: string; name: string; hsn: string }[];
  invoices: { invoice_no: string; party_id: string; invoice_date: string }[];
  accounts: { code: string; name: string }[];
}

export interface AuditOverview {
  has_engagement: boolean;
  engagement_id?: string;
  entity_name?: string;
  period_start?: string;
  period_end?: string;
  framework?: string;
  status?: string;
  materiality_paise?: number;
  materiality_formatted?: string;
  revenue_paise?: number;
  revenue_formatted?: string;
  invoices_count?: number;
  customers_count?: number;
  register_rows_count?: number;
  company_risk?: {
    band: "HIGH" | "MODERATE" | "REVIEW" | "LOW";
    exposure_paise: number;
    circular_paise: number;
    cycles_count: number;
  };
  detector_counts?: Record<string, number>;
  top_codes?: Record<string, number>;
  findings_counts?: Record<string, number>;
  samples_total?: number;
  samples_tested?: number;
  evidence_requests?: Record<string, number>;
  signed_by?: string;
  signed_at?: string;
  detectors?: DetectorMeta[];
}

export interface DetectorMeta {
  detector_id: string;
  name: string;
  standard: string;
  severity: number;
}

export interface TransactionItem {
  id: string;
  invoice_no: string;
  invoice_date: string;
  party_name: string;
  buyer_gstin: string;
  is_related_party: boolean;
  taxable_amount: string;
  taxable_paise: number;
  total_amount: string;
  total_paise: number;
  irn?: string;
  risk_score: number;
  risk_band: "HIGH" | "REVIEW" | "LOW";
  reasons: string[];
  detector_hits: {
    detector: string;
    code: string;
    severity: number;
  }[];
}

export interface TransactionDetail {
  invoice: {
    id: string;
    invoice_no: string;
    invoice_date: string;
    supplier_gstin: string;
    buyer_gstin: string;
    place_of_supply: string;
    irn?: string;
    status: string;
  };
  party: {
    id: string;
    name: string;
    pan?: string;
    gstin?: string;
    state_code?: string;
    tags?: string;
  };
  lines: {
    line_no: number;
    item_id: string;
    item_name: string;
    hsn: string;
    qty: number;
    rate_paise: number;
    taxable_formatted: string;
    total_tax_formatted: string;
  }[];
  movements: {
    lr_no: string;
    lr_date: string;
    vehicle_no: string;
    transporter_id: string;
    delivered_on?: string;
    received_by?: string;
  }[];
  ewaybills: {
    ewb_no: string;
    generated_at: string;
    valid_upto: string;
    vehicle_no: string;
    distance_km: number;
    status: string;
  }[];
  journals: {
    journal_no: number;
    journal_date: string;
    account_code: string;
    dr_paise: number;
    cr_paise: number;
  }[];
  risk_hits: {
    id: string;
    detector: string;
    code: string;
    severity: number;
    impact_paise: number;
    reason: string;
  }[];
  evidence: any[];
}

export interface CycleItem {
  nodes: string[];
  amount_paise: number;
  amount_formatted: string;
  invoices: string[];
  span_days: number;
  type: string;
}

export interface RiskGraphData {
  company: any;
  cycles: CycleItem[];
  graph: {
    nodes: {
      id: string;
      name: string;
      is_rp: boolean;
      group: string;
      state: string;
    }[];
    links: {
      source: string;
      target: string;
      amount: string;
      type: string;
    }[];
  };
}

export interface FindingItem {
  id: string;
  engagement_id: string;
  detector: string;
  code: string;
  category: string;
  title: string;
  explanation: string;
  standards: string;
  doc_refs: string[];
  gross_impact_paise: number;
  gross_impact_formatted: string;
  taxable_impact_paise: number;
  taxable_impact_formatted: string;
  affected_fy: string;
  confidence: "HIGH" | "MEDIUM" | "LOW";
  proposed_aje?: {
    account_code: string;
    party_id?: string;
    dr_paise?: number;
    cr_paise?: number;
  }[];
  status: "PROPOSED" | "CONFIRMED" | "REJECTED" | "MODIFIED";
  decision_note?: string;
}

export interface EvidenceRequestItem {
  // pbc.evidence_requests (vault 03 #27): sample_ref is opaque, the client never sees why a document was requested
  id: string;
  engagement_id: string;
  sample_ref: string;
  doc_kind: "INVOICE" | "EWAY_BILL" | "LR" | "POD" | "CREDIT_NOTE" | "RETURN_PROOF" | "CONTRACT" | "OTHER";
  about_doc_no: string | null;
  requested_at: string;
  due_on: string;
  status: "OPEN" | "RECEIVED" | "OVERDUE" | "WAIVED";
  submissions: {
    id: string;
    filename: string;
    mime: string;
    size: number;
    sha256: string;
    submitted_by: string;
    submitted_at: string;
  }[];
}

export interface ShapContribution {
  feature: string;
  kind: "hit" | "entity";
  detector: string | null;
  code: string | null;
  severity: number | null;
  value: number;
}

export interface ShapExplanation {
  invoice_id: string;
  invoice_no: string;
  invoice_date: string;
  party_id: string;
  party_name: string;
  risk_score: number;
  stored_risk_score: number;
  risk_band: "HIGH" | "REVIEW" | "LOW";
  A: number;
  E: number;
  base_value: number;
  contributions: ShapContribution[];
  entity_terms: { term: string; feature: string; value: number; term_value?: number }[];
  check: { sum_of_attributions: number; model_output: number; exact: boolean; note: string };
  method: string;
  shap_values: Record<string, number>;
  top_positive: { feature: string; value: number }[];
  top_negative: { feature: string; value: number }[];
  explanation_text: string;
  detector_hits_count: number;
}

export interface ShapSummary {
  invoices: number;
  min_risk: number;
  features: { feature: string; detector: string | null; mean_abs: number; sum_abs: number; invoices: number }[];
}

export interface N8nEvents {
  webhook_configured: boolean;
  events: { id: number; kind: string; at: string; notified_at: string | null }[];
  workflows: string[];
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  description?: string;
  created_at: string;
}

export interface Department {
  id: string;
  org_id: string;
  name: string;
  description?: string;
  parent_id?: string;
  created_at: string;
}

export interface OrgMembership {
  id: string;
  org_id: string;
  user_id: string;
  role: "owner" | "admin" | "auditor" | "viewer";
  user_email?: string;
  user_name?: string;
  created_at: string;
}

export interface Permission {
  id: string;
  org_id: string;
  user_id?: string;
  dept_id?: string;
  resource_type: string;
  resource_id?: string;
  can_view: boolean;
  can_edit: boolean;
  can_approve: boolean;
  can_export: boolean;
}

export interface Investigation {
  id: string;
  org_id: string;
  title: string;
  description: string;
  engagement_id?: string;
  finding_id?: string;
  transaction_id?: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  status: "OPEN" | "IN_REVIEW" | "PROPOSED" | "RESOLVED" | "CLOSED";
  resolution_summary?: string;
  created_at: string;
  created_by?: string;
}

export interface AuditReport {
  id: string;
  org_id: string;
  title: string;
  report_type: "workpaper" | "memo" | "trail" | "full_audit";
  engagement_id: string;
  published_at: string;
  shared_count?: number;
}

export interface ChartsData {
  period: { start: string; end: string };
  volume: {
    days: { date: string; count: number; total_paise: number; z: number; flagged: boolean; period_end_window: boolean }[];
    mean_paise: number;
    stdev_paise: number;
    z_flag: number;
  };
  benford: {
    n: number;
    chi2: number;
    critical: number;
    flagged: boolean;
    mad: number;
    digits: { digit: number; count: number; actual: number; expected: number }[];
  };
  risk: {
    histogram: { band: string; count: number }[];
    scatter: { invoice_no: string; total_paise: number; risk_score: number; category: string; code: string | null }[];
    scatter_total: number;
    scatter_shown: number;
  };
}

export interface StatutoryMemo {
  markdown: string;
  html: string;
  sha256: string;
  status: string;
  finding_ids: string[];
  aje_totals: { dr_paise: number; cr_paise: number };
  polished: boolean;
}

export interface TenantItem {
  slug: string;
  name: string;
  pan: string;
  gstin: string;
  fy_label: string;
  period_start: string;
  period_end: string;
  engagement_id: string;
  default: boolean;
  invoices_count: number;
  active?: boolean;
}

export interface NewTenantInput {
  name: string;
  pan: string;
  gstin: string;
  fy: string;
}

export interface TrailRow {
  seq: number;
  at: string;
  principal: string;
  role: string;
  transport: "STDIO" | "HTTP" | "UI" | "SYSTEM" | "CONNECTOR";
  tool: string;
  args: Record<string, unknown>;
  outcome: "OK" | "DENIED" | "ERROR";
  result_sha256: string | null;
  erp_seq: number | null;
  erp_hash: string | null;
  prev_hash: string;
  hash: string;
}

export interface TrailResponse {
  total: number;
  offset: number;
  limit: number;
  items: TrailRow[];
  verification: { valid: boolean; broken_at_seq: number | null; anchor_mismatch_at: number | null; head_seq: number; head_hash: string; anchors: number };
}

export interface CsvCheckRow {
  row: number;
  status: "MATCHED" | "AMOUNT_MISMATCH" | "DATE_MISMATCH" | "NOT_IN_BOOKS" | "NO_KEY" | "UNPARSED_AMOUNT";
  doc_type?: string;
  doc_id?: string;
  csv_paise?: number;
  books_paise?: number;
  difference_paise?: number;
  books_date?: string;
  client_data: { key?: string; amount?: string; date?: string };
}

export interface CsvCheckResult {
  sha256: string;
  filename: string;
  framework: string;
  path: string[];
  profile: {
    has_data: boolean;
    verdict: "HAS_DATA" | "NO_DATA";
    reason: "EMPTY_FILE" | "NOT_TEXT" | "HEADER_ONLY" | "BLANK_ROWS" | null;
    rows_total: number;
    data_rows: number;
    blank_rows: number;
    columns: string[];
    bytes: number;
  };
  verification: {
    key_column?: string | null;
    amount_column?: string | null;
    counts: Record<string, number>;
    rows: CsvCheckRow[];
    note?: string;
  };
  summary: { text: string; by: string; status: string; usd?: number; llm?: string };
}
