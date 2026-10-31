# Atlas Release Plan

Last reviewed: 2026-10-31

## Status Vocabulary

- Implemented: behavior exists and has focused executable evidence.
- Pilot-ready: implemented, documented, observable, secured, and exercised in a production-like environment.
- Production-ready: capacity, availability, recovery, security, and operations gates have passed.
- Enterprise-ready: contractual controls, scale, interoperability, compliance evidence, and support model have passed.

These labels are not interchangeable.

## Current Baseline

Implemented vertical workflow:

```text
CSV claim import -> AI analysis -> AI appeal -> human approval
-> connector submission -> status polling -> payment detection
-> recovery attribution -> verification -> monthly invoice -> dashboard
```

Current evidence includes a 591/591 complete backend regression pass, production web build/type-check, a verified 29-route static web export for Apache-compatible `public_html` hosting, PostgreSQL migrations through `d4f7a2c6e9b3`, and responsive dashboard checks. The HCode synthetic staging deployment is live at `api.atlashealth.ke` with managed PostgreSQL/Redis readiness, HTTPS, frontend-origin CORS, login, restart-safe demo seeding, and API/Celery worker/Celery beat supervision verified. Daily PostgreSQL and Redis schedules retain backups for seven days, and manual artifacts reached `Ready`; an isolated restore rehearsal is still open. In-container ClamAV failed its deployment check when `freshclam` was killed by signal 9, so malware scanning remains disabled until a private adequately sized scanner is available. AI budget enforcement is implemented, but hosted AI remains disabled until the displayed provider key is rotated and replaced. Durable S3 storage, centralized monitoring/alerting, SMTP, production-like E2E, and governance approval remain open. Mock submission proves orchestration but is not evidence of a real payer integration.

Migration `d4f7a2c6e9b3` adds a composite `(organization_id, created_at)` index and `pg_trgm` GIN indexes (`claims.claim_number`, `patients.first_name`/`last_name`, `payers.name`) backing the claims list/search query, and the claims list/detail repository query was changed from a blanket `joinedload` of every relation to `joinedload` for many-to-one/one-to-one relations plus `selectinload` for one-to-many collections, removing an unused `documents`/`organization` eager-load and the row-multiplication caused by joining multiple one-to-many collections in a single query. Deployment impact: the migration is additive (new indexes only, no column/table changes) and backward compatible; `CREATE INDEX` on `claims`/`patients`/`payers` should be scheduled during low-traffic windows on large datasets since Postgres index builds take a read lock briefly even without `CONCURRENTLY`. The complete backend suite now passes 591/591, including claim repository/service, architecture-contract, HCode deployment, governed recovery attribution, and submission-to-invoice regressions.

## Milestone 1: One-Hospital Pilot

### Outcome

One named hospital can run a deliberately constrained recovery workflow with trained users, defined support ownership, auditable outcomes, and a documented rollback path.

### Supported Scope

- One hospital organization
- CSV and scheduled SFTP claim ingestion
- Human-reviewed AI analysis and appeal generation
- Explicit human submission action
- Mock connector for internal validation, then one market-appropriate real connector before live payer traffic
- Payment attribution, recovery verification, and itemized invoices

### Blocking Work

- [ ] Complete module layering for submissions, recoveries, and invoices with dedicated repositories and module-owned services/docs.
- [ ] Complete appeal-evidence document upload, storage, retrieval, retention, and access-control workflow.
- [ ] Thread correlation IDs through HTTP requests, Celery tasks, events, audit records, and external calls.
- [ ] Add audit before/after/reason fields consistently for material mutations.
- [ ] Validate required production secrets at startup, including integration encryption and JWT signing keys.
- [ ] Replace hardcoded recovery fee defaults and schedules with versioned organization configuration.
- [ ] Implement one real submission connector selected for the pilot market and pass contract certification/sandbox tests.
- [ ] Add backup/restore rehearsal, alerting, support runbook, and incident ownership.
- [ ] Run a production-like E2E using non-synthetic connector acknowledgements and payment messages.
- [ ] Complete privacy/security review and hospital data-processing agreements.

### Exit Criteria

- Zero cross-tenant access findings in automated and manual tests.
- All pilot workflows are traceable by correlation ID from request to invoice.
- Restore rehearsal meets documented RPO/RTO.
- Alert delivery and incident runbook are exercised.
- Pilot connector meets agreed success/error/timeout behavior.
- Hospital acceptance test is signed by clinical revenue-cycle and security owners.

## Milestone 2: Production SaaS

### Outcome

Multiple hospitals can operate safely on a scalable, monitored, billable service with reliable integrations and repeatable onboarding.

### Required Capabilities

- [ ] Redis or broker-backed multi-instance event delivery and notifications.
- [ ] Durable outbox/inbox pattern for event publication and idempotent consumption.
- [ ] Signed webhook delivery with retry, replay protection, and dead-letter operations.
- [ ] Per-organization versioned settings for AI, fees, rules, workflows, and integrations.
- [ ] Key rotation, API-key expiry, session controls, dependency scanning, and regular penetration testing.
- [ ] Centralized structured logs, traces, metrics, SLOs, alerts, and cost monitoring.
- [ ] Automated tenant provisioning, plans, metering, billing, and customer invoice reconciliation.
- [ ] High-availability database, tested backups, disaster recovery, and zero-downtime migration strategy.
- [ ] Data retention/export/deletion workflows and compliance evidence collection.
- [ ] At least one production integration with measured availability and support ownership.

### Exit Criteria

- Ten production tenants onboard through the same documented process.
- Published SLOs are met for four consecutive weeks.
- Disaster recovery and security incident exercises pass.
- No unresolved critical/high security findings.
- Billing and recovery attribution reconcile to source payments.

## Milestone 3: Enterprise Platform

### Outcome

Atlas supports enterprise interoperability, controls, scale, advanced intelligence, and contractual support requirements.

### Required Capabilities

- [ ] Multiple certified clearinghouse/EHR/FHIR/X12 connectors driven by customer demand.
- [ ] Enterprise SSO/SAML/OIDC, SCIM, delegated administration, and configurable segregation of duties.
- [ ] Policy/rule versioning with approvals, simulation, effective dates, and rollback.
- [ ] Model governance: evaluation sets, drift monitoring, approval, rollback, and tenant/provider controls.
- [ ] Outcome-learning pipeline with bias, quality, and provenance controls.
- [ ] Advanced financial reconciliation, contract modeling, forecasting, and executive analytics.
- [ ] Regional data residency, retention policies, legal hold, and export controls.
- [ ] Enterprise audit exports, evidence packages, support SLAs, and change-management controls.

### Exit Criteria

- Enterprise design partner operates at agreed volume for three months.
- Connector and financial reconciliation accuracy meet contractual thresholds.
- External security/compliance assessment passes.
- Model and policy changes are fully reproducible and auditable.

## Sequencing Rule

Work may be researched ahead of its milestone, but implementation does not bypass an open release blocker merely because a later feature is more visible. Any exception requires an ADR and named owner.

## Readiness Ownership

Each milestone must assign owners for product, engineering, security/privacy, data/AI governance, operations, finance, and customer acceptance before release approval.
