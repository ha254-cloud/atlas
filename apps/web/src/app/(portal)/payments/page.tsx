"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Banknote, CheckCircle2, FileCheck2, Gavel, Link2, ReceiptText, ShieldCheck, WalletCards } from "lucide-react";
import { Header } from "@/components/layout/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage } from "@/lib/api-client";
import { paymentsService } from "@/services/payments-service";
import { formatCurrency, formatDate, formatNumber } from "@/lib/utils";

export default function PaymentsPage() {
  const queryClient = useQueryClient();
  const [selectedPaymentId, setSelectedPaymentId] = useState<number | null>(null);
  const [selectedRecoveryId, setSelectedRecoveryId] = useState<number | null>(null);
  const [reason, setReason] = useState("Matched against insurer payment advice");
  const [governanceReason, setGovernanceReason] = useState("Finance review of recovery evidence");
  const [interventionType, setInterventionType] = useState("underpayment_challenge");
  const [interventionOccurredAt, setInterventionOccurredAt] = useState("");
  const [resolutionOutcome, setResolutionOutcome] = useState<"upheld" | "partially_upheld" | "accepted">("partially_upheld");
  const [resolutionEligibleAmount, setResolutionEligibleAmount] = useState("");
  const [allocationAmounts, setAllocationAmounts] = useState<Record<number, string>>({});
  const [allocationKey, setAllocationKey] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const { data, isLoading, isError } = useQuery({ queryKey: ["payments"], queryFn: paymentsService.list });
  const records = useQuery({ queryKey: ["payment-records"], queryFn: paymentsService.records });
  const candidates = useQuery({
    queryKey: ["payment-candidates", selectedPaymentId],
    queryFn: () => paymentsService.candidates(selectedPaymentId!),
    enabled: selectedPaymentId !== null,
  });
  const interventions = useQuery({
    queryKey: ["recovery-interventions", selectedRecoveryId],
    queryFn: () => paymentsService.interventions(selectedRecoveryId!),
    enabled: selectedRecoveryId !== null,
  });
  const disputes = useQuery({
    queryKey: ["recovery-disputes", selectedRecoveryId],
    queryFn: () => paymentsService.disputes(selectedRecoveryId!),
    enabled: selectedRecoveryId !== null,
  });
  const refreshGovernance = () => {
    void queryClient.invalidateQueries({ queryKey: ["payments"] });
    void queryClient.invalidateQueries({ queryKey: ["recovery-interventions", selectedRecoveryId] });
    void queryClient.invalidateQueries({ queryKey: ["recovery-disputes", selectedRecoveryId] });
  };
  const allocatePayment = useMutation({
    mutationFn: () => paymentsService.allocate(
      selectedPaymentId!,
      Object.entries(allocationAmounts)
        .filter(([, amount]) => Number(amount) > 0)
        .map(([claimId, amount]) => ({ claim_id: Number(claimId), amount })),
      reason,
      allocationKey,
    ),
    onSuccess: () => {
      setMessage("Payment allocated. Recovery evidence is ready for finance verification.");
      setSelectedPaymentId(null);
      setAllocationAmounts({});
      setAllocationKey("");
      void queryClient.invalidateQueries({ queryKey: ["payment-records"] });
      void queryClient.invalidateQueries({ queryKey: ["payments"] });
    },
    onError: (error) => setMessage(getErrorMessage(error, "Payment could not be allocated.")),
  });
  const verifyRecovery = useMutation({
    mutationFn: () => paymentsService.verifyRecovery(selectedRecoveryId!, governanceReason),
    onSuccess: () => {
      setMessage("Recovery verified. A different finance approver must decide attribution.");
      refreshGovernance();
    },
    onError: (error) => setMessage(getErrorMessage(error, "Recovery could not be verified.")),
  });
  const recordIntervention = useMutation({
    mutationFn: () => paymentsService.recordIntervention(
      governedRecovery!.claim_id,
      interventionType,
      new Date(interventionOccurredAt).toISOString(),
      governanceReason,
    ),
    onSuccess: () => {
      setMessage("Immutable Atlas intervention evidence recorded.");
      refreshGovernance();
    },
    onError: (error) => setMessage(getErrorMessage(error, "Intervention could not be recorded.")),
  });
  const approveAttribution = useMutation({
    mutationFn: () => paymentsService.decideAttribution(
      selectedRecoveryId!,
      interventions.data![interventions.data!.length - 1].id,
      governanceReason,
    ),
    onSuccess: () => {
      setMessage("Recovery attribution approved with snapshotted KES fee terms.");
      refreshGovernance();
    },
    onError: (error) => setMessage(getErrorMessage(error, "Attribution could not be approved.")),
  });
  const openDispute = useMutation({
    mutationFn: () => paymentsService.openDispute(selectedRecoveryId!, governanceReason),
    onSuccess: () => {
      setMessage("Recovery attribution dispute opened. Billing eligibility is paused.");
      refreshGovernance();
    },
    onError: (error) => setMessage(getErrorMessage(error, "Dispute could not be opened.")),
  });
  const resolveDispute = useMutation({
    mutationFn: () => paymentsService.resolveDispute(
      selectedRecoveryId!,
      disputes.data!.find((item) => item.resolution === null)!.id,
      resolutionOutcome,
      resolutionOutcome === "partially_upheld" ? resolutionEligibleAmount : null,
      governanceReason,
    ),
    onSuccess: (result) => {
      setMessage(result.credit_note_id ? "Dispute resolved and an immutable invoice credit note was issued." : "Dispute resolved with a new attribution version.");
      refreshGovernance();
    },
    onError: (error) => setMessage(getErrorMessage(error, "Dispute could not be resolved.")),
  });
  const unmatched = records.data?.filter((payment) => Number(payment.unallocated_amount) > 0) ?? [];
  const selectedPayment = records.data?.find((payment) => payment.id === selectedPaymentId);
  const governedRecovery = data?.payments.find((payment) => payment.recovery_id === selectedRecoveryId);
  const unresolvedDispute = disputes.data?.find((item) => item.resolution === null);
  const metrics = data?.summary;
  const cards: Array<[string, string, React.ElementType]> = [
    ["Total recovered", formatCurrency(metrics?.total_recovered ?? 0), Banknote],
    ["Net recovered", formatCurrency(metrics?.net_recovered ?? 0), WalletCards],
    ["Atlas fees", formatCurrency(metrics?.total_fees ?? 0), ReceiptText],
    ["Payments recorded", formatNumber(metrics?.payment_count ?? 0), CheckCircle2],
  ];

  return (
    <div className="flex h-full flex-col"><Header title="Payments" /><div className="flex-1 overflow-y-auto p-4 sm:p-6"><div className="mx-auto max-w-7xl space-y-6">
      {message ? <div className="border-l-2 border-primary bg-muted/50 px-4 py-3 text-sm">{message}</div> : null}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{isLoading ? Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />) : cards.map(([label, value, Icon]) => <Card key={label}><CardContent className="flex items-start justify-between p-5"><div><p className="text-xs font-medium uppercase text-muted-foreground">{label}</p><p className="mt-1 text-2xl font-bold">{value}</p></div><div className="rounded-md bg-emerald-50 p-2 text-emerald-700"><Icon className="h-4 w-4" /></div></CardContent></Card>)}</div>
      <Card><CardContent className="p-0"><div className="flex items-center justify-between border-b px-5 py-4"><div><h2 className="text-sm font-semibold">Needs reconciliation</h2><p className="mt-0.5 text-xs text-muted-foreground">Payment evidence that has not been linked to a claim</p></div><Badge variant={unmatched.length ? "outline" : "success"}>{unmatched.length} open</Badge></div>
        {records.isError ? <div className="py-12 text-center text-sm text-destructive">Payment evidence could not be loaded.</div> : records.isLoading ? <div className="space-y-3 p-5">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div> : <Table><TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Reference</TableHead><TableHead>Payer</TableHead><TableHead>Source</TableHead><TableHead className="text-right">Amount</TableHead><TableHead className="w-28" /></TableRow></TableHeader><TableBody>
          {unmatched.length ? unmatched.map((payment) => <TableRow key={payment.id}><TableCell className="text-muted-foreground">{formatDate(payment.payment_date)}</TableCell><TableCell className="font-mono text-xs font-medium">{payment.payment_reference}</TableCell><TableCell>{payment.payer_name}</TableCell><TableCell><Badge variant="outline">{payment.source.replaceAll("_", " ")}</Badge></TableCell><TableCell className="text-right font-semibold">{new Intl.NumberFormat("en-KE", { style: "currency", currency: payment.currency }).format(Number(payment.unallocated_amount))}</TableCell><TableCell><Button size="sm" variant="outline" onClick={() => { setMessage(null); setAllocationAmounts({}); setAllocationKey(crypto.randomUUID()); setSelectedPaymentId(payment.id); }}><Link2 className="h-4 w-4" />Review</Button></TableCell></TableRow>) : <TableRow><TableCell colSpan={6} className="h-28 text-center"><CheckCircle2 className="mx-auto mb-2 h-5 w-5 text-emerald-600" /><p className="text-sm text-muted-foreground">No unmatched payment evidence.</p></TableCell></TableRow>}
        </TableBody></Table>}
      </CardContent></Card>
      <Card><CardContent className="p-0"><div className="flex items-center justify-between border-b px-5 py-4"><div><h2 className="text-sm font-semibold">Matched payment ledger</h2><p className="mt-0.5 text-xs text-muted-foreground">Payment evidence, verification status, and generated invoices</p></div><span className="text-xs text-muted-foreground">{metrics?.invoices_generated ?? 0} invoices generated</span></div>
        {isError ? <div className="py-16 text-center text-sm text-destructive">Payment records could not be loaded.</div> : isLoading ? <div className="space-y-3 p-5">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div> : <Table><TableHeader><TableRow><TableHead>Received</TableHead><TableHead>Claim</TableHead><TableHead>Payer</TableHead><TableHead className="text-right">Recovered</TableHead><TableHead>Attribution</TableHead><TableHead className="text-right">Fee</TableHead><TableHead className="text-right">Net</TableHead><TableHead>Invoice</TableHead><TableHead className="w-24" /></TableRow></TableHeader><TableBody>
          {data?.payments.length ? data.payments.map((payment) => <TableRow key={`${payment.payment_id}-${payment.recovery_id}`}><TableCell className="text-muted-foreground">{formatDate(payment.received_at)}</TableCell><TableCell><Link href={`/claims/${payment.claim_id}`} className="font-mono text-xs font-medium text-primary hover:underline">{payment.claim_number}</Link></TableCell><TableCell>{payment.payer}</TableCell><TableCell className="text-right font-medium">{payment.recovery_verified ? formatCurrency(payment.recovered_amount, payment.currency) : <Badge variant="outline">Awaiting verification</Badge>}</TableCell><TableCell>{payment.attribution_status ? <Badge variant={payment.attribution_status === "eligible" ? "success" : "outline"}>{payment.attribution_status.replaceAll("_", " ")}</Badge> : <Badge variant="outline">Unreviewed</Badge>}</TableCell><TableCell className="text-right text-muted-foreground">{payment.recovery_verified ? formatCurrency(payment.atlas_fee, payment.currency) : "—"}</TableCell><TableCell className="text-right font-semibold">{payment.recovery_verified ? formatCurrency(payment.net_amount, payment.currency) : "—"}</TableCell><TableCell>{payment.invoice_generated ? <Badge variant="success"><FileCheck2 className="mr-1 h-3 w-3" />Generated</Badge> : <Badge variant="outline">Pending</Badge>}</TableCell><TableCell>{payment.recovery_id ? <Button size="sm" variant="outline" onClick={() => { setSelectedRecoveryId(payment.recovery_id); setGovernanceReason("Finance review of recovery evidence"); setInterventionOccurredAt(payment.received_at.slice(0, 16)); setMessage(null); }}><ShieldCheck className="h-4 w-4" />Review</Button> : null}</TableCell></TableRow>) : <TableRow><TableCell colSpan={9} className="h-40 text-center"><Banknote className="mx-auto mb-2 h-6 w-6 text-muted-foreground/50" /><p className="text-sm text-muted-foreground">Matched payment evidence will appear here.</p></TableCell></TableRow>}
        </TableBody></Table>}
      </CardContent></Card>
      <Dialog open={selectedPaymentId !== null} onOpenChange={(open) => { if (!open) setSelectedPaymentId(null); }}><DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>Reconcile payment evidence</DialogTitle><DialogDescription>{selectedPayment ? `${selectedPayment.payment_reference} from ${selectedPayment.payer_name}` : "Review deterministic claim candidates."}</DialogDescription></DialogHeader>
        <div className="space-y-4"><div><label htmlFor="matching-reason" className="text-sm font-medium">Finance reason</label><Textarea id="matching-reason" value={reason} onChange={(event) => setReason(event.target.value)} className="mt-1" maxLength={500} /></div>
          <div className="max-h-80 overflow-y-auto border-y">{candidates.isLoading ? <div className="space-y-3 py-4">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div> : candidates.isError ? <div className="py-8 text-center text-sm text-destructive">Candidate claims could not be loaded.</div> : candidates.data?.length ? candidates.data.map((candidate) => <div key={candidate.claim_id} className="flex items-center justify-between gap-4 border-b py-3 last:border-b-0"><div className="min-w-0"><div className="flex items-center gap-2"><Link href={`/claims/${candidate.claim_id}`} className="font-mono text-xs font-semibold text-primary hover:underline">{candidate.claim_number}</Link><Badge variant="outline">{candidate.confidence}% match</Badge></div><p className="mt-1 text-xs text-muted-foreground">{candidate.payer_name} · Outstanding {formatCurrency(Number(candidate.outstanding_amount), candidate.currency)} · {candidate.reasons.map((item) => item.replaceAll("_", " ")).join(", ")}</p></div><Input aria-label={`Allocation for ${candidate.claim_number}`} className="w-32 text-right" inputMode="decimal" min="0" max={candidate.outstanding_amount} step="0.01" placeholder="KES 0.00" type="number" value={allocationAmounts[candidate.claim_id] ?? ""} onChange={(event) => setAllocationAmounts((current) => ({ ...current, [candidate.claim_id]: event.target.value }))} /></div>) : <div className="py-10 text-center"><AlertCircle className="mx-auto mb-2 h-5 w-5 text-amber-600" /><p className="text-sm font-medium">No reliable candidate found</p><p className="mt-1 text-xs text-muted-foreground">Review the payer advice and claim identifiers before matching.</p></div>}</div>
          <div className="flex items-center justify-between gap-3"><p className="text-xs text-muted-foreground">Allocations are atomic and may not exceed the unallocated payment amount.</p><Button disabled={!reason.trim() || allocatePayment.isPending || !Object.values(allocationAmounts).some((amount) => Number(amount) > 0)} onClick={() => allocatePayment.mutate()}>{allocatePayment.isPending ? "Allocating…" : "Allocate selected"}</Button></div>
        </div>
      </DialogContent></Dialog>
      <Dialog open={selectedRecoveryId !== null} onOpenChange={(open) => { if (!open) setSelectedRecoveryId(null); }}><DialogContent className="max-w-xl"><DialogHeader><DialogTitle>Govern recovery attribution</DialogTitle><DialogDescription>{governedRecovery ? `${governedRecovery.claim_number} · ${formatCurrency(governedRecovery.recovered_amount, governedRecovery.currency)}` : "Review recovery evidence and approval state."}</DialogDescription></DialogHeader>
        {governedRecovery ? <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 rounded-md border bg-muted/30 p-3 text-sm"><div><p className="text-xs text-muted-foreground">Verification</p><p className="font-medium">{governedRecovery.recovery_verified ? "Verified" : "Pending"}</p></div><div><p className="text-xs text-muted-foreground">Attribution</p><p className="font-medium capitalize">{governedRecovery.attribution_status ?? "Unreviewed"}</p></div></div>
          <div><label htmlFor="governance-reason" className="text-sm font-medium">Decision reason</label><Textarea id="governance-reason" value={governanceReason} onChange={(event) => setGovernanceReason(event.target.value)} className="mt-1" maxLength={500} /></div>
          {!governedRecovery.recovery_verified ? <Button className="w-full" disabled={!governanceReason.trim() || verifyRecovery.isPending} onClick={() => verifyRecovery.mutate()}><ShieldCheck className="h-4 w-4" />{verifyRecovery.isPending ? "Verifying…" : "Verify recovery"}</Button> : null}
          {governedRecovery.recovery_verified && !interventions.data?.length ? <div className="space-y-3 rounded-md border p-3"><p className="text-sm font-medium">Record Atlas intervention evidence</p><select aria-label="Intervention type" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={interventionType} onChange={(event) => setInterventionType(event.target.value)}><option value="underpayment_challenge">Underpayment challenge</option><option value="appeal_submission">Appeal submission</option><option value="corrected_resubmission">Corrected resubmission</option><option value="missing_document_response">Missing document response</option><option value="documented_follow_up">Documented follow-up</option></select><Input aria-label="Intervention occurred at" type="datetime-local" value={interventionOccurredAt} onChange={(event) => setInterventionOccurredAt(event.target.value)} /><Button className="w-full" disabled={!governanceReason.trim() || !interventionOccurredAt || recordIntervention.isPending} onClick={() => recordIntervention.mutate()}>{recordIntervention.isPending ? "Recording…" : "Record immutable intervention"}</Button></div> : null}
          {governedRecovery.recovery_verified && !governedRecovery.attribution_status && interventions.data?.length ? <div className="space-y-2 rounded-md border border-amber-200 bg-amber-50/40 p-3"><p className="text-sm font-medium">Independent attribution approval</p><p className="text-xs text-muted-foreground">The approver must be different from the person who verified this recovery.</p><Button className="w-full" disabled={!governanceReason.trim() || approveAttribution.isPending} onClick={() => approveAttribution.mutate()}><CheckCircle2 className="h-4 w-4" />{approveAttribution.isPending ? "Approving…" : "Approve eligible attribution"}</Button></div> : null}
          {governedRecovery.attribution_status && governedRecovery.attribution_status !== "disputed" ? <Button className="w-full" variant="outline" disabled={!governanceReason.trim() || openDispute.isPending} onClick={() => openDispute.mutate()}><Gavel className="h-4 w-4" />{openDispute.isPending ? "Opening…" : "Open attribution dispute"}</Button> : null}
          {governedRecovery.attribution_status === "disputed" && unresolvedDispute ? <div className="space-y-3 rounded-md border border-amber-200 p-3"><p className="text-sm font-medium">Resolve disputed attribution</p><p className="text-xs text-muted-foreground">A different finance user from the dispute opener must resolve it.</p><select aria-label="Dispute outcome" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={resolutionOutcome} onChange={(event) => setResolutionOutcome(event.target.value as typeof resolutionOutcome)}><option value="upheld">Upheld</option><option value="partially_upheld">Partially upheld</option><option value="accepted">Accepted</option></select>{resolutionOutcome === "partially_upheld" ? <Input aria-label="Resolved eligible amount" type="number" min="0" step="0.01" placeholder="KES eligible amount" value={resolutionEligibleAmount} onChange={(event) => setResolutionEligibleAmount(event.target.value)} /> : null}<Button className="w-full" disabled={!governanceReason.trim() || (resolutionOutcome === "partially_upheld" && !(Number(resolutionEligibleAmount) > 0)) || resolveDispute.isPending} onClick={() => resolveDispute.mutate()}>{resolveDispute.isPending ? "Resolving…" : "Resolve dispute"}</Button></div> : null}
        </div> : <Skeleton className="h-48" />}
      </DialogContent></Dialog>
    </div></div></div>
  );
}
