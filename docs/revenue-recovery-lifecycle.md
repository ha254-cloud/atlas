# Revenue Recovery Lifecycle Engine

## Purpose

The Revenue Recovery Lifecycle Engine accounts for each claim from original billed value through verified cash, contract adjustment, approved write-off, and closure. It is owned by the Revenue engine. It does not replace payment evidence, recovery attribution, or invoice eligibility.

The controlling invariant is:

```text
original billed amount = verified recovered cash + contract adjustments
                       + approved write-offs + outstanding amount
```

An account cannot enter `recovered` or `closed` while an amount remains unaccounted. Balances are projections over canonical claims, verified recoveries, and immutable lifecycle events; no mutable balance total is stored on the account.

## Data Ownership

- `recovery_accounts` is directly tenant-owned. Its non-null `organization_id` and claim uniqueness constraint establish one lifecycle account per tenant claim.
- `recovery_lifecycle_events` is directly tenant-owned and parent-bound to a recovery account. Events are append-only and uniquely sequenced per account.
- `Recovery` remains canonical verified cash evidence.
- `Payment` remains canonical payment evidence.
- Atlas fee snapshots are read from verified recoveries. Lifecycle activity never makes a recovery billable or creates an invoice.

Every repository query is scoped by the authenticated or task-derived organization. The API ignores client-supplied tenant identity. Cross-tenant account reads return not found.

## Lifecycle And Audit

Supported states are draft, submitted, under review, approved, partially paid, outstanding balance, appeal, recovered, written off, and closed. Services validate allowed transitions, optimistic versions, allocation limits, and closure accounting.

Each material operation appends an event containing organization, account sequence, before and after state, amount where applicable, actor, reason, timestamp, correlation ID, and idempotency key. User operations also use the platform audit service. Scheduled reconciliation records `actor_type=system` in the lifecycle ledger because no user initiated the work.

Verified recovery synchronization is idempotent by recovery ID. Allocation and transition retries are idempotent by caller key.

## API

All routes require authentication and tenant context.

| Permission | Routes |
|---|---|
| `analytics:read` | Account detail, portfolio, forecast, billing readiness |
| `claims:write` | Open account, transition, assign |
| `billing:write` | Contract adjustment and write-off allocation |

The Executive Command Center uses the portfolio and 90-day forecast projections. It shows only governed organization-level data; branch and department reporting remain unavailable until tenant-owned branch and membership models exist.

## Background Reconciliation

Celery Beat runs `tasks.reconcile_recovery_lifecycles` hourly. For each organization it:

1. Selects a bounded batch of tenant claims, prioritizing claims without accounts.
2. Opens missing accounts with a system actor.
3. Synchronizes verified recoveries into the immutable event ledger.
4. Commits per tenant and rolls back/logs failures without stopping other tenants.

`RECOVERY_LIFECYCLE_SYNC_BATCH_SIZE` controls the per-tenant batch size and defaults to 500. The task is a repair and bootstrap path; direct recovery verification remains the immediate transactional path.

## Security And Privacy

The module stores financial operations and claim references but introduces no new clinical document or patient fields. Logs contain organization IDs and failure classes, not payment payloads or PHI. RBAC separates analytics, workflow mutation, and billing allocation. Tests cover cross-tenant API denial and task-scoped tenant processing.

## Deployment And Rollback

Migration `c1e6a9d4f2b7` creates the account and event tables and must be applied before API or worker rollout. Deploy API first, then workers and Beat, then web. During rollback, disable the Beat schedule before rolling back application code. Database downgrade deletes lifecycle history and therefore requires an approved data-retention decision and backup; it is not a routine operational rollback.

Operational alerts should cover task failure by tenant, reconciliation lag, and repeated version or constraint failures. Those production alerts and a scheduler runbook remain open before pilot readiness.

## Known Limits

- Forecast confidence uses current payer timing evidence and has not been calibrated against a Kenyan design partner.
- Contract adjustments and write-offs require valid human reasons but do not yet implement a configurable approval matrix.
- Reversal, refund, dispute, credit-note, and bulk payment-allocation ledgers remain release blockers.
- No automatic invoice creation or fee eligibility change is performed.
