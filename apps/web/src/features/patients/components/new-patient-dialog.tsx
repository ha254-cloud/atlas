"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getErrorMessage } from "@/lib/api-client";
import { patientsService } from "@/services/patients-service";

const EMPTY_FORM = {
  first_name: "",
  last_name: "",
  medical_record_number: "",
  date_of_birth: "",
};

export function NewPatientDialog() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  const createMutation = useMutation({
    mutationFn: () => patientsService.create(form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patients"] });
      setForm(EMPTY_FORM);
      setOpen(false);
    },
  });

  const updateField = (field: keyof typeof form, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" className="gap-1.5">
          <Plus className="h-4 w-4" /> New Patient
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Patient</DialogTitle>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            createMutation.mutate();
          }}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="patient-first-name">First name</Label>
              <Input
                id="patient-first-name"
                autoComplete="given-name"
                value={form.first_name}
                onChange={(event) => updateField("first_name", event.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="patient-last-name">Last name</Label>
              <Input
                id="patient-last-name"
                autoComplete="family-name"
                value={form.last_name}
                onChange={(event) => updateField("last_name", event.target.value)}
                required
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="patient-mrn">Medical record number</Label>
            <Input
              id="patient-mrn"
              value={form.medical_record_number}
              onChange={(event) => updateField("medical_record_number", event.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="patient-date-of-birth">Date of birth</Label>
            <Input
              id="patient-date-of-birth"
              type="date"
              max={new Date().toISOString().slice(0, 10)}
              value={form.date_of_birth}
              onChange={(event) => updateField("date_of_birth", event.target.value)}
              required
            />
          </div>
          {createMutation.isError && (
            <p className="rounded bg-destructive/10 px-3 py-2 text-sm text-destructive" role="alert">
              {getErrorMessage(createMutation.error, "Failed to create patient.")}
            </p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating..." : "Create Patient"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}