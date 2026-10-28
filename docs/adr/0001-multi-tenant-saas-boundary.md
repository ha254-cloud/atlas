# ADR 0001: Multi-Tenant SaaS Boundary

- Status: Accepted
- Date: 2026-08-01
- Owners: Architecture and security
- Review date: 2026-11-01
- Related milestone: M1/M2/M3

## Context

Atlas is a shared healthcare revenue-cycle platform, not a hospital-specific
deployment. Hospitals, clinics, laboratories, imaging centers, dental practices,
pharmacies, and revenue-cycle organizations may share one Atlas environment.
They require independent users, workflows, integrations, AI behavior, reporting,
and billing with no cross-organization data visibility.

The current schema uses integer organization keys. Most first-class records are
directly organization-owned; some child records inherit tenant ownership through
a non-null parent foreign key. Configuration is currently split between global
application settings, organization-scoped integrations/workflows, and hardcoded
defaults. Recovery invoices currently represent fees associated with recovered
hospital revenue; customer SaaS subscriptions are not implemented.

## Decision

1. `Organization` is the tenant security boundary. Tenant identity is derived
   from authenticated or trusted execution context, never request payload data.
2. Every persisted table is classified as:
   - global platform data;
   - directly tenant-owned, with a non-null organization foreign key; or
   - parent-scoped, with a non-null foreign key to a tenant-owned parent.
3. APIs, repositories, tasks, events, AI calls, integrations, caches, object
   storage paths, reports, audit records, and telemetry must preserve tenant
   context. Missing or conflicting context fails closed for tenant work.
4. New public organization identifiers use UUIDs. Existing integer primary and
   foreign keys remain internal during a staged compatibility migration. Key
   type alone is not an isolation control; authenticated scoping, constraints,
   tests, and database policy provide the security boundary.
5. Tenant behavior is configuration, not a code fork. Versioned organization
   settings will own AI policy, presentation preferences, fee schedules,
   currency/locale, feature entitlements, and integration/workflow defaults.
   Secrets remain in encrypted integration or secret storage, not settings JSON.
6. Recovery accounting and Atlas customer billing are separate bounded contexts:
   - Recovery accounting records payer payments, hospital recoveries, success
     fees, and recovery statements.
   - Customer billing records subscriptions, metered usage, storage and premium
     integration charges, customer invoices, and customer payments.
7. Human approval remains mandatory for AI-generated appeals. Tenant
   configuration may add stricter approvals but cannot disable this baseline.
8. A feature is not complete until its tenant ownership, configuration behavior,
   cross-tenant tests, audit behavior, and operational context are explicit.

## Alternatives Considered

- **Database per organization:** strong physical isolation, but operationally
  expensive for early scale and cross-tenant platform operations. It remains an
  option for contractual isolation tiers later.
- **Schema per organization:** migration and connection-pool complexity grows
  with tenant count and is not selected as the default.
- **Immediate integer-to-UUID rewrite:** rejected because rewriting every primary
  and foreign key creates substantial migration risk without independently
  preventing cross-tenant queries. UUID adoption will be staged.
- **One generic organization JSON document:** rejected for financial, policy,
  entitlement, and secret-bearing settings that require typing, versioning,
  constraints, audit history, or independent access controls.

## Consequences

- New tables fail the tenant model contract until explicitly classified.
- Tenant-owned query paths require negative cross-organization tests.
- Background jobs carry immutable tenant context and verify it against loaded
  entities before processing.
- Events and AI usage without tenant context are not valid tenant operations.
- Adding organization settings and customer billing requires separate models,
  migrations, services, APIs, permissions, audit events, and operational docs.
- Existing integer organization foreign keys remain supported during migration.

Migration will add stable public UUIDs first, update external contracts, then
evaluate foreign-key conversion separately. Rollback preserves internal integer
keys until all consumers and data have been verified.

## Validation

- `tests/test_tenant_model_contract.py` classifies every ORM table and validates
  direct or inherited ownership constraints.
- Repository and API tests attempt cross-organization reads and mutations.
- Task tests reject mismatched organization and entity ownership.
- Event and AI tests reject missing tenant context.
- PostgreSQL migration tests verify one Alembic head and required constraints.
- Security review includes manual attempts to cross organization boundaries.

## Intentional Debt

- **Risk:** Existing organization keys are integers and exposed by some legacy
  contracts. **Mitigation:** authenticated scope remains authoritative; add UUID
  public IDs before changing external contracts. **Owner:** platform engineering.
  **Removal condition:** all external organization references use UUIDs.
  **Target:** M2.
- **Risk:** Versioned organization settings and customer SaaS billing do not yet
  exist. **Mitigation:** global defaults remain explicit and release plan blocks
  production SaaS readiness. **Owner:** platform and revenue engineering.
  **Removal condition:** configured tenants onboard without code changes.
  **Target:** M2.