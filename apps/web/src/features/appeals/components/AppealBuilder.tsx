"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, FileText, ChevronDown, ChevronUp, CheckCircle, Send, ClipboardCheck, ThumbsUp, XCircle, Save } from "lucide-react";
import { appealsService, type Appeal } from "@/services/appeals-service";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { getErrorMessage } from "@/lib/api-client";

const SECTION_LABELS: Record<string, string> = {
  introduction:          "Introduction",
  medical_necessity:     "Medical Necessity",
  coding_justification:  "Coding Justification",
  policy_references:     "Policy References",
  supporting_documents:  "Supporting Documents",
  requested_action:      "Requested Action",
  signature:             "Signature",
};

function AppealSection({
  title, text, editable, onChange,
}: {
  title: string; text: string; editable: boolean; onChange: (val: string) => void;
}) {
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded-lg border overflow-hidden">
      <button
        className="flex w-full items-center justify-between px-4 py-3 bg-muted/40 hover:bg-muted/60 transition-colors text-sm font-medium"
        onClick={() => setOpen(!open)}
      >
        {title}
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>
      {open && (
        editable ? (
          <textarea
            className="w-full p-4 text-sm font-sans leading-relaxed resize-y focus:outline-none focus:ring-2 focus:ring-ring min-h-32"
            value={text}
            onChange={(e) => onChange(e.target.value)}
            rows={6}
          />
        ) : (
          <p className="whitespace-pre-wrap p-4 text-sm leading-relaxed">{text}</p>
        )
      )}
    </div>
  );
}

interface Props {
  claimId: number;
  recoveryId?: number;
}

export function AppealBuilder({ claimId, recoveryId }: Props) {
  const [appeal, setAppeal] = useState<Appeal | null>(null);
  const [appealText, setAppealText] = useState("");
  const [sections, setSections] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<"idle" | "simple" | "sectioned">("idle");
  const [manualOpen, setManualOpen] = useState(false);
  const [confirmationNumber, setConfirmationNumber] = useState("");

  const generateSimple = useMutation({
    mutationFn: () => appealsService.generate(claimId, recoveryId),
    onSuccess: (data) => {
      setAppeal(data);
      setAppealText(data.appeal_text);
      setMode("simple");
    },
  });

  const generateSectioned = useMutation({
    mutationFn: () => appealsService.generateSectioned(claimId, recoveryId),
    onSuccess: (data) => {
      setAppeal(data);
      setAppealText(data.appeal_text);
      setSections((data.sections as Record<string, string>) ?? {});
      setMode("sectioned");
    },
  });

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!appeal) throw new Error("Appeal is not loaded");
      let text = appealText;
      if (mode === "sectioned") {
        text = appeal.appeal_text;
        const savedSections = appeal.sections ?? {};
        for (const key of Object.keys(SECTION_LABELS)) {
          const saved = savedSections[key];
          const edited = sections[key];
          if (saved !== undefined && edited !== undefined && saved !== edited) {
            text = text.replace(saved, edited);
          }
        }
      }
      return appealsService.update(
        appeal.id,
        text,
        mode === "sectioned" ? sections : undefined,
      );
    },
    onSuccess: (data) => {
      setAppeal(data);
      setAppealText(data.appeal_text);
      if (data.sections) setSections(data.sections);
    },
  });

  const electronicSubmission = useMutation({
    mutationFn: (id: number) => appealsService.submitElectronically(id),
    onSuccess: (data) => setAppeal(data),
  });

  const manualSubmission = useMutation({
    mutationFn: () => appealsService.recordManualSubmission(
      appeal!.id,
      confirmationNumber.trim(),
    ),
    onSuccess: (data) => {
      setAppeal(data);
      setManualOpen(false);
      setConfirmationNumber("");
    },
  });

  const reviewMutation = useMutation({
    mutationFn: (id: number) => appealsService.sendForReview(id),
    onSuccess: (data) => setAppeal(data),
  });

  const approveMutation = useMutation({
    mutationFn: (id: number) => appealsService.approve(id),
    onSuccess: (data) => setAppeal(data),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: number) => appealsService.reject(id),
    onSuccess: (data) => setAppeal(data),
  });

  const isPending = generateSimple.isPending || generateSectioned.isPending;

  if (mode === "idle") {
    return (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Choose how to generate the appeal. Sectioned mode lets you edit each part independently.
        </p>
        <div className="flex gap-3">
          <Button onClick={() => generateSimple.mutate()} disabled={isPending} variant="outline" className="gap-2">
            {generateSimple.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
            Single draft
          </Button>
          <Button onClick={() => generateSectioned.mutate()} disabled={isPending} className="gap-2">
            {generateSectioned.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
            Sectioned builder
          </Button>
        </div>
        {(generateSimple.isError || generateSectioned.isError) && (
          <p className="text-sm text-destructive">Failed to generate. Please try again.</p>
        )}
      </div>
    );
  }

  if (!appeal) return <Skeleton className="h-40 w-full" />;

  const isEditable = appeal.status === "draft" || appeal.status === "review";
  const isDirty = mode === "sectioned"
    ? JSON.stringify(sections) !== JSON.stringify(appeal.sections ?? {})
    : appealText !== appeal.appeal_text;

  return (
    <div className="space-y-4">
      {appeal.summary && (
        <div className="rounded-md bg-muted/40 border p-3 text-sm text-foreground">
          <strong>Summary: </strong>{appeal.summary}
        </div>
      )}

      {mode === "sectioned" && Object.keys(sections).length > 0 ? (
        <div className="space-y-3">
          {Object.entries(SECTION_LABELS).map(([key, label]) =>
            sections[key] !== undefined ? (
              <AppealSection
                key={key}
                title={label}
                text={sections[key]}
                editable={isEditable}
                onChange={(val) => setSections((s) => ({ ...s, [key]: val }))}
              />
            ) : null
          )}
        </div>
      ) : (
        <div className="rounded-lg border bg-muted/30 p-4">
          {isEditable ? (
            <textarea
              aria-label="Appeal letter"
              className="min-h-96 w-full resize-y bg-transparent text-sm font-sans leading-relaxed focus:outline-none"
              value={appealText}
              onChange={(event) => setAppealText(event.target.value)}
            />
          ) : (
            <pre className="text-sm whitespace-pre-wrap font-sans leading-relaxed">{appeal.appeal_text}</pre>
          )}
        </div>
      )}

      {appeal.citations?.length ? (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1.5">Citations</p>
          <ul className="space-y-1">
            {appeal.citations.map((c: { source: string; reference: string }, i: number) => (
              <li key={i} className="text-xs text-muted-foreground">
                <span className="font-medium text-foreground">{c.source}: </span>{c.reference}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2 pt-1">
        {isEditable && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => saveMutation.mutate()}
            disabled={!isDirty || saveMutation.isPending}
            className="gap-1.5"
          >
            {saveMutation.isPending
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <Save className="h-3.5 w-3.5" />}
            {saveMutation.isPending ? "Saving..." : "Save changes"}
          </Button>
        )}
        {appeal.status === "draft" && (
          <Button
            size="sm"
            onClick={() => reviewMutation.mutate(appeal.id)}
            disabled={reviewMutation.isPending || isDirty}
            className="gap-1.5"
          >
            {reviewMutation.isPending
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <ClipboardCheck className="h-3.5 w-3.5" />}
            Send for Review
          </Button>
        )}
        {appeal.status === "review" && (
          <>
            <Button
              size="sm"
              onClick={() => approveMutation.mutate(appeal.id)}
              disabled={approveMutation.isPending || isDirty}
              className="gap-1.5"
            >
              {approveMutation.isPending
                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                : <ThumbsUp className="h-3.5 w-3.5" />}
              Approve
            </Button>
            <Button
              size="sm" variant="outline"
              onClick={() => rejectMutation.mutate(appeal.id)}
              disabled={rejectMutation.isPending}
              className="gap-1.5"
            >
              {rejectMutation.isPending
                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                : <XCircle className="h-3.5 w-3.5" />}
              Reject
            </Button>
          </>
        )}
        {appeal.status === "approved" && (
          <>
            <Button
              size="sm"
              onClick={() => electronicSubmission.mutate(appeal.id)}
              disabled={electronicSubmission.isPending}
              className="gap-1.5"
            >
              {electronicSubmission.isPending
                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                : <Send className="h-3.5 w-3.5" />}
              Send electronically
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                manualSubmission.reset();
                setManualOpen(true);
              }}
            >
              Record manual submission
            </Button>
          </>
        )}
        {appeal.status === "rejected" && (
          <Badge variant="destructive" className="gap-1">
            <XCircle className="h-3 w-3" /> Rejected — needs revision
          </Badge>
        )}
        {appeal.status === "submitted" && appeal.confirmation_number && (
          <Badge variant="success" className="gap-1">
            <CheckCircle className="h-3 w-3" /> Submitted · {appeal.confirmation_number}
          </Badge>
        )}
        {appeal.status === "submitted" && !appeal.confirmation_number && (
          <Badge variant="destructive">Unverified submission record</Badge>
        )}
        <Button
          size="sm" variant="ghost"
          onClick={() => { setAppeal(null); setMode("idle"); }}
        >
          Regenerate
        </Button>
      </div>
      {isEditable && isDirty && (
        <p className="text-xs text-amber-700">Save changes before continuing the approval workflow.</p>
      )}
      {saveMutation.isSuccess && !isDirty && (
        <p className="text-xs text-green-700">Saved as version {appeal.current_version}.</p>
      )}
      {saveMutation.isError && (
        <p className="rounded bg-destructive/10 px-3 py-2 text-sm text-destructive" role="alert">
          {getErrorMessage(saveMutation.error, "The appeal changes could not be saved.")}
        </p>
      )}
      {electronicSubmission.isError && (
        <p className="rounded bg-destructive/10 px-3 py-2 text-sm text-destructive" role="alert">
          {getErrorMessage(
            electronicSubmission.error,
            "The appeal could not be delivered electronically.",
          )}
        </p>
      )}
      <Dialog
        open={manualOpen}
        onOpenChange={(open) => {
          setManualOpen(open);
          if (!open) manualSubmission.reset();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Record manual submission</DialogTitle>
            <DialogDescription>
              Use this only after submitting through the payer portal, email, or another external channel. Atlas will record the result but will not transmit the appeal.
            </DialogDescription>
          </DialogHeader>
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              manualSubmission.mutate();
            }}
          >
            <div className="space-y-1.5">
              <Label htmlFor={`appeal-confirmation-${appeal.id}`}>Payer confirmation or tracking reference</Label>
              <Input
                id={`appeal-confirmation-${appeal.id}`}
                value={confirmationNumber}
                onChange={(event) => setConfirmationNumber(event.target.value)}
                maxLength={255}
                required
              />
            </div>
            {manualSubmission.isError && (
              <p className="rounded bg-destructive/10 px-3 py-2 text-sm text-destructive" role="alert">
                {getErrorMessage(manualSubmission.error, "The manual submission could not be recorded.")}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setManualOpen(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={!confirmationNumber.trim() || manualSubmission.isPending}
              >
                {manualSubmission.isPending ? "Recording..." : "Record submission"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
