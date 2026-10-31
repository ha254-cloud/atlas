import { Suspense } from "react";
import IntegrationDetail from "./integration-detail";

export default function IntegrationDetailPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading integration...</div>}>
      <IntegrationDetail />
    </Suspense>
  );
}
