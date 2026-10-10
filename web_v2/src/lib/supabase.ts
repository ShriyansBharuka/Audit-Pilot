import { createClient } from "@supabase/supabase-js";
import {
  AuditReport,
  Department,
  Investigation,
  Organization,
  OrgMembership,
  Permission,
} from "./types";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://ysimtmaxmdkubvkbpyes.supabase.co";
const SUPABASE_ANON_KEY =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlzaW10bWF4bWRrdWJ2a2JweWVzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE2MzQyNzMsImV4cCI6MjEwNzIxMDI3M30.Km5TYirgZOX01ZSKE6ifyb8toD5EaWI0MXtHhNApWD0";

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

export const supabaseService = {
  // Organizations
  async getOrganizations(): Promise<Organization[]> {
    const { data, error } = await supabase.from("organizations").select("*").order("name");
    if (error) {
      console.warn("Supabase fetch orgs error:", error.message);
      return [];
    }
    return data || [];
  },

  async createOrganization(name: string, description?: string): Promise<Organization | null> {
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    const { data, error } = await supabase
      .from("organizations")
      .insert([{ name, slug, description }])
      .select()
      .single();

    if (error) {
      throw new Error(error.message);
    }
    return data;
  },

  // Departments
  async getDepartments(orgId: string): Promise<Department[]> {
    const { data, error } = await supabase
      .from("departments")
      .select("*")
      .eq("org_id", orgId)
      .order("name");
    if (error) return [];
    return data || [];
  },

  async createDepartment(orgId: string, name: string, description?: string): Promise<Department | null> {
    const { data, error } = await supabase
      .from("departments")
      .insert([{ org_id: orgId, name, description }])
      .select()
      .single();
    if (error) throw new Error(error.message);
    return data;
  },

  // Memberships
  async getMemberships(orgId: string): Promise<OrgMembership[]> {
    const { data, error } = await supabase
      .from("org_memberships")
      .select("*, profiles(*)")
      .eq("org_id", orgId);
    if (error) return [];
    return (data || []).map((m: any) => ({
      id: m.id,
      org_id: m.org_id,
      user_id: m.user_id,
      role: m.role,
      user_email: m.profiles?.email || "auditor@auditpilot.internal",
      user_name: m.profiles?.full_name || "Team Member",
      created_at: m.created_at,
    }));
  },

  // Granular Permissions
  async getPermissions(orgId: string): Promise<Permission[]> {
    const { data, error } = await supabase
      .from("permissions")
      .select("*")
      .eq("org_id", orgId);
    if (error) return [];
    return data || [];
  },

  async updatePermission(permId: string, updates: Partial<Permission>): Promise<void> {
    const { error } = await supabase.from("permissions").update(updates).eq("id", permId);
    if (error) throw new Error(error.message);
  },

  async getPermissionAuditLog(orgId: string): Promise<any[]> {
    const { data, error } = await supabase
      .from("permission_audit_log")
      .select("*")
      .eq("org_id", orgId)
      .order("performed_at", { ascending: false })
      .limit(20);
    if (error) return [];
    return data || [];
  },

  // Investigations Hub
  async getInvestigations(orgId?: string): Promise<Investigation[]> {
    let query = supabase.from("investigations").select("*").order("created_at", { ascending: false });
    if (orgId) {
      query = query.eq("org_id", orgId);
    }
    const { data, error } = await query;
    if (error) return [];
    return data || [];
  },

  async createInvestigation(item: Partial<Investigation>): Promise<Investigation | null> {
    const { data, error } = await supabase
      .from("investigations")
      .insert([item])
      .select()
      .single();
    if (error) throw new Error(error.message);
    return data;
  },

  async getInvestigationThreads(investigationId: string): Promise<any[]> {
    const { data, error } = await supabase
      .from("investigation_threads")
      .select("*, investigation_comments(*)")
      .eq("investigation_id", investigationId)
      .order("created_at");
    if (error) return [];
    return data || [];
  },

  async addInvestigationComment(threadId: string, comment: string, authorName: string): Promise<any> {
    const { data, error } = await supabase
      .from("investigation_comments")
      .insert([{ thread_id: threadId, comment, author_name: authorName }])
      .select()
      .single();
    if (error) throw new Error(error.message);
    return data;
  },

  // Report Sharing
  async getAuditReports(orgId?: string): Promise<AuditReport[]> {
    let query = supabase.from("audit_reports").select("*").order("published_at", { ascending: false });
    if (orgId) {
      query = query.eq("org_id", orgId);
    }
    const { data, error } = await query;
    if (error) return [];
    return data || [];
  },

  async getReportShares(reportId: string): Promise<any[]> {
    const { data, error } = await supabase
      .from("report_shares")
      .select("*")
      .eq("report_id", reportId);
    if (error) return [];
    return data || [];
  },

  async shareReport(reportId: string, params: { user_id?: string; dept_id?: string; is_full_access: boolean; allowed_fields?: string[] }): Promise<any> {
    const { data, error } = await supabase
      .from("report_shares")
      .insert([{ report_id: reportId, ...params }])
      .select()
      .single();
    if (error) throw new Error(error.message);
    return data;
  },
};
