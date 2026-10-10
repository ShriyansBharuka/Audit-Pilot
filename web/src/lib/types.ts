// TypeScript type definitions for AuditPilot AI

export type UserRole =
  | "engagement_partner"
  | "audit_staff"
  | "client_admin"
  | "accounts"
  | "warehouse"
  | "sales"
  | "orchestrator";

export interface UserSession {
  token: string;
  principal: string;
  role: UserRole;
  name: string;
  membership_no?: string;
  org_id?: string;
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
    band: "HIGH" | "REVIEW" | "LOW";
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
  id: string;
  about_doc_no: string;
  doc_type: string;
  requested_at: string;
  deadline?: string;
  status: "REQUESTED" | "RECEIVED" | "TESTED" | "EXPIRED";
  reason: string;
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

export interface ShapExplanation {
  invoice_no: string;
  invoice_date: string;
  party_name: string;
  risk_score: number;
  risk_band: "HIGH" | "REVIEW" | "LOW";
  base_value: number;
  shap_values: Record<string, number>;
  top_positive: { feature: string; value: number }[];
  top_negative: { feature: string; value: number }[];
  explanation_text: string;
  detector_hits_count: number;
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
