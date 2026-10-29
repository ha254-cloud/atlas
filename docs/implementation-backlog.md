# Atlas Implementation Backlog Index

Last reviewed: 2026-08-03

## Purpose

This document is the dependency-ordered implementation index for Atlas. It answers
which acceptance slice may be selected next, which canonical owner must contain it,
which existing files control the behavior, and what evidence closes the slice.

`BUILD_STATUS.md` remains the only delivery-status ledger. `ROADMAP.md` remains the
frozen batch sequence. This index does not independently mark modules or batches
complete. A checkbox, file, route, model, migration, or test is not completion unless
the executable evidence is recorded in `BUILD_STATUS.md` under Current Work.

The backlog deliberately does not pre-create or enumerate hundreds of speculative
files. New files are admitted only when a selected slice proves that an existing owner
cannot safely contain the artifact. Existing canonical files are extended first.

## Session Protocol

1. Read `BUILD_STATUS.md` and select only its exact Next acceptance slice.
2. Confirm the owner in `docs/module-registry.md` and inspect the anchors below.
3. Check `DATABASE_SCHEMA.md` and `API_SPEC.md` before persistence or HTTP changes.
4. State one falsifiable hypothesis and one focused check.
5. Implement the smallest end-to-end behavior, then run focused and adjacent checks.
6. Update contracts, readiness documentation, and `BUILD_STATUS.md` with evidence.
7. The repository owner creates a commit checkpoint only after all applicable gates pass.

## Platform Stability Freeze

Effective 2026-08-03, the product architecture and milestone sequence are frozen for
execution. New requests are first mapped to an admitted outcome below and then routed
to `BUILD_STATUS.md`'s active slice. A different name, folder layout, tutorial, UI,
transport, or vendor does not reopen platform design.

Planning changes are permitted only when one of these conditions is evidenced:

- a critical security, tenant-isolation, data-integrity, or production incident;
- signed pilot evidence that falsifies a current workflow, data, commercial, or
  operational assumption;
- a legal, regulatory, payer, or integration contract that the admitted design cannot
  satisfy safely;
- an approved ADR for a durable cross-cutting change or genuinely new bounded context.

An exception records its evidence, owner, impact on the active milestone, migration and
rollback consequences, and acceptance checks in `BUILD_STATUS.md`. Ideas without this
evidence remain backlog context and do not interrupt the active slice.

## File Planning Rules

- Production backend code belongs under `apps/api/app/`; the repository-root `app/`
  tree is legacy and receives no product changes.
- Production web code belongs under `apps/web/src/`.
- A proposed filename is a likely artifact, not permission to create it. Search the
  owner and compatibility surfaces first.
- Do not add snapshot, metric, history, assignment, notification, report, contract,
  or integration tables when an existing aggregate or append-only version owns the
  behavior.
- Every new table requires ownership classification, migration/rollback, tenant tests,
  registry review, and architecture-contract updates.
- File counts and line counts are repository inventory, not progress metrics.

## Proposal Reconciliation

The final enterprise-layer proposal maps to existing owners as follows.

| Proposed capability | Canonical owner and existing surface | Admission decision |
|---|---|---|
| Configurable workflows | `workflow_engine/`, `workflows/`; `workflow_definitions`, `workflow_steps`, `workflow_executions`, `workflow_step_executions`, `workflow_events` | Extend the executor or durable trigger owner. Do not add a third workflow package or generic workflow history table. |
| Human tasks | `tasks/`; `tasks`, `task_activities`, `user_task_skills`, `task_notifications` | Assignment remains on the task unless a proven many-assignee contract requires migration. Comments and attachments need a concrete workflow and retention policy before tables. |
| Notifications | `events/`, `api/v1/notifications.py`, `webhooks/`, task notifications, email service | Consolidate shared delivery behavior here. Do not create a second event bus or unscoped notification service. |
| Reports | `dashboard/`, `finance/`, `recovery_workspace/` projections | Add governed projections and exports over canonical facts. Scheduled delivery is Batch Five; do not persist duplicate financial totals. |
| Governance | `governance/`, `audit/`, authentication/security owners | Extend immutable audit, consent, retention, session, and credential surfaces. Do not add duplicate access-token, API-key, or settings models. |
| Administration | Existing organization, user, payer, integration, governance, billing, and settings APIs | Build an authorized composition UI. A separate admin business-logic module or tenant table is not admitted. |
| Integrations | `integrations/`, `payer_connectivity/`, `webhooks/`, `canonical/`, `imports/` | Add certified adapters through registered interfaces. A class or mock is not a production connector. |
| Background work | `workers/` invoking canonical services | Add task entrypoints and schedules only for selected behavior; do not move domain rules into specialized worker packages. |
| Object storage | `documents/storage.py` and the Documents service | Add registered storage and scanning adapters inside Documents; local/S3/Azure/GCS are transports, not separate document stores. |
| SSO providers | Authentication/security owner | Add only with enterprise identity contracts, tenant mapping, audit, and failure-closed configuration. |

The proposed `apps/api/auth`, `apps/api/claims`, and similar top-level layout is not
the production layout. Canonical backend packages remain under `apps/api/app/`.
`recovery/` versus `recoveries/` and `workflow_engine/` versus `workflows/` are
intentional responsibility splits documented in the module registry.

## Epic Coverage Map

This map reconciles the product vision to the dependency-ordered milestones. It does
not create an alternative priority or status system.

| Epic | Canonical owners | Execution milestone | Scope rule and principal open outcomes |
|---|---|---|---|
| 1. Core Platform | Authentication, organizations, users/security; Branches under ADR 0003 | M1-PLT-01, M5-GOV-01, M5-ADM-01, M6 | Complete branches/departments/memberships, production secrets, MFA/SSO, stable tenant onboarding and audit. Units, teams, licenses and preferences extend these owners only after a concrete authorization or product contract proves the need. |
| 2. Clinical | `patients/`, `claims/`, `documents/`, imports/canonical/validation | M1 | Close governed storage, quarantine, versions, provenance, access/retention, OCR/classification, portability and audit consistency. Patient merge/archive and claim notes require explicit identity, retention and audit invariants before admission. |
| 3. Insurance | `payers/`, `submissions/`, `payer_connectivity/`, `payments/` | M2 | Validate signed payer contracts/rules, certify one real human-triggered channel, and close settlement/allocation/reversal safety. |
| 4. Revenue Recovery | `recovery/`, `recoveries/`, `appeals/`, tasks and finance boundaries | M3 | Close allocation approval, reversals/credits, forecasts, appeal evidence/delivery and independent reconciliation. Write-off remains a governed recovery decision requiring approval and accounting-export evidence, not a parallel module. |
| 5. Artificial Intelligence | `ai/`, `agents/`, `decisions/`, `copilot/` through `AIGateway` | M1-DOC-04, M3-AI-01 | Productize only Claim Validator, Denial Predictor, Document Classifier, OCR, Knowledge Search, Appeal Generator and Executive Copilot with evaluation, provenance, quotas, drift and rollback. |
| 6. Workflow | `workflow_engine/`, `workflows/`, `tasks/`, events/notifications | M5-TSK-01, M5-NOT-01 | Productionize configurable execution, branch routing, scheduler/dead-letter operations, templates/preferences and certified delivery channels without new engines or event buses. |
| 7. Finance | `finance/`, `billing/`, `invoices/` and recovery financial records | M4 | Reconcile KPIs/forecasts, complete commercial terms, VAT, credit notes and recovery invoices; build Atlas SaaS billing as a separate bounded context. |
| 8. Analytics | `dashboard/`, `finance/`, `recovery_workspace/` read models | M4-ANA-01, M5-RPT-01 | Validate dashboards against canonical facts, add governed exports and scheduled daily/weekly/monthly/quarterly/annual reports without duplicate metric tables. |
| 9. Governance | `governance/`, `audit/`, authentication/security | M5-GOV-01, M6-SEC-01 | Enforce retention/hold, signed exports, SIEM, identity hardening and Kenya/privacy controls. Compliance readiness is evidence-based; Atlas does not claim certification from architecture alone. |
| 10. Integrations | `integrations/`, `payer_connectivity/`, `webhooks/`, canonical/import adapters | M2-SUB-01, M5-INT-01, M6 | Certify only demanded hospital, payer, storage, messaging, M-Pesa/bank and identity transports with real contracts, credentials, mapping, retries and runbooks. |
| 11. Administration | Composition of organizations, users/security, settings, billing, integrations, governance and observability | M5-ADM-01 | Deliver platform/hospital/support administration with role separation, audit, entitlements, queue/error visibility and maintenance controls; no duplicate admin domain. |
| 12. Infrastructure | Deployment, database, workers, events, observability, Documents storage | M1-DOC-01, M6 | Complete object storage, production ingress, CI/CD, HA, monitoring, backups, logging, queue operations and rollback. Celery remains the admitted worker platform; do not add RQ in parallel. |
| 13. Frontend | `apps/web/src/` pages and feature components | Every active milestone | Deliver the user workflow for each activated owner with accessibility, type-check, production build and desktop/mobile browser acceptance. Mobile remains future demand, not a reserved package. |
| 14. Testing | `apps/api/tests/`, frontend checks, CI and production-like acceptance | Every active milestone, M6 | Scale unit, repository, API, tenant/security, migration, integration, browser E2E, performance, load and recovery evidence with blast radius. |
| 15. Deployment | Compose/Docker/CI/deployment docs and production infrastructure | M6 | Rehearse development, staging and production promotion, domain/TLS, monitoring, backups, disaster recovery, zero-downtime migration and incident ownership. |

## Enterprise Feature Decisions

### Rules Engine

Payer rules remain in `payers/`; configurable process conditions remain in
`workflow_engine/`. Both use versioned tenant configuration and approval/audit rules.
A new generic rules engine is rejected unless two existing owners cannot safely express
the same proven rule semantics.

### Contract Engine

Payer reimbursement/SLA contracts remain in `payers/`. Atlas recovery-fee terms remain
in `billing/`; future SaaS subscriptions remain a separate bounded context. A shared
"contract engine" module is rejected because these contracts have different parties,
facts, permissions and accounting consequences.

### Case Management

Operational recovery composition starts with `recovery/` lifecycle accounts, Tasks,
Documents and the existing financial boundary in `recoveries/`. A new multi-claim case
aggregate is not admitted until pilot evidence defines grouping, ownership, allocation,
closure, audit, retention and cross-claim authorization semantics that these owners
cannot safely contain.

### Scheduler

Celery Beat and `workers/` are the canonical scheduler. Extend typed schedules,
idempotent task entrypoints, monitoring, dead-letter operations and runbooks there.
Do not add a second scheduler service for imports, reconciliation, reports or reminders.

### Feature Flags

Organization entitlements and versioned tenant settings are the canonical feature
controls. Complete background/event enforcement, audit, safe defaults and rollback
before adding flags. Do not create a second feature-flag table merely for UI toggles.

### API Gateway

FastAPI middleware currently owns authentication integration, CORS, correlation and
rate limiting; routers provide API versioning. Production ingress may add a managed
gateway or reverse proxy for TLS, WAF, quotas and edge telemetry under M6 when deployment
requirements justify it. It is infrastructure, not a new business module.

## Milestone 1: Batch One Exit

Batch: Patients, Claims, Documents. This is the only active milestone.

### M1-DOC-01: Governed Object Storage And Quarantine

- Owner: `documents/`.
- Existing anchors: `documents/storage.py`, `documents/service.py`,
  `documents/repository.py`, `documents/router.py`, `models/document.py`,
  `tests/test_documents.py`, `.env.example`, `docker-compose.yml`.
- Deliverable: typed local/object-storage selection, tenant-safe object keys, streamed
  upload/download, checksum preservation, malware scan/quarantine before availability,
  failure-closed production configuration, deletion semantics, structured telemetry.
- Expected artifacts only if the selected design requires them: storage adapter
  interface/implementation files, scanning adapter, typed settings, migration for a
  persisted quarantine/provenance state, worker task for asynchronous scanning.
- Required evidence: clean/infected/error upload paths; unavailable quarantined files;
  same-tenant and cross-tenant tests; retry/idempotency tests; focused Ruff; deployment
  and rollback documentation; one Alembic head.

### M1-DOC-02: Immutable Versions And Extraction Provenance

- Owner: `documents/`.
- Existing anchors: document model/service/repository, extraction adapter, audit writer.
- Deliverable: append-only document versions, predecessor/reason/actor, source checksum,
  extractor/OCR version, timestamps, and safe retrieval of current and historical evidence.
- Required evidence: no in-place replacement, parent/tenant ownership enforcement,
  migration upgrade/downgrade, audit correlation, version and cross-tenant tests.

### M1-DOC-03: Retention And Clinical Access Policy

- Owners: Documents with Governance and Security policy surfaces.
- Existing anchors: `governance/`, `security/`, retention-policy models, Documents router.
- Deliverable: enforceable retention disposition, legal/clinical hold behavior,
  least-privilege document access, audit of view/download/export/delete decisions.
- Required evidence: policy precedence tests, denied clinical access tests, retention
  dry-run and enforcement tests, operator runbook, no silent deletion.

### M1-DOC-04: Classification And OCR Acceptance

- Owner: `documents/` through `AIGateway` for model calls.
- Existing anchors: extraction adapter, Documents service, `ai/gateway.py`, AI call logs.
- Deliverable: governed document classification and OCR with provenance, confidence,
  review state, configurable model/provider, and graceful unavailable-provider behavior.
- Engineering evidence: synthetic typed/scanned documents, deterministic fixtures,
  model/prompt provenance, tenant attribution, explicit accuracy thresholds, aggregate-only
  evaluator output, failure exit codes, and a human correction path.
- Pilot evidence: authorized representative documents, hospital/data-governance-approved
  thresholds, measured aggregate results, and reviewer sign-off. Pilot evidence is not
  required to continue engineering, but is mandatory before pilot-ready claims.

### M1-CLM-01: Claims Portability And Audit Consistency

Engineering status: **Complete on 2026-08-14; not pilot certified.**

- Owners: `claims/`, `imports/`, `canonical/`, `processing/`, `validation/`.
- Existing anchors: Claims service/router, import pipeline, canonical normalizers,
  `tests/test_claim_api.py`, import and validation tests.
- Deliverable: reusable CSV/Excel portability, authorized-export controls, and consistent
  actor/before/after/reason/correlation evidence for material mutations.
- Engineering evidence: deterministic representative mappings, round-trip export tests,
  invalid-row remediation, idempotent retry, and same/cross-tenant tests.
- Pilot evidence: signed hospital mappings, authorized source/export samples, and
  production-like workflow acceptance under `docs/release-plan.md`.

### M1-PLT-01: Branch Ownership Prerequisite

- Owner: new owner already governed by ADR 0003; implementation must update the registry.
- Existing anchors: ADR 0003, organizations/users/security/claims owners.
- Deliverable: tenant-owned branches, departments, memberships, claim branch/currency
  snapshots, narrow cross-branch RBAC.
- Expected artifacts after activation: canonical package layers, models, migration,
  permissions, tests, API/admin composition, and documentation.
- Required evidence: organization and branch isolation, immutable claim snapshots,
  migration rehearsal, authenticated administration acceptance.
- Engineering status: complete on 2026-08-14 with the registered `branches/` owner.
  The following 72-table/241-operation/`d5a8c1f3e7b9` figures are the preserved
  Batch One exit snapshot, not the current architecture registry. Evidence included
  tenant-safe composite ownership, branch-scoped Claims, canonical branch/currency
  round-trip behavior, Settings administration, responsive Claim selectors, 533/533
  complete backend tests, web build, browser acceptance, 72 registered
  tables, 241 HTTP operations, and one Alembic head `d5a8c1f3e7b9`. Pilot evidence
  and downstream task/report branch behavior remain open under their owning slices.

### M1 Exit Evidence

- All applicable Patient, Claim, and Document Definition of Done checks pass.
- Cross-module Patient-to-Claim-to-Document transaction and tenant tests pass.
- PostgreSQL upgrade/rollback rehearsal passes with exactly one Alembic head.
- Focused and adjacent backend regression, Ruff, web type-check/build, responsive
  browser checks, architecture contracts, and diagnostics pass.
- `BUILD_STATUS.md`, contracts, release plan, deployment docs, and user docs agree.

## Milestone 2: Batch Two Exit

Batch: Payers, Submissions, Payments. Blocked until Milestone 1 exits.

### M2-PAY-01: Design-Partner Payer Records

- Owner: `payers/`.
- Existing anchors: payer profiles, contracts, tariffs, rules, advisory validation.
- Deliverable: signed Kenyan payer/contract/rule ingestion, approval/version workflow,
  source provenance, effective dates, monitoring.
- Evidence: representative SHA and commercial-payer records, approval/RBAC/audit tests,
  rollback and stale-rule alerts.

### M2-SUB-01: Certified Human-Initiated Payer Channel

- Owners: `submissions/`, `payer_connectivity/`, registered integration adapter.
- Deliverable: one design-partner-selected real channel with payload contract,
  acknowledgement, polling, timeout, retry, duplicate prevention, support ownership.
- Evidence: vendor/sandbox contract tests plus production-like acceptance; human action
  remains explicit and appeal generation/approval never submits automatically.

### M2-PMT-01: Settlement, Allocation, And Reversal Safety

- Owner: `payments/` with recovery financial records under `recoveries/`.
- Deliverable: stronger settlement evidence, bulk/partial allocation, reversals/refunds,
  idempotent retry, unmatched remediation, immutable provenance.
- Evidence: exact-money tests, many-to-many allocation cases, cross-tenant denial,
  reversal reconciliation, independently checked totals.
- Engineering status: complete on 2026-10-29 through immutable settlement and
  allocation ledgers, intervention-backed attribution versions, maker-checker
  dispute resolution, allocation- and dispute-sourced credit notes, and immutable
  independent KES invoice reconciliation runs. External finance acceptance remains
  part of the Batch Two exit.

### M2 Exit Evidence

- One real payer workflow and stronger settlement lifecycle pass end to end.
- Payers and Payments user workflows pass responsive acceptance.
- Contracts, migrations, tests, runbooks, monitoring, and support ownership are current.

## Milestone 3: Batch Three Exit

Batch: Recovery, Appeals, AI. Blocked until Milestone 2 exits.

### M3-REC-01: Governed Recovery Allocation And Credits

- Owners: `recovery/`, `recoveries/`, `billing/`, `invoices/` at their documented boundaries.
- Deliverable: allocation approval, reversal/refund consequences, credit-note linkage,
  calibrated forecast, alerts, independent invoice reconciliation.
- Evidence: ADR 0004 invariants, segregation of duties, immutable financial versions,
  exact-money and dispute tests.

### M3-APL-01: Complete Appeal Evidence And Delivery

- Owner: `appeals/` with Documents evidence and registered delivery integration.
- Deliverable: governed attachments, PDF, audited outbound email, delivery state,
  conversation threading, explicit human submission action.
- Evidence: attachment access/retention tests, email failure/retry tests, no automatic
  submission, production-like payer correspondence acceptance.

### M3-AI-01: Product AI Governance

- Owners: `ai/`, `agents/`, `decisions/`, `copilot/` through `AIGateway`.
- Deliverable: evaluation sets for the seven admitted AI services, prompt/model
  provenance, quota/cost enforcement, drift alerts, approval, rollback, live-provider runbook.
- Evidence: representative evaluation thresholds, unavailable/quota/provider-error paths,
  PHI review, tenant attribution, human override and rollback drills.

## Milestone 4: Batch Four Exit

Batch: Finance, Billing, Analytics. Blocked until Milestone 3 exits.

### M4-FIN-01: Reconciled Finance Intelligence

- Owner: `finance/`; projections read canonical claims/payments/recoveries.
- Deliverable: production-like accounting reconciliation, branch/department views,
  calibrated cash forecast, authorized exports.
- Evidence: source-to-KPI reconciliation, currency/branch tests, forecast calibration,
  cross-tenant report denial, export audit.

### M4-BIL-01: Recovery Invoice Completion

- Owners: `billing/`, `invoices/`.
- Deliverable: versioned commercial terms, VAT review, bulk settlement consequences,
  credit notes, payment status, one independently reconciled monthly invoice.
- Evidence: minimum/cap/grace/net-term/hybrid cases, no hardcoded universal fee,
  exact-money and dispute tests, signed finance acceptance.

### M4-SUB-01: Atlas SaaS Billing

- Owner: a separate bounded context requiring registry/ADR/schema admission when activated.
- Deliverable: subscriptions, entitlements, metering, customer invoices, SaaS payments,
  dunning, and reconciliation kept separate from hospital recovery accounting.
- Evidence: tenant lifecycle, usage idempotency, invoice correctness, failed payment,
  cancellation, entitlement, security, and reconciliation tests.

### M4-ANA-01: Validated Executive Analytics

- Owners: `dashboard/`, `finance/` read models and existing web analytics surfaces.
- Deliverable: branch-aware validated KPIs, payer/recovery performance, forecast,
  observability, executive acceptance.
- Evidence: canonical-source reconciliation, no duplicate financial facts, responsive
  dashboard checks, role/tenant tests, metric definitions documented.

## Milestone 5: Batch Five Exit

Batch: Tasks, Notifications, Reports, Governance. Blocked until Milestone 4 exits.
Workflow, integrations, and administration foundations are maintained through their
existing owners when required; they are not rebuilt as new Batch Five modules.

### M5-TSK-01: Production Task Operations

- Owner: `tasks/`.
- Deliverable: branch-aware routing, operator acceptance, scheduler monitoring,
  production SLA alerts and delivery evidence.
- Evidence: branch/skill/least-load routing, duplicate-event idempotency, escalation,
  cross-tenant/branch tests, queue runbook and alert drill.

### M5-NOT-01: Shared Notification Delivery

- Owners: Events/Notifications/Webhooks registered surfaces.
- Deliverable: templates, user/tenant preferences, email/in-app/webhook delivery,
  retries/dead letters, metrics, user inbox without a second event bus.
- SMS/WhatsApp/push are admitted only after provider, consent, cost, privacy, retry,
  opt-out, and support contracts are approved.
- Evidence: preference/consent tests, duplicate suppression, provider failure/retry,
  delivery audit, tenant isolation, observability.

### M5-RPT-01: Governed Reports And Scheduling

- Owners: `dashboard/`, `finance/`, `recovery_workspace/` projections.
- Deliverable: 30/60/90 aging, payer timing, denial cost, collections, balances,
  recovery rate, productivity, authorized CSV/Excel/PDF/JSON exports, scheduled delivery.
- Expected artifacts only after activation: report projection/service, export adapters,
  schedule/task entrypoint, Reports page, tests and runbooks under existing owners.
- Evidence: metric reconciliation, export audit, recipient authorization, timezone and
  retry behavior, responsive Reports page, no duplicate fact tables.

### M5-GOV-01: Enterprise Governance And Identity

- Owners: `governance/`, `audit/`, authentication/security.
- Deliverable: signed exports, SIEM delivery, legal hold, enforced retention, MFA/SSO,
  session hardening, security acceptance.
- Evidence: immutable signed package verification, SIEM failure/retry, hold precedence,
  MFA recovery, SSO tenant mapping, penetration/security review.

### M5-ADM-01: Administration Composition

- Owners: organizations, users/security, payers, integrations, governance, settings,
  billing and observability APIs.
- Deliverable: authorized hospital onboarding/suspension, entitlements, usage/queue/error
  visibility, AI and commercial configuration, support operations.
- Evidence: platform-versus-tenant role separation, audit, support impersonation policy,
  cross-tenant denial, responsive administration workflows.

### M5-INT-01: Certified Integration Portfolio

- Owners: `integrations/`, `payer_connectivity/`, `webhooks/`, `canonical/`, `imports/`.
- Deliverable: only customer-demanded HIS/payer/identity adapters with real transport,
  canonical mapping, credentials, timeout/retry/idempotency, health and support runbooks.
- Evidence: per-connector contract and sandbox tests, secret rotation, tenant isolation,
  failure recovery, certification/acceptance record. Stub classes remain explicitly unready.

## Milestone 6: Production And Enterprise Release Gates

This is a release-hardening milestone, not a new numbered product batch.

### M6-OPS-01: Production Platform

- Owners: deployment, observability, security, database, workers, events/webhooks.
- Deliverable: production secret validation, HA topology, durable multi-instance events,
  queue/dead-letter operations, logs/metrics/traces/SLOs, cost monitoring, zero-downtime
  migration strategy, incident ownership.
- Evidence: load and failure tests, alert drills, deploy/rollback rehearsal, capacity and
  cost report, incident runbook acceptance.

### M6-DR-01: Backup And Recovery

- Deliverable: encrypted backups, restore/PITR, object-store recovery, key recovery,
  documented RPO/RTO and named operators.
- Evidence: timed restore rehearsal with integrity and tenant-isolation verification.

### M6-SEC-01: External Security And Compliance

- Deliverable: privacy/security review, vulnerability remediation, dependency and secret
  scanning, regional/residency controls where contracted, evidence package and support SLA.
- Evidence: external assessment, accepted residual risks, signed release decision.

### M6-SCALE-01: SaaS And Enterprise Acceptance

- Deliverable: repeatable tenant onboarding, ten production tenants with SLO evidence,
  enterprise SSO/SCIM and certified connectors only where contracted.
- Evidence: four-week Production SaaS SLO window and three-month enterprise design-partner
  reconciliation target defined in `docs/release-plan.md`.

## Completion Record

For every closed slice, `BUILD_STATUS.md` must record:

- owning module and whether an existing owner was extended;
- behavior completed and exact next action;
- focused and adjacent tests with results;
- Ruff/type-check/build/browser/diagnostic evidence as applicable;
- migration head and upgrade/rollback state;
- security, tenant, audit, observability, deployment, and residual-risk notes;
- contracts and release-readiness documents changed.

This index changes only when dependencies, ownership, or admitted milestone outcomes
change. Daily progress belongs exclusively in `BUILD_STATUS.md`.