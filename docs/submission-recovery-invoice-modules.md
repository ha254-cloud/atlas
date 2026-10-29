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
  `POST /api/v1/payments/records/{payment_id}/match`.
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
are now implemented, but append-only bulk/partial allocations, stronger settlement
evidence, reversals/refunds, disputes, and credits remain open. Production contingency
invoices remain blocked until the attribution ledger and controls in
[ADR 0004](adr/0004-revenue-recovery-partner-operating-model.md) pass.

## Compatibility

Legacy imports from `app.services.submission_service`,
`app.services.recovery_service`, and `app.services.invoice_service` remain thin
re-exports of the module-owned services. New production code should import from
the owning module. `app.submissions.schemas` owns submission schemas and explicitly
re-exports the recovery and invoice schemas from their owning modules for import
compatibility; it does not duplicate their definitions. The payer-connectivity
service remains a compatibility subclass of the module-owned submission service.