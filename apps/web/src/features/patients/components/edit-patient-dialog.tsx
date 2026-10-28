"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
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
import type { Patient, PatientUpdateInput } from "@/types";

function patientForm(patient: Patient): PatientUpdateInput {
  return {
    first_name: patient.first_name,
    last_name: patient.last_name,
    medical_record_number: patient.medical_record_number,
    date_of_birth: patient.date_of_birth,
  };
}

export function EditPatientDialog({ patient }: { patient: Patient }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<PatientUpdateInput>(() => patientForm(patient));

  const updateMutation = useMutation({
    mutationFn: () => patientsService.update(patient.id, form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patients"] });
      setOpen(false);
    },
  });

  const updateField = (field: keyof PatientUpdateInput, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (nextOpen) {
          setForm(patientForm(patient));
          updateMutation.reset();
        }
        setOpen(nextOpen);
      }}
    >
      <DialogTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          title={`Edit ${patient.first_name} ${patient.last_name}`}
          aria-label={`Edit ${patient.first_name} ${patient.last_name}`}
        >
          <Pencil className="h-3.5 w-3.5" />
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Patient</DialogTitle>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            updateMutation.mutate();
          }}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor={`patient-first-name-${patient.id}`}>First name</Label>
              <Input
                id={`patient-first-name-${patient.id}`}
                autoComplete="given-name"
                value={form.first_name ?? ""}
                onChange={(event) => updateField("first_name", event.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={`patient-last-name-${patient.id}`}>Last name</Label>
              <Input
                id={`patient-last-name-${patient.id}`}
                autoComplete="family-name"
                value={form.last_name ?? ""}
                onChange={(event) => updateField("last_name", event.target.value)}
                required
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`patient-mrn-${patient.id}`}>Medical record number</Label>
            <Input
              id={`patient-mrn-${patient.id}`}
              value={form.medical_record_number ?? ""}
              onChange={(event) => updateField("medical_record_number", event.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`patient-date-of-birth-${patient.id}`}>Date of birth</Label>
            <Input
              id={`patient-date-of-birth-${patient.id}`}
              type="date"
              max={new Date().toISOString().slice(0, 10)}
              value={form.date_of_birth ?? ""}
              onChange={(event) => updateField("date_of_birth", event.target.value)}
              required
            />
          </div>
          {updateMutation.isError && (
            <p className="rounded bg-destructive/10 px-3 py-2 text-sm text-destructive" role="alert">
              {getErrorMessage(updateMutation.error, "Failed to update patient.")}
            </p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}