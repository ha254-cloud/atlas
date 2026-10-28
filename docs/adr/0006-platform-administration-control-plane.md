# ADR 0006: Platform Administration Control Plane

- Status: Accepted
- Date: 2026-08-15
- Owners: Platform operations, security, finance, and architecture
- Review date: Before production superuser access is enabled
- Related milestone: Production foundation

## Context

Hospital organization administrators operate one tenant. Atlas platform operators
need a different view of customer status, aggregate recovery value, Atlas fee
revenue, AI cost, integration failures, and system health across the service.
Reusing hospital Administration would blur authorization boundaries and encourage
unreviewed cross-tenant access.

Atlas already has `User.is_superuser`, but permission bypass alone is not a platform
administration policy. Company-wide reporting also cannot sum money across currencies
or treat projections, unmatched payments, or draft invoices as realized value.

## Decision

Create `apps/api/app/platform_admin/` as the canonical control-plane owner and
`/atlas-admin` as its separate frontend shell.

The first slice is read-only and aggregate-first:

- only authenticated users with `is_superuser=true` may call its API;
- hospital roles, including owner and admin, receive HTTP 403;
- customer summaries expose organization operating metadata and aggregate counts,
  never patient, document, claim-line, credential, or payment payloads;
- money is grouped by currency unless an approved conversion policy exists;
- recovered value uses verified `recoveries`; Atlas revenue uses recovery-fee
  invoices and is not presented as hospital revenue;
- AI cost remains in its recorded USD estimate until governed FX conversion exists;
- unavailable SaaS, CRM, support, and infrastructure telemetry is labeled unavailable
  rather than inferred or fabricated;
- every successful platform-admin read appends privileged-access audit evidence with
  actor, organization, correlation context, scope, and reason.

Platform superuser access does not implicitly authorize routine browsing of a
hospital's confidential records. Future support access requires a purpose-bound,
time-limited, audited impersonation or break-glass workflow with customer and legal
policy review.

## Consequences

- Atlas operators receive a distinct shell and authorization boundary.
- Hospital navigation and APIs remain tenant-scoped and unchanged.
- New platform metrics must extend this owner and document provenance.
- CRM, subscriptions, support tickets, feature rollout, infrastructure telemetry,
  and platform audit search remain separate acceptance slices; UI placeholders do
  not make those capabilities complete.
- No schema migration is required for the first read-only aggregate slice.

## Alternatives Considered

- **Reuse hospital Administration**: rejected because hospital admin and platform
  operator authority are materially different.
- **Use `require_permission`**: rejected because superuser bypass does not prove the
  caller is a platform operator.
- **Query tenant repositories without scope**: rejected because it weakens their
  ownership contracts. Global aggregate queries live only in `platform_admin/`.
- **Seed example business metrics**: rejected because synthetic values could be
  mistaken for Atlas financial or operational evidence.

## Rollback

Remove the platform-admin router and frontend shell, then disable superuser accounts.
No database downgrade is required. Existing privileged-read audit rows remain as
immutable governance evidence.