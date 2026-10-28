# Tenant Architecture

## Standard

Atlas is a shared multi-tenant SaaS platform. An organization is the security,
configuration, integration, workflow, reporting, and billing boundary. A pilot
with one design partner does not permit single-tenant assumptions in code.

Tenant identity comes from one of these trusted contexts:

- authenticated user or API key;
- a persisted entity loaded by an internal scheduler;
- a signed, validated event or webhook envelope; or
- an internally created task envelope whose organization is revalidated against
  the loaded entity.

Client request bodies and query parameters are never authoritative sources of
organization identity.

## Persistence Classes

Every table must belong to exactly one class:

1. **Global platform data:** organization-independent reference or platform data.
   Current examples are `organizations` and the shared `denial_codes` catalog.
2. **Directly tenant-owned:** contains a non-null indexed organization foreign
   key. Claims, patients, users, analyses, appeals, documents, submissions,
   payments, recoveries, integrations, workflows, reports, and audit data belong
   here unless an approved ADR says otherwise.
3. **Parent-scoped:** contains a non-null foreign key to a tenant-owned aggregate
   and is only accessed through that ownership boundary. Claim lines and invoice
   lines are examples. This is deliberate ownership inheritance, not global data.

The executable classification lives in
`apps/api/tests/test_tenant_model_contract.py`. Adding a table without updating
and justifying its class fails CI.

## Execution Boundaries

- Repositories require organization context and scope every tenant query.
- Routers derive organization context from authentication and apply least-privilege
  RBAC. Cross-tenant identifiers return not found rather than disclosing existence.
- Background tasks do not trust a caller-supplied organization ID. They compare
  task context with persisted entity ownership before processing.
- Events include organization, correlation, event, and entity identifiers.
  Tenant event handlers skip or reject missing organization context.
- AI calls run through `AIGateway` with organization context. AI usage, model,
  prompt version, and generated artifacts remain attributable to one tenant.
- Integration credentials and settings are organization-owned and encrypted.
  Connector implementations are selected through registered interfaces.
- Object storage and cache keys include organization identity; authorization is
  still checked at read time.
- Reports and aggregates are generated from organization-scoped query roots.

## Organization Configuration

Tenant onboarding must not require a code change. Versioned, typed organization
configuration will cover:

- AI provider/model policy, prompt policy, tone, length, and approval controls;
- default connectors, payer mappings, and integration behavior;
- workflow definitions, thresholds, assignments, and escalation rules;
- recovery fee schedules and effective dates;
- currency, locale, language, and time zone;
- feature entitlements, limits, and rollout flags.

Credentials are not configuration values. They remain encrypted and access
controlled. Financial settings and policies use versioned relational records;
small presentation preferences may use a validated structured field.

## Financial Boundaries

Atlas maintains two distinct ledgers:

- **Recovery accounting:** payer payments and revenue recovered for an
  organization, recovery verification, success-fee calculation, and recovery
  statements. Existing `recoveries` and `invoices` implement this domain; they
  are not subscription billing.
- **Customer billing:** Atlas plans, subscriptions, entitlements, metered AI and
  storage usage, premium integration charges, customer invoices, payments,
  credits, and reconciliation. This is a separate future module.

Names, APIs, reports, and accounting entries must not conflate these domains.

## Verification

A tenant-owned feature requires:

- schema ownership constraints and indexes;
- repository and service scoping;
- authenticated API ownership checks;
- task, event, AI, integration, report, audit, cache, and storage context where
  applicable;
- positive same-tenant and negative cross-tenant tests;
- migration, rollback, observability, and security review evidence.