"use client";

import { useDeferredValue, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, FileSearch, Search } from "lucide-react";
import { Header } from "@/components/layout/header";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ClaimDocuments } from "@/features/claims/components/ClaimDocuments";
import { cn, formatCurrency, formatDate } from "@/lib/utils";
import { claimsService } from "@/services/claims-service";

export default function DocumentsPage() {
  const [search, setSearch] = useState("");
  const [selectedClaimId, setSelectedClaimId] = useState<number | null>(null);
  const deferredSearch = useDeferredValue(search.trim());

  const { data: claims = [], isLoading, isError } = useQuery({
    queryKey: ["document-claims", deferredSearch],
    queryFn: () => claimsService.list({
      limit: 50,
      search: deferredSearch || undefined,
    }),
    staleTime: 30_000,
  });

  const activeClaim = claims.find((claim) => claim.id === selectedClaimId) ?? claims[0];
  const activeClaimId = activeClaim?.id ?? null;

  return (
    <div className="flex h-full flex-col">
      <Header title="Documents" />
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto grid max-w-7xl gap-5 lg:grid-cols-[20rem_minmax(0,1fr)]">
          <section className="overflow-hidden rounded-lg border bg-card" aria-label="Claim selector">
            <div className="border-b px-4 py-4">
              <h2 className="text-sm font-semibold">Claims</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Select a claim to manage its evidence.
              </p>
            </div>
            <div className="border-b bg-muted/20 p-3">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  aria-label="Search claims for documents"
                  className="h-9 bg-background pl-9"
                  placeholder="Claim, patient, or payer"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </div>
            </div>

            <div className="max-h-[32rem] overflow-y-auto">
              {isLoading ? (
                <div className="space-y-2 p-3">
                  {Array.from({ length: 6 }).map((_, index) => (
                    <Skeleton key={index} className="h-16 w-full" />
                  ))}
                </div>
              ) : isError ? (
                <p className="flex items-center justify-center gap-2 px-4 py-12 text-sm text-destructive" role="alert">
                  <AlertCircle className="h-4 w-4" /> Unable to load claims.
                </p>
              ) : claims.length === 0 ? (
                <div className="px-4 py-12 text-center text-muted-foreground">
                  <FileSearch className="mx-auto mb-3 h-7 w-7" />
                  <p className="text-sm font-medium text-foreground">No claims found</p>
                  <p className="mt-1 text-xs">Adjust the current search.</p>
                </div>
              ) : (
                <ul className="divide-y">
                  {claims.map((claim) => (
                    <li key={claim.id}>
                      <button
                        type="button"
                        className={cn(
                          "w-full px-4 py-3 text-left transition-colors hover:bg-muted/40",
                          activeClaimId === claim.id && "bg-primary/5 shadow-[inset_3px_0_0_hsl(var(--primary))]",
                        )}
                        aria-current={activeClaimId === claim.id ? "true" : undefined}
                        onClick={() => setSelectedClaimId(claim.id)}
                      >
                        <span className="block truncate font-mono text-xs font-semibold">
                          {claim.claim_number || `Claim ${claim.id}`}
                        </span>
                        <span className="mt-1 block truncate text-sm">{claim.patient_name || "Unknown patient"}</span>
                        <span className="mt-1 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                          <span className="truncate">{claim.payer_name || "Unknown payer"}</span>
                          <span className="shrink-0 tabular-nums">{formatCurrency(claim.billed_amount)}</span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <main className="min-w-0">
            {activeClaim ? (
              <div className="overflow-hidden rounded-lg border bg-card">
                <div className="border-b px-4 py-4 sm:px-5">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <p className="font-mono text-sm font-semibold">
                        {activeClaim.claim_number || `Claim ${activeClaim.id}`}
                      </p>
                      <p className="mt-1 truncate text-sm text-muted-foreground">
                        {activeClaim.patient_name || "Unknown patient"} · {activeClaim.payer_name || "Unknown payer"}
                      </p>
                    </div>
                    <p className="shrink-0 text-xs tabular-nums text-muted-foreground">
                      Service date {formatDate(activeClaim.service_date)}
                    </p>
                  </div>
                </div>
                <div className="px-4 pb-4 sm:px-5 sm:pb-5">
                  <ClaimDocuments claimId={activeClaim.id} />
                </div>
              </div>
            ) : (
              <div className="flex min-h-72 flex-col items-center justify-center rounded-lg border border-dashed px-6 text-center text-muted-foreground">
                <FileSearch className="mb-3 h-8 w-8" />
                <p className="text-sm font-medium text-foreground">Select a claim</p>
                <p className="mt-1 max-w-sm text-xs">
                  Supporting evidence remains attached to its owning claim and tenant boundary.
                </p>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}