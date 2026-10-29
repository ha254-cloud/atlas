# Atlas Release Plan

Last reviewed: 2026-08-01

## Status Vocabulary

- Implemented: behavior exists and has focused executable evidence.
- Pilot-ready: implemented, documented, observable, secured, and exercised in a production-like environment.
- Production-ready: capacity, availability, recovery, security, and operations gates have passed.
- Enterprise-ready: contractual controls, scale, interoperability, compliance evidence, and support model have passed.

These labels are not interchangeable.

## Current Baseline

Implemented orchestration workflow:

```text
CSV claim import -> AI analysis -> AI appeal -> human approval
-> connector submission -> status polling -> payment detection
-> recovery attribution -> verification -> monthly invoice -> dashboard
```

This proves the technical sequence with deterministic test data. The current
payment-to-recovery rule is not approved for production contingency billing; the
evidence, allocation, intervention, attribution, dispute, and credit controls in
ADR 0004 remain release blockers.

Current evidence includes a passing backend regression, production web build/type-check,
PostgreSQL migration rehearsals, a schema-level tenant ownership
contract, versioned typed organization settings, API-level product entitlements,
and responsive dashboard checks. AI usage and agent execution logs require
organization attribution. Live AI provider success remains dependent on provider
quota. Mock submission proves orchestration but is not evidence of a real payer
integration.

Atlas v1 is Kenya-first and is positioned as an AI Revenue Recovery Platform, not a
replacement claims-management system. The implemented payer control plane supports
tenant-scoped routing metadata and manual-safe defaults. SHA, Jubilee, AAR, Britam,
and CIC connectors are roadmap targets, not certified integrations.

Workflow Engine 2.0 is implemented with tenant-scoped configurable graphs,
typed domain triggers, a durable workflow event inbox, idempotent execution,
retry/dead-letter handling, human approval, audited definition changes, and an
operator UI. Focused backend tests and PostgreSQL upgrade/downgrade rehearsal
pass. Production alert delivery, automated dead-letter replay, and transactional
publication from every originating domain transaction remain open operations
work, so this capability is implemented rather than pilot-ready.

## Milestone 1: First Design-Partner Pilot

### Outcome

One named healthcare organization can run a deliberately constrained recovery
workflow on the same multi-tenant architecture intended for all future tenants,
with trained users, defined support ownership, auditable outcomes, and a
documented rollback path. Pilot rollout scope does not permit single-tenant code.

### Supported Scope

- One active design-partner organization; no single-tenant implementation assumptions
- Hospital HIS CSV and scheduled SFTP claim ingestion
- Human-reviewed AI analysis and appeal generation
- Explicit human submission action
- Manual, portal, or email payer workflows where verified, with mock transport only for internal validation
- CSV/Excel/portal-export payment ingestion, human recovery verification, and draft itemized invoices for controlled validation

### Blocking Work

- [ ] Complete a workflow study with one Kenyan design partner using representative HIS exports, payer responses, documents, approvals, and payment reports.
- [ ] Agree a design-partner commercial schedule covering onboarding, retainer, recovery eligibility, fee rules, exclusions, evidence standard, dispute window, VAT review, and service levels.
- [ ] Replace payment-timing attribution with append-only intervention,
      payment-allocation, settlement-evidence, and attribution-version ledgers.
- [x] Restore deterministic same-tenant unmatched-payment candidates and persist human
      matching provenance, audit, and post-commit event evidence.
- [ ] Add bulk/partial payment allocation, reversal/refund, recovery
      dispute/resolution, and invoice credit-note workflows.
  - [x] Add bulk/partial payment allocation, reversal/refund, and immutable invoice
        credit-note workflows.
  - [ ] Complete recovery dispute/resolution workflow and independent production-like
        monthly reconciliation.
- [ ] Reconcile one production-like monthly invoice independently from immutable claim, intervention, payment, contract, and verification evidence.
- [ ] Add tenant-owned branches, branch memberships, departments, claim branch/currency snapshots, and cross-branch authorization tests.
- [ ] Add reusable CSV/Excel import profiles, row-level remediation, idempotent retries, and authorized CSV/Excel exports.
- [ ] Replace the global-only denial catalog with layered, versioned country/payer/organization reasons and reviewed provenance.
- [ ] Publish Kenya Knowledge Pack v1 with evaluation evidence and version attribution in AI outputs.
- [x] Complete module layering for submissions, recoveries, and invoices with dedicated repositories and module-owned services/docs.
- [ ] Complete appeal-evidence upload, malware scanning, storage, retrieval, retention, access control, and extraction provenance.
- [ ] Implement audited outbound email appeals with PDF/evidence attachments, delivery state, and conversation threading.
- [ ] Deliver branch-aware 30/60/90 aging, payer payment-time, denial-cost, collections, balance, recovery-rate, and analyst-productivity reports.
- [ ] Thread correlation IDs through HTTP requests, Celery tasks, events, audit records, and external calls.
- [ ] Add audit before/after/reason fields consistently for material mutations.
- [ ] Validate required production secrets at startup, including integration encryption and JWT signing keys.
- [x] Replace hardcoded recovery fee defaults and schedules with versioned organization configuration.
- [ ] Add stable public organization UUIDs and migrate external tenant identifiers without weakening internal ownership checks.
- [ ] Enforce organization ownership across background tasks, events, AI usage, storage, caches, reports, and audit records with negative tests.
- [ ] Certify one real Kenyan payer workflow selected from design-partner evidence; do not require an API where email, portal, or file exchange is the verified channel.
- [x] Add a tenant-owned Kenya-first payer registry and route submissions by the claim's payer configuration.
- [ ] Validate payer-specific manual, portal, and email operating procedures with a Kenyan design partner.
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
- [ ] Durable outbox/inbox pattern for event publication and idempotent consumption. Workflow consumption has a durable inbox; originating-domain transactional outboxes remain open.
- [ ] Signed webhook delivery with retry, replay protection, and dead-letter operations.
- [x] Per-organization versioned settings for AI, fees, workflows, connector selection, and feature entitlements.
- [ ] Version payer rules and enforce tenant entitlements in background tasks and events.
- [ ] Separate Atlas customer subscriptions, metering, invoices, and payments from hospital recovery accounting.
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

- [x] Tenant-scoped connector credential control plane with typed contracts, encrypted current secrets, audited rotation history, and bounded health checks.
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
