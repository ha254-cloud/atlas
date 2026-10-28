"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload, FileText, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { claimsService } from "@/services/claims-service";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

const TERMINAL_STATUSES = new Set(["completed", "failed"]);
const POLL_INTERVAL_MS = 1500;

function statusBadgeVariant(status: string): "success" | "destructive" | "warning" | "secondary" {
  if (status === "completed") return "success";
  if (status === "failed") return "destructive";
  if (status === "processing") return "warning";
  return "secondary";
}

export function UploadClaimsDialog() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<number | null>(null);
  const [uploadedFilename, setUploadedFilename] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const invalidatedRef = useRef(false);

  const uploadMutation = useMutation({
    mutationFn: () => claimsService.uploadCsv(file as File),
    onSuccess: (data) => {
      setJobId(data.job_id);
      setUploadedFilename(data.filename);
    },
  });

  const jobQuery = useQuery({
    queryKey: ["import-job", jobId],
    queryFn: () => claimsService.getImportJob(jobId as number),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && TERMINAL_STATUSES.has(status) ? false : POLL_INTERVAL_MS;
    },
  });

  const job = jobQuery.data;

  // Refresh the claims list exactly once, the moment the job reaches "completed".
  useEffect(() => {
    if (job?.status === "completed" && !invalidatedRef.current) {
      invalidatedRef.current = true;
      queryClient.invalidateQueries({ queryKey: ["claims"] });
    }
  }, [job?.status, queryClient]);

  const reset = () => {
    setFile(null);
    setJobId(null);
    setUploadedFilename(null);
    invalidatedRef.current = false;
    uploadMutation.reset();
    if (inputRef.current) inputRef.current.value = "";
  };

  const progressPct =
    job && job.total ? Math.min(100, Math.round((job.processed / job.total) * 100)) : null;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" className="gap-1.5">
          <Upload className="h-4 w-4" /> Upload CSV
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload Claims</DialogTitle>
        </DialogHeader>

        {jobId !== null ? (
          <div className="space-y-4">
            <div className="rounded-lg bg-muted/40 border p-4 space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div className="text-sm">
                  <p className="font-medium">{uploadedFilename ?? job?.filename ?? "Import job"}</p>
                  <p className="text-muted-foreground mt-0.5">Job #{jobId}</p>
                </div>
                <Badge
                  variant={statusBadgeVariant(job?.status ?? "queued")}
                  className="capitalize shrink-0"
                >
                  {job?.status ?? "queued"}
                </Badge>
              </div>

              {job && !TERMINAL_STATUSES.has(job.status) && (
                <div className="space-y-1.5">
                  <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                    <div
                      className={cn(
                        "h-full bg-primary transition-all duration-500",
                        progressPct === null && "animate-pulse w-1/3",
                      )}
                      style={progressPct !== null ? { width: `${progressPct}%` } : undefined}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {progressPct !== null
                      ? `${job.processed} of ${job.total} rows processed (${progressPct}%)`
                      : "Starting up…"}
                  </p>
                </div>
              )}

              {job?.status === "completed" && (
                <div className="flex items-start gap-2.5 text-sm">
                  <CheckCircle className="h-4 w-4 text-green-600 mt-0.5 shrink-0" />
                  <div>
                    <p>
                      Imported <span className="font-medium">{job.imported}</span> claim
                      {job.imported === 1 ? "" : "s"}
                      {job.duplicates > 0 && (
                        <> · {job.duplicates} duplicate{job.duplicates === 1 ? "" : "s"} skipped</>
                      )}
                      {job.invalid > 0 && (
                        <> · {job.invalid} row{job.invalid === 1 ? "" : "s"} failed</>
                      )}
                    </p>
                    {job.duration_ms !== null && (
                      <p className="text-muted-foreground mt-0.5">
                        Finished in {(job.duration_ms / 1000).toFixed(1)}s
                      </p>
                    )}
                  </div>
                </div>
              )}

              {job?.status === "failed" && (
                <div className="flex items-start gap-2.5 text-sm">
                  <XCircle className="h-4 w-4 text-destructive mt-0.5 shrink-0" />
                  <p className="text-destructive">
                    {job.error_message ?? "The import job failed unexpectedly."}
                  </p>
                </div>
              )}

              {job?.errors && job.errors.length > 0 && (
                <div className="rounded border bg-background/60 p-2 max-h-32 overflow-y-auto space-y-1">
                  {job.errors.slice(0, 5).map((err, idx) => (
                    <p key={idx} className="text-xs text-muted-foreground">
                      Row {err.row}
                      {err.claim_number ? ` (${err.claim_number})` : ""}: {err.error}
                    </p>
                  ))}
                  {job.errors.length > 5 && (
                    <p className="text-xs text-muted-foreground">
                      +{job.errors.length - 5} more error{job.errors.length - 5 === 1 ? "" : "s"}
                    </p>
                  )}
                </div>
              )}

              {jobQuery.isPending && !job && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" /> Checking status…
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={reset}>Upload another</Button>
              <Button onClick={() => setOpen(false)}>Done</Button>
            </div>
          </div>
        ) : (
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (file) uploadMutation.mutate();
            }}
          >
            <p className="text-sm text-muted-foreground">
              Upload a CSV file with columns: claim_number, patient_first_name,
              patient_last_name, payer_code, billed_amount, paid_amount, service_date.
            </p>

            <label
              htmlFor="claims-csv"
              className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-8 text-center cursor-pointer hover:bg-muted/30 transition-colors"
            >
              <FileText className="h-6 w-6 text-muted-foreground" />
              <span className="text-sm font-medium">
                {file ? file.name : "Click to choose a CSV file"}
              </span>
              <input
                id="claims-csv"
                ref={inputRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>

            {uploadMutation.isError && (
              <p className="text-sm text-destructive rounded bg-destructive/10 px-3 py-2">
                Upload failed. Please check the file and try again.
              </p>
            )}

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={!file || uploadMutation.isPending}>
                {uploadMutation.isPending ? "Uploading…" : "Upload"}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
