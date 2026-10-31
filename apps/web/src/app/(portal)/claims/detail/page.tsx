import { Suspense } from "react";
import ClaimDetail from "./claim-detail";

export default function ClaimDetailPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading claim...</div>}>
      <ClaimDetail />
    </Suspense>
  );
}
