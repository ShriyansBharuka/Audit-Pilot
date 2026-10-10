"use client";

import React, { useEffect, useState } from "react";
import { supabaseService } from "@/lib/supabase";
import { Department, Organization, OrgMembership } from "@/lib/types";
import {
  Building,
  CheckCircle2,
  FolderTree,
  Mail,
  Plus,
  RefreshCw,
  Shield,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";

export default function OrgsPage() {
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [members, setMembers] = useState<OrgMembership[]>([]);
  const [loading, setLoading] = useState(true);

  // Modals
  const [createOrgOpen, setCreateOrgOpen] = useState(false);
  const [newOrgName, setNewOrgName] = useState("");
  const [newOrgDesc, setNewOrgDesc] = useState("");

  const [createDeptOpen, setCreateDeptOpen] = useState(false);
  const [newDeptName, setNewDeptName] = useState("");
  const [newDeptDesc, setNewDeptDesc] = useState("");

  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "auditor" | "viewer">("auditor");

  const loadOrgs = async () => {
    setLoading(true);
    try {
      const list = await supabaseService.getOrganizations();
      setOrgs(list);
      if (list.length > 0 && !selectedOrg) {
        setSelectedOrg(list[0]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOrgs();
  }, []);

  useEffect(() => {
    if (selectedOrg) {
      supabaseService.getDepartments(selectedOrg.id).then((d) => setDepartments(d));
      supabaseService.getMemberships(selectedOrg.id).then((m) => setMembers(m));
    }
  }, [selectedOrg]);

  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newOrgName.trim()) return;
    try {
      const created = await supabaseService.createOrganization(newOrgName.trim(), newOrgDesc.trim());
      if (created) {
        setOrgs([...orgs, created]);
        setSelectedOrg(created);
        setCreateOrgOpen(false);
        setNewOrgName("");
        setNewOrgDesc("");
      }
    } catch (err: any) {
      alert("Failed to create org: " + err.message);
    }
  };

  const handleCreateDept = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOrg || !newDeptName.trim()) return;
    try {
      const dept = await supabaseService.createDepartment(selectedOrg.id, newDeptName.trim(), newDeptDesc.trim());
      if (dept) {
        setDepartments([...departments, dept]);
        setCreateDeptOpen(false);
        setNewDeptName("");
        setNewDeptDesc("");
      }
    } catch (err: any) {
      alert("Failed to create department: " + err.message);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            Organization & Department Management
            <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-mono font-normal">
              Supabase RLS Backed
            </span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Configure multi-tenant audit firms, client entities, functional departments, and role assignments.
          </p>
        </div>

        <button
          onClick={() => setCreateOrgOpen(true)}
          className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition shadow-lg shadow-indigo-600/20"
        >
          <Plus className="h-4 w-4" />
          <span>New Organization</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Orgs list */}
        <div className="glass-panel p-4 rounded-xl border border-slate-800 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
            <h2 className="text-sm font-semibold text-white flex items-center gap-1.5">
              <Building className="h-4 w-4 text-indigo-400" />
              Organizations
            </h2>
            <span className="text-xs font-mono text-slate-400">{orgs.length}</span>
          </div>

          <div className="space-y-2">
            {orgs.length === 0 ? (
              <div className="py-8 text-center text-slate-400 text-xs">
                No organizations created yet. Click "New Organization" to create the first tenant.
              </div>
            ) : (
              orgs.map((org) => (
                <div
                  key={org.id}
                  onClick={() => setSelectedOrg(org)}
                  className={`p-3 rounded-lg border cursor-pointer transition ${
                    selectedOrg?.id === org.id
                      ? "border-indigo-500 bg-indigo-500/10"
                      : "border-slate-800 bg-slate-900/40 hover:border-slate-700"
                  }`}
                >
                  <div className="font-semibold text-xs text-white">{org.name}</div>
                  <div className="text-[11px] text-slate-400 font-mono mt-0.5">{org.slug}</div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right 2 Columns: Selected Org Departments and Members */}
        <div className="lg:col-span-2 space-y-6">
          {selectedOrg ? (
            <>
              {/* Org Details Bar */}
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-white">{selectedOrg.name}</h2>
                  <p className="text-xs text-slate-400 mt-0.5">{selectedOrg.description || "Active multi-tenant audit firm"}</p>
                </div>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                  Tenant ID: {selectedOrg.id.slice(0, 8)}...
                </span>
              </div>

              {/* Departments Section */}
              <div className="glass-panel p-5 rounded-xl border border-slate-800 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    <FolderTree className="h-4 w-4 text-indigo-400" />
                    Departments & Engagement Teams ({departments.length})
                  </h3>
                  <button
                    onClick={() => setCreateDeptOpen(true)}
                    className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs border border-slate-700 flex items-center gap-1"
                  >
                    <Plus className="h-3 w-3" />
                    <span>Add Department</span>
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {departments.length === 0 ? (
                    <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-800 text-slate-400 text-xs col-span-2">
                      No departments configured. Add Audit, Forensics, Accounts, or Tax groups.
                    </div>
                  ) : (
                    departments.map((dept) => (
                      <div key={dept.id} className="p-3.5 rounded-lg bg-slate-900/60 border border-slate-800 space-y-1">
                        <div className="font-semibold text-xs text-slate-200">{dept.name}</div>
                        <div className="text-xs text-slate-400">{dept.description || "Active departmental unit"}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Members Section */}
              <div className="glass-panel p-5 rounded-xl border border-slate-800 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    <Users className="h-4 w-4 text-indigo-400" />
                    Assigned Team Members & Roles ({members.length})
                  </h3>
                  <button
                    onClick={() => setInviteOpen(true)}
                    className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs border border-slate-700 flex items-center gap-1"
                  >
                    <UserPlus className="h-3 w-3" />
                    <span>Invite User</span>
                  </button>
                </div>

                <div className="space-y-2">
                  {members.length === 0 ? (
                    <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-800 text-slate-400 text-xs">
                      No members assigned to this organization.
                    </div>
                  ) : (
                    members.map((m) => (
                      <div
                        key={m.id}
                        className="p-3 rounded-lg bg-slate-900/40 border border-slate-800 flex items-center justify-between text-xs"
                      >
                        <div>
                          <div className="font-medium text-white">{m.user_name}</div>
                          <div className="text-[11px] text-slate-400 font-mono">{m.user_email}</div>
                        </div>
                        <span className="text-[11px] uppercase font-mono px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-bold">
                          {m.role}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="py-20 text-center text-slate-400 text-xs">Select or create an organization.</div>
          )}
        </div>
      </div>

      {/* Create Org Modal */}
      {createOrgOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <form onSubmit={handleCreateOrg} className="bg-slate-900 border border-slate-700 rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4 text-xs">
            <h3 className="font-bold text-white text-sm">Create New Organization</h3>
            <div className="space-y-1">
              <label className="text-slate-300 font-semibold">Organization Name</label>
              <input
                type="text"
                required
                placeholder="e.g. Apex Statutory Auditors LLP"
                value={newOrgName}
                onChange={(e) => setNewOrgName(e.target.value)}
                className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-white"
              />
            </div>
            <div className="space-y-1">
              <label className="text-slate-300 font-semibold">Description</label>
              <textarea
                rows={2}
                placeholder="Audit firm or corporate client group..."
                value={newOrgDesc}
                onChange={(e) => setNewOrgDesc(e.target.value)}
                className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-white"
              />
            </div>
            <div className="flex justify-end space-x-2 pt-2">
              <button
                type="button"
                onClick={() => setCreateOrgOpen(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-400 text-xs"
              >
                Cancel
              </button>
              <button type="submit" className="px-4 py-1.5 rounded-lg bg-indigo-600 text-white font-medium">
                Create Tenant
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Create Department Modal */}
      {createDeptOpen && selectedOrg && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <form onSubmit={handleCreateDept} className="bg-slate-900 border border-slate-700 rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4 text-xs">
            <h3 className="font-bold text-white text-sm">Add Department to {selectedOrg.name}</h3>
            <div className="space-y-1">
              <label className="text-slate-300 font-semibold">Department / Group Name</label>
              <input
                type="text"
                required
                placeholder="e.g. Statutory Audit Team A"
                value={newDeptName}
                onChange={(e) => setNewDeptName(e.target.value)}
                className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-white"
              />
            </div>
            <div className="space-y-1">
              <label className="text-slate-300 font-semibold">Description</label>
              <textarea
                rows={2}
                placeholder="Scope of work..."
                value={newDeptDesc}
                onChange={(e) => setNewDeptDesc(e.target.value)}
                className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-white"
              />
            </div>
            <div className="flex justify-end space-x-2 pt-2">
              <button
                type="button"
                onClick={() => setCreateDeptOpen(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-400 text-xs"
              >
                Cancel
              </button>
              <button type="submit" className="px-4 py-1.5 rounded-lg bg-indigo-600 text-white font-medium">
                Add Department
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
