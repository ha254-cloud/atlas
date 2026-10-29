"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Banknote, CheckCircle2, FileCheck2, Link2, ReceiptText, WalletCards } from "lucide-react";
import { Header } from "@/components/layout/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage } from "@/lib/api-client";
import { paymentsService } from "@/services/payments-service";
import { formatCurrency, formatDate, formatNumber } from "@/lib/utils";

export default function PaymentsPage() {
  const queryClient = useQueryClient();
  const [selectedPaymentId, setSelectedPaymentId] = useState<number | null>(null);
  const [reason, setReason] = useState("Matched against insurer payment advice");
  const [message, setMessage] = useState<string | null>(null);
  const { data, isLoading, isError } = useQuery({ queryKey: ["payments"], queryFn: paymentsService.list });
  const records = useQuery({ queryKey: ["payment-records"], queryFn: paymentsService.records });
  const candidates = useQuery({
    queryKey: ["payment-candidates", selectedPaymentId],
    queryFn: () => paymentsService.candidates(selectedPaymentId!),
    enabled: selectedPaymentId !== null,
  });
  const matchPayment = useMutation({
    mutationFn: (claimId: number) => paymentsService.match(selectedPaymentId!, claimId, reason),
    onSuccess: () => {
      setMessage("Payment matched. Recovery evidence is ready for finance verification.");
      setSelectedPaymentId(null);
      void queryClient.invalidateQueries({ queryKey: ["payment-records"] });
      void queryClient.invalidateQueries({ queryKey: ["payments"] });
    },
    onError: (error) => setMessage(getErrorMessage(error, "Payment could not be matched.")),
  });
  const unmatched = records.data?.filter((payment) => payment.claim_id === null) ?? [];
  const selectedPayment = records.data?.find((payment) => payment.id === selectedPaymentId);
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
          {unmatched.length ? unmatched.map((payment) => <TableRow key={payment.id}><TableCell className="text-muted-foreground">{formatDate(payment.payment_date)}</TableCell><TableCell className="font-mono text-xs font-medium">{payment.payment_reference}</TableCell><TableCell>{payment.payer_name}</TableCell><TableCell><Badge variant="outline">{payment.source.replaceAll("_", " ")}</Badge></TableCell><TableCell className="text-right font-semibold">{new Intl.NumberFormat("en-KE", { style: "currency", currency: payment.currency }).format(Number(payment.paid_amount))}</TableCell><TableCell><Button size="sm" variant="outline" onClick={() => { setMessage(null); setSelectedPaymentId(payment.id); }}><Link2 className="h-4 w-4" />Review</Button></TableCell></TableRow>) : <TableRow><TableCell colSpan={6} className="h-28 text-center"><CheckCircle2 className="mx-auto mb-2 h-5 w-5 text-emerald-600" /><p className="text-sm text-muted-foreground">No unmatched payment evidence.</p></TableCell></TableRow>}
        </TableBody></Table>}
      </CardContent></Card>
      <Card><CardContent className="p-0"><div className="flex items-center justify-between border-b px-5 py-4"><div><h2 className="text-sm font-semibold">Matched payment ledger</h2><p className="mt-0.5 text-xs text-muted-foreground">Payment evidence, verification status, and generated invoices</p></div><span className="text-xs text-muted-foreground">{metrics?.invoices_generated ?? 0} invoices generated</span></div>
        {isError ? <div className="py-16 text-center text-sm text-destructive">Payment records could not be loaded.</div> : isLoading ? <div className="space-y-3 p-5">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div> : <Table><TableHeader><TableRow><TableHead>Received</TableHead><TableHead>Claim</TableHead><TableHead>Payer</TableHead><TableHead className="text-right">Recovered</TableHead><TableHead className="text-right">Fee</TableHead><TableHead className="text-right">Net</TableHead><TableHead>Invoice</TableHead></TableRow></TableHeader><TableBody>
          {data?.payments.length ? data.payments.map((payment) => <TableRow key={payment.payment_id}><TableCell className="text-muted-foreground">{formatDate(payment.received_at)}</TableCell><TableCell><Link href={`/claims/${payment.claim_id}`} className="font-mono text-xs font-medium text-primary hover:underline">{payment.claim_number}</Link></TableCell><TableCell>{payment.payer}</TableCell><TableCell className="text-right font-medium">{payment.recovery_verified ? formatCurrency(payment.recovered_amount, payment.currency) : <Badge variant="outline">Awaiting verification</Badge>}</TableCell><TableCell className="text-right text-muted-foreground">{payment.recovery_verified ? formatCurrency(payment.atlas_fee, payment.currency) : "—"}</TableCell><TableCell className="text-right font-semibold">{payment.recovery_verified ? formatCurrency(payment.net_amount, payment.currency) : "—"}</TableCell><TableCell>{payment.invoice_generated ? <Badge variant="success"><FileCheck2 className="mr-1 h-3 w-3" />Generated</Badge> : <Badge variant="outline">Pending</Badge>}</TableCell></TableRow>) : <TableRow><TableCell colSpan={7} className="h-40 text-center"><Banknote className="mx-auto mb-2 h-6 w-6 text-muted-foreground/50" /><p className="text-sm text-muted-foreground">Matched payment evidence will appear here.</p></TableCell></TableRow>}
        </TableBody></Table>}
      </CardContent></Card>
      <Dialog open={selectedPaymentId !== null} onOpenChange={(open) => { if (!open) setSelectedPaymentId(null); }}><DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>Reconcile payment evidence</DialogTitle><DialogDescription>{selectedPayment ? `${selectedPayment.payment_reference} from ${selectedPayment.payer_name}` : "Review deterministic claim candidates."}</DialogDescription></DialogHeader>
        <div className="space-y-4"><div><label htmlFor="matching-reason" className="text-sm font-medium">Finance reason</label><Textarea id="matching-reason" value={reason} onChange={(event) => setReason(event.target.value)} className="mt-1" maxLength={500} /></div>
          <div className="max-h-80 overflow-y-auto border-y">{candidates.isLoading ? <div className="space-y-3 py-4">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div> : candidates.isError ? <div className="py-8 text-center text-sm text-destructive">Candidate claims could not be loaded.</div> : candidates.data?.length ? candidates.data.map((candidate) => <div key={candidate.claim_id} className="flex items-center justify-between gap-4 border-b py-3 last:border-b-0"><div className="min-w-0"><div className="flex items-center gap-2"><Link href={`/claims/${candidate.claim_id}`} className="font-mono text-xs font-semibold text-primary hover:underline">{candidate.claim_number}</Link><Badge variant="outline">{candidate.confidence}% match</Badge></div><p className="mt-1 text-xs text-muted-foreground">{candidate.payer_name} · Outstanding {formatCurrency(Number(candidate.outstanding_amount), candidate.currency)} · {candidate.reasons.map((item) => item.replaceAll("_", " ")).join(", ")}</p></div><Button size="sm" disabled={!reason.trim() || matchPayment.isPending} onClick={() => matchPayment.mutate(candidate.claim_id)}>Confirm</Button></div>) : <div className="py-10 text-center"><AlertCircle className="mx-auto mb-2 h-5 w-5 text-amber-600" /><p className="text-sm font-medium">No reliable candidate found</p><p className="mt-1 text-xs text-muted-foreground">Review the payer advice and claim identifiers before matching.</p></div>}</div>
        </div>
      </DialogContent></Dialog>
    </div></div></div>
  );
}
