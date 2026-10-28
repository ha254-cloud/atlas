# Enterprise Multi-Tenant Platform

## Product Boundary

Atlas operates one shared platform for many hospitals. A hospital is an
`Organization`, and authenticated organization context is the only source of
tenant identity. Client-supplied organization IDs never select tenant data.

Organization onboarding uses `POST /api/v1/auth/register`. It creates the
organization, first administrator, email verification token, audit entry, and
initial settings revision in one transaction. The former organization-only
creation endpoint was removed because it could create orphan tenants.

## Organization Control Plane

The owning module is `app/organizations`:

```text
organizations/
  models.py
  schemas.py
  repository.py
  service.py
  entitlements.py
  router.py
```

Legacy organization model, schema, repository, service, and router imports are
compatibility re-exports. New code imports the owning module.

`Organization` is directly tenant-owned and stores the current operational
profile and validated settings snapshot. `OrganizationSettingsVersion` is
directly tenant-owned, append-only history with actor, reason, correlation ID,
and timestamp.

Typed settings cover:

- AI provider, model, temperature, and prompt version
- Workflow auto-analysis, auto-appeal, and mandatory human approval
- Submission connector, retries, and polling interval
- Recovery success fee, VAT, currency, payment terms, and invoice frequency
- Branding document references and primary color
- Product entitlements for AI, appeals, payments, analytics, Copilot, and portal automation

Human approval cannot be disabled. Financial setting changes append an
effective-dated Revenue Engine fee schedule in the same database transaction.
Same-day amendments remain append-only and the newest record wins.

## API

All routes below require authentication. Mutations require
`manage_organization`, which is granted only to organization owners and admins.

```text
GET   /api/v1/organizations/current
PATCH /api/v1/organizations/current
GET   /api/v1/organizations/current/settings
PUT   /api/v1/organizations/current/settings
GET   /api/v1/organizations/current/settings/history
GET   /api/v1/organizations/{organization_id}
```

Cross-tenant reads return `404`. Settings and profile mutations record before,
after, reason, actor, tenant, IP, user agent, and request correlation ID in the
audit trail. Dedicated audit columns remain part of the Audit Engine work; no
history is lost because the context is currently stored in immutable metadata.

## Entitlements

Feature checks are enforced at the API boundary for multi-agent analysis,
AI appeals, payment/recovery/invoice APIs, hospital analytics, and Copilot.
Permissions and entitlements are independent: a user must have both the RBAC
permission and the organization's purchased feature.

Background task and event entitlement enforcement is still required before the
platform is production-ready.

## Migration And Rollback

Migration `f7a2c9d4e6b1` adds organization profile/settings fields and immutable
settings history. Existing organizations are backfilled from their latest
recovery fee schedule where possible, with typed bootstrap defaults otherwise.

Downgrade is supported while no same-day recovery fee amendments exist. It
fails closed rather than deleting financial history if restoring the legacy
one-schedule-per-day constraint would be lossy.

## Sprint 15 Backend Roadmap

Status terms follow `docs/release-plan.md`.

1. **Organization control plane**: implemented. Enriched tenant profile,
   versioned typed settings, transactional registration, and tenant tests.
2. **Feature entitlements**: API enforcement implemented. Background tasks,
   events, and frontend navigation enforcement remain.
3. **Connector control plane**: implemented. Registered providers declare
   typed credential contracts; secret rotation is append-only and audited;
   expiry, bounded health checks, correlation logging, and cross-tenant
   contract tests are enforced. Real vendor certification remains a release
   milestone rather than a control-plane claim.
4. **Audit engine**: immutable tenant audit exists. Add dedicated correlation
   ID, user agent, before/after/reason fields, redaction policy, and export.
5. **Notification engine**: event-driven email exists. Add durable preferences,
   in-app inbox, webhook channel, retry/dead-letter handling, and templates.
6. **Document management**: tenant metadata and local object abstraction exist.
   Add S3-compatible storage, malware scanning, retention, legal hold, and audit.
7. **Analytics separation**: hospital analytics are tenant-scoped. Add a
   platform-only metrics store and APIs that never reuse hospital permissions.
8. **Internal admin**: add platform staff identity, audited support access,
   time-limited impersonation, subscriptions, health, usage, and incidents.
9. **Platform security and operations**: replace process-local rate limiting,
   add key rotation and secure sessions, evaluate PostgreSQL RLS, and complete
   backup/restore plus disaster-recovery rehearsal.

Each item closes only after its model/schema/repository/service/API or event
entrypoint, negative tenant tests, audit behavior, observability, migration,
documentation, and operational impact satisfy the Definition of Done.

## Kenya-First Product Sequence

The market sequence now prioritizes revenue recovery around the systems Kenyan
hospitals and payers actually expose:

1. **Payer registry and connector framework**: implemented control-plane slice.
   Tenant-scoped payer capabilities, audited configuration, connector binding, and
   claim-payer routing exist. Real insurer certification remains open.
2. **Hospital HIS import layer**: CSV and scheduled SFTP exist. Expand mapping,
   validation, reusable import profiles, and operational error handling before adding
   vendor APIs.
3. **Kenyan insurer submission workflows**: implement verified manual, portal, and
   email operating procedures first; add API/SFTP connectors only where contractual
   interfaces are available.
4. **Payment reconciliation**: canonical payment sources now include CSV, Excel,
   portal export, emailed report, API, SFTP, and manual entry. File-specific parsers and
   payer mapping profiles remain to be implemented.
5. **Kenya-aware intelligence**: version payer rules and prompts using reviewed local
   evidence, tenant configuration, and measured outcomes. Do not encode unsupported
   insurer behavior as model fact.