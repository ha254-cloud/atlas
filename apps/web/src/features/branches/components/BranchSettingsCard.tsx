"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Loader2, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getErrorMessage } from "@/lib/api-client";
import { authService } from "@/services/auth-service";
import { branchesService } from "@/services/branches-service";

const selectClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

export function BranchSettingsCard() {
  const queryClient = useQueryClient();
  const [selectedBranchId, setSelectedBranchId] = useState("");
  const [branchName, setBranchName] = useState("");
  const [branchCode, setBranchCode] = useState("");
  const [departmentName, setDepartmentName] = useState("");
  const [departmentCode, setDepartmentCode] = useState("");
  const [memberId, setMemberId] = useState("");
  const [reason, setReason] = useState("Configure organization branch access");
  const [feedback, setFeedback] = useState<string | null>(null);

  const { data: branches } = useQuery({
    queryKey: ["branches"],
    queryFn: branchesService.list,
  });
  const { data: members } = useQuery({
    queryKey: ["org-members"],
    queryFn: authService.listMembers,
  });
  const branchId = Number(selectedBranchId);
  const { data: departments } = useQuery({
    queryKey: ["branches", branchId, "departments"],
    queryFn: () => branchesService.listDepartments(branchId),
    enabled: branchId > 0,
  });
  const { data: memberships } = useQuery({
    queryKey: ["branches", branchId, "memberships"],
    queryFn: () => branchesService.listMemberships(branchId),
    enabled: branchId > 0,
  });

  useEffect(() => {
    if (!selectedBranchId && branches?.length) {
      setSelectedBranchId(String(branches[0].id));
    }
  }, [branches, selectedBranchId]);

  const createBranch = useMutation({
    mutationFn: () => branchesService.create({ name: branchName, code: branchCode, reason }),
    onSuccess: async (branch) => {
      await queryClient.invalidateQueries({ queryKey: ["branches"] });
      setSelectedBranchId(String(branch.id));
      setBranchName("");
      setBranchCode("");
      setFeedback("Branch created.");
    },
    onError: (error) => setFeedback(getErrorMessage(error, "Failed to create branch")),
  });
  const createDepartment = useMutation({
    mutationFn: () =>
      branchesService.createDepartment(branchId, {
        name: departmentName,
        code: departmentCode,
        reason,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["branches", branchId, "departments"] });
      setDepartmentName("");
      setDepartmentCode("");
      setFeedback("Department created.");
    },
    onError: (error) => setFeedback(getErrorMessage(error, "Failed to create department")),
  });
  const assignMember = useMutation({
    mutationFn: () =>
      branchesService.assignMembership(branchId, {
        user_id: Number(memberId),
        role_template: "operational",
        reason,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["branches", branchId, "memberships"] });
      setMemberId("");
      setFeedback("Branch access assigned.");
    },
    onError: (error) => setFeedback(getErrorMessage(error, "Failed to assign branch access")),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Building2 className="h-4 w-4" /> Branches
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <form className="grid gap-3 sm:grid-cols-[1fr_8rem_auto] sm:items-end" onSubmit={(event) => { event.preventDefault(); setFeedback(null); createBranch.mutate(); }}>
          <div className="space-y-2"><Label htmlFor="branch-name">Branch name</Label><Input id="branch-name" value={branchName} onChange={(event) => setBranchName(event.target.value)} required /></div>
          <div className="space-y-2"><Label htmlFor="branch-code">Code</Label><Input id="branch-code" value={branchCode} onChange={(event) => setBranchCode(event.target.value.toUpperCase())} required /></div>
          <Button type="submit" disabled={createBranch.isPending}>{createBranch.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Branch</Button>
        </form>

        {branches?.length ? (
          <div className="space-y-4 border-t pt-5">
            <div className="space-y-2"><Label htmlFor="active-branch">Manage branch</Label><select id="active-branch" className={selectClass} value={selectedBranchId} onChange={(event) => setSelectedBranchId(event.target.value)}>{branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name} ({branch.code})</option>)}</select></div>
            <div className="grid gap-4 lg:grid-cols-2">
              <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); setFeedback(null); createDepartment.mutate(); }}>
                <p className="text-sm font-medium">Departments</p>
                <div className="flex flex-wrap gap-2">{departments?.map((department) => <Badge key={department.id} variant="secondary">{department.name} · {department.code}</Badge>)}</div>
                <div className="grid grid-cols-[1fr_7rem] gap-2"><Input aria-label="Department name" placeholder="Department name" value={departmentName} onChange={(event) => setDepartmentName(event.target.value)} required /><Input aria-label="Department code" placeholder="Code" value={departmentCode} onChange={(event) => setDepartmentCode(event.target.value.toUpperCase())} required /></div>
                <Button type="submit" size="sm" variant="outline" disabled={createDepartment.isPending}><Plus className="h-4 w-4" /> Department</Button>
              </form>
              <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); setFeedback(null); assignMember.mutate(); }}>
                <p className="text-sm font-medium">Assigned team</p>
                <div className="flex flex-wrap gap-2">{memberships?.map((membership) => { const member = members?.find((item) => item.id === membership.user_id); return <Badge key={membership.id} variant="secondary">{member ? `${member.first_name} ${member.last_name}` : `User ${membership.user_id}`}</Badge>; })}</div>
                <select aria-label="Team member" className={selectClass} value={memberId} onChange={(event) => setMemberId(event.target.value)} required><option value="">Select team member…</option>{members?.map((member) => <option key={member.id} value={member.id}>{member.first_name} {member.last_name}</option>)}</select>
                <Button type="submit" size="sm" variant="outline" disabled={assignMember.isPending}><Plus className="h-4 w-4" /> Assign</Button>
              </form>
            </div>
          </div>
        ) : <p className="text-sm text-muted-foreground">Create the first branch to configure departments and team access.</p>}

        <div className="space-y-2"><Label htmlFor="branch-reason">Change reason</Label><Input id="branch-reason" value={reason} onChange={(event) => setReason(event.target.value)} minLength={3} required /></div>
        {feedback && <p className="rounded-md bg-muted px-3 py-2 text-sm">{feedback}</p>}
      </CardContent>
    </Card>
  );
}