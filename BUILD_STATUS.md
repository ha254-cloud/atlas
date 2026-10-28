# Atlas Build Status

Last verified: 2026-10-28

This is the single delivery ledger for Atlas. It records what already exists, what
is being completed, and what may be built next. `docs/module-registry.md` remains
the source of truth for ownership; this file is the source of truth for delivery
status and sequence. `DATABASE_SCHEMA.md`, `API_SPEC.md`, and `ROADMAP.md` freeze the
physical schema, HTTP surface, and execution order.

`docs/implementation-backlog.md` is the dependency and evidence index for selecting
implementation slices. It does not carry independent status and cannot override this
ledger's active batch or exact next action.

## Status Rules

Only these delivery states are allowed:

- **Not Started**: no usable implementation exists in the canonical owner.
- **In Progress**: any required implementation or Definition of Done evidence is open.
- **Complete**: every applicable gate in `docs/definition-of-done.md` is satisfied,
  focused and adjacent tests pass, migrations are rehearsed, frontend behavior is
  verified, documentation is current, and no release blocker remains for the stated
  scope.

File presence is not completion. A foundation, mock connector, stub, or passing unit
test is not production readiness. Status may move backward when evidence expires or a
regression is found.

## Non-Duplication Gate

Before editing production code:

1. Read this file, `ROADMAP.md`, `DATABASE_SCHEMA.md`, `API_SPEC.md`, and
   `docs/module-registry.md`.
2. Search the owner, models, migrations, routes, services, workers, pages, and tests.
3. Extend the canonical owner. Do not create a parallel package, table, API, matcher,
   ledger, event bus, AI gateway, or integration framework.
4. Search all Alembic revisions and ORM table names before proposing a table.
5. Record the active module and exact acceptance criterion in the Current Work section.
6. Update this ledger only after executable evidence changes status.

The production backend remains `apps/api/app/`. The repository-root `app/` tree is
legacy. Existing compatibility imports remain until a tested migration removes them.

## Platform Stability Freeze

Effective 2026-08-03, Atlas executes from `docs/implementation-backlog.md` and this
ledger without reopening the platform architecture for unverified feature lists or
alternative folder structures. Every session starts from Current Work and implements
the exact Next acceptance slice.

Only a critical security, tenant-isolation, data-integrity, or production incident;
signed pilot evidence that falsifies an admitted assumption; a binding legal/vendor
contract; or an approved durable ADR may interrupt the sequence. Record the evidence,
owner, active-batch impact, migration/rollback consequences, and acceptance checks here
before implementation.

## Delivery Order

Work is horizontal within each batch: close the smallest shared platform gap across
the batch, then deepen each canonical owner without rebuilding completed behavior.

| Batch | Modules | State | Exit condition |
|---|---|---|---|
| One | Patients, Claims, Documents | **In Progress** | Safe patient operations, production claim workflow, and governed document evidence are complete together. |
| Two | Payers, Submissions, Payments | **Not Started** | Begins only after Batch One exits; existing implementations remain maintained. |
| Three | Recovery, Appeals, AI | **Not Started** | Begins only after Batch Two exits; existing implementations remain maintained. |
| Four | Finance, Billing, Analytics | **Not Started** | Begins only after Batch Three exits. Recovery fees and Atlas SaaS billing remain separate contexts. |
| Five | Notifications, Tasks, Reports, Governance | **Not Started** | Begins only after Batch Four exits. |

Foundation modules are maintained whenever required for the active batch. A critical
security, tenant-isolation, data-integrity, or production incident overrides batch
order and must be recorded under Current Work.

## Module Ledger

No module is marked Complete in this baseline because each has an open applicable
Definition of Done or release-readiness gate.

| Module | Status | Canonical owner | Existing evidence | Required next outcome |
|---|---|---|---|---|
| Authentication | **In Progress** | `api/v1/auth.py`, `security/`, `services/auth_service.py` | Registration, login, sessions, JWT, and tests exist. | Production secret validation, MFA/SSO roadmap controls, complete audit/correlation evidence. |
| Organizations | **In Progress** | `organizations/` | Models, schemas, repository, service, router, settings versions, entitlements, and tests exist. | Stable public UUID migration and production onboarding/operations evidence. |
| Branches | **In Progress** | `branches/` under ADR 0003 | Tenant-owned branches, departments, memberships, composite tenant-safe ownership, narrow RBAC, audited APIs, migration, Settings administration, Claim selectors, and cross-tenant/cross-branch tests exist. | Extend branch authorization into downstream tasks, documents, reports, AI context, audit queries, and cache keys where those workflows require branch access; obtain pilot administration acceptance. |
| Users | **In Progress** | `api/v1/users.py`, `security/`, existing user model/repository/service | User and invitation workflows exist. | Complete module layering without duplicating identity or permission logic; add full user administration evidence. |
| Patients | **In Progress** | `patients/`, existing patient model, and claim/import boundaries | Canonical tenant-scoped schemas, repository, service, authenticated list/create/detail/update API, narrow RBAC, mutation audit, PHI-minimal events, search/DOB filtering, pagination, cross-tenant tests, responsive create/edit page, and desktop/mobile browser acceptance exist over the original table. Legacy blank MRNs render safely; new MRN-less imports receive unique identifiers. | Prove the Patient-to-Claim-to-Document integration and remaining applicable production/DoD evidence without a second patient store. |
| Claims | **In Progress** | `claims/`, `imports/`, `processing/`, `validation/`, `canonical/` | Layered claim APIs, ingestion, validation, events, reusable mapping profiles, PHI-minimized row errors, explicit failed/partial retry, narrowly authorized canonical CSV export, branch/department/currency snapshots and round-trip evidence, and complete claim-update mutation audit exist. | Obtain signed hospital mappings and production workflow evidence during pilot certification. |
| Documents | **In Progress** | `documents/` | Upload/search/download, extraction, deduplication, audit, tests, Claim-detail evidence controls, responsive workspace, configured local/S3 storage, failure-closed ClamAV screening, quarantine, immutable versions/provenance, retention enforcement, legal/clinical holds, clinical least privilege, security telemetry, and synthetic OCR/classification engineering acceptance exist. | Pilot certification against authorized documents and the selected production object store; these external gates do not block continued engineering. |
| Payers | **In Progress** | `payers/` | Registry, profile versions, contracts, tariffs, rules, advisory validation, and tests exist. | Validate against signed Kenyan records, add approval workflow and production monitoring, and deliver Payers page. |
| Submissions | **In Progress** | `submissions/`, `payer_connectivity/` | Human-triggered lifecycle, connector routing, polling, audit, and tests exist. | Certify one real design-partner payer workflow and production delivery/error evidence. |
| Payments | **In Progress** | `payments/` | Canonical evidence, idempotency, unmatched queue, suggestions, human provenance, tests, and Payments page exist. | Stronger settlement evidence, bulk allocation, reversals/refunds, and production reconciliation. |
| Recovery | **In Progress** | `recovery/`, `recoveries/`, `recovery_workspace/` | Operational engine and financial evidence/attribution are intentionally separate owners; lifecycle, ledgers, disputes, tests, and Recovery page exist. | Complete allocation approvals, reversal/credit-note behavior, calibrated forecasting, alerts, and independent invoice reconciliation. |
| Appeals | **In Progress** | `appeals/` | Versioned generation, review, approval, evidence, APIs, tests, and Appeals page exist. | Complete governed evidence storage, PDF/email delivery, conversation threading, and production acceptance evidence. |
| AI | **In Progress** | `ai/`, `agents/`, `decisions/`, `copilot/` through `AIGateway` | Gateway, prompts, usage logs, claim analysis, denial classification, appeal generation, and Copilot exist. | Restrict supported product catalog to the seven services below; complete evaluation, provenance, quota, drift, rollback, and live-provider evidence. |
| Finance | **In Progress** | `finance/` | Tenant-scoped cash views, scorecards, forecast, reconciliation, APIs, tests, and executive UI exist. | Production accounting reconciliation, branch/department views, calibrated forecasts, and export evidence. |
| Billing | **In Progress** | `billing/`, `invoices/` | Recovery fee schedules, attribution-gated recovery invoices, disputes, and tests exist. | Add bulk settlement, credit notes, VAT review, production invoice reconciliation; build separate Atlas subscription billing only when this batch activates. |
| Tasks | **In Progress** | `tasks/` | Tenant queue, priority, assignment, SLA, notifications, workers, tests, and Tasks page exist. | Branch routing, production scheduler monitoring, alert delivery, and operator acceptance evidence. |
| Notifications | **In Progress** | Events, `api/v1/notifications.py`, task notifications, email service, webhooks | Durable task notifications and API/event delivery surfaces exist. | Consolidate only shared delivery behavior under the registered event owner; add templates, preferences, retries, metrics, tests, and user UI without a second event bus. |
| Reports | **In Progress** | `dashboard/`, `finance/`, `recovery_workspace/` read models | Executive and operational projections exist. | Deliver governed 30/60/90 aging, payer timing, denial cost, collection, balance, recovery-rate, productivity, export, and Reports page without duplicate financial facts. |
| Analytics | **In Progress** | `finance/`, `dashboard/` | Tenant-scoped analytics APIs, tests, Dashboard and Analytics pages exist. | Branch-aware validated metrics, production data reconciliation, observability, and acceptance evidence. |
| Integrations | **In Progress** | `integrations/`, `payer_connectivity/`, `webhooks/` | Credential versions, mapping, sync history, SFTP/CSV support, connector contracts, and tests exist. | Remove readiness claims from stubs; certify demanded Kenyan channels with contract, timeout, retry, support, and production evidence. |
| Governance | **In Progress** | `governance/`, `audit/`, audit API | Immutable audit evidence, consent/retention versions, sessions, tests, and Governance page exist. | Signed export, SIEM, legal hold, enforcement, MFA/SSO, backup/PITR rehearsal, and security acceptance evidence. |
| Administration | **In Progress** | Administrative views in organizations, users, branches, payers, integrations, governance, workflows, and settings | Owner/admin-only Administration navigation and control center compose canonical Team, Branch, Governance, Integration, and Workflow surfaces; personal account settings remain separate. | Complete organization configuration and remaining administrative workflows by composing canonical APIs; do not create duplicate admin business logic or tables. |
| Frontend | **In Progress** | `apps/web/src/` | Auth, claims, payments, recovery, tasks, analytics, integrations, governance, appeals, workflows, Copilot, settings, dashboard, and executive pages exist. | Complete missing batch pages, accessibility/responsive acceptance, production build, and end-to-end workflows. |
| Testing | **In Progress** | `apps/api/tests/`, frontend checks, CI | Focused backend suites, tenant tests, build checks, and architecture drift tests exist. | Close open cross-tenant, production-like integration, browser E2E, load, security, recovery, and operational acceptance gates. |
| Deployment | **In Progress** | Dockerfiles, Compose, CI, deployment docs | Reproducible local API/worker/web builds and migrations exist. | Production secrets, HA, monitoring, alerting, backup/PITR restore rehearsal, rollback, and incident ownership. |

## Required Module Shape

Each canonical business owner must provide these responsibilities where applicable:

```text
owned model(s)
schemas.py
repository.py
service.py
router.py or event/task entrypoint
permissions.py or shared RBAC policy
tests
module documentation
```

The responsibility matters more than an identical filename. Read-only projections,
AI orchestration, append-only audit logs, and event consumers must not gain artificial
CRUD methods merely to satisfy a template. APIs expose only operations valid for the
domain. Pagination, filtering, search, and export are required where collections or
operational workflows genuinely need them.

## Data Contract

The proposed business nouns are product aggregates, not a destructive physical-table
allowlist. Atlas already requires supporting tables for immutable versions, history,
idempotency, tenant settings, integration credentials, workflow execution, audit, and
financial attribution. Removing or merging them would weaken traceability and can lose
data.

Before adding a physical table:

- prove no current table or aggregate owns the data;
- classify it as global, directly tenant-owned, or parent-scoped;
- document constraints, indexes, retention, audit, migration, rollback, and tenant tests;
- update the module registry when ownership changes;
- never rename `claim_lines` to `claim_items`, `invoices` to `atlas_invoices`, or create
  `payment_matches` merely to match vocabulary without an approved data migration and
  demonstrated semantic need.

## AI Product Catalog

The supported product-facing AI services are limited to:

1. Claim Validator
2. Denial Predictor
3. Document Classifier
4. OCR
5. Knowledge Search
6. Appeal Generator
7. Executive Copilot

All model calls use `AIGateway`; prompts and model choices are versioned and tenant
configurable. Existing recovery scoring, workflow agents, and decision code are
supporting orchestration or deterministic domain behavior, not additional marketed AI
services. No new AI service may be added without updating this catalog and the module
registry.

## Frontend Ledger

| Page | Status | Current route or next owner |
|---|---|---|
| Login | **In Progress** | `/login` exists; production auth controls remain open. |
| Dashboard | **In Progress** | `/dashboard` exists. |
| Patients | **In Progress** | `/patients` uses the canonical Patient API; create/edit/search desktop plus 390x844 responsive acceptance pass. |
| Claims | **In Progress** | `/claims` and `/claims/[id]` exist. |
| Documents | **In Progress** | `/documents` composes canonical Claims and Documents APIs; production document controls remain open. |
| Payers | **Not Started** | Batch Two; use `payers/`. |
| Payments | **In Progress** | `/payments` exists. |
| Recovery | **In Progress** | `/recovery` exists. |
| Tasks | **In Progress** | `/tasks` exists. |
| Reports | **Not Started** | Batch Five; read from canonical report/finance projections. |
| Analytics | **In Progress** | `/analytics` exists. |
| Billing | **Not Started** | Batch Four; distinguish recovery invoices from Atlas subscriptions. |
| Settings | **In Progress** | `/settings` exists. |
| Administration | **In Progress** | `/administration` composes admin-authorized Team, Branch, Governance, Integration, and Workflow surfaces. |

Additional implemented workflow pages such as Appeals, Integrations, Governance,
Executive, Workflows, and Copilot remain supported; they are not duplicate modules.

## Current Work

| Field | Value |
|---|---|
| Active batch | Batch One: Patients, Claims, Documents — **engineering-complete, exited 2026-10-28** (see Batch One exit row below). Batch Two: Payers, Submissions, Payments is now admitted per `ROADMAP.md`; active slice selection is pending. |
| Active module | Batch Two slice not yet selected. |
| Goal | Complete the canonical Patient-to-Claim-to-Document workflow before Batch Two begins. (Achieved 2026-10-28; Batch Two scope follows.) |
| First acceptance slice | Add responsive claim-document upload/list evidence to the existing Claim detail workflow, then prove tenant-scoped Patient creation, Claim creation, document upload, uploader-selected classification metadata, extraction, and claim validation visibility end to end. |
| Completed acceptance slice | Patient create/edit/search/pagination and authenticated responsive acceptance; canonical Claim-detail document upload/list and responsive `/documents` workspace; configured tenant-scoped local/S3 storage; checksum-preserving remote materialization; failure-closed ClamAV screening; non-readable quarantine; API 422/503 behavior; structured security telemetry; `M1-DOC-02` immutable binary versions and extraction provenance; and `M1-DOC-03` report-only/enforced retention policy, preview and exact-policy confirmation, append-only legal/clinical holds, hold precedence, audited retryable deletion, and separate clinical-document permission across reads and mutations. |
| Next acceptance slice | Batch One exited (see Batch One exit row). Batch Two's first admitted slice is not yet selected; it must come from `ROADMAP.md`'s Batch Two outcomes (Payers approval/monitoring workflows and Payers page; a certified real payer submission channel; stronger settlement evidence; or signed-record payer/contract validation, which is pilot-gated). |
| Batch One exit | **Closed 2026-10-28.** All `ROADMAP.md` Batch One Exit checklist items are evidenced: module DoD checks pass for Patients/Claims/Documents; cross-module tenant tests pass; the complete backend regression passes 520/520; an isolated PostgreSQL upgrade -> downgrade -> re-upgrade rehearsal against a disposable database ends at the sole live head `a1c7e4b9d2f3`; web type-check, ESLint, and the 26-route production build pass cleanly; `BUILD_STATUS.md`/`DATABASE_SCHEMA.md`/`API_SPEC.md` reflect shipped behavior; and the repository-owner commit checkpoint exists (`80b956c`, `1b79cf7`). This is an engineering checkpoint only — First Design-Partner Pilot, production object-storage, and hospital acceptance remain governed by `docs/release-plan.md`. |
| Login availability maintenance | **Implemented on 2026-08-18; does not advance the active batch.** The existing Authentication and Deployment owners now distinguish invalid credentials from unavailable sign-in infrastructure, restart local PostgreSQL unless stopped, and health-gate API/worker/beat startup on database readiness. The Compose model validates, PostgreSQL reports healthy, seeded login plus authenticated `/auth/me` succeeds, web type-check and the 26-route production build pass, and editor diagnostics are clean. No schema, migration, route, or owner change was required. The repository-owner checkpoint and cross-page responsive scenarios were both closed on 2026-10-28 (see Batch One exit row). |
| M1-PLT-01 progress | **Engineering acceptance complete on 2026-08-14; not pilot certified.** ADR 0003 now has the registered `branches/` owner with tenant-owned branches, parent-scoped departments and memberships, composite tenant-safe foreign keys, audited management APIs, branch-scoped operational Claim access, organization-currency snapshots, canonical import/export provenance, and fail-closed unknown or mismatched hierarchy codes. Owner/admin Settings administration and branch-dependent Claim creation selectors pass desktop and 390px browser acceptance. The complete backend regression passes 533/533 after reconciling inherited test-path, document-storage compatibility, integration-mapping, payer-audit, and tenant-classification gaps; focused Ruff passes with inherited typing-modernization rules excluded; web type-check, production build, and editor diagnostics pass. PostgreSQL upgrade/downgrade/re-upgrade passed with one Alembic head `d5a8c1f3e7b9`; contracts agree at 72 tables and 241 operations. Downstream branch routing/reporting remains separately scheduled and pilot administration evidence remains external. |
| Current engineering checkpoint | **Verified 2026-10-28; superseded by the Batch One exit row above.** Restored registration of existing API routers and Branch ORM models, completed the referenced audit-action registry, added typed document S3/scanner configuration with production fail-closed validation, and reconciled API/schema manifests to 223 operations and 66 registered tables (carried over from 2026-10-27). This pass additionally closed a tenant-isolation gap: `departments.organization_id` and `branch_memberships.organization_id` carried only composite foreign keys to `branches`/`users` and were missing the direct `organizations.id` foreign key that every other directly tenant-owned table (including `claims`, which keeps both) requires; migration `a1c7e4b9d2f3` adds the missing direct foreign keys as defense in depth, alongside the model and `DATABASE_SCHEMA.md` updates. It also added the previously-missing `tasks.reconcile_recovery_lifecycles` Celery beat task (opens/synchronizes a recovery lifecycle account for every claim with a recovery case, system-attributed and idempotent across reruns) and a `Settings` validator that fails closed when `APP_ENV=production` is combined with local document storage or disabled malware scanning. The complete backend regression now passes in full: **520 passed, 0 failed** (`pytest tests/`, ~19 minutes). Changed Python files pass scoped Ruff and editor diagnostics (two pre-existing, unrelated Ruff findings in `app/workers/tasks.py` functions this change did not touch were left as-is). Alembic has exactly one head, `a1c7e4b9d2f3`, confirmed by `alembic heads` and `test_alembic_has_exactly_one_head`. No web/frontend files changed this pass, so web type-check/lint/build were not rerun. The repository-owner checkpoint is complete: this pass's evidence is recorded in the repository's first commit, `80b956c` (2026-10-28, root commit). Remaining cross-page responsive browser scenarios were re-verified and closed later the same day (see the Cross-page responsive browser acceptance and Batch One exit rows). |
| Cross-page responsive browser acceptance | **Re-verified live on 2026-10-28.** With the full stack running (`docker compose` Postgres/Redis/ClamAV/API/worker/beat plus `next dev`), `tests/e2e/batch-one-workflow.spec.ts` was executed live against the seeded demo account, proving the canonical Patient -> Claims -> Documents navigation, search-control visibility, and no-horizontal-overflow assertions on both `desktop-chromium` (1440x900) and `mobile-chromium` (390x844): 2 passed. A first attempt showed one transient "sign-in service unavailable" desktop failure immediately after container restart (API/DB still warming up); two subsequent full reruns both passed 2/2, so this is recorded as container-startup flake, not a regression. No source files changed to produce this evidence. |
| M1-CLM-01 progress | **Engineering acceptance complete on 2026-08-14; not pilot certified.** Existing versioned mapping profiles and PHI-minimized row errors are now joined by explicit failed/partial sync retry that re-fetches through the registered connector, corrected Celery actor/trigger propagation, canonical tenant-scoped CSV export under the new `export_claims` permission, mandatory export reasons, aggregate audit evidence, spreadsheet-formula neutralization, canonical round-trip proof, and claim-update actor/reason/before/after/correlation evidence. Focused and adjacent Claims/import/integration/architecture regressions pass 57/57; focused Ruff passes with only inherited typing-modernization rules excluded; editor diagnostics are clean. The executable API and `API_SPEC.md` agree at 234 operations. No schema or migration change was required; Alembic remains recorded at one head `c4f9a2e7b1d6`. Signed hospital mappings, authorized representative samples, and production-like workflow acceptance remain First Design-Partner Pilot evidence. |
| Batch One event-flow validation | **Engineering acceptance complete on 2026-08-15.** The canonical Patient-to-Claim-to-Document integration now proves the ordered tenant-attributed event flow `patient.created` -> `claim.created` -> `workflow.transitioned` -> `document.uploaded`, including entity identifiers and correlation envelopes. Direct API claim creation no longer mislabels its event as an import, and document upload publishes only after its transaction commits. The focused test passes 1/1, adjacent Claims/Documents/events/workflow regressions pass 120/120, the complete backend suite passes 533/533 including architecture contracts, focused Ruff and editor diagnostics pass, and web type-check plus the 24-route production build pass. No route, schema, migration, or ownership change was required. Cross-page responsive browser scenarios and the repository-owner checkpoint were both closed on 2026-10-28 (see Batch One exit row). |
| Administration UI maintenance | **In progress on 2026-08-15; does not advance the active batch.** `/administration` now provides owner/admin-only navigation, live Team invitation/member visibility, Branch/Department/membership administration, and links to canonical Governance, Integrations, and Workflows. Direct access renders a denied state for other roles, personal account details remain under `/settings`, and no backend route, table, or business owner was added. Web type-check and the 25-route production build pass; live desktop and 390x844 browser acceptance confirms canonical data loading, role-gated navigation/direct access, usable stacked controls, and no page-level horizontal overflow. The repository-owner checkpoint and cross-page responsive scenarios were both closed on 2026-10-28 (see Batch One exit row). |
| Platform administration maintenance | **Implemented on 2026-08-15; does not advance the active batch or establish pilot readiness.** ADR 0006 and the registered `platform_admin/` owner establish a separate Atlas-company control plane at `/atlas-admin`, protected by `User.is_superuser` in both application routing and the API dependency. The first CEO/Founder, Operations, and Platform views use audited aggregate-only customer, claim, verified-recovery, invoice, AI-cost, integration, and health projections; totals remain separated by currency, confidential hospital records are excluded, and unsupported MRR/ARR, support, customer-health, and infrastructure telemetry is explicitly unavailable. Hospital users receive HTTP 403 from both platform endpoints and cannot render the Atlas shell; superusers are redirected away from the hospital portal. Focused authorization/privacy/currency/audit tests pass 3/3, architecture contracts pass 4/4 at 243 operations, scoped Ruff, web type-check, the 26-route production build, and editor diagnostics pass. Live desktop and 390px acceptance covers all three views with no page-level horizontal overflow. No schema or migration change was required. The repository-owner checkpoint and cross-page responsive scenarios were both closed on 2026-10-28 (see Batch One exit row). |
| Whole-product UI foundation | **Implemented on 2026-08-15; does not advance the active batch.** Atlas now uses a shared Manrope typography system, warm neutral surface tokens, restrained teal actions, a refined hospital navigation/header shell, canonical responsive page containers, and one reusable metric-card vocabulary across the hospital Recovery Command Center, Executive Command Center, and Finance Intelligence. The separate Atlas-company control plane now uses a compact operator bar, explicit freshness controls, denser information hierarchy, readable infrastructure states, and mobile customer summaries rather than a compressed desktop table. Authentication inherits the same product typography and tokens without adding decorative marketing content. Web type-check and the complete 26-route production build pass; editor diagnostics and diff hygiene are clean. Live 1440px and 390px acceptance covers login, hospital dashboard, Claims, Finance Intelligence, and Atlas platform administration with no page-level horizontal overflow. This is a shared foundation and representative acceptance, not a claim that every workflow received bespoke browser review. The repository-owner checkpoint and cross-page responsive scenarios were both closed on 2026-10-28 (see Batch One exit row). |
| Copilot usability maintenance | **Implemented on 2026-08-15; does not advance the active batch.** The registered `copilot/` owner now guides underspecified messages with concise clarification and API-provided one-click questions instead of repeating a static capability paragraph. Grounded follow-ups retain tenant/user-scoped evidence, navigation, and explicit write confirmation, and conversations opened with a vague greeting are retitled from the first grounded request. The hospital Copilot UI renders the suggestions without changing the HTTP contract. Focused Copilot tests pass 13/13, scoped Ruff, web type-check, the complete 26-route production build, and editor diagnostics pass. Live desktop and isolated 390px browser acceptance confirms suggested prompts, a grounded 32-claim result with evidence/navigation, a visible composer, and no page-level horizontal overflow; deployed API acceptance additionally confirms six fallback suggestions, `pending_appeals` execution, and the updated title `Show pending appeals`. No schema, migration, route, or owner change was required. The complete backend regression was not rerun for this maintenance slice. The repository-owner checkpoint and cross-page responsive scenarios were both closed on 2026-10-28 (see Batch One exit row). |
| M1-DOC-04 progress | **Engineering acceptance complete on 2026-08-14.** Implementation includes Tesseract-backed OCR status/engine/version/confidence evidence, tenant-attributed `AIGateway` classification with provider/model/prompt provenance, pending human review, audited accept/correct behavior, and explicit unavailable-provider handling. A deterministic, PHI-free evaluator enforces corpus sample minimums, classification accuracy, OCR word accuracy, and OCR success rate; its local JSON runner emits aggregate evidence only and fails when a threshold is missed. Evaluator/CLI tests pass 8/8, and Documents, evaluator, adjacent Appeals, and architecture regressions pass 52/52; focused Ruff and diagnostics pass. The rebuilt Python 3.11 image passes synthetic Tesseract OCR and live OpenAI classification with tenant-attributed usage. PostgreSQL rehearsal previously passed with one head `c4f9a2e7b1d6`. Authorized-corpus measurement and sign-off remain First Design-Partner Pilot evidence and are not represented as completed. |
| Compatibility gap found | The current source snapshot contains `document_versions` persistence but no registered document-version HTTP routes despite prior ledger claims. `API_SPEC.md` was reconciled to the executable 232-operation API; restoring those public operations requires the original immutable-version service behavior and focused compatibility tests, not placeholder routes. |
| Schema decision | `document_versions` remains the parent-scoped immutable-history table for stable tenant-owned document identity. `document_holds` extends the same owner as append-only parent-scoped hold history with non-null `organization_id` for defense in depth. No parallel document store or policy engine was introduced. |
| Blockers | Batch One engineering remains open on the repository-owner checkpoint and any remaining cross-page responsive browser scenarios. Authorized claim/document validation, production object-store certification, and restore evidence remain explicit pilot-readiness gates; they do not block continued engineering and must not be reported as complete. Batch Two still begins only after the Batch One engineering checkpoint exits. |
| M1-DOC-02 validation | On 2026-08-05, final Documents and adjacent storage tests pass 28/28 under the Python 3.11 API image; architecture contracts pass 4/4 with 68 registered tables, 229 HTTP operations, and one Alembic head `a2d7e4c9f1b6`; PostgreSQL upgrade, downgrade to `f0c8a3d6e1b4`, and re-upgrade pass; focused Ruff, editor diagnostics, contract counts, and `git diff --check` pass. The canonical Documents owner was extended; no ADR or new first-class module was required. |
| M1-DOC-03 validation | On 2026-08-05, Documents, Governance, and storage regressions pass 41/41 under the Python 3.11 API image, including cross-tenant, denied-clinical-access, hold precedence, dry-run/enforcement, manual tombstone, and storage-failure behavior. Architecture contracts pass 4/4 with 69 registered tables, 233 HTTP operations, and one Alembic head `b3e8f5a1c7d9`. PostgreSQL upgrade, downgrade to `a2d7e4c9f1b6`, and re-upgrade pass. Focused Ruff passes. The registered Documents, Governance, and Security owners were extended; no ADR or new first-class module was required. |
| Last validation | M1-DOC-01 storage contracts 6/6 and the complete touched/adjacent regression 31/31 remain the active-slice evidence. On 2026-08-04, a synthetic claim completed live OpenAI `gpt-4.1-mini` analysis through `AIGateway` and Celery, rendered on Claim detail, persisted tenant/claim-attributed token and estimated-cost evidence, and produced an append-only decision. AI pipeline tests pass 5/5; Decision Intelligence plus architecture contracts pass 26/26; focused Ruff and touched-file editor diagnostics pass. PostgreSQL and Alembic have one head, `f0c8a3d6e1b4`, after timestamp-default repairs for AI usage and decision evidence. Appeal-submission maintenance now distinguishes connector-backed electronic delivery from externally completed manual submission, requires payer confirmation evidence for manual records, fails closed when no electronic route is configured, and keeps submission actions in the canonical Claim workflow; focused and adjacent Appeals/Submission tests pass 61/61, architecture contracts pass 4/4, and web type-check/production build plus desktop and 390px browser acceptance pass. The legacy record renders as unverified and is excluded from submitted metrics. Kenya-first maintenance now defaults new tenants to KE/Africa-Nairobi/KES, rejects and suppresses mock/sandbox submission transports outside development/test, and prohibits demo seeding in production. Active tenant 1 was migrated through audited organization APIs to KE/Africa-Nairobi/KES with settings version 1; a missing fee-schedule dispute-period argument found by that live update was repaired and covered. Adjacent registration/organization/submission/connectivity/seed tests pass 39/39, focused connector discovery passes 1/1, and Alembic remains at `f0c8a3d6e1b4`. Local records remain synthetic; real-data certification still requires authoritative design-partner inputs and connector evidence. This maintenance evidence does not advance the active Documents slice; the next action remains `M1-DOC-02`. |
| Kenya payer maintenance | Active tenant 1 now has 11 Kenya-relevant synthetic payer records, updated in place through the canonical audited Payers API; all 108 existing claim links retain their payer IDs. Routes remain manual with no invented credentials, contracts, tariffs, or official routing identifiers. Demo fixtures use SHA, Jubilee, AAR, CIC, and Britam; the 17-row denial starter catalog has no unsourced payer affinities; generated appeals no longer auto-inject US CMS citations; and Claim Evidence no longer presents CMS/LCD/NCD or cross-tenant success as confirmed evidence. Payer/appeal/seed/denial/AI regressions pass 56/56, architecture contracts pass 4/4, payer audit tests pass 6/6, Ruff and editor diagnostics pass after scoped cleanup, web type-check/production build pass, and browser acceptance confirms Kenya payer names, KSh values, and fail-closed evidence labels. This does not certify any payer relationship or advance the active Documents slice; the next action remains `M1-DOC-02`. |
| Appeal edit maintenance | Draft and in-review appeal letters are editable and explicitly saved before approval. Saves persist full text and section maps as a new immutable version and write tenant/actor-attributed `appeal.edited` audit evidence; review and approval controls block while browser changes are unsaved, and approved or later appeals reject edits with HTTP 409. Both simple and sectioned generation now require supplied Kenya-applicable sources, prohibit invented payer/US-policy citations, and format amounts as KES. Lifecycle and prompt-contract tests pass 24/24, API persistence/audit tests pass 6/6, adjacent appeal and architecture tests pass 29/29, scoped Ruff and editor diagnostics pass, web type-check and production build pass, and Alembic remains one head `f0c8a3d6e1b4`. Live browser acceptance created draft appeal 5, blocked review while text was dirty, saved reviewer text as version 2, verified it through the tenant API, and left it unapproved. No schema migration or new owner was required. This maintenance does not advance the active Documents slice; the next action remains `M1-DOC-02`. |
| Payment evidence maintenance | Claim Payment Tracking and the Payments ledger now derive state only from canonical appeal, submission, matched payment, verified recovery, and invoice evidence. AI estimates no longer appear as received cash; payment receipt, finance verification, and invoicing remain separate stages. Claim tracking uses `VIEW_CLAIMS`, is tenant-scoped, and refreshes every five seconds while active or backgrounded; this is near-real-time polling, not guaranteed real-time delivery. The legacy direct outcome route returns HTTP 410 instead of manufacturing payment, recovery, invoice, timeline, audit, workflow, or event state. Recovery probability fallback values are normalized from 0-1 to percentage points before priority display. Focused lifecycle and tenant tests pass 3/3, adjacent payment/submission/recovery/claim regressions pass 44/44, architecture contracts pass 4/4, scoped Ruff and web type-check/production build pass. Browser acceptance on claim 109 confirms the KSh 23,562 projection remains only under Recovery Analysis, all unsupported financial stages remain pending, and the refresh timestamp advances across polling intervals; the Payments page reports KSh 0 recovered and labels its canonical table as matched payment evidence. No schema migration or new owner was required. This maintenance does not advance the active Documents slice; the next action remains `M1-DOC-02`. |

## Update Protocol

At the end of every implementation session:

1. Update Current Work with the exact completed acceptance slice and next slice.
2. Change a module state only when the Status Rules are met.
3. Link or name focused tests, adjacent regressions, lint/type/build checks, migration
   head, browser checks, and diagnostics in the session/PR evidence.
4. Update `docs/release-plan.md` only when readiness evidence changes.
5. Do not record line counts as progress. Working, secure, tested product behavior is
   the measure.