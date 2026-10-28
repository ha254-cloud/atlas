# Submission, Recovery, and Invoice Modules

## Ownership

The `app.submissions`, `app.recoveries`, and `app.invoices` packages each own their
repository, service, schemas, and router. Routers translate authenticated HTTP
requests, repositories perform organization-scoped queries, and services enforce
domain behavior.

Public API endpoints are:

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

The authenticated organization dependency supplies `organization_id` to each
service. Repositories scope tenant-owned `get`, `list`, and lookup queries by that
value. Request payloads do not accept an organization ID, and an identifier owned
by another organization is treated as not found.

## Events and Audit State

Submission lifecycle changes create submission event records and publish the
implemented submission lifecycle events. Status and payment changes also write
the existing claim timeline events, and payment detection publishes the existing
payment event before recovery attribution.

Recovery verification and invoice generation, sending, and payment update their
persisted domain records. Complete mutation audit records containing actor,
before/after values, reason, and correlation ID are not implemented across these
modules yet. Correlation-ID propagation also remains release-blocking work.

## Partner Billing Readiness

The current payment-to-recovery path is an orchestration proof. A matched positive
payment in `paid` or `partial` state creates an unverified recovery, and a human must
verify it before monthly invoice inclusion. That rule is not sufficient evidence for
production success-fee billing: it does not yet model contractual scope, qualifying
interventions, bulk/partial allocations, settlement evidence, reversals, disputes, or
credits. Production contingency invoices remain blocked until the attribution ledger
and controls in [ADR 0004](adr/0004-revenue-recovery-partner-operating-model.md) pass.

## Compatibility

Legacy imports from `app.services.submission_service`,
`app.services.recovery_service`, and `app.services.invoice_service` remain thin
re-exports of the module-owned services. New production code should import from
the owning module. `app.submissions.schemas` owns submission schemas and explicitly
re-exports the recovery and invoice schemas from their owning modules for import
compatibility; it does not duplicate their definitions. The payer-connectivity
service remains a compatibility subclass of the module-owned submission service.