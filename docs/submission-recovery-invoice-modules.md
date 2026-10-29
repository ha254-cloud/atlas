# Submission, Recovery, and Invoice Modules

## Ownership

The `app.submissions`, `app.recoveries`, and `app.invoices` packages each own their
repository, service, schemas, and router. Routers translate authenticated HTTP
requests, repositories perform organization-scoped queries, and services enforce
domain behavior.

Public API endpoints are:

- Payments: `GET /api/v1/payments`, `POST /api/v1/payments`,
  `GET /api/v1/payments/records`,
  `GET /api/v1/payments/records/{payment_id}`,
  `GET /api/v1/payments/records/{payment_id}/candidates`, and
  `POST /api/v1/payments/records/{payment_id}/match`;
  settlement evidence and allocation routes are documented in `API_SPEC.md`.
- Submissions: `GET /api/v1/submission-connectors`,
  `POST /api/v1/appeals/{appeal_id}/submissions`, `GET /api/v1/submissions`,
  `GET /api/v1/submissions/{submission_id}`,
  `POST /api/v1/submissions/{submission_id}/refresh`, and
  `POST /api/v1/submissions/{submission_id}/cancel`.
- Recoveries: `GET /api/v1/recoveries` and
  `POST /api/v1/recoveries/{recovery_id}/verify`.
- Invoices: `POST /api/v1/invoices/monthly`, `GET /api/v1/invoices`,
  `GET /api/v1/invoices/{invoice_id}`, `POST /api/v1/invoices/{invoice_id}/send`,
  and `POST /api/v1/invoices/{invoice_id}/paid`.

All endpoints require authentication and their configured claims, appeals, or
billing permission.

## Invariants

Submission is always an explicit human action. `SubmissionService.submit` rejects
an appeal unless it is already human-approved; approval and appeal generation do
not submit automatically.

When no explicit connector override is supplied, submission resolves the claim's
tenant-owned payer configuration first. The payer can bind a registered connector and
tenant integration or declare a manual, email, or portal workflow without pretending
that an automated transport exists. Payment reports from CSV, Excel, payer portals,
email, API/SFTP, and manual entry converge on the same payment and recovery services.
Unmatched payment candidates are deterministic and tenant-scoped: currency must
match, and confidence derives only from a claim reference in the canonical payload,
normalized payer name, and exact or within-outstanding amount evidence. A human with
`manage_billing` must supply a reason before confirming a match. The payment stores
the actor, method, reason, and timestamp; the API records before/after audit evidence
and publishes `payment.matched` only after commit. Foreign payment and claim IDs are
returned as not found.

The authenticated organization dependency supplies `organization_id` to each
service. Repositories scope tenant-owned `get`, `list`, and lookup queries by that
value. Request payloads do not accept an organization ID, and an identifier owned
by another organization is treated as not found.

Each canonical payment has at least one immutable settlement-evidence record. Source
ingestion hashes the canonical payload; finance can append independently hashed bank,
remittance, portal, or settlement-report evidence. Evidence amount and currency must
match the payment. KES is the Kenya-first operational currency; cross-currency
allocation fails closed. Payment ingestion snapshots effective configured payment
terms when present. Unmatched evidence without a fee contract retains the migration's
named legacy 30-day placeholder only to satisfy the persisted contract; the first
allocation requires a fee schedule and atomically replaces that placeholder with the
effective configured terms.

`payment_allocations` is the append-only source for bulk and partial allocation.
One request may atomically split a payment across up to 100 same-tenant claims.
Organization-scoped idempotency keys make safe retry explicit. A reversal or refund is
a positive compensating row linked to its original allocation and cannot exceed its
remaining amount. Refunds and reversals reduce retained recovery but never reopen cash
for reallocation. PostgreSQL serializes each payment, affected claims, original
allocation, and tenant/idempotency key before recomputing limits so concurrent finance
requests cannot overallocate cash, overpay a claim, or over-adjust an allocation.
Claim and Recovery amounts are projections of the immutable ledger.
If an adjustment affects an invoiced recovery, Payments synchronously asks Invoices
to issue a credit note in the same transaction because the financial correction must
be atomic; this is the documented exception to event-only cross-domain coordination.

## Events and Audit State

Submission lifecycle changes create submission event records and publish the
implemented submission lifecycle events. Status and payment changes also write
the existing claim timeline events, and payment detection publishes the existing
payment event before recovery attribution.

Payment ingestion and manual matching record actor, before/after values, reason,
organization, and correlation ID through the platform audit writer. Recovery
verification and invoice generation, sending, and payment update their persisted
domain records, but complete mutation audit and correlation-ID propagation are not
yet consistent across every recovery and invoice mutation and remain release-blocking
work.

## Partner Billing Readiness

The current payment-to-recovery path is an orchestration proof. A matched positive
payment in `paid` or `partial` state creates an unverified recovery, and a human must
verify it before monthly invoice inclusion. That rule is not sufficient evidence for
production success-fee billing. Deterministic candidate matching and human provenance
are now implemented together with append-only settlement evidence, atomic bulk/partial
allocation, reversal/refund, and immutable credit notes. Recovery dispute/resolution,
independent production reconciliation, and design-partner acceptance remain open.
Production contingency invoices remain blocked until those controls and
[ADR 0004](adr/0004-revenue-recovery-partner-operating-model.md) pass.

## Operations And Rollback

Migration `7c2e8a4f9b1d` creates the three directly tenant-owned ledgers, backfills
source evidence and allocations from canonical Payment/Recovery records, and changes
Recovery uniqueness from payment-only to payment-plus-claim. Deploy database, API,
workers, then web. Application rollback is compatible while the new tables remain.
Database downgrade is destructive and refuses to restore the old uniqueness rule when
a payment has multiple Recovery projections; it requires a backup and an approved
financial-data retention decision.

Monitor HTTP failures for settlement/allocation/adjustment routes, idempotency
conflicts, allocation batches rejected for insufficient/unmatched funds, credit-note
creation failures, and settlement evidence without allocation. Alert Finance
Operations and Platform Engineering when a tenant has five failures in 15 minutes or
unallocated settled cash remains open for 24 hours. Logs and events carry tenant and
correlation IDs but never raw settlement payloads or patient data. Event publication
currently occurs after commit through the platform's in-process event bus; a process
failure between commit and publication is not replayed because Atlas does not yet have
a transactional domain-event outbox. Immutable ledger and audit records remain the
recovery source of truth, and production event-driven automation remains blocked until
the shared event platform adds durable outbox delivery.

## Compatibility

Legacy imports from `app.services.submission_service`,
`app.services.recovery_service`, and `app.services.invoice_service` remain thin
re-exports of the module-owned services. New production code should import from
the owning module. `app.submissions.schemas` owns submission schemas and explicitly
re-exports the recovery and invoice schemas from their owning modules for import
compatibility; it does not duplicate their definitions. The payer-connectivity
service remains a compatibility subclass of the module-owned submission service.