"use client";

import { useDeferredValue, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ChevronLeft, ChevronRight, Search, Users } from "lucide-react";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EditPatientDialog } from "@/features/patients/components/edit-patient-dialog";
import { NewPatientDialog } from "@/features/patients/components/new-patient-dialog";
import { formatDate } from "@/lib/utils";
import { patientsService } from "@/services/patients-service";

const PAGE_SIZE = 20;

export default function PatientsPage() {
  const [search, setSearch] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [offset, setOffset] = useState(0);
  const deferredSearch = useDeferredValue(search.trim());

  const { data: patients = [], isLoading, isError } = useQuery({
    queryKey: ["patients", { search: deferredSearch, dateOfBirth, offset }],
    queryFn: () => patientsService.list({
      limit: PAGE_SIZE,
      offset,
      search: deferredSearch || undefined,
      date_of_birth: dateOfBirth || undefined,
    }),
    staleTime: 30_000,
  });

  return (
    <div className="flex h-full flex-col">
      <Header title="Patients" />
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-6xl space-y-4">
          <section className="overflow-hidden rounded-lg border bg-card" aria-label="Patient registry">
            <div className="flex flex-col gap-3 border-b px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-sm font-semibold">Patient registry</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Tenant-scoped identities used across claim workflows
                </p>
              </div>
              <NewPatientDialog />
            </div>

            <div className="flex flex-col gap-2 border-b bg-muted/20 p-3 sm:flex-row">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  aria-label="Search patients"
                  placeholder="Search name or medical record number"
                  className="h-9 bg-background pl-9"
                  value={search}
                  onChange={(event) => {
                    setSearch(event.target.value);
                    setOffset(0);
                  }}
                />
              </div>
              <Input
                aria-label="Filter patients by date of birth"
                type="date"
                className="h-9 bg-background sm:w-48"
                value={dateOfBirth}
                onChange={(event) => {
                  setDateOfBirth(event.target.value);
                  setOffset(0);
                }}
              />
            </div>

            {isLoading ? (
              <div className="space-y-3 p-4">
                {Array.from({ length: 6 }).map((_, index) => (
                  <Skeleton key={index} className="h-14 w-full" />
                ))}
              </div>
            ) : isError ? (
              <div className="flex items-center justify-center gap-2 px-4 py-16 text-sm text-destructive" role="alert">
                <AlertCircle className="h-4 w-4" /> Unable to load patients.
              </div>
            ) : patients.length === 0 ? (
              <div className="flex flex-col items-center px-4 py-16 text-center text-muted-foreground">
                <Users className="mb-3 h-8 w-8" />
                <p className="text-sm font-medium text-foreground">No patients found</p>
                <p className="mt-1 text-xs">
                  {search || dateOfBirth ? "Adjust the current filters." : "Create the first patient to begin a claim."}
                </p>
              </div>
            ) : (
              <>
                <div className="hidden grid-cols-[minmax(180px,1.3fr)_minmax(150px,1fr)_150px_130px_40px] bg-muted/30 px-4 py-2 text-xs font-medium text-muted-foreground md:grid">
                  <span>Patient</span><span>Medical record number</span><span>Date of birth</span><span>Added</span><span className="sr-only">Actions</span>
                </div>
                <div className="divide-y">
                  {patients.map((patient) => (
                    <div
                      key={patient.id}
                      className="grid gap-3 px-4 py-3 hover:bg-muted/20 md:grid-cols-[minmax(180px,1.3fr)_minmax(150px,1fr)_150px_130px_40px] md:items-center"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{patient.last_name}, {patient.first_name}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground md:hidden">Patient</p>
                      </div>
                      <div>
                        <p className="font-mono text-sm">
                          {patient.medical_record_number || "Not provided"}
                        </p>
                        <p className="mt-0.5 text-xs text-muted-foreground md:hidden">Medical record number</p>
                      </div>
                      <div>
                        <p className="text-sm tabular-nums">{formatDate(patient.date_of_birth)}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground md:hidden">Date of birth</p>
                      </div>
                      <div>
                        <p className="text-sm tabular-nums">{formatDate(patient.created_at)}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground md:hidden">Added</p>
                      </div>
                      <div className="justify-self-end">
                        <EditPatientDialog patient={patient} />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="flex items-center justify-between gap-3 border-t px-4 py-2">
                  <span className="text-xs tabular-nums text-muted-foreground">
                    Showing {offset + 1}-{offset + patients.length}
                  </span>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      title="Previous page"
                      aria-label="Previous page"
                      disabled={offset === 0 || isLoading}
                      onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="min-w-16 text-center text-xs tabular-nums text-muted-foreground">
                      Page {Math.floor(offset / PAGE_SIZE) + 1}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      title="Next page"
                      aria-label="Next page"
                      disabled={patients.length < PAGE_SIZE || isLoading}
                      onClick={() => setOffset((current) => current + PAGE_SIZE)}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}