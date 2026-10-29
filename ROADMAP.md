# Atlas Roadmap

Last reviewed: 2026-10-28

This is the execution sequence for Atlas. `BUILD_STATUS.md` records current module
state, `DATABASE_SCHEMA.md` admits physical tables, `API_SPEC.md` admits HTTP
operations, and `docs/release-plan.md` owns pilot/production/enterprise readiness.

The roadmap is frozen at the batch and outcome level. Implementation may refine an
acceptance slice, but it may not introduce a parallel architecture. Critical security,
tenant-isolation, data-integrity, or production incidents may interrupt sequence and
must be recorded in `BUILD_STATUS.md`.

## Completed Platform Baseline

- [x] Docker Compose development stack with PostgreSQL and Redis.
- [x] FastAPI application, Celery worker/beat, SQLAlchemy, and Alembic foundation.
- [x] Multi-tenant organizations, authenticated users, RBAC foundation, and audit log.
- [x] Canonical module registry and non-duplicate development gate.
- [x] Claim-to-invoice orchestration proven with deterministic test data.
- [x] Human approval separated from appeal generation and submission.
- [x] Payment attribution safety, disputes, contract snapshots, and routine-payment
  zero-fee behavior.
- [x] Root architecture contracts established and protected by executable drift tests.
- [x] Kenya-first tenant defaults and production guards prevent demo seeding and
  mock/sandbox payer transports from being represented as production evidence.
- [x] Local synthetic payer fixtures and active records use Kenya-relevant names;
  unsourced US payer affinities and automatic CMS appeal citations are disabled.
- [x] Draft and in-review appeal letters support explicit versioned, audited saves;
  approved and later appeal records are immutable through the edit API.
- [x] Payment tracking and the Payments ledger derive financial state from matched
  payment, verified recovery, and invoice evidence; AI estimates remain projections.
- [x] Atlas platform administration is separated from hospital administration by
  superuser authorization, aggregate-only audited APIs, and a dedicated command center;
  unsupported company and infrastructure metrics remain explicitly unavailable.
- [x] Hospital, authentication, and Atlas-company surfaces share a responsive visual
  foundation, while retaining distinct role-specific application shells.
- [x] Local PostgreSQL readiness gates API and worker startup, and login distinguishes
  invalid credentials from unavailable sign-in infrastructure.

These checks mean behavior exists; they do not override open production gates in
`BUILD_STATUS.md` or `docs/release-plan.md`.

The local dataset remains synthetic. Real-data acceptance requires authorized Kenyan
design-partner source files, documents, payer confirmations/credentials, and payment
reconciliation, and remains a First Design-Partner Pilot gate. Synthetic engineering
acceptance does not claim hospital or production validation. `M1-PLT-01` engineering
acceptance is complete. The 533/533 backend regression result is historical (2026-08-15).
On 2026-10-28, the complete backend regression passed 520/520 (`pytest tests/`, ~19
minutes), the repository's first commit checkpoint was created (`80b956c`, followed by
`1b79cf7`), the cross-page Patients/Claims/Documents Playwright scenario was re-verified
live on both desktop (1440x900) and 390x844 mobile (2/2), web type-check, lint, and the
26-route production build passed, and an isolated PostgreSQL upgrade -> downgrade -> re-
upgrade rehearsal passed against a disposable database, ending at the sole live head
`a1c7e4b9d2f3`. The repository-owner checkpoint and the remaining cross-page responsive
scenario are both closed; see `BUILD_STATUS.md` for full evidence.

## Batch One: Patients, Claims, Documents

Status: **Engineering Complete** (2026-10-28). Not pilot or production certified; see
`docs/release-plan.md` for remaining First Design-Partner Pilot gates.

### Patients

- [x] Canonical tenant-scoped repository and service over the existing `patients` table.
- [x] Authenticated list/detail API with pagination, search, filtering, narrow RBAC,
  PHI-safe schemas, logging, error mapping, and audit policy.
- [x] Same-tenant and cross-tenant repository/API tests.
- [x] Responsive Patients page integrated with canonical APIs.
- [x] Manual desktop/mobile browser acceptance and documentation.

### Claims

- [x] Canonical model, lines, diagnoses, validations, events, repository, service,
  router, imports, and Claims pages exist.
- [x] Complete reusable CSV/Excel portability with deterministic representative
  fixtures, row-level remediation, idempotent retry, and authorized-export controls.
- [x] Add branch/currency snapshots under the ADR 0003 branch ownership model.
- [x] Close claim-update mutation audit consistency with actor, reason, before/after,
  organization, and correlation evidence.
- [x] Prove the tenant-attributed Patient-to-Claim-to-Document event sequence with
  correlated `patient.created`, `claim.created`, `workflow.transitioned`, and
  post-commit `document.uploaded` delivery.
- [ ] Complete signed-mapping and production-like workflow evidence during the
  First Design-Partner Pilot.
- [x] Run complete Batch One integration and browser regression.

### Documents

- [x] Tenant-scoped upload, claim listing, detail, download, extraction, checksum
  duplicate prevention, summaries, and mutation audit foundation exist.
- [x] Configured tenant-scoped local/S3 storage, failure-closed malware screening,
  quarantine, security telemetry, and live ClamAV acceptance.
- [x] Complete configured local/S3 engineering behavior, encryption configuration,
  failure-closed scanning, and documented rollback behavior.
- [x] Immutable document versions and extraction provenance.
- [x] Retention enforcement and document-level clinical access policy.
- [x] Complete synthetic classification/OCR engineering acceptance with provenance,
  human correction, deterministic corpus metrics, threshold enforcement, and
  aggregate-only evidence output.
- [x] Responsive claim-scoped Documents page and manual browser acceptance.

### Batch One Exit

Batch exit is an engineering checkpoint, not pilot or production certification.
Authorized real-data validation, production object-store certification, and hospital
acceptance remain governed by `docs/release-plan.md`.

- [x] All applicable module DoD checks pass for Patients, Claims, and Documents.
- [x] Cross-module claim/patient/document transaction and tenant tests pass.
- [x] PostgreSQL migration rehearsal has one head.
- [x] Ruff, backend regression, web type-check/build, responsive browser checks, and
  editor diagnostics pass.
- [x] `BUILD_STATUS.md`, `DATABASE_SCHEMA.md`, `API_SPEC.md`, and user documentation
  reflect the shipped behavior.
- [x] Commit checkpoint created by the repository owner.

## Batch Two: Payers, Submissions, Payments

Status: **In Progress**; first slice closed, existing foundations remain maintained.

- [ ] Validate payer profiles, contracts, tariffs, and sourced rules against signed
  Kenyan design-partner records.
- [x] Complete payer approval and monitoring workflows plus Payers page.
- [ ] Certify one real payer submission channel with explicit human initiation,
  acknowledgements, retries, errors, support ownership, and contract tests.
- [ ] Add stronger settlement evidence, bulk payment allocation, reversals/refunds,
  idempotent retry, and production reconciliation.
  - [x] Restore deterministic tenant-scoped unmatched-payment candidates and persist
    human matching provenance, audit, and post-commit event evidence.
  - [x] Add append-only settlement evidence, atomic bulk/partial allocation,
    idempotent reversal/refund, and invoice credit-note ledgers.
  - [ ] Independently reconcile a production-like monthly settlement and invoice.
- [ ] Complete Batch Two frontend workflows, tests, documentation, and checkpoint.

## Batch Three: Recovery, Appeals, AI

Status: **Not Started** for scheduled batch work; existing foundations remain maintained.

- [ ] Complete recovery allocation approval, reversals, credit-note integration,
  calibrated forecasts, production alerts, and independently reconciled evidence.
- [ ] Complete appeal evidence storage, PDF generation, audited outbound email,
  attachments, delivery state, and conversation threading.
- [ ] Productize only Claim Validator, Denial Predictor, Document Classifier, OCR,
  Knowledge Search, Appeal Generator, and Executive Copilot.
- [ ] Add AI evaluation sets, prompt/model provenance, quota enforcement, drift,
  approval, rollback, and live-provider operational evidence.
- [x] Prove one local synthetic claim through live OpenAI analysis, tenant-attributed
  usage/cost logging, Claim-detail rendering, and append-only decision automation.
  Production provider controls, evaluation, quotas, and operational certification remain open.
- [x] Preserve mandatory human approval before every appeal submission; distinguish
  configured electronic delivery from manual records backed by a payer reference.
- [ ] Complete Batch Three frontend workflows, tests, documentation, and checkpoint.

## Batch Four: Finance, Billing, Analytics

Status: **Not Started** for scheduled batch work; existing foundations remain maintained.

- [ ] Reconcile finance projections to production-like accounting evidence.
- [ ] Deliver branch/department scorecards and calibrated cash forecasting.
- [ ] Extend Billing's versioned commercial terms for recovery percentage,
  subscription/hybrid model, minimums and caps, grace period, payment terms, VAT,
  billing frequency, and supported payment methods; do not create a separate
  contract module or hardcode a universal 15 percent fee.
- [ ] Complete recovery invoice credit notes, VAT review, payment status, and one
  independently reconciled monthly invoice.
- [ ] Implement Atlas subscriptions, metering, customer invoices, payments, and dunning
  as a separate bounded context from hospital recovery accounting.
- [ ] Deliver governed exports, Billing page, validated Analytics page, tests, and
  checkpoint.

## Batch Five: Tasks, Notifications, Reports, Governance

Status: **Not Started** for scheduled batch work; existing foundations remain maintained.

- [ ] Add branch-aware task routing, scheduler monitoring, production alerts, and
  operator acceptance.
- [ ] Complete shared notification delivery, templates, preferences, retries, metrics,
  and user interface without creating a second event bus.
- [ ] Deliver governed 30/60/90 aging, payer timing, denial cost, collections, balance,
  recovery-rate, and analyst-productivity reports and exports.
- [ ] Complete signed governance exports, SIEM delivery, legal hold, retention
  enforcement, MFA/SSO, and security acceptance.
- [ ] Complete Batch Five frontend workflows, tests, documentation, and checkpoint.

## Cross-Cutting Release Gates

### First Design-Partner Pilot

- [ ] Representative Kenyan hospital workflow study and acceptance criteria signed.
- [ ] Commercial schedule, evidence standard, dispute window, VAT, and SLAs agreed.
- [ ] Branch and department authorization complete.
- [ ] One real payer channel and one production-like end-to-end run pass.
- [ ] Correlation trace is complete from request through invoice.
- [ ] Backup restore, alerts, incident runbook, privacy/security review, and hospital
  acceptance pass.

### Production SaaS

- [ ] Multi-instance durable events/webhooks and dead-letter operations.
- [ ] Tenant provisioning, entitlements, subscriptions, metering, billing, and
  reconciliation.
- [ ] Centralized logs, metrics, traces, SLOs, alerts, cost monitoring, HA database,
  tested backups, and zero-downtime migration strategy.
- [ ] Ten production tenants onboard through one documented process and SLOs hold for
  four consecutive weeks.

### Enterprise Platform

- [ ] Certified customer-demanded connectors and enterprise SSO/SCIM.
- [ ] Versioned policy approvals, simulation, rollback, and model governance.
- [ ] Regional residency, legal hold, export controls, evidence packages, support SLAs,
  and external security/compliance assessment.
- [ ] Enterprise design partner meets contractual volume and reconciliation targets for
  three months.

## Update Protocol

1. Work only in the active batch named by `BUILD_STATUS.md`.
2. Tick an item only with linked executable or signed acceptance evidence.
3. Update schema and API contracts in the same change as migrations/routes.
4. Update release readiness only in `docs/release-plan.md`.
5. Create commit checkpoints only after focused and adjacent gates pass; agents do not
   commit unless explicitly requested.