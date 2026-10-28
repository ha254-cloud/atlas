"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { claimsService } from "@/services/claims-service";
import { branchesService } from "@/services/branches-service";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ClaimCreateInput } from "@/types";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

const selectClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";

export function NewClaimDialog() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [patientId, setPatientId] = useState("");
  const [payerId, setPayerId] = useState("");
  const [claimNumber, setClaimNumber] = useState("");
  const [billedAmount, setBilledAmount] = useState("");
  const [paidAmount, setPaidAmount] = useState("");
  const [serviceDate, setServiceDate] = useState("");
  const [provider, setProvider] = useState("");
  const [priority, setPriority] = useState("medium");
  const [branchId, setBranchId] = useState("");
  const [departmentId, setDepartmentId] = useState("");

  const { data: patients } = useQuery({
    queryKey: ["claim-lookups", "patients"],
    queryFn: () => claimsService.listPatients(),
    enabled: open,
  });

  const { data: payers } = useQuery({
    queryKey: ["claim-lookups", "payers"],
    queryFn: () => claimsService.listPayers(),
    enabled: open,
  });

  const { data: branches } = useQuery({
    queryKey: ["branches"],
    queryFn: branchesService.list,
    enabled: open,
  });

  const { data: departments } = useQuery({
    queryKey: ["branches", Number(branchId), "departments"],
    queryFn: () => branchesService.listDepartments(Number(branchId)),
    enabled: open && Boolean(branchId),
  });

  const resetForm = () => {
    setPatientId("");
    setPayerId("");
    setClaimNumber("");
    setBilledAmount("");
    setPaidAmount("");
    setServiceDate("");
    setProvider("");
    setPriority("medium");
    setBranchId("");
    setDepartmentId("");
  };

  const createMutation = useMutation({
    mutationFn: () =>
      claimsService.create({
        branch_id: branchId ? Number(branchId) : undefined,
        department_id: departmentId ? Number(departmentId) : undefined,
        patient_id: Number(patientId),
        payer_id: Number(payerId),
        claim_number: claimNumber || undefined,
        billed_amount: Number(billedAmount),
        paid_amount: paidAmount ? Number(paidAmount) : 0,
        service_date: serviceDate || undefined,
        provider: provider || undefined,
        priority: priority as ClaimCreateInput["priority"],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["claims"] });
      resetForm();
      setOpen(false);
    },
  });

  const canSubmit = patientId && payerId && billedAmount;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" className="gap-1.5">
          <Plus className="h-4 w-4" /> New Claim
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Claim</DialogTitle>
        </DialogHeader>

        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
        >
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="patient">Patient</Label>
              <select
                id="patient"
                className={selectClass}
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
                required
              >
                <option value="">Select patient…</option>
                {patients?.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="payer">Insurance / Payer</Label>
              <select
                id="payer"
                className={selectClass}
                value={payerId}
                onChange={(e) => setPayerId(e.target.value)}
                required
              >
                <option value="">Select payer…</option>
                {payers?.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="claim_number">Claim Number (optional)</Label>
            <Input
              id="claim_number"
              placeholder="Auto-generated if left blank"
              value={claimNumber}
              onChange={(e) => setClaimNumber(e.target.value)}
            />
          </div>

          {branches?.length ? (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="branch">Branch</Label>
                <select id="branch" className={selectClass} value={branchId} onChange={(e) => { setBranchId(e.target.value); setDepartmentId(""); }} required>
                  <option value="">Select branch…</option>
                  {branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="department">Department</Label>
                <select id="department" className={selectClass} value={departmentId} onChange={(e) => setDepartmentId(e.target.value)} disabled={!branchId}>
                  <option value="">No department</option>
                  {departments?.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}
                </select>
              </div>
            </div>
          ) : null}

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="billed">Billed Amount</Label>
              <Input
                id="billed"
                type="number"
                step="0.01"
                min="0"
                value={billedAmount}
                onChange={(e) => setBilledAmount(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="paid">Paid Amount</Label>
              <Input
                id="paid"
                type="number"
                step="0.01"
                min="0"
                value={paidAmount}
                onChange={(e) => setPaidAmount(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="service_date">Date of Service</Label>
            <Input
              id="service_date"
              type="date"
              value={serviceDate}
              onChange={(e) => setServiceDate(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="provider">Provider (optional)</Label>
              <Input
                id="provider"
                placeholder="Rendering provider name"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="priority">Priority</Label>
              <select
                id="priority"
                className={selectClass}
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>

          {createMutation.isError && (
            <p className="text-sm text-destructive rounded bg-destructive/10 px-3 py-2">
              Failed to create claim. Please check the fields and try again.
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!canSubmit || createMutation.isPending}>
              {createMutation.isPending ? "Creating…" : "Create Claim"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
