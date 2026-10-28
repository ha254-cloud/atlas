"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, Loader2, Upload } from "lucide-react";
import { documentsService } from "@/services/documents-service";
import { getErrorMessage } from "@/lib/api-client";
import type { ClaimDocument, DocumentType } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate } from "@/lib/utils";

const DOCUMENT_TYPES: Array<{ value: DocumentType; label: string }> = [
  { value: "operative_report", label: "Operative report" },
  { value: "imaging", label: "Imaging" },
  { value: "referral", label: "Referral" },
  { value: "lab_results", label: "Lab results" },
  { value: "authorization", label: "Authorization" },
  { value: "physician_notes", label: "Physician notes" },
  { value: "other", label: "Other" },
];

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ClaimDocuments({ claimId }: { claimId: number }) {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState<DocumentType>("other");
  const [error, setError] = useState<string | null>(null);
  const queryKey = ["claim-documents", claimId];

  const { data: documents = [], isLoading } = useQuery({
    queryKey,
    queryFn: () => documentsService.listForClaim(claimId),
  });

  const uploadMutation = useMutation({
    mutationFn: () => documentsService.upload(claimId, file!, documentType),
    onSuccess: () => {
      setFile(null);
      setError(null);
      if (fileInput.current) fileInput.current.value = "";
      queryClient.invalidateQueries({ queryKey });
    },
    onError: (uploadError) =>
      setError(getErrorMessage(uploadError, "The document could not be uploaded.")),
  });

  const download = async (document: ClaimDocument) => {
    try {
      setError(null);
      await documentsService.download(document);
    } catch (downloadError) {
      setError(getErrorMessage(downloadError, "The document could not be downloaded."));
    }
  };

  return (
    <section className="space-y-4 border-y py-5" aria-labelledby="claim-documents-title">
      <div>
        <h2 id="claim-documents-title" className="flex items-center gap-2 text-sm font-semibold">
          <FileText className="h-4 w-4 text-primary" /> Supporting documents
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Evidence attached to this claim.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_11rem_auto] sm:items-end">
        <div className="space-y-1.5">
          <label htmlFor="claim-document-file" className="text-xs font-medium">File</label>
          <Input
            ref={fileInput}
            id="claim-document-file"
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.tiff,.txt"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="claim-document-type" className="text-xs font-medium">Document type</label>
          <select
            id="claim-document-type"
            value={documentType}
            onChange={(event) => setDocumentType(event.target.value as DocumentType)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            {DOCUMENT_TYPES.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>
        <Button
          type="button"
          disabled={!file || uploadMutation.isPending}
          onClick={() => uploadMutation.mutate()}
        >
          {uploadMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
          Upload
        </Button>
      </div>

      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}

      {isLoading ? (
        <div className="space-y-2"><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /></div>
      ) : documents.length === 0 ? (
        <p className="py-3 text-sm text-muted-foreground">No supporting documents attached.</p>
      ) : (
        <ul className="divide-y rounded-md border">
          {documents.map((document) => (
            <li key={document.id} className="flex flex-col gap-3 p-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{document.filename}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {DOCUMENT_TYPES.find((item) => item.value === document.document_type)?.label ?? "Other"}
                  {" · "}{formatFileSize(document.file_size)}{" · "}{formatDate(document.created_at)}
                </p>
                {document.ai_summary && <p className="mt-2 text-sm text-muted-foreground">{document.ai_summary}</p>}
              </div>
              <div className="flex shrink-0 gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  title="Download document"
                  aria-label={`Download ${document.filename}`}
                  onClick={() => download(document)}
                >
                  <Download className="h-4 w-4" />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}