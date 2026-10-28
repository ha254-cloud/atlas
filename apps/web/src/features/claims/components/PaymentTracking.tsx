"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertCircle, CheckCircle, Clock, ArrowRight, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { formatCurrency } from "@/lib/utils";
import { paymentsService } from "@/services/payments-service";

interface Props {
  claimId: number;
}

export function PaymentTracking({ claimId }: Props) {
  const { data, dataUpdatedAt, isLoading, isError } = useQuery({
    queryKey: ["payment-tracking", claimId],
    queryFn: () => paymentsService.trackingForClaim(claimId),
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
  });

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-sm">Payment Tracking</CardTitle>
          <span className="text-xs text-muted-foreground">
            {dataUpdatedAt ? `Updated ${new Date(dataUpdatedAt).toLocaleTimeString()}` : "Checking..."}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Checking payment evidence...
          </div>
        ) : isError || !data ? (
          <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive" role="alert">
            <AlertCircle className="h-4 w-4" /> Payment tracking could not be loaded.
          </div>
        ) : <><div className="flex items-center gap-1 flex-wrap">
          {data.stages.map((step, i) => (
            <div key={i} className="flex items-center gap-1">
              <div className={cn(
                "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium",
                step.state === "complete"
                  ? "bg-green-100 text-green-800"
                  : step.state === "current"
                    ? "bg-blue-100 text-blue-800"
                    : step.state === "failed"
                      ? "bg-red-100 text-red-800"
                    : "bg-muted text-muted-foreground",
              )}>
                {step.state === "complete"
                  ? <CheckCircle className="h-3 w-3" />
                  : step.state === "failed"
                    ? <AlertCircle className="h-3 w-3" />
                  : step.state === "current"
                    ? <Clock className="h-3 w-3 animate-pulse" />
                    : <Clock className="h-3 w-3 opacity-40" />}
                {step.label}
              </div>
              {i < data.stages.length - 1 && (
                <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
              )}
            </div>
          ))}
        </div>

        {data.payment_received && (
          <div className="mt-4 grid gap-3 rounded-lg border border-green-100 bg-green-50 p-3 text-sm sm:grid-cols-3">
            <div>
              <p className="text-xs text-muted-foreground">Payment evidence</p>
              <p className="font-bold text-green-700">
                {data.payment_amount != null && data.payment_currency
                  ? formatCurrency(data.payment_amount, data.payment_currency)
                  : "Multiple currencies"}
              </p>
            </div>
            {data.recovery_verified && data.recovered_amount != null && (
              <div>
                <p className="text-xs text-muted-foreground">Verified recovery</p>
                <p className="font-semibold">
                  {formatCurrency(data.recovered_amount, data.payment_currency ?? "KES")}
                </p>
              </div>
            )}
            <div>
              <p className="text-xs text-muted-foreground">Invoice</p>
              <p className="font-medium">{data.invoice_created ? data.invoice_number : "Pending verification"}</p>
            </div>
          </div>
        )}
        </>}</CardContent>
    </Card>
  );
}
