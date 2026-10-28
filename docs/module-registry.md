# Atlas Master Module Registry

## Purpose

This registry is the source of truth for domain ownership. Check it before creating
any package, model, service, repository, router, worker, page, or integration.
Existing owners are extended; parallel implementations are not created merely to
use a different name or folder structure.

The production backend root is `apps/api/app/`. The repository-root `app/` tree is
legacy and is not imported by the API image. Do not add production code there.
The production web root is `apps/web/src/`.

## Required Pre-Build Decision

Before implementation, record these answers in the issue, pull request, or working
notes:

1. Which registered module owns the business behavior?
2. Which existing model, repository, service, route, event, worker, or page was checked?
3. Why can the behavior not be added to that owner, if a new module is proposed?
4. Does the change require a new table, or can an existing aggregate own the data?
5. Which compatibility or legacy surface must remain unchanged?

A new first-class module requires an update to this registry and an ADR explaining
why no existing owner can safely contain the capability. Different terminology,
a new transport, or a new UI view is not sufficient justification.

## Canonical Owners

| Capability | Canonical owner | Primary entrypoint or responsibility | Extension rule |
|---|---|---|---|
| Authentication | `api/v1/auth.py`, `security/`, `services/auth_service.py` | Registration, login, credentials, JWT and auth dependencies | Extend these files until an approved migration creates a dedicated `auth/` package. Do not create another identity stack. |
| Organizations | `organizations/` | Tenant lifecycle, settings and entitlements | All tenant configuration extends this owner or a typed domain setting referenced by it. |
| Users and RBAC | `api/v1/users.py`, `security/` | Membership, invitations, roles and permissions | Do not add a second user or permission model. A future `users/` package must migrate these paths deliberately. |
| Branches and departments | `branches/`, governed by ADR 0003 | Tenant-owned branch hierarchy, departments, memberships, and branch access scope | Extend this owner for branch administration and membership policy. Claims snapshot branch/department/currency in `claims/`; downstream modules consume that context without duplicating hierarchy tables. |
| Patients | `patients/`, existing ORM in `models/patient.py`, claim/import boundaries | Tenant patient identity, authenticated CRUD API, and patient lookup used by claims | Extend this owner over the existing `patients` table. Do not create a competing patient store or bypass its repository from other modules. |
| Claims | `claims/`, `imports/`, `processing/`, `validation/`, `canonical/` | Claim CRUD, canonical ingestion, validation and processing | Claim business behavior belongs in `claims/`; source normalization belongs in `canonical/` or `imports/`; orchestration belongs in `processing/`. |
| Denials and knowledge | `models/denial.py`, `models/denial_code.py`, `api/v1/denial_codes.py`, `repositories/denial_code_repository.py` | Denial records and governed denial-code knowledge | Extend the existing models and API. A future package move is a migration, not a second denial catalog. |
| Documents | `documents/` | Upload, extraction, evidence and document lifecycle | Add formats and extraction adapters here; do not create claim-specific document stores. |
| Payers | `payers/` | Tenant payer registry, contracts, rules and capabilities | This is the payer source of truth. Vendor connectivity remains in `integrations/` or `payer_connectivity/`. |
| Appeals | `appeals/` | Generation, evidence, versions, human review and approval | Extend the existing appeal lifecycle. AI generation still routes through `ai/` and `AIGateway`. |
| Payer submissions | `submissions/`, `payer_connectivity/` | Human-triggered submission records, transport routing, polling and payer responses | `submissions/` owns domain state; `payer_connectivity/` adapts payer channels. Never submit automatically from generation or approval. |
| Payments | `payments/` | Canonical payment evidence, idempotency, matching and reconciliation | Every payment source converges here. Add source adapters elsewhere, but do not create `claim_payments` or a second matcher. |
| Recovery engine | `recovery/`, `recovery_workspace/` | Recovery scoring, lifecycle accounts, work queue and recommendations | Extend this owner for recovery decisions and operational state. |
| Recovery financial records | `recoveries/`, `models/recovery.py`, `models/recovery_attribution.py` | Payment-backed recovery evidence, verification, attribution, disputes and versions | Intentional split from `recovery/`. Extend this owner for financial evidence; do not merge casually or create another recovery ledger. |
| Invoices and recovery fees | `invoices/`, `billing/` | Success-fee schedules, invoice generation and invoice lifecycle | Hospital recovery invoices remain separate from future Atlas SaaS billing. |
| Finance intelligence | `finance/` | Financial projections, reconciliation summaries and governed reporting | Read from canonical claim/payment/recovery records; do not persist duplicate financial facts. |
| Tasks | `tasks/` | Human work queue, assignment, notifications and SLA state | Domain modules request work; task lifecycle remains here. |
| Configurable workflows | `workflow_engine/`, `workflows/` | Definition execution plus durable event-trigger inbox/actions | This is an intentional executor-versus-trigger split. Extend the relevant half; do not add a third workflow engine. |
| AI and agents | `ai/`, `agents/`, `decisions/`, `copilot/` | Provider gateway, specialized orchestration, decisions and user-facing Copilot | Provider calls go only through `AIGateway`. Extend an existing task/agent before adding one; AI never owns canonical financial facts. |
| Integrations | `integrations/`, `payer_connectivity/`, `webhooks/` | Registered vendor connectors, payer channels and inbound/outbound webhooks | Add adapters through existing interfaces. A connector class is not production-ready without real transport and contract tests. |
| Events and notifications | `events/`, `api/v1/notifications.py`, `webhooks/` | Domain event publication, SSE notifications and external delivery | Extend current event vocabulary and delivery paths; do not introduce a parallel event bus. |
| Analytics and reports | `dashboard/`, `finance/` | Operational dashboards, forecasts, executive and financial reports | Derive from canonical records. New views belong to the owning read model, not new duplicate ledgers. |
| Governance and audit | `governance/`, `audit/`, `api/v1/audit_logs.py` | Consent, retention, sessions, immutable audit evidence and access | Material mutations use the existing audit writer and governance controls. |
| Platform administration | `platform_admin/`, governed by ADR 0006 | Superuser-only, aggregate-first customer, Atlas business, AI cost, integration, and platform health control plane | Keep this separate from hospital Administration. Cross-tenant reads require explicit superuser authorization, privacy-safe projections, currency-safe aggregation, and privileged-access audit evidence. |
| MCP | `mcp/` | Tool exposure over existing domain services | MCP tools call canonical services; they never reimplement business behavior. |
| Background execution | `workers/` | Celery task entrypoints and schedules | Workers translate and invoke owning services. Business rules stay in domain services. |
| Shared platform | `core/`, `db/`, `middleware/`, `observability/`, `models/`, `schemas/` | Cross-cutting infrastructure and shared declarations | Do not place domain behavior here to avoid selecting an owner. Shared placement requires more than one genuine consumer. |

## Compatibility and Legacy Surfaces

- The repository-root `app/` directory is legacy/dead for production. Do not modify it
  for product work or import it from `apps/api/app/`.
- `apps/api/app/services/` and `apps/api/app/repositories/` contain compatibility and
  older wired surfaces. New domain behavior belongs in the registered owner. Move old
  behavior only with call-site tests and a backward-compatibility plan.
- Compatibility re-exports for submissions, recoveries, invoices, and organizations
  may remain until a documented removal milestone. Do not add new callers to them.
- `recovery/` versus `recoveries/`, and `workflow_engine/` versus `workflows/`, are
  intentional responsibility splits described above, not invitations to add more
  similarly named packages.

## Phase-Based Delivery

Atlas plans delivery by product capability rather than numbered sprints:

1. Foundation: identity, organizations and infrastructure.
2. Claims Core: patients, claims, documents and payers.
3. AI: prevention, appeals and governed knowledge.
4. Recovery: payments, reconciliation, recovery and invoicing.
5. Intelligence: dashboards, forecasting and reports.
6. Integrations: CSV/SFTP, email, HIS, SHA and payer APIs.
7. Production: testing, security, monitoring, deployment and real-user operations.

Phases describe readiness, not permission to rebuild earlier phases. Work starts from
the current implementation and closes the smallest verified gap end to end.

## Registry Maintenance

Update this file in the same change when ownership genuinely changes. A registry
update alone does not make a stub, model, route, connector, or page complete. Readiness
continues to be governed by `docs/definition-of-done.md` and `docs/release-plan.md`.
