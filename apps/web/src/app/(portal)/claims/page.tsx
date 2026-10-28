"use client";

import { useState } from "react";
import { Search } from "lucide-react";
import { Header } from "@/components/layout/header";
import { Input } from "@/components/ui/input";
import { ClaimsTable } from "@/features/claims/components/claims-table";
import { NewClaimDialog } from "@/features/claims/components/NewClaimDialog";
import { UploadClaimsDialog } from "@/features/claims/components/UploadClaimsDialog";

const selectClass =
  "flex h-9 rounded-md border border-input bg-background px-2.5 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

export default function ClaimsPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");

  return (
    <div className="flex flex-col h-full">
      <Header title="Claims" />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-1">
            <div className="relative w-full max-w-xs">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                className="pl-8 h-9"
                placeholder="Search claim #, patient, or payer…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <select
              className={selectClass}
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">All statuses</option>
              <option value="imported">Imported</option>
              <option value="pending">Pending</option>
              <option value="paid">Paid</option>
              <option value="denied">Denied</option>
              <option value="appealed">Appealed</option>
              <option value="closed">Closed</option>
            </select>
            <select
              className={selectClass}
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
            >
              <option value="">All priorities</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <UploadClaimsDialog />
            <NewClaimDialog />
          </div>
        </div>
        <ClaimsTable search={search} status={status} priority={priority} />
      </div>
    </div>
  );
}
